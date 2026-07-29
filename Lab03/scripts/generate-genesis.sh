#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

CONFIGTXGEN="$(command -v configtxgen || true)"

PROFILE="FogbedGenesis"

CHANNEL_ARTIFACTS="${ROOT_DIR}/channel-artifacts"

CONFIG_FILE="${ROOT_DIR}/configtx.yaml"

GENESIS_BLOCK="${CHANNEL_ARTIFACTS}/genesis.block"



echo "==========================================="
echo " Hyperledger Fabric - Genesis Block Builder"
echo "==========================================="
echo

if [ -z "${CONFIGTXGEN}" ]; then
    echo "[ERRO] configtxgen não encontrado."
    echo "Instale os binários do Hyperledger Fabric."
    exit 1
fi

if [ ! -f "${CONFIG_FILE}" ]; then
    echo "[ERRO] configtx.yaml não encontrado."
    exit 1
fi

if [ ! -d "${ROOT_DIR}/crypto-material" ]; then
    echo "[ERRO] crypto-material não encontrado."
    echo "Execute primeiro:"
    echo "    ./scripts/generate-crypto.sh"
    exit 1
fi

mkdir -p "${CHANNEL_ARTIFACTS}"

echo "[INFO] Gerando bloco gênesis..."

export FABRIC_CFG_PATH="${ROOT_DIR}"

"${CONFIGTXGEN}" \
    -profile "${PROFILE}" \
    -channelID system-channel \
    -outputBlock "${GENESIS_BLOCK}"

echo

if [ -f "${GENESIS_BLOCK}" ]; then
    echo "[OK] Genesis block criado com sucesso."
    echo
    ls -lh "${GENESIS_BLOCK}"
else
    echo "[ERRO] O arquivo genesis.block não foi criado."
    exit 1
fi