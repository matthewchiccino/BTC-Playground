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
        "editable": {
            "field": "value_sats",
            "label": "Coinbase payout (satoshis)",
            "type": "int",
            "min": 0,
            "max": 10_000_000_000,
            "step": 1,
        },
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
            "A block's merkle root is a single hash that summarizes every "
            "transaction inside it -- change even one transaction and the "
            "correct root changes completely. Here the real transactions are "
            "untouched, but the header claims a different root anyway. Every "
            "node recomputes the true root from the actual transactions and "
            "compares it to what's claimed, without even needing to check the "
            "transactions themselves for anything else -- any mismatch is an "
            "instant, cheap rejection."
        ),
        "editable": {
            "field": "merkle_root_hex",
            "label": "Merkle root (hex)",
            "type": "hex",
            "length": 64,
        },
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
            "This block spends a UTXO (an unspent transaction output) that "
            "was already consumed by a different transaction earlier in this "
            "same chain. Every full node tracks the current set of unspent "
            "outputs -- once one is spent, it's removed from that set for "
            "good. Try to spend it again and the node simply can't find it "
            "there anymore. This is the actual mechanism that makes it "
            "impossible to spend the same bitcoin twice."
        ),
        "editable": {
            "field": "utxo_key",
            "label": "UTXO to spend",
            "type": "choice",
            "options": [
                {"value": "already_spent", "label": "Already-spent UTXO (the attack)"},
                {"value": "spendable_a", "label": "Fresh, unspent UTXO (control)"},
            ],
        },
    },
]

SCENARIOS_BY_ID = {s["id"]: s for s in SCENARIOS}
