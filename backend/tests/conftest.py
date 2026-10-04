"""Test tiers and shared setup.

Three tiers, selected by directory (no per-test decorator to forget):

    tests/unit/         no node, no network       -> `make test`
    tests/network/      internet only             -> `make test-sources`
    tests/integration/  live regtest bitcoind     -> `make test-integration`

Plain `pytest` (and `make test`) runs only the unit tier (pytest.ini sets
`-m "not integration and not network"`), so it is safe to run anywhere,
including a fresh clone with no chain. The other tiers are opt-in because they
fail for environmental reasons, not code reasons, when their dependency is
missing. Override with `-m integration` / `-m network`.
"""
import json
import os
import tempfile

import pytest

_HERE = os.path.dirname(__file__)
_REAL_FIXTURES = os.path.join(_HERE, "..", "fixtures.json")

# mutations.py reads fixtures.json at import time. With no mined chain (a
# fresh clone, CI's unit job) point it at a throwaway stub so importing the
# backend never requires a node. A real fixtures.json always wins, so the
# integration tier is unaffected.
if "BTC_FIXTURES_PATH" not in os.environ and not os.path.exists(_REAL_FIXTURES):
    _stub = {
        "network": "regtest",
        "frozen_tip_hash": "00" * 32,
        "frozen_tip_height": 123,
        "mining_address": "bcrt1qstub",
        "utxos": {
            "spendable_a": {"txid": "aa" * 32, "vout": 0, "amount": 1.0, "scriptPubKey": "0014" + "11" * 20, "address": "bcrt1qa"},
            "already_spent": {"txid": "bb" * 32, "vout": 0, "amount": 1.0, "scriptPubKey": "0014" + "22" * 20, "address": "bcrt1qb"},
        },
        "scratch_addresses": {k: "bcrt1qstub" for k in (
            "dust_a", "dust_change", "fee_dest", "double_spend_dest", "coinbase_spend_dest", "locktime_dest")},
    }
    _fd, _path = tempfile.mkstemp(suffix=".json", prefix="btc-fixtures-stub-")
    with os.fdopen(_fd, "w") as f:
        json.dump(_stub, f)
    os.environ["BTC_FIXTURES_PATH"] = _path


_TIERS = ("unit", "network", "integration")


def pytest_collection_modifyitems(config, items):
    for item in items:
        for tier in _TIERS:
            if f"{os.sep}tests{os.sep}{tier}{os.sep}" in str(item.fspath):
                item.add_marker(getattr(pytest.mark, tier))
