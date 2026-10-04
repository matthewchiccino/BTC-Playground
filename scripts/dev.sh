#!/usr/bin/env bash
# One-command local dev: node (if not already up) -> backend -> frontend.
# Ctrl-C stops the backend and frontend; the node is left running on purpose
# (it is slow to re-mine and the chain is frozen) -- stop it with `make node-stop`.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python

if ! bitcoin-cli -regtest -conf="$(pwd)/regtest.conf" -datadir="$(pwd)/.bitcoin-regtest" \
     -rpcuser="${BTC_RPC_USER:-btcplayground}" -rpcpassword="${BTC_RPC_PASSWORD:-btcplayground}" \
     getblockchaininfo >/dev/null 2>&1; then
  echo "dev: node is not running -- starting it"
  ./scripts/start_node.sh
fi

# Idempotent: exits immediately if fixtures.json already exists.
(cd backend && "../$PY" setup_chain.py)

pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; wait 2>/dev/null || true; }
trap cleanup EXIT INT TERM

"$PY" -m uvicorn main:app --app-dir backend --port 8000 &
pids+=($!)
npm run dev --prefix frontend -- --host &
pids+=($!)

echo "dev: backend http://localhost:8000 | frontend http://localhost:5173 (Ctrl-C to stop; node keeps running)"
wait -n "${pids[@]}"
