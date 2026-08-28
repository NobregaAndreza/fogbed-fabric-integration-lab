# Lab05: Integração Incremental do Peer Hyperledger Fabric 2.5 com o Fogbed

## Visão Geral

Este laboratório dá início à integração do nó **Peer (Hyperledger Fabric 2.5)** com a plataforma **Fogbed**. Seguimos uma estratégia estritamente incremental e modular:

1. Componente isolado funcionando (Peer)
2. Identificar e parametrizar configurações variáveis (Nome, IP, Domínio, MSP ID, Porta, TLS)
3. Integrar múltiplos componentes (Peer + Orderer)
4. Validar conectividade de rede sem criar canais prematuramente

---

## Estrutura do Diretório `Lab05/`

```
Lab05/
├── README.md                           # Este documento explicativo
├── notes.md                            # Anotações técnicas para auxílio na escrita do TCC
├── common.py                           # Funções parametrizadas e diagnósticos por camada via nsenter
├── crypto-config.yaml                  # Definição das identidades criptográficas (OrdererOrg + Org1 Peer)
├── configtx.yaml                       # Configuração do Genesis Block com o consórcio FogbedConsortium
├── clean.sh                            # Script auxiliar de limpeza dos artefatos do Lab05
├── scripts/
│   ├── fabric-env.sh                   # Resolução dinâmica dos binários (cryptogen, configtxgen) inclusive sob sudo
│   ├── generate-crypto.sh              # Automação de geração MSP/TLS via cryptogen
│   ├── generate-genesis.sh             # Automação de geração do genesis.block via configtxgen
│   ├── generate-artifacts.sh           # Script mestre de geração de artefatos
│   └── clean.sh                        # Remoção de crypto-material/ e channel-artifacts/
├── experiment01_peer.py                # Experimento 01: Subir peer0 isolado no Fogbed
└── experiment02_peer_orderer.py         # Experimento 02: Subir peer0 + orderer0 na mesma topologia Fogbed
```

---

## Diagnósticos por Camadas com Exceções Técnicas Transparentes

### Por que os diagnósticos anteriores falhavam?
1. **Ausência de utilitários nas imagens Fabric 2.5**: As imagens oficiais (`hyperledger/fabric-peer:2.5` e `hyperledger/fabric-orderer:2.5`) são minimalistas e não possuem `bash`, `openssl`, `curl`, `wget`, `nc`, `ss`, `netstat`, `ping` ou suporte a `/dev/tcp`.
2. **Isolamento do Host**: Testes de socket executados a partir do host raiz sofriam `TimeoutError` devido à falta de rota para os IPs virtuais `10.0.0.20` e `10.0.0.30` do Mininet.
3. **Condição de Corrida (Boot)**: Os processos aparecem no `ps aux` antes que o Fabric conclua a carga das chaves MSP/TLS e abra o listener gRPC.

### Solução via `nsenter` com Exceções Reais
- O diagnóstico obtém o PID real do container (`docker inspect -f '{{.State.Pid}}'`).
- Executa a validação usando `nsenter -t <pid> -n python3 -c "..."` diretamente dentro do Network Namespace de cada container.
- Exibe a exceção técnica real em caso de falha (`ConnectionRefusedError`, `TimeoutError`, `certificate verify failed`, `HTTP 503`, etc.).

---

## Camadas essenciais de validação no `experiment02_peer_orderer.py`

1. `[PROCESS]`: Confirmação dos processos `orderer` e `peer` via `ps aux` e checagem de logs.
2. `[NETWORK NAMESPACE / IPS]`: Confirmação do namespace isolado e do IP real observado dentro do container.
3. `[TCP LOCAL]`: Conexão TCP pura em `127.0.0.1:7050` e `127.0.0.1:7051` (sem TLS / sem HTTP).
4. `[TCP NETWORK]`: Conexão TCP pura a partir do namespace do `peer0` até o IP real do `orderer0` na porta gRPC.
5. `[TLS LOCAL]`: Handshake TLS em `127.0.0.1` usando o `server_hostname` correto do certificado.
6. `[TLS NETWORK]`: Handshake TLS real do `peer0` até o `orderer0` no IP real do namespace.

> Observação importante: `Operations Service /healthz` é diagnóstico auxiliar e foi removido do fluxo principal para manter o Lab05 focado na comunicação Fabric principal.

---

## Fluxo Interativo de Execução

> **Nota**: Os experimentos utilizam o Fogbed e requerem permissões de superusuário (`sudo`).

### 1. Executando o Experimento 01 (Peer Isolado)

```bash
cd Lab05
sudo python3 experiment01_peer.py
```

### 2. Executando o Experimento 02 (Peer + Orderer)

```bash
cd Lab05
sudo python3 experiment02_peer_orderer.py
```

### 3. Encerramento e Limpeza Interativa

Ao finalizar a exibição dos diagnósticos, o experimento permanece ativo até a confirmação do usuário:

```text
Pressione ENTER para finalizar...
```

Após o encerramento da topologia Fogbed, o script consulta interativamente sobre a limpeza:

```text
Executar a limpeza do Lab05? [y/N]:
```
