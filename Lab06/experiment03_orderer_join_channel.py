#!/usr/bin/env python3
"""Ingresso de um único Orderer usando o bloco existente; nenhum Peer."""
from common import (
    prepare_environment, create_orderer, get_container_real_ip,
    check_container_process, check_container_logs, check_orderer_participation_api,
    join_orderer_to_channel, CHANNEL_ID, banner, format_diagnostic_line, wait_for_user,
)
from fogbed import FogbedExperiment


def main():
    prepare_environment(application_channel=True, require_existing=True)
    exp = FogbedExperiment()
    cloud = exp.add_virtual_instance('cloud')
    orderer = create_orderer(channel_participation=True)
    exp.add_docker(orderer, cloud)
    success = False
    try:
        exp.start()
        banner('ORDERER JOIN: APPLICATION CHANNEL')
        results = []
        try:
            real_ip = get_container_real_ip(orderer)
            if not real_ip:
                raise RuntimeError('IP real do Orderer não encontrado')
            print(f'Orderer IP real: {real_ip}')
            initial = check_orderer_participation_api(orderer, real_ip)
            results.append(('Admin mTLS / estado inicial vazio', initial))
            if initial[0]:
                joined = join_orderer_to_channel(orderer, real_ip)
                results.append(('osnadmin channel join / HTTP 201', joined))
                # Consulta mesmo após resposta de erro: pode haver ingresso parcial.
                results.append(('Admin / canal presente e sem system channel',
                                check_orderer_participation_api(
                                    orderer, real_ip, expected_channel=CHANNEL_ID)))
            else:
                print('Join não executado: estado inicial não confirmado.')
        except Exception as error:
            results.append(('Execução', (False, str(error))))
        results.extend([
            ('Processo Orderer após operação', check_container_process(orderer, 'orderer')),
            ('Logs Orderer após operação', check_container_logs(orderer)),
        ])
        for label, (ok, message) in results:
            print(format_diagnostic_line(label, ok))
            print(f'  {message}')
        success = all(ok for _, (ok, _) in results)
        print(format_diagnostic_line(f'Orderer em {CHANNEL_ID}', success))
        wait_for_user()
    finally:
        exp.stop()
        print('Artefatos preservados. Nenhum Peer foi iniciado.')
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
