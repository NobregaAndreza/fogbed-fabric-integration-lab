# Lab06 — application channel Fabric + Fogbed [VALIDADO]

## Objetivo

Validar a rede mínima com Orderer e Peer no application channel `mychannel`,
incluindo a conexão do blocksprovider ao Ordering Service. O experimento final
foi confirmado manualmente em execução limpa e independente. Esta marca registra
o resultado informado pelo usuário; não representa uma nova execução do assistente.

## Topologia

```text
cloud / orderer0 ── link Fogbed ── fog / peer0
OrdererMSP                         Org1MSP
orderer0.example.com:7050           peer0.org1.example.com:7051
Admin mTLS :9443                   Operations :9443 (outro namespace)
Operations :8443
              ambos participam de mychannel
```

Há uma organização de Orderer e uma de Peer, um nó de cada tipo e consenso
etcdraft. Os endereços efetivos são descobertos em execução: não se presume que
os IPs 10.0.0.x declarados estejam presentes na rede real.

## Pré-requisitos

- Linux, Python 3, Fogbed/Containernet e Docker configurados como nos Labs anteriores.
- Permissões sudo para Docker, namespaces, chroot e acesso a `/proc`.
- Ferramentas do host: bash, ip, nsenter, unshare e mount.
- Imagens `hyperledger/fabric-peer:2.5` e `hyperledger/fabric-orderer:2.5`.
  O resultado experimental relatado utilizou Fabric 2.5.16.
- Binários Fabric 2.5 (`cryptogen`, `configtxgen`, `osnadmin`), resolvidos pelo
  `scripts/fabric-env.sh`: FABRIC_BIN, instalação local ou PATH conforme o script.
- Os módulos compartilhados dos Labs anteriores devem permanecer no repositório;
  não é necessário executar aqueles Labs previamente.

Execute somente um experimento por vez: os nomes de containers são compartilhados.

## Execução final independente

Na raiz do repositório, com os experimentos encerrados:

```bash
cd Lab06
sudo bash clean.sh && sudo -E python3 experiment04_peer_join_channel.py
```

Para repetir preservando artefatos, execute apenas o segundo comando. A preparação
cria crypto se ausente/vazio, reutiliza identidades existentes e reescreve o bloco.
Material parcial produz erro, sem rotação silenciosa de certificados.

ENTER encerra a rede; os experimentos 02–04 preservam os artefatos. `clean.sh`
remove `crypto-material` e `channel-artifacts`, mas não para containers.

## Experimentos e evolução incremental

| Experimento | Responsabilidade |
|---|---|
| `experiment01_baseline.py` | Baseline Peer + Orderer, processos, namespace/IP, TCP/TLS; conserva bootstrap histórico por system channel. |
| `experiment02_orderer_channel_participation.py` | Orderer sem system channel; consulta Admin mTLS inicialmente sem canais. |
| `experiment03_orderer_join_channel.py` | Prepara artefatos, executa osnadmin join e confirma o Orderer no canal. |
| `experiment04_peer_join_channel.py` | Reconstrói rede/canal, aplica resolução dinâmica, ingressa Peer, consulta canais e verifica delivery. |

Cada experimento é uma entrada independente. Pode repetir etapas necessárias por
helpers, mas não executa outro `experimentXX.py` nem exige artefatos deixados por
uma sessão anterior. O cenário final foi validado após `clean.sh`.

A baseline anterior utilizou legitimamente `system-channel -> genesis.block ->
Orderer` para investigar processos, MSP, TLS e Raft. O fluxo de aplicação evoluiu para:

```text
crypto + configtx.yaml -> mychannel.block
Orderer (bootstrap none + Participation API + Admin mTLS)
  -> osnadmin channel join -> Orderer em mychannel
Peer + mapeamento dinâmico -> peer channel join -b mychannel.block
  -> peer channel list -> resolução/TLS -> blocksprovider conectado
```

O teste de resolução/TLS é feito antes do Peer join para isolar falhas; a conexão
delivery é observada depois. Não usamos `peer channel create` ou transação
`-outputCreateChannelTx` no fluxo do application channel.

## Resultados validados

- [VALIDADO] `mychannel.block` gerado com `FogbedApplicationChannel`.
- [VALIDADO] Orderer sem system channel, Participation API e Admin/mTLS.
- [VALIDADO] Estado inicial experimental: `{"systemChannel":null,"channels":null}`.
- [VALIDADO] osnadmin join: HTTP 201, `mychannel`, `consenter`, `active`, altura 1.
- [VALIDADO] Consulta posterior associa mychannel ao Orderer; systemChannel continua null.
- [VALIDADO] Peer ativo, join com exit code zero e listagem contendo mychannel.
- [VALIDADO] Resolução dinâmica da identidade Fabric do Orderer no ambiente do Peer.
- [VALIDADO] TCP/TLS com validação de CA e hostname; blocksprovider comunicando com Orderer.
- [VALIDADO] Orderer líder Raft do canal.
- [VALIDADO] Execução limpa independente e correção do falso negativo do parser CLI.

A documentação oficial exemplifica listas de canais existentes. `channels: null`
com zero canais é a observação do Fabric 2.5.16 deste projeto; não é apresentado
como comportamento especificado pelo exemplo oficial consultado.

## Evidências da execução manual

