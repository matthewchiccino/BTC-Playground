"""The attack catalog. Add a scenario by adding one entry here and one
mutation function in mutations.py -- nothing else should need to change.
"""

SCENARIOS = [
    {
        "id": "coinbase_oversubsidy",
        "title": "Coinbase Oversubsidy",
        "kind": "block",
        "fixture_key": None,
        "mutation": "coinbase_oversubsidy",
        "expected_reject_reason": "bad-cb-amount",
        "rule_type": "consensus",
        "explanation": (
            "This is the exact check that stops a miner from paying itself "
            "extra bitcoin out of thin air. Every block starts with a "
            "special transaction called the coinbase. It is how the miner "
            "pays itself for finding the block. The most a miner can pay "
            "itself is the block subsidy plus any fees from other "
            "transactions in the block. On this chain, the block subsidy "
            "is 5,000,000,000 satoshis (50 BTC), and this block has no "
            "other transactions, so there are no extra fees to add. "
            "Adjust the coinbase payout and see how the node responds. "
            "Hint: 5,000,000,001 is 1 satoshi too many."
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
        "id": "double_spend",
        "title": "Double Spend",
        "kind": "block",
        "fixture_key": "already_spent",
        "mutation": "double_spend",
        "expected_reject_reason": "bad-txns-inputs-missingorspent",
        "rule_type": "consensus",
        "explanation": (
            "This is the actual mechanism that stops someone from "
            "spending the same bitcoin twice. A UTXO is an unspent "
            "transaction output. Think of it as one specific coin sitting "
            "in a wallet, ready to be spent. This block tries to spend a "
            "UTXO that was already spent by an earlier transaction on "
            "this same chain. Every full node keeps a running list of "
            "which UTXOs are still unspent. Once a UTXO is spent, it "
            "comes off that list for good. Trying to spend it again "
            "fails, because the node can no longer find it there. Adjust "
            "which UTXO gets spent and see how the node responds."
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
        "id": "bad_merkle_root",
        "title": "Bad Merkle Root",
        "kind": "block",
        "fixture_key": None,
        "mutation": "bad_merkle_root",
        "expected_reject_reason": "bad-txnmrklroot",
        "rule_type": "consensus",
        "explanation": (
            "This is the check that lets a node catch a tampered block "
            "without even reading every transaction inside it. Think of "
            "the merkle root as a fingerprint for everything in the "
            "block. Change even one transaction, and the fingerprint "
            "changes completely. In this scenario, the real transactions "
            "are left alone. Only the fingerprint written in the block "
            "header is swapped for a fake one. Every node recalculates "
            "the real fingerprint from the actual transactions and "
            "compares it to what the header claims. If they do not "
            "match, the block is rejected right away, without the node "
            "even needing to check the transactions for anything else. "
            "Adjust the merkle root and see how the node responds."
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
        "id": "dust_output",
        "title": "Dust Output",
        "kind": "tx",
        "fixture_key": "spendable_a",
        "mutation": "dust_output",
        "expected_reject_reason": "dust",
        "rule_type": "policy",
        "explanation": (
            "This is the rule that keeps the network from filling up "
            "with coins too small to ever be worth spending. A dust "
            "output is an amount so small that spending it later would "
            "cost more in fees than it is even worth. Almost every real "
            "transaction pays some fee. If a transaction pays a fee and "
            "has even one dust output, Bitcoin Core rejects the whole "
            "thing. There is one narrow exception, called {ref}. It only "
            "applies to a transaction that pays zero fee and is meant to "
            "be cleaned up right away by a follow up transaction. That is "
            "not what is happening in this scenario. This rule comes from "
            "relay policy, not consensus. The exact same transaction "
            "would be perfectly valid if a miner put it directly into a "
            "block. Adjust the output value and see how the node "
            "responds."
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
            "This is the reason a wallet sometimes calls a transaction "
            "stuck. Every node sets a minimum fee rate it is willing to "
            "relay. Pay less than that rate, and your transaction gets "
            "dropped before it ever reaches the mempool, even though "
            "nothing else is wrong with it. The transaction is not "
            "broken. It is just not worth a node's bandwidth to pass "
            "along at that price. Like dust, this is a relay policy "
            "choice, not a consensus rule. A miner could still mine the "
            "exact same transaction into a block for free, and it would "
            "be perfectly valid. Adjust the fee and see how the node "
            "responds."
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
            "This is the rule that protects against a chain reorg "
            "undoing coins that were already spent. A block reward is "
            "not spendable right away. It needs 100 confirmations first. "
            "This uses the same check as Double Spend, a function called "
            "Consensus::CheckTxInputs, just a different part of it. That "
            "check looks at whether the coin being spent came from a "
            "coinbase transaction, and if so, whether enough time has "
            "passed yet. Adjust the confirmations and see how the node "
            "responds."
        ),
        "reference": None,
        "editable": {
            "field": "confirmations",
            "label": "Confirmations",
            "type": "int",
            "min": 1,
            "max": 123,
            "step": 1,
        },
    },
]

SCENARIOS_BY_ID = {s["id"]: s for s in SCENARIOS}
