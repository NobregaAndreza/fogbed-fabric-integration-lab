#!/usr/bin/env bash

set -e

# ============================================================
# Hyperledger Fabric - Crypto Material Generator (Lab05)
#
# Gera os certificados X.509 e estruturas MSP usando `cryptogen`.
# Entrada: crypto-config.yaml
# Saída: crypto-material/
# ============================================================

echo "================================="
echo " Gerando certificados Fabric (Lab05)"
echo "================================="

ROOT_DIR="$(cd "$(dirname "$0")/.."; pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

source "$SCRIPT_DIR/fabric-env.sh"

CRYPTOGEN="$(command -v cryptogen || true)"

if [ -z "$CRYPTOGEN" ]; then
    echo "[ERRO] cryptogen não encontrado."
    echo "Instale os binários do Hyperledger Fabric ou informe FABRIC_BIN."
    exit 1
fi

echo "[INFO] cryptogen encontrado em: $CRYPTOGEN"
echo

cd "$ROOT_DIR"

echo "[1/2] Limpando material criptográfico antigo..."
rm -rf crypto-material/*

echo "[2/2] Executando cryptogen..."
"$CRYPTOGEN" generate \
    --config=crypto-config.yaml \
    --output=crypto-material

echo
echo "Certificados gerados com sucesso no Lab05!"
echo
