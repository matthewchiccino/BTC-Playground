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

    spend_addr = rpc("getnewaddress", ["spend_sink"])
    rpc("sendtoaddress", [spend_addr, 0.5])
    rpc("generatetoaddress", [1, mining_address])

    already_spent = already_spent_fixture

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
