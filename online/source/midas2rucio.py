#!/usr/bin/env python3

import os
import subprocess
from datetime import datetime
import subprocess

import midas.client

import gspread

LOG = "/home/daq/DAQ/online/logs/rucio_upload.log"


def log(msg: str, dmp_on_file: bool = False) -> None:
    """Scrive una riga nel log con timestamp."""
    ts = datetime.now().isoformat(timespec="seconds")
    if dmp_on_file:
       with open(LOG, "a") as f:
          f.write(f"{ts} {msg}\n")
    else:
       print(f"{ts} {msg}\n") 

def ensure_headers(ws, header_list):
    first_row = ws.row_values(1)
    if not first_row:  # foglio vuoto
        ws.insert_row(header_list, 1)
        return header_list
    return first_row

def add_record(ws, header_list, record_dict):
    # Assicura che ci sia la riga di intestazione
    headers = ensure_headers(ws, header_list)

    # Converte il dict in una lista ordinata secondo gli header
    row = [record_dict.get(h, "") for h in headers]

    # Inserisce la riga in fondo
    ws.append_row(row)

def append_record_last(ws, headers, record_dict):
    headers = ensure_headers(ws, headers)
    row = [record_dict.get(h, "") for h in headers]

    # usa la colonna 1 (A) come riferimento "quante righe piene ci sono"
    colA = ws.col_values(1)  # include header in riga 1
    next_row = len(colA) + 1  # dopo l'ultima riga non vuota in col A

    ws.insert_row(row, next_row)

def main() -> int:

    HEADER = [
       "run", "description", "start_date", "start_epoch", "filename",
       "beam_status", "end_date", "end_epoch", "events",
       "end_description", "rucio_status"
    ]
    record = {key: "" for key in HEADER}
    gc = gspread.service_account(filename='/home/.logbook-478712-cffc1d289aa8.json')
# https://docs.google.com/spreadsheets/d/1dBHc4fwQgmx092ohra6Y-ueF_BpOPVk26BNhi5dCRnM/edit?usp=sharing
    sh = gc.open_by_key('1dBHc4fwQgmx092ohra6Y-ueF_BpOPVk26BNhi5dCRnM')
    worksheet = sh.worksheet("log")


    # Leggi info da ODB
    c = midas.client.MidasClient("midas2rucio")
    try:
        name        = c.odb_get("/Logger/Channels/0/Settings/Current filename")
        data_dir    = c.odb_get("/Logger/Data dir")
        record['run']         = c.odb_get("/Runinfo/Run number")
        record['description'] = c.odb_get("/Experiment/Run Parameters/Run description")
        record['start_date']  = c.odb_get("/Runinfo/Start time")
        record['start_epoch'] = c.odb_get("/Runinfo/Start time binary")
        record['end_date']    = c.odb_get("/Runinfo/Stop time")
        record['end_epoch']   = c.odb_get("/Runinfo/Stop time binary")
        record['beam_status'] = ""
        record['events']      = c.odb_get("/Logger/Channels/0/Statistics/Events written") 
        record['end_description'] = ""
        record['write']       = c.odb_get("Logger/Write data")
        record['rucio_status']= -1

        # to be sure to get right file information
        c.odb_set("/Custom/Rucio run status", 1)

    except Exception as e:
        print('ERROR: ', e)
        c.disconnect()
        return 1

    if not name:
        log("ERROR: /Logger/Channels/0/Settings/Current filename è vuoto, esco.")
        return 1

    if not data_dir:
        data_dir = ""

    # Costruisci path completo del file
    full_path = os.path.join(data_dir, name)

    log(f"Compressing: {full_path}")

    try:
        # Adatta la firma di msg() alla tua versione, se necessario)
        c.msg("INFO: Compressing file {:s}".format(full_path))
    except Exception as e:
        print('ERROR: ', e)
        c.disconnect()
        return 1

    try:
        result = subprocess.run(
            ["gzip", full_path],
            check=True,
            capture_output=True,
            text=True
        )
        log("Compressione riuscita!")
    except subprocess.CalledProcessError as e:
        log("❌ Errore durante la compressione!")
        log("Return code:", e.returncode)
        log("Stderr:", e.stderr)
        return 1

    log(f"Uploading: {full_path}")
    
    full_path=full_path+".gz"
    name=name+".gz"
    record['filename']    = name

    try:
        # Adatta la firma di msg() alla tua versione, se necessario
        c.msg("INFO: Uploading file {:s}".format(full_path))
    except Exception as e:
        print('ERROR: ', e)
        c.disconnect()
        return 1
    if record['write']==1:
        # Comando docker per RUCIO
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            "/home/.rucio.cfg:/home/.rucio.cfg",
            "-v",
            f"{full_path}:/app/{name}",
            "gmazzitelli/rucio-uploader:v0.2",
            "--file",
            f"/app/{name}",
            "--bucket",
            "cygno-data",
            "--did_name",
            f"FLASH/QUAX/TEST/{name}",
            "--upload_rse",
            "CNAF_USERDISK",
            "--transfer_rse",
            "T1_USERTAPE",
            "--account",
            "rucio-daq",
        ]

        log("Running: " + " ".join(docker_cmd))

        # Esegui docker e appendi stdout/stderr al log
        result = subprocess.run(docker_cmd, capture_output=True, text=True)

        #| Exit Code | Meaning                                            |
        #| --------- | -------------------------------------------------- |
        #| 0         | Upload and replica created (or both already exist) |
        #| 1         | File already uploaded, replica just created        |
        #| 2         | Upload failed                                      |
        #| 3         | Upload done, replica failed                        |
        #| 4         | Client configuration error                         |

        rucio_status = result.returncode
        record['rucio_status']=rucio_status
    
        # Messaggio MIDAS: upload finito
        try:
            if (rucio_status==0 or rucio_status==1):
               c.msg("INFO: RUCIO upload DONE for {:s}".format(full_path))
            else:
               c.msg("ERROR: RUCIO upload FAIL for {:s}".format(full_path))
        except Exception as e:
            print('ERROR: ', e)
            c.disconnect()
            return 1
        try:
            append_record_last(worksheet, HEADER, record)
        except Exception as e:
            print('ERROR: ', e)
            log("ERROR Uploading logbook")
    else:
        record['description']="none"
        record['filename']   ="none"
        record['events']     =0
#
# spostato dentro, se qui applica il none.
#    try:
#        add_record(worksheet, HEADER, record)
#    except Exception as e:
#        print('ERROR: ', e)
#        log("ERROR Uploading logbook")

    c.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
