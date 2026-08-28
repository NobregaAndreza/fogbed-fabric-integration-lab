#!/usr/bin/env python3

"""
experiment01_peer.py (Lab05)

Primeiro experimento do Lab05:
- Subir um único Peer (peer0) isolado na topologia Fogbed.
- Utilizar MSP e certificados TLS gerados pelo cryptogen.
- Inicializar o Peer através de `peer node start`.
- Validar diagnósticos via `nsenter` no Network Namespace do container: Processo, Local gRPC (7051 com TLS Handshake) e Operations Service (/healthz na 9443).
"""

import sys
import os

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
    banner,
    section_header,
    format_diagnostic_line,
    check_container_process,
    check_grpc_tls_port_in_netns,
    check_http_health_in_netns,
    wait_for_user,
    ask_cleanup
)

setLogLevel("info")

# 1. Preparação dos certificados criptográficos (MSP e TLS)
prepare_environment()

# 2. Configuração da topologia Fogbed
exp = FogbedExperiment()
fog = exp.add_virtual_instance("fog")

PEER_IP = "10.0.0.20"
PEER_GRPC_PORT = 7051
PEER_OPS_PORT = 9443

# 3. Criação parametrizada do Peer
peer0 = create_peer(
    name="peer0",
    ip=PEER_IP,
    org_domain="org1.example.com",
    msp_id="Org1MSP",
    port=PEER_GRPC_PORT,
    operations_port=PEER_OPS_PORT,
    tls_enabled=True
)

exp.add_docker(peer0, fog)

try:
    exp.start()

    banner("PEER DIAGNOSTICS", width=60)

    # 1. Processo ativo no container
    section_header("PROCESS", width=60)
    proc_ok, proc_err = check_container_process(peer0, "peer")
    print(format_diagnostic_line("Peer process", proc_ok, width=60))

    # 2. Serviços locais na porta gRPC (de dentro do Network Namespace do peer0)
    section_header("LOCAL SERVICES", width=60)
    grpc_ok, grpc_msg = check_grpc_tls_port_in_netns(peer0, "127.0.0.1", PEER_GRPC_PORT)
    print(format_diagnostic_line(f"Peer localhost:{PEER_GRPC_PORT}", grpc_ok, width=60))

    # 3. Operations Service / Health Check local
    section_header("OPERATIONS HEALTH - LOCAL", width=60)
    health_ok, health_msg = check_http_health_in_netns(peer0, "127.0.0.1", PEER_OPS_PORT, "/healthz")
    print(format_diagnostic_line(f"Peer localhost:{PEER_OPS_PORT}/healthz", health_ok, width=60))

    banner("EVIDÊNCIAS DE SUCESSO NOS LOGS", width=60)
    print("""
Para verificar os logs do Peer em outro terminal:
  docker logs peer0.fogbed   (ou podman logs peer0.fogbed)

Evidências esperadas nos logs:
  - "Starting peer:" e "Version: 2.5.x"
  - "Loaded MSP Org1MSP"
  - "TLS status: enabled"
  - "Starting Peer server" ou "Listening on 0.0.0.0:7051"
""")

    banner("AMBIENTE EM EXECUÇÃO", width=60)
    wait_for_user()

except Exception as ex:
    banner("ERRO DURANTE A EXECUÇÃO DO EXPERIMENTO 01", width=60)
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
        print("\n[INFO] Limpeza ignorada. Os artefatos permanecem em crypto-material/ e channel-artifacts/.")
