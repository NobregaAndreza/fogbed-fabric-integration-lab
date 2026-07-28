
# LAB 01 — Validação do Hyperledger Fabric test-network

## Objetivo

Este laboratório tem como objetivo validar o funcionamento de uma rede mínima utilizando o Hyperledger Fabric antes da integração com o Fogbed.

A configuração inicial do `test-network` já havia sido realizada durante a Iniciação Científica (IC), porém este laboratório tem como propósito revisitar esse ambiente utilizando uma versão mais recente do Hyperledger Fabric, verificando possíveis mudanças na configuração, ferramentas e fluxo de execução.

Além disso, essa etapa serve como base para compreender os componentes fundamentais de uma rede Fabric que posteriormente serão incorporados ao ambiente de experimentação com Fogbed.

---

# Ambiente utilizado

Versão do Hyperledger Fabric:

```text
Fabric v2.5.16
````

Sistema operacional:

```text
Ubuntu 22.04.5 LTS
```

Componentes utilizados:

* Hyperledger Fabric binaries
* Fabric Samples
* Docker
* Docker Compose

---

# Arquitetura da rede de teste

A rede utilizada neste laboratório é baseada no `test-network` oficial disponibilizado pelo Hyperledger Fabric.

A arquitetura mínima contém:

```text
Docker Compose

├── peer0.org1.example.com
├── peer0.org2.example.com
├── orderer.example.com
├── ca_org1
├── ca_org2
└── ca_orderer
```

---

## Peers

Os peers são responsáveis por manter o ledger, executar chaincodes e validar transações.

Neste laboratório foram utilizados:

* `peer0.org1.example.com`
* `peer0.org2.example.com`

---

## Orderer

O orderer é responsável pela ordenação das transações e distribuição dos blocos para os peers da rede.

Componente utilizado:

* `orderer.example.com`

---

## Certificate Authority (CA)

As autoridades certificadoras são responsáveis pela criação e gerenciamento das identidades utilizadas na rede.

Componentes utilizados:

* `ca_org1`
* `ca_org2`
* `ca_orderer`

---

# Inicialização da rede

A rede foi inicializada utilizando o script oficial do Hyperledger Fabric:

```bash
cd third_party/fabric-samples/test-network

./network.sh up
```

Após a inicialização, os containers foram verificados utilizando:

```bash
docker ps
```

Resultado esperado:

```text
peer0.org1.example.com
peer0.org2.example.com
orderer.example.com
```

---

# Criação do canal

Foi criado um canal para comunicação entre as organizações da rede.

Comando utilizado:

```bash
./network.sh createChannel -c canalteste
```

Canal criado:

```text
canalteste
```

Após a criação, os peers das organizações foram associados ao canal:

* Org1
* Org2

O processo confirmou:

* criação do bloco gênese do canal;
* participação do orderer;
* entrada dos peers no canal;
* configuração dos anchor peers.

---

# Deploy do Chaincode

Foi utilizado o chaincode de exemplo disponibilizado pelo Hyperledger Fabric:

```text
asset-transfer-basic
```

O deploy foi realizado utilizando:

```bash
./network.sh deployCC \
-ccn basic \
-ccp ../asset-transfer-basic/chaincode-go \
-ccl go
```

O chaincode foi instalado e aprovado pelas organizações:

```text
Org1MSP: true
Org2MSP: true
```

Resultado:

```text
Committed chaincode definition for chaincode 'basic'

Version: 1.0
Sequence: 1
Approvals:
[Org1MSP: true, Org2MSP: true]
```

---

# Teste de interação com a rede

Após o deploy do chaincode, foram realizadas operações de interação com o ledger.

## Inicialização do ledger

O ledger foi inicializado utilizando a função `InitLedger`:

```bash
peer chaincode invoke \
-o localhost:7050 \
-C canalteste \
-n basic \
-c '{"function":"InitLedger","Args":[]}'
```

Resultado:

```text
Chaincode invoke successful.
result: status:200
```

---

## Consulta dos ativos

Foi realizada uma consulta para verificar os ativos armazenados:

```bash
peer chaincode query \
-C canalteste \
-n basic \
-c '{"Args":["GetAllAssets"]}'
```

Resultado obtido:

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
  }
]
```

A consulta confirmou que o chaincode estava executando corretamente e que os dados estavam persistidos no ledger.

---

# Observações

Durante a validação da rede foram identificadas algumas diferenças em relação aos experimentos realizados anteriormente durante a Iniciação Científica (IC), principalmente relacionadas às versões dos componentes utilizados.

O objetivo desta etapa não é apenas reproduzir a execução anterior, mas também garantir que a arquitetura utilizada atualmente esteja compatível com as versões mais recentes do Hyperledger Fabric.

A rede criada neste laboratório será utilizada como referência para os próximos experimentos de integração.

---

# Conclusão

O ambiente mínimo do Hyperledger Fabric foi validado com sucesso.

Os testes confirmaram:

* execução dos binários do Fabric;
* inicialização da rede utilizando Docker Compose;
* criação de organizações e identidades;
* criação e configuração de canais;
* comunicação entre peers;
* instalação e aprovação de chaincodes;
* interação com o ledger através de transações e consultas.

A rede validada será utilizada como base para os próximos laboratórios envolvendo a integração entre Hyperledger Fabric e Fogbed.

Arquitetura futura:

```text
Hyperledger Fabric

        ↓

      Fogbed

        ↓

   Containernet

        ↓

      Docker
```

O próximo laboratório iniciará a adaptação dessa arquitetura para execução dos componentes do Hyperledger Fabric dentro do ambiente de emulação do Fogbed.

