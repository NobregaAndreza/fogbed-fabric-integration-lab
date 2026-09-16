#!/usr/bin/env python3
"""Sessão independente até readiness, commit e querycommitted; sem lógica de negócio."""
import argparse

from common import (
    CHAINCODES, PACKAGE_DIR, infra, select_chaincode, fabric_environment,
    check_prerequisites, create_network, validate_network, package_chaincode,
    install_chaincode, query_installed_chaincodes, identify_installed_package, show_command,
    DEFINITION_DEFAULTS, approve_chaincode_for_org,
    check_commit_readiness, commit_chaincode_definition, query_committed_chaincode,
)


def main():
    """Orquestra uma sessão independente e retorna 0 após readiness, commit e consulta final.

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
        infra.banner('LAB07: COMMIT DA DEFINIÇÃO NO CANAL')
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
        # Readiness consulta a aprovação; falha aqui impede o envio do commit.
        approvals, result = check_commit_readiness(peer, peer_ip, definition)
        show_command('checkcommitreadiness', result)
        msp = peer.environment['CORE_PEER_LOCALMSPID']
        print(f'  {msp}: {str(approvals[msp]).lower()}')

        # Commit registra a definição no canal, aguardando a transação válida.
        show_command('commit', commit_chaincode_definition(
            peer, peer_ip, orderer, definition))

        # Consulta independente comprova o estado persistido, não executa contrato.
        committed, result = query_committed_chaincode(peer, peer_ip, definition)
        show_command('querycommitted', result)
        for key in ('name', 'version', 'sequence'):
            print(f'  {key}: {committed[key]}')
        print(infra.format_diagnostic_line(
            f"Definição do chaincode em {definition['channel']}", True))
        success = True
    except Exception as error:
        print(infra.format_diagnostic_line('Experimento 03 / definição do chaincode', False))
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
