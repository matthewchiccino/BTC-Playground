"""The attack catalog. Add a scenario by adding one entry here and one
mutation function in mutations.py -- nothing else should need to change.
"""

SCENARIOS = [
    {
        "id": "coinbase_oversubsidy",
        "title": "Coinbase Over-subsidy",
        "kind": "block",
        "fixture_key": None,
        "mutation": "coinbase_oversubsidy",
        "expected_reject_reason": "bad-cb-amount",
        "rule_type": "consensus",
        "explanation": (
            "The coinbase transaction pays itself exactly 1 satoshi more than "
            "the block subsidy plus fees allows. Every node independently "
            "recomputes the maximum a miner is allowed to pay itself for a "
            "given height -- there's no way to sneak extra sats past that "
            "check, no matter how much hashpower you have."
        ),
    },
    {
        "id": "bad_merkle_root",
        "title": "Bad Merkle Root",
        "kind": "block",
        "fixture_key": None,
        "mutation": "bad_merkle_root",
        "expected_reject_reason": "bad-txnmrklroot",
        "rule_type": "consensus",
        "explanation": (
            "The block header's merkle root is flipped by a single bit, so it "
            "no longer matches the block's actual transactions. The merkle "
            "root is what lets a node (or an SPV wallet) verify a block's "
            "contents without re-deriving them from scratch -- mutate it and "
            "the mismatch is instantly and cheaply detectable."
        ),
    },
    {
        "id": "double_spend",
        "title": "Double Spend",
        "kind": "block",
        "fixture_key": "already_spent",
        "mutation": "double_spend",
        "expected_reject_reason": "bad-txns-inputs-missingorspent",
        "rule_type": "consensus",
        "explanation": (
            "This transaction spends a UTXO that was already consumed by a "
            "different transaction mined earlier in this same chain. Once an "
            "output is spent, it's gone -- every full node's UTXO set enforces "
            "this, which is the entire mechanism that makes Bitcoin's ledger "
            "resistant to spending the same coin twice."
        ),
    },
]

SCENARIOS_BY_ID = {s["id"]: s for s in SCENARIOS}
