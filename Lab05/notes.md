# Notas Técnicas e Conceituais - Lab05

## Contexto do TCC: Integração Incremental Peer + Fogbed

No Hyperledger Fabric 2.5, o nó Peer é responsável por:
- Manter o estado do ledger (World State e Blockchain log).
- Validar e simular transações enviadas por clientes (Endorsement).
- Aplicar políticas de validação de bloco (Block Validation) e comitar blocos recebidos do Orderer.

---

### Diagnósticos no Fogbed via Linux Network Namespace (`nsenter`)

As imagens oficiais do Hyperledger Fabric 2.5 (`hyperledger/fabric-peer:2.5` e `hyperledger/fabric-orderer:2.5`) são minimalistas e não possuem binários extras como `curl`, `wget`, `nc`, `ss`, `netstat`, `ping` ou `bash` com `/dev/tcp`.

1. **Por que testes do Host falhavam com Timeout?**
   - No Mininet/Fogbed, cada container reside em um Network Namespace isolado.
   - Sockets abertos pelo processo raiz do host para IPs como `10.0.0.20` ou `10.0.0.30` sofrem `TimeoutError` por ausência de rota no namespace global do host.
2. **Solução via `nsenter` com Diagnósticos Transparentes**:
   - Descobrimos o PID do container no host (`docker inspect -f '{{.State.Pid}}'`).
   - Executamos a checagem com `nsenter -t <pid> -n python3 -c "..."`.
   - O teste entra exatamente no namespace de rede do container e executa o código Python usando `socket`, `ssl` e `urllib.request`.
   - Quando um teste falha, a exceção técnica real (`ConnectionRefusedError`, `TimeoutError`, `certificate verify failed`, `HTTP 503`, etc.) é preservada e exibida na saída do terminal.

---

### Mitigação de Condição de Corrida (Race Condition) no Boot

Os processos `orderer` e `peer node start` aparecem na tabela de processos (`ps aux`) alguns instantes antes que a biblioteca Go do Fabric conclua a carga das chaves MSP/TLS e abra os sockets de escuta nas portas `7050` e `7051`.

- Implementamos **espera ativa (retries)** com contagem de tentativas (`check_grpc_tls_port_in_netns`).
- A função tenta estabelecer a conexão a cada 0.5s (até 10 tentativas).
- Assim que o serviço se torna disponível, a função retorna imediatamente indicando quantas tentativas foram necessárias.

---

### Operations Service & Health Checks (`/healthz`)

- **Peer**: `CORE_OPERATIONS_LISTENADDRESS=0.0.0.0:9443` (`CORE_OPERATIONS_TLS_ENABLED=false`)
- **Orderer**: `ORDERER_OPERATIONS_LISTENADDRESS=0.0.0.0:8443` (`ORDERER_OPERATIONS_TLS_ENABLED=false`)
- O Operations Service roda em portas dedicadas (`9443` e `8443`) totalmente separadas da comunicação gRPC Fabric (`7051` e `7050`).
- Diagnósticos de `/healthz` testam a saúde do serviço HTTP e são apresentados separadamente na validação final.

---

### Criptografia e Identidade (cryptogen & NodeOUs)

- **MSP (Membership Service Provider)**: Define quais identidades X.509 são válidas para atuar como membros, administradores ou peers de uma determinada organização.
- **NodeOUs (Organizational Units)**: Permite classificar o tipo de papel de um certificado digital (Peer, Admin, Client, Orderer) embutido no atributo OU da chave pública X.509.
- **TLS (Transport Layer Security)**: No Fabric 2.5, o TLS assegura confidencialidade e integridade no canal gRPC entre Peer <-> Orderer e Peer <-> Peer.

#TODO: ler tudo que tenho aqui no lab05 para ver o que posso simplificar/ melhorar.
TODO: verificar erro de handshake em ambos os nós.

---

## Registro de Investigação Incremental (Peer ↔ Orderer)

### ETAPA A — Processos
- **Objetivo**: Confirmar se os containers do `orderer0` e `peer0` estão em execução ativa (processos `orderer` e `peer`) e sem erros críticos nos logs.
- **Teste Realizado**: Execução manual de `sudo python3 experiment02_peer_orderer.py` com checagem de `ps aux` e varredura de palavras-chave de erro (`panic`, `FATAL`, `CRIT`) nos logs dos containers.
- **Resultado validado**:
  - Orderer process: `[OK]`
  - Peer process: `[OK]`
  - Orderer logs clean: `[OK]`
  - Peer logs clean: `[OK]`
- **Conclusão**: A etapa A foi validada com sucesso: ambos os containers estão ativos e os processos principais do Fabric iniciaram sem exceções fatais ou pânicos imediatos.
- **Eventual Problema Encontrado**: Nenhum na camada de processo.

### ETAPA B — Network Namespace / IPs
- **Objetivo**: Confirmar PID real, isolamento de namespace de rede e IPs atribuídos a `peer0` e `orderer0`.
- **Teste Realizado**: `check_container_netns_info` comparando o namespace do processo com o namespace do host e listando interfaces IPv4 via `nsenter -t <pid> -n ip -4 addr show`.
- **Resultado observado no teste manual**:
  - Orderer: PID `116275` | namespace isolado OK (`net:[4026533480]`) | `lo=127.0.0.1`, `eth0=172.17.0.3` | `STATUS:MISSING`
  - Peer: PID `116425` | namespace isolado OK (`net:[4026533600]`) | `lo=127.0.0.1`, `eth0=172.17.0.4` | `STATUS:MISSING`
