#!/usr/bin/env bash

# Script auxiliar de limpeza na raiz do Lab05
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/scripts/clean.sh"
