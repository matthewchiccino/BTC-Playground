"""Tiny builders for real, deserializable tx/block hex -- no node involved.

Uses the same vendored Core test_framework classes the app itself builds
payloads with, so what these produce is exactly what decode.py must handle.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "vendor"))

from test_framework.blocktools import create_coinbase  # noqa: E402
from test_framework.messages import COutPoint, CBlock, CTransaction, CTxIn, CTxOut  # noqa: E402

P2WPKH_SPK = bytes.fromhex("0014" + "11" * 20)


def make_tx(value_sats: int = 99_000, locktime: int = 0, sequence: int = 0xFFFFFFFE) -> CTransaction:
    tx = CTransaction()
    tx.version = 2
    tx.nLockTime = locktime
    tx.vin = [CTxIn(COutPoint(int.from_bytes(bytes([0xAB]) * 32, "little"), 3), b"", sequence)]
    tx.vout = [CTxOut(value_sats, P2WPKH_SPK)]
    return tx


def tx_hex(**kwargs) -> str:
    return make_tx(**kwargs).serialize().hex()


def make_block(height: int = 124, merkle_root: int | None = None) -> CBlock:
    block = CBlock()
    block.nVersion = 0x20000000
    block.hashPrevBlock = int.from_bytes(bytes([0x01]) * 32, "little")
    block.nTime = 1_700_000_000
    block.nBits = 0x207FFFFF
    block.nNonce = 42
    block.vtx = [create_coinbase(height=height)]
    block.hashMerkleRoot = block.calc_merkle_root() if merkle_root is None else merkle_root
    return block


def block_hex(**kwargs) -> str:
    return make_block(**kwargs).serialize().hex()
