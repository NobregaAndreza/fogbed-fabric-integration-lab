#!/usr/bin/env python3
"""Orderer e Peer no mesmo canal; sem operações de chaincode."""
from datetime import datetime, timezone

from common import (
    prepare_environment, create_orderer, create_peer, get_container_real_ip,
    check_container_process, check_container_logs, check_tcp_port_in_netns,
    check_grpc_tls_port_in_netns, check_orderer_participation_api,
    join_orderer_to_channel, run_peer_channel, CHANNEL_ID,
    banner, format_diagnostic_line, wait_for_user,
    map_orderer_for_peer, check_peer_orderer_name, check_peer_delivery,
)
from fogbed import FogbedExperiment


def main():
    """Orquestra esta etapa isoladamente; mantém inspeção até ENTER e retorna 0/1."""
    prepare_environment(application_channel=True)
    exp = FogbedExperiment()
    cloud = exp.add_virtual_instance('cloud')
    fog = exp.add_virtual_instance('fog')
    orderer = create_orderer(channel_participation=True)
    peer = create_peer(application_channel=True)
    exp.add_docker(orderer, cloud)
    exp.add_docker(peer, fog)
    exp.add_link(cloud, fog)
    results = []

    def report(label, result):
        """Registra e apresenta a evidência (bool, mensagem), retornando o bool."""
        ok, message = result
        results.append(ok)
        print(format_diagnostic_line(label, ok))
        print(f'  {message}')
        return ok

    def require(label, result):
        """Interrompe operações dependentes quando uma pré-condição falha."""
        if not report(label, result):
            raise RuntimeError(f'Pré-condição/operação falhou: {label}')

    try:
        exp.start()
        banner('ORDERER + PEER: APPLICATION CHANNEL')
        try:
            orderer_ip = get_container_real_ip(orderer)
            peer_ip = get_container_real_ip(peer)
            if not orderer_ip or not peer_ip:
                raise RuntimeError('Não foi possível descobrir os IPs reais dos dois nós')
            print(f'IPs reais: Orderer={orderer_ip}; Peer={peer_ip}')
            require('Mapeamento dinâmico no Peer',
                    map_orderer_for_peer(peer, orderer, orderer_ip))
            require('Orderer inicialmente sem canais',
                    check_orderer_participation_api(orderer, orderer_ip))
            require('Orderer join / HTTP 201', join_orderer_to_channel(orderer, orderer_ip))
            require('Orderer em mychannel / sem system channel',
                    check_orderer_participation_api(
                        orderer, orderer_ip, expected_channel=CHANNEL_ID))
            port = int(peer.environment['CORE_PEER_LISTENADDRESS'].rsplit(':', 1)[1])
            require('TCP principal Peer', check_tcp_port_in_netns(peer, peer_ip, port))
            require('TLS principal Peer', check_grpc_tls_port_in_netns(
                peer, peer_ip, port, server_hostname=peer.environment['CORE_PEER_ID']))
            for name, node, process in [('Orderer', orderer, 'orderer'), ('Peer', peer, 'peer')]:
                require(f'Processo {name} antes do Peer join', check_container_process(node, process))
                require(f'Logs {name} antes do Peer join', check_container_logs(node))
            # Não repetir o join em caso de erro; a consulta mostra o estado real.
            require('Resolução do Orderer pelo Peer / TLS',
                    check_peer_orderer_name(peer, orderer, orderer_ip))
            since = datetime.now(timezone.utc).isoformat(timespec='microseconds')
            require('Peer ingressou em mychannel', run_peer_channel(peer, peer_ip, 'join'))
            require('Peer reconhece mychannel', run_peer_channel(peer, peer_ip, 'list'))
            report('Comunicação Peer -> Orderer após join', check_peer_delivery(
                peer, orderer_ip, int(orderer.environment['ORDERER_GENERAL_LISTENPORT']), since))
        except Exception as error:
            report('Execução', (False, str(error)))
        for name, node, process in [('Orderer', orderer, 'orderer'), ('Peer', peer, 'peer')]:
            report(f'Processo {name} após operação', check_container_process(node, process))
            report(f'Logs {name} após operação', check_container_logs(node))
        success = all(results)
        print(format_diagnostic_line(f'Orderer e Peer em {CHANNEL_ID}', success))
        wait_for_user()
    finally:
        exp.stop()
        print('Artefatos preservados.')
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
