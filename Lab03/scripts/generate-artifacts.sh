#!/usr/bin/env bash

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo " Hyperledger Fabric Artifact Builder"
echo "=========================================="

echo
echo "[1/2] Gerando certificados..."
bash "$ROOT_DIR/generate-crypto.sh"

echo
echo "[2/2] Gerando bloco gênesis..."
bash "$ROOT_DIR/generate-genesis.sh"

echo
echo "=========================================="
echo " Todos os artefatos foram gerados."
echo "=========================================="

echo
echo "Crypto material:"
echo "  $ROOT_DIR/crypto-material"

echo
echo "Genesis block:"
echo "  $ROOT_DIR/channel-artifacts/genesis.block"