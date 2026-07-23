#!/usr/bin/env python3

import os
import re
import argparse
from datetime import datetime
from typing import Dict, Any, Optional, List

import gspread


# ----------------------------------------------------------------------
# Default configuration
# ----------------------------------------------------------------------

DEFAULT_DATA_DIR = "/home/cold/data/"
DEFAULT_LOG_DIR = "/home/cold/daq/online/logs/"

# Google Sheet
SERVICE_ACCOUNT_JSON = "/home/.logbook-478712-cffc1d289aa8.json"
SHEET_KEY = "1dBHc4fwQgmx092ohra6Y-ueF_BpOPVk26BNhi5dCRnM"
WORKSHEET_NAME = "log"

LOG_FILE: Optional[str] = None


# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------

def init_log(log_dir: str) -> str:
    """
    Crea il nome del logfile marcato con data e ora.

    Esempio:
        /home/cold/daq/online/logs/rucio_cleanup_20260721_184523.log
    """

    global LOG_FILE

    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    LOG_FILE = os.path.join(
        log_dir,
        f"rucio_cleanup_{timestamp}.log"
    )

    return LOG_FILE


def log(msg: str, dmp_on_file: bool = True, verbose: bool = True) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    line = f"{ts} {msg}"

    if verbose:
        print(line)

    if dmp_on_file and LOG_FILE:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")


# ----------------------------------------------------------------------
# Google Sheet helpers
# ----------------------------------------------------------------------

def parse_rucio_status(raw: Any) -> Optional[int]:
    """
    Converte rucio_status in int in modo robusto.

    Esempi:
        0, 0.0, "0", "0.0" -> 0
        1, 1.0, "1", "1.0" -> 1
        "", None, "nan"     -> None
    """

    if raw is None:
        return None

    s = str(raw).strip()

    if s == "" or s.lower() in {"nan", "none", "null", "n/a"}:
        return None

    try:
        return int(float(s))
    except Exception:
        return None


def ensure_local_file_column(ws) -> List[str]:
    """
    Verifica gli header del Google Sheet.

    Se la colonna 'local_file' non esiste, viene aggiunta
    automaticamente in fondo.

    Restituisce la lista aggiornata degli header.
    """

    headers = ws.row_values(1)

    if not headers:
        raise RuntimeError("Il Google Sheet non contiene una riga di header.")

    required = ["filename", "rucio_status"]

    missing = [h for h in required if h not in headers]

    if missing:
        raise RuntimeError(
            f"Colonne obbligatorie mancanti nello sheet: {missing}. "
            f"Header trovati: {headers}"
        )

    if "local_file" not in headers:
        new_col = len(headers) + 1

        log(
            f"Google Sheet: colonna 'local_file' non presente -> "
            f"aggiunta nella colonna {new_col}"
        )

        ws.update_cell(1, new_col, "local_file")

        headers.append("local_file")

    return headers


def find_col(headers: List[str], col_name: str) -> int:
    """
    Restituisce il numero di colonna Google Sheet (1-based).
    """

    try:
        return headers.index(col_name) + 1
    except ValueError:
        raise RuntimeError(
            f"Colonna '{col_name}' non trovata nello sheet. "
            f"Header: {headers}"
        )


def build_sheet_index(ws) -> Dict[str, Dict[str, Any]]:
    """
    Costruisce un indice:

        filename -> {
            "row": ...,
            "rucio_status": ...,
            "local_file": ...,
            "record": ...
        }

    Il filename atteso nello sheet è, per esempio:

        run00591.mid.gz
    """

    records = ws.get_all_records()

    index: Dict[str, Dict[str, Any]] = {}

    for i, rec in enumerate(records, start=2):

        fname = str(rec.get("filename", "")).strip()

        if not fname:
            continue

        index[fname] = {
            "row": i,
            "rucio_status": rec.get("rucio_status", ""),
            "local_file": rec.get("local_file", ""),
            "record": rec,
        }

    return index


def set_local_file_zero(
    ws,
    headers: List[str],
    row: int,
    filename: str
) -> None:
    """
    Imposta local_file=0 per la riga indicata.
    """

    col = find_col(headers, "local_file")

    ws.update_cell(row, col, 0)

    log(
        f"SHEET UPDATED: {filename} row={row} -> local_file=0"
    )


