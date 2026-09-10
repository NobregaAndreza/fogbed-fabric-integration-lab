#!/usr/bin/env python3

"""
experiment01_baseline.py (Lab06)

ETAPA 1 do Lab06:
- reproduzir a baseline funcional já validada no Lab05;
- manter apenas os diagnósticos essenciais do canal principal Pair -> Orderer;
- não criar canal ainda.

Objetivo:
- garantir que o Lab06 começa exatamente no mesmo estado funcional que o Lab05
  comprovou em TCP/TLS.
"""

import os
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

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

CONTAINERNET_PATH = "/opt/fogbed/containernet"
if os.path.exists(CONTAINERNET_PATH) and CONTAINERNET_PATH not in sys.path:
    sys.path.insert(0, CONTAINERNET_PATH)

from fogbed import FogbedExperiment

# Endereços declarados na topologia. O IP real do namespace pode diferir.
ORDERER_IP = "10.0.0.30"
ORDERER_GRPC_PORT = 7050
PEER_IP = "10.0.0.20"
PEER_GRPC_PORT = 7051

# Baseline mínima: 1 Orderer + 1 Peer + MSP + TLS.
exp = FogbedExperiment()
cloud = exp.add_virtual_instance("cloud")
fog = exp.add_virtual_instance("fog")

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
exp.add_link(cloud, fog)

prepare_environment()

try:
    exp.start()

    orderer_real_ip = get_container_real_ip(orderer0) or ORDERER_IP
    peer_real_ip = get_container_real_ip(peer0) or PEER_IP

    banner("LAB06 BASELINE PEER + ORDERER", width=60)

    section_header("PROCESS", width=60)
    ord_proc_ok, ord_proc_msg = check_container_process(orderer0, "orderer")
    peer_proc_ok, peer_proc_msg = check_container_process(peer0, "peer")
    ord_logs_ok, ord_logs_msg = check_container_logs(orderer0)
    peer_logs_ok, peer_logs_msg = check_container_logs(peer0)
    print(format_diagnostic_line("Orderer", ord_proc_ok and ord_logs_ok, ord_proc_msg if not ord_proc_ok else ord_logs_msg, width=60))
    print(format_diagnostic_line("Peer", peer_proc_ok and peer_logs_ok, peer_proc_msg if not peer_proc_ok else peer_logs_msg, width=60))

    section_header("NETWORK NAMESPACE / IPS", width=60)
    # Importante: o endereço declarado na topologia pode não existir no namespace real.
    # A validação funcional deve usar o IP efetivo do container (172.17.0.x) para
    # evitar falsos negativos. O valor configurado permanece registrado apenas como
    # referência da estrutura declarada do Fogbed.
    ord_ns_ok, ord_ns_msg = check_container_netns_info(orderer0, orderer_real_ip)
    peer_ns_ok, peer_ns_msg = check_container_netns_info(peer0, peer_real_ip)
    print(format_diagnostic_line(f"Orderer declared {ORDERER_IP} / actual {orderer_real_ip}", ord_ns_ok, ord_ns_msg, width=60))
    print(format_diagnostic_line(f"Peer declared {PEER_IP} / actual {peer_real_ip}", peer_ns_ok, peer_ns_msg, width=60))

    section_header("TCP LOCAL", width=60)
    ord_tcp_loc_ok, ord_tcp_loc_msg = check_tcp_port_in_netns(orderer0, "127.0.0.1", ORDERER_GRPC_PORT)
    peer_tcp_loc_ok, peer_tcp_loc_msg = check_tcp_port_in_netns(peer0, "127.0.0.1", PEER_GRPC_PORT)
    print(format_diagnostic_line(f"Orderer TCP local {ORDERER_GRPC_PORT}", ord_tcp_loc_ok, ord_tcp_loc_msg, width=60))
    print(format_diagnostic_line(f"Peer TCP local {PEER_GRPC_PORT}", peer_tcp_loc_ok, peer_tcp_loc_msg, width=60))

    section_header("TCP NETWORK", width=60)
    conn_tcp_ok, conn_tcp_msg = check_tcp_port_in_netns(peer0, orderer_real_ip, ORDERER_GRPC_PORT)
    print(format_diagnostic_line(f"Peer -> Orderer TCP ({orderer_real_ip}:{ORDERER_GRPC_PORT})", conn_tcp_ok, conn_tcp_msg, width=60))

    section_header("TLS LOCAL", width=60)
    ord_tls_ok, ord_tls_msg = check_grpc_tls_port_in_netns(orderer0, "127.0.0.1", ORDERER_GRPC_PORT, server_hostname="orderer0.example.com")
    peer_tls_ok, peer_tls_msg = check_grpc_tls_port_in_netns(peer0, "127.0.0.1", PEER_GRPC_PORT, server_hostname="peer0.org1.example.com")
    print(format_diagnostic_line("Orderer TLS local", ord_tls_ok, ord_tls_msg, width=60))
    print(format_diagnostic_line("Peer TLS local", peer_tls_ok, peer_tls_msg, width=60))

    section_header("TLS NETWORK", width=60)
    conn_tls_ok, conn_tls_msg = check_grpc_tls_port_in_netns(peer0, orderer_real_ip, ORDERER_GRPC_PORT, server_hostname="orderer0.example.com")
    print(format_diagnostic_line(f"Peer -> Orderer TLS ({orderer_real_ip}:{ORDERER_GRPC_PORT})", conn_tls_ok, conn_tls_msg, width=60))

    banner("BASELINE STATUS", width=60)
    baseline_ok = all([
        ord_proc_ok,
        peer_proc_ok,
        ord_logs_ok,
        peer_logs_ok,
        ord_ns_ok,
        peer_ns_ok,
        ord_tcp_loc_ok,
        peer_tcp_loc_ok,
        conn_tcp_ok,
        ord_tls_ok,
        peer_tls_ok,
        conn_tls_ok,
    ])
    print(format_diagnostic_line("Baseline Lab06", baseline_ok, width=60))

    if baseline_ok:
        print("\nStatus: baseline funcional Peer + Orderer validada no Lab06.\n")
    else:
        print("\nStatus: baseline não validada. Revisar a camada de rede/identidade antes de avançar.\n")

    banner("AMBIENTE EM EXECUÇÃO", width=60)
    wait_for_user()

except Exception as ex:
    banner("ERRO DURANTE A BASELINE DO LAB06", width=60)
    print(ex)

finally:
    try:
        exp.stop()
    except Exception:
        pass

    if ask_cleanup():
        print("\n[INFO] Executando script de limpeza do Lab06...")
        cleanup()
        print("[OK] Limpeza do Lab06 concluída.")
    else:
        print("\n[INFO] Limpeza ignorada. Artefatos permanecerão disponíveis.")
