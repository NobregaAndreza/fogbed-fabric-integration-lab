# LAB02 - Execução Incremental do Hyperledger Fabric em Containers Fogbed

## Objetivo

Este experimento tem como objetivo validar a execução inicial de componentes do Hyperledger Fabric dentro de containers Docker gerenciados pelo Fogbed.

A proposta desta etapa é verificar a integração entre:

- Fogbed como plataforma de emulação de ambientes Fog/Edge;
- Containernet como camada de virtualização de containers;
- Docker como mecanismo de execução dos serviços;
- Hyperledger Fabric como aplicação distribuída a ser posteriormente implantada na infraestrutura emulada.

O experimento representa o primeiro passo para a construção de uma arquitetura baseada em:

```
Hyperledger Fabric
        |
     Docker
        |
  Containernet
        |
      Fogbed
```

---

# Ambiente utilizado

## Componentes

| Componente | Versão |
|---|---|
| Sistema operacional | Ubuntu 22.04 |
| Python | 3.10 |
| Fogbed | 1.3.0 |
| Containernet | versão atual do repositório oficial |
| Hyperledger Fabric | 2.5.16 |
| Docker | instalado no ambiente local |

---

# Arquitetura do experimento

A topologia inicial consiste em uma infraestrutura simples contendo:

- Uma instância virtual Fogbed;
- Um container Docker baseado na imagem oficial do Hyperledger Fabric Tools;
- Dois switches virtuais Containernet;
- Um controlador OpenFlow padrão.

Representação:

```
             Fogbed

        Virtual Instance
              |
          Containernet

              |
        +-------------+
        |     s2      |
        +-------------+
              |
        fabric-tools
        Fabric 2.5.16

              |
        +-------------+
        |     s1      |
        +-------------+
```

---

# Implementação

O experimento foi implementado utilizando a API Python do Fogbed.

O container utilizado foi:

```
hyperledger/fabric-tools:2.5
```

Esse container fornece as ferramentas de linha de comando do Hyperledger Fabric, incluindo:

- peer CLI;
- ferramentas de configuração;
- comandos auxiliares para interação com redes Fabric.

---

# Execução

O experimento foi executado através de:

```bash
sudo -E python3 experiment01_fabric_container.py
```

O uso de privilégios administrativos é necessário porque o Fogbed/Containernet realiza operações de baixo nível no sistema operacional, incluindo:

- criação de interfaces virtuais;
- namespaces de rede;
- bridges;
- configuração de switches virtuais.

---

# Resultado da execução

A topologia foi criada corretamente:

```
*** Creating network

*** Adding hosts:
ftools

*** Adding switches:
s1 s2

*** Adding links:
(ftools, s2) (s1, s2)
```

O container foi inicializado:

```
ftools: kwargs {'ip': '10.0.0.10'}
```

A rede virtual foi configurada pelo Containernet:

```
*** Configuring hosts

ftools
```

---

# Validação do Hyperledger Fabric

Após a inicialização do container, foi executado o comando:

```bash
peer version
```

Resultado obtido:

```
Version: v2.5.16
Commit SHA: f871cf9
Go version: go1.26.4
OS/Arch: linux/amd64

Chaincode:
 Base Docker Label: org.hyperledger.fabric
 Docker Namespace: hyperledger
```

## Análise

O resultado confirma que:

- o container Docker foi iniciado corretamente pelo Fogbed;
- o ambiente possui os binários do Hyperledger Fabric disponíveis;
- a versão utilizada corresponde à linha 2.5.x definida para o projeto;
- a camada de virtualização não interfere na execução do software Fabric.

---

# Teste de conectividade

Foi iniciado um teste de comunicação dentro do container.

O teste apresentou o seguinte retorno:

```
bash: ip: command not found
```

## Diagnóstico

O erro não está relacionado ao Fogbed ou ao Hyperledger Fabric.

A causa é que a imagem:

```
hyperledger/fabric-tools:2.5
```

utiliza uma distribuição Linux mínima e não possui instalado o pacote:

```
iproute2
```

responsável pelo comando:

```bash
ip
```

---

# Ajuste necessário

Para os próximos experimentos, será adicionada uma etapa de preparação do container contendo ferramentas básicas de rede:

```bash
apt update
apt install -y iproute2 iputils-ping
```

Isso permitirá realizar testes como:

```bash
ip addr
```

e:

```bash
ping <endereço>
```

dentro dos containers Fabric.

---

# Conclusão

O experimento confirmou a viabilidade da execução de componentes Hyperledger Fabric dentro de uma infraestrutura Fogbed baseada em containers.

Resultados obtidos:

| Validação | Resultado |
|-|-|
| Inicialização da topologia Fogbed | ✅ Sucesso |
| Integração Fogbed + Containernet | ✅ Sucesso |
| Execução de container Docker | ✅ Sucesso |
| Download da imagem Fabric | ✅ Sucesso |
| Execução do binário `peer` | ✅ Sucesso |
| Compatibilidade Fabric 2.5 | ✅ Sucesso |
| Testes avançados de rede | ⚠️ Necessitam instalação de ferramentas adicionais |

Esta etapa estabelece a base para os próximos experimentos, onde serão adicionados componentes reais de uma rede Hyperledger Fabric, incluindo:

- Peer;
- Orderer;
- Certificate Authority (CA);
- Criação de canais;
- Deploy de chaincodes;
- Avaliação da comunicação entre nós distribuídos no ambiente Fog/Edge.

# Experimento 04 — Inicialização de Serviços Hyperledger Fabric no Fogbed

## Objetivo

Este experimento tem como objetivo avançar a integração entre o Fogbed e o Hyperledger Fabric, adicionando componentes de infraestrutura necessários para uma rede Fabric real.

Nesta etapa foi realizada a tentativa de inicialização de um serviço **Hyperledger Fabric Orderer** utilizando containers Docker gerenciados pelo Fogbed/Containernet.

O experimento busca validar:

- criação de containers Fabric dentro do ambiente Fogbed;
- configuração de variáveis de ambiente necessárias para os serviços;
- comunicação entre componentes da rede virtual;
- comportamento do serviço Orderer durante sua inicialização.

---

## Arquitetura Experimental

A topologia utilizada foi composta por:

    +----------------+
    | Virtual Network|
    +----------------+

          s1

    /          \

 peer0       orderer0



Componentes:

| Componente | Container | Imagem |
|---|---|---|
| Peer | peer0 | hyperledger/fabric-peer:2.5 |
| Orderer | orderer0 | hyperledger/fabric-orderer:2.5 |

---

## Implementação

Foi criado o experimento:
e chegamos ao ponto em que o nó dá erro, pois falta o camminho do do bloco gênesis. O objetivo para o próximo experimento é resolver esse problema.