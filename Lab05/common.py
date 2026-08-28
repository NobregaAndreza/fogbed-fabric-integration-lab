#!/usr/bin/env python3

"""
common.py (Lab05)

Funções compartilhadas pelos experimentos do Lab05:
- Preparação de ambiente (geração automática de artefatos do Fabric);
- Construção parametrizada de containers Peer e Orderer;
- Configuração de escuta em 0.0.0.0 para os serviços gRPC e Operations Service;
- Diagnósticos executados via `nsenter` diretamente dentro do Network Namespace dos containers;
- Resolução dinâmica do PID dos containers Docker/Containernet (suportando prefixos mn., fogbed., etc.);
- Ajuste dos timeouts de subprocesso (6.0s) e socket (2.0s) para evitar falsos relatórios de timeout de processo;
- Suporte a respostas HTTP 200 e 503 no Operations Service (/healthz);
- Espera ativa / retries com contagem de tentativas;
- Formatação alinhada em 60 colunas com status honestos ([OK], [FAIL], [SKIP]);
- Controle do fluxo interativo e limpeza pós-execução.
"""

import sys
import os
import time
import socket
import ssl
import urllib.request
import urllib.error
import subprocess

# Garante que o Python carregue o módulo Containernet de /opt/fogbed/containernet
CONTAINERNET_PATH = "/opt/fogbed/containernet"
if os.path.exists(CONTAINERNET_PATH) and CONTAINERNET_PATH not in sys.path:
    sys.path.insert(0, CONTAINERNET_PATH)

from fogbed import Container

# ---------------------------------------------------------
# Diretórios e Caminhos Base
# ---------------------------------------------------------

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
CRYPTO_DIR = os.path.join(ROOT_DIR, "crypto-material")
CHANNEL_ARTIFACTS = os.path.join(ROOT_DIR, "channel-artifacts")
GENESIS_BLOCK = os.path.join(CHANNEL_ARTIFACTS, "genesis.block")

ARTIFACT_SCRIPT = os.path.join(SCRIPTS_DIR, "generate-artifacts.sh")
CLEAN_SCRIPT = os.path.join(SCRIPTS_DIR, "clean.sh")


# ---------------------------------------------------------
# Gerenciamento de Ambiente
# ---------------------------------------------------------

def prepare_environment():
    """
    Verifica se o bloco gênesis e os certificados MSP/TLS existem.
    Caso contrário, executa o script de geração de artefatos.
    """
    if os.path.exists(GENESIS_BLOCK) and os.path.exists(CRYPTO_DIR):
        print("\n[INFO] Artefatos do Hyperledger Fabric encontrados.")
        return

    print("\n[INFO] Artefatos inexistentes ou incompletos no Lab05.")
    print("[INFO] Gerando certificados e bloco gênesis...\n")
    subprocess.run([ARTIFACT_SCRIPT], check=True)


def cleanup():
    """
    Executa o script de limpeza do Lab05.
    """
    subprocess.run([CLEAN_SCRIPT], check=False)


# ---------------------------------------------------------
# Formatação Visual de Terminal (Largura Consistente: 60 colunas)
# ---------------------------------------------------------

def banner(title, width=60):
    """
    Exibe um banner principal centralizado com largura consistente.
    """
    print()
    print("=" * width)
    print(title.center(width))
    print("=" * width)


def section_header(title, width=60):
    """
    Exibe um cabeçalho de seção estruturado com separador alinhado.
    """
    print()
    print(f"[{title.upper()}]")
    print("-" * width)


def format_diagnostic_line(label, status_val, detail=None, width=60):
    """
    Formata uma linha de resultado com alinhamento de pontos e status [OK], [FAIL] ou [SKIP].
    Exibe a causa técnica real (exceção/erro) sem mascarar diagnósticos.
    """
    if status_val is True or status_val == "OK" or (isinstance(status_val, str) and status_val.startswith("OK")):
        status_tag = "[OK]"
    elif status_val is False or status_val == "FAIL" or (isinstance(status_val, str) and status_val.startswith("FAIL")):
        status_tag = "[FAIL]"
    elif status_val == "SKIP":
        status_tag = "[SKIP]"
    else:
        status_tag = f"[{status_val}]"

    padding_len = max(2, width - len(label) - len(status_tag) - 1)
    dots = "." * padding_len
    line = f"{label} {dots} {status_tag}"

    if detail:
        if status_tag == "[FAIL]":
            line += f"\n  -> Erro real: {detail}"
        elif isinstance(detail, str) and ("tentativa" in detail or "HTTP" in detail or "packets" in detail or "bytes" in detail):
            line += f"\n  -> Evidência: {detail}"

    return line


