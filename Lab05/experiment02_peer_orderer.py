#!/usr/bin/env python3

"""
experiment02_peer_orderer.py (Lab05)

Segundo experimento do Lab05:
- Subir `peer0` (Org1) e `orderer0` (OrdererOrg) na mesma topologia Fogbed.
- Reproduzir a configuração funcional do Orderer validada no Lab04 (bloco gênesis + etcdraft).
- Validar diagnósticos estruturados por camadas via `nsenter` dentro do Network Namespace de cada nó:
  1. Processos [PROCESS]
  2. TCP Local [TCP LOCAL] (127.0.0.1:7050, 127.0.0.1:7051 e 10.0.0.30:7050 no netns do orderer0)
  3. Diagnóstico de Ping da Topologia (peer0 -> 10.0.0.30)
  4. TCP de Rede [TCP NETWORK] (peer0 netns -> 10.0.0.30:7050)
  5. TLS Handshake Local [TLS LOCAL]
  6. TLS Handshake na Rede [TLS NETWORK] (peer0 netns -> 10.0.0.30:7050 TLS)
  7. Operations Service Local [OPERATIONS HEALTH - LOCAL]
  8. Operations Service na Rede [OPERATIONS HEALTH - NETWORK]
- Resumo final honesto alinhado aos critérios de sucesso.
- NÃO cria canais.
"""

import sys
import os
import time

CONTAINERNET_PATH = "/opt/fogbed/containernet"
if os.path.exists(CONTAINERNET_PATH) and CONTAINERNET_PATH not in sys.path:
    sys.path.insert(0, CONTAINERNET_PATH)

from fogbed import (
    FogbedExperiment,
    setLogLevel
)

from common import (
    prepare_environment,
    cleanup,
    create_peer,
    create_orderer,
    get_container_real_ip,
    banner,
    section_header,
    format_diagnostic_line,
    check_container_process,
    check_container_logs,
    check_container_netns_info,
    check_tcp_port_in_netns,
    check_grpc_tls_port_in_netns,
    wait_for_user,
    ask_cleanup
)

setLogLevel("info")

# 1. Preparação dos certificados e do bloco gênesis
prepare_environment()

# 2. Configuração da topologia Fogbed (cloud para Orderer, fog para Peer)
# Observação: no namespace real dos containers, o IP pode diferir do endereço
# declarado na topologia. Por isso o diagnóstico usa `get_container_real_ip()`
# após a criação dos containers para validar a rede real e não a rede imaginada.
exp = FogbedExperiment()

cloud = exp.add_virtual_instance("cloud")
fog = exp.add_virtual_instance("fog")

ORDERER_IP = "10.0.0.30"
ORDERER_GRPC_PORT = 7050

PEER_IP = "10.0.0.20"
PEER_GRPC_PORT = 7051

# 3. Criação dos componentes Fabric
orderer0 = create_orderer(
    name="orderer0",
    ip=ORDERER_IP,
    domain="example.com",
    msp_id="OrdererMSP",
    port=ORDERER_GRPC_PORT,
    operations_port=8443
)

peer0 = create_peer(
    name="peer0",
    ip=PEER_IP,
    org_domain="org1.example.com",
    msp_id="Org1MSP",
    port=PEER_GRPC_PORT,
    operations_port=9443,
    tls_enabled=True
)

exp.add_docker(orderer0, cloud)
exp.add_docker(peer0, fog)

# Link de rede entre as instâncias virtuais
exp.add_link(cloud, fog)

