

#/bin/sh
source /home/.storage.env
RESPONSE="$(curl -s -u ${STORAGE_IAM_CLIENT_ID}:${STORAGE_IAM_CLIENT_SECRET} \
    	-d scopes="\"${STORAGE_SCOPES}"\" -d grant_type=refresh_token \
    	-d refresh_token=${STORAGE_REFRESH_TOKEN} ${STORAGE_IAM_TOKEN_ENDPOINT}/token)"
echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 
