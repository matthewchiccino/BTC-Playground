"""Asserts every SOURCES entry's literal reject string still appears inside
its declared line range in the actual Core source at the pinned commit.

Independent of the live node -- only needs internet access to fetch files
from raw.githubusercontent.com. Catches hand-edit typos/drift in sources.py
itself; does not re-derive correctness on its own (see `gen_sources.py diff`
for finding new/moved/ambiguous call sites across the whole source tree).
"""
import re

import pytest
import requests

from sources import COMMIT, SOURCES

RAW_URL = "https://raw.githubusercontent.com/bitcoin/bitcoin/{sha}/{path}"
_file_cache: dict[str, list[str]] = {}


def _fetch_lines(path: str) -> list[str]:
    if path not in _file_cache:
        resp = requests.get(RAW_URL.format(sha=COMMIT, path=path), timeout=15)
        resp.raise_for_status()
        _file_cache[path] = resp.text.splitlines()
    return _file_cache[path]


def _assert_literal_in_range(key: str, entry: dict):
    lines = _fetch_lines(entry["file"])
    start, end = entry["lines"]
    assert 1 <= start <= end <= len(lines), (
        f"{key}: line range {entry['lines']} out of bounds for {entry['file']} ({len(lines)} lines)"
    )
    window = "\n".join(lines[start - 1 : end])
    pattern = re.compile(rf'"{re.escape(key)}[^"]*"')
    assert pattern.search(window), (
        f"{key}: literal not found in {entry['file']} lines {start}-{end} at commit {COMMIT}"
    )


@pytest.mark.parametrize("key", list(SOURCES), ids=list(SOURCES))
def test_source_line_range_contains_literal(key):
    _assert_literal_in_range(key, SOURCES[key])


def _also_produced_by_cases():
    cases = []
    for key, entry in SOURCES.items():
        for i, alt in enumerate(entry.get("also_produced_by", [])):
            cases.append((f"{key}[alt{i}]", alt))
    return cases


@pytest.mark.parametrize("id_key,alt", _also_produced_by_cases(), ids=[c[0] for c in _also_produced_by_cases()])
def test_also_produced_by_line_range_contains_literal(id_key, alt):
    key = id_key.split("[")[0]
    _assert_literal_in_range(key, alt)
