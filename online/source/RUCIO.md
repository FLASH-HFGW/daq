### RUCIO useful CLI
- database: https://docs.google.com/spreadsheets/d/1dBHc4fwQgmx092ohra6Y-ueF_BpOPVk26BNhi5dCRnM/
- rucio shell: docker run --rm -it --name rucio-shell -e  BEARER_TOKEN=$(python3 get_storage_token.py) -v /home/.rucio.cfg:/app/.rucio.cfg gmazzitelli/rucio-shell
* stato delle repliche di un file: rucio rule list --did data:LNF/run00601.mid.gz
* rucio rule add --copies 1 --rse-exp T1_USERDISK --lifetime 7776000 data:LNF/run00601.mid.gz (ricopia un file da TAPE a T1_USERDISK per 3 mesi)
- RUN=00010; docker run --rm -v /home/.rucio.cfg:/home/.rucio.cfg -e BEARER_TOKEN=$(`python3 get_storage_token.py`) -v /home/cold/data/run${RUN}.mid.gz:/app/run${RUN}.mid.gz  gmazzitelli/rucio-uploader:v0.4 --file /app/run${RUN}.mid.gz --bucket data --did_name LNF/run${RUN}.mid.gz --upload_rse T1_USERDISK --transfer_rse T1_USERTAPE --account rucio-daq
- ./data2rucio_recheck.py per caricare eventuali file mancanti andati in fault per motivi di rucio
- ./rucio_cleanup.py per cancelare file, esempio ./rucio_cleanup.py 206 (--ragne x y, --all, --dry-run), la cancellazione e' consentita solo se i file sono opportunamete replicati
