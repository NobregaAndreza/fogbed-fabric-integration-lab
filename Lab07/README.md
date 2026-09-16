# Lab07 — lifecycle inicial de chaincodes

## Objetivo e estado

- **Experiment 01 — package/install/queryinstalled [VALIDADO]**
- **Experiment 02 — approveformyorg [VALIDADO]**
- **Experiment 03 — commit/querycommitted [VALIDADO]**
- **Experiment 03b — Runtime Chaincode → Peer [VALIDADO]**
- **Experiment 04 — invoke/query [PRÓXIMO]**

Reconstruir a rede mínima validada no Lab06 e comprovar que o lifecycle de um chaincode local
pode ser executado e registrado no Peer. Os Experimentos 01, 02, 03 e 03b foram validados manualmente.
No Experiment 03b, o endpoint operacional do chaincode é resolvido dinamicamente na inicialização do container.
O próximo passo do Lab07 é o Experiment 04 (operações de negócio `invoke` e `query`).

## Relação com o Lab06 e independência

Lab06 validou Orderer/Peer em mychannel, resolução de nome, TLS e delivery. Lab07
carrega uma instância privada de seu common e ajusta apenas os caminhos dessa
instância para Lab07. Os construtores e helpers de geração, MSP/TLS, namespaces,
joins, resolução e delivery são reutilizados sem copiar suas implementações.

Não é necessário executar Lab06 antes. O repositório precisa conter Lab05/Lab06
para reutilizar seus módulos, scripts e configurações; isso é dependência de código,
não de estado ou artefatos anteriores. Crypto, bloco e pacotes ficam no Lab07.
Não execute Labs simultaneamente: os nomes orderer0/peer0 são compartilhados.

## Estrutura

```text
Lab07/
  common.py                            # infraestrutura reutilizada + lifecycle
  experiment01_package_install.py      # package/install/queryinstalled
  experiment02_approve_chaincode.py     # até aprovação da organização
  experiment03_commit_chaincode.py      # até commit e consulta da definição
  experiment03b_chaincode_runtime.py   # endpoint dinâmico, runtime e registro do cc
  configtx.yaml -> ../Lab06/configtx.yaml
  crypto-config.yaml -> ../Lab06/crypto-config.yaml
  scripts/                             # links internos para geradores validados
  config/core.yaml                     # configuração local do CLI no host
  chaincodes/basic/                    # fontes Go, módulos, vendor e licença
  chaincode-packages/basic.tar.gz       # gerado; não versionado
  channel-artifacts/mychannel.block     # gerado; não versionado
  crypto-material/                     # gerado; não versionado
  tests/test_common.py                  # testes locais sem Docker/Fabric ativo
  clean.sh
```

Os links preservam o caminho de invocação Lab07 nos scripts (não usar readlink -f
para executá-los). As definições YAML continuam sendo a topologia mínima conhecida.
O core.yaml copiado é usado apenas pelo CLI do host; o Peer usa o de sua imagem.
Algumas mensagens textuais dos geradores compartilhados ainda mencionam Lab06;
os caminhos de execução/artefatos são os do Lab07, conforme os links e ROOT_DIR.

## Pré-requisitos

- Linux, sudo, Docker local em `/var/run/docker.sock`, Fogbed/Containernet e Python 3
  como na execução validada do Lab06.
- bash, ip, nsenter, unshare e mount no host.
- Binários Fabric 2.5 acessíveis por FABRIC_BIN ou PATH. O resolvedor também aceita
  o caminho local conhecido; o código do chaincode não depende dele.
- Go >= 1.23 no host (PATH ou `/usr/local/go/bin/go`), exigido pela cópia local basic.
- Imagens oficiais peer/orderer/ccenv/baseos **2.5.16**, disponíveis no Docker local.

Preparação das imagens, se ainda ausentes:

```bash
docker pull hyperledger/fabric-peer:2.5.16
docker pull hyperledger/fabric-orderer:2.5.16
docker pull hyperledger/fabric-ccenv:2.5.16
docker pull hyperledger/fabric-baseos:2.5.16
```

O experimento verifica pré-requisitos; não instala ferramentas nem baixa imagens
automaticamente. Go/vendor devem ser compatíveis com a toolchain da imagem ccenv.
O Fabric pode precisar de acesso externo se o builder exigir atualização de Go;
com toolchain compatível, vendor evita downloads de dependências do contrato.

