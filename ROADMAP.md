# Roadmap

What is shipped, what is next, and what is deliberately **not** being built.
Each "next" item is written to be handed to an agent or a person cold: why it
matters, the smallest useful slice, and an objective "done when". Update this
file in the same change that ships (or reshapes) an item.

## Shipped

| Area | State |
|---|---|
| Scenarios | 7: coinbase oversubsidy, double spend, bad merkle root, coinbase maturity, locktime (consensus); dust, fee too low (policy) |
| Flow | Build → Submit → Verdict; raw response and verdict side by side; editable input per scenario with a live boundary hint |
| Source map | Hand-verified citations pinned to one Core commit, audited by `gen_sources.py` and `make test-sources` |
| Quality | Unit tests (mutation-checked), per-scenario boundary tests against a live node, CI on every push |
| Deployment | Single container (bitcoind + backend + Caddy), stateless boot, on Fly.io |

## Next, in priority order

### 1. Script Lab: failures inside the Script interpreter
- **Why:** every current scenario fails at the block/transaction layer. None exercise Bitcoin Script (signatures, spending conditions), which is the part most relevant to wallet, custody, and protocol work.
- **Smallest slice:** one scenario, `bad_signature` (a valid spend with one signature bit flipped), rejected with a `mandatory-script-verify-flag-failed` string. Same catalog + mutation + source + boundary-row shape as the others.
- **Then:** more script scenarios (wrong sighash type, non-DER / high-S as a *policy* failure, in-script `OP_CHECKLOCKTIMEVERIFY`), then a step-through stack trace panel.
- **Done when:** the scenario passes `make test-integration`, its citation passes `make test-sources`, and the UI explains consensus-vs-policy for it correctly.
- **Unknowns to resolve first:** whether the vendored `test_framework` has enough signing/sighash helpers (see `backend/vendor/VENDORED.md`), and whether the trace panel is our own small interpreter cross-checked against the node's verdict, or a wrapper around an existing debugger. See [open decisions](#open-decisions-for-a-human).

### 2. Frontend tests and `App.jsx` decomposition
- **Why:** the backend is thoroughly tested; the frontend has lint and a build, nothing more. `App.jsx` is large and orchestrates every stage.
- **Smallest slice:** Vitest + Testing Library; test the `EditableHint` placeholder rendering and the stage progression (build → submit → verdict) with a mocked `fetch`. Extract the three stage panes into components only as far as the tests need.
- **Done when:** `npm test` runs in CI's frontend job and fails on a broken stage transition.

### 3. Shareable permalinks
- **Why:** "here is the exact input where the verdict flips" is the product's best moment, and right now it can't be linked to.
- **Smallest slice:** `?scenario=dust_output&value=294` selects the scenario and prefills the input. Frontend only; validate against the catalog's min/max.
- **Done when:** loading such a URL lands on the right scenario with the input filled; invalid values are ignored, not trusted.

### 4. Differential validation (the original "phase 2")
- **Why:** feed identical payloads to Bitcoin Core *and* a second implementation and surface disagreements. This is how real consensus bugs are found.
- **Smallest slice:** a CLI/test harness (not UI) comparing Core's verdict with `libbitcoinconsensus` or another implementation on the existing scenarios.
- **Blocked on:** an [open decision](#open-decisions-for-a-human) (which implementation, and whether it ships in the 512 MB container).

### 5. Node resilience
- **Why:** the local regtest node has twice shut itself down mid-run with `Operation not permitted` on its own datadir (`node_debug.log`: "Flushing block file to disk failed"). Cause not yet established (suspected macOS file-protection or sandbox interaction; unproven).
- **Smallest slice:** reproduce outside any tool sandbox, then decide between a documented workaround, a datadir outside protected folders, or a no-op. Also confirm `/health` goes 503 when the node dies (unit-tested, but not yet exercised against a real crash).
- **Done when:** a known cause is written down in `docs/` and `AGENTS.md`'s gotcha is replaced by a fix or a precise workaround.

### 6. Re-pin to a newer Bitcoin Core tag
- **Why:** citations are pinned to v31.1; Core moves.
- **Procedure:** bump `COMMIT`/bitcoind version together (`sources.py`, `Dockerfile`, CI `BITCOIN_VERSION`, `VENDORED.md`), run `gen_sources.py scan && diff`, fix every moved line, run all test tiers. A verdict string that changed is a finding, not a failure to hide.

## Not building (constraints carried from the original plan)

No database or persistence, no accounts/auth, no free-form block editor (the
original plan calls this the biggest scope trap), no websockets / live
`debug.log` pane until a deliberate decision to relax this. See
[`docs/history/build-plan.md`](docs/history/build-plan.md) §0 and
[`docs/decisions/`](docs/decisions/).

## Open decisions for a human

Agents should stop and ask rather than pick an answer here.

1. **Script Lab trace:** write our own interpreter (more impressive, more correctness risk) or wrap an existing debugger?
2. **Differential testing target:** which second implementation, and is the extra weight acceptable on the 512 MB Fly machine?
3. **Live `debug.log` pane:** worth relaxing the "no websockets" constraint, or stay out of scope?