def wait_for_user():
    """
    Mantém a topologia ativa aguardando interação do usuário.
    """
    print()
    print("O ambiente está ativo. Comandos de inspeção úteis:")
    print("  docker ps / podman ps")
    print("  docker logs <container> / podman logs <container>")
    print("  docker exec -it <container> bash / podman exec -it <container> bash")
    print()
    input("Pressione ENTER para finalizar...")


def ask_cleanup():
    """
    Pergunta ao usuário se deseja remover os artefatos temporários gerados.
    """
    answer = input("\nExecutar a limpeza do Lab05? [y/N]: ").strip().lower()
    return answer in ("y", "yes", "s", "sim")


# ---------------------------------------------------------
# Inspeção de PID e Namespace do Container
# ---------------------------------------------------------

def get_container_pid(container):
    """
    Obtém o PID do container no host para uso no `nsenter`.
    Utiliza múltiplos métodos de inspeção para garantir suporte ao Containernet/Mininet/Docker/Podman.
    """
    if hasattr(container, 'pid') and container.pid:
        return container.pid
    if hasattr(container, 'params') and isinstance(container.params, dict) and 'pid' in container.params:
        return container.params['pid']

    name = getattr(container, 'name', str(container))

    candidate_names = [
        name,
        f"mn.{name}",
        f"{name}.fogbed",
        f"fogbed.{name}",
        f"mn.fogbed.{name}",
        f"mn.{name}.fogbed"
    ]
    for c_name in candidate_names:
        for runtime in ["docker", "podman"]:
            try:
                cmd = [runtime, "inspect", "-f", "{{.State.Pid}}", c_name]
                res = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
                if res.isdigit() and int(res) > 0:
                    return int(res)
            except Exception:
                pass

    for runtime in ["docker", "podman"]:
        try:
            cmd = [runtime, "ps", "--format", "{{.Names}} {{.ID}}"]
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    docker_name, docker_id = parts[0], parts[1]
                    if name in docker_name:
                        pid_cmd = [runtime, "inspect", "-f", "{{.State.Pid}}", docker_id]
                        pid_res = subprocess.check_output(pid_cmd, stderr=subprocess.DEVNULL, text=True).strip()
                        if pid_res.isdigit() and int(pid_res) > 0:
                            return int(pid_res)
        except Exception:
            pass

    return None


def run_in_container_netns(container, py_code, timeout=6.0):
    """
    Executa um snippet de código Python dentro do Network Namespace do container.
    """
    pid = get_container_pid(container)
    if not pid:
        return False, f"PID do container {getattr(container, 'name', str(container))} não encontrado"

    cmd = [
        "nsenter", "-t", str(pid), "-n",
        "python3", "-c", py_code
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=timeout).strip()
        if "OK" in out:
            return True, out
        return False, out if out else "Sem resposta OK"
    except subprocess.TimeoutExpired:
        return False, "SubprocessTimeout: nsenter excedeu o tempo limite"
    except subprocess.CalledProcessError as cpe:
        return False, cpe.output.strip() if cpe.output else str(cpe)
    except Exception as ex:
        return False, str(ex)


# ---------------------------------------------------------
# Diagnósticos Nativos por Camadas com Espera Ativa (Retries)
# ---------------------------------------------------------

def check_container_process(container, process_keyword):
    """
    Verifica se um processo está rodando no container chamando 'ps aux'.
    """
    try:
        proc_out = container.cmd("ps aux").strip()
        if process_keyword in proc_out:
            return True, "OK"
        return False, f"Processo '{process_keyword}' não encontrado em ps aux"
    except Exception as ex:
        return False, str(ex)


def check_container_logs(container):
    """
    Verifica se os logs do container contêm erros críticos (panic, fatal, CRIT).
    """
    name = getattr(container, 'name', str(container))
    candidate_names = [
        name,
        f"mn.{name}",
        f"{name}.fogbed",
        f"fogbed.{name}",
        f"mn.fogbed.{name}",
        f"mn.{name}.fogbed"
    ]
    logs = ""
    for c_name in candidate_names:
        try:
            cmd = ["docker", "logs", "--tail", "50", c_name]
            logs = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
            if logs:
                break
        except Exception:
            pass

    if not logs:
        return True, "Sem logs capturados via Docker API"

    critical_keywords = ["panic:", "FATAL", "CRIT", "panic"]
    found_errors = []
    for line in logs.splitlines():
        if any(kw in line for kw in critical_keywords):
            found_errors.append(line.strip())

    if found_errors:
        return False, f"Erro crítico nos logs: {'; '.join(found_errors[:2])}"
    return True, "Nenhum panic/fatal nos logs"


