"""decode.py turns raw payload bytes back into labeled fields and marks which
differ from a baseline. The UI's highlighting is only as trustworthy as this.
"""
from decode import _script_asm, decode_payload

from helpers import P2WPKH_SPK, block_hex, make_block, tx_hex


def leaf(node):
    return node["value"]


def test_decodes_tx_fields():
    out = decode_payload(tx_hex(value_sats=99_000, locktime=7, sequence=0xFFFFFFFE), "tx")
    tx = out["transactions"][0]
    assert leaf(tx["version"]) == 2
    assert leaf(tx["locktime"]) == 7
    assert leaf(tx["vin"][0]["sequence"]) == 0xFFFFFFFE
    assert leaf(tx["vin"][0]["prev_vout"]) == 3
    assert leaf(tx["vout"][0]["value_sats"]) == 99_000


def test_prev_txid_is_shown_in_display_byte_order():
    # The input hash is stored little-endian; explorers (and Core's RPC) show it reversed.
    out = decode_payload(tx_hex(), "tx")
    assert leaf(out["transactions"][0]["vin"][0]["prev_txid"]) == "ab" * 32


def test_no_baseline_means_nothing_is_marked_changed():
    out = decode_payload(tx_hex(), "tx")
    assert leaf(out["transactions"][0]["locktime"]) == 0
    assert out["transactions"][0]["locktime"]["changed"] is False


def test_baseline_marks_exactly_the_changed_fields():
    out = decode_payload(tx_hex(locktime=124), "tx", baseline_hex=tx_hex(locktime=0))
    tx = out["transactions"][0]
    assert tx["locktime"]["changed"] is True
    # Everything else is identical, so nothing else may light up.
    assert tx["version"]["changed"] is False
    assert tx["vin"][0]["sequence"]["changed"] is False
    assert tx["vout"][0]["value_sats"]["changed"] is False


def test_identical_payload_and_baseline_has_no_changes():
    h = tx_hex()
    tx = decode_payload(h, "tx", baseline_hex=h)["transactions"][0]
    assert not tx["locktime"]["changed"] and not tx["vout"][0]["value_sats"]["changed"]


def test_decodes_block_header_and_marks_merkle_root_change():
    good = make_block()
    root_bytes = bytes(range(32))
    bad = make_block(merkle_root=int.from_bytes(root_bytes, "little"))
    out = decode_payload(bad.serialize().hex(), "block", baseline_hex=good.serialize().hex())
    header = out["header"]
    assert leaf(header["merkle_root"]) == root_bytes[::-1].hex()
    assert header["merkle_root"]["changed"] is True
    assert leaf(header["nonce"]) == 42
    assert leaf(header["bits"]) == "207fffff"
    assert header["nonce"]["changed"] is False
    assert len(out["transactions"]) == 1


def test_block_with_baseline_of_different_height_flags_the_coinbase():
    out = decode_payload(block_hex(height=124), "block", baseline_hex=block_hex(height=125))
    # height is committed in the coinbase scriptSig, so that script must differ
    assert out["transactions"][0]["vin"][0]["scriptSig_asm"]["changed"] is True


class TestScriptAsm:
    def test_empty_script(self):
        assert _script_asm(b"") == "(empty)"

    def test_p2wpkh_script_is_readable(self):
        asm = _script_asm(P2WPKH_SPK)
        assert asm.endswith("11" * 20)

    def test_truncated_push_does_not_raise(self):
        # OP_PUSHDATA1 claiming bytes that are not there: must degrade, not 500.
        out = _script_asm(bytes([0x4C, 0x05, 0x01]))
        assert isinstance(out, str) and out
