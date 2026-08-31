# Vendored files

Source: https://github.com/bitcoin/bitcoin
Tag: `v31.1`
Commit: `9be056a8a72b624dae9623b2f7bded92c2a21c91`

Local `bitcoind`/`bitcoin-cli` are also v31.1 (installed via `brew install bitcoin`).
Source permalinks in `backend/sources.py` are pinned to the same commit.

Copied verbatim from `test/functional/test_framework/` at that commit, plus the
minimal dependency closure needed for them to import cleanly. Do not edit these
files — if something doesn't import, vendor its dependency instead of patching.

- `messages.py`
- `blocktools.py`
- `script.py`
- `script_util.py`
- `address.py`
- `util.py`
- `coverage.py` (dep of nothing we call directly; pulled in transitively)
- `authproxy.py` (dep of coverage.py)
- `descriptors.py` (dep of address.py)
- `key.py` (dep of address.py)
- `segwit_addr.py` (dep of address.py)
- `crypto/ripemd160.py`
- `crypto/siphash.py`
- `crypto/secp256k1.py` (dep of key.py)
