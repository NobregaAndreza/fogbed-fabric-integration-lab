from fogbed import (
    FogbedExperiment,
    Container,
    setLogLevel
)

import time


# Log do Fogbed
setLogLevel('info')


# Criando experimento
exp = FogbedExperiment()


# Criando infraestrutura virtual
fog = exp.add_virtual_instance('fog')


# =========================
# Hyperledger Fabric Peer
# =========================

peer = Container(
    'peer0',
    ip='10.0.0.20',
    dimage='hyperledger/fabric-peer:2.5',
    environment={
        'CORE_PEER_ID': 'peer0',
        'CORE_PEER_ADDRESS': 'peer0:7051',
        'CORE_PEER_LISTENADDRESS': '0.0.0.0:7051',
        'CORE_PEER_LOCALMSPID': 'Org1MSP',
        'FABRIC_LOGGING_SPEC': 'INFO'
    },
    ports=[
        7051
    ],
    dcmd='peer node start'
)


# =========================
# Hyperledger Fabric Orderer
# =========================

orderer = Container(
    'orderer0',
    ip='10.0.0.30',
    dimage='hyperledger/fabric-orderer:2.5',
    environment={
        'ORDERER_GENERAL_LISTENADDRESS': '0.0.0.0',
        'ORDERER_GENERAL_LISTENPORT': '7050',
        'ORDERER_GENERAL_LOCALMSPID': 'OrdererMSP',
        'FABRIC_LOGGING_SPEC': 'INFO'
    },
    ports=[
        7050
    ],
    dcmd='orderer'
)


# Adicionando containers no nó Fog
exp.add_docker(
    peer,
    fog
)


exp.add_docker(
    orderer,
    fog
)


# Criando conexão virtual
exp.add_link(
    fog,
    fog
)


try:

    exp.start()


    print("\n=== Peer iniciado ===")
    print(peer.cmd("hostname"))


    print("\n=== Orderer iniciado ===")
    print(orderer.cmd("hostname"))


    print("\n=== Processo Peer ===")
    print(
        peer.cmd(
            "ps aux"
        )
    )


    print("\n=== Processo Orderer ===")
    print(
        orderer.cmd(
            "ps aux"
        )
    )


    print("\n=== Portas Peer ===")
    print(
        peer.cmd(
            "netstat -tulnp || ss -tulnp"
        )
    )


    print("\n=== Portas Orderer ===")
    print(
        orderer.cmd(
            "netstat -tulnp || ss -tulnp"
        )
    )


    print("\n=== Ambiente mantido ativo ===")
    input(
        "Pressione ENTER para finalizar\n"
    )


except Exception as ex:

    print("\nErro:")
    print(ex)


finally:

    exp.stop()