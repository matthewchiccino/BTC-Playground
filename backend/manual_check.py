"""Plain-script sanity check, no web app: build each attack, submit it,
print the node's verdict. Run before trusting the FastAPI wrapper.
"""
from mutations import bad_merkle_root, coinbase_oversubsidy, double_spend
from node import rpc


def check_block(name: str, hexdata: str):
    result = rpc("getblocktemplate", [{"mode": "proposal", "data": hexdata}])
    verdict = result if result else "accepted (unexpected!)"
    print(f"[{name}] {verdict}")


if __name__ == "__main__":
    check_block("coinbase_oversubsidy", coinbase_oversubsidy()["payload_hex"])
    check_block("bad_merkle_root", bad_merkle_root()["payload_hex"])
    check_block("double_spend", double_spend()["payload_hex"])
