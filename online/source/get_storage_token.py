#!/usr/bin/env python3
"""
Ottiene uno storage access token tramite refresh token.

Per impostazione predefinita legge le credenziali da /home/.storage.env
e stampa esclusivamente l'access token su stdout, così può essere usato
direttamente in una sostituzione di comando della shell.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


REQUIRED_ENV = (
    "STORAGE_IAM_CLIENT_ID",
    "STORAGE_IAM_CLIENT_SECRET",
    "STORAGE_SCOPES",
    "STORAGE_REFRESH_TOKEN",
    "STORAGE_IAM_TOKEN_ENDPOINT",
)


def get_storage_access_token(config_path: str) -> str:
    env_file = Path(config_path)

    if not env_file.is_file():
        raise RuntimeError(f"File di configurazione non trovato: {env_file}")

    if not load_dotenv(env_file, override=False):
        raise RuntimeError(f"Impossibile caricare il file: {env_file}")

    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Variabili mancanti in .storage.env: " + ", ".join(missing)
        )

    client_id = os.environ["STORAGE_IAM_CLIENT_ID"]
    client_secret = os.environ["STORAGE_IAM_CLIENT_SECRET"]
    scopes = os.environ["STORAGE_SCOPES"]
    refresh_token = os.environ["STORAGE_REFRESH_TOKEN"]
    endpoint = os.environ["STORAGE_IAM_TOKEN_ENDPOINT"].rstrip("/")

    # OAuth 2.0 usa normalmente il parametro "scope".
    # Impostare STORAGE_SCOPE_PARAM=scopes solo se il server richiede
    # esplicitamente il nome non standard "scopes".
    scope_param = os.environ.get("STORAGE_SCOPE_PARAM", "scope")

    response = requests.post(
        f"{endpoint}/token",
        auth=(client_id, client_secret),
        data={
            scope_param: scopes,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body = response.text.strip()
        if len(body) > 1000:
            body = body[:1000] + "..."
        raise RuntimeError(
            f"Token endpoint HTTP {response.status_code}: {body}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Il token endpoint non ha restituito JSON valido") from exc

    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError(
            "La risposta JSON non contiene il campo 'access_token'"
        )

    return str(access_token)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ottiene uno storage access token tramite refresh token."
    )
    parser.add_argument(
        "--config",
        default="/home/.storage.env",
        help="Percorso del file .env (default: /home/.storage.env)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        token = get_storage_access_token(args.config)
    except (RuntimeError, requests.RequestException) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # stdout contiene soltanto il token.
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())