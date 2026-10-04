# Testing

## Three tiers, by what they need

| Tier | Command | Needs | What it proves |
|---|---|---|---|
| unit | `make test` | nothing, ~1s | Logic and contracts: validation, rate limiting, build cache, decoder, scanner heuristics, catalog shape, read-only-RPC guarantee. |
| integration | `make test-integration` | live regtest node | Every scenario really gets the catalog's verdict, and the exact accept/reject **boundary** of each. |
| network | `make test-sources` | internet | Every cited line range in Core's source at the pinned commit still contains its rejection string. |

Plain `pytest` runs only unit (`backend/pytest.ini`). The tiers are directories
under `backend/tests/` and are auto-marked, so there is no decorator to forget.
Unit tests need no chain: `tests/conftest.py` points `BTC_FIXTURES_PATH` at a stub
when no real `fixtures.json` exists.

## What CI runs

`.github/workflows/ci.yml`: frontend lint+build, unit tests, integration (installs
checksum-verified Bitcoin Core 31.1, mines a fresh chain, runs the integration
tier), source citations, and a Docker image build. The integration job was
dry-run locally against a fresh node on a different port before being relied on.

## The tests worth knowing

- **Boundary tests** (`integration/test_boundaries.py`): each scenario's threshold is derived from the mutation's `hint_value` and checked against the node on both sides. This verifies the *hint text shown to users is true*, and fails loudly if a Core upgrade moves a threshold.
- **Catalog contract** (`unit/test_catalog.py`): turns "add one entry and one mutation" into failures that say what to fix. Includes that `editable.field` is a real optional parameter of the mutation (a typo would otherwise be a runtime 502).
- **Read-only guarantee** (`unit/test_api.py`): for every scenario, `/submit` only ever invokes `getblocktemplate` or `testmempoolaccept`.

## Do the tests actually test?

A suite that cannot fail is decoration. `scripts/mutation_check.py` breaks the
code on purpose (inverts a comparison, reverses a byte order, removes a bound
check, swaps in a write RPC, ...) in a scratch copy and confirms the unit tier
goes red for each. Run it after meaningful test changes; it is not part of CI
because its patterns track source text and need updating when that text moves.

```bash
.venv/bin/python scripts/mutation_check.py
```

## Adding tests

- New logic with no node dependency → `tests/unit/`. Mock `main.rpc`; build payload hex with `tests/unit/helpers.py`.
- New scenario → boundary row in `EDGES` (see [`adding-a-scenario.md`](adding-a-scenario.md)).
- Prefer testing a contract (what must stay true) over a snapshot (what it happens to return).
