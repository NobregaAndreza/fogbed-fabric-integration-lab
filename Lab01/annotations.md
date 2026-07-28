# Realizando testes com o `test-network` da versão mais recente do Hyperledger Fabric para analisar possíveis mudanças.

# Environment Notes

## Atualização do ambiente para compatibilidade com o Hyperledger Fabric 2.5

Durante a configuração inicial do ambiente, foi identificado que os binários do Hyperledger Fabric 2.5, obtidos através do script oficial `install-fabric.sh`, não podiam ser executados devido a uma incompatibilidade com a versão da biblioteca GLIBC disponível no sistema operacional.

---

# Ambiente inicial

Sistema operacional:

```bash
Ubuntu 20.04.6 LTS (Focal Fossa)
```

Versão da GLIBC:

```bash
ldd --version

glibc 2.31
```

---

# Erro encontrado

Ao executar:

```bash
./bin/peer version
```

era retornado:

```text
./bin/peer: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.34' not found
./bin/peer: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.32' not found
```

---

# Análise

Os binários do Hyperledger Fabric foram baixados corretamente através do script oficial, porém foram compilados utilizando uma versão mais recente da GLIBC do que a disponível no Ubuntu 20.04.

Configuração encontrada:

```text
Ubuntu 20.04
GLIBC 2.31
```

Configuração exigida pelos binários:

```text
GLIBC >= 2.34
```

Portanto, o problema não estava relacionado a:

- `fabric-samples`;
- `network.sh`;
- Docker;
- script de instalação do Fabric.

Tratava-se exclusivamente de uma incompatibilidade entre os binários do Fabric e a versão da GLIBC presente no sistema operacional.

---

# Decisão

Como o objetivo deste trabalho é construir um ambiente de experimentação reproduzível para integração entre Fogbed e Hyperledger Fabric, optou-se por atualizar o sistema operacional em vez de utilizar soluções alternativas para contornar a incompatibilidade.

Essa decisão reduz problemas futuros de compatibilidade com o ecossistema atual do Hyperledger Fabric, Docker e demais dependências utilizadas no laboratório.

---

# Atualização do sistema operacional

Foi realizada a atualização da distribuição utilizando o mecanismo oficial do Ubuntu:

```bash
do-release-upgrade
```

## Ambiente atual

Sistema operacional:

```bash
Ubuntu 22.04.5 LTS (Jammy Jellyfish)
```

Versão da GLIBC:

```bash
ldd --version

glibc 2.35
```

Kernel:

```bash
uname -r

6.8.0-136-generic
```

---

# Validação das ferramentas do ambiente

Após a atualização, foram validadas as principais ferramentas utilizadas no laboratório.

## Docker

```bash
docker --version

Docker version 28.1.1
```

## Docker Compose

```bash
docker compose version

Docker Compose version v2.35.1
```

## Python

```bash
python3 --version

Python 3.10.12
```

A atualização eliminou a incompatibilidade da GLIBC identificada anteriormente.

---

# Organização do projeto

O repositório não versionará dependências externas, objetivando um repositório enxuto com menos chances de erros.

Exemplos:

- Hyperledger Fabric binaries;
- `fabric-samples`;
- código-fonte do Fogbed;
- imagens Docker;
- certificados;
- artefatos gerados durante a execução da rede.

Esses componentes deverão ser preparados futuramente através de scripts de automação, garantindo a reprodutibilidade do ambiente.

Estrutura prevista:

```text
scripts/
├── install-fabric.sh
├── install-fogbed.sh
└── setup-environment.sh

third_party/
└── external dependencies
```

---

# Validação dos binários do Hyperledger Fabric

Após a atualização do sistema, os binários passaram a executar corretamente.

Validação:

```bash
./bin/peer version
```

Resultado:

```text
Version: v2.5.16
```

Também foi validado:

```bash
configtxgen --version
```

---

# Hyperledger Fabric Test Network

Após a correção do ambiente, foi executada a rede de testes oficial do Fabric.

Comando:

```bash
cd third_party/fabric-samples/test-network

./network.sh up
```

A rede foi iniciada com os seguintes componentes:

- `peer0.org1.example.com`
- `peer0.org2.example.com`
- `orderer.example.com`

Resultado:

