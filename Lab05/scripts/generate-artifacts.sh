#!/usr/bin/env bash

set -e

# ============================================================
# Hyperledger Fabric Artifact Builder (Lab05)
#
# Executa em sequência a geração de criptografia e do bloco gênesis.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

source "$SCRIPT_DIR/fabric-env.sh"

echo "=========================================="
echo " Hyperledger Fabric Artifact Builder (Lab05)"
echo "=========================================="

echo
echo "[1/2] Gerando certificados..."
bash "$SCRIPT_DIR/generate-crypto.sh"

echo
echo "[2/2] Gerando bloco gênesis..."
bash "$SCRIPT_DIR/generate-genesis.sh"

echo
echo "=========================================="
echo " Todos os artefatos do Lab05 foram gerados."
echo "=========================================="
echo
echo "Crypto material: $ROOT_DIR/crypto-material"
echo "Genesis block:   $ROOT_DIR/channel-artifacts/genesis.block"
