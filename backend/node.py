"""Thin JSON-RPC wrapper around a single regtest bitcoind instance."""
import os
from requests.auth import HTTPBasicAuth
import requests

RPC_URL = os.environ.get("BTC_RPC_URL", "http://127.0.0.1:18443")
RPC_USER = os.environ.get("BTC_RPC_USER", "btcplayground")
RPC_PASSWORD = os.environ.get("BTC_RPC_PASSWORD", "btcplayground")
RPC_WALLET = os.environ.get("BTC_RPC_WALLET", "playground")

_auth = HTTPBasicAuth(RPC_USER, RPC_PASSWORD)


def rpc(method: str, params: list | None = None, wallet: str | None = RPC_WALLET):
    url = f"{RPC_URL}/wallet/{wallet}" if wallet else RPC_URL
    resp = requests.post(
        url,
        json={"jsonrpc": "1.0", "id": "btcplayground", "method": method, "params": params or []},
        auth=_auth,
        timeout=10,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("error"):
        raise RuntimeError(f"RPC error in {method}: {body['error']}")
    return body["result"]
