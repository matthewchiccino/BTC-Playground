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
from test_framework.messages import CTransaction, ser_uint256  # noqa: E402

from node import rpc  # noqa: E402

FIXTURES_PATH = os.path.join(os.path.dirname(__file__), "fixtures.json")

with open(FIXTURES_PATH) as f:
    FIXTURES = json.load(f)


def _traced_rpc(calls: list, method: str, params: list | None = None):
    calls.append(method)
    return rpc(method, params)


def coinbase_oversubsidy(value_sats: int | None = None) -> dict:
    """Pay the coinbase output some amount. Defaults to 1 satoshi over the
    block subsidy; a caller-supplied value_sats lets the UI's "try a
    different value" knob explore the accept/reject boundary directly.
    """
    calls = []
    tmpl = _traced_rpc(calls, "getblocktemplate", [{"rules": ["segwit"]}])

    valid_coinbase = create_coinbase(height=tmpl["height"])
    subsidy_sats = valid_coinbase.vout[0].nValue
    baseline_block = create_block(tmpl=tmpl, coinbase=valid_coinbase)
    baseline_block.hashMerkleRoot = baseline_block.calc_merkle_root()

    attack_coinbase = create_coinbase(height=tmpl["height"])
    attack_coinbase.vout[0].nValue = subsidy_sats + 1 if value_sats is None else value_sats
    attack_block = create_block(tmpl=tmpl, coinbase=attack_coinbase)
    attack_block.hashMerkleRoot = attack_block.calc_merkle_root()

    return {
        "baseline_hex": baseline_block.serialize().hex(),
        "payload_hex": attack_block.serialize().hex(),
        "build_calls": calls,
        "subsidy_sats": subsidy_sats,
        "editable_value": attack_coinbase.vout[0].nValue,
    }


def bad_merkle_root(merkle_root_hex: str | None = None) -> dict:
    """A structurally valid block whose merkle root doesn't match its transactions.

    Defaults to flipping a single bit in the correct root. A caller-supplied
    merkle_root_hex lets the UI's "try a different value" knob prove the
    root isn't arbitrary -- anything except the one true value gets
    rejected, and typing the exact value back makes it valid again.
    """
    calls = []
    tmpl = _traced_rpc(calls, "getblocktemplate", [{"rules": ["segwit"]}])

    baseline_block = create_block(tmpl=tmpl)
    baseline_block.hashMerkleRoot = baseline_block.calc_merkle_root()
    correct_root_hex = ser_uint256(baseline_block.hashMerkleRoot)[::-1].hex()

    attack_block = create_block(tmpl=tmpl)
    if merkle_root_hex is None:
        attack_block.hashMerkleRoot = baseline_block.calc_merkle_root() ^ 1
    else:
        attack_block.hashMerkleRoot = int.from_bytes(bytes.fromhex(merkle_root_hex)[::-1], "little")

    return {
        "baseline_hex": baseline_block.serialize().hex(),
        "payload_hex": attack_block.serialize().hex(),
        "build_calls": calls,
        "editable_value": ser_uint256(attack_block.hashMerkleRoot)[::-1].hex(),
        "hint_value": correct_root_hex,
    }


def _build_spend_block(calls: list, utxo_key: str):
    """A block containing one tx that spends the named fixture UTXO."""
    fixture = FIXTURES["utxos"][utxo_key]
    dest = _traced_rpc(calls, "getnewaddress", [f"spend_{utxo_key}"])
    fee = 0.0001
    send_amount = round(fixture["amount"] - fee, 8)

    raw = _traced_rpc(
        calls,
        "createrawtransaction",
        [[{"txid": fixture["txid"], "vout": fixture["vout"]}], {dest: send_amount}],
    )
    prevtx = {
        "txid": fixture["txid"],
        "vout": fixture["vout"],
        "scriptPubKey": fixture["scriptPubKey"],
        "amount": fixture["amount"],
    }
    signed = _traced_rpc(calls, "signrawtransactionwithwallet", [raw, [prevtx]])
    if not signed["complete"]:
        raise RuntimeError(f"{utxo_key} spend tx failed to sign: {signed}")

    tx = CTransaction()
    tx.deserialize(io.BytesIO(bytes.fromhex(signed["hex"])))

    tmpl = _traced_rpc(calls, "getblocktemplate", [{"rules": ["segwit"]}])
    block = create_block(tmpl=tmpl, txlist=[tx])
    add_witness_commitment(block)
    return block


