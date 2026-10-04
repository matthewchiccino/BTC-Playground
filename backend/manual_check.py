"""Plain-script sanity check, no web app: build each attack, submit it,
print the node's verdict. Run before trusting the FastAPI wrapper.

Iterates the scenario catalog, so a new scenario is covered automatically.
"""
from mutations import MUTATIONS
from node import rpc
from scenarios import SCENARIOS


def verdict_for(kind: str, payload_hex: str) -> str | None:
    if kind == "block":
        return rpc("getblocktemplate", [{"mode": "proposal", "data": payload_hex}]) or None
    result = rpc("testmempoolaccept", [[payload_hex]])[0]
    return None if result["allowed"] else result["reject-reason"]


if __name__ == "__main__":
    for s in SCENARIOS:
        verdict = verdict_for(s["kind"], MUTATIONS[s["mutation"]]()["payload_hex"])
        status = "ok" if verdict == s["expected_reject_reason"] else "MISMATCH"
        print(f"[{s['id']}] {verdict or 'accepted (unexpected!)'}  ({status})")
