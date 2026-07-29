# Lab03 — Geração dos Artefatos Criptográficos da Rede

## Objetivo

O objetivo deste laboratório é construir os primeiros artefatos permanentes necessários para uma rede Hyperledger Fabric.

Nos laboratórios anteriores foram validados:

- execução do Fogbed;
- integração com o Containernet;
- execução de containers Docker;
- imagens oficiais do Hyperledger Fabric;
- inicialização dos binários `peer` e `orderer`.

Entretanto, apesar dos containers iniciarem corretamente, o serviço Orderer não conseguia permanecer em execução, encerrando com a seguinte mensagem:

```text
panic: unable to bootstrap orderer.
Error reading genesis block file:
open /etc/hyperledger/fabric/genesisblock:
no such file or directory
```

Esse comportamento é esperado.

O Orderer somente consegue inicializar quando existe um bloco gênesis (Genesis Block) válido, contendo a configuração inicial da blockchain.

Este laboratório resolve exatamente esse problema.

---

# Estrutura produzida

Ao final do laboratório são gerados dois conjuntos de artefatos:

```
Lab03
│
├── crypto-config.yaml
├── configtx.yaml
│
├── crypto-material/
│
├── channel-artifacts/
│   └── genesis.block
│
└── scripts/
    ├── generate-crypto.sh
    └── generate-genesis.sh
```

---

# Etapa 1 — Definição das identidades

O arquivo `crypto-config.yaml` descreve todas as entidades criptográficas da rede.

Neste laboratório foi criada uma rede mínima composta por:

- 1 organização Orderer
- 1 organização Peer
- 1 Orderer
- 1 Peer
- 1 usuário administrador

A partir desse arquivo o utilitário `cryptogen` gera automaticamente:

- certificados X.509;
- MSPs;
- certificados TLS;
- chaves privadas.

Esses artefatos ficam armazenados no diretório:

```
crypto-material/
```

---

# Estrutura dos certificados

Após a execução do script `generate-crypto.sh` foi produzida uma estrutura semelhante a:

```
crypto-material
├── ordererOrganizations
└── peerOrganizations
```

Cada organização possui:

- CA
- TLS CA
- MSP
- certificados dos usuários
- certificados dos peers/orderers

Esses diretórios serão posteriormente montados como volumes dentro dos containers Docker.

---

# Etapa 2 — Configuração da rede Fabric

Depois dos certificados foi criado o arquivo:

```
configtx.yaml
```

Este é um dos arquivos mais importantes do Hyperledger Fabric.

Ele descreve toda a configuração lógica da blockchain.

Entre suas responsabilidades estão:

- organizações participantes;
- políticas de acesso;
- capacidades da rede;
- algoritmo de consenso;
- consortium;
- perfil utilizado para criação do Genesis Block.

---

# Organizações

O arquivo define duas organizações.

## OrdererMSP

Responsável pelos nós Orderer da rede.

```yaml
Name: OrdererMSP
ID: OrdererMSP
```

Seu MSP aponta para:

```
crypto-material/ordererOrganizations/example.com/msp
```

---

## Org1MSP

Representa a primeira organização participante da blockchain.

```yaml
Name: Org1MSP
ID: Org1MSP
```

Seu MSP aponta para:

```
crypto-material/peerOrganizations/org1.example.com/msp
```

---

# Policies

Cada organização define três políticas principais.

## Readers

Permite leitura das informações da rede.

## Writers

Permite envio de transações.

## Admins

Permite operações administrativas.

Essas políticas são utilizadas pelo Fabric para validar permissões durante toda a execução da blockchain.

---

# Capabilities

As capacidades especificam quais funcionalidades da versão atual do Hyperledger Fabric serão habilitadas.

Neste laboratório foram utilizadas:

```yaml
Channel:
Orderer:
Application:
```

compatíveis com a série Fabric 2.x.

---

# Orderer

O bloco `Orderer` define o serviço responsável pelo consenso.

Neste laboratório foi utilizado:

```
OrdererType: etcdraft
```

O algoritmo EtcdRaft é o mecanismo de consenso atualmente recomendado pelo Hyperledger Fabric.

Também foi definido:

- endereço do Orderer;
- porta 7050;
- parâmetros de batching;
- certificados TLS utilizados pelos consenters.

---

# Consortium

O consortium representa o conjunto de organizações autorizadas a criar canais.

Neste laboratório foi criado um consortium simples contendo apenas:

```
Org1
```

---

# Profile FogbedGenesis

O profile

```
FogbedGenesis
```

define toda a configuração utilizada pelo utilitário `configtxgen` para gerar o bloco gênesis.

Esse profile reúne:

- Orderer
- Consortium
- Policies
- Capabilities

em um único documento.

---

# Etapa 3 — Geração do Genesis Block

Foi desenvolvido o script:

```
scripts/generate-genesis.sh
```

O script realiza automaticamente:

1. validação do ambiente;
2. verificação do `configtxgen`;
3. criação do diretório `channel-artifacts`;
4. geração do bloco gênesis;
5. validação do resultado.

A geração é feita através do comando:

```bash
configtxgen \
    -profile FogbedGenesis \
    -channelID system-channel \
    -outputBlock channel-artifacts/genesis.block
```

---

# Resultado

Ao final do processo foi produzido:

```
channel-artifacts/genesis.block
```

com aproximadamente 14 KB.

Esse arquivo contém a configuração inicial da blockchain e será utilizado pelo serviço Orderer durante sua inicialização.

---

# Importância do Genesis Block

O Genesis Block é o primeiro bloco da blockchain.

Ele não contém transações de usuários.

Seu conteúdo consiste exclusivamente na configuração inicial da rede, incluindo:

- organizações participantes;
- políticas;
- MSPs;
- algoritmo de consenso;
- consortium;
- configurações do canal do sistema.

Sem esse arquivo o Orderer não consegue iniciar.

---
