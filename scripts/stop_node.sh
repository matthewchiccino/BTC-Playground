#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
BTC_RPC_USER="${BTC_RPC_USER:-btcplayground}"
BTC_RPC_PASSWORD="${BTC_RPC_PASSWORD:-btcplayground}"
bitcoin-cli -regtest -conf="$(pwd)/regtest.conf" -datadir="$(pwd)/.bitcoin-regtest" \
  -rpcuser="$BTC_RPC_USER" -rpcpassword="$BTC_RPC_PASSWORD" stop