# ----------------------------------------------------------------------
# Run/file handling
# ----------------------------------------------------------------------

def normalize_run(run_arg: str) -> str:
    """
    Accetta:

        591
        00591
        run00591
        run00591.mid.gz

    e restituisce:

        run00591
    """

    value = str(run_arg).strip()

    if value.lower().startswith("run"):
        value = value[3:]

    for suffix in [
        ".mid.gz",
        ".mid.crc32c",
        ".crc32c",
    ]:
        if value.endswith(suffix):
            value = value[:-len(suffix)]
            break

    if not value.isdigit():
        raise ValueError(
            f"Numero di run non valido: {run_arg}"
        )

    return f"run{int(value):05d}"


def run_number(run_name: str) -> int:
    """
    Converte:

        run00591

    in:

        591
    """

    return int(run_name[3:])


def files_for_run(data_dir: str, run_name: str) -> List[str]:
    """
    Restituisce i tre possibili file associati al run:

        runXXXXX.mid.gz
        runXXXXX.mid.crc32c
        runXXXXX.crc32c
    """

    return [
        os.path.join(data_dir, f"{run_name}.mid.gz"),
        os.path.join(data_dir, f"{run_name}.mid.crc32c"),
        os.path.join(data_dir, f"{run_name}.crc32c"),
    ]


def discover_runs(data_dir: str) -> List[str]:
    """
    Cerca nella directory tutti i run che abbiano almeno uno
    dei file:

        runXXXXX.mid.gz
        runXXXXX.mid.crc32c
        runXXXXX.crc32c
    """

    patterns = [
        re.compile(r"^(run\d+)\.mid\.gz$"),
        re.compile(r"^(run\d+)\.mid\.crc32c$"),
        re.compile(r"^(run\d+)\.crc32c$"),
    ]

    runs = set()

    try:
        entries = os.listdir(data_dir)

    except OSError as e:
        raise RuntimeError(
            f"Impossibile leggere la directory {data_dir}: {e}"
        ) from e

    for fname in entries:

        for pattern in patterns:

            match = pattern.match(fname)

            if match:
                runs.add(match.group(1))
                break

    return sorted(
        runs,
        key=run_number
    )


# ----------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------