def double_spend(utxo_key: str | None = None) -> dict:
    """Try to spend a UTXO. Defaults to "already_spent" -- one that was
    already consumed by a different transaction mined earlier in this same
    chain. A caller-supplied utxo_key of "spendable_a" spends a UTXO that's
    genuinely still free, for direct comparison against the attack.

    testmempoolaccept alone can't tell "never existed" apart from "already
    spent" -- both just report missing-inputs. Putting the same tx in a
    block and proposing it hits ConnectBlock's UTXO-set check instead, which
    is what actually produces bad-txns-inputs-missingorspent.
    """
    calls = []
    chosen_key = utxo_key or "already_spent"

    baseline_block = _build_spend_block(calls, "spendable_a")
    attack_block = baseline_block if chosen_key == "spendable_a" else _build_spend_block(calls, chosen_key)

    return {
        "baseline_hex": baseline_block.serialize().hex(),
        "payload_hex": attack_block.serialize().hex(),
        "build_calls": calls,
        "editable_value": chosen_key,
    }


# A P2WPKH output below this many sats costs more to spend later than it's
# worth. Verified against src/policy/policy.cpp's GetDustThreshold at the
# default relay fee -- see sources.py for the permalink.
DUST_THRESHOLD_SATS = 294


def dust_output(value_sats: int | None = None) -> dict:
    """Spend spendable_a into one caller-controlled output plus change.

    Checked empirically, not assumed: Core's "ephemeral dust" allowance
    (one tolerated dust output per tx) only applies to a completely
    0-fee transaction, meant to be paired with a follow-up transaction
    that immediately spends the dust and pays for both (see
    PreCheckEphemeralTx in src/policy/ephemeral_policy.cpp). This
    transaction pays an ordinary fee, like almost every real transaction
    -- and once any fee is present, Core tolerates zero dust outputs, not
    one. That's the rule this scenario actually demonstrates.
    """
    calls = []
    spendable = FIXTURES["utxos"]["spendable_a"]
    fee_sats = 1000
    chosen_sats = 1 if value_sats is None else value_sats

    def _build(sats: int) -> str:
        addr = _traced_rpc(calls, "getnewaddress", ["dust_output"])
        change_addr = _traced_rpc(calls, "getnewaddress", ["dust_change"])

        spend_sats = round(spendable["amount"] * 100_000_000)
        change_sats = spend_sats - sats - fee_sats

        outputs = {
            addr: round(sats / 100_000_000, 8),
            change_addr: round(change_sats / 100_000_000, 8),
        }
        raw = _traced_rpc(
            calls,
            "createrawtransaction",
            [[{"txid": spendable["txid"], "vout": spendable["vout"]}], outputs],
        )
        prevtx = {
            "txid": spendable["txid"],
            "vout": spendable["vout"],
            "scriptPubKey": spendable["scriptPubKey"],
            "amount": spendable["amount"],
        }
        signed = _traced_rpc(calls, "signrawtransactionwithwallet", [raw, [prevtx]])
        if not signed["complete"]:
            raise RuntimeError(f"dust_output tx failed to sign (sats={sats}): {signed}")
        return signed["hex"]

    baseline_hex = _build(DUST_THRESHOLD_SATS + 1)
    payload_hex = baseline_hex if chosen_sats == DUST_THRESHOLD_SATS + 1 else _build(chosen_sats)

    return {
        "baseline_hex": baseline_hex,
        "payload_hex": payload_hex,
        "build_calls": calls,
        "editable_value": chosen_sats,
        "hint_value": DUST_THRESHOLD_SATS,
    }


MUTATIONS = {
    "coinbase_oversubsidy": coinbase_oversubsidy,
    "bad_merkle_root": bad_merkle_root,
    "double_spend": double_spend,
    "dust_output": dust_output,
}
