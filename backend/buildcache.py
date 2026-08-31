"""Short-lived server-side memory of what /build actually produced.

/submit used to take payload_hex straight from the client and feed it into
the node -- harmless against state (proposal mode / testmempoolaccept never
mutate anything) but still an open door for someone to lob arbitrary
malformed bytes at the shared node. Now /submit only ever validates a payload
this process built itself, looked up by an opaque token. No database: this
is deliberately just memory that expires, matching the "no persistence"
constraint -- it's a cache, not a store.
"""
import secrets
import threading
import time

TTL_SECONDS = 120
MAX_ENTRIES = 500

_cache: dict[str, dict] = {}
_lock = threading.Lock()


def _prune_locked():
    now = time.time()
    expired = [k for k, v in _cache.items() if v["expires_at"] < now]
    for k in expired:
        del _cache[k]
    if len(_cache) > MAX_ENTRIES:
        overflow = len(_cache) - MAX_ENTRIES
        oldest = sorted(_cache.items(), key=lambda kv: kv[1]["expires_at"])[:overflow]
        for k, _ in oldest:
            del _cache[k]


def store(scenario_id: str, payload_hex: str) -> str:
    build_id = secrets.token_urlsafe(16)
    with _lock:
        _prune_locked()
        _cache[build_id] = {
            "scenario_id": scenario_id,
            "payload_hex": payload_hex,
            "expires_at": time.time() + TTL_SECONDS,
        }
    return build_id


def get(build_id: str) -> dict | None:
    with _lock:
        entry = _cache.get(build_id)
        if entry is None:
            return None
        if entry["expires_at"] < time.time():
            del _cache[build_id]
            return None
        return entry
