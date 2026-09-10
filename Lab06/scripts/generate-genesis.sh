#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$SCRIPT_DIR/fabric-env.sh"

CONFIGTXGEN="$(command -v configtxgen || true)"
if [ -z "${CONFIGTXGEN}" ]; then
    echo "[ERRO] configtxgen não encontrado."
    exit 1
fi

PROFILE=FogbedGenesis
CHANNEL_ID=system-channel
GENESIS_BLOCK="${ROOT_DIR}/channel-artifacts/genesis.block"
case "${1:---baseline}" in
    --baseline) ;;
    --application)
        PROFILE=FogbedApplicationChannel
        CHANNEL_ID=mychannel
        GENESIS_BLOCK="${ROOT_DIR}/channel-artifacts/${CHANNEL_ID}.block"
        ;;
    *) echo "Uso: $0 [--baseline|--application]" >&2; exit 1 ;;
esac

mkdir -p "$(dirname "$GENESIS_BLOCK")"

export FABRIC_CFG_PATH="${ROOT_DIR}"
"${CONFIGTXGEN}" -profile "$PROFILE" -channelID "$CHANNEL_ID" -outputBlock "${GENESIS_BLOCK}"

echo "[OK] ${GENESIS_BLOCK} gerado no Lab06."
