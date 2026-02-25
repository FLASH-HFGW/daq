#!/usr/bin/env python3
import os
import glob
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

import gspread

DATA_DIR = "/home/cold/data/"
PATTERN = "run*.mid.gz"
LOG = "/home/cold/daq/online/logs/rucio_reupload.log"

# Google Sheet
SERVICE_ACCOUNT_JSON = "/home/.logbook-478712-cffc1d289aa8.json"
SHEET_KEY = "1dBHc4fwQgmx092ohra6Y-ueF_BpOPVk26BNhi5dCRnM"
WORKSHEET_NAME = "log"

# Header atteso (ORA include rucio_messages)
HEADER = [
    "run", "description", "start_date", "start_epoch", "filename",
    "beam_status", "end_date", "end_epoch", "events",
    "end_description", "rucio_status", "rucio_messages"
]

# --- logging ---
def log(msg: str, dmp_on_file: bool = True, verbose: bool = True) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    line = f"{ts} {msg}"
    if verbose:
        print(line)
    if dmp_on_file:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write(line + "\n")

# --- sheet helpers ---
def ensure_headers(ws, header_list: List[str]) -> List[str]:
    first_row = ws.row_values(1)
    if not first_row:
        ws.insert_row(header_list, 1)
        return header_list

    # Qui vogliamo che lo sheet sia coerente: niente fallback silenziosi.
    if first_row != header_list:
        raise RuntimeError(
            "Header sheet diverso da atteso.\n"
            f"Atteso: {header_list}\n"
            f"Trovato: {first_row}\n"
            "Allinea lo sheet oppure aggiorna HEADER nello script."
        )
    return first_row

def build_sheet_index(ws) -> Dict[str, Dict[str, Any]]:
    records = ws.get_all_records()
    index: Dict[str, Dict[str, Any]] = {}
    for i, rec in enumerate(records, start=2):
        fname = str(rec.get("filename", "")).strip()
        if not fname:
            continue
        index[fname] = {
            "row": i,
            "rucio_status": rec.get("rucio_status", ""),
            "record": rec
        }
    return index

def find_col(headers: List[str], col_name: str) -> int:
    try:
        return headers.index(col_name) + 1
    except ValueError:
        raise RuntimeError(f"Colonna '{col_name}' non trovata nello sheet. Header: {headers}")

def update_row_fields(ws, headers: List[str], row: int, updates: Dict[str, Any]) -> None:
    for k, v in updates.items():
        col = find_col(headers, k)
        ws.update_cell(row, col, v)

def parse_rucio_status(raw: Any) -> Optional[int]:
    """
    Converte rucio_status in int in modo robusto:
      - 1, 1.0, "1", "1.0", " 1 " -> 1
      - "" / None / "nan" / "N/A" -> None
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "" or s.lower() in {"nan", "none", "null", "n/a"}:
        return None
    try:
        return int(float(s))  # gestisce "1.0"
    except Exception:
        return None

# --- rucio upload ---
def rucio_upload_gz(full_path_gz: str) -> Tuple[int, str, str]:
    name = os.path.basename(full_path_gz)

    docker_cmd = [
        "docker", "run", "--rm",
        "-v", "/home/.rucio.cfg:/home/.rucio.cfg",
        "-v", f"{full_path_gz}:/app/{name}",
        "gmazzitelli/rucio-uploader:v0.2",
        "--file", f"/app/{name}",
        "--bucket", "cygno-data",
        "--did_name", f"FLASH/QUAX/TEST/{name}",
        "--upload_rse", "CNAF_USERDISK",
        "--transfer_rse", "T1_USERTAPE",
        "--account", "rucio-daq",
    ]

    log("Running: " + " ".join(docker_cmd))
    result = subprocess.run(docker_cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

# --- main flow ---
def list_data_files() -> List[str]:
    return sorted(glob.glob(os.path.join(DATA_DIR, PATTERN)))

def main() -> int:
    files = list_data_files()
    if not files:
        log(f"Nessun file trovato in {DATA_DIR} con pattern {PATTERN}")
        return 0

    log(f"Trovati {len(files)} file: primo={os.path.basename(files[0])} ultimo={os.path.basename(files[-1])}")

    gc = gspread.service_account(filename=SERVICE_ACCOUNT_JSON)
    sh = gc.open_by_key(SHEET_KEY)
    ws = sh.worksheet(WORKSHEET_NAME)

    headers = ensure_headers(ws, HEADER)
    sheet_index = build_sheet_index(ws)

    # colonne obbligatorie
    _ = find_col(headers, "filename")
    _ = find_col(headers, "rucio_status")
    _ = find_col(headers, "rucio_messages")

    retried = 0
    skipped_missing = 0
    skipped_ok = 0
    updated = 0

    for fpath in files:
        fname = os.path.basename(fpath)

        if fname not in sheet_index:
            skipped_missing += 1
            log(f"SKIP: {fname} non presente nello sheet.")
            continue

        row = sheet_index[fname]["row"]
        raw_status = sheet_index[fname]["rucio_status"]
        status = parse_rucio_status(raw_status)

        # OK se status in {0,1}
        if status in (0, 1):
            skipped_ok += 1
            log(f"OK: {fname} rucio_status={status} (row {row}) -> nessuna azione")
            continue

        retried += 1
        log(f"RETRY: {fname} (row {row}) rucio_status_raw='{raw_status}' parsed={status} -> provo upload")

        exit_code, out, err = rucio_upload_gz(fpath)

        now = datetime.now().isoformat(timespec="seconds")
        note = f"[{now}] reupload exit_code={exit_code}"
        if err:
            err_short = err.strip().splitlines()[-1] if err.strip().splitlines() else err.strip()
            note += f" stderr_last='{err_short[:200]}'"
        if out:
            out_short = out.strip().splitlines()[-1] if out.strip().splitlines() else out.strip()
            note += f" stdout_last='{out_short[:200]}'"

        try:
            update_row_fields(ws, headers, row, {
                "rucio_status": int(exit_code),
                "rucio_messages": note,
            })
            updated += 1
            log(f"UPDATED: {fname} row {row} -> rucio_status={exit_code}")
        except Exception as e:
            log(f"ERROR: update sheet per {fname} row {row}: {e}")

    log(f"Done. retried={retried}, updated={updated}, skipped_ok={skipped_ok}, skipped_missing={skipped_missing}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())