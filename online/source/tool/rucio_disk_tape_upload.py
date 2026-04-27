# MUST be first: silence urllib3 TLS warnings before rucio/requests import anything
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

import urllib3
urllib3.disable_warnings(InsecureRequestWarning)

import os
import sys
import argparse

from rucio.client.client import Client
from rucio.client.uploadclient import UploadClient
from rucio.client.replicaclient import ReplicaClient
from rucio.common.exception import DuplicateRule, NoFilesUploaded


# RUCIO tool
# G. Mazzitelli 2025
# copia i file da DAQ (o comunque da locale) in CLOUD e li replica su TAPE
#
# Exit Code meanings (MUST NOT CHANGE):
#| Exit Code | Meaning                                            |
#| --------- | -------------------------------------------------- |
#| 0         | Upload and replica created (or both already exist) |
#| 1         | File already uploaded, replica just created        |
#| 2         | Upload failed                                      |
#| 3         | Upload done, replica failed                        |
#| 4         | Client creation failed                             |

# Config file path from ENV or default
rucio_cfg = os.environ.get('RUCIO_CONFIG', '/home/.rucio.cfg')
os.environ['RUCIO_CONFIG'] = rucio_cfg

bearer_token = os.environ.get("BEARER_TOKEN")

if bearer_token:
    os.environ["RUCIO_AUTH_TOKEN"] = bearer_token
    print(bearer_token)
else:
    print("[WARNING] Missing BEARER_TOKEN environment variable")


# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('--file', required=True, help="File to upload")
parser.add_argument('--bucket', required=True, help="Bucket/scope")
parser.add_argument('--did_name', required=True, help="DID name")
parser.add_argument('--upload_rse', required=True, help="Upload RSE")
parser.add_argument('--transfer_rse', required=True, help="Transfer RSE")
parser.add_argument('--account', required=True, help="Rucio account")
args = parser.parse_args()

# Initialize clients
try:
    upload_client = UploadClient()
    transfer_client = Client()
    replica_client = ReplicaClient()
except Exception as e:
    print(f"[ERROR] Client creation failed: {str(e)}")
    sys.exit(4)


def replica_exists_on_rse(scope: str, name: str, rse: str) -> bool:
    """
    Returns True if a replica of (scope, name) is found on the given RSE.
    Uses list_replicas filtered by rse_expression to keep it cheap and precise.
    """
    dids = [{'scope': scope, 'name': name}]
    try:
        for r in replica_client.list_replicas(dids, rse_expression=rse):
            # 'states' is typically a dict {RSE: state}
            states = r.get('states') or {}
            if rse in states:
                return True
            # Fallback (some server/client combos may expose explicit RSE lists)
            rses = r.get('rses') or []
            if rse in rses:
                return True
        return False
    except Exception as e:
        print(f"[ERROR] Could not verify replica on {rse}: {str(e)}")
        return False


# Define upload item
# Key change: register_after_upload=True to avoid leaving a DID registered when the physical upload fails.
item = [{
    "path": args.file,
    "rse": args.upload_rse,
    "did_scope": args.bucket,
    "did_name": args.did_name,
    "register_after_upload": True
}]

# Track status
upload_done = False
replica_done = False

# Upload step
try:
    print(f"[INFO] Uploading file: {args.file}")
    upload_client.upload(item)
    upload_done = True
    print("[SUCCESS] Upload completed.")
except NoFilesUploaded:
    # IMPORTANT: NoFilesUploaded does not *guarantee* the file is on the target RSE.
    # Verify replica exists on upload_rse; otherwise treat as upload failure (exit code 2).
    if replica_exists_on_rse(args.bucket, args.did_name, args.upload_rse):
        print(f"[WARNING] File '{args.file}' is already uploaded.")
        # upload_done remains False -> preserves original exit-code logic (exit 1 if replica gets created now)
    else:
        print(f"[ERROR] Upload did not complete and no replica found on {args.upload_rse}.")
        sys.exit(2)
except Exception as e:
    print(f"[ERROR] Upload failed: {str(e)}")
    sys.exit(2)

# Try to add replication rule
did = [{'scope': args.bucket, 'name': args.did_name}]
try:
    print(f"[INFO] Adding replication rule to {args.transfer_rse}")
    transfer_client.add_replication_rule(did, 1, args.transfer_rse, account=args.account)
    replica_done = True
    print("[SUCCESS] Replica created.")
except DuplicateRule:
    print(f"[WARNING] Replica already exists on {args.transfer_rse}.")
    replica_done = True
except Exception as e:
    print(f"[ERROR] Replica creation failed: {str(e)}")
    sys.exit(3)

# Exit status logic (UNCHANGED)
if upload_done and replica_done:
    sys.exit(0)
elif (not upload_done) and replica_done:
    sys.exit(1)
else:
    sys.exit(2)