```text
Network fabric_test created

Container peer0.org1.example.com Started
Container peer0.org2.example.com Started
Container orderer.example.com Started
```

---

# Criação do canal

Foi criado um canal personalizado para os testes:

```bash
./network.sh createChannel -c canalteste
```

O processo realizou:

- geração do bloco gênesis;
- criação do canal;
- inclusão do orderer;
- entrada dos peers no canal;
- configuração dos anchor peers.

Resultado:

```text
Channel 'canalteste' joined
```

---

# Deploy do Chaincode

Foi utilizado o chaincode de exemplo:

```text
asset-transfer-basic
```

Deploy realizado através de:

```bash
./network.sh deployCC \
-ccn basic \
-ccp ../asset-transfer-basic/chaincode-go \
-ccl go
```

Durante a execução foi identificado inicialmente um problema relacionado à versão do Go:

```text
invalid go version '1.23.0': must match format 1.23
```

O problema ocorreu devido à versão do Go utilizada pelo ambiente não aceitar o formato definido no arquivo `go.mod` do chaincode.

Após a atualização/configuração correta do ambiente Go, o deploy foi concluído.

Validação:

```text
Committed chaincode definition for chaincode 'basic'

Version: 1.0
Sequence: 1

Approvals:
[Org1MSP: true, Org2MSP: true]
```

---

# Interação com o Ledger

Após o deploy, foram realizadas operações utilizando o chaincode.

## Configuração do ambiente do peer

Foram configuradas as variáveis necessárias:

```bash
export PATH=${PWD}/../bin:$PATH

export FABRIC_CFG_PATH=$PWD/../config/

export CORE_PEER_TLS_ENABLED=true

export CORE_PEER_LOCALMSPID="Org1MSP"

export CORE_PEER_TLS_ROOTCERT_FILE=${PWD}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt

export CORE_PEER_MSPCONFIGPATH=${PWD}/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp

export CORE_PEER_ADDRESS=localhost:7051
```

---

# Inicialização do Ledger

Comando:

```bash
peer chaincode invoke \
-o localhost:7050 \
--ordererTLSHostnameOverride orderer.example.com \
--tls \
-C canalteste \
-n basic \
-c '{"function":"InitLedger","Args":[]}'
```

Resultado:

```text
Chaincode invoke successful. result: status:200
```

---

# Consulta dos ativos

Consulta executada:

```bash
peer chaincode query \
-C canalteste \
-n basic \
-c '{"Args":["GetAllAssets"]}'
```

Resultado:

```json
[
  {
    "AppraisedValue":300,
    "Color":"blue",
    "ID":"asset1",
    "Owner":"Tomoko",
    "Size":5
  },
  {
    "AppraisedValue":400,
    "Color":"red",
    "ID":"asset2",
    "Owner":"Brad",
    "Size":5
  },
  {
    "AppraisedValue":500,
    "Color":"green",
    "ID":"asset3",
    "Owner":"Jin Soo",
    "Size":10
  },
  {
    "AppraisedValue":600,
    "Color":"yellow",
    "ID":"asset4",
    "Owner":"Max",
    "Size":10
  },
  {
    "AppraisedValue":700,
    "Color":"black",
    "ID":"asset5",
    "Owner":"Adriana",
    "Size":15
  },
  {
    "AppraisedValue":800,
    "Color":"white",
    "ID":"asset6",
    "Owner":"Michel",
    "Size":15
  }
]
```

A consulta confirmou que o ledger estava funcional e armazenando corretamente os ativos.

---

# Observação sobre canais


Após ajustar o parâmetro:

```bash
-C canalteste
```

as operações foram executadas corretamente.

---

# Resultado

A rede Hyperledger Fabric foi validada isoladamente com sucesso.

O ambiente atual possui:

- Hyperledger Fabric v2.5.16 funcionando;
- peers executando em containers Docker;
- orderer ativo;
- canal criado;
- chaincode instalado;
- transações executadas;
- consultas realizadas no ledger.

Essa validação estabelece uma base funcional antes da integração com o Fogbed.

---

# Próximos passos

1. Criar experimentos incrementais:

- execução de um peer dentro do Fogbed;
- comunicação peer ↔ orderer;
- múltiplas organizações em nós Fog distintos;
- avaliação da arquitetura completa.