# Lab07 — lifecycle inicial de chaincodes

## Objetivo e estado

**Experiment 01 — package/install/queryinstalled [EM VALIDAÇÃO]**

Reconstruir a rede mínima validada no Lab06 e comprovar que um chaincode local pode
ser empacotado, instalado no Peer e identificado em `queryinstalled`. O teste manual
deste Lab ainda não foi executado/confirmado pelo usuário. Não há aprovação,
commit de definição ou operação de negócio.

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
  experiment01_package_install.py      # orquestração da sessão
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
| `peer_lifecycle` | Executa somente install/queryinstalled via Docker exec sem TTY, no contexto Admin/MSP/TLS do Peer. |
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

- Experiment 01 — package/install/queryinstalled **[EM VALIDAÇÃO]**.
- Experiment 02 — approveformyorg **[PRÓXIMO]**.
- Experiment 03 — checkcommitreadiness/commit **[FUTURO]**.
- Experiment 04 — invoke/query **[FUTURO]**.

Não há funções implementadas para essas etapas futuras, Fabric CA, novos nós ou
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

Essas verificações não validam instalação nem rede do Lab07. Aguardam-se os
resultados manuais completos do Experiment 01.

Para repetir apenas os testes locais de interpretação:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```