def cleanup_run(
    data_dir: str,
    run_name: str,
    sheet_index: Dict[str, Dict[str, Any]],
    ws,
    headers: List[str],
    dry_run: bool = False,
) -> Dict[str, int]:

    """
    Controlla il rucio_status del file:

        runXXXXX.mid.gz

    Cancella i file locali SOLO se rucio_status è 0 oppure 1.

    Dopo una cancellazione effettivamente riuscita, se nessuno dei
    file associati al run rimane localmente, imposta:

        local_file = 0

    nel Google Sheet.

    In modalità --dry-run il Google Sheet non viene modificato.
    """

    stats = {
        "removed": 0,
        "missing": 0,
        "skipped": 0,
        "errors": 0,
        "sheet_updated": 0,
    }

    mid_gz_name = f"{run_name}.mid.gz"

    paths = files_for_run(
        data_dir,
        run_name
    )

    # --------------------------------------------------------------
    # Controllo presenza nel Google Sheet
    # --------------------------------------------------------------

    if mid_gz_name not in sheet_index:

        log(
            f"SKIP: {run_name}: "
            f"{mid_gz_name} non presente nel Google Sheet"
        )

        stats["skipped"] += 1
        return stats

    row = sheet_index[mid_gz_name]["row"]

    raw_status = sheet_index[mid_gz_name]["rucio_status"]

    status = parse_rucio_status(raw_status)

    # --------------------------------------------------------------
    # Cancellazione consentita soltanto per status 0 o 1
    # --------------------------------------------------------------

    if status not in (0, 1):

        log(
            f"SKIP: {run_name}: "
            f"rucio_status='{raw_status}' "
            f"(parsed={status}), "
            f"cancellazione NON consentita"
        )

        stats["skipped"] += 1
        return stats

    log(
        f"OK: {run_name}: "
        f"rucio_status={status} -> "
        f"cancellazione locale consentita"
    )

    # Controlliamo se almeno un file esisteva prima
    existing_before = [
        path
        for path in paths
        if os.path.exists(path)
    ]

    if not existing_before:

        log(
            f"MISSING: {run_name}: "
            f"nessun file locale associato trovato"
        )

        stats["missing"] += len(paths)

        # Non modifichiamo local_file perché in questa esecuzione
        # non abbiamo effettivamente cancellato nulla.
        return stats

    # --------------------------------------------------------------
    # Cancella i tre possibili file
    # --------------------------------------------------------------

    for path in paths:

        if not os.path.exists(path):

            log(f"MISSING: {path}")

            stats["missing"] += 1
            continue

        if dry_run:

            log(f"DRY-RUN: rm {path}")

            stats["removed"] += 1
            continue

        try:

            os.remove(path)

            log(f"REMOVED: {path}")

            stats["removed"] += 1

        except OSError as e:

            log(
                f"ERROR: impossibile rimuovere {path}: {e}"
            )

            stats["errors"] += 1

    # --------------------------------------------------------------
    # Aggiornamento local_file nel Google Sheet
    # --------------------------------------------------------------

    if not dry_run and stats["removed"] > 0:

        remaining_files = [
            path
            for path in paths
            if os.path.exists(path)
        ]

        if not remaining_files:

            try:

                set_local_file_zero(
                    ws,
                    headers,
                    row,
                    mid_gz_name
                )

                stats["sheet_updated"] += 1

                # Mantiene coerente anche l'indice locale
                sheet_index[mid_gz_name]["local_file"] = 0

            except Exception as e:

                log(
                    f"ERROR: impossibile aggiornare local_file "
                    f"per {mid_gz_name}: {e}"
                )

                stats["errors"] += 1

        else:

            log(
                f"WARNING: {run_name}: "
                f"rimangono ancora {len(remaining_files)} "
                f"file locali -> local_file NON modificato"
            )

            for path in remaining_files:
                log(f"REMAINING: {path}")

    return stats


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Rimuove file locali di run solo se il relativo "
            "rucio_status nel Google Sheet è 0 oppure 1."
        )
    )

    parser.add_argument(
        "run",
        nargs="?",
        help=(
            "Singolo run. "
            "Esempi: 591, 00591, run00591"
        ),
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Controlla tutti i run presenti nella directory."
        ),
    )

    parser.add_argument(
        "--range",
        dest="run_range",
        nargs=2,
        metavar=("START", "END"),
        help=(
            "Intervallo inclusivo di run. "
            "Esempio: --range 590 600"
        ),
    )

    parser.add_argument(
        "--directory",
        "-d",
        default=DEFAULT_DATA_DIR,
        help=(
            f"Directory dei dati "
            f"(default: {DEFAULT_DATA_DIR})"
        ),
    )

    parser.add_argument(
        "--log-dir",
        default=DEFAULT_LOG_DIR,
        help=(
            f"Directory dei log "
            f"(default: {DEFAULT_LOG_DIR})"
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Mostra cosa verrebbe cancellato senza "
            "rimuovere file e senza modificare Google Sheet."
        ),
    )

    args = parser.parse_args()

    # --------------------------------------------------------------
    # Inizializzazione log
    # --------------------------------------------------------------

    try:

        logfile = init_log(
            os.path.abspath(args.log_dir)
        )

    except Exception as e:

        print(
            f"ERROR: impossibile creare il logfile: {e}"
        )

        return 1

    log(f"Log file: {logfile}")

    # --------------------------------------------------------------
    # Validazione modalità
    # --------------------------------------------------------------

    modes = sum([
        args.run is not None,
        args.all,
        args.run_range is not None,
    ])

    if modes == 0:

        parser.error(
            "specificare un singolo run, --range START END "
            "oppure --all"
        )

    if modes > 1:

        parser.error(
            "run, --range e --all sono mutuamente esclusivi"
        )

    data_dir = os.path.abspath(
        args.directory
    )

    if not os.path.isdir(data_dir):

        log(
            f"ERROR: directory non trovata: {data_dir}"
        )

        return 1

    log(f"Directory dati: {data_dir}")

    if args.dry_run:

        log(
            "***** DRY-RUN MODE: "
            "nessun file verrà cancellato e "
            "Google Sheet non verrà modificato *****"
        )

    # --------------------------------------------------------------
    # Collegamento Google Sheet
    # --------------------------------------------------------------

    try:

        gc = gspread.service_account(
            filename=SERVICE_ACCOUNT_JSON
        )

        sh = gc.open_by_key(
            SHEET_KEY
        )

        ws = sh.worksheet(
            WORKSHEET_NAME
        )

        # NOTA:
        # anche in dry-run manteniamo la filosofia di NON modificare
        # il Google Sheet.
        #
        # Pertanto se manca local_file:
        #   - normalmente viene aggiunta
        #   - in dry-run segnaliamo che manca ma non la aggiungiamo

        current_headers = ws.row_values(1)

        if args.dry_run:

            if "local_file" not in current_headers:

                log(
                    "DRY-RUN: la colonna 'local_file' "
                    "non esiste e verrebbe aggiunta al Google Sheet"
                )

                # Per le funzioni successive simuliamo la presenza
                headers = current_headers + ["local_file"]

            else:

                headers = current_headers

            required = [
                "filename",
                "rucio_status"
            ]

            missing = [
                h
                for h in required
                if h not in current_headers
            ]

            if missing:

                raise RuntimeError(
                    f"Colonne obbligatorie mancanti: {missing}"
                )

        else:

            headers = ensure_local_file_column(
                ws
            )

        sheet_index = build_sheet_index(
            ws
        )

    except Exception as e:

        log(
            f"ERROR: impossibile leggere/preparare "
            f"Google Sheet: {e}"
        )

        return 1

    log(
        f"Google Sheet caricato: "
        f"{len(sheet_index)} filename indicizzati"
    )

    # --------------------------------------------------------------
    # Determina i run da processare
    # --------------------------------------------------------------

    if args.all:

        try:

            runs = discover_runs(
                data_dir
            )

        except Exception as e:

            log(f"ERROR: {e}")
            return 1

        if not runs:

            log(
                "Nessun file run*.mid.gz / "
                "run*.mid.crc32c / "
                "run*.crc32c trovato."
            )

            return 0

        log(
            f"--all: trovati {len(runs)} "
            f"run locali da controllare"
        )

    elif args.run_range:

        try:

            start_name = normalize_run(
                args.run_range[0]
            )

            end_name = normalize_run(
                args.run_range[1]
            )

            start = run_number(
                start_name
            )

            end = run_number(
                end_name
            )

        except ValueError as e:

            log(f"ERROR: {e}")
            return 1

        if start > end:

            log(
                f"ERROR: range non valido: "
                f"{start} > {end}"
            )

            return 1

        runs = [
            f"run{n:05d}"
            for n in range(start, end + 1)
        ]

        log(
            f"--range: da run{start:05d} "
            f"a run{end:05d} "
            f"({len(runs)} run)"
        )

    else:

        try:

            run_name = normalize_run(
                args.run
            )

        except ValueError as e:

            log(f"ERROR: {e}")
            return 1

        runs = [
            run_name
        ]

    # --------------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------------

    total_removed = 0
    total_missing = 0
    total_skipped = 0
    total_errors = 0
    total_sheet_updated = 0

    for run_name in runs:

        result = cleanup_run(
            data_dir=data_dir,
            run_name=run_name,
            sheet_index=sheet_index,
            ws=ws,
            headers=headers,
            dry_run=args.dry_run,
        )

        total_removed += result["removed"]
        total_missing += result["missing"]
        total_skipped += result["skipped"]
        total_errors += result["errors"]
        total_sheet_updated += result["sheet_updated"]

    # --------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------

    action = (
        "would_remove"
        if args.dry_run
        else "removed"
    )

    log(
        f"Done. "
        f"runs_checked={len(runs)}, "
        f"{action}={total_removed}, "
        f"missing={total_missing}, "
        f"skipped_runs={total_skipped}, "
        f"local_file_updated={total_sheet_updated}, "
        f"errors={total_errors}"
    )

    return 1 if total_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())