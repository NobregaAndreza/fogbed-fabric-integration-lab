- Realizando testes com o test-network da versão mais recente do hyperledger para analisar possíveis mudanças.


# Environment Notes

## Hyperledger Fabric 2.5 - Compatibility Issue

During the initial setup of the Hyperledger Fabric 2.5 test network, the Fabric binaries were downloaded successfully through `install-fabric.sh`, however the `peer` binary could not be executed.

### Current environment

```bash
Ubuntu 20.04.6 LTS (Focal Fossa)
```

GLIBC version:

```bash
ldd --version

glibc 2.31
```

### Error found

When executing:

```bash
./bin/peer version
```

The following error was returned:

```text
./bin/peer: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.34' not found
./bin/peer: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.32' not found
```

### Root cause

The Hyperledger Fabric 2.5 binaries downloaded from the official installation script were compiled requiring a newer version of GLIBC.

Current system:

```
Ubuntu 20.04
GLIBC 2.31
```

Required by Fabric binary:

```
GLIBC >= 2.34
```

Therefore, the issue is not related to:

- `fabric-samples`;
- `network.sh`;
- Docker configuration;
- Fabric installation script.

The binaries exist correctly, but cannot execute due to operating system compatibility.

---

# Decision

Upgrade the operating system to a newer Ubuntu version before continuing the experiments.

Target environment:

```
Ubuntu 22.04 LTS or newer
```

Reason:

- Better compatibility with Hyperledger Fabric 2.5;
- More recent Docker ecosystem;
- Fewer compatibility issues with Fogbed/Containernet dependencies;
- Environment closer to current software stacks.

---

# Current project setup

The repository will not version external dependencies directly.

Examples:

- Hyperledger Fabric binaries;
- fabric-samples;
- Fogbed source code;
- Docker images;
- Generated certificates and artifacts.

These components will be installed through automation scripts in the future.

Expected structure:

```
scripts/
├── install-fabric.sh
├── install-fogbed.sh
└── setup-environment.sh

third_party/
└── external dependencies
```

---

# Next steps after OS update

1. Install base dependencies:
   - Docker
   - Git
   - Python
   - Required development tools

2. Reinstall Hyperledger Fabric:

```bash
./install-fabric.sh \
  --fabric-version 2.5.16 \
  --ca-version 1.5.17 \
  binary docker
```

3. Validate binaries:

```bash
peer version
configtxgen --version
```

4. Start Fabric test network:

```bash
cd third_party/fabric-samples/test-network

./network.sh up
```

5. Continue experiments:
   - Validate Fabric standalone;
   - Understand test-network architecture;
   - Begin integration with Fogbed.