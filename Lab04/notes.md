# Lab04 - Inicialização automatizada de um Hyperledger Fabric Orderer no Fogbed

## Objetivo

Este laboratório tem como objetivo implementar a primeira integração funcional entre o **Fogbed** e um componente real do **Hyperledger Fabric**, automatizando a criação e inicialização de um nó **Orderer**.

Nesta etapa foi desenvolvido um fluxo automatizado responsável por:

- gerar o material criptográfico da rede Fabric;
- criar identidades das organizações;
- gerar o bloco gênesis da rede;
- configurar um container Docker executando o Hyperledger Fabric Orderer;
- executar o Orderer dentro de uma topologia Fogbed;
- validar sua inicialização utilizando logs e comandos de diagnóstico.

O experimento representa a primeira camada da arquitetura proposta:

```

Hyperledger Fabric
|
|
Docker Container
|
|
Fogbed / Containernet
|
|
Ambiente de Experimentação

```

---

# Arquitetura do experimento

A arquitetura utilizada neste laboratório possui um único nó Fabric:


```
             Fogbed

               |
               |
         Virtual Instance
               |
               |
          Container Docker
               |
               |
  Hyperledger Fabric Orderer
               |
               |
    +----------------------+
    |                      |
    |                      |
 MSP/TLS              Genesis Block
    |                      |
    +----------------------+
```


O Orderer é responsável por:

- receber transações;
- ordenar blocos;
- executar consenso;
- manter o ledger do sistema.

Neste laboratório é utilizado o mecanismo de consenso:

```

etcdraft

```

presente nas versões atuais do Hyperledger Fabric.

---

# Estrutura do laboratório

Após a implementação, o Lab04 possui a seguinte organização:

```

Lab04/

├── common.py
├── experiment01_orderer_with_genesis.py
│
├── configtx.yaml
├── crypto-config.yaml
│
├── crypto-material/
│
├── channel-artifacts/
│   └── genesis.block
│
└── scripts/
|
├── generate-artifacts.sh
├── generate-crypto.sh
├── generate-genesis.sh
├── clean.sh
└── prepare-lab.sh

```

---

# Descrição dos arquivos

## experiment01_orderer_with_genesis.py

Arquivo principal responsável pela execução do experimento.

Responsabilidades:

- inicializar o ambiente;
- criar a topologia Fogbed;
- criar o container do Orderer;
- iniciar a execução;
- realizar diagnósticos;
- manter o ambiente disponível para inspeção.


Fluxo:

```

prepare_environment()

```
    |

    v
```

Gerar certificados

```
    |

    v
```

Gerar genesis block

```
    |

    v
```

Criar Fogbed Experiment

```
    |

    v
```

Criar container Orderer

```
    |

    v
```

Executar experimento

```

---

# common.py

Arquivo responsável por centralizar funções reutilizadas.

Principais responsabilidades:

- gerenciamento dos caminhos do laboratório;
- geração automática dos artefatos Fabric;
- criação dos containers Fabric;
- funções auxiliares de diagnóstico.


Principais funções:

## prepare_environment()

Verifica se os artefatos necessários existem.

Caso o bloco gênesis não exista:

```

crypto-material/
channel-artifacts/genesis.block

```

executa automaticamente:

```

generate-artifacts.sh

```

---

## create_orderer()

Responsável por criar o container Docker do Hyperledger Fabric Orderer.

Configura:

- imagem Docker;
- volumes;
- variáveis de ambiente;
- certificados;
- bloco gênesis.

---

## show_container_details()

Realiza diagnósticos do container:

- hostname;
- versão do Fabric;
- processos ativos;
- informações de execução.

---

# Geração dos artefatos Fabric

Antes da inicialização do Orderer é necessário gerar os artefatos criptográficos.

O processo é automatizado pelo script:

```

scripts/generate-artifacts.sh

```

Ele executa duas etapas:

```

generate-artifacts.sh

```
    |
    |
    +---- generate-crypto.sh
    |
    |
    +---- generate-genesis.sh
```

```

---

# Etapa 1 - Geração dos certificados

Arquivo:

```

scripts/generate-crypto.sh

```

Utiliza a ferramenta:

```

cryptogen

````

Responsável por gerar:

- MSP das organizações;
- certificados TLS;
- identidades dos nós.


Comando executado:

```bash
cryptogen generate \
--config=crypto-config.yaml \
--output=crypto-material
````

Resultado:

```
crypto-material/

├── ordererOrganizations/
│
└── peerOrganizations/

```

---

# Etapa 2 - Geração do bloco gênesis

Arquivo:

```
scripts/generate-genesis.sh
```

Utiliza:

```
configtxgen
```

A ferramenta utiliza:

```
configtx.yaml
```

para gerar o bloco inicial da rede.

Comando:

```bash
configtxgen \
-profile SampleEtcdRaft \
-channelID system-channel \
-outputBlock \
channel-artifacts/genesis.block
```

Resultado:

```
channel-artifacts/

└── genesis.block

```

Esse arquivo contém:

* configuração do sistema;
* organizações participantes;
* configuração do Orderer;
* parâmetros do consenso.

---

# Configuração do Orderer

