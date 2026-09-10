#!/usr/bin/env python3
"""Inicialização e consulta de leitura do Admin; nenhum join é executado."""
from common import (
    prepare_environment, create_orderer, get_container_real_ip,
    check_container_process, check_container_logs, check_container_netns_info,
    check_tcp_port_in_netns, check_grpc_tls_port_in_netns,
    check_orderer_participation_api, banner, format_diagnostic_line,
    wait_for_user,
)
from fogbed import FogbedExperiment


def main():
    prepare_environment(application_channel=True)
    exp = FogbedExperiment()
    cloud = exp.add_virtual_instance('cloud')
    orderer = create_orderer(channel_participation=True)
    exp.add_docker(orderer, cloud)
    success = False
    try:
        exp.start()
        banner('ORDERER: CHANNEL PARTICIPATION SEM JOIN')
        real_ip = get_container_real_ip(orderer)
        if not real_ip:
            raise RuntimeError('IP real do Orderer não encontrado no namespace')
        print(f'Orderer IP real: {real_ip}')
        env = orderer.environment
        port = int(env['ORDERER_GENERAL_LISTENPORT'])
        admin_port = int(env['ORDERER_ADMIN_LISTENADDRESS'].rsplit(':', 1)[1])
        # A disponibilidade das portas usa as esperas já existentes no common.
        results = [
            ('Namespace', check_container_netns_info(orderer, real_ip)),
            ('TCP principal', check_tcp_port_in_netns(orderer, real_ip, port)),
            ('TLS principal', check_grpc_tls_port_in_netns(orderer, real_ip, port)),
            ('TCP Admin', check_tcp_port_in_netns(orderer, real_ip, admin_port)),
            ('Admin mTLS / ausência de canais',
             check_orderer_participation_api(orderer, real_ip)),
            ('Processo Orderer', check_container_process(orderer, 'orderer')),
            ('Logs Orderer', check_container_logs(orderer)),
        ]
        for label, (ok, message) in results:
            print(format_diagnostic_line(label, ok))
            print(f'  {message}')
        success = all(ok for _, (ok, _) in results)
        print(format_diagnostic_line('Inicialização sem canais', success))
        wait_for_user()
    finally:
        exp.stop()
        print('Artefatos preservados para a próxima etapa.')
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
