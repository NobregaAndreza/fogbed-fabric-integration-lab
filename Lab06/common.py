#!/usr/bin/env python3

"""
Lab06/common.py

Este módulo reaproveita as funções já validadas no Lab05 sem duplicar a lógica
principal de diagnóstico. Ele apenas carrega o common.py do Lab05 em tempo de
execução e expõe os símbolos necessários para a baseline do Lab06.

Objetivo:
- manter a infraestrutura Peer + Orderer herdada do Lab05;
- reduzir o ruído e manter apenas os checks essenciais;
- preparar a base para futuras etapas de canal.
"""

import importlib.util
import os
import subprocess
import time
import json
import tempfile
import shlex

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LAB05_COMMON = os.path.abspath(os.path.join(ROOT_DIR, "..", "Lab05", "common.py"))

spec = importlib.util.spec_from_file_location("lab05_common", LAB05_COMMON)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Não foi possível carregar o módulo comum do Lab05 em: {LAB05_COMMON}")

lab05_common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab05_common)

# Reaproveita os diagnósticos já validados no Lab05.
get_container_real_ip = lab05_common.get_container_real_ip
check_container_process = lab05_common.check_container_process
check_container_logs = lab05_common.check_container_logs
check_container_netns_info = lab05_common.check_container_netns_info
check_tcp_port_in_netns = lab05_common.check_tcp_port_in_netns
check_grpc_tls_port_in_netns = lab05_common.check_grpc_tls_port_in_netns
format_diagnostic_line = lab05_common.format_diagnostic_line
banner = lab05_common.banner
section_header = lab05_common.section_header
wait_for_user = lab05_common.wait_for_user
ask_cleanup = lab05_common.ask_cleanup

ORDERER_ADMIN_PORT = 9443
CHANNEL_ID = "mychannel"
CHANNEL_BLOCK = os.path.join(ROOT_DIR, "channel-artifacts", f"{CHANNEL_ID}.block")
PEER_ADMIN_MSP = "/etc/hyperledger/fabric/admin-msp"
PEER_CHANNEL_BLOCK = f"/etc/hyperledger/fabric/channel-artifacts/{CHANNEL_ID}.block"


def create_peer(*args, application_channel=False, **kwargs):
    """Preserva a baseline; no teste de canal usa identidades e bloco do Lab06."""
    peer = lab05_common.create_peer(*args, **kwargs)
    if not application_channel:
        return peer
    prepare_environment(application_channel=True, require_existing=True)
    volumes = []
    for volume in peer.volumes:
        source, destination = volume.split(':', 1)
        source = os.path.join(ROOT_DIR, 'crypto-material',
                              os.path.relpath(source, lab05_common.CRYPTO_DIR))
        if not os.path.isdir(source):
            raise FileNotFoundError(f'Material do Peer ausente: {source}')
        volumes.append(f'{source}:{destination}')
        if destination == peer.environment['CORE_PEER_MSPCONFIGPATH']:
            org_dir = os.path.dirname(os.path.dirname(os.path.dirname(source)))
    domain = os.path.basename(org_dir)
    admin_msp = os.path.join(org_dir, 'users', f'Admin@{domain}', 'msp')
    if not os.path.isdir(admin_msp):
        raise FileNotFoundError(f'MSP administrativo ausente: {admin_msp}')
    peer.volumes = volumes + [f'{admin_msp}:{PEER_ADMIN_MSP}:ro',
                              f'{CHANNEL_BLOCK}:{PEER_CHANNEL_BLOCK}:ro']
    return peer


def run_peer_channel(peer, target_ip, operation):
    """Join/list usando CLI da imagem e MSP Admin, sem mudar o ambiente do nó."""
    if operation not in ('join', 'list'):
        raise ValueError('Operação permitida: join ou list')
    env = peer.environment
    cli_env = {
        'CORE_PEER_LOCALMSPID': env['CORE_PEER_LOCALMSPID'],
        'CORE_PEER_MSPCONFIGPATH': PEER_ADMIN_MSP,
        'CORE_PEER_ADDRESS': f"{target_ip}:{env['CORE_PEER_LISTENADDRESS'].rsplit(':', 1)[1]}",
        'CORE_PEER_TLS_ENABLED': env['CORE_PEER_TLS_ENABLED'],
        'CORE_PEER_TLS_ROOTCERT_FILE': env['CORE_PEER_TLS_ROOTCERT_FILE'],
        'CORE_PEER_TLS_SERVERHOSTOVERRIDE': env['CORE_PEER_ID'],
    }
    command = ['env'] + [f'{key}={value}' for key, value in cli_env.items()]
    command += ['peer', 'channel', operation]
    if operation == 'join':
        command += ['-b', PEER_CHANNEL_BLOCK]
    marker = '__LAB06_PEER_EXIT__='
    script = (shlex.join(command) + ' 2>&1; result=$?; '
              + "printf '\\n" + marker + "%s\\n' \"$result\"")
    try:
        output = peer.cmd('sh -c ' + shlex.quote(script)).rstrip()
        body, separator, status = output.rpartition('\n' + marker)
        if not separator or status.strip() != '0':
            return False, output
        evidence = body + '\nexit code: 0'
        if operation == 'list':
            header = 'Channels peers has joined:'
            _, found, channels = body.partition(header)
            if not found or CHANNEL_ID not in [line.strip() for line in channels.splitlines()]:
                return False, evidence
        return True, evidence
    except Exception as error:
        return False, f'peer channel {operation}: {error}'


