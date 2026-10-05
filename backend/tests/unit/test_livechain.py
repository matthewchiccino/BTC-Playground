"""The mainnet strip's proxy: caching, stale fallback, and the API surface,
with the explorer stubbed out."""
import pytest
from fastapi.testclient import TestClient

import livechain
import main

BLOCK = {"height": 900000, "id": "00" * 32, "timestamp": 1, "tx_count": 2, "size": 3, "weight": 4}


@pytest.fixture(autouse=True)
def clean_state():
    livechain._cache.update(blocks=None, fetched_at=0.0)
    main.status_limiter._hits.clear()
    yield
    livechain._cache.update(blocks=None, fetched_at=0.0)


@pytest.fixture
def upstream(monkeypatch):
    """Counts fetches; set .fail to make the explorer error."""
    state = {"calls": 0, "fail": False}

    def fake():
        state["calls"] += 1
        if state["fail"]:
            raise ConnectionError("explorer down")
        return [dict(BLOCK)]

    monkeypatch.setattr(livechain, "_fetch", fake)
    return state


def test_caches_within_ttl(upstream):
    livechain.recent_blocks()
    livechain.recent_blocks()
    assert upstream["calls"] == 1


def test_refetches_after_ttl(upstream):
    livechain.recent_blocks()
    livechain._cache["fetched_at"] -= livechain.TTL_SECONDS + 1
    livechain.recent_blocks()
    assert upstream["calls"] == 2


def test_serves_stale_copy_when_upstream_fails(upstream):
    livechain.recent_blocks()
    livechain._cache["fetched_at"] -= livechain.TTL_SECONDS + 1
    upstream["fail"] = True
    out = livechain.recent_blocks()
    assert out["stale"] is True
    assert out["blocks"] == [BLOCK]


def test_endpoint_502_when_never_fetched(upstream):
    upstream["fail"] = True
    res = TestClient(main.app).get("/mainnet-blocks")
    assert res.status_code == 502


def test_endpoint_labels_its_source(upstream):
    body = TestClient(main.app).get("/mainnet-blocks").json()
    # The UI must never present this as our node's data.
    assert body["network"] == "mainnet"
    assert body["source"] == livechain.SOURCE_NAME
    assert body["blocks"] == [BLOCK]


def test_fetch_keeps_only_whitelisted_fields(monkeypatch):
    class Res:
        def raise_for_status(self):
            pass

        def json(self):
            return [{**BLOCK, "merkle_root": "ff", "nonce": 7}]

    monkeypatch.setattr(livechain.requests, "get", lambda *a, **k: Res())
    assert livechain._fetch() == [BLOCK]
