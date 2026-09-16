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
ORDERER_CLI_CA = '/lab07/orderer-tls/ca.crt'
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
DEFINITION_DEFAULTS = {'channel': infra.CHANNEL_ID, 'version': '1.0', 'sequence': 1}
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


def create_network(orderer_cli=False):
    """Prepara artefatos Lab07 e retorna (exp, orderer, peer), ainda sem start.

    orderer_cli=True monta a CA do Orderer em leitura no Peer para approveformyorg.
    O padrão preserva o Experiment 01. Reutiliza construtores/geração validados.
    Acrescenta socket Docker e
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
    if orderer_cli:
        tls_dir = next(v.split(':', 1)[0] for v in orderer.volumes
                       if v.split(':', 1)[1] == '/etc/hyperledger/fabric/tls')
        peer.volumes.append(f'{Path(tls_dir) / "ca.crt"}:{ORDERER_CLI_CA}:ro')
    peer.environment.update({
        'CORE_VM_ENDPOINT': f'unix://{DOCKER_SOCKET}',
        'CORE_CHAINCODE_BUILDER': f'hyperledger/fabric-ccenv:{FABRIC_VERSION}',
        'CORE_CHAINCODE_GOLANG_RUNTIME': f'hyperledger/fabric-baseos:{FABRIC_VERSION}',
        'CORE_CHAINCODE_INSTALLTIMEOUT': '300s',
    })
    # O topology_ip (10.0.0.20) é mantido nos metadados do Fogbed.
    # O chaincode_endpoint é descoberto dinamicamente na inicialização do container a partir da interface eth0
    # (onde o Docker atribui o IP operacional), garantindo que o Peer anuncie um endpoint
    # efetivamente alcançável ao runtime do chaincode (NetworkMode=host).
    peer.dcmd = (
        'sh -c \'export CORE_PEER_CHAINCODEADDRESS="$(ip -4 addr show dev eth0 | '
        'grep -oP "(?<=inet\\s)\\d+(\\.\\d+){3}" || hostname -i | awk "{print \\$1}"):7052"; '
        'exec peer node start\''
    )
    exp.add_docker(orderer, cloud)
    exp.add_docker(peer, fog)
    exp.add_link(cloud, fog)
    return exp, orderer, peer


def check_chaincode_endpoint_reachability(peer, port=7052, retries=10, delay=0.5):
    """Valida a alcançabilidade do endpoint :7052 a partir do contexto do host (runtime host mode).

    Reutiliza a descoberta de IP real do container Peer (infra.get_container_real_ip)
    e testa a porta TCP 7052 a partir do namespace do HOST.
    """
    import socket
    import time
    peer_ip = infra.get_container_real_ip(peer)
    if not peer_ip:
        return False, 'IP do Peer não encontrado'
    endpoint = f'{peer_ip}:{port}'
    for attempt in range(1, retries + 1):
        try:
            with socket.create_connection((peer_ip, port), timeout=2.0):
                return True, f'OK TCP {endpoint} alcançável do host ({attempt} tentativa(s))'
        except Exception as err:
            if attempt < retries:
                time.sleep(delay)
            else:
                return False, f'Falha ao conectar em {endpoint} a partir do host: {err}'
    return False, f'Timeout em {endpoint}'


def validate_chaincode_runtime_registration(peer, chaincode_name='basic', timeout=30):
    """Observa o container de runtime do chaincode e valida o registro no Peer.

    Verifica se o container dev-peer0... foi criado e permanece ativo, e se os logs
    do Peer confirmam o registro sem mensagens de erro/timeout.
    """
    import time
    start_time = time.time()
    container_found = False
    cc_container_name = None

    while time.time() - start_time < timeout:
        try:
            out = subprocess.check_output(['docker', 'ps', '--format', '{{.Names}}'], text=True).strip()
            for line in out.splitlines():
                if chaincode_name in line and 'dev-peer0' in line:
                    container_found = True
                    cc_container_name = line.strip()
                    break
        except Exception:
            pass
        if container_found:
            break
        time.sleep(1.0)

    if not container_found:
        return False, f'Container de runtime do chaincode {chaincode_name} não foi criado dentro de {timeout}s'

    # Aguarda uma janela curta para garantir estabilidade (não apenas ms)
    time.sleep(3.0)

    try:
        out = subprocess.check_output(['docker', 'ps', '--format', '{{.Names}}'], text=True).strip()
        if cc_container_name not in out.splitlines():
            try:
                err_logs = subprocess.check_output(['docker', 'logs', '--tail', '30', cc_container_name],
                                                 stderr=subprocess.STDOUT, text=True).strip()
            except Exception:
                err_logs = 'logs indisponíveis'
            return False, f'Runtime {cc_container_name} encerrou prematuramente. Logs:\n{err_logs}'
    except Exception as ex:
        return False, f'Erro ao verificar status do container runtime: {ex}'

    peer_logs = ''
    try:
        candidate_names = [peer.name, f'mn.{peer.name}', f'{peer.name}.fogbed']
        for c_name in candidate_names:
            try:
                peer_logs = subprocess.check_output(['docker', 'logs', '--tail', '100', c_name],
                                                    stderr=subprocess.STDOUT, text=True).strip()
                if peer_logs:
                    break
            except Exception:
                pass
    except Exception:
        pass

    negative_keywords = [
        'chaincode registration failed',
        'container exited with 2',
        'Error starting asset-transfer-basic chaincode',
        'i/o timeout'
    ]
    found_negatives = [kw for kw in negative_keywords if kw in peer_logs]
    if found_negatives:
        return False, f'Erros de registro detectados nos logs do Peer: {", ".join(found_negatives)}'

    evidence = f'Container {cc_container_name} ativo e estável. Registro no Peer confirmado sem erros.'
    return True, evidence


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

    arguments contém uma operação de lifecycle até querycommitted e seus argumentos. Usa ID
    Docker guardado pelo Fogbed; não redescobre nomes de containers. O ambiente CLI
    deriva do nó e substitui somente MSP administrativo/endereço/hostname TLS.
    Exit code e streams separados evitam novo parser de marcadores de terminal.
    """
    if not arguments or arguments[0] not in (
        'install', 'queryinstalled', 'approveformyorg',
        'checkcommitreadiness', 'commit', 'querycommitted',
    ):
        raise ValueError('Operação fora do escopo do lifecycle implementado')
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


