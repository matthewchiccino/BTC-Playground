"""The public explorer still returns what the mainnet strip relies on.

Catches upstream API drift; the unit tier stubs the explorer out entirely.
"""
import livechain


def test_explorer_returns_recent_blocks_newest_first():
    blocks = livechain._fetch()
    assert len(blocks) >= 2
    assert set(blocks[0]) == set(livechain.FIELDS)
    heights = [b["height"] for b in blocks]
    assert heights == sorted(heights, reverse=True)
    assert all(len(b["id"]) == 64 for b in blocks)