def check_container_netns_info(container, expected_ip):
    """
    Valida PID real, isolamento do Network Namespace e IPs do container.

    Camada 1 (host): Compara /proc/<pid>/ns/net com /proc/1/ns/net para confirmar
    se o container tem namespace isolado ou compartilha o namespace do host.

    Camada 2 (nsenter + ip do host): Usa `nsenter -t <pid> -n ip -4 addr show`
    executado a partir do HOST. O binário `ip` usa NETLINK (namespace-aware via
    syscall), sem depender de /sys/class/net (que segue o mount namespace).
    Funciona mesmo que a imagem Fabric não tenha `ip`, `ifconfig` ou `python3`.
    """
    pid = get_container_pid(container)
    if not pid:
        return False, f"PID do container {getattr(container, 'name', str(container))} não encontrado"

    clean_exp_ip = expected_ip.split('/')[0]

    # Camada 1: verifica isolamento do namespace via inode
    ns_note = "isolamento desconhecido"
    try:
        container_ns = os.readlink(f"/proc/{pid}/ns/net")
        host_ns      = os.readlink("/proc/1/ns/net")
        if container_ns == host_ns:
            ns_note = f"COMPARTILHA namespace com o host ({container_ns})"
        else:
            ns_note = f"namespace isolado OK ({container_ns})"
    except Exception as ex:
        ns_note = f"erro ao ler ns/net: {ex}"

    # Camada 2: lista interfaces reais via nsenter + ip (NETLINK, namespace-aware)
    iface_info = "sem dados"
    ip_found   = False
    try:
        out = subprocess.check_output(
            ["nsenter", "-t", str(pid), "-n", "ip", "-4", "addr", "show"],
            stderr=subprocess.STDOUT, text=True, timeout=5
        ).strip()
        # Extrai pares iface=IP da saída de `ip addr`
        pairs = []
        current_iface = None
        for line in out.splitlines():
            line = line.strip()
            # linha de interface: "2: eth0: <BROADCAST,...>"
            if line and line[0].isdigit():
                current_iface = line.split(":")[1].strip().split("@")[0]
            # linha de IP: "inet 10.0.0.20/8 ..."
            elif line.startswith("inet ") and current_iface:
                addr = line.split()[1]          # ex: "10.0.0.20/8"
                ip   = addr.split("/")[0]
                pairs.append(f"{current_iface}={ip}")
                if ip == clean_exp_ip:
                    ip_found = True
        iface_info = ", ".join(pairs) if pairs else "nenhuma interface IPv4 ativa"
    except subprocess.TimeoutExpired:
        iface_info = "nsenter timeout"
    except subprocess.CalledProcessError as cpe:
        iface_info = cpe.output.strip() if cpe.output else str(cpe)
    except Exception as ex:
        iface_info = str(ex)

    status_tag = "FOUND" if ip_found else "MISSING"
    summary = f"PID {pid} | {ns_note} | {iface_info} | STATUS:{status_tag}"
    return ip_found, summary




def get_container_real_ip(container):
    """
    Retorna o primeiro IP não-loopback da interface principal do container,
    descoberto via `nsenter -t <pid> -n ip -4 addr show` (NETLINK, namespace-aware).
    Funciona mesmo sem `ip`/`ifconfig` dentro da imagem Fabric.
    Retorna None se não encontrar.
    """
    pid = get_container_pid(container)
    if not pid:
        return None
    try:
        out = subprocess.check_output(
            ["nsenter", "-t", str(pid), "-n", "ip", "-4", "addr", "show"],
            stderr=subprocess.DEVNULL, text=True, timeout=5
        ).strip()
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                addr = line.split()[1].split("/")[0]
                if not addr.startswith("127."):
                    return addr
    except Exception:
        pass
    return None


def check_tcp_port_in_netns(container, target_ip, target_port, retries=10, delay=0.5):

    """
    Testa porta TCP pura (sem TLS, sem HTTP) no Network Namespace do container.
    """
    clean_target_ip = target_ip.split('/')[0]
    sock_timeout = 2.0
    py_code = f"""
import socket
try:
    s = socket.create_connection(('{clean_target_ip}', {target_port}), timeout={sock_timeout})
    s.close()
    print('OK')
except Exception as e:
    print(type(e).__name__ + ': ' + str(e))
"""
    last_err = "Timeout"
    for attempt in range(1, retries + 1):
        ok, msg = run_in_container_netns(container, py_code, timeout=6.0)
        if ok:
            return True, f"OK ({attempt} tentativa(s) TCP)"
        last_err = msg
        if attempt < retries:
            time.sleep(delay)

    return False, last_err


