"""Recent mainnet blocks, for the chain drawn on the landing page visualization.

This is deliberately *not* our node. The regtest node is frozen (ADR 0002) so
scenario boundaries stay exact; this is display-only context from a public
Esplora explorer, labeled as such in the UI. Nothing here feeds a scenario.

Proxied through the backend rather than fetched by the browser so visitors'
IPs never reach a third party, and one shared cache means upstream sees at
most one request per TTL no matter how many people have the page open.
"""
import threading
import time

import requests

SOURCE_NAME = "blockstream.info"
BLOCKS_URL = "https://blockstream.info/api/blocks"
TTL_SECONDS = 30
TIMEOUT_SECONDS = 4
FIELDS = ("height", "id", "timestamp", "tx_count", "size", "weight")

_cache: dict = {"blocks": None, "fetched_at": 0.0}
_lock = threading.Lock()


def _fetch() -> list[dict]:
    res = requests.get(BLOCKS_URL, timeout=TIMEOUT_SECONDS)
    res.raise_for_status()
    return [{k: b[k] for k in FIELDS} for b in res.json()]


def recent_blocks() -> dict:
    """Newest first. Serves the last good copy (marked stale) if upstream
    fails, so a flaky explorer degrades the strip instead of blanking it.
    Raises only when there has never been a successful fetch."""
    with _lock:
        now = time.time()
        if _cache["blocks"] is not None and now - _cache["fetched_at"] < TTL_SECONDS:
            return _response(stale=False)
        try:
            _cache["blocks"] = _fetch()
            _cache["fetched_at"] = now
            return _response(stale=False)
        except Exception:
            if _cache["blocks"] is None:
                raise
            return _response(stale=True)


def _response(stale: bool) -> dict:
    return {
        "network": "mainnet",
        "source": SOURCE_NAME,
        "fetched_at": int(_cache["fetched_at"]),
        "stale": stale,
        "blocks": _cache["blocks"],
    }