```text
Created ledger [mychannel] with genesis block
Joining gossip network of channel mychannel
This peer will retrieve blocks from ordering service
Pulling next blocks from ordering service
channel=mychannel orderer-address=orderer0.example.com:7050
1 became leader at term 2 channel=mychannel
Start accepting requests as Raft leader at block [0]
```

Join retornou `Successfully submitted proposal to join channel` e exit code 0;
`peer channel list` retornou `mychannel`. O marcador interno de exit code é separado
da saída funcional. stdout/stderr chegam combinados pelo terminal; ANSI e quebras
de linha são normalizados. Join depende do status real; list exige status zero e
uma linha exata com o nome do canal, sem comparar o output inteiro.

## Resolução de nomes: problema e solução experimental

`Orderer.Addresses` define `orderer0.example.com:7050`; o profile herda esse valor,
incorporado pelo configtxgen ao bloco em `/Channel/OrdererAddresses`.
`EtcdRaft.Consenters.Host/Port` descreve também o consenter Raft. Não há endpoints
por organização neste YAML. Editar o YAML não altera um canal já criado.

O Peer ingressou usando o bloco local, mas inicialmente não resolvia o hostname
para delivery (`Could not connect to ordering service`, `no such host`). Os checks
por IP contornavam DNS; a eleição Raft não comprovava acesso do Peer ao Orderer.

`map_orderer_for_peer` usa o IP descoberto e atualiza apenas o hosts do Peer via
`/proc/<pid>/root/etc/hosts`, antes dos joins. Preserva aliases alheios, substitui
entradas antigas e recusa modificar um arquivo compartilhado com o host. Não altera
TLS, certificados ou endpoint do canal. A associação é recriada a cada execução.

O hosts temporário de `join_orderer_to_channel` pertence somente ao mount namespace
do comando osnadmin. Ele não substitui o mapeamento necessário ao processo Peer.
`check_peer_orderer_name` usa a rede e os arquivos de resolução do Peer, carregando
Python/CA do host antes de chroot somente no subprocesso. Não instala ferramentas
na imagem e exige certificado válido para o hostname esperado.

## Organização do código

`common.py` concentra caminhos, adaptação de containers e operações reutilizáveis;
os experimentos orquestram etapas e apresentam resultados. Uma instância privada
do common do Lab05 fornece os construtores e diagnósticos herdados. No modo de
application channel, os mounts usam crypto do Lab06. A baseline histórica conserva
seus mounts originais; não foi reescrita nesta documentação.

- `prepare_environment`: geração ou verificação de artefatos via scripts existentes.
- `create_orderer` / `create_peer`: descrições Fogbed e configuração MSP/TLS.
- `check_orderer_participation_api` / `join_orderer_to_channel`: Admin mTLS e ingresso.
- `run_peer_channel`: contexto administrativo CLI e interpretação de status/lista.
- `map_orderer_for_peer`: associação dinâmica visível ao processo Peer.
- `check_peer_orderer_name`: resolução e TCP/TLS autenticado.
- `check_peer_delivery`: conexão e logs na janela posterior ao join.

Docstrings descrevem parâmetros, retorno, efeitos colaterais e limites dos helpers.
O Peer usa o MSP do nó; somente o CLI recebe o MSP administrativo montado em leitura.

## Limitações e interpretação dos checks

- O diagnóstico TLS herdado da baseline desativa verificação de CA/nome; o novo
  check de resolução/TLS e as chamadas administrativas fazem essa verificação.
- O check geral de logs busca panic/FATAL/CRIT. Delivery possui check específico
  para falhas de conexão/DNS e desconexão; ausência de panic isoladamente não basta.
- Delivery observa três amostras ESTABLISHED, espaçadas em 1 s, e logs desde um
  instante UTC imediatamente anterior ao join. A janela é limitada; não prova
  estabilidade indefinida, recebimento de novos blocos ou transações.
- O IP descoberto é o primeiro IPv4 não-loopback; a interface/rota da topologia
  emulada ainda precisa de tratamento mais explícito numa integração futura.
- Os ledgers dos containers não têm persistência garantida entre experimentos.
- O cliente mTLS administrativo reutiliza o par TLS do Orderer neste laboratório.
- Não há chaincode, aplicação cliente, SDK, múltiplos nós ou plugin neste Lab.

## Descobertas para a futura integração

| Conceito | Exemplo |
|---|---|
| Identidade Fabric estável | orderer0.example.com |
| Nome do nó Fogbed | orderer0 |
| Nome observado do container | mn.orderer0 |
| Endereço efetivo | IP descoberto em execução |

A integração precisa manter `identidade lógica Fabric ↔ endereço efetivo da
topologia`. O hosts dinâmico é uma solução experimental, não a arquitetura definitiva
do plugin. DNS interno ou mecanismos nativos poderão substituir sua implementação
preservando identidades/certificados e os caminhos de rede emulados.

## Referências

- [Channel Participation API — Fabric 2.5](https://hyperledger-fabric.readthedocs.io/en/release-2.5/create_channel/create_channel_participation.html).
- [peer channel — Fabric 2.5](https://hyperledger-fabric.readthedocs.io/en/release-2.5/commands/peerchannel.html).
- [Configuração do Orderer](https://github.com/hyperledger/fabric/blob/release-2.5/sampleconfig/orderer.yaml).

O próximo laboratório estuda lifecycle. Nenhum resultado do Lab07 está incluído
na validação do Lab06.