O container utiliza a imagem:

```
hyperledger/fabric-orderer:2.5
```

Os seguintes volumes são montados:

## MSP

Origem:

```
crypto-material/
└── ordererOrganizations/
```

Destino:

```
/etc/hyperledger/fabric/msp
```

Responsável pela identidade do Orderer.

---

## TLS

Origem:

```
crypto-material/
└── ordererOrganizations/
```

Destino:

```
/etc/hyperledger/fabric/tls
```

Responsável pela comunicação segura.

---

## Genesis Block

Origem:

```
channel-artifacts/genesis.block
```

Destino:

```
/etc/hyperledger/fabric/genesis.block
```

Responsável pelo bootstrap inicial da rede.

---

# Variáveis de ambiente utilizadas

O container recebe as configurações:

```python
ORDERER_GENERAL_BOOTSTRAPMETHOD=file
```

Define que o Orderer será inicializado utilizando arquivo.

---

```python
ORDERER_GENERAL_BOOTSTRAPFILE=/etc/hyperledger/fabric/genesis.block
```

Define o bloco inicial utilizado.

---

```python
ORDERER_GENERAL_LOCALMSPID=OrdererMSP
```

Define o MSP local do Orderer.

---

```python
ORDERER_GENERAL_LOCALMSPDIR=/etc/hyperledger/fabric/msp
```

Define onde estão os certificados MSP.

---

```python
ORDERER_GENERAL_TLS_ENABLED=true
```

Habilita comunicação TLS.

---

```python
ORDERER_GENERAL_LISTENPORT=7050
```

Define a porta de comunicação do Orderer.

---

# Execução

Para executar o experimento:

```bash
sudo -E python3 experiment01_orderer_with_genesis.py
```

---

# Fluxo esperado

Durante a execução ocorre:

## 1 - Verificação dos artefatos

Saída esperada:

```
[INFO] Artefatos inexistentes.
[INFO] Gerando ambiente...
```

---

## 2 - Geração dos certificados

Exemplo:

```
Gerando certificados Fabric

cryptogen encontrado

Certificados gerados com sucesso!
```

---

## 3 - Geração do bloco gênesis

Exemplo:

```
Generating genesis block

[OK] Genesis block criado com sucesso.
```

---

## 4 - Inicialização do Fogbed

Exemplo:

```
*** Creating network

*** Starting controller

*** Starting switches

```

---

## 5 - Inicialização do Orderer

Exemplo:

```
ORDERER EXECUTANDO COM SUCESSO
```

---

# Validação do funcionamento

Após a inicialização, o laboratório permite executar comandos de inspeção.

## Verificar versão do Fabric

```bash
orderer version
```

Resultado esperado:

```
Version: v2.5.16
```

---

## Verificar processo ativo

```bash
ps aux
```

Resultado esperado:

```
root  orderer
```

---

## Verificar logs

```bash
docker logs <container>
```

O log deve apresentar:

```
Starting with system channel:
system-channel,
consensus type: etcdraft
```

---

# Resultado obtido

Ao final do experimento foi possível validar:

✅ geração automática de certificados Fabric;

✅ geração automática do bloco gênesis;

✅ resolução dinâmica dos binários Fabric;

✅ execução do Orderer dentro de container Docker;

✅ integração inicial entre Fogbed e Hyperledger Fabric;

✅ inicialização do consenso Raft;

✅ criação automática do sistema de ledger.

Mensagem final esperada:

```
Start accepting requests as Raft leader at block [0]
```

Esse resultado confirma que o Orderer foi inicializado corretamente.

---

# Problemas encontrados e soluções

## 1. Binários Fabric não encontrados utilizando sudo

Problema:

Ao executar:

```bash
sudo python3 experiment01_orderer_with_genesis.py
```

o ambiente perdeu o PATH contendo:

```
cryptogen
configtxgen
```

Solução:

Foi implementada uma resolução dinâmica dos binários:

Ordem de busca:

1. variável `FABRIC_BIN`;
2. diretório `third_party/fabric-samples/bin`;
3. diretório do usuário original (`SUDO_USER`);
4. diretórios do sistema.

Isso permite executar o laboratório em diferentes ambientes sem depender de caminhos absolutos.

---

## 2. Formato dos volumes Fogbed

Problema:

A API do Fogbed espera volumes no formato:

```
host_path:container_path
```

e não tuplas Python.

Correção:

Antes:

```python
(
"/origem",
"/destino"
)
```

Depois:

```python
"/origem:/destino"
```

---

## 3. TLS obrigatório para Orderer Raft

Problema:

Erro:

```
TLS is required for running ordering nodes of cluster type.
```

Solução:

Habilitação do TLS:

```python
ORDERER_GENERAL_TLS_ENABLED=true
```

e montagem dos certificados:

```
server.key
server.crt
ca.crt
```

---



# Conclusão

O Lab04 estabelece a primeira prova de conceito da integração entre Hyperledger Fabric e Fogbed.

A partir deste ponto, o ambiente possui uma infraestrutura automatizada capaz de provisionar componentes Fabric dentro de uma arquitetura de experimentação em névoa computacional, servindo como base para a construção de uma arquitetura modular e extensível.


