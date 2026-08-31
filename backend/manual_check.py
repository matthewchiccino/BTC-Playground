"""Plain-script sanity check, no web app: build each attack, submit it,
print the node's verdict. Run before trusting the FastAPI wrapper.
"""
from mutations import bad_merkle_root, coinbase_oversubsidy, double_spend, dust_output, fee_too_low
from node import rpc


def check_block(name: str, hexdata: str):
    result = rpc("getblocktemplate", [{"mode": "proposal", "data": hexdata}])
    verdict = result if result else "accepted (unexpected!)"
    print(f"[{name}] {verdict}")


def check_tx(name: str, hexdata: str):
    result = rpc("testmempoolaccept", [[hexdata]])[0]
    verdict = "accepted (unexpected!)" if result["allowed"] else result["reject-reason"]
    print(f"[{name}] {verdict}")


if __name__ == "__main__":
    check_block("coinbase_oversubsidy", coinbase_oversubsidy()["payload_hex"])
    check_block("bad_merkle_root", bad_merkle_root()["payload_hex"])
    check_block("double_spend", double_spend()["payload_hex"])
    check_tx("dust_output", dust_output()["payload_hex"])
    check_tx("fee_too_low", fee_too_low()["payload_hex"])
