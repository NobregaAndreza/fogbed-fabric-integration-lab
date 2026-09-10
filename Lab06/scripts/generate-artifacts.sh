#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

source "$SCRIPT_DIR/fabric-env.sh"

case "${1:---baseline}" in
    --application)
        # Reutiliza o crypto da baseline. Gera somente se ainda não houver
        # material; um diretório parcialmente preenchido não deve ser apagado.
        if [ ! -d "$ROOT_DIR/crypto-material" ] ||
           [ -z "$(ls -A "$ROOT_DIR/crypto-material")" ]; then
            bash "$SCRIPT_DIR/generate-crypto.sh"
        fi
        bash "$SCRIPT_DIR/generate-genesis.sh" --application
        exit 0
        ;;
    --baseline) ;;
    *) echo "Uso: $0 [--baseline|--application]" >&2; exit 1 ;;
esac

bash "$SCRIPT_DIR/generate-crypto.sh"
bash "$SCRIPT_DIR/generate-genesis.sh"

echo "[OK] artefatos do Lab06 gerados."