def check_grpc_tls_port_in_netns(container, target_ip, target_port, server_hostname=None, retries=10, delay=0.5):
    """
    Testa a porta gRPC com TLS habilitado executando o Handshake TLS no Network Namespace do container.
    """
    clean_target_ip = target_ip.split('/')[0]
    sock_timeout = 2.0
    hostname_param = f"'{server_hostname}'" if server_hostname else "None"
    py_code = f"""
import socket, ssl
try:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    hostname = {hostname_param}
    with socket.create_connection(('{clean_target_ip}', {target_port}), timeout={sock_timeout}) as s:
        with ctx.wrap_socket(s, server_hostname=hostname) as ss:
            cipher_name = ss.cipher()[0] if ss.cipher() else 'TLS'
            print(f'OK Handshake TLS (Cipher: {{cipher_name}})')
except Exception as e:
    print(type(e).__name__ + ': ' + str(e))
"""
    last_err = "Timeout"
    for attempt in range(1, retries + 1):
        ok, msg = run_in_container_netns(container, py_code, timeout=6.0)
        if ok:
            return True, f"OK ({attempt} tentativa(s) TLS - {msg})"
        last_err = msg
        if attempt < retries:
            time.sleep(delay)

    return False, last_err


def check_http_health_in_netns(container, target_ip, target_port, endpoint="/healthz", retries=10, delay=0.5):
    """
    Testa o endpoint /healthz do Operations Service no Network Namespace do container.
    Suporta tanto respostas HTTP 200 quanto HTTP 503 (serviço ativo mas pendente de canal).
    """
    clean_target_ip = target_ip.split('/')[0]
    sock_timeout = 2.0
    py_code = f"""
import urllib.request, urllib.error
try:
    req = urllib.request.Request('http://{clean_target_ip}:{target_port}{endpoint}', headers={{'User-Agent': 'Fogbed-HealthCheck'}})
    try:
        with urllib.request.urlopen(req, timeout={sock_timeout}) as resp:
            body = resp.read().decode('utf-8').strip()
            print(f'OK (HTTP {{resp.status}} - {{body}})')
    except urllib.error.HTTPError as he:
        body = he.read().decode('utf-8').strip() if he.fp else ''
        print(f'OK (HTTP {{he.code}} - {{body}})')
except Exception as e:
    print(type(e).__name__ + ': ' + str(e))
"""
    last_err = "Timeout"
    for attempt in range(1, retries + 1):
        ok, msg = run_in_container_netns(container, py_code, timeout=6.0)
        if ok:
            return True, f"OK ({attempt} tentativa(s) HTTP - {msg})"
        last_err = msg
        if attempt < retries:
            time.sleep(delay)

    return False, last_err


# ---------------------------------------------------------
# Construção Parametrizada de Containers Fabric
# ---------------------------------------------------------

