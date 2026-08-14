#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# utilizando scripts do lab03 para mantermos módulos independentes
cp -r ../Lab03/channel-artifacts ..
cp -r ../Lab03/crypto-material ..