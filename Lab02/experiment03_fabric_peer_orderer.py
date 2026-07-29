from fogbed import (
    FogbedExperiment,
    Container,
    setLogLevel
)


setLogLevel('info')


exp = FogbedExperiment()


# Nós virtuais

cloud = exp.add_virtual_instance('cloud')

fog_peer = exp.add_virtual_instance('fog-peer')

fog_orderer = exp.add_virtual_instance('fog-orderer')


# Peer Fabric

peer = Container(
    'peer0',
    ip='10.0.0.20',
    dimage='hyperledger/fabric-peer:2.5'
)


# Orderer Fabric

orderer = Container(
    'orderer0',
    ip='10.0.0.30',
    dimage='hyperledger/fabric-orderer:2.5'
)


# Adicionando containers

exp.add_docker(
    peer,
    fog_peer
)


exp.add_docker(
    orderer,
    fog_orderer
)


# Links da infraestrutura

exp.add_link(
    cloud,
    fog_peer
)


exp.add_link(
    cloud,
    fog_orderer
)



try:

    exp.start()


    print("\n=== Peer iniciado ===")
    print(peer.cmd("hostname"))


    print("\n=== Peer version ===")
    print(peer.cmd("peer version"))


    print("\n=== Orderer iniciado ===")
    print(orderer.cmd("hostname"))


    print("\n=== Orderer version ===")
    print(orderer.cmd("orderer version"))


    print("\n=== Containers ativos ===")
    print(peer.cmd("ps aux"))
    print(orderer.cmd("ps aux"))


    print("\n=== Ambiente mantido ativo ===")
    print("Pressione ENTER para finalizar")

    input()


except Exception as ex:

    print("\nErro:")
    print(ex)


finally:

    exp.stop()