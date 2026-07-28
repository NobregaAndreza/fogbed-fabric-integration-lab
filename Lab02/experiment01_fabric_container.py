from fogbed import (
    FogbedExperiment,
    Container,
    setLogLevel
)

# Nível de log
setLogLevel('info')

#TODO: estou configurando novamente o ambiente do fogbed para realização das integrações
# Criando experimento Fogbedls

exp = FogbedExperiment()


# Criando uma infraestrutura virtual simples
cloud = exp.add_virtual_instance('cloud')
fog = exp.add_virtual_instance('fog')


# Container com ferramentas do Hyperledger Fabric
fabric_tools = Container(
    'fabric-tools',
    ip='10.0.0.10',
    dimage='hyperledger/fabric-tools:2.5'
)


# Associando container ao nó Fog
exp.add_docker(
    fabric_tools,
    fog
)


# Conexão entre nós virtuais
exp.add_link(
    cloud,
    fog
)


try:
    exp.start()

    print("\n=== Container iniciado ===")
    print(
        fabric_tools.cmd(
            "hostname"
        )
    )

    print("\n=== Validando Hyperledger Fabric ===")
    print(
        fabric_tools.cmd(
            "peer version"
        )
    )

    print("\n=== Teste de conectividade ===")
    print(
        fabric_tools.cmd(
            "ip addr"
        )
    )


except OSError as ex:
    print("Erro:")
    print(ex)


finally:
    exp.stop()