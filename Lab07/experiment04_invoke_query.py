#!/usr/bin/env python3
"""Experiment 04: Primeira execução de transações de negócio (invoke e query) no ledger.

Este experimento testa a primeira execução funcional de um chaincode no ambiente
Hyperledger Fabric + Fogbed. Ele prepara a topologia e lifecycle validados e executa:
1. peer chaincode invoke (CreateAsset) enviando a proposta de transação ao Orderer;
2. Validação da criação do bloco no Orderer e commit no ledger do Peer;
3. peer chaincode query (ReadAsset) consultando e validando semanticamente o estado.
"""
import json
import sys
import time
from common import (
    CHAINCODES, PACKAGE_DIR, infra, select_chaincode, fabric_environment,
    check_prerequisites, create_network, validate_network, package_chaincode,
    install_chaincode, query_installed_chaincodes, identify_installed_package,
    DEFINITION_DEFAULTS, approve_chaincode_for_org, check_commit_readiness,
    commit_chaincode_definition, query_committed_chaincode, show_command,
    check_chaincode_endpoint_reachability, validate_chaincode_runtime_registration,
    invoke_chaincode, query_chaincode, check_orderer_block_created,
    check_peer_block_committed, require_check
)

# Dados determinísticos do cenário do teste (definidos na camada do experimento)
TEST_ASSET = {
    "id": "asset100",
    "color": "blue",
    "size": "5",
    "owner": "Andreza",
    "appraised_value": "300"
}


def main():
    infra.banner("LAB07 - EXPERIMENT 04: INVOKE E QUERY DE NEGÓCIO")

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

        print("\n[FASE 5] Transação de Negócio (Invoke CreateAsset)")
        infra.section_header("Execução do Invoke")
        invoke_args = [
            TEST_ASSET["id"],
            TEST_ASSET["color"],
            TEST_ASSET["size"],
            TEST_ASSET["owner"],
            TEST_ASSET["appraised_value"]
        ]
        invoke_res = invoke_chaincode(
            peer, peer_ip, orderer,
            definition["channel"], chaincode["name"],
            "CreateAsset", invoke_args
        )
        show_command("Chaincode invoke (CreateAsset)", invoke_res)

        # Evidência de criação e commit de novo bloco
        orderer_ok, block_num, orderer_msg = check_orderer_block_created(orderer)
        require_check("Bloco gerado no Orderer", (orderer_ok, orderer_msg))

        peer_ok, peer_msg = check_peer_block_committed(
            peer, channel_name=definition["channel"], expected_block=block_num
        )
        require_check("Bloco committed no Peer", (peer_ok, peer_msg))

        print("\n[FASE 6] Consulta do Estado do Ledger (Query ReadAsset)")
        infra.section_header("Execução do Query")
        query_res = query_chaincode(
            peer, peer_ip,
            definition["channel"], chaincode["name"],
            "ReadAsset", [TEST_ASSET["id"]]
        )
        show_command("Chaincode query (ReadAsset)", query_res)

        # Validação semântica do estado retornado
        raw_output = query_res.stdout.strip()
        data = json.loads(raw_output)
        semantic_ok = (
            data.get("ID") == TEST_ASSET["id"] and
            data.get("Color") == TEST_ASSET["color"] and
            data.get("Size") == int(TEST_ASSET["size"]) and
            data.get("Owner") == TEST_ASSET["owner"] and
            data.get("AppraisedValue") == int(TEST_ASSET["appraised_value"])
        )
        require_check("Validação semântica do estado consultado", (semantic_ok, f"Estado no ledger: {data}"))

        infra.banner("EXPERIMENT 04 CONCLUÍDO COM SUCESSO")
        print("\n[OK] Invoke committed no ledger e estado confirmado por query.\n")
        success = True

    except Exception as error:
        print(infra.format_diagnostic_line("Experimento 04 / invoke e query", False))
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