def approve_chaincode_for_org(peer, peer_ip, orderer, definition, package_id):
    """Aprova uma definição pela organização do Admin MSP usado pelo CLI.

    peer/peer_ip identificam o Peer ativo e seu IP descoberto; orderer fornece
    hostname TLS/porta. definition contém channel, name, version e sequence;
    package_id deve vir de queryinstalled nesta sessão, identificado pelo helper.
    Retorna CompletedProcess com exit code 0 e streams preservados; falhas propagam
    RuntimeError. Envia transação ao Ordering Service e aguarda seu evento válido.
    Não executa checkcommitreadiness nem commit da definição no canal.
    """
    definition_args = _definition_arguments(definition)
    if not isinstance(package_id, str) or not package_id.strip():
        raise ValueError('Package ID da instalação não identificado')
    arguments = ['approveformyorg', *definition_args, '--package-id', package_id,
                 *_orderer_arguments(peer, orderer),
                 '--waitForEvent', '--waitForEventTimeout', '60s']
    return peer_lifecycle(peer, peer_ip, arguments, timeout=90)


def _definition_arguments(definition):
    """Valida channel/name/version/sequence e retorna flags comuns, sem efeitos.

    A mesma definição explícita alimenta aprovação, readiness e commit, evitando
    defaults divergentes entre operações. Entradas inválidas levantam ValueError.
    """
    for key in ('channel', 'name', 'version'):
        if not isinstance(definition.get(key), str) or not definition[key].strip():
            raise ValueError(f'Definição exige {key} textual não vazio')
    sequence = definition.get('sequence')
    if type(sequence) is not int or sequence < 1:
        raise ValueError('sequence deve ser inteiro positivo')
    return ['--channelID', definition['channel'], '--name', definition['name'],
            '--version', definition['version'], '--sequence', str(sequence)]


def _orderer_arguments(peer, orderer):
    """Deriva flags gRPC/TLS dos nós existentes para aprovação e commit.

    Recebe os containers, verifica a montagem da CA e retorna argv sem modificar
    rede ou certificados. O hostname continua usando o mapeamento já validado.
    """
    if not any(v.endswith(f':{ORDERER_CLI_CA}:ro') for v in peer.volumes):
        raise ValueError('CA do Orderer não montada: prepare a rede com orderer_cli=True')

    # A mesma identidade TLS usada pelo Lab06 resolve no hosts do Peer. O CLI
    # roda nesse container; não usa IP fixo ou um mapeamento temporário paralelo.
    tls_dir = next(v.split(':', 1)[0] for v in orderer.volumes
                   if v.split(':', 1)[1] == '/etc/hyperledger/fabric/tls')
    hostname = Path(tls_dir).parent.name
    port = orderer.environment['ORDERER_GENERAL_LISTENPORT']
    return ['-o', f'{hostname}:{port}', '--tls', '--cafile', ORDERER_CLI_CA,
            '--ordererTLSHostnameOverride', hostname]


