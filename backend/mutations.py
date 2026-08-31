"""One function per attack scenario. Each returns a dict:
    payload_hex   -- the attack, ready to submit
    baseline_hex  -- a structurally-identical valid version, for byte-diffing
                     in the UI (None where there's no meaningful single-tx
                     bit-flip baseline, e.g. double_spend)
    build_calls   -- ordered list of RPC method names used to construct the
                     payload, so the UI can show what actually happened

Transactions: build a valid baseline via the node's own wallet, then mutate
the deserialized bytes in Python (see plam.md section 4.1).

Blocks: vendor Core's own test_framework for coinbase/merkle construction
rather than hand-rolling serialization (see plam.md section 4.2).
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "vendor"))

from test_framework.blocktools import add_witness_commitment, create_block, create_coinbase  # noqa: E402
from test_framework.messages import CTransaction  # noqa: E402

from node import rpc  # noqa: E402

FIXTURES_PATH = os.path.join(os.path.dirname(__file__), "fixtures.json")

with open(FIXTURES_PATH) as f:
    FIXTURES = json.load(f)


def _traced_rpc(calls: list, method: str, params: list | None = None):
    calls.append(method)
    return rpc(method, params)


def coinbase_oversubsidy() -> dict:
    """Mint exactly 1 satoshi more than the block subsidy allows."""
    calls = []
    tmpl = _traced_rpc(calls, "getblocktemplate", [{"rules": ["segwit"]}])

    valid_coinbase = create_coinbase(height=tmpl["height"])
    baseline_block = create_block(tmpl=tmpl, coinbase=valid_coinbase)
    baseline_block.hashMerkleRoot = baseline_block.calc_merkle_root()

    attack_coinbase = create_coinbase(height=tmpl["height"])
    attack_coinbase.vout[0].nValue += 1
    attack_block = create_block(tmpl=tmpl, coinbase=attack_coinbase)
    attack_block.hashMerkleRoot = attack_block.calc_merkle_root()

    return {
        "baseline_hex": baseline_block.serialize().hex(),
        "payload_hex": attack_block.serialize().hex(),
        "build_calls": calls,
    }


def bad_merkle_root() -> dict:
    """A structurally valid block whose merkle root doesn't match its transactions."""
    calls = []
    tmpl = _traced_rpc(calls, "getblocktemplate", [{"rules": ["segwit"]}])

    baseline_block = create_block(tmpl=tmpl)
    baseline_block.hashMerkleRoot = baseline_block.calc_merkle_root()

    attack_block = create_block(tmpl=tmpl)
    attack_block.hashMerkleRoot = attack_block.calc_merkle_root() ^ 1

    return {
        "baseline_hex": baseline_block.serialize().hex(),
        "payload_hex": attack_block.serialize().hex(),
        "build_calls": calls,
    }


def double_spend() -> dict:
    """Try to re-spend a UTXO that was already consumed by a mined transaction.

    testmempoolaccept alone can't tell "never existed" apart from "already
    spent" -- both just report missing-inputs. Putting the same tx in a
    block and proposing it hits ConnectBlock's UTXO-set check instead, which
    is what actually produces bad-txns-inputs-missingorspent.
    """
    calls = []
    already_spent = FIXTURES["utxos"]["already_spent"]
    dest = _traced_rpc(calls, "getnewaddress", ["double_spend_dest"])
    fee = 0.0001
    send_amount = round(already_spent["amount"] - fee, 8)

    raw = _traced_rpc(
        calls,
        "createrawtransaction",
        [
            [{"txid": already_spent["txid"], "vout": already_spent["vout"]}],
            {dest: send_amount},
        ],
    )
    prevtx = {
        "txid": already_spent["txid"],
        "vout": already_spent["vout"],
        "scriptPubKey": already_spent["scriptPubKey"],
        "amount": already_spent["amount"],
    }
    signed = _traced_rpc(calls, "signrawtransactionwithwallet", [raw, [prevtx]])
    if not signed["complete"]:
        raise RuntimeError(f"double_spend baseline tx failed to sign: {signed}")

    tx = CTransaction()
    tx.deserialize(io.BytesIO(bytes.fromhex(signed["hex"])))

    tmpl = _traced_rpc(calls, "getblocktemplate", [{"rules": ["segwit"]}])
    block = create_block(tmpl=tmpl, txlist=[tx])
    add_witness_commitment(block)

    return {
        "baseline_hex": None,
        "payload_hex": block.serialize().hex(),
        "build_calls": calls,
    }


MUTATIONS = {
    "coinbase_oversubsidy": coinbase_oversubsidy,
    "bad_merkle_root": bad_merkle_root,
    "double_spend": double_spend,
}
