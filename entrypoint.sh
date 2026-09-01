#!/usr/bin/env bash
# Boots the whole container: bitcoind -> setup_chain.py (always, see
# FORCE_SETUP) -> uvicorn -> caddy. Runs as PID 1.
#
# All three long-running processes are backgrounded and then raced with
# `wait -n`: if any one of them dies, this script exits (propagating that
# exit code), which kills the container. That's deliberate, not a bug --
# there's no per-process supervisor restarting bitcoind alone, because a
# half-alive container (say, caddy up but bitcoind gone) is worse than no
# container. The orchestrator's restart-on-failure policy, driven by
# /health, is what brings it back -- and because boot is stateless
# (fresh datadir, FORCE_SETUP re-mines every time), a full container
# restart is cheap and correct, not just a fallback.
set -euo pipefail

DATADIR=/data/bitcoin-regtest
mkdir -p "$DATADIR"
CONF="/app/regtest.conf"

# regtest.conf deliberately carries no rpcuser/rpcpassword (see its own
# comment) -- a committed credential looks careless even for a
# loopback-only node. Generate one fresh every boot unless the operator
# supplied their own via env (e.g. a compose secret), and export it so
# node.py -- which already reads these same var names -- picks it up for
# every RPC call uvicorn makes.
export BTC_RPC_USER="${BTC_RPC_USER:-btcplayground}"
if [ -z "${BTC_RPC_PASSWORD:-}" ]; then
    export BTC_RPC_PASSWORD="$(head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)"
    echo "entrypoint: generated a random RPC password (set BTC_RPC_PASSWORD to supply your own)."
fi
AUTH=(-rpcuser="$BTC_RPC_USER" -rpcpassword="$BTC_RPC_PASSWORD")

cleanup() {
    echo "entrypoint: shutting down..."
    kill -TERM "$BITCOIND_PID" "$UVICORN_PID" "$CADDY_PID" 2>/dev/null || true
    wait || true
    exit 0
}
trap cleanup SIGTERM SIGINT

bitcoind -regtest -conf="$CONF" -datadir="$DATADIR" "${AUTH[@]}" &
BITCOIND_PID=$!

echo "entrypoint: waiting for bitcoind RPC..."
ready=0
for i in $(seq 1 60); do
    if bitcoin-cli -regtest -conf="$CONF" -datadir="$DATADIR" "${AUTH[@]}" getblockchaininfo >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 1
done
if [ "$ready" -ne 1 ]; then
    echo "entrypoint: bitcoind did not become ready in time" >&2
    exit 1
fi
echo "entrypoint: RPC is up."

cd /app/backend
python3 setup_chain.py
cd /app

# Bound to localhost only -- caddy is the sole thing that reaches
# uvicorn; it is never exposed on the container's own external port.
# BTC_RPC_USER/BTC_RPC_PASSWORD are already exported above, so node.py
# picks them up without any further plumbing.
uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

caddy run --config /app/Caddyfile --adapter caddyfile &
CADDY_PID=$!

wait -n "$BITCOIND_PID" "$UVICORN_PID" "$CADDY_PID"
exit_code=$?
echo "entrypoint: a supervised process exited (code $exit_code), stopping container."
exit "$exit_code"
