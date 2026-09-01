#!/usr/bin/env bash
# Starts the frozen regtest node for My BTC Playground.
set -euo pipefail
cd "$(dirname "$0")/.."

DATADIR="$(pwd)/.bitcoin-regtest"
mkdir -p "$DATADIR"

# Same env vars node.py reads, same defaults -- regtest.conf deliberately
# doesn't hardcode a credential (see its own comment).
BTC_RPC_USER="${BTC_RPC_USER:-btcplayground}"
BTC_RPC_PASSWORD="${BTC_RPC_PASSWORD:-btcplayground}"
AUTH=(-rpcuser="$BTC_RPC_USER" -rpcpassword="$BTC_RPC_PASSWORD")

bitcoind -regtest -conf="$(pwd)/regtest.conf" -datadir="$DATADIR" "${AUTH[@]}" \
  -daemon -debuglogfile="$(pwd)/node_debug.log"

echo "bitcoind starting with datadir=$DATADIR"
echo "waiting for RPC..."
for i in $(seq 1 30); do
  if bitcoin-cli -regtest -conf="$(pwd)/regtest.conf" -datadir="$DATADIR" "${AUTH[@]}" getblockchaininfo >/dev/null 2>&1; then
    echo "RPC is up."
    # bitcoind doesn't auto-load a previously created wallet on restart --
    # load it now so the backend's wallet-scoped RPCs don't 500.
    bitcoin-cli -regtest -conf="$(pwd)/regtest.conf" -datadir="$DATADIR" "${AUTH[@]}" loadwallet playground >/dev/null 2>&1 || true
    exit 0
  fi
  sleep 1
done

echo "bitcoind did not become ready in time" >&2
exit 1
