#!/usr/bin/env python3

"""
common.py

Funções compartilhadas pelos experimentos do Lab04.

Responsabilidades:
- preparar ambiente Fabric;
- gerar artefatos automaticamente;
- criar containers Hyperledger Fabric;
- padronizar saída dos experimentos;
- centralizar funções reutilizadas pelos laboratórios.
"""


import os
import subprocess

from fogbed import Container



ROOT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


SCRIPTS_DIR = os.path.join(
    ROOT_DIR,
    "scripts"
)


CRYPTO_DIR = os.path.join(
    ROOT_DIR,
    "crypto-material"
)


CHANNEL_ARTIFACTS = os.path.join(
    ROOT_DIR,
    "channel-artifacts"
)


GENESIS_BLOCK = os.path.join(
    CHANNEL_ARTIFACTS,
    "genesis.block"
)


ARTIFACT_SCRIPT = os.path.join(
    SCRIPTS_DIR,
    "generate-artifacts.sh"
)


CLEAN_SCRIPT = os.path.join(
    SCRIPTS_DIR,
    "clean.sh"
)



# ---------------------------------------------------------
# Ambiente
# ---------------------------------------------------------


def prepare_environment():
    """
    Verifica se os artefatos do Hyperledger Fabric existem.

    Caso o bloco gênesis não exista, executa o script responsável
    pela geração dos certificados e artefatos necessários.

    Raises:
        subprocess.CalledProcessError:
            Caso o script de geração falhe.
    """

    if os.path.exists(GENESIS_BLOCK):

        print(
            "\n[INFO] Artefatos encontrados."
        )

        return


    print(
        "\n[INFO] Artefatos inexistentes."
    )

    print(
        "[INFO] Gerando ambiente...\n"
    )

    subprocess.run(
        [ARTIFACT_SCRIPT],
        check=True
    )



def cleanup():
    """
    Executa o script de limpeza do laboratório.

    Remove arquivos temporários ou artefatos gerados
    durante a execução dos experimentos.
    """

    subprocess.run(
        [CLEAN_SCRIPT],
        check=False
    )



# ---------------------------------------------------------
# Interface
# ---------------------------------------------------------


def banner(title):
    """
    Exibe um título formatado no terminal.

    Args:
        title (str):
            Texto que será exibido no banner.
    """

    print()

    print(
        "=" * 60
    )

    print(
        title.center(60)
    )

    print(
        "=" * 60
    )



def wait_for_user():
    """
    Mantém o experimento ativo aguardando interação do usuário.

    Permite realizar inspeções externas utilizando Docker,
    Podman ou comandos de diagnóstico.
    """

    print()

    print(
        "Agora você pode executar:"
    )

    print()

    print(
        "docker ps"
    )

    print(
        "docker logs <container>"
    )

    print(
        "docker exec -it <container> bash"
    )

    print()

    print(
        "podman ps"
    )

    print(
        "podman logs <container>"
    )

    print(
        "podman exec -it <container> bash"
    )

    print()

    input(
        "Pressione ENTER para finalizar..."
    )



def ask_cleanup():
    """
    Pergunta ao usuário se deseja executar a limpeza.

    Returns:
        bool:
            True caso o usuário confirme a execução do clean.sh.
    """

    answer = input(
        "\nExecutar clean.sh? [y/N]: "
    ).strip().lower()


    return answer in (
        "y",
        "yes",
        "s",
        "sim"
    )



# ---------------------------------------------------------
# Containers Fabric
# ---------------------------------------------------------


