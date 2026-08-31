# Consensus Lab — Build Plan

A handoff document for an AI coding agent. Optimized for **lightweight** and
**readable**, not for feature count.

Sections marked **DECIDE** are deliberately blank. Do not invent answers to
them — stop and ask.

---

## 0. Non-negotiable constraints

Read these before writing any code. They exist to stop the project from
tripling in size.

1. **No database.** No ORM, no migrations, no persistence layer. All state
   lives in the regtest chain and one JSON file.
2. **No authentication, no accounts, no sessions.**
3. **No websockets in v1.** The live `debug.log` pane is explicitly out of
   scope until v2.
4. **No free-form block editor in v1.** See §6 — this is the single biggest
   scope trap in the project.
5. **The backend is one Python package with roughly five files.** If it grows
   past that, something is wrong.
6. **Every scenario is declarative data, not bespoke code paths.** Adding a
   new attack should mean adding one dict entry and one small mutation
   function, and nothing else.

---

## 1. What the system actually does

For a given "attack scenario," the backend must produce three things:

| Pane | Content | Source |
|---|---|---|
| The Payload | Raw hex of the invalid tx or block | Built server-side |
| The Verdict | Bitcoin Core's verbatim rejection string | Read-only RPC |
| The Source | C++ snippet + permalink to the exact line | Hand-curated map |

That's it. Everything else is decoration.

---

## 2. Correct understanding of the node

### 2.1 The two read-only validation calls

**Transactions** — `testmempoolaccept([raw_hex])`

Returns a list with `allowed: bool` and, on failure, `reject-reason`. Does
not mutate the mempool or chain.

Important: this endpoint applies **both consensus and policy rules**, and
the returned string doesn't tell you which one fired. `bad-txns-in-belowout`
is consensus. `dust`, `min relay fee not met`, and `scriptsig-not-pushonly`
are policy. Treat this distinction as a first-class part of the product
(see §7) rather than papering over it — it is one of the most commonly
misunderstood things about Bitcoin, and surfacing it is a genuine
differentiator.

**Blocks** — `getblocktemplate({"mode": "proposal", "data": <block_hex>})`

Returns `null` on acceptance, or a rejection string. Two things the agent
must know:

- **Proof of work is not checked in proposal mode.** Core calls
  `TestBlockValidity` with `fCheckPOW = false`. You never mine an attack
  block. Do not write mining code.
- **The proposed block must build on the current tip.** Its `prevhash` must
  equal the current best block hash, or you get
  `inconclusive-not-best-prevblk` — a confusing error unrelated to the
  attack being demonstrated. This is why the chain must be frozen (§3).

### 2.2 The chain must be frozen during serving

Nothing mines while the app is running. The setup script mines once, then
the tip never moves. This guarantees:

- Proposal-mode blocks always have a valid `prevhash`.
- Fixture UTXOs are never consumed, because nothing is ever broadcast.
- Concurrent users cannot interfere with each other.

If you ever need to reset, delete the regtest datadir and re-run setup.

---

## 3. Setup script (`setup_chain.py`)

Run once, at container build or first boot. Idempotent — check whether the
fixture file already exists and exit early if so.

Steps:

1. Start `bitcoind -regtest` with a wallet loaded.
2. Mine ~120 blocks to a wallet address (coinbase maturity is 100 blocks;
   the surplus gives spendable headroom).
3. Create the fixture UTXOs the scenarios need. At minimum:
   - **`spendable_a`** — a normal confirmed UTXO, used as the input for most
     tx attacks.
   - **`already_spent`** — a UTXO that is spent by a transaction which has
     been **mined into a block**. This is what makes the double-spend demo
     return `bad-txns-inputs-missingorspent` rather than a generic missing-
     input error.
   - **DECIDE:** any additional fixtures your chosen scenarios require.
4. Write `fixtures.json` containing txids, vouts, amounts, addresses, and
   the frozen tip hash/height.
5. Stop mining. Never mine again.

