# Playbook: add a scenario

The contract: **one catalog entry + one mutation**, plus a source citation if the
rejection string is new, plus a boundary row. `backend/tests/unit/test_catalog.py`
enforces the shape and tells you what is missing. No `App.jsx` change should be
needed (inputs and hints are data).

## 0. Establish the facts first (before writing code)

Do not write a rejection string from memory. Trigger the failure on the live
node (`bitcoin-cli ... testmempoolaccept` or `getblocktemplate` proposal) and
note the exact string. Decide: **consensus** (enforced in block validation) or
**policy** (mempool/relay only)? The `kind` follows: consensus failures of whole
blocks use `block`; mempool-only rules use `tx`.

## 1. Checklist

1. **`backend/mutations.py`**: add `def my_scenario(<field>: <type> | None = None) -> dict`. Return `payload_hex`, `baseline_hex` (a valid twin so the UI can diff), `build_calls`, `editable_value`, and `hint_value`. The parameter name must equal the catalog's `editable.field` and default to `None`. Register it in `MUTATIONS`.
2. **`backend/scenarios.py`**: add the entry. `editable.hint` is shown under the input; `{hint_value}` is replaced by the mutation's `hint_value`. Lead the explanation with the punchline; match the tone of the others.
3. **`backend/sources.py`**: if the string is new, add its entry (file, function, line range, snippet, `rule_type`). Find the line in the pinned source, not on `master`. Use `python3 backend/gen_sources.py scan && python3 backend/gen_sources.py diff` to see *every* site that produces the string, and use `also_produced_by` where more than one can fire.
4. **`backend/setup_chain.py`**: only if you need a new fixed destination address (so baseline and attack share it and the diff shows only your change). Add the key under `scratch_addresses`, and to the stub in `tests/conftest.py`. Existing local chains need that key added to `fixtures.json` (or `make reset-chain && make node`).
5. **`backend/tests/integration/test_boundaries.py`**: add a row to `EDGES` giving the value just inside and just outside the boundary, derived from `hint_value`. `test_every_scenario_has_an_edge_test` fails until you do.
6. **Verify:** `make check`, then `make test-integration`, then `make test-sources`, then try it in the UI (`make dev`).

## 2. Worked example: Locktime (`locktime_nonfinal`)

- Rule: `ContextualCheckBlock` rejects any tx failing `IsFinalTx(tx, height, ...)`. A height-style locktime is final only if it is **strictly below** the including block's height. The proposed block is `frozen_tip_height + 1 = 124`, so 123 passes and 124 fails. That is the whole boundary, and it is the `hint_value`.
- Gotcha found by reading the code, not guessing: a tx whose inputs are all `0xFFFFFFFF` is "final" and ignores its locktime. The mutation sets the input sequence to `0xFFFFFFFE` so the locktime means something.
- Citation: lines 4193-4195 of `src/validation.cpp`. The same string is also produced by the BIP68 relative-locktime check in `ConnectBlock`, recorded as `also_produced_by` with a note on why it is not the one that fires.
- Baseline: the same block with locktime 0, so the hex diff highlights exactly the four locktime bytes.

## 3. Common mistakes

- Citing the first grep hit. The same string can come from two checks; confirm which one fires for *your* payload.
- Calling a rule consensus because the node rejected it. Mempool rejection alone does not make it consensus.
- Choosing a `max` in the catalog above what the API schema allows (`override_value_sats` ≤ 100,000,000,000); a contract test catches this.
