#!/usr/bin/env bash

# ============================================================
# Fabric Environment Resolution Script (Lab06)
#
# Reaproveita a resolução dinâmica do Lab05 e mantém o mesmo padrão
# para localizar `cryptogen` e `configtxgen` com suporte a sudo.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$LAB_ROOT/.." && pwd)"

if [ -n "${FABRIC_BIN:-}" ] && { [ -f "${FABRIC_BIN}/cryptogen" ] || [ -f "${FABRIC_BIN}/configtxgen" ]; }; then
    FOUND_BIN="$FABRIC_BIN"
elif [ -f "${REPO_ROOT}/third_party/fabric-samples/bin/cryptogen" ] || [ -f "${REPO_ROOT}/third_party/fabric-samples/bin/configtxgen" ]; then
    FOUND_BIN="$(cd "${REPO_ROOT}/third_party/fabric-samples/bin" && pwd)"
elif command -v cryptogen >/dev/null 2>&1; then
    FOUND_BIN="$(dirname "$(command -v cryptogen)")"
elif command -v configtxgen >/dev/null 2>&1; then
    FOUND_BIN="$(dirname "$(command -v configtxgen)")"
elif [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != "root" ]; then
    USER_HOME="$(eval echo "~${SUDO_USER}")"
    if [ -f "${USER_HOME}/Desktop/fabric-samples/bin/cryptogen" ]; then
        FOUND_BIN="${USER_HOME}/Desktop/fabric-samples/bin"
    elif [ -f "${USER_HOME}/fabric-samples/bin/cryptogen" ]; then
        FOUND_BIN="${USER_HOME}/fabric-samples/bin"
    fi
fi

if [ -n "${FOUND_BIN:-}" ]; then
    export FABRIC_BIN="$FOUND_BIN"
    case ":$PATH:" in
        *":$FABRIC_BIN:"*) ;;
        *) export PATH="$FABRIC_BIN:$PATH" ;;
    esac
else
    echo "[ERRO] Binários do Hyperledger Fabric (cryptogen / configtxgen) não foram encontrados." >&2
    return 1 2>/dev/null || exit 1
fi