**Necessidade nova do install:** o Peer monta o socket Docker e recebe explicitamente
VM endpoint, ccenv, baseos e timeout de build. O socket concede acesso ao daemon do
host; é uma escolha do laboratório para o builder padrão, não isolamento de produção.
O build utiliza containers auxiliares do Fabric, não novos nós Peer/Orderer.
Nenhuma ferramenta é instalada dentro das imagens Peer/Orderer.

## Chaincode basic e múltiplos chaincodes

`chaincodes/basic` contém uma cópia do asset-transfer-basic Go dos fabric-samples
locais, commit `65592350d7d7c51b02c8a4d89383d4bbdcc45725`. Foram mantidos entrypoint,
contrato, go.mod/go.sum, vendor e licenças; não há aplicação cliente ou suíte de mocks.
Veja a proveniência em `chaincodes/basic/README.md`.

A cópia e as dependências ficam no Lab07 para que remover o fabric-samples original
não remova o código necessário. Os binários Fabric são pré-requisitos separados:
se estavam naquele diretório removido, aponte FABRIC_BIN para outra instalação.
Não há import de fonte por caminho externo; o nome fabric-samples em go.mod é o
identificador do módulo local, não uma instrução para ler o repositório original.

CHAINCODES é um dicionário com `name`, `path`, `language` e `label`. Cada chaincode
fica em um diretório próprio. Para outro contrato, adicione uma entrada e selecione
`--chaincode <nome>`; as funções de lifecycle recebem explicitamente a definição.
Somente basic está fornecido. Os pré-requisitos atuais cobrem o build Go.

## Fluxo do experimento

```text
seleção/pré-requisitos -> preparar crypto e bloco -> subir Orderer + Peer
  -> IPs e mapeamento -> Orderer join -> Peer join/list -> validar delivery
  -> package -> install -> queryinstalled -> comparar label e package ID
  -> inspeção até ENTER -> parar rede e preservar artefatos
```

Package é local e não requer canal; install é operação do Peer, não uma transação
que aprova o chaincode no canal. A rede/canal são preparados antes por escolha
metodológica para preservar a baseline funcional do estudo.

## Funções do lifecycle

| Função | Responsabilidade e retorno |
|---|---|
| `package_chaincode` | CLI oficial package; publica arquivo após exit 0; retorna path, label, ID esperado e evidência. |
| `install_chaincode` | Verifica integridade do arquivo e envia install ao Peer; retorna exit/stdout/stderr. |
| `query_installed_chaincodes` | Executa consulta JSON, valida estrutura e retorna lista e evidência. |
| `identify_installed_package` | Exige correspondência exata de label e ID com o pacote local. |
| `peer_lifecycle` | Executa operações de lifecycle até querycommitted via Docker exec sem TTY, no contexto Admin/MSP/TLS do Peer. |
| `run_command` | Captura streams/exit e propaga erros/timeout sem repetir comandos. |

Os helpers herdados de canal continuam usando sua execução validada. Para lifecycle,
Docker exec sem TTY preserva exit code e mantém logs de stderr fora do JSON de stdout;
não foi copiado o parser de marcadores do Lab06.

## Pacote e package ID

O arquivo é `chaincode-packages/<name>.tar.gz`. O label identifica humanamente o
pacote. O package ID combina label e hash SHA256 do arquivo (`label:hash`). O teste
calcula o ID esperado sobre os bytes efetivos e exige que `queryinstalled` retorne
exatamente esse ID e label. Apenas encontrar o label não é suficiente.

A geração usa a cópia local e vendor; publicação em arquivo temporário evita
considerar pacote antigo como resultado de um comando que falhou. Instalação
aceita pelo CLI deve ser seguida pela consulta; sucesso de rede não implica
sucesso de instalação.

## Comandos e resultado esperado

Na raiz do repositório:

```bash
cd Lab07
sudo -E python3 experiment01_package_install.py --chaincode basic
```

Para uma nova execução limpa, encerre o experimento antes:

```bash
sudo bash clean.sh && sudo -E python3 experiment01_package_install.py
```

`clean.sh` remove apenas crypto, bloco e pacotes do Lab07. Não remove imagens,
fontes/vendor, containers ativos ou imagens auxiliares geradas pelo builder.

Esperado:

```text
Rede mínima funcional ............. [OK]
Peer em mychannel ................. [OK]
Delivery Peer -> Orderer .......... [OK]
Chaincode selecionado ............. [OK]
Chaincode package ................. [OK]  exit code: 0
Chaincode install ................. [OK]  exit code: 0
queryinstalled .................... [OK]  exit code: 0
Package ID identificado ........... [OK]  basic_1.0:<hash real>
```

Se falhar, preserve a saída completa (exit code e streams) e inspecione os logs do
Peer enquanto o ambiente está ativo. Falhas de install/build não são corrigidas
regenerando canal/crypto. ENTER para a rede e mantém os artefatos para análise.
A instalação fica no armazenamento do Peer; não se promete persistência ao remover
containers. O pacote local é preservado para inspeção.

## Limitações e próximas etapas

Um Peer/Orderer, uma organização de cada tipo, um canal. A observação de delivery
é limitada à janela herdada do Lab06. Sucesso de install não significa definição
aprovada/commitada nem disponibilidade de operações de negócio. O exemplo contém
funções de ativos, mas nenhuma delas é chamada nesta rodada.

- Experiment 01 — package/install/queryinstalled **[VALIDADO]**.
- Experiment 02 — approveformyorg **[VALIDADO]**.
- Experiment 03 — checkcommitreadiness/commit/querycommitted **[VALIDADO]**.
- Experiment 04 — invoke/query **[BLOQUEADO — NÃO IMPLEMENTADO]**.

O lifecycle está implementado até querycommitted; o Experiment 03 foi validado manualmente. Não há Fabric CA, novos nós ou
plugin. A validação de execução é manual, após envio dos resultados pelo usuário.

