#!/usr/bin/env python3

"""
experiment01_orderer_with_genesis.py

Primeiro experimento do Lab04.

Objetivo:
- iniciar um Orderer Hyperledger Fabric;
- utilizar certificados gerados previamente;
- utilizar o bloco gênesis criado pelo configtxgen;
- validar a inicialização do serviço dentro do Fogbed.

O experimento mantém o ambiente ativo para inspeção manual.
"""

from fogbed import (
    FogbedExperiment,
    setLogLevel
)


from common import (
    prepare_environment,
    cleanup,
    create_orderer,
    banner,
    show_container_details,
    wait_for_user,
    ask_cleanup
)



setLogLevel("info")



# ---------------------------------------------------------
# Preparação do ambiente
# ---------------------------------------------------------

prepare_environment()



# ---------------------------------------------------------
# Criação da topologia Fogbed
# ---------------------------------------------------------

exp = FogbedExperiment()


cloud = exp.add_virtual_instance(
    "cloud"
)


fog = exp.add_virtual_instance(
    "fog"
)



# ---------------------------------------------------------
# Criação do Orderer Hyperledger Fabric
# ---------------------------------------------------------

orderer = create_orderer()



# Associando o container ao nó Fog

exp.add_docker(
    orderer,
    fog
)



# Criando comunicação entre os nós virtuais

exp.add_link(
    cloud,
    fog
)



# ---------------------------------------------------------
# Execução do experimento
# ---------------------------------------------------------

try:

    exp.start()


    banner(
        "ORDERER EXECUTANDO COM SUCESSO"
    )


    show_container_details(
        orderer,
        "orderer version"
    )


    banner(
        "AMBIENTE EM EXECUÇÃO"
    )


    wait_for_user()



except Exception as ex:


    banner(
        "ERRO DURANTE EXECUÇÃO"
    )


    print(ex)



finally:


    # Finaliza a topologia Fogbed

    try:

        exp.stop()

    except Exception:

        pass



    # Limpeza opcional

    if ask_cleanup():

        cleanup()


    else:

        print(
            "\n[INFO] Limpeza ignorada."
        )

        print(
            "[INFO] Os artefatos permanecem disponíveis."
        )