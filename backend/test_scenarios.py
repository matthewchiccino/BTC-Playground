"""Asserts the live node still agrees with the catalog's expected_reject_reason.

If a future Core release changes an error string, this fails loudly instead
of the UI quietly showing a verdict that no longer matches reality.
"""
import pytest

from mutations import MUTATIONS
from node import rpc
from scenarios import SCENARIOS


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario_matches_catalog(scenario):
    payload_hex = MUTATIONS[scenario["mutation"]]()["payload_hex"]

    if scenario["kind"] == "block":
        result = rpc("getblocktemplate", [{"mode": "proposal", "data": payload_hex}])
        verdict = result if result else None
    else:
        result = rpc("testmempoolaccept", [[payload_hex]])[0]
        verdict = None if result["allowed"] else result["reject-reason"]

    assert verdict == scenario["expected_reject_reason"]
