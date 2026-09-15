#!/usr/bin/env python3
"""Rede mínima e package/install/queryinstalled; nenhuma aprovação ou commit."""
import argparse

from common import (
    CHAINCODES, PACKAGE_DIR, infra, select_chaincode, fabric_environment,
    check_prerequisites, create_network, validate_network, package_chaincode,
    install_chaincode, query_installed_chaincodes, identify_installed_package,
)


def show_command(label, result):
    """Apresenta exit code e streams de comando que já passou pela checagem."""
    print(infra.format_diagnostic_line(label, True))
    print(f'  exit code: {result.returncode}')
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())


def main():
    """Orquestra uma sessão independente e retorna 0 somente após ID confirmado.

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
        exp, orderer, peer = create_network()
        exp.start()
        infra.banner('LAB07: PACKAGE / INSTALL / QUERYINSTALLED')
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
        success = True
    except Exception as error:
        print(infra.format_diagnostic_line('Experimento 01', False))
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
