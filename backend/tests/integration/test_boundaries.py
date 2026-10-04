"""Pins the exact accept/reject edge of every scenario against the live node.

The UI promises users a boundary ("watch the verdict flip right at the line")
and prints the threshold as a hint. If a Bitcoin Core upgrade moves a
threshold, or a refactor shifts an off-by-one, this fails loudly instead of
the app quietly teaching something false.

Each row: scenario id -> (value that is ACCEPTED, value that is REJECTED),
both derived from the mutation's own `hint_value`, so the hint text and the
node's behavior are checked against each other.
"""
import pytest

from mutations import MUTATIONS
from node import rpc
from scenarios import SCENARIOS_BY_ID


def _flip_last_hex_digit(h: str) -> str:
    return h[:-1] + ("0" if h[-1] != "0" else "1")


# scenario -> (accepted(hint), rejected(hint))
EDGES = {
    "coinbase_oversubsidy": (lambda h: h, lambda h: h + 1),      # may pay exactly the subsidy, not 1 sat more
    "dust_output": (lambda h: h, lambda h: h - 1),               # 294 sats is the smallest non-dust P2WPKH output
    "fee_too_low": (lambda h: h, lambda h: h - 1),               # hint is the exact minimum relay fee
    "coinbase_maturity": (lambda h: h, lambda h: h - 1),         # 100 confirmations, not 99
    "locktime_nonfinal": (lambda h: h - 1, lambda h: h),         # must be strictly below the block's height
    "bad_merkle_root": (lambda h: h, _flip_last_hex_digit),      # exactly one root is valid
}


def verdict(kind: str, payload_hex: str) -> str | None:
    if kind == "block":
        return rpc("getblocktemplate", [{"mode": "proposal", "data": payload_hex}]) or None
    result = rpc("testmempoolaccept", [[payload_hex]])[0]
    return None if result["allowed"] else result["reject-reason"]


@pytest.mark.parametrize("scenario_id", list(EDGES))
def test_threshold_is_exactly_where_the_hint_says(scenario_id):
    s = SCENARIOS_BY_ID[scenario_id]
    mutate = MUTATIONS[s["mutation"]]
    field = s["editable"]["field"]
    hint = mutate()["hint_value"]
    accepted_value, rejected_value = EDGES[scenario_id][0](hint), EDGES[scenario_id][1](hint)

    assert verdict(s["kind"], mutate(**{field: accepted_value})["payload_hex"]) is None
    assert verdict(s["kind"], mutate(**{field: rejected_value})["payload_hex"]) == s["expected_reject_reason"]


def test_double_spend_control_utxo_is_accepted_and_attack_is_rejected():
    s = SCENARIOS_BY_ID["double_spend"]
    mutate = MUTATIONS[s["mutation"]]
    assert verdict("block", mutate(utxo_key="spendable_a")["payload_hex"]) is None
    assert verdict("block", mutate(utxo_key="already_spent")["payload_hex"]) == s["expected_reject_reason"]


def test_every_scenario_has_an_edge_test():
    covered = set(EDGES) | {"double_spend"}
    assert covered == set(SCENARIOS_BY_ID), "new scenario: add its accept/reject edge to EDGES"
