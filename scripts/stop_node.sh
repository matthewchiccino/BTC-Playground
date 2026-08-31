#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bitcoin-cli -regtest -conf="$(pwd)/regtest.conf" -datadir="$(pwd)/.bitcoin-regtest" stop
