"""Deserialize a payload's raw bytes back into labeled fields, using the same
vendored CBlock/CTransaction classes used to build it. No RPC calls, no new
dependencies -- this is the exact inverse of what mutations.py does.

When a baseline is supplied, every leaf value is annotated with whether it
differs from the baseline at the same position, so the frontend can highlight
mutated fields the same way it highlights mutated hex bytes.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "vendor"))

from test_framework.messages import CBlock, CTransaction, ser_uint256  # noqa: E402
from test_framework.script import CScript  # noqa: E402

_NO_BASELINE = object()


def _hash_hex(u: int) -> str:
    """uint256 int (internal byte order) -> conventional display hex string."""
    return ser_uint256(u)[::-1].hex()


def _script_asm(script_bytes: bytes) -> str:
    if not script_bytes:
        return "(empty)"
    try:
        return " ".join(
            token.hex() if isinstance(token, (bytes, bytearray)) else str(token)
            for token in CScript(script_bytes)
        )
    except Exception:
        return f"<unparseable: {script_bytes.hex()}>"


def _decode_tx(tx: CTransaction) -> dict:
    return {
        "txid": tx.txid_hex,
        "version": tx.version,
        "locktime": tx.nLockTime,
        "vin": [
            {
                "prev_txid": _hash_hex(vin.prevout.hash),
                "prev_vout": vin.prevout.n,
                "scriptSig_asm": _script_asm(vin.scriptSig),
                "sequence": vin.nSequence,
            }
            for vin in tx.vin
        ],
        "vout": [
            {"value_sats": vout.nValue, "scriptPubKey_asm": _script_asm(vout.scriptPubKey)}
            for vout in tx.vout
        ],
    }


def _decode_raw(hexdata: str, kind: str) -> dict:
    raw = bytes.fromhex(hexdata)
    if kind == "block":
        block = CBlock()
        block.deserialize(io.BytesIO(raw))
        return {
            "header": {
                "version": block.nVersion,
                "prev_block_hash": _hash_hex(block.hashPrevBlock),
                "merkle_root": _hash_hex(block.hashMerkleRoot),
                "time": block.nTime,
                "bits": f"{block.nBits:08x}",
                "nonce": block.nNonce,
            },
            "transactions": [_decode_tx(tx) for tx in block.vtx],
        }
    tx = CTransaction()
    tx.deserialize(io.BytesIO(raw))
    return {"transactions": [_decode_tx(tx)]}


def _baseline_lookup(container, key):
    if container is _NO_BASELINE:
        return _NO_BASELINE
    try:
        return container[key]
    except (KeyError, IndexError, TypeError):
        return _NO_BASELINE


def _annotate(value, baseline_value):
    if isinstance(value, dict):
        return {k: _annotate(v, _baseline_lookup(baseline_value, k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_annotate(item, _baseline_lookup(baseline_value, i)) for i, item in enumerate(value)]
    return {"value": value, "changed": baseline_value is not _NO_BASELINE and value != baseline_value}


def decode_payload(payload_hex: str, kind: str, baseline_hex: str | None = None) -> dict:
    decoded = _decode_raw(payload_hex, kind)
    baseline_decoded = _decode_raw(baseline_hex, kind) if baseline_hex else _NO_BASELINE
    return _annotate(decoded, baseline_decoded)