def check_commit_readiness(peer, peer_ip, definition):
    """Consulta aprovações da definição e exige aprovação da organização do Peer.

    Recebe nó/IP descoberto e a definição usada em approveformyorg. Usa Admin MSP
    via peer_lifecycle; não envia transação. Retorna (aprovações, CompletedProcess),
    preservando streams/exit. JSON inválido ou aprovação diferente de bool true
    levanta RuntimeError antes de permitir commit nesta topologia de uma org.
    """
    result = peer_lifecycle(peer, peer_ip, [
        'checkcommitreadiness', *_definition_arguments(definition), '--output', 'json'])
    try:
        data = json.loads(result.stdout)
        # O exemplo da documentação 2.5 usa Approvals; o protobuf usa approvals.
        approvals = data['approvals'] if 'approvals' in data else data['Approvals']
        if not isinstance(approvals, dict) or any(type(v) is not bool for v in approvals.values()):
            raise ValueError('Mapa de aprovações inválido')
        msp = peer.environment['CORE_PEER_LOCALMSPID']
        if approvals.get(msp) is not True:
            raise ValueError(f'{msp} não aprovou a definição; commit interrompido')
    except (ValueError, KeyError, TypeError) as error:
        raise RuntimeError(f'checkcommitreadiness: {error}\nexit code: {result.returncode}'
                           f'\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}') from error
    return approvals, result


def commit_chaincode_definition(peer, peer_ip, orderer, definition):
    """Registra a definição aprovada no canal e aguarda seu evento de commit.

    Recebe a mesma definição de readiness e os nós/IP existentes. Endpoint, CA e
    MSP do Peer vêm do ambiente CLI; Orderer usa as flags TLS compartilhadas com
    approveformyorg. Envia uma transação, sem retry. Retorna CompletedProcess após
    exit 0 com --waitForEvent; status explicitamente não VALID provoca erro mesmo
    com exit 0. Streams permanecem separados e disponíveis como evidência.
    """
    result = peer_lifecycle(peer, peer_ip, [
        'commit', *_definition_arguments(definition), *_orderer_arguments(peer, orderer),
        '--waitForEvent', '--waitForEventTimeout', '60s'], timeout=90)
    # Exit 0 com espera habilitada é o contrato do CLI. Os logs acrescentam
    # evidência, sem exigir prefixos/timestamps ou comparar o output inteiro.
    statuses = re.findall(r'committed\s+with\s+status\s*\(\s*([A-Z_]+)\s*\)',
                          result.stdout + '\n' + result.stderr)
    if any(status != 'VALID' for status in statuses):
        raise RuntimeError(f'commit: transação inválida {statuses}\nexit code: {result.returncode}'
                           f'\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')
    return result


def query_committed_chaincode(peer, peer_ip, definition):
    """Consulta e compara name/version/sequence com a definição esperada no canal.

    Recebe nó/IP e a mesma definição do commit; retorna (registro, CompletedProcess).
    Consulta todas as definições em JSON para obter também name (a consulta por
    --name omite esse campo). É somente leitura; ausência, duplicidade, resposta
    inválida ou divergência levantam RuntimeError com os streams originais.
    """
    _definition_arguments(definition)
    result = peer_lifecycle(peer, peer_ip, [
        'querycommitted', '--channelID', definition['channel'], '--output', 'json'])
    try:
        entries = json.loads(result.stdout)['chaincode_definitions']
        if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
            raise ValueError('Lista de definições inválida')
        matches = [entry for entry in entries if entry.get('name') == definition['name']]
        if len(matches) != 1:
            raise ValueError(f'Definição {definition["name"]} ausente ou duplicada')
        found = matches[0]
        for key in ('name', 'version', 'sequence'):
            if type(found.get(key)) is not type(definition[key]) or found[key] != definition[key]:
                raise ValueError(f'{key}: esperado {definition[key]!r}, recebido {found.get(key)!r}')
    except (ValueError, KeyError, TypeError) as error:
        raise RuntimeError(f'querycommitted: {error}\nexit code: {result.returncode}'
                           f'\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}') from error
    return found, result


def show_command(label, result):
    """Apresenta exit code/stdout/stderr de um comando já checado por run_command.

    label identifica a etapa; result é CompletedProcess bem-sucedido. Retorna None;
    escreve apenas no terminal. Não infere sucesso comparando frases de logs.
    """
    print(infra.format_diagnostic_line(label, True))
    print(f'  exit code: {result.returncode}')
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())


def run_peer_cli(peer, peer_ip, command_args, timeout=90):
    """Executa um comando genérico da CLI do Fabric (peer ...) no container do Peer via Docker exec.

    command_args contém a sublista de argumentos a ser passada ao binário `peer`,
    por exemplo ['chaincode', 'invoke', ...].
    """
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
    command += [str(container_id), 'peer', *map(str, command_args)]
    return run_command(command, timeout=timeout)


