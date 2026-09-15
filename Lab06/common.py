#!/usr/bin/env python3

"""
Infraestrutura e operações reutilizáveis do Lab06, validado manualmente.

Carrega uma instância privada do common do Lab05 para reutilizar containers e
checks. Adapta somente o modo application channel: artefatos locais, Admin/mTLS,
joins, resolução da identidade Fabric no Peer e observação de delivery.

Experimentos controlam sequência e apresentação. Este módulo concentra caminhos,
efeitos nos nós e interpretação de respostas, sem arquitetura de plugin. Funções
herdadas não são copiadas e os arquivos de Labs anteriores não são modificados.
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
    """Cria a descrição Fogbed do Peer, sem iniciar o container.

    Args/kwargs seguem o construtor herdado. application_channel=True seleciona
    MSP/TLS locais e monta Admin MSP e bloco como somente leitura para o CLI.
    Retorna Container; gera erro se os artefatos obrigatórios não existirem.
    O MSP do processo Peer não é substituído pelo MSP administrativo.
    """
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
    """Executa join/list no container usando o Admin MSP apenas para o CLI.

    peer é o Container ativo; target_ip vem da descoberta real; operation aceita
    join ou list. Retorna (sucesso, evidência com exit code). Join altera o ledger
    do Peer; list é leitura. Não repete joins nem gera blocos.
    container.cmd combina stdout/stderr em um terminal: normaliza ANSI/quebras,
    separa um único marcador de status e exige também o canal esperado em list.
    """
    import re
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
        output = peer.cmd('sh -c ' + shlex.quote(script))
        # container.cmd usa terminal: stdout/stderr já estão combinados por 2>&1.
        # Remove formatação ANSI, mas mantém a saída funcional separada do status.
        normalized = re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]', '', output)
        lines = normalized.splitlines()
        statuses = []
        content = []
        for line in lines:
            match = re.fullmatch(re.escape(marker) + r'([0-9]+)', line.strip())
            if match:
                statuses.append(int(match.group(1)))
            else:
                content.append(line)
        body = '\n'.join(content).strip()
        if len(statuses) != 1:
            return False, body + '\nMarcador de exit code ausente ou ambíguo. Saída bruta: ' + repr(output)
        exit_code = statuses[0]
        evidence = body + f'\nexit code: {exit_code}'
        if exit_code != 0:
            return False, evidence
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
    """Cria a descrição do Orderer reaproveitando o construtor do Lab05.

    Args/kwargs seguem o construtor herdado; channel_participation ativa o modo
    sem system channel e admin_port define a porta Admin (distinta de gRPC).
    Retorna Container ainda não iniciado. Ajusta somente volumes/ambiente desta
    instância: crypto local, bootstrap none, Admin mTLS e CA já existente.
    O padrão mantém a baseline histórica por system channel.
    """
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
    """Consulta o Admin por HTTPS/mTLS a partir da rede do Orderer.

    orderer fornece volumes/porta; target_ip é efetivo; retries limita tentativas.
    expected_channel=None exige estado vazio; um nome exige exatamente esse canal.
    Retorna (sucesso, resposta/erro). Não modifica canais. Carrega certificados
    do host, entra apenas no namespace de rede e valida CA/nome do servidor.
    null e [] são aceitos como ausência de application channels.
    """
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
    """Prepara artefatos locais antes de criar/iniciar os containers.

    application_channel seleciona o gerador do bloco de aplicação; require_existing
    apenas verifica esse bloco, sem geração. Retorna None ou propaga erro.
    A geração application preserva crypto existente e reescreve o bloco. O modo
    histórico mantém seu fluxo original. Não inicia rede nem executa joins.
    """
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
    """Envia uma única solicitação osnadmin join ao Orderer ativo.

    Recebe Container e IP real, usa CHANNEL_BLOCK existente e TLS dos volumes.
    Retorna (sucesso, resposta real); exige HTTP 201, nome, active/consenter e
    altura 1. Exit code do CLI isoladamente não comprova sucesso HTTP.
    Altera o ledger do Orderer. Usa hosts temporário em mount namespace privado
    para validar o nome TLS sem alterar o hosts do host. Não repete em timeout.
    """
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
    """Executa clean.sh do laboratório para remover crypto e channel-artifacts.

    Sem argumentos/retorno útil. Efeito destrutivo restrito a artefatos locais;
    não encerra containers. Mantém a semântica histórica de execução do script.
    """
    script = os.path.join(ROOT_DIR, "clean.sh")
    if os.path.exists(script):
        os.system(f"bash '{script}'")
        return
    raise FileNotFoundError(f"Script de limpeza não encontrado em: {script}")


def map_orderer_for_peer(peer, orderer, orderer_ip):
    """Publica a identidade TLS do Orderer no hosts visível ao processo Peer.

    Recebe os dois Containers e orderer_ip descoberto. Retorna (sucesso, evidência).
    Escreve /proc/<PID>/root/etc/hosts em lugar, preservando aliases alheios e
    substituindo entradas antigas desse nome. Recusa compartilhar o arquivo do
    host. Aplicar antes do join; repetir após recriação/mudança de endereço.
    """
    import ipaddress
    ipaddress.ip_address(orderer_ip)
    tls_dir = next(v.split(':', 1)[0] for v in orderer.volumes
                   if v.split(':', 1)[1] == '/etc/hyperledger/fabric/tls')
    hostname = os.path.basename(os.path.dirname(tls_dir))
    pid = lab05_common.get_container_pid(peer)
    if not pid:
        return False, 'PID do Peer não encontrado'
    path = f'/proc/{pid}/root/etc/hosts'
    try:
        if os.path.samefile(path, '/etc/hosts'):
            return False, 'O Peer compartilha o arquivo hosts do host; alteração recusada'
        with open(path, encoding='utf-8') as stream:
            lines = stream.readlines()
        updated = []
        for line in lines:
            entry, mark, comment = line.partition('#')
            fields = entry.split()
            if len(fields) > 1 and hostname in fields[1:]:
                aliases = [alias for alias in fields[1:] if alias != hostname]
                if aliases:
                    updated.append(' '.join([fields[0]] + aliases) +
                                   (' #' + comment.rstrip() if mark else '') + '\n')
            else:
                updated.append(line if line.endswith('\n') else line + '\n')
        updated.append(f'{orderer_ip} {hostname}\n')
        # Escrita no inode montado pelo Docker; rename de /etc/hosts não é adequado.
        with open(path, 'w', encoding='utf-8') as stream:
            stream.writelines(updated)
        return True, f'{hostname} -> {orderer_ip} no /etc/hosts do Peer (PID {pid})'
    except OSError as error:
        return False, str(error)


def check_peer_orderer_name(peer, orderer, expected_ip):
    """Testa resolução e TCP/TLS na rede e raiz de arquivos do Peer.

    Recebe Peer, Orderer e expected_ip; retorna (sucesso, evidência/erro).
    O subprocesso carrega Python/CA do host antes de chroot na raiz do Peer.
    Somente o subprocesso muda de raiz. Exige IP esperado e certificado válido
    para o hostname Fabric; não instala ferramentas nem modifica TLS.
    """
    pid = lab05_common.get_container_pid(peer)
    if not pid:
        return False, 'PID do Peer não encontrado'
    tls_dir = next(v.split(':', 1)[0] for v in orderer.volumes
                   if v.split(':', 1)[1] == '/etc/hyperledger/fabric/tls')
    hostname = os.path.basename(os.path.dirname(tls_dir))
    port = int(orderer.environment['ORDERER_GENERAL_LISTENPORT'])
    code = f'''
import socket, ssl, os, encodings.idna
ctx = ssl.create_default_context(cafile={os.path.join(tls_dir, 'ca.crt')!r})
# Apenas o subprocesso de diagnóstico muda de raiz; usa hosts/resolv.conf do Peer.
# Python/socket/SSL e CA são carregados antes: nada é instalado na imagem.
os.chroot('/proc/{pid}/root')
os.chdir('/')
addresses = {{item[4][0] for item in socket.getaddrinfo({hostname!r}, {port}, socket.AF_INET, socket.SOCK_STREAM)}}
if addresses != {{{expected_ip!r}}}:
    raise RuntimeError(f'Resolução inesperada: {{addresses}}')
with socket.create_connection(({hostname!r}, {port}), timeout=3) as raw:
    with ctx.wrap_socket(raw, server_hostname={hostname!r}) as secure:
        print('OK Resolução e TCP/TLS com CA/hostname: ' + {hostname!r} + ' -> ' + secure.getpeername()[0])
'''
    return lab05_common.run_in_container_netns(peer, code, timeout=8)


def check_peer_delivery(peer, orderer_ip, orderer_port, since, timeout=10):
    """Observa conexão ao Orderer e logs novos em uma janela limitada pós-join.

    peer fornece PID/ID Docker; orderer_ip/port identificam o destino; since é
    instante UTC aceito por docker logs; timeout limita a observação.
    Retorna (sucesso, evidência/erro). Exige três amostras ESTABLISHED espaçadas
    em 1 s e logs presentes sem falhas Deliver/DNS/panic. Não modifica a rede.
    Não comprova entrega de novos blocos nem estabilidade por tempo ilimitado.
    """
    import socket
    import struct
    pid = lab05_common.get_container_pid(peer)
    if not pid:
        return False, 'PID do Peer não encontrado'
    # O serviço Fogbed já guarda o Docker/Containernet associado ao container.
    docker = getattr(getattr(peer, '_service', None), 'docker', None)
    container_id = getattr(docker, 'did', None)
    if not container_id:
        return False, 'ID Docker não disponível no serviço Fogbed; logs não verificados'
    deadline = time.monotonic() + timeout
    consecutive = 0
    last_logs = ''
    while time.monotonic() < deadline:
        try:
            result = subprocess.run(['docker', 'logs', '--since', since, str(container_id)],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode:
                return False, result.stderr or result.stdout
            last_logs = result.stdout + result.stderr
            errors = [line for line in last_logs.splitlines() if any(word in line for word in (
                'Could not connect to ordering service', 'lookup orderer', 'no such host',
                'Disconnected from ordering service', 'panic', 'FATAL', 'CRIT'))]
            if errors:
                return False, '\n'.join(errors)
            established = False
            for table in ('tcp', 'tcp6'):
                with open(f'/proc/{pid}/net/{table}', encoding='utf-8') as stream:
                    for line in stream.readlines()[1:]:
                        fields = line.split()
                        address, port = fields[2].split(':')
                        if fields[3] != '01' or int(port, 16) != orderer_port:
                            continue
                        raw = b''.join(struct.pack('=I', int(address[i:i+8], 16))
                                       for i in range(0, len(address), 8))
                        if table == 'tcp6':
                            if raw[:12] != b'\x00' * 10 + b'\xff\xff':
                                continue
                            raw = raw[-4:]
                        if socket.inet_ntop(socket.AF_INET, raw) == orderer_ip:
                            established = True
            consecutive = consecutive + 1 if established else 0
            if consecutive >= 3 and last_logs.strip():
                return True, ('Conexão Peer -> Orderer ESTABLISHED em 3 amostras (1 s); '
                              'logs pós-join sem falhas Deliver/DNS.\n' + last_logs)
        except (OSError, subprocess.TimeoutExpired) as error:
            return False, str(error)
        time.sleep(1)
    return False, 'Conexão estável/logs pós-join não confirmados na janela de observação.\n' + last_logs
