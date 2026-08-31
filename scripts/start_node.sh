#!/usr/bin/env bash
# Starts the frozen regtest node for My BTC Playground.
set -euo pipefail
cd "$(dirname "$0")/.."

DATADIR="$(pwd)/.bitcoin-regtest"
mkdir -p "$DATADIR"

bitcoind -regtest -conf="$(pwd)/regtest.conf" -datadir="$DATADIR" -daemon -debuglogfile="$(pwd)/node_debug.log"

echo "bitcoind starting with datadir=$DATADIR"
echo "waiting for RPC..."
for i in $(seq 1 30); do
  if bitcoin-cli -regtest -conf="$(pwd)/regtest.conf" -datadir="$DATADIR" getblockchaininfo >/dev/null 2>&1; then
    echo "RPC is up."
    # bitcoind doesn't auto-load a previously created wallet on restart --
    # load it now so the backend's wallet-scoped RPCs don't 500.
    bitcoin-cli -regtest -conf="$(pwd)/regtest.conf" -datadir="$DATADIR" loadwallet playground >/dev/null 2>&1 || true
    exit 0
  fi
  sleep 1
done

echo "bitcoind did not become ready in time" >&2
exit 1