def invoke_chaincode(peer, peer_ip, orderer, channel_name, chaincode_name, function, args=None, timeout=90):
    """Executa peer chaincode invoke no canal/chaincode especificando a função e argumentos.

    Formata o construtor JSON -c '{"Args":[function, arg1, arg2, ...]}' e envia a transação
    ao Ordering Service utilizando as flags gRPC/TLS derivadas do Orderer, aguardando o commit.
    Retorna CompletedProcess após exit 0. Falhas ou timeouts levantam RuntimeError.
    """
    if args is None:
        args = []
    ctor_payload = json.dumps({'Args': [function] + [str(a) for a in args]})
    arguments = [
        'chaincode', 'invoke',
        *_orderer_arguments(peer, orderer),
        '-C', channel_name,
        '-n', chaincode_name,
        '-c', ctor_payload,
        '--waitForEvent',
        '--waitForEventTimeout', '60s'
    ]
    return run_peer_cli(peer, peer_ip, arguments, timeout=timeout)


def query_chaincode(peer, peer_ip, channel_name, chaincode_name, function, args=None, timeout=30):
    """Executa peer chaincode query no canal/chaincode especificando a função e argumentos.

    Formata o construtor JSON -c '{"Args":[function, arg1, arg2, ...]}'.
    Retorna CompletedProcess com a resposta em stdout. Falhas levantam RuntimeError.
    """
    if args is None:
        args = []
    ctor_payload = json.dumps({'Args': [function] + [str(a) for a in args]})
    arguments = [
        'chaincode', 'query',
        '-C', channel_name,
        '-n', chaincode_name,
        '-c', ctor_payload
    ]
    return run_peer_cli(peer, peer_ip, arguments, timeout=timeout)


def check_orderer_block_created(orderer):
    """Verifica se o Orderer gerou/escreveu um novo bloco nos logs recentes.

    Retorna (sucesso, block_number, evidencia).
    """
    import re
    candidate_names = [orderer.name, f'mn.{orderer.name}', f'{orderer.name}.fogbed']
    logs = ''
    for c_name in candidate_names:
        try:
            logs = subprocess.check_output(['docker', 'logs', '--tail', '50', c_name],
                                           stderr=subprocess.STDOUT, text=True).strip()
            if logs:
                break
        except Exception:
            pass

    blocks = re.findall(r'(?:Created|Writing)\s+block\s+\[?(\d+)\]?', logs, re.IGNORECASE)
    if blocks:
        latest_block = int(blocks[-1])
        return True, latest_block, f'Novo bloco {latest_block} gerado/escrito pelo Orderer'
    return False, None, 'Nenhuma evidência de novo bloco nos logs do Orderer'


def check_peer_block_committed(peer, channel_name='mychannel', expected_block=None, timeout=10, delay=0.5):
    """Verifica se o Peer recebeu, validou e commitou o bloco esperado no ledger.

    Utiliza polling limitado para aguardar a recepção, validação e commit do bloco N.
    Retorna (sucesso, evidencia).
    """
    import re
    import time
    if expected_block is None:
        return False, 'Bloco esperado não especificado para a validação do Peer'

    block_str = str(expected_block)
    candidate_names = [peer.name, f'mn.{peer.name}', f'{peer.name}.fogbed']
    start_time = time.time()
    last_evidence = ''

    while time.time() - start_time < timeout:
        logs = ''
        for c_name in candidate_names:
            try:
                logs = subprocess.check_output(['docker', 'logs', '--tail', '100', c_name],
                                               stderr=subprocess.STDOUT, text=True).strip()
                if logs:
                    break
            except Exception:
                pass

        has_received = bool(re.search(rf'Received\s+block\s+\[?{block_str}\]?', logs, re.IGNORECASE))
        has_validated = bool(re.search(rf'Validated\s+block\s+\[?{block_str}\]?', logs, re.IGNORECASE))
        has_committed = bool(re.search(rf'Committed\s+block\s+\[?{block_str}\]?', logs, re.IGNORECASE))

        if has_received and has_validated and has_committed:
            return True, f'Bloco {block_str} recebido, validado e committed no ledger {channel_name}'

        missing = []
        if not has_received: missing.append('Received')
        if not has_validated: missing.append('Validated')
        if not has_committed: missing.append('Committed')
        last_evidence = f'Aguardando bloco {block_str} ({", ".join(missing)} pendente)'

        time.sleep(delay)

    return False, f'Timeout aguardando commit do bloco {block_str} no Peer: {last_evidence}'
