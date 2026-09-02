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
            "Every block starts with a special transaction called the "
            "coinbase. This is how the miner pays itself for finding the "
            "block. The most a miner can pay itself is the block subsidy "
            "plus any fees from other transactions in the block. On this "
            "chain, the block subsidy is 5,000,000,000 satoshis (50 BTC), "
            "and this block has no other transactions, so there are no "
            "extra fees to add. This scenario has the miner pay itself "
            "5,000,000,001 satoshis. That is exactly 1 satoshi too many. "
            "Every node checks this exact math on every single block. There "
            "is no way to sneak extra satoshis past that check, no matter "
            "how much mining power you have."
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
            "transaction inside it. Change even one transaction, and the "
            "correct merkle root changes completely. In this scenario, the "
            "real transactions in the block are left untouched. Only the "
            "header's claimed merkle root is swapped for the wrong one. "
            "Every node recomputes the true merkle root from the actual "
            "transactions and compares it to what the header claims. If the "
            "two do not match, the block is rejected immediately. This "
            "check is fast and cheap, so a node does not even need to look "
            "closely at the transactions to catch this."
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
            "A UTXO is an unspent transaction output. Think of it as one "
            "specific coin sitting in a wallet, ready to be spent. This "
            "block tries to spend a UTXO that was already spent by an "
            "earlier transaction on this same chain. Every full node keeps "
            "a running list of which UTXOs are still unspent. Once a UTXO "
            "is spent, it comes off that list for good. Trying to spend it "
            "again fails, because the node can no longer find it there. "
            "This is the actual mechanism that stops someone from spending "
            "the same bitcoin twice."
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
            "A dust output is an amount so small that spending it later "
            "would cost more in fees than it is even worth. Almost every "
            "real transaction pays some fee. If a transaction pays a fee "
            "and has even one dust output, Bitcoin Core rejects the whole "
            "thing. There is one narrow exception, called {ref}. It only "
            "applies to a transaction that pays zero fee and is meant to "
            "be cleaned up right away by a follow up transaction. That is "
            "not what is happening in this scenario. This rule comes from "
            "relay policy, not consensus. The exact same transaction would "
            "be perfectly valid if a miner put it directly into a block."
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
            "Every node sets a minimum fee rate it is willing to relay. "
            "Pay less than that rate, and your transaction gets dropped "
            "before it ever reaches the mempool, even though nothing else "
            "is wrong with it. This is the same reason a wallet sometimes "
            "shows a stuck transaction with a fee too low warning. The "
            "transaction is not broken. It is just not worth a node's "
            "bandwidth to pass along at that price. Like dust, this is a "
            "relay policy choice, not a consensus rule. A miner could "
            "still mine the exact same transaction into a block for free, "
            "and it would be perfectly valid."
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
            "A block reward is not spendable right away. It needs 100 "
            "confirmations first. This uses the same check as Double "
            "Spend, a function called Consensus::CheckTxInputs, just a "
            "different part of it. That check looks at whether the coin "
            "being spent came from a coinbase transaction, and if so, "
            "whether enough time has passed yet. This rule exists so "
            "that if a recent block ever gets reorganized out of the "
            "chain, the coins it created, and anything built on spending "
            "them, can be safely undone too."
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
