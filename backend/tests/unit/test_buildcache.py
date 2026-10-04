"""buildcache is the only thing standing between /submit and arbitrary bytes
reaching the shared node, so its expiry and bounds are security-relevant.
"""
import re

import pytest

import buildcache
import main


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    buildcache._cache.clear()
    yield
    buildcache._cache.clear()


@pytest.fixture
def clock(monkeypatch):
    state = {"now": 5000.0}
    monkeypatch.setattr(buildcache.time, "time", lambda: state["now"])
    return state


def test_roundtrip(clock):
    build_id = buildcache.store("dust_output", "deadbeef")
    entry = buildcache.get(build_id)
    assert entry["scenario_id"] == "dust_output"
    assert entry["payload_hex"] == "deadbeef"


def test_unknown_id_is_none():
    assert buildcache.get("nope-nope-nope-nope") is None


def test_entry_expires_after_ttl_and_is_removed(clock):
    build_id = buildcache.store("s", "00")
    clock["now"] += buildcache.TTL_SECONDS - 1
    assert buildcache.get(build_id) is not None
    clock["now"] += 2
    assert buildcache.get(build_id) is None
    assert build_id not in buildcache._cache


def test_ids_are_unique_and_match_the_api_schema(clock):
    ids = {buildcache.store("s", "00") for _ in range(50)}
    assert len(ids) == 50
    # main.SubmitRequest rejects anything not matching this -- if the token
    # format ever drifts, every submit would 422. Catch it here instead.
    assert all(re.fullmatch(main.BUILD_ID_PATTERN, i) for i in ids)


def test_cache_is_bounded_and_evicts_oldest_first(clock, monkeypatch):
    monkeypatch.setattr(buildcache, "MAX_ENTRIES", 3)
    ids = []
    for i in range(8):
        clock["now"] += 1  # distinct, increasing expiry
        ids.append(buildcache.store("s", f"{i:02x}"))
    # Eviction runs before insert, so the bound is MAX_ENTRIES + 1.
    assert len(buildcache._cache) <= 3 + 1
    assert buildcache.get(ids[-1]) is not None
    assert buildcache.get(ids[0]) is None
