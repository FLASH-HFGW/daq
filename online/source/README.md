# Rucio Re-Upload Monitor

## Overview

This script monitors compressed MIDAS run files (`run*.mid.gz`) in: ```/home/cold/data```

and ensures their upload status to Rucio is consistent with the experiment log stored in a Google Sheet.

If a file has not been successfully uploaded, the script automatically retries the upload and updates the logbook.

---

## How It Works

1. Scans the data directory for `run*.mid.gz` files.
2. Matches each file against the Google Sheet using the `filename` column.
3. Checks the `rucio_status` field:
   - `0` or `1` → Upload already successful (no action).
   - Any other value → Re-attempt upload.
4. Executes the upload via the Docker-based Rucio uploader.
5. Updates:
   - `rucio_status`
   - `rucio_messages` (timestamped summary).

---

## Rucio Exit Codes

| Code | Meaning |
|------|----------|
| 0 | Upload and replica created (or already exist) |
| 1 | File already uploaded, replica created |
| 2 | Upload failed |
| 3 | Upload succeeded, replica failed |
| 4 | Configuration error |

Codes `0` and `1` are treated as successful states.

---

## Requirements

- Google service account credentials
- Access to the target Google Sheet
- Docker installed
- `gmazzitelli/rucio-uploader:v0.2` image available

---

## Typical Use

Designed to be executed periodically (e.g., via cron) to maintain consistency between:

- Local DAQ storage
- Rucio storage
- Experiment logbook