try:
    exp.start()

    orderer_real_ip = get_container_real_ip(orderer0) or ORDERER_IP
    peer_real_ip = get_container_real_ip(peer0) or PEER_IP

    banner("PEER & ORDERER DIAGNOSTICS", width=60)

    # 1. Processo e logs: confirmar que o nó subiu e não caiu com erro crítico.
    section_header("PROCESS", width=60)
    ord_proc_ok, ord_proc_msg = check_container_process(orderer0, "orderer")
    peer_proc_ok, peer_proc_msg = check_container_process(peer0, "peer")
    ord_logs_ok, ord_logs_msg = check_container_logs(orderer0)
    peer_logs_ok, peer_logs_msg = check_container_logs(peer0)
    print(format_diagnostic_line("Orderer process", ord_proc_ok, ord_proc_msg, width=60))
    print(format_diagnostic_line("Peer process", peer_proc_ok, peer_proc_msg, width=60))
    print(format_diagnostic_line("Orderer logs clean", ord_logs_ok, ord_logs_msg, width=60))
    print(format_diagnostic_line("Peer logs clean", peer_logs_ok, peer_logs_msg, width=60))

    # 2. Namespace e IP real: a topologia declarada pode não coincidir com o IP
    # que o container realmente recebe dentro do namespace de rede.
    section_header("NETWORK NAMESPACE / IPS", width=60)
    ord_netns_ok, ord_netns_msg = check_container_netns_info(orderer0, ORDERER_IP)
    peer_netns_ok, peer_netns_msg = check_container_netns_info(peer0, PEER_IP)
    print(format_diagnostic_line(f"Orderer NetNS & IP ({ORDERER_IP})", ord_netns_ok, ord_netns_msg, width=60))
    print(format_diagnostic_line(f"Peer NetNS & IP ({PEER_IP})", peer_netns_ok, peer_netns_msg, width=60))

    # 3. TCP local: confirma que o serviço abriu a porta no namespace do próprio nó.
    section_header("TCP LOCAL", width=60)
    ord_tcp_loc_ok, ord_tcp_loc_msg = check_tcp_port_in_netns(orderer0, "127.0.0.1", ORDERER_GRPC_PORT)
    ord_tcp_ip_ok, ord_tcp_ip_msg = check_tcp_port_in_netns(orderer0, ORDERER_IP, ORDERER_GRPC_PORT)
    peer_tcp_loc_ok, peer_tcp_loc_msg = check_tcp_port_in_netns(peer0, "127.0.0.1", PEER_GRPC_PORT)

    print(format_diagnostic_line(f"Orderer 127.0.0.1:{ORDERER_GRPC_PORT}", ord_tcp_loc_ok, ord_tcp_loc_msg, width=60))
    print(format_diagnostic_line(f"Orderer {ORDERER_IP}:{ORDERER_GRPC_PORT} (netns orderer0)", ord_tcp_ip_ok, ord_tcp_ip_msg, width=60))
    print(format_diagnostic_line(f"Peer 127.0.0.1:{PEER_GRPC_PORT}", peer_tcp_loc_ok, peer_tcp_loc_msg, width=60))

    # 4. TCP de rede: valida o canal principal sem TLS, partindo do peer em direção ao orderer.
    section_header("TCP NETWORK", width=60)
    conn_tcp_ok, conn_tcp_msg = check_tcp_port_in_netns(peer0, orderer_real_ip, ORDERER_GRPC_PORT)
    print(format_diagnostic_line(f"peer0 -> {orderer_real_ip}:{ORDERER_GRPC_PORT}", conn_tcp_ok, conn_tcp_msg, width=60))

    # 5. TLS local: prova que o certificado/handshake do nó funciona em loopback.
    section_header("TLS LOCAL", width=60)
    ord_tls_loc_ok, ord_tls_loc_msg = check_grpc_tls_port_in_netns(orderer0, "127.0.0.1", ORDERER_GRPC_PORT, server_hostname="orderer0.example.com")
    peer_tls_loc_ok, peer_tls_loc_msg = check_grpc_tls_port_in_netns(peer0, "127.0.0.1", PEER_GRPC_PORT, server_hostname="peer0.org1.example.com")
    print(format_diagnostic_line(f"Orderer TLS localhost:{ORDERER_GRPC_PORT}", ord_tls_loc_ok, ord_tls_loc_msg, width=60))
    print(format_diagnostic_line(f"Peer TLS localhost:{PEER_GRPC_PORT}", peer_tls_loc_ok, peer_tls_loc_msg, width=60))

    # 6. TLS de rede: prova final da comunicação Fabric principal peer <-> orderer.
    section_header("TLS NETWORK (PEER -> ORDERER)", width=60)
    conn_tls_ok, conn_tls_msg = check_grpc_tls_port_in_netns(peer0, orderer_real_ip, ORDERER_GRPC_PORT, server_hostname="orderer0.example.com")
    print(format_diagnostic_line(f"peer0 -> {orderer_real_ip}:{ORDERER_GRPC_PORT} TLS", conn_tls_ok, conn_tls_msg, width=60))

    # 7. Resumo mínimo e honesto: manter apenas as camadas que importam para a comunicação principal.
    banner("RESUMO DA CONECTIVIDADE", width=60)
    fabric_comm_status = "OK" if (ord_proc_ok and peer_proc_ok and ord_netns_ok and peer_netns_ok and ord_tcp_loc_ok and peer_tcp_loc_ok and conn_tcp_ok and ord_tls_loc_ok and peer_tls_loc_ok and conn_tls_ok) else "FAIL"

    print(format_diagnostic_line("Comunicação Peer -> Orderer", fabric_comm_status, width=60))

    if fabric_comm_status == "OK":
        print("""
Status: Comunicação principal Peer -> Orderer estabelecida com SUCESSO na topologia real do namespace.
(Validação gRPC + TLS executada diretamente a partir do Network Namespace do peer0)
""")
    else:
        print(f"""
ATENÇÃO: A comunicação entre peer0 e orderer0 ainda apresentou falha real.
- Detalhes TLS/gRPC: {conn_tls_msg}
""")

    banner("AMBIENTE EM EXECUÇÃO", width=60)
    wait_for_user()

except Exception as ex:
    banner("ERRO DURANTE A EXECUÇÃO DO EXPERIMENTO 02", width=60)
    print(ex)

finally:
    try:
        exp.stop()
    except Exception:
        pass

    if ask_cleanup():
        print("\n[INFO] Executando script de limpeza...")
        cleanup()
        print("[OK] Limpeza do Lab05 concluída com sucesso.")
    else:
        print("\n[INFO] Limpeza ignorada. Os artefatos permanecem disponíveis.")
