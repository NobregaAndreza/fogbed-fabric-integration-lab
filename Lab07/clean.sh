#!/usr/bin/env bash
# Remove apenas artefatos locais; a rede deve estar encerrada antes da limpeza.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
rm -rf "$ROOT_DIR/crypto-material" "$ROOT_DIR/channel-artifacts" "$ROOT_DIR/chaincode-packages"
echo "[OK] Artefatos do Lab07 removidos; fontes e dependências preservados."
