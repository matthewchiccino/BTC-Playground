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
        "reference": None,
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
        "reference": None,
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
        "reference": None,
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
    {
        "id": "dust_output",
        "title": "Dust Output",
        "kind": "tx",
        "fixture_key": "spendable_a",
        "mutation": "dust_output",
        "expected_reject_reason": "dust",
        "rule_type": "policy",
        "explanation": (
            "A \"dust\" output is one so small it would cost more in future "
            "fees to spend than it's worth. Any transaction that pays a fee "
            "-- which is almost every real transaction -- gets zero "
            "tolerance for dust: even one such output gets the whole thing "
            "rejected. (Core does allow exactly one dust output through a "
            "narrow exception called {ref}, but only for a completely "
            "fee-free transaction meant to be cleaned up immediately by a "
            "follow-up transaction -- not the everyday case this scenario "
            "shows.) This is purely a relay policy choice, not a consensus "
            "rule: the exact same transaction would be perfectly valid if a "
            "miner mined it directly into a block."
        ),
        "reference": {
            "label": "ephemeral dust",
            "url": "https://github.com/bitcoin/bitcoin/pull/30239",
        },
        "editable": {
            "field": "value_sats",
            "label": "Output value (satoshis)",
            "type": "int",
            "min": 1,
            "max": 2000,
            "step": 1,
        },
    },
    {
        "id": "fee_too_low",
        "title": "Fee Too Low",
        "kind": "tx",
        "fixture_key": "spendable_a",
        "mutation": "fee_too_low",
        "expected_reject_reason": "min relay fee not met",
        "rule_type": "policy",
        "explanation": (
            "Every node sets a minimum fee rate it's willing to relay -- pay "
            "less than that and your transaction is dropped before it ever "
            "reaches the mempool, even though it's otherwise perfectly "
            "valid. This is the exact mechanism behind a wallet's "
            "\"transaction stuck, fee too low\" warning: the transaction "
            "isn't broken, it's just not worth a node's bandwidth to "
            "forward at that price. Like dust, this is a relay policy "
            "choice, not a consensus rule -- a miner could mine the same "
            "transaction directly into a block for free and it would be "
            "perfectly valid."
        ),
        "reference": None,
        "editable": {
            "field": "fee_sats",
            "label": "Fee (satoshis)",
            "type": "int",
            "min": 1,
            "max": 1000,
            "step": 1,
        },
    },
    {
        "id": "coinbase_maturity",
        "title": "Coinbase Maturity",
        "kind": "block",
        "fixture_key": None,
        "mutation": "coinbase_maturity",
        "expected_reject_reason": "bad-txns-premature-spend-of-coinbase",
        "rule_type": "consensus",
        "explanation": (
            "A freshly-mined block's reward isn't spendable right away -- it "
            "needs 100 confirmations first. This is the same "
            "Consensus::CheckTxInputs function that catches Double Spend, "
            "just a different branch: it checks whether an input being "
            "spent is a coinbase output, and if so, whether it's actually "
            "old enough yet. The rule exists so that if a chain reorg ever "
            "erases a recently-mined block, the coins it created -- and "
            "anything built on top of spending them -- can be safely undone "
            "too."
        ),
        "reference": None,
        "editable": {
            "field": "spend_height",
            "label": "Coinbase height to spend",
            "type": "int",
            "min": 1,
            "max": 123,
            "step": 1,
        },
    },
]

SCENARIOS_BY_ID = {s["id"]: s for s in SCENARIOS}