The backend loads `fixtures.json` at startup and treats it as read-only.

---

## 4. Building the payloads — the lightweight path

There are two ways to construct these artifacts. Pick the lighter one for
each case.

### 4.1 Transactions: let Core's wallet sign, then mutate the bytes

Do **not** vendor Core's `key.py` and implement signing in Python. Instead:

1. `createrawtransaction` — build a valid baseline tx from a fixture UTXO.
2. `signrawtransactionwithwallet` — Core signs it.
3. Deserialize the signed hex in Python, apply the scenario's mutation,
   re-serialize.
4. `testmempoolaccept` the result.

This keeps the Python surface tiny. Most attacks (over-spend, double spend,
bad locktime, oversized output count) are byte surgery on an already-valid
transaction, and signature invalidity is often *itself* the lesson.

Note: some mutations invalidate the signature as a side effect, which
produces `mandatory-script-verify-flag-failed` instead of the intended
error. When that happens, either pick a mutation that doesn't touch the
signed fields, or re-sign after mutating, or make the signature failure the
point of that scenario. **Flag any scenario where this bites rather than
silently working around it.**

### 4.2 Blocks: vendor the minimum from Core's test framework

Blocks need coinbase construction and merkle root computation, which are
genuinely annoying to hand-roll. Vendor these files from the Bitcoin Core
repo into `backend/vendor/test_framework/`:

`messages.py`, `blocktools.py`, `script.py`, `script_util.py`,
`address.py`, `util.py`, `crypto/` (as required by the imports)

Rules for vendoring:
- **DECIDE:** which Core release tag to pin to. Whatever version of
  `bitcoind` you actually install — check `bitcoind --version` and match it.
- Copy verbatim. Do not edit vendored files. Record the tag and commit SHA
  in a `VENDORED.md` alongside them.
- Import them, don't fork them. If something doesn't import cleanly, the
  answer is to vendor its dependency, not to patch it.

Block flow: `getblocktemplate` (normal mode) → build block with
`create_block` / `create_coinbase` → mutate → submit as proposal.

---

## 5. Backend structure

```
backend/
  main.py            # FastAPI app, 2 endpoints, ~60 lines
  node.py            # thin RPC wrapper, ~50 lines
  scenarios.py       # the catalog — declarative, one entry per attack
  mutations.py       # one small function per attack
  sources.py         # rejection string -> C++ location map
  fixtures.json      # written by setup, read-only at runtime
  vendor/test_framework/
```

### Endpoints

- `GET /scenarios` — returns the catalog for the frontend to render.
- `POST /run` — body `{"scenario_id": "..."}`, returns
  `{payload_hex, verdict, source}`.

That's the whole API. Resist adding more.

### Scenario catalog shape

Each entry is data:

```
id, title, kind ("tx" | "block"), fixture_key,
mutation ("name of function in mutations.py"),
expected_reject_reason,
rule_type ("consensus" | "policy"),
explanation  # DECIDE: you write this copy
```

The `expected_reject_reason` field is not used to fake the output — the
verdict always comes from the live node. It exists so a test can assert
that reality still matches the catalog. If Core changes an error string in
a future release, that test fails loudly instead of the UI quietly lying.
Write that test.

---

## 6. The scope trap — read this carefully

Your write-up describes "a visual, editable structure of a block/transaction"
where users "click fields and mutate them." **That is the most expensive part
of the project by a wide margin, and it is not where the insight lives.**

A free-form editor means: a schema for every field, live re-serialization,
validation of user input before it even reaches the node, undo state, and
a UI that gracefully handles nonsense. It is weeks of frontend work in
service of a backend that is a few hundred lines.

**v1 ships fixed scenario buttons.** A sidebar list of named attacks; click
one; see three panes. This delivers the entire educational thesis with
about 5% of the frontend cost.

The editor is v1.5, and only if v1 is deployed and someone has actually used
it. If you build the editor first, the honest prediction is that this
project joins the half-finished repos.