Referências: [CLI lifecycle Fabric 2.5](https://hyperledger-fabric.readthedocs.io/en/release-2.5/commands/peerlifecycle.html),
[build Go do Fabric 2.5.16](https://github.com/hyperledger/fabric/blob/v2.5.16/core/chaincode/platforms/golang/platform.go).

## Verificações locais realizadas pelo assistente

- Dez testes unitários passaram, sem Docker/Fabric ativo, cobrindo falhas CLI,
  JSON inválido, label/hash divergentes, contexto Admin e integridade do pacote.
- A cópia Go compilou offline com vendor e Go 1.23.0.
- Package real via CLI em `/tmp`: fontes/vendor e metadata conferidos; ID calculado
  pelo hash local igual ao retornado por `calculatepackageid` oficial. Esse último
  foi usado somente na verificação local, não acrescentado ao fluxo do experimento.
- Geradores compartilhados criaram crypto/bloco em diretório temporário isolado.
- A AST executável do Lab06 foi comparada antes/depois da documentação e preservada.

Essas verificações locais foram posteriormente complementadas pela execução manual
bem-sucedida do Experiment 01, registrada abaixo.

Para repetir apenas os testes locais de interpretação:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

## Experiment 01 — evidências e interpretação [VALIDADO]

A execução manual confirmou Peer em mychannel, delivery e rede mínima funcional.
`peer channel list` retornou `mychannel` com exit code 0. Os logs mostraram
`This peer will retrieve blocks from ordering service` e
`Pulling next blocks from ordering service`, com `channel=mychannel`,
`orderer-address=orderer0.example.com:7050` e `nextBlock=1`.

Chaincode selecionado: name `basic`, language `golang`, label `basic_1.0`,
fonte `Lab07/chaincodes/basic`. Package gerou `chaincode-packages/basic.tar.gz`
com exit code 0. Install retornou exit code 0 e `Installed remotely: response:<status:200 ...>`.
Queryinstalled retornou o registro:

```json
{
  "installed_chaincodes": [{
    "package_id": "basic_1.0:620167201f49423926debc1e286bebb823e0ae3bbe00bcd217d21fcfb8c976bf",
    "label": "basic_1.0"
  }]
}
```

O ID acima é evidência desta execução, não constante para execuções futuras.
Seleção, package, install, queryinstalled e identificação do ID estão validados.

Empacotar produz um arquivo local; instalar armazena/constrói o código no Peer;
aprovar registra a definição aceita pela organização no canal; commit da definição
no canal é uma operação posterior, necessária para disponibilizar o chaincode
para uso, junto aos demais requisitos aplicáveis. Instalação não equivale a aprovação
nem a commit. Ao fim do Experiment 01:

```text
basic
  package/install/queryinstalled  [VALIDADO]
  approveformyorg                 [NÃO REALIZADO]
  commit                         [NÃO REALIZADO]
  invoke/query                   [NÃO REALIZADO]
```

Containers/processos auxiliares podem ser usados no build Go. Um container de build
parado não significa falha nem que o chaincode já deveria estar executando. O critério
desta etapa é install com exit 0, pacote esperado em queryinstalled e ID identificado.

As fontes/ vendor de `chaincodes/` estão ignoradas pelo Git por decisão do projeto.
Um clone novo deve receber a cópia local separadamente; clean.sh não a remove.

## Experiment 02 — approveformyorg [VALIDADO]

O novo experimento é independente: prepara rede/canal e valida delivery; seleciona
chaincode, executa package/install/queryinstalled e identifica o ID retornado pela
consulta da própria sessão, exigindo correspondência de label e hash. Não executa
Experiment 01 como script/subprocesso e não reutiliza seu ID como constante.

`DEFINITION_DEFAULTS` centraliza canal mychannel, version 1.0 e sequence 1; o nome
vem da definição selecionada no catálogo. `approve_chaincode_for_org` recebe esses
valores e o ID real explicitamente, permitindo outros chaincodes.

```text
source -> package -> install -> queryinstalled -> Package ID -> approveformyorg
```

Aprovação difere da instalação: registra a definição para a organização dentro do
canal e exige comunicação com o Ordering Service. O helper usa o Admin MSP da Org1
já configurado e o hostname Fabric do Orderer resolvido pelo mapeamento existente.
A CA do Orderer é montada adicionalmente em leitura no Peer somente quando
`create_network(orderer_cli=True)` é solicitado. Não se modifica CA/certificado,
TLS, hosts ou configtx.yaml; Experiment 01 mantém sua configuração padrão.

Parâmetros: `--channelID` seleciona canal; `--name` identifica chaincode;
`--version` indica versão; `--sequence` identifica revisão da definição;
`--package-id` vincula o código instalado à aprovação da organização. `-o` usa
hostname e porta gRPC do Orderer, `--tls`/`--cafile` validam o servidor e
`--ordererTLSHostnameOverride` mantém sua identidade TLS. Admin/mTLS é usado no
join do Orderer, não como endpoint de aprovação.

O CLI aguarda evento da transação com `--waitForEvent` e timeout de 60 segundos.
Isso pertence ao próprio approveformyorg; não é commit da definição nem uma chamada
a checkcommitreadiness. O critério é exit code zero, com stdout/stderr preservados,
sem comparar uma frase específica. Falhas/timeout interrompem o fluxo, sem retry
automático da aprovação. Depois da resposta, mantém-se inspeção até ENTER.

Teste a partir de artefatos limpos, com experimentos anteriores encerrados e os
fontes locais do chaincode disponíveis:

```bash
cd Lab07
sudo bash clean.sh && sudo -E python3 experiment02_approve_chaincode.py --chaincode basic
```

Esperado: rede, Peer em mychannel, delivery, seleção, package, install,
queryinstalled, Package ID identificado e approveformyorg com [OK]. Se falhar,
envie exit code, stdout/stderr e logs do Peer/Orderer antes de encerrar.

A execução manual do Experiment 02 partiu de ambiente limpo. Rede mínima,
Peer em mychannel e delivery passaram. Package, install e queryinstalled foram
repetidos na mesma sessão e o Package ID foi descoberto dinamicamente.
A definição foi channel=mychannel, name=basic, version=1.0, sequence=1.
Approveformyorg retornou exit code 0 e `txid [...] committed with status (VALID)`.
O Peer registrou `Successfully endorsed chaincode approval` para essa definição
e o pacote instalado nesta execução. O Orderer criou e escreveu o bloco [1];
o Peer recebeu, validou e commitou esse bloco com uma transação.

**Conclusão:** Org1 aprovou a definição do chaincode basic para mychannel; a
transação correspondente foi ordenada, entregue e commitada como válida.
Isso confirma a aprovação da organização, não o commit da definição no canal.
O número do bloco é evidência desta execução, não critério fixo de sucesso.

Durante install, o ccaas_builder informou `chaincode type not supported: golang`,
seguido de instalação bem-sucedida pelo fluxo padrão e confirmação em queryinstalled.
Essa mensagem isolada não representou falha. O contexto gRPC cancelado posterior
também não invalida a transação já confirmada como VALID e o bloco commitado.


## Experiment 03 — checkcommitreadiness/commit/querycommitted [VALIDADO]

Sessão independente: reutiliza preparação de crypto/bloco, criação da rede,
joins, IPs/mapeamento, TLS e delivery. Repete package/install/queryinstalled e
approveformyorg usando helpers; não executa os scripts anteriores nem depende de
seus artefatos. O Package ID vem da consulta desta sessão, conferido por label/hash.

```text
source -> package -> install -> queryinstalled -> Package ID -> approveformyorg
       -> checkcommitreadiness -> commit -> querycommitted
```

Uma única definição (catálogo + DEFINITION_DEFAULTS) é passada às quatro operações.
Aprovação registra a escolha da organização; readiness consulta as aprovações;
commit registra a definição no canal; querycommitted confirma o estado final.

| Função nova | Evidência exigida |
|---|---|
| `check_commit_readiness` | JSON com aprovação boolean true do MSP configurado no Peer (Org1MSP); caso contrário interrompe antes do commit. Retorna aprovações e resultado CLI. |
| `commit_chaincode_definition` | Exit 0 com `--waitForEvent` e timeout 60s; status explícito diferente de VALID é rejeitado. Retorna resultado CLI completo. |
| `query_committed_chaincode` | JSON com exatamente um registro do nome esperado e version/sequence iguais à definição. Retorna registro e resultado CLI. |

Os streams stdout/stderr e exit code são preservados. JSON é lido somente de stdout.
O commit reutiliza endpoint/CA/TLS do Orderer da aprovação e o contexto Admin/MSP,
endereço dinâmico e CA TLS do Peer já usados pelo CLI. Não altera naming ou rede.
Nenhuma operação mutante é repetida automaticamente após falha/timeout.

Conforme a [CLI oficial Fabric 2.5](https://hyperledger-fabric.readthedocs.io/en/release-2.5/commands/peerlifecycle.html),
querycommitted sem nome permite consultar registros com name/version/sequence;
o exemplo JSON com nome omite name. Readiness aceita `approvals` e a grafia
`Approvals` do exemplo oficial, validando o mapa e o booleano relevante.
A espera pelo evento do CLI confirma a transação; logs de status VALID são
apresentados como evidência adicional, sem comparação do output inteiro.

Com experimentos anteriores encerrados e fontes locais disponíveis, na raiz:

```bash
cd Lab07
sudo bash clean.sh && sudo -E python3 experiment03_commit_chaincode.py
```

Esperado: rede/delivery, pacote/instalação/ID/aprovação [OK], readiness com Org1MSP
true, commit exit 0 e evento VALID, querycommitted com name basic, version 1.0 e
sequence 1. Só então `Definição do chaincode em mychannel [OK]`.
Não há dependência de número de bloco. Se falhar, observe a primeira etapa com
erro e preserve exit code/stdout/stderr e logs do Peer/Orderer antes de ENTER.
A rede fica disponível para inspeção e é encerrada pelo finally após ENTER.

Package/install/approve/commit e consulta final estão **[VALIDADO]** por execução manual. Invoke/query de negócio permanecem **[NÃO VALIDADO]**,
Experiment 04 **[BLOQUEADO — NÃO IMPLEMENTADO]**. Mesmo o sucesso do Experiment 03 não comprova execução
de lógica de negócio. O assistente não executou este experimento.


### Evidências manuais do Experiment 03 [VALIDADO]

Approveformyorg e commit retornaram exit 0 e transações `committed with status
(VALID)`. Checkcommitreadiness confirmou Org1MSP=true. Querycommitted confirmou
name=basic, version=1.0, sequence=1; o check final da definição em mychannel passou.
O Peer registrou `Successfully endorsed commit` para basic/mychannel, recebeu,
validou e commitou o bloco [2], e informou que o package ID da execução estava
available on channel mychannel para basic:1.0. A altura [2] é evidência, não regra.
O problema posterior de runtime não invalida o objetivo de lifecycle concluído.

## Descoberta após o Experiment 03: comunicação entre runtime do chaincode e Peer

```text
Lifecycle da definição ............. VALIDADO
Runtime do chaincode ............... PROBLEMA IDENTIFICADO
Chaincode → Peer :7052 .............. EM INVESTIGAÇÃO
Experiment 04 invoke/query ......... BLOQUEADO — NÃO IMPLEMENTADO
```

### OBSERVADO

O usuário reportou timeout TCP em `10.0.0.20:7052`, panic do asset-transfer-basic
e `chaincode registration failed: container exited with 2`. Peer → Orderer
permaneceu validado. A inspeção pontual, sem reiniciar containers, encontrou:

- Peer `mn.peer0`, ID `658d46ef7b25`, PID 102599, namespace `net:[4026533421]`,
  Docker NetworkMode=bridge. Interfaces: lo, eth0 e peer0-eth0. A tabela IPv4 local
  contém 127.0.0.1 e 172.17.0.4, sem 10.0.0.20. Docker informa eth0/bridge com
  172.17.0.4/16 e gateway 172.17.0.1; a interface Fogbed existe, mas não tem
  10.0.0.20 atribuído nesta observação. Rota default do Peer: eth0 via 172.17.0.1.
- `/proc/net/tcp6` contém `[::]:7052` (hex 1B8C), estado LISTEN (0A).
  O ambiente configura `CORE_PEER_CHAINCODELISTENADDRESS=0.0.0.0:7052`.
  O teste IPv4 bem-sucedido confirma atendimento também por IPv4.
- Runtime ID `091190acdd3e`, nome
  `dev-peer0.org1.example.com-basic_1.0-620167201f49423926debc1e286bebb823e0ae3bbe00bcd217d21fcfb8c976bf`,
  Exited(2), PID=0, NetworkMode=host. Config.Cmd é
  `["chaincode", "-peer.address=10.0.0.20:7052"]`.
  Não há PID/namespace vivo a inspecionar nem IP exclusivo do runtime.
  Pelo modo host configurado, sua rede de execução é a do host Docker, não a
  bridge como membro separado nem a interface Fogbed do Peer.
- Host observado: namespace `net:[4026531840]`, lo=127.0.0.1, docker0=172.17.0.1/16,
  wlp2s0=192.168.1.12/24; bridges adicionais 172.18.0.1/16 e 172.19.0.1/16.
  Default via 192.168.1.1/wlp2s0; rota 172.17.0.0/16 por docker0, nenhuma rota
  específica para 10.0.0.20. Interfaces de switches/veth também existem no host.
- Hosts do runtime parado: localhost e hostname da máquina, sem peer0 ou FQDN
  do Peer. Resolv.conf gerado pelo Docker usa 127.0.0.53, baseado no host.

Testes pontuais Python socket pelo host (rede correspondente a NetworkMode=host):

| Destino :7052 | Resultado |
|---|---|
| 10.0.0.20 | Timeout após 3 segundos |
| 172.17.0.4 | Conexão TCP aberta |
| peer0 | Falha de resolução |
| peer0.org1.example.com | Falha de resolução |

Os testes não foram executados dentro do processo encerrado. São comparação pelo
namespace host correspondente à configuração registrada. Testaram TCP apenas,
não handshake TLS, registro do shim ou execução de negócio. IPs/IDs/PIDs acima
são evidências efêmeras desta sessão, não configuração proposta.

### CONFIRMADO: origem e propagação

```text
Lab05/common.py:create_peer(ip="10.0.0.20", port=7051)
  -> clean_ip + port+1
  -> CORE_PEER_CHAINCODEADDRESS=10.0.0.20:7052
  -> Lab06/common.py:create_peer preserva ambiente, adapta volumes MSP/TLS
  -> Lab07/common.py:create_network chama o helper sem substituir ip/porta
  -> processo Peer lê a variável de ambiente
  -> launcher Docker do Fabric fornece -peer.address ao runtime
  -> chaincode tenta conectar em 10.0.0.20:7052
```

O core.yaml ativo é o da imagem Peer em `/etc/hyperledger/fabric/core.yaml`:
chaincodeAddress/listenAddress aparecem comentados e são definidos pelo ambiente;
`vm.docker.hostConfig.NetworkMode: host` está na linha 546 e não é sobrescrito
pelo Lab07. `Lab07/config/core.yaml` serve ao CLI do host, não ao processo Peer.
A distinção entre endpoint anunciado e listener é descrita no
[checklist oficial Fabric 2.5](https://hyperledger-fabric.readthedocs.io/en/release-2.5/deploypeer/peerchecklist.html).

Fogbed local.py:add_docker registra o Peer como Docker host da topologia e cria
seu link com o switch. Containernet (`/opt/fogbed/containernet/mininet/node.py`)
repassa network_mode para create_host_config; o default é None, e o resultado
observado no Docker é bridge. Já o runtime é criado pelo Fabric através do socket
Docker montado no Peer (`Lab07/common.py:create_network`), não por add_docker do
Fogbed. O [Docker controller Fabric 2.5.16](https://github.com/hyperledger/fabric/blob/v2.5.16/core/container/dockercontroller/dockercontroller.go)
gerencia esse container auxiliar. Portanto ele não recebe automaticamente os links,
endereços ou mapeamentos de nomes configurados para os nós Fogbed.

**Causa de conectividade comprovada:** o Peer anuncia ao runtime um IPv4 conceitual
que não está atribuído ao Peer observado e não é alcançável pela rede host do runtime.
O listener está ativo; o endereço efetivo bridge é alcançável por TCP. O erro
reportado ocorre antes do handshake TLS. Não é falha de commit da definição.

### HIPÓTESES / questões restantes

A razão específica pela qual peer0-eth0 ficou sem o IPv4 conceitual não foi isolada;
exige investigar a configuração/start do nó no Containernet, caso essa opção seja
escolhida. Não se conclui que toda topologia Fogbed é inacessível por definição.
Ainda falta validar TLS e registro do runtime após uma futura correção autorizada.
A inspeção via sudo/nsenter foi impedida por senha; /proc foi lido por Docker exec,
e arquivos do runtime parado por Docker cp para stdout, sem extração permanente.

### Relação com Lab06 e opções conceituais (não implementadas)

Lab06 precisou tornar a identidade do Orderer resolvível no namespace do Peer.
Aqui, o consumidor é o runtime e o endpoint anunciado do Peer precisa corresponder
a um destino alcançável em sua rede. A responsabilidade comum é conciliar identidade
estável, endereço efetivo e namespace consumidor; corrigir somente DNS não atribui
um IP ausente nem cria uma rota. O hosts do Peer não é o hosts do runtime.

Opções:

1. Preservar as redes atuais e anunciar um endpoint estável do Peer cuja resolução
   seja fornecida ao runtime e atualizada a partir da descoberta do IP efetivo.
   Precisa definir o momento dessa descoberta antes do lançamento do runtime e
   preservar a identidade TLS; alterar apenas CORE_PEER_ADDRESS do CLI não resolve.
2. Fornecer o endpoint descoberto dinamicamente ao launcher, preservando identidade
   TLS separadamente. Exige validar o suporte real do caminho de lançamento/TLS;
   não equivale a gravar 172.17.0.4 no código.
3. Integrar deliberadamente o runtime à rede/topologia do Peer, ou configurar
   corretamente IP/rotas Fogbed. É uma mudança maior, com implicações para os
   experimentos de rede, e deve ser investigada separadamente.

### DECISÃO EXPERIMENTAL - EXPERIMENT 03B (RUNTIME DO CHAINCODE)

O endereço planejado da topologia Fogbed (`10.0.0.20`) e o endpoint operacional utilizado pelo runtime são tratados separadamente nesta etapa.
O `CORE_PEER_CHAINCODEADDRESS` é resolvido dinamicamente durante a inicialização do container a partir da interface `eth0` (onde o Docker atribui o IP operacional), e não hardcoded.
Isso garante que o Peer anuncie ao runtime (NetworkMode=host) um endpoint TCP alcançável em `:7052`, permitindo a conexão e o registro do chaincode sem alterar os listeners nem atribuir IPs manualmente a `peer0-eth0`.
A limitação da interface `peer0-eth0` permanecer sem IPv4 continua documentada como uma restrição identificada da integração Fogbed/Containernet.
