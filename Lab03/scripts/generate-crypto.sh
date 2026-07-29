#!/bin/bash

set -e


echo "================================="
echo " Gerando certificados Fabric"
echo "================================="


ROOT_DIR=$(cd "$(dirname "$0")/.."; pwd)


CRYPTOGEN=$(which cryptogen)


if [ -z "$CRYPTOGEN" ]; then
    echo "Erro: cryptogen não encontrado"
    exit 1
fi


cd "$ROOT_DIR"


echo "[1/2] Limpando material antigo..."

rm -rf crypto-material/*


echo "[2/2] Executando cryptogen..."


cryptogen generate \
--config=crypto-config.yaml \
--output=crypto-material


echo ""
echo "Certificados gerados com sucesso!"
echo ""