- **Conclusão**:
  - ✅ Os containers têm namespaces de rede **isolados** do host.
  - ❌ Os IPs esperados `10.0.0.30` e `10.0.0.20` **não estão presentes** dentro do namespace do container.
  - ✅ Os IPs reais observados são `172.17.0.3` e `172.17.0.4`.
- **Causa Raiz**: o ambiente Fogbed/Containernet não disponibiliza a interface de rede esperada `10.0.0.x` no namespace do container; os nós estão recebendo apenas a interface Docker bridge padrão (`eth0` em `172.17.0.0/16`).
- **IPs Reais a usar nas próximas etapas**: orderer0 = `172.17.0.3` | peer0 = `172.17.0.4`
- **Status da etapa**: **não validada** para a topologia esperada `10.0.0.x`; o ponto confirmado é que o IP real do namespace é `172.17.0.3/172.17.0.4` e não o endereço teórico do Fogbed.

### ETAPA C — TCP Local
- **Objetivo**: Confirmar se os serviços gRPC estão aceitando conexões TCP nas suas portas locais (`127.0.0.1:7050` e `127.0.0.1:7051`).
- **Teste Realizado**: `check_tcp_port_in_netns` via `nsenter -t <pid> -n python3` tentando `socket.create_connection` em loopback.
- **Resultado**:
  - `Orderer 127.0.0.1:7050 = [OK]` — porta aberta na 1ª tentativa.
  - `Peer 127.0.0.1:7051 = [OK]` — porta aberta na 1ª tentativa.
  - `Orderer 10.0.0.30:7050 = [FAIL]` — esperado; IP não existe no namespace.
- **Conclusão**: Ambos os processos Fabric estão escutando ativamente em `0.0.0.0` nas suas respectivas portas gRPC. O stack gRPC/TLS está inicializado corretamente.
- **Eventual Problema Encontrado**: A validação via IP `10.0.0.x` falha por ausência do endereço na interface — não é problema do processo Fabric em si.

### ETAPA D — TCP Peer -> Orderer
- **Objetivo**: Confirmar se o `peer0` consegue abrir conexão TCP pura diretamente ao `orderer0` no namespace real do container, sem TLS e sem HTTP.
- **Teste Realizado**: `check_tcp_port_in_netns(peer0, orderer_real_ip, 7050)` com `orderer_real_ip = 172.17.0.3`, descoberto via `nsenter -t <pid> -n ip -4 addr show`.
- **Resultado validado**:
  - `peer0 -> 172.17.0.3:7050 = [OK]`
  - `Orderer 127.0.0.1:7050 = [OK]`
  - `Peer 127.0.0.1:7051 = [OK]`
- **Conclusão**: A comunicação TCP principal entre `peer0` e `orderer0` foi validada na rede real do namespace do container. O problema observado não é da aplicação Fabric, mas da incompatibilidade entre a topologia teórica `10.0.0.x` e o IP real do namespace (`172.17.0.3`).
- **Eventual Problema Encontrado**: `10.0.0.30` não existe no namespace; a rede real do laboratório não corresponde ao endereço da topologia declarada.
- **Status da etapa**: **validada** para o IP real do namespace e para a camada TCP pura.

### ETAPA E — TLS Local
- **Objetivo**: Validar o handshake TLS local em cada nó, sem depender da rede entre containers, para separar a identidade/certificado do problema de roteamento.
- **Teste Realizado**: `check_grpc_tls_port_in_netns` para `127.0.0.1:7050` e `127.0.0.1:7051` com `server_hostname` correto (`orderer0.example.com`, `peer0.org1.example.com`).
- **Resultado validado**:
  - `Orderer TLS localhost:7050 = [OK]`
  - `Peer TLS localhost:7051 = [OK]`
- **Conclusão**: A etapa E está validada. O TLS local funciona corretamente em ambos os serviços.
- **Eventual Problema Encontrado**: O erro de handshake observado nos logs do container aparece ao tentar a comunicação de rede e não na conexão local.

### ETAPA F — TLS Peer -> Orderer
- **Objetivo**: Validar o handshake TLS entre `peer0` e `orderer0` usando o IP real do namespace e o `server_hostname` correto do certificado do orderer.
- **Teste Realizado**: `check_grpc_tls_port_in_netns(peer0, orderer_real_ip, 7050, server_hostname="orderer0.example.com")` com `orderer_real_ip = 172.17.0.3`.
- **Resultado validado**:
  - `peer0 -> 172.17.0.3:7050 TLS = [OK]`
- **Conclusão**: A comunicação principal do Fabric foi validada em TCP e TLS, usando o IP real do namespace. O diagnóstico funcional principal está estável e os checks de `healthz` não são mais necessários para a investigação incremental.
- **Observação**: `Operations Service /healthz` continua sendo útil como diagnóstico auxiliar, mas não deve ser usado como gate da camada principal do Peer ↔ Orderer.

### Fluxo Essencial Final do Lab05
- Processo + logs
- Namespace + IP real
- TCP local
- TCP peer -> orderer
- TLS local
- TLS peer -> orderer
- Nenhum check de `healthz` na validação principal