def create_orderer(*args, channel_participation=False,
                   admin_port=ORDERER_ADMIN_PORT, **kwargs):
    """Adapta o container herdado somente quando Participation é solicitado."""
    orderer = lab05_common.create_orderer(*args, **kwargs)
    if not channel_participation:
        return orderer

    # Preserva os destinos MSP/TLS, usando as identidades do bloco do Lab06.
    volumes = []
    for volume in orderer.volumes:
        source, destination = volume.split(":", 1)
        if destination == "/etc/hyperledger/fabric/genesis.block":
            continue
        source = os.path.join(ROOT_DIR, "crypto-material",
                              os.path.relpath(source, lab05_common.CRYPTO_DIR))
        volumes.append(f"{source}:{destination}")
    orderer.volumes = volumes
    env = orderer.environment
    env.pop("ORDERER_GENERAL_BOOTSTRAPFILE", None)
    env.update({
        "ORDERER_GENERAL_BOOTSTRAPMETHOD": "none",
        "ORDERER_CHANNELPARTICIPATION_ENABLED": "true",
        "ORDERER_ADMIN_LISTENADDRESS": f"0.0.0.0:{admin_port}",
        "ORDERER_ADMIN_TLS_ENABLED": "true",
        "ORDERER_ADMIN_TLS_CLIENTAUTHREQUIRED": "true",
        "ORDERER_ADMIN_TLS_CERTIFICATE": env["ORDERER_GENERAL_TLS_CERTIFICATE"],
        "ORDERER_ADMIN_TLS_PRIVATEKEY": env["ORDERER_GENERAL_TLS_PRIVATEKEY"],
        "ORDERER_ADMIN_TLS_CLIENTROOTCAS": env["ORDERER_GENERAL_TLS_ROOTCAS"],
    })
    return orderer


def check_orderer_participation_api(orderer, target_ip, retries=10, expected_channel=None):
    """GET autenticado: sem system channel e com a lista esperada de canais."""
    env = orderer.environment
    tls_dir = next(source for source, destination in
                   (volume.split(":", 1) for volume in orderer.volumes)
                   if destination == "/etc/hyperledger/fabric/tls")
    hostname = os.path.basename(os.path.dirname(tls_dir))
    port = int(env["ORDERER_ADMIN_LISTENADDRESS"].rsplit(":", 1)[1])
    # nsenter apenas na rede: caminhos de certificados continuam sendo do host.
    code = fr'''
import http.client, json, socket, ssl
ctx = ssl.create_default_context(cafile={os.path.join(tls_dir, 'ca.crt')!r})
ctx.load_cert_chain({os.path.join(tls_dir, 'server.crt')!r},
                    {os.path.join(tls_dir, 'server.key')!r})
with socket.create_connection(({target_ip!r}, {port}), timeout=2) as raw:
    with ctx.wrap_socket(raw, server_hostname={hostname!r}) as sock:
        sock.sendall(b'GET /participation/v1/channels HTTP/1.1\r\nHost: ' +
                     {hostname!r}.encode() + b'\r\nConnection: close\r\n\r\n')
        response = http.client.HTTPResponse(sock)
        response.begin()
        body = response.read().decode()
        if response.status != 200:
            raise RuntimeError(f'HTTP {{response.status}}: {{body}}')
        data = json.loads(body)
        if 'systemChannel' not in data or data['systemChannel'] is not None:
            raise RuntimeError(f'System channel inesperado: {{body}}')
        expected = {expected_channel!r}
        channels = data.get('channels')
        if 'channels' not in data:
            raise RuntimeError(f'Campo channels ausente: {{body}}')
        if expected is None and channels not in (None, []):
            raise RuntimeError(f'Lista de canais inesperada: {{body}}')
        if expected is not None and (not isinstance(channels, list) or
                len(channels) != 1 or channels[0].get('name') != expected):
            raise RuntimeError(f'Lista de canais inesperada: {{body}}')
        print('OK Admin mTLS HTTP 200: ' + body)
'''
    for attempt in range(retries):
        ok, message = lab05_common.run_in_container_netns(orderer, code)
        if ok:
            return ok, message
        if attempt + 1 < retries:
            time.sleep(0.5)
    return False, message

# Gera artefatos do Lab06 usando a mesma abordagem do Lab05, mas no diretório do Lab06.
def prepare_environment(application_channel=False, require_existing=False):
    """Gera certificados e genesis para o Lab06 quando necessário."""
    if require_existing:
        if not application_channel:
            raise ValueError("require_existing exige application_channel=True")
        if not os.path.isfile(CHANNEL_BLOCK) or os.path.getsize(CHANNEL_BLOCK) == 0:
            raise FileNotFoundError(f"Bloco previamente validado ausente/vazio: {CHANNEL_BLOCK}")
        return
    if application_channel:
        subprocess.run(
            ["bash", os.path.join(ROOT_DIR, "scripts", "generate-artifacts.sh"),
             "--application"],
            check=True,
        )
        return
    crypto_dir = os.path.join(ROOT_DIR, "crypto-material")
    genesis_block = os.path.join(ROOT_DIR, "channel-artifacts", "genesis.block")
    if os.path.exists(genesis_block) and os.path.exists(crypto_dir):
        return
    script = os.path.join(ROOT_DIR, "scripts", "generate-artifacts.sh")
    if os.path.exists(script):
        os.system(f"bash '{script}'")
        return
    raise FileNotFoundError(f"Script de geração de artefatos não encontrado em: {script}")


def join_orderer_to_channel(orderer, target_ip):
    """Executa osnadmin uma vez, preservando bloco, status HTTP e resposta real."""
    prepare_environment(application_channel=True, require_existing=True)
    pid = lab05_common.get_container_pid(orderer)
    if not pid:
        return False, "PID do Orderer não encontrado"
    tls_dir = next(source for source, destination in
                   (volume.split(":", 1) for volume in orderer.volumes)
                   if destination == "/etc/hyperledger/fabric/tls")
    hostname = os.path.basename(os.path.dirname(tls_dir))
    port = orderer.environment['ORDERER_ADMIN_LISTENADDRESS'].rsplit(':', 1)[1]
    # Bash recebe dados como argumentos; nenhuma interpolação de caminhos em código.
    script = r'''
set -euo pipefail
source "$1"
shift
OSNADMIN_BIN="$(command -v osnadmin)"
HOSTS_FILE="$1"
ORDERER_PID="$2"
shift 2
exec nsenter -t "$ORDERER_PID" -n unshare --mount --propagation private \
    bash -c 'set -e; mount --bind "$1" /etc/hosts; shift; exec "$@"' \
    bash "$HOSTS_FILE" "$OSNADMIN_BIN" channel join "$@"
'''
    try:
        with tempfile.TemporaryDirectory(prefix="lab06-osnadmin-") as tmp:
            hosts_path = os.path.join(tmp, 'hosts')
            with open('/etc/hosts', encoding='utf-8') as source:
                hosts = source.read()
            with open(hosts_path, 'w', encoding='utf-8') as destination:
                destination.write(f"{target_ip} {hostname}\n" + hosts)
            result = subprocess.run([
                'bash', '-c', script, 'lab06-osnadmin',
                os.path.join(ROOT_DIR, 'scripts', 'fabric-env.sh'), hosts_path, str(pid),
                '-o', f'{hostname}:{port}',
                '--ca-file', os.path.join(tls_dir, 'ca.crt'),
                '--client-cert', os.path.join(tls_dir, 'server.crt'),
                '--client-key', os.path.join(tls_dir, 'server.key'),
                '--channelID', CHANNEL_ID, '--config-block', CHANNEL_BLOCK,
            ], capture_output=True, text=True, timeout=30)
        output = result.stdout.strip()
        evidence = output + ('\n' + result.stderr.strip() if result.stderr else '')
        if result.returncode != 0:
            return False, evidence
        status, _, body = output.partition('\n')
        if status.strip() != 'Status: 201':
            return False, evidence
        data = json.loads(body)
        valid = (data.get('name') == CHANNEL_ID
                 and data.get('consensusRelation') == 'consenter'
                 and data.get('status') == 'active'
                 and data.get('height') == 1)
        return valid, evidence
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return False, f"osnadmin: {error}. Join não repetido; inspecione o Orderer."


def cleanup():
    """Limpeza específica do Lab06."""
    script = os.path.join(ROOT_DIR, "clean.sh")
    if os.path.exists(script):
        os.system(f"bash '{script}'")
        return
    raise FileNotFoundError(f"Script de limpeza não encontrado em: {script}")
