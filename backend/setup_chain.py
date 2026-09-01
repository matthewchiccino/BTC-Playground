"""
Mines a frozen regtest chain and writes fixtures.json.

Run once, against a freshly-started, empty regtest node. Idempotent by
default: exits early if fixtures.json already exists, which is what you
want on a laptop where the regtest datadir persists across restarts.

In a container, bitcoind starts with a fresh, empty datadir every boot --
so setup needs to run every time too, regardless of whether a fixtures.json
happens to already be sitting there (e.g. one that got baked into the image
by accident; see .dockerignore). Pass --force, or set FORCE_SETUP=1, to
skip the idempotency check and always re-mine.

The chain is never mined again after this runs within a given boot -- see
plam.md section 2.2 for why.
"""
import json
import os
import sys

from node import rpc

FIXTURES_PATH = os.path.join(os.path.dirname(__file__), "fixtures.json")


def main():
    force = "--force" in sys.argv or os.environ.get("FORCE_SETUP", "").lower() in ("1", "true", "yes")

    if os.path.exists(FIXTURES_PATH) and not force:
        print(f"{FIXTURES_PATH} already exists, skipping setup.")
        return

    if os.path.exists(FIXTURES_PATH) and force:
        print(f"{FIXTURES_PATH} exists but --force/FORCE_SETUP is set -- re-mining.")
        os.remove(FIXTURES_PATH)

    wallets = rpc("listwallets", wallet=None)
    if "playground" not in wallets:
        try:
            rpc("createwallet", ["playground"], wallet=None)
        except RuntimeError:
            rpc("loadwallet", ["playground"], wallet=None)

    mining_address = rpc("getnewaddress", ["mining"])
    mined_hashes = rpc("generatetoaddress", [120, mining_address])

    # --- spendable_a: a normal confirmed UTXO, unspent at freeze time ---
    # Funded from a specific, named coinbase (mined_hashes[0]) rather than
    # sendtoaddress's automatic coin selection. On a from-empty run there's
    # nothing else to pick, but on a --force re-run over an already-used
    # wallet there is: the previous run's leftover 1-BTC-ish outputs are
    # exactly the kind of coin an automatic selector prefers over a 50-BTC
    # coinbase, which is precisely how already_spent's own funding step
    # once ended up silently spending spendable_a's fresh output instead of
    # a coinbase (caught by the postcondition check below).
    addr_a = rpc("getnewaddress", ["fixture_a"])
    txid_a = _fund_from_coinbase(mined_hashes[0], addr_a, 1.0, "change_a")
    rpc("generatetoaddress", [1, mining_address])
    vout_a = _find_vout(txid_a, addr_a)
    utxo_a = rpc("gettxout", [txid_a, vout_a])

    spendable_a = {
        "txid": txid_a,
        "vout": vout_a,
        "amount": utxo_a["value"],
        "scriptPubKey": utxo_a["scriptPubKey"]["hex"],
        "address": addr_a,
    }

    # --- already_spent: a UTXO spent by a tx that is itself mined ---
    # Same reasoning: a distinct, specific coinbase (mined_hashes[1]), not
    # automatic selection.
    addr_b = rpc("getnewaddress", ["fixture_b"])
    txid_b = _fund_from_coinbase(mined_hashes[1], addr_b, 1.0, "change_b")
    rpc("generatetoaddress", [1, mining_address])
    vout_b = _find_vout(txid_b, addr_b)
    utxo_b = rpc("gettxout", [txid_b, vout_b])

    already_spent_fixture = {
        "txid": txid_b,
        "vout": vout_b,
        "amount": utxo_b["value"],
        "scriptPubKey": utxo_b["scriptPubKey"]["hex"],
        "address": addr_b,
    }

    # Spend txid_b:vout_b specifically -- sendtoaddress would run automatic
    # coin selection and could just as easily pick a coinbase output or
    # spendable_a instead, leaving this fixture silently NOT double-spent.
    # Pin the input explicitly so this is deterministic, not "whatever this
    # Core version's selector happens to prefer today."
    spend_addr = rpc("getnewaddress", ["spend_sink"])
    raw = rpc(
        "createrawtransaction",
        [[{"txid": txid_b, "vout": vout_b}], {spend_addr: round(utxo_b["value"] - 0.0001, 8)}],
    )
    signed = rpc("signrawtransactionwithwallet", [raw])
    rpc("sendrawtransaction", [signed["hex"]])
    rpc("generatetoaddress", [1, mining_address])

    if rpc("gettxout", [txid_b, vout_b]) is not None:
        raise RuntimeError("already_spent fixture is not actually spent")
    if rpc("gettxout", [txid_a, vout_a]) is None:
        raise RuntimeError("spendable_a got consumed during setup")

    already_spent = already_spent_fixture

    # Fixed destination addresses reused by every mutation's own tx-building
    # (dust_output, fee_too_low, double_spend, coinbase_maturity). Generated
    # once here instead of minting a fresh one per /build call: baseline and
    # payload builds land on the same address, so the hex/readable diff only
    # highlights what actually changed, not incidental scriptPubKey churn --
    # and the wallet's keypool stops growing on every request.
    scratch_addresses = {
        "dust_a": rpc("getnewaddress", ["scratch_dust_a"]),
        "dust_change": rpc("getnewaddress", ["scratch_dust_change"]),
        "fee_dest": rpc("getnewaddress", ["scratch_fee_dest"]),
        "double_spend_dest": rpc("getnewaddress", ["scratch_double_spend_dest"]),
        "coinbase_spend_dest": rpc("getnewaddress", ["scratch_coinbase_spend_dest"]),
    }

    tip_hash = rpc("getbestblockhash")
    tip_height = rpc("getblockcount")

    fixtures = {
        "network": "regtest",
        "frozen_tip_hash": tip_hash,
        "frozen_tip_height": tip_height,
        "mining_address": mining_address,
        "utxos": {
            "spendable_a": spendable_a,
            "already_spent": already_spent,
        },
        "scratch_addresses": scratch_addresses,
    }

    with open(FIXTURES_PATH, "w") as f:
        json.dump(fixtures, f, indent=2)

    print(f"Wrote {FIXTURES_PATH}. Frozen at height {tip_height}, tip {tip_hash}.")
    print("Do not mine again. Re-run from a fresh datadir to reset.")


def _fund_from_coinbase(block_hash: str, to_address: str, amount_btc: float, change_label: str) -> str:
    """Spend a specific, named coinbase output to pay to_address, with
    change back to a fresh wallet address -- not sendtoaddress, which would
    run automatic coin selection and could pick any wallet-owned UTXO."""
    block = rpc("getblock", [block_hash, 2])
    coinbase = block["tx"][0]
    coinbase_value = coinbase["vout"][0]["value"]
    fee = 0.0001
    change_amount = round(coinbase_value - amount_btc - fee, 8)
    change_address = rpc("getnewaddress", [change_label])
    raw = rpc(
        "createrawtransaction",
        [[{"txid": coinbase["txid"], "vout": 0}], {to_address: amount_btc, change_address: change_amount}],
    )
    signed = rpc("signrawtransactionwithwallet", [raw])
    return rpc("sendrawtransaction", [signed["hex"]])


def _find_vout(txid: str, address: str) -> int:
    tx = rpc("gettransaction", [txid, True])
    for detail in tx["details"]:
        if detail.get("address") == address:
            return detail["vout"]
    raise RuntimeError(f"could not find vout paying {address} in {txid}")


if __name__ == "__main__":
    main()
