#!/usr/bin/env bash

set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

source "$SCRIPT_DIR/fabric-env.sh"

CRYPTOGEN="$(command -v cryptogen || true)"
if [ -z "$CRYPTOGEN" ]; then
    echo "[ERRO] cryptogen não encontrado."
    exit 1
fi

cd "$ROOT_DIR"
rm -rf crypto-material/*
"$CRYPTOGEN" generate --config=crypto-config.yaml --output=crypto-material

echo "[OK] crypto-material gerado no Lab06."
