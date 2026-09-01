"""
Mines a frozen regtest chain and writes fixtures.json.

Run once, against a freshly-started, empty regtest node. Idempotent: exits
early if fixtures.json already exists. The chain is never mined again after
this runs -- see plam.md section 2.2 for why.
"""
import json
import os

from node import rpc

FIXTURES_PATH = os.path.join(os.path.dirname(__file__), "fixtures.json")


def main():
    if os.path.exists(FIXTURES_PATH):
        print(f"{FIXTURES_PATH} already exists, skipping setup.")
        return

    wallets = rpc("listwallets", wallet=None)
    if "playground" not in wallets:
        try:
            rpc("createwallet", ["playground"], wallet=None)
        except RuntimeError:
            rpc("loadwallet", ["playground"], wallet=None)

    mining_address = rpc("getnewaddress", ["mining"])
    rpc("generatetoaddress", [120, mining_address])

    # --- spendable_a: a normal confirmed UTXO, unspent at freeze time ---
    addr_a = rpc("getnewaddress", ["fixture_a"])
    txid_a = rpc("sendtoaddress", [addr_a, 1.0])
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
    addr_b = rpc("getnewaddress", ["fixture_b"])
    txid_b = rpc("sendtoaddress", [addr_b, 1.0])
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


def _find_vout(txid: str, address: str) -> int:
    tx = rpc("gettransaction", [txid, True])
    for detail in tx["details"]:
        if detail.get("address") == address:
            return detail["vout"]
    raise RuntimeError(f"could not find vout paying {address} in {txid}")


if __name__ == "__main__":
    main()
