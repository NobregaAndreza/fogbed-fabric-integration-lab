# Lab06: application channel no Fabric 2.5 LTS

## Objetivo e status

Validar uma operação funcional do Fabric com OrdererOrg/orderer0 e Org1/peer0
participando de `mychannel`, evoluindo a infraestrutura do Lab05.

- [VALIDADO] Baseline Peer + Orderer, MSP, processos, namespaces, TCP local e
  Peer -> Orderer, handshake TLS local e Peer -> Orderer no Lab05 e, conforme
  confirmação manual informada pelo usuário, no início do Lab06.
- [VALIDADO] Geração manual do bloco inicial `channel-artifacts/mychannel.block`
  com o profile `FogbedApplicationChannel`. Logs confirmaram criação do application
  channel genesis block e escrita do arquivo, que será usado no ingresso futuro.
- [VALIDADO] Orderer sem system channel, Admin endpoint com mTLS e confirmação
  de ausência de canais antes do join.
- [VALIDADO] `osnadmin channel join` e consulta confirmando `active`/`consenter`.
- [VALIDADO] Peer ingressa em `mychannel`; `peer channel list` retorna `mychannel`.
- [PENDENTE] Comunicação contínua Peer → Ordering Service e resolução de
  `orderer0.example.com` dentro da topologia Fogbed.

A inicialização sem canais foi confirmada manualmente após a correção do check.
Os ingressos do Orderer e do Peer foram confirmados manualmente. A etapa completa
permanece pendente enquanto persistirem os warnings do blocksprovider.

## Evolução do modelo

Os experimentos iniciais usaram legitimamente o bootstrap por system channel
para investigar inicialização, MSP, TLS e Raft:

```text
system-channel -> genesis.block -> Orderer
```

O fluxo adotado para o novo objetivo é a Channel Participation API:

```text
configtx.yaml -> mychannel.block -> osnadmin channel join -> Orderer
                                 -> peer channel join   -> Peer -> mychannel
```

`mychannel.block` é o genesis do próprio application channel. O profile reúne
Orderer e Application, sem Consortiums. `configtxgen -outputCreateChannelTx` e
`peer channel create` pertencem ao fluxo baseado em system channel e não são a
base desta evolução. O profile `FogbedGenesis` permanece como padrão do gerador para reproduzir a
baseline. A opção `--application` seleciona explicitamente o novo artefato.

A baseline continua usando bootstrap `file`. O experimento 02 adapta o
container existente, apenas quando `channel_participation=True`, para
`General.BootstrapMethod=none`, `ChannelParticipation.Enabled=true` e um Admin
endpoint próprio com TLS, certificado/chave e autenticação de cliente obrigatória.
O Admin endpoint é distinto do gRPC e do Operations Service. A CA confiável e o
certificado/chave vêm do crypto do Lab06. Neste cenário mínimo, o teste usa
o par TLS do próprio Orderer também como cliente mTLS, confiado pela sua CA TLS.
Isso não representa uma identidade administrativa MSP separada.

