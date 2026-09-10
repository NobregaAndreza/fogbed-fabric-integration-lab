#!/usr/bin/env bash

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

rm -rf "$ROOT_DIR/crypto-material" "$ROOT_DIR/channel-artifacts"

echo "[OK] Lab06 limpo."