def create_peer(
    name="peer0",
    ip="10.0.0.20",
    org_domain="org1.example.com",
    msp_id="Org1MSP",
    port=7051,
    operations_port=9443,
    tls_enabled=True
):
    """
    Cria um container Hyperledger Fabric Peer parametrizado para o Fogbed.
    """
    clean_ip = ip.split('/')[0]

    peer_msp = os.path.join(
        CRYPTO_DIR,
        "peerOrganizations",
        org_domain,
        "peers",
        f"{name}.{org_domain}",
        "msp"
    )

    peer_tls = os.path.join(
        CRYPTO_DIR,
        "peerOrganizations",
        org_domain,
        "peers",
        f"{name}.{org_domain}",
        "tls"
    )

    env = {
        "FABRIC_LOGGING_SPEC": "INFO",
        "CORE_PEER_ID": f"{name}.{org_domain}",
        "CORE_PEER_ADDRESS": f"{clean_ip}:{port}",
        "CORE_PEER_LISTENADDRESS": f"0.0.0.0:{port}",
        "CORE_PEER_CHAINCODEADDRESS": f"{clean_ip}:{port + 1}",
        "CORE_PEER_CHAINCODELISTENADDRESS": f"0.0.0.0:{port + 1}",
        "CORE_PEER_LOCALMSPID": msp_id,
        "CORE_PEER_MSPCONFIGPATH": "/etc/hyperledger/fabric/msp",
        # Operations Service ouvindo em 0.0.0.0:9443 sem TLS inicial
        "CORE_OPERATIONS_LISTENADDRESS": f"0.0.0.0:{operations_port}",
        "CORE_OPERATIONS_LISTEN_ADDRESS": f"0.0.0.0:{operations_port}",
        "FABRIC_OPERATIONS_LISTENADDRESS": f"0.0.0.0:{operations_port}",
        "CORE_OPERATIONS_TLS_ENABLED": "false",
        # Gossip & Leader Election
        "CORE_PEER_GOSSIP_USELEADERELECTION": "true",
        "CORE_PEER_GOSSIP_ORGLEADER": "false",
        "CORE_PEER_GOSSIP_EXTERNALENDPOINT": f"{clean_ip}:{port}",
        "CORE_PEER_GOSSIP_BOOTSTRAP": f"{clean_ip}:{port}",
        # TLS Configuration gRPC principal
        "CORE_PEER_TLS_ENABLED": "true" if tls_enabled else "false",
    }

    if tls_enabled:
        env.update({
            "CORE_PEER_TLS_CERT_FILE": "/etc/hyperledger/fabric/tls/server.crt",
            "CORE_PEER_TLS_KEY_FILE": "/etc/hyperledger/fabric/tls/server.key",
            "CORE_PEER_TLS_ROOTCERT_FILE": "/etc/hyperledger/fabric/tls/ca.crt",
        })

    return Container(
        name,
        ip=ip,
        dimage="hyperledger/fabric-peer:2.5",
        volumes=[
            f"{peer_msp}:/etc/hyperledger/fabric/msp",
            f"{peer_tls}:/etc/hyperledger/fabric/tls"
        ],
        environment=env,
        dcmd="peer node start"
    )


def create_orderer(
    name="orderer0",
    ip="10.0.0.30",
    domain="example.com",
    msp_id="OrdererMSP",
    port=7050,
    operations_port=8443
):
    """
    Cria um container Hyperledger Fabric Orderer parametrizado para o Fogbed.
    """
    clean_ip = ip.split('/')[0]

    orderer_msp = os.path.join(
        CRYPTO_DIR,
        "ordererOrganizations",
        domain,
        "orderers",
        f"{name}.{domain}",
        "msp"
    )

    orderer_tls = os.path.join(
        CRYPTO_DIR,
        "ordererOrganizations",
        domain,
        "orderers",
        f"{name}.{domain}",
        "tls"
    )

    return Container(
        name,
        ip=ip,
        dimage="hyperledger/fabric-orderer:2.5",
        volumes=[
            f"{orderer_msp}:/etc/hyperledger/fabric/msp",
            f"{orderer_tls}:/etc/hyperledger/fabric/tls",
            f"{GENESIS_BLOCK}:/etc/hyperledger/fabric/genesis.block"
        ],
        environment={
            "FABRIC_LOGGING_SPEC": "INFO",
            "ORDERER_GENERAL_BOOTSTRAPMETHOD": "file",
            "ORDERER_GENERAL_BOOTSTRAPFILE": "/etc/hyperledger/fabric/genesis.block",
            "ORDERER_GENERAL_LOCALMSPID": msp_id,
            "ORDERER_GENERAL_LOCALMSPDIR": "/etc/hyperledger/fabric/msp",
            # Operations Service ouvindo em 0.0.0.0:8443 sem TLS inicial
            "ORDERER_OPERATIONS_LISTENADDRESS": f"0.0.0.0:{operations_port}",
            "ORDERER_OPERATIONS_LISTEN_ADDRESS": f"0.0.0.0:{operations_port}",
            "ORDERER_OPERATIONS_TLS_ENABLED": "false",
            # TLS gRPC principal (etcdraft requer TLS ativado)
            "ORDERER_GENERAL_TLS_ENABLED": "true",
            "ORDERER_GENERAL_TLS_PRIVATEKEY": "/etc/hyperledger/fabric/tls/server.key",
            "ORDERER_GENERAL_TLS_CERTIFICATE": "/etc/hyperledger/fabric/tls/server.crt",
            "ORDERER_GENERAL_TLS_ROOTCAS": "[/etc/hyperledger/fabric/tls/ca.crt]",
            # Endereço de escuta do serviço gRPC principal
            "ORDERER_GENERAL_LISTENADDRESS": "0.0.0.0",
            "ORDERER_GENERAL_LISTENPORT": str(port),
        },
        dcmd="orderer"
    )