Referências oficiais consultadas para Fabric 2.5:
[Channel Participation API](https://hyperledger-fabric.readthedocs.io/en/release-2.5/create_channel/create_channel_participation.html),
[configtx.yaml](https://github.com/hyperledger/fabric/blob/release-2.5/sampleconfig/configtx.yaml),
[orderer.yaml](https://github.com/hyperledger/fabric/blob/release-2.5/sampleconfig/orderer.yaml).

## Organização e reutilização

`common.py` concentra infraestrutura, configuração, caminhos e operações
reutilizáveis; o experimento concentra sequência e apresentação dos resultados.
O common do Lab06 carrega uma instância privada do common do Lab05, sem copiar
funções e sem modificar aquele arquivo. Os construtores importados ainda usam
os caminhos globais do Lab05; a geração local usa o diretório do Lab06. Essa
baseline mantém esses mounts. Somente no modo Participation os volumes MSP/TLS
são redirecionados ao crypto do Lab06 e o volume de genesis é removido. Assim
o novo Orderer usa as mesmas identidades incorporadas ao bloco validado.

Reutilização identificada:

- `create_peer` e `create_orderer`: containers, imagens 2.5, MSP, TLS e listeners.
- `get_container_real_ip`, `get_container_pid`, `run_in_container_netns` e checks
  de processos/logs, namespaces, TCP e TLS: infraestrutura de diagnóstico herdada.
- `prepare_environment`: mantém a baseline por padrão; com
  `application_channel=True`, chama o mesmo gerador de artefatos com
  `--application` e propaga falhas.
- `scripts/fabric-env.sh`: resolução dos binários e PATH, inclusive sob sudo;
  esta lógica já era shell, não uma função Python do common.
- `generate-genesis.sh`: reutiliza a resolução e a execução de configtxgen;
  sem argumentos mantém `FogbedGenesis`/`genesis.block`. A nova opção
  `--application` gera apenas `mychannel.block`, usando o crypto existente.
- `generate-artifacts.sh`, `generate-crypto.sh` e `cleanup`/`clean.sh`:
  permanecem sem alterações no fluxo da baseline.

O experimento 02 acrescenta somente a sequência de inicialização; o helper
`check_orderer_participation_api` concentra a consulta administrativa reutilizável. O novo profile reutiliza
Orderer, Channel, Org1 e capabilities por referências YAML, preservando o profile
legado. As policies de endorsement são configuração do canal, sem implantação de
chaincode. A identidade peer0 já está definida no crypto-config.

A execução validada da baseline continua sendo:

```bash
cd Lab06
sudo -E python3 experiment01_baseline.py
```

## Geração do bloco — validada manualmente

Na raiz do repositório, execute:

```bash
cd Lab06
sudo -E python3 -c "from common import prepare_environment; prepare_environment(application_channel=True)"
```

O teste deve gerar `channel-artifacts/mychannel.block` e terminar com `[OK]`
indicando esse caminho. Não inicia containers nem executa joins. Usa o material
MSP/TLS já existente em `Lab06/crypto-material`, sem sobrescrever `genesis.block`.
Se o diretório estiver ausente ou vazio, o gerador chama o `generate-crypto.sh`
existente, como na preparação da baseline. Material existente é preservado;
material parcial causa erro, sem remoção ou regeneração automática.

[VALIDADO] Após passar pelo fluxo de preparação existente, o teste manual
confirmou geração do crypto e de `mychannel.block`, com os logs
`Creating application channel genesis block` e `Writing genesis block`.

Para limpar os artefatos, com o experimento encerrado e dentro de `Lab06`:

```bash
sudo bash clean.sh
```

Esse comando remove `crypto-material` e `channel-artifacts`; não para containers.

## Orderer sem system channel [VALIDADO]

Com a baseline encerrada, execute na raiz do repositório:

```bash
cd Lab06
sudo -E python3 experiment02_orderer_channel_participation.py
```

O experimento reutiliza `prepare_environment(application_channel=True)`; isso
reescreve o bloco com o crypto existente, sem rotacionar identidades. Sobe somente
orderer0 e preserva gRPC 7050 e Operations 8443. Admin usa 9443 no namespace do
Orderer (separado do namespace do Peer da baseline).

Configurações específicas: bootstrap `none`, Participation habilitado, Admin
em `0.0.0.0:9443`, TLS e autenticação de cliente obrigatórios, CA TLS existente.
O teste descobre o IP real e consulta `GET /participation/v1/channels` via mTLS,
validando CA e hostname do servidor. Espera HTTP 200 com `systemChannel: null`
e `channels: null` ou `channels: []`, além dos checks de processo, TCP e TLS principal.
Os dois campos são obrigatórios; um system channel ou application channels
inesperados continuam causando falha. Não faz POST
nem executa comandos de join. Sem canais, não se espera eleição Raft; a configuração
etcdraft permanece no bloco para a etapa posterior.

Ao pressionar ENTER, o experimento para e mantém os artefatos. Não execute a
baseline simultaneamente: ambos os experimentos usam o nome orderer0.
Se falhar, envie toda a saída e os logs do Orderer antes de encerrar o experimento.
[VALIDADO EXPERIMENTALMENTE] No Fabric 2.5.16 utilizado no Lab06, antes de
qualquer channel join, a consulta à Channel Participation API retornou:

```json
{"systemChannel":null,"channels":null}
```

O resultado manual foi obtido com Orderer ativo, serviço principal TCP/TLS
funcional, Admin endpoint ativo, comunicação administrativa via mTLS e HTTP 200,
sem system channel e sem application channels associados ao Orderer. O `[FAIL]`
foi produzido pelo check local, que aceitava somente `channels: []`.

A documentação oficial do Fabric 2.5, na referência de Channel Participation API
citada acima, exemplifica `osnadmin channel list` pelo Admin endpoint com mTLS,
HTTP 200, `systemChannel: null` e uma lista em `channels` quando existem
application channels. O caso de zero application channels não aparece
explicitamente no exemplo oficial consultado. Portanto, `channels: null` nesse
estado é uma observação experimental do Fabric 2.5.16 deste projeto, não uma
representação especificada por aquele exemplo da documentação.

[VALIDADO] A nova execução manual confirmou todos os checks: namespace, TCP/TLS
principal, TCP Admin, Admin mTLS/ausência de canais, processo e logs, culminando
em `Inicialização sem canais [OK]`. A resposta anterior ao join foi
`{"systemChannel":null,"channels":null}`.

## Ingresso do Orderer [VALIDADO]

```bash
cd Lab06
sudo -E python3 experiment03_orderer_join_channel.py
```

Encerre o experimento anterior antes de executar: ambos usam orderer0. O experimento
03 exige o bloco `channel-artifacts/mychannel.block` existente e não regenera
bloco ou crypto. Sobe somente o Orderer com a configuração validada, confirma
estado vazio, executa `osnadmin channel join` uma vez e consulta novamente a API.
A operação deve retornar `Status: 201`, `name: mychannel`, `consensusRelation:
consenter`, `status: active` e `height: 1`. Os valores reais são exibidos e
verificados. A consulta posterior exige ausência de system channel e exatamente
`mychannel` na lista; processo e logs também são verificados após o join.

O helper reutiliza `fabric-env.sh` para resolver os binários. O certificado
existente tem SAN DNS do Orderer, não o IP real: o comando usa esse hostname com
um mapeamento para o IP descoberto. Um mount namespace privado (`unshare`) permite
montar um arquivo hosts temporário apenas para o comando, mantendo o `/etc/hosts`
do host intacto. `nsenter` reutiliza a descoberta de PID existente para acessar a
rede do Orderer. Certificados, chave e CA são os mesmos usados no teste mTLS.
Não são instaladas ferramentas nas imagens. `mount` e `unshare` são usados no host.

A baseline e o experimento 02 permanecem intactos. ENTER encerra o experimento e
preserva artefatos. Em falha, envie a saída real do osnadmin e os logs do Orderer
antes de encerrar. O join não é repetido automaticamente. A remoção do container
não promete persistência do ledger; esta etapa observa o ingresso na execução atual.

Referência: [CLI osnadmin do Fabric 2.5](https://github.com/hyperledger/fabric/blob/release-2.5/cmd/osnadmin/main.go).
O CLI pode terminar com exit code zero mesmo para erro HTTP; o helper verifica
explicitamente o status retornado e o JSON, sem considerar somente o exit code.

[VALIDADO] O teste manual retornou `Status: 201`, `name: mychannel`,
`consensusRelation: consenter`, `status: active` e `height: 1`. A consulta
administrativa posterior retornou `systemChannel: null` e `mychannel` na lista.
O processo Orderer permaneceu ativo e nenhum panic/fatal foi identificado nos logs.

## Ingresso do Peer [VALIDADO]; comunicação contínua [PENDENTE]

```bash
cd Lab06
sudo -E python3 experiment04_peer_join_channel.py
```

Encerre os experimentos anteriores antes de iniciar. A topologia reutiliza cloud,
fog e um link, com Orderer0 e Peer0. O bloco já existente é obrigatório; não há
regeneração. O Orderer ingressa pelo helper validado. Somente após confirmação do
canal, processos, logs e disponibilidade TCP/TLS do Peer, executam-se os comandos
`peer channel join -b <bloco montado>` e `peer channel list` no próprio container.

A opção `application_channel=True` de `create_peer` reutiliza o construtor herdado,
redireciona MSP/TLS para o Lab06 e monta o MSP de Admin da organização e o bloco
como somente leitura. O MSP do processo Peer permanece o do nó; somente os
comandos CLI recebem o MSP administrativo. MSP ID, CA TLS e hostname são derivados
da configuração existente. O CLI usa o IP descoberto e o hostname TLS do Peer.
O binário `peer` e o core.yaml são os da própria imagem, sem instalação adicional.

O helper de CLI captura explicitamente o exit code por um marcador ao final da
saída de `container.cmd`; texto de log contendo OK não define sucesso. Para list,
exige o cabeçalho da lista e uma linha exatamente igual a `mychannel`.
As evidências esperadas são join com exit code zero, canal listado, ambos os
processos ativos e logs sem panic/fatal após a operação. O ambiente fica ativo até
ENTER; os artefatos são preservados. A baseline e experimentos 02/03 não mudam.

O ingresso com bloco local demonstra associação ao canal; não comprova entrega
contínua de blocos ou execução de transações. A resolução dos endpoints anunciados
pelo Orderer para tráfego posterior permanece uma consideração arquitetural.

Referência: [peer channel no Fabric 2.5](https://hyperledger-fabric.readthedocs.io/en/release-2.5/commands/peerchannel.html).

[PENDENTE] Resolver o nome do Ordering Service no ambiente do Peer e confirmar
comunicação contínua antes de definir outra operação Fabric. Nenhum chaincode ou
invoke/query foi implementado.

### Investigação de resolução de nome — sem solução aplicada

[VALIDADO] O teste manual retornou `Successfully submitted proposal to join channel`
com `__LAB06_PEER_EXIT__=0`; `peer channel list` retornou `mychannel` e exit code zero.
O Orderer permaneceu saudável, com eleição de líder Raft para o canal.

[PENDENTE] Após o join, o blocksprovider tenta acessar
`orderer0.example.com:7050` e recebe `lookup orderer0.example.com on
192.168.1.1:53: no such host`. A falha ocorre na resolução, antes da conexão TCP
ou handshake TLS. O join com bloco local não depende de obter blocos do Orderer.
O check atual de logs busca panic/FATAL/CRIT e não detecta esse WARN como falha;
portanto seus resultados não comprovam comunicação contínua.

Origem: `Orderer.Addresses` em configtx.yaml, herdado pelo profile
`FogbedApplicationChannel` via `OrdererDefaults`. O configtxgen grava esse endereço
em `/Channel/OrdererAddresses`. `EtcdRaft.Consenters.Host/Port` também contém o
mesmo nome/porta, mas descreve o consenter Raft. Não há `OrdererEndpoints` por
organização neste YAML. Editar o YAML posteriormente não atualiza o bloco existente.
Referência: [encoder Fabric 2.5](https://github.com/hyperledger/fabric/blob/release-2.5/internal/configtxgen/encoder/encoder.go).

Os construtores herdados usam nomes orderer0/peer0, IPs declarados 10.0.0.30/20 e
listeners 0.0.0.0. O Containernet instalado define hostname igual ao nome curto e
não recebe configuração DNS ou aliases Fabric dos experimentos. Criar links entre
as instâncias não registra nomes em DNS. O IP efetivo é descoberto por nsenter;
essa descoberta não configura resolução nem reescreve os endpoints do canal.

Os checks TCP/TLS abrem sockets pelo IP real. O helper TLS herdado envia o hostname
como SNI, quando fornecido, mas desativa a validação de CA/nome. A consulta Admin
valida CA/nome, conectando explicitamente por IP. O join via osnadmin tem um arquivo
hosts temporário em mount namespace privado, válido apenas para aquele comando.
O processo Peer não recebe esse arquivo. Compartilhar um network namespace não
compartilha automaticamente arquivos hosts de outro mount namespace.

Opções em análise, nenhuma aplicada:

- Mapeamento hosts administrado pelo experimento no ambiente do Peer, preenchido
  com o IP descoberto e atualizado a cada recriação. Menor intervenção para o Lab06;
  deve existir no contexto real do processo Peer, antes do join.
- DNS interno da topologia, com registros derivados dos nós e seus endereços
  efetivos. Mais infraestrutura, mas adequado a múltiplos nós/hosts no futuro.
- Rede Docker definida pelo usuário com alias DNS completo do Orderer. Docker
  oferece resolução por nome/alias nessa rede, mas sua integração precisa preservar
  os caminhos e condições de rede emulados pelo Fogbed, evitando um caminho paralelo
  que contorne os links do experimento.

Referência: [redes bridge Docker](https://docs.docker.com/engine/network/drivers/bridge/).
A bridge padrão não fornece a mesma descoberta automática por nomes de uma rede
criada pelo usuário. Apenas definir hostname não publica um registro DNS.

Recomendação ainda não implementada: começar pelo mapeamento dinâmico e restrito
aos containers do experimento. Para a futura abstração, tratar resolução de nomes
como responsabilidade da topologia, separando identidade Fabric estável de endereço
de execução. DNS pode substituir o mecanismo inicial sem mudar nomes, certificados
ou configuração do canal. A escolha do IP deve respeitar a interface/rota pretendida;
o helper atual escolhe o primeiro IPv4 não-loopback, não certifica o caminho emulado.


## Endereçamento e futuro plugin

A descoberta dinâmica do IP real continua necessária: não assumir os endereços
10.0.0.x declarados nem fixar endereços da bridge Docker. Os hostnames Fabric do
bloco devem ser resolvidos para os IPs efetivos nos namespaces ao implementar o
runtime, preservando a validação de nome dos certificados.

O helper TLS herdado usa `CERT_NONE` e desativa `check_hostname`: a baseline
comprova handshake, não verificação de CA/nome ou mTLS administrativo. O executor
`run_in_container_netns` atual é voltado a snippets Python e procura `OK` na saída;
a futura execução de CLI precisará preservar exit code e resposta Fabric, sem
reinterpretar essa heurística como prova de participação no canal.

Essas observações orientam uma futura abstração de nós, organizações, artefatos,
configuração de canais e participação de Orderers/Peers. Nenhum plugin, SDK,
aplicação cliente ou framework é implementado neste laboratório.
