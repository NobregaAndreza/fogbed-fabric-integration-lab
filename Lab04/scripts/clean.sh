#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo " Cleaning Lab04"
echo "=========================================="

echo

echo "[INFO] Removendo crypto-material..."
rm -rf "$LAB_DIR/crypto-material"

echo "[INFO] Removendo channel-artifacts..."
rm -rf "$LAB_DIR/channel-artifacts"

echo
echo "[OK] Lab04 limpo."