from fogbed import (
    FogbedExperiment,
    Container,
    setLogLevel
)


# Nível de log do Fogbed
setLogLevel('info')


# Criando experimento Fogbed
exp = FogbedExperiment()


# Criando nó virtual Fog
fog = exp.add_virtual_instance('fog')


# Container Hyperledger Fabric Peer
peer = Container(
    'peer0',
    ip='10.0.0.20',
    dimage='hyperledger/fabric-peer:2.5'
)


# Associando peer ao nó Fog
exp.add_docker(
    peer,
    fog
)


try:

    exp.start()


    print("\n=== Container Peer iniciado ===")

    print(
        peer.cmd(
            "hostname"
        )
    )


    print("\n=== Validando Hyperledger Fabric Peer ===")

    print(
        peer.cmd(
            "peer version"
        )
    )


    print("\n=== Processos ativos ===")

    print(
        peer.cmd(
            "ps aux"
        )
    )


except Exception as ex:

    print("\nErro:")
    print(ex)


finally:

    exp.stop()