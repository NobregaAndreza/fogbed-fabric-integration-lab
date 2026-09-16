#!/usr/bin/env python3
"""Sessão independente até approveformyorg para Org1; sem commit da definição."""
import argparse

from common import (
    CHAINCODES, PACKAGE_DIR, infra, select_chaincode, fabric_environment,
    check_prerequisites, create_network, validate_network, package_chaincode,
    install_chaincode, query_installed_chaincodes, identify_installed_package, show_command,
    DEFINITION_DEFAULTS, approve_chaincode_for_org,
)


def main():
    """Orquestra uma sessão independente e retorna 0 somente após aprovação bem-sucedida.

    Mantém a rede para inspeção até ENTER mesmo em falha de lifecycle. O finally
    encerra a rede, preservando crypto/bloco/pacote. Falhas de pré-requisitos não
    iniciam containers. Nenhum experimento anterior é executado.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chaincode', choices=sorted(CHAINCODES), default='basic')
    args = parser.parse_args()
    exp = None
    success = False
    try:
        # Seleção/pré-requisitos não dependem de artefatos deixados por outro Lab.
        chaincode = select_chaincode(args.chaincode)
        env = fabric_environment()
        check_prerequisites(env, chaincode)
        exp, orderer, peer = create_network(orderer_cli=True)
        exp.start()
        infra.banner('LAB07: APROVAÇÃO DA DEFINIÇÃO POR ORG1')
        peer_ip = validate_network(orderer, peer)
        print(infra.format_diagnostic_line('Chaincode selecionado', True))
        print(f"  {chaincode['name']} | {chaincode['language']} | {chaincode['label']} | {chaincode['path']}")

        # Package é local; install altera o Peer; queryinstalled confirma o ID real.
        package = package_chaincode(chaincode, PACKAGE_DIR, env)
        show_command('Chaincode package', package['result'])
        print(f"  Pacote: {package['path']}")
        show_command('Chaincode install', install_chaincode(peer, peer_ip, package))
        installed, result = query_installed_chaincodes(peer, peer_ip)
        show_command('queryinstalled', result)
        package_id = identify_installed_package(package, installed)
        print(infra.format_diagnostic_line('Package ID identificado', True))
        print(f'  {package_id}')

        # A revisão da definição é independente do label/hash do pacote instalado.
        definition = {**DEFINITION_DEFAULTS, 'name': chaincode['name']}
        print(f'  Definição: {definition}')
        show_command('approveformyorg', approve_chaincode_for_org(
            peer, peer_ip, orderer, definition, package_id))
        success = True
    except Exception as error:
        print(infra.format_diagnostic_line('Experimento 02', False))
        print(f'  {error}')
    finally:
        if exp is not None:
            try:
                infra.wait_for_user()
            finally:
                exp.stop()
                print('Artefatos Lab07 preservados; instalações/ledger não têm persistência garantida.')
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