**DECIDE:** accept this, or explicitly overrule it. Do not let it be decided
by drift.

---

## 7. The source-mapping layer

This is the feature that makes the project distinctive, so do it properly
and manually.

`sources.py` holds a hand-written dict:

```
"bad-cb-amount": {
    "file": "src/validation.cpp",
    "function": "ConnectBlock",
    "lines": [start, end],
    "permalink": "https://github.com/bitcoin/bitcoin/blob/<COMMIT_SHA>/src/validation.cpp#L<start>-L<end>",
    "snippet": "<the actual C++ lines, copied in>",
}
```

Rules:

- **Use a commit-SHA permalink, never a branch name.** Line numbers on
  `master` drift within weeks and every link silently becomes wrong.
- Pin to the same Core tag as the vendored test framework and the running
  `bitcoind`. One version, everywhere.
- Hand-map roughly 8–12 errors. Do not attempt to auto-derive this from the
  source tree; the mapping from error string to the enclosing check is not
  mechanically extractable in the general case, and a wrong deep-link is
  worse than no deep-link.
- Include the `rule_type` (consensus vs policy) in what you display. A user
  learning that `dust` is *not* a consensus rule — that a miner could
  include it and the block would be perfectly valid — is learning something
  most Bitcoin holders don't know.

---

## 8. Frontend

One page. React. **DECIDE:** styling approach and visual design — that's
yours, not the agent's.

Layout: scenario list on the left, three panes on the right. The Verdict
pane is the hero; make the raw Core string prominent and monospaced rather
than wrapping it in friendly language. The verbatim string *is* the product.

No routing library. No state management library. `useState` and `fetch` are
sufficient for two endpoints.

---

## 9. Build order

Ship each step before starting the next. Each is independently verifiable.

1. **Node up.** `bitcoind -regtest` in Docker, RPC reachable. Verify by
   hand with `bitcoin-cli`.
2. **Setup script.** Mines the chain, writes `fixtures.json`. Re-runnable
   from scratch.
3. **One scenario, no web app.** A Python script that builds the coinbase
   over-subsidy block, calls proposal mode, prints `bad-cb-amount`. This is
   the riskiest technical step — do it before any web code exists. If this
   works, the project works.
4. **Second and third scenarios** as plain scripts: bad merkle root, double
   spend.
5. **Wrap in FastAPI.** Two endpoints, returning payload + verdict.
6. **Source map** for the three scenarios.
7. **Frontend**, fixed scenario buttons.
8. **Deploy.** Single container, node and API together.
   **DECIDE:** hosting target.
9. **Stop.** Get someone to use it before adding anything.

---

## 10. v2 candidates (do not start these now)

- Free-form field editor.
- Live `debug.log` streaming. Note the real limitation: the log is shared
  across all concurrent users, so a "your node's reaction" pane will
  interleave strangers' requests. Solvable, but not trivially, and not in
  v1.
- Policy-vs-consensus toggle showing which rules a miner could ignore.
- More scenarios (BIP68 sequence locks, witness malleation, sigop limits).

**On the Rust/Go differential validator (Phase 2 of your write-up):** that
is not a phase of this project. It's a separate project of roughly ten
times the size, and writing a consensus-compatible validator is a genuinely
hard multi-month undertaking that has defeated experienced engineers. It is
an excellent thing to want to do. Frame it as its own repo, after this one
is shipped, and don't let it hang over v1 as unfinished business.

---

## 11. Open decisions to resolve before coding

- [ ] **DECIDE:** Core version to pin (bitcoind, vendored framework, permalinks).
- [ ] **DECIDE:** The v1 scenario list — which attacks, in what order.
- [ ] **DECIDE:** Explanation copy for each scenario (your voice, not the agent's).
- [ ] **DECIDE:** Accept or overrule the "no editor in v1" constraint (§6).
- [ ] **DECIDE:** Visual design and styling approach.
- [ ] **DECIDE:** Hosting target.
- [ ] **DECIDE:** Project name — "Consensus Lab" is a working title.