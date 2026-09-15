#!/usr/bin/env python3
"""Infraestrutura Lab06 isolada no Lab07 e operações iniciais de lifecycle.

Não importa experimentos. A instância privada do common mantém seus próprios
caminhos; somente scripts/configurações declarativos são compartilhados por links.
Funções de lifecycle retornam dados estruturados ou levantam RuntimeError com
comando/exit code/stdout/stderr, permitindo ao experimento parar sem falso OK.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent
FABRIC_VERSION = '2.5.16'
DOCKER_SOCKET = Path('/var/run/docker.sock')
PACKAGE_DIR = ROOT_DIR / 'chaincode-packages'
CONTAINER_PACKAGES = '/lab07/chaincode-packages'
CHAINCODES = {
    'basic': {'name': 'basic', 'path': ROOT_DIR / 'chaincodes/basic',
              'language': 'golang', 'label': 'basic_1.0'},
}

# Carrega uma instância privada: não muda os globais de uma execução do Lab06.
_spec = importlib.util.spec_from_file_location('lab07_infra_lab06', ROOT_DIR.parent / 'Lab06/common.py')
if _spec is None or _spec.loader is None:
    raise RuntimeError('Não foi possível carregar os helpers do Lab06')
infra = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(infra)
infra.ROOT_DIR = str(ROOT_DIR)
infra.CHANNEL_BLOCK = str(ROOT_DIR / 'channel-artifacts' / f'{infra.CHANNEL_ID}.block')
# LAB05_COMMON no módulo carregado aponta ao arquivo original, somente para leitura.
# Seus construtores continuam servindo de base para as adaptações locais do Lab06.


def run_command(arguments, *, env=None, cwd=None, timeout=120):
    """Executa argv sem shell e devolve CompletedProcess em sucesso.

    env/cwd configuram apenas o subprocesso; timeout é em segundos. Captura stdout
    e stderr separadamente. Falhas/timeout levantam RuntimeError com evidência;
    operações mutantes não são repetidas automaticamente.
    """
    try:
        result = subprocess.run([str(arg) for arg in arguments], env=env, cwd=cwd,
                                capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f'Timeout ({timeout}s) em {arguments!r}; inspecione o Peer antes de repetir') from error
    except OSError as error:
        raise RuntimeError(f'Não foi possível executar {arguments[0]}: {error}') from error
    if result.returncode:
        raise RuntimeError(f'{arguments!r}\nexit code: {result.returncode}\n'
                           f'stdout:\n{result.stdout}\nstderr:\n{result.stderr}')
    return result


def fabric_environment():
    """Obtém PATH pelo resolvedor compartilhado e configura o CLI local.

    Retorna cópia do ambiente. Não gera artefatos nem modifica a máquina. O core.yaml
    local é somente para o CLI do host; o processo Peer usa o arquivo de sua imagem.
    Go é necessário para package Go; /usr/local/go/bin é aceito quando sudo omite PATH.
    """
    result = run_command(['bash', '-c', 'set -e; source "$1"; env -0', 'lab07-env',
                          ROOT_DIR / 'scripts/fabric-env.sh'])
    env = dict(item.split('=', 1) for item in result.stdout.split('\0') if '=' in item)
    env['FABRIC_CFG_PATH'] = str(ROOT_DIR / 'config')
    if not shutil.which('go', path=env.get('PATH')) and Path('/usr/local/go/bin/go').is_file():
        env['PATH'] = '/usr/local/go/bin:' + env.get('PATH', '')
    # O pacote inclui vendor: não baixar dependências nem trocar toolchain em silêncio.
    env.update(GOFLAGS='-mod=vendor', GOPROXY='off', GOSUMDB='off', GOTOOLCHAIN='local')
    return env


def select_chaincode(name):
    """Retorna uma cópia da definição de name no catálogo, com fonte local válida.

    Erra antes de iniciar a rede se o nome/path/label não forem válidos. Não gera
    código nem acessa o diretório original dos fabric-samples.
    """
    if name not in CHAINCODES:
        raise ValueError(f'Chaincode desconhecido: {name}; opções: {", ".join(CHAINCODES)}')
    chaincode = dict(CHAINCODES[name])
    source = Path(chaincode['path']).resolve()
    if not source.is_relative_to((ROOT_DIR / 'chaincodes').resolve()) or not source.is_dir():
        raise ValueError(f'Fonte local ausente/inválida: {source}')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]*', chaincode['label']):
        raise ValueError(f'Label inválido: {chaincode["label"]}')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', chaincode['name']):
        raise ValueError('Nome inválido para arquivo do pacote')
    chaincode['path'] = source
    return chaincode


def check_prerequisites(env, chaincode):
    """Verifica ferramentas, socket e imagens antes de criar a rede.

    Retorna None ou erro útil. Não instala ferramentas nem baixa imagens. O install
    utiliza Docker para compilar o pacote: ccenv e baseos devem estar disponíveis.
    """
    for command in ('peer', 'cryptogen', 'configtxgen', 'osnadmin', 'docker', 'nsenter', 'unshare', 'mount'):
        if not shutil.which(command, path=env.get('PATH')):
            raise RuntimeError(f'Ferramenta ausente no PATH resolvido: {command}')
    if chaincode['language'] == 'golang':
        if not shutil.which('go', path=env.get('PATH')):
            raise RuntimeError('Go >= 1.23 necessário para package; configure PATH inclusive sob sudo')
        version = run_command(['go', 'version'], env=env).stdout
        match = re.search(r'go(\d+)\.(\d+)', version)
        if not match or tuple(map(int, match.groups())) < (1, 23):
            raise RuntimeError(f'Go >= 1.23 necessário para o basic local: {version}')
    if not DOCKER_SOCKET.is_socket():
        raise RuntimeError(f'Socket Docker ausente: {DOCKER_SOCKET}')
    for image in ('peer', 'orderer', 'ccenv', 'baseos'):
        run_command(['docker', 'image', 'inspect', f'hyperledger/fabric-{image}:{FABRIC_VERSION}'], env=env)


def create_network():
    """Prepara artefatos Lab07 e retorna (exp, orderer, peer), ainda sem start.

    Reutiliza construtores/geração validados. Acrescenta somente socket Docker e
    volume de pacotes ao Peer para o builder/install. Não cria nós extras.
    """
    from fogbed import FogbedExperiment
    infra.prepare_environment(application_channel=True)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    exp = FogbedExperiment()
    cloud = exp.add_virtual_instance('cloud')
    fog = exp.add_virtual_instance('fog')
    orderer = infra.create_orderer(channel_participation=True)
    peer = infra.create_peer(application_channel=True)
    orderer.dimage = f'hyperledger/fabric-orderer:{FABRIC_VERSION}'
    peer.dimage = f'hyperledger/fabric-peer:{FABRIC_VERSION}'
    peer.volumes += [f'{DOCKER_SOCKET}:{DOCKER_SOCKET}', f'{PACKAGE_DIR}:{CONTAINER_PACKAGES}:ro']
    peer.environment.update({
        'CORE_VM_ENDPOINT': f'unix://{DOCKER_SOCKET}',
        'CORE_CHAINCODE_BUILDER': f'hyperledger/fabric-ccenv:{FABRIC_VERSION}',
        'CORE_CHAINCODE_GOLANG_RUNTIME': f'hyperledger/fabric-baseos:{FABRIC_VERSION}',
        'CORE_CHAINCODE_INSTALLTIMEOUT': '300s',
    })
    exp.add_docker(orderer, cloud)
    exp.add_docker(peer, fog)
    exp.add_link(cloud, fog)
    return exp, orderer, peer


def require_check(label, result):
    """Apresenta um resultado (bool, evidência) herdado; impede avanço se falhar."""
    ok, evidence = result
    print(infra.format_diagnostic_line(label, ok))
    print(f'  {evidence}')
    if not ok:
        raise RuntimeError(f'Pré-condição não satisfeita: {label}')


def validate_network(orderer, peer):
    """Reconstrói joins e valida delivery na rede iniciada; retorna o IP do Peer.

    Reutiliza operações do Lab06, sem duplicar sua implementação. Modifica hosts
    do Peer e ledgers via joins. Nenhum lifecycle é executado antes de terminar.
    """
    orderer_ip = infra.get_container_real_ip(orderer)
    peer_ip = infra.get_container_real_ip(peer)
    if not orderer_ip or not peer_ip:
        raise RuntimeError('Descoberta de IP real falhou')
    require_check('Mapeamento dinâmico', infra.map_orderer_for_peer(peer, orderer, orderer_ip))
    require_check('Admin sem canais', infra.check_orderer_participation_api(orderer, orderer_ip))
    require_check('Orderer join', infra.join_orderer_to_channel(orderer, orderer_ip))
    require_check('Orderer em mychannel', infra.check_orderer_participation_api(
        orderer, orderer_ip, expected_channel=infra.CHANNEL_ID))
    peer_port = int(peer.environment['CORE_PEER_LISTENADDRESS'].rsplit(':', 1)[1])
    require_check('TCP Peer', infra.check_tcp_port_in_netns(peer, peer_ip, peer_port))
    require_check('Resolução/TLS Orderer', infra.check_peer_orderer_name(peer, orderer, orderer_ip))
    for label, node, process in (('Orderer', orderer, 'orderer'), ('Peer', peer, 'peer')):
        require_check(f'Processo {label}', infra.check_container_process(node, process))
        require_check(f'Logs {label}', infra.check_container_logs(node))
    since = datetime.now(timezone.utc).isoformat(timespec='microseconds')
    require_check('Peer join', infra.run_peer_channel(peer, peer_ip, 'join'))
    require_check('Peer em mychannel', infra.run_peer_channel(peer, peer_ip, 'list'))
    require_check('Delivery Peer -> Orderer', infra.check_peer_delivery(
        peer, orderer_ip, int(orderer.environment['ORDERER_GENERAL_LISTENPORT']), since))
    require_check('Rede mínima funcional', (True, 'Joins e delivery confirmados nesta sessão'))
    return peer_ip


def peer_lifecycle(peer, peer_ip, arguments, timeout=60):
    """Executa lifecycle no Peer via Docker exec sem TTY e retorna CompletedProcess.

    arguments contém somente install ou queryinstalled e seus argumentos. Usa ID
    Docker guardado pelo Fogbed; não redescobre nomes de containers. O ambiente CLI
    deriva do nó e substitui somente MSP administrativo/endereço/hostname TLS.
    Exit code e streams separados evitam novo parser de marcadores de terminal.
    """
    if not arguments or arguments[0] not in ('install', 'queryinstalled'):
        raise ValueError('Somente install e queryinstalled são permitidos nesta etapa')
    docker = getattr(getattr(peer, '_service', None), 'docker', None)
    container_id = getattr(docker, 'did', None)
    if not container_id:
        raise RuntimeError('ID Docker ausente no serviço Fogbed do Peer')
    env = dict(peer.environment)
    env['CORE_PEER_MSPCONFIGPATH'] = infra.PEER_ADMIN_MSP
    port = env['CORE_PEER_LISTENADDRESS'].rsplit(':', 1)[1]
    env['CORE_PEER_ADDRESS'] = f'{peer_ip}:{port}'
    env['CORE_PEER_TLS_SERVERHOSTOVERRIDE'] = env['CORE_PEER_ID']
    command = ['docker', 'exec']
    for key, value in env.items():
        command += ['--env', f'{key}={value}']
    command += [str(container_id), 'peer', 'lifecycle', 'chaincode', *map(str, arguments)]
    return run_command(command, timeout=timeout)


def package_chaincode(chaincode, package_dir, env):
    """Empacota a definição selecionada e retorna caminho/label/package ID/evidência.

    chaincode contém name/path/language/label; package_dir é destino local; env
    fornece binários e core.yaml. Escreve primeiro em diretório temporário e só
    publica o .tar.gz após sucesso. O ID é label + SHA256 dos bytes exatos do pacote.
    """
    import tempfile
    package_dir = Path(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)
    destination = package_dir / f'{chaincode["name"]}.tar.gz'
    with tempfile.TemporaryDirectory(prefix='.package-', dir=package_dir) as temporary:
        output = Path(temporary) / destination.name
        result = run_command(['peer', 'lifecycle', 'chaincode', 'package', output,
                              '--path', chaincode['path'], '--lang', chaincode['language'],
                              '--label', chaincode['label']], env=env, timeout=120)
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError('Package retornou exit 0 sem criar arquivo válido')
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        output.replace(destination)
    return {'path': destination, 'label': chaincode['label'],
            'package_id': f'{chaincode["label"]}:{digest}', 'result': result}


def install_chaincode(peer, peer_ip, package):
    """Instala o pacote local no Peer e retorna a evidência CLI (exit code zero).

    package vem de package_chaincode. Verifica integridade antes do envio. Altera
    o armazenamento de instalações e aciona o builder Docker; não aprova/commita.
    """
    path = Path(package['path']).resolve()
    if path.parent != PACKAGE_DIR.resolve():
        raise ValueError('Pacote deve estar no diretório montado de chaincode-packages')
    expected = f"{package['label']}:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    if expected != package['package_id']:
        raise RuntimeError('Pacote mudou desde a geração; instalação interrompida')
    return peer_lifecycle(peer, peer_ip, ['install', f'{CONTAINER_PACKAGES}/{path.name}'], timeout=330)


def query_installed_chaincodes(peer, peer_ip):
    """Consulta instalações como JSON; retorna (lista, evidência CLI).

    É leitura. Rejeita resposta inválida mesmo com exit code zero; não mistura
    logs de stderr ao JSON. Cada item deve conter package_id e label textuais.
    """
    result = peer_lifecycle(peer, peer_ip, ['queryinstalled', '--output', 'json'])
    try:
        data = json.loads(result.stdout)
        entries = data['installed_chaincodes']
        if entries is None:
            entries = []
        if not isinstance(entries, list) or any(
            not isinstance(item, dict) or not isinstance(item.get('package_id'), str)
            or not isinstance(item.get('label'), str) for item in entries
        ):
            raise ValueError('Lista de instalações inválida')
    except (ValueError, KeyError, TypeError) as error:
        raise RuntimeError(f'queryinstalled: resposta inválida\n{result.stdout}\n{result.stderr}') from error
    return entries, result


def identify_installed_package(package, installed):
    """Exige correspondência exata de label e hash entre pacote local e instalação.

    Retorna o package ID confirmado ou levanta erro. Não aceita apenas label,
    pois builds diferentes podem compartilhar o mesmo label. Sem efeitos colaterais.
    """
    matches = [item for item in installed if item['label'] == package['label']
               and item['package_id'] == package['package_id']]
    if len(matches) != 1:
        raise RuntimeError(f'Package ID esperado não identificado univocamente: {package["package_id"]}')
    return matches[0]['package_id']
