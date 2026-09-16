#!/usr/bin/env python3
"""Experiment 03b: Validação da conexão e registro do runtime do chaincode no Peer.

Este experimento é intermediário (NÃO é o Experiment 04). Ele estende o Experiment 03
garantindo que o endpoint CORE_PEER_CHAINCODEADDRESS seja resolvido dinamicamente para
o IP operacional do Peer na interface eth0, permitindo que o container de runtime do chaincode
(executado em NetworkMode=host) conecte e registre-se no Peer com sucesso.
"""
import sys
import time
from common import (
    CHAINCODES, PACKAGE_DIR, infra, select_chaincode, fabric_environment,
    check_prerequisites, create_network, validate_network, package_chaincode,
    install_chaincode, query_installed_chaincodes, identify_installed_package,
    DEFINITION_DEFAULTS, approve_chaincode_for_org, check_commit_readiness,
    commit_chaincode_definition, query_committed_chaincode, show_command,
    check_chaincode_endpoint_reachability, validate_chaincode_runtime_registration,
    require_check
)


def main():
    infra.banner("LAB07 - EXPERIMENT 03B: RUNTIME DO CHAINCODE -> PEER")

    exp = None
    success = False
    try:
        # Seleção/pré-requisitos locais
        chaincode = select_chaincode("basic")
        env = fabric_environment()
        check_prerequisites(env, chaincode)

        print("\n[FASE 1] Inicialização da Topologia e Validação de Rede")
        exp, orderer, peer = create_network(orderer_cli=True)
        exp.start()

        peer_ip = validate_network(orderer, peer)
        infra.section_header("Validação do Endpoint de Chaincode (:7052)")
        require_check(
            "Alcançabilidade Runtime -> Peer :7052",
            check_chaincode_endpoint_reachability(peer, port=7052)
        )

        print("\n[FASE 2] Empacotamento e Instalação do Chaincode basic")
        package = package_chaincode(chaincode, PACKAGE_DIR, env)
        show_command("Chaincode package", package["result"])

        install_res = install_chaincode(peer, peer_ip, package)
        show_command("Chaincode install", install_res)

        installed, query_inst_res = query_installed_chaincodes(peer, peer_ip)
        show_command("queryinstalled", query_inst_res)

        package_id = identify_installed_package(package, installed)
        print(infra.format_diagnostic_line("Package ID identificado", True))
        print(f"  {package_id}")

        print("\n[FASE 3] Aprovação e Commit da Definição")
        definition = {**DEFINITION_DEFAULTS, "name": chaincode["name"]}

        approve_res = approve_chaincode_for_org(peer, peer_ip, orderer, definition, package_id)
        show_command("approveformyorg", approve_res)

        approvals, readiness_res = check_commit_readiness(peer, peer_ip, definition)
        show_command("checkcommitreadiness", readiness_res)

        commit_res = commit_chaincode_definition(peer, peer_ip, orderer, definition)
        show_command("commit", commit_res)

        committed, query_comm_res = query_committed_chaincode(peer, peer_ip, definition)
        show_command("querycommitted", query_comm_res)
        print(f"  committed: {committed}")

        print("\n[FASE 4] Validação do Runtime e Registro do Chaincode")
        require_check(
            "Registro do Runtime no Peer",
            validate_chaincode_runtime_registration(peer, chaincode_name=chaincode["name"])
        )

        infra.banner("EXPERIMENT 03B CONCLUÍDO COM SUCESSO")
        print("\n[OK] Runtime do chaincode conectado e registrado no Peer dinamicamente.\n")
        success = True

    except Exception as error:
        print(infra.format_diagnostic_line("Experimento 03b / runtime do chaincode", False))
        print(f"  {error}")

    finally:
        if exp is not None:
            try:
                infra.wait_for_user()
            finally:
                print("[INFO] Encerrando a topologia Fogbed...")
                exp.stop()
                if infra.ask_cleanup():
                    infra.cleanup()

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