def create_orderer(
    name="orderer0",
    ip="10.0.0.30"
):
    """
    Cria um container Hyperledger Fabric Orderer.

    Este container executa o serviço responsável pelo
    ordenamento das transações da rede Fabric.

    Para este laboratório é utilizado:

    - imagem oficial do Hyperledger Fabric 2.5;
    - consenso etcdraft;
    - bloco gênesis previamente gerado;
    - material criptográfico produzido pelo cryptogen.
    """

    # ==========================================================
    # Diretório MSP do Orderer
    #
    # Contém:
    #
    # - certificado da organização;
    # - certificados dos administradores;
    # - CA da organização.
    #
    # O Fabric utiliza esse diretório para identificar
    # o Orderer dentro da rede.
    # ==========================================================

    orderer_msp = os.path.join(
        CRYPTO_DIR,
        "ordererOrganizations",
        "example.com",
        "orderers",
        "orderer0.example.com",
        "msp"
    )


    # ==========================================================
    # Diretório TLS do Orderer
    #
    # Contém:
    #
    # - server.crt
    # - server.key
    # - ca.crt
    #
    # Esse material é utilizado nas conexões seguras
    # entre Orderers e Peers.
    # ==========================================================

    orderer_tls = os.path.join(
        CRYPTO_DIR,
        "ordererOrganizations",
        "example.com",
        "orderers",
        "orderer0.example.com",
        "tls"
    )


    return Container(

        # ------------------------------------------------------
        # Nome do container Docker.
        #
        # Também será utilizado como hostname.
        # ------------------------------------------------------

        name,

        # ------------------------------------------------------
        # Endereço IP dentro da topologia Fogbed.
        # ------------------------------------------------------

        ip=ip,

        # ------------------------------------------------------
        # Imagem oficial do Orderer Fabric.
        # ------------------------------------------------------

        dimage="hyperledger/fabric-orderer:2.5",

        # ------------------------------------------------------
        # Montagem de volumes.
        #
        # Formato esperado pelo Fogbed:
        #
        # host_path:container_path
        #
        # Dessa forma o container consegue acessar
        # os arquivos existentes no host.
        # ------------------------------------------------------

        volumes=[

            # Material MSP do Orderer

            f"{orderer_msp}:/etc/hyperledger/fabric/msp",

            # Material TLS

            f"{orderer_tls}:/etc/hyperledger/fabric/tls",

            # Bloco gênesis

            f"{GENESIS_BLOCK}:/etc/hyperledger/fabric/genesis.block"

        ],

        # ------------------------------------------------------
        # Variáveis de ambiente do Orderer.
        #
        # Equivalem às configurações presentes
        # no arquivo orderer.yaml.
        # ------------------------------------------------------

        environment={

            # Nível de log

            "FABRIC_LOGGING_SPEC":
                "INFO",

            # O bloco gênesis será carregado a partir
            # de um arquivo.

            "ORDERER_GENERAL_BOOTSTRAPMETHOD":
                "file",

            # Caminho do bloco gênesis dentro
            # do container.

            "ORDERER_GENERAL_BOOTSTRAPFILE":
                "/etc/hyperledger/fabric/genesis.block",

            # Nome do MSP do Orderer.

            "ORDERER_GENERAL_LOCALMSPID":
                "OrdererMSP",

            # Diretório onde está o MSP.

            "ORDERER_GENERAL_LOCALMSPDIR":
                "/etc/hyperledger/fabric/msp",

            # ==================================================
            # TLS
            #
            # Como estamos utilizando etcdraft,
            # TLS é obrigatório.
            # ==================================================

            "ORDERER_GENERAL_TLS_ENABLED":
                "true",

            "ORDERER_GENERAL_TLS_PRIVATEKEY":
                "/etc/hyperledger/fabric/tls/server.key",

            "ORDERER_GENERAL_TLS_CERTIFICATE":
                "/etc/hyperledger/fabric/tls/server.crt",

            "ORDERER_GENERAL_TLS_ROOTCAS":
                "[/etc/hyperledger/fabric/tls/ca.crt]",

            # ==================================================
            # Endereço onde o serviço ficará escutando.
            # ==================================================

            "ORDERER_GENERAL_LISTENADDRESS":
                "0.0.0.0",

            "ORDERER_GENERAL_LISTENPORT":
                "7050"

        },

        # ------------------------------------------------------
        # Processo principal executado pelo container.
        #
        # Equivale ao comando:
        #
        # orderer
        # ------------------------------------------------------

        dcmd="orderer"

    )

def create_peer(
    name="peer0",
    ip="10.0.0.20"
):
    """
    Cria um container Hyperledger Fabric Peer.

    Args:
        name (str):
            Nome do peer.
        ip (str):
            Endereço IP do peer.

    Returns:
        Container:
            Instância configurada do Peer.
    """

    return Container(

        name,

        ip=ip,

        dimage="hyperledger/fabric-peer:2.5",

        volumes=[

            (

                os.path.join(
                    CRYPTO_DIR,
                    "peerOrganizations",
                    "org1.example.com",
                    "peers",
                    "peer0.org1.example.com",
                    "msp"
                ),

                "/etc/hyperledger/fabric/msp"

            ),

            (

                os.path.join(
                    CRYPTO_DIR,
                    "peerOrganizations",
                    "org1.example.com",
                    "peers",
                    "peer0.org1.example.com",
                    "tls"
                ),

                "/etc/hyperledger/fabric/tls"

            )

        ],

        environment={

            "FABRIC_LOGGING_SPEC":
            "INFO",

            "CORE_PEER_ID":
            name,

            "CORE_PEER_ADDRESS":
            f"{ip}:7051",

            "CORE_PEER_LOCALMSPID":
            "Org1MSP",

            "CORE_PEER_MSPCONFIGPATH":
            "/etc/hyperledger/fabric/msp",

            "CORE_PEER_TLS_ENABLED":
            "false"

        },

        dcmd="peer node start"
    )



# ---------------------------------------------------------
# Diagnóstico
# ---------------------------------------------------------


def show_container_details(
    container,
    version_command
):
    """
    Exibe informações de diagnóstico de um container Fabric.

    Args:
        container:
            Container Fogbed a ser analisado.

        version_command (str):
            Comando usado para verificar a versão do serviço.
    """

    print(
        "\nHostname"
    )

    print(
        "-" * 40
    )

    print(
        container.cmd(
            "hostname"
        )
    )


    print(
        "\nVersão"
    )

    print(
        "-" * 40
    )

    print(
        container.cmd(
            version_command
        )
    )


    print(
        "\nProcessos"
    )

    print(
        "-" * 40
    )

    print(
        container.cmd(
            "ps aux"
        )
    )


    print(
        "\nPortas abertas"
    )

    print(
        "-" * 40
    )

    print(
        container.cmd(
            "ss -ltn || netstat -tln"
        )
    )
    