# Fogbed + Hyperledger Fabric Integration Lab

![Hyperledger Fabric](https://img.shields.io/badge/Hyperledger%20Fabric-2.5-blue)
![Python](https://img.shields.io/badge/Python-3.x-blue)
![Docker](https://img.shields.io/badge/Docker-Containers-blue)
![Status](https://img.shields.io/badge/Status-Experimental-orange)
![Research](https://img.shields.io/badge/Project-Academic%20Research-purple)

Ambiente experimental para estudo, validação e desenvolvimento de uma integração entre **Hyperledger Fabric** e **Fogbed**, com foco na execução de redes blockchain permissionadas em ambientes emulados de **Edge/Fog Computing**.

O projeto adota uma abordagem incremental: cada laboratório valida isoladamente uma parte da infraestrutura antes de avançar para configurações mais complexas da rede Fabric.

---

## 🎯 Objetivo

Investigar como os componentes e mecanismos do Hyperledger Fabric podem ser executados e abstraídos sobre o Fogbed.

Os experimentos buscam construir gradualmente uma base para uma integração modular capaz de representar diferentes configurações de redes Fabric no ambiente de emulação.

---

## 🏗️ Arquitetura

A integração estudada utiliza a seguinte pilha:

```text
┌─────────────────────────────┐
│     Hyperledger Fabric      │
├─────────────────────────────┤
│           Fogbed            │
├─────────────────────────────┤
│        Containernet         │
├─────────────────────────────┤
│           Docker            │
└─────────────────────────────┘
```

O **Hyperledger Fabric** representa a camada blockchain.

O **Fogbed** é responsável pela construção e execução dos cenários de Fog/Edge Computing.

O **Containernet** fornece a infraestrutura de emulação de rede com suporte a containers.

O **Docker** executa os componentes da rede Fabric.

---

## 🧪 Metodologia

O desenvolvimento é organizado em experimentos incrementais.

Cada laboratório busca responder uma questão específica antes que novas funcionalidades sejam adicionadas:

```text
Fogbed
   ↓
Comunicação
   ↓
Containers
   ↓
Orderer
   ↓
Peer
   ↓
Peer ↔ Orderer
   ↓
Certificate Authority
   ↓
Canais
   ↓
Chaincode
   ↓
Rede completa
   ↓
Abstração / Plugin
```

Essa estratégia permite identificar separadamente problemas relacionados ao **Fogbed**, à infraestrutura de rede e ao próprio **Hyperledger Fabric**.

---

## 🧪 Experimentos

### ✅ Lab00 — Instalação e topologia básica `DONE`

- Instalação e configuração do Fogbed.
- Criação de uma topologia simples.

### ✅ Lab01 — Comunicação entre nós `DONE`

- Validação da comunicação entre nós da topologia.

### ✅ Lab02 — Containers personalizados `DONE`

- Execução de containers personalizados no Fogbed.

### ✅ Lab03 — Docker + Fogbed `DONE`

- Validação da integração entre containers Docker e a topologia Fogbed.

### ✅ Lab04 — Orderer Hyperledger Fabric `DONE`

- Geração dinâmica de material criptográfico.
- Geração do Genesis Block.
- Inicialização de um Orderer Fabric 2.5.
- Configuração de MSP.
- TLS habilitado.
- Consenso `etcdraft` (Raft).
- Inicialização do System Channel.
- Eleição do Orderer como líder Raft.

### ✅ Lab05 — Peer Hyperledger Fabric `DONE`

- Inicialização de um Peer no Fogbed.
- MSP e identidade da organização.
- TLS.
- Serviço gRPC.
- Operations Service e health checks.
- Execução conjunta de Peer e Orderer.

### ✅ Lab06 — Peer ↔ Orderer `DONE`

- Validação da comunicação entre Peer e Orderer.
- Mapeamento dinâmico de nomes TLS em `/etc/hosts`.
- Bootstrap sem system channel via API `osnadmin` (channel participation).
- Join de Peer e Orderer em `mychannel`.
- Validação de entrega de blocos (delivery).

### ✅ Lab07 — Lifecycle e Execução de Chaincode `DONE`

- Empacotamento, instalação e consulta de pacotes de chaincode (`basic`).
- Aprovação da definição da organização (`approveformyorg`).
- Verificação de prontidão, commit e consulta de definição no canal (`checkcommitreadiness`, `commit`, `querycommitted`).
- Resolução dinâmica do endpoint do Peer e validação do runtime e registro do chaincode (`experiment03b`).
- Execução de transações de negócio (`invoke` / `CreateAsset`), commit no ledger do canal `mychannel` e confirmação semântica por `query` (`ReadAsset`) (`experiment04`).

### ⏳ Lab08 — Arquitetura e Abstração / Plugin `TODO`

- Abstração modular dos componentes validados nos laboratórios anteriores.
- Configuração parametrizada e extensível de redes Fabric no Fogbed.

---

## 📊 Progresso

| Lab | Experimento | Status |
|---|---|---|
| Lab00 | Topologia básica | ✅ Done |
| Lab01 | Comunicação entre nós | ✅ Done |
| Lab02 | Containers personalizados | ✅ Done |
| Lab03 | Docker + Fogbed | ✅ Done |
| Lab04 | Orderer | ✅ Done |
| Lab05 | Peer | ✅ Done |
| Lab06 | Peer ↔ Orderer | ✅ Done |
| Lab07 | Lifecycle e Execução de Chaincode | ✅ Done |
| Lab08 | Arquitetura / Plugin | ⏳ Todo |

---

## 💡 Ideias para a integração

Esta seção reúne possibilidades identificadas durante os experimentos.

**Não representam necessariamente funcionalidades já implementadas.**

### Health Check

Criar um mecanismo centralizado para verificar automaticamente a saúde dos componentes Fabric.

Possíveis níveis de diagnóstico:

```text
Container
   ↓
Processo Fabric
   ↓
Serviço gRPC
   ↓
Operations Service
   ↓
Comunicação entre componentes
   ↓
Participação em canais
```

### Configuração modular

Permitir que uma futura abstração represente diferentes topologias, evitando configurações fixas como:

```text
1 Orderer
1 Peer
1 Organização
```

A configuração deverá futuramente considerar cenários com:

- múltiplos Peers;
- múltiplos Orderers;
- múltiplas organizações;
- diferentes distribuições entre nós Fog/Edge/Cloud;
- diferentes canais.

### Geração automática de configuração

Investigar a geração automática de:

- `crypto-config.yaml`;
- `configtx.yaml`;
- material MSP;
- certificados TLS;
- artefatos necessários à rede.

A configuração deverá ser derivada, quando possível, da topologia definida pelo usuário.

### Gerenciamento de canais

Investigar uma abstração para:

- criação de canais;
- participação de organizações;
- entrada de Peers;
- configuração de políticas.

### Diagnóstico

Centralizar mecanismos para distinguir problemas relacionados a:

```text
Fogbed / Containernet
        ↓
Rede / conectividade
        ↓
Container
        ↓
MSP / certificados
        ↓
TLS
        ↓
Peer / Orderer
        ↓
Canal
        ↓
Chaincode
```

### Interface de terminal

Padronizar a saída dos experimentos e, posteriormente:

- adicionar cores para sucesso, erro, aviso e informação;
- manter alinhamento consistente;
- facilitar leitura dos diagnósticos;
- centralizar a apresentação em funções reutilizáveis.

 **Integração contínua (CI)**
  - Validar código Python e scripts do projeto.
  - Validar arquivos de configuração Fabric.
  - Testar a geração dos artefatos criptográficos.
  - Testar a geração do Genesis Block.
  - Executar testes automatizados das abstrações do plugin.
  - Investigar futuramente testes de integração com Fogbed/Containernet.

---

## 📂 Organização

Cada laboratório possui sua própria documentação e os arquivos necessários para reproduzir o experimento.

```text
fogbed-fabric-integration-lab/
│
├── Lab00/
├── Lab01/
├── Lab02/
├── Lab03/
├── Lab04/
├── Lab05/
├── Lab06/
├── Lab07/
│
├── third_party/
│
└── readme.md
```

Os READMEs individuais registram:

- objetivo do experimento;
- configuração utilizada;
- procedimentos executados;
- problemas encontrados;
- decisões tomadas;
- resultados obtidos;
- próximos passos.

---

## 🔬 Estado atual

O **Hyperledger Fabric 2.5** foi integrado ao **Fogbed** com sucesso até a validação completa do lifecycle e da execução funcional de transações de negócio no **Lab07**.

Foram validados: a comunicação Peer ↔ Orderer via gRPC/TLS, o bootstrap por canal de aplicação via `osnadmin`, a entrega de blocos (delivery), o empacotamento, instalação, aprovação e commit de definições de chaincode, a resolução dinâmica do endpoint do Peer (`CORE_PEER_CHAINCODEADDRESS`), o registro do runtime, a execução de transações (`CreateAsset`), o commit de novos blocos no ledger e a consulta semântica do estado persistido (`ReadAsset`).

O Lab07 está concluído. A base experimental construída servirá como fundação para a futura abstração/plugin da integração.

---

## 🎓 Contexto

Este repositório faz parte de um trabalho acadêmico voltado à investigação da integração do **Hyperledger Fabric com ambientes de Edge/Fog Computing**, utilizando o Fogbed como plataforma de emulação.