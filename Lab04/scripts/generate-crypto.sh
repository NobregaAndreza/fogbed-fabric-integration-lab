#!/usr/bin/env bash

set -e


# ============================================================
# Hyperledger Fabric - Crypto Material Generator
#
# Responsável por gerar os certificados e identidades
# criptográficas da rede Fabric utilizando o cryptogen.
#
# Este script gera:
#
# - MSP do Orderer;
# - MSP dos Peers;
# - certificados TLS;
# - identidades das organizações.
#
# O arquivo de entrada utilizado é:
#
#   crypto-config.yaml
#
# O material gerado será armazenado em:
#
#   crypto-material/
#
# Estrutura esperada:
#
# crypto-material/
# ├── ordererOrganizations/
# └── peerOrganizations/
#
# ============================================================



echo "================================="
echo " Gerando certificados Fabric"
echo "================================="



# ============================================================
# Localização do laboratório
#
# ROOT_DIR aponta para a raiz do Lab04.
#
# O script está localizado em:
#
# Lab04/scripts/generate-crypto.sh
#
# Portanto precisamos subir um diretório.
#
# ============================================================

ROOT_DIR=$(cd "$(dirname "$0")/.."; pwd)



# ============================================================
# Descoberta dos binários Hyperledger Fabric
#
# O laboratório não deve depender de um caminho absoluto
# específico de uma máquina.
#
# A variável FABRIC_BIN pode ser definida externamente:
#
# export FABRIC_BIN=/caminho/fabric/bin
#
# Caso não seja definida, o script procura em locais comuns.
#
# Essa abordagem permite executar o laboratório em diferentes
# ambientes sem alterar o código.
#
# ============================================================


SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/fabric-env.sh"



# ============================================================
# Localização do cryptogen
#
# cryptogen é a ferramenta responsável por gerar:
#
# - certificados das organizações;
# - identidades MSP;
# - certificados TLS.
#
# ============================================================


CRYPTOGEN=$(command -v cryptogen || true)



if [ -z "$CRYPTOGEN" ]; then

    echo "[ERRO] cryptogen não encontrado."

    echo

    echo "Instale os binários do Hyperledger Fabric ou informe:"
    echo

    echo "export FABRIC_BIN=/caminho/fabric/bin"

    exit 1

fi



echo "[INFO] cryptogen encontrado em:"
echo "$CRYPTOGEN"

echo



# ============================================================
# Entrando na raiz do laboratório
#
# O cryptogen espera encontrar o arquivo:
#
# crypto-config.yaml
#
# relativo ao diretório atual.
#
# ============================================================


cd "$ROOT_DIR"



# ============================================================
# Limpeza do material anterior
#
# Remove certificados antigos para garantir que cada execução
# gere um ambiente limpo.
#
# ============================================================


echo "[1/2] Limpando material antigo..."


rm -rf crypto-material/*



# ============================================================
# Geração dos certificados
#
# Entrada:
#
# crypto-config.yaml
#
# Saída:
#
# crypto-material/
#
# ============================================================


echo "[2/2] Executando cryptogen..."



"$CRYPTOGEN" generate \
    --config=crypto-config.yaml \
    --output=crypto-material



echo

echo "Certificados gerados com sucesso!"

echo

# Lab04: automatizando a inicialização de um Hyperledger Fabric Orderer dentro do Fogbed (geração de crypto + genesis + container Docker).
