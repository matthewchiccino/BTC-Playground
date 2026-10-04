# Architecture

## The idea in one paragraph

Ask a real Bitcoin Core node "would you accept this?" for a payload built to be
wrong, using calls that **never change state**, then show its verbatim answer
beside the C++ that produced it. One shared regtest node serves every visitor
because nothing is ever broadcast or mined at serve time.

## Request lifecycle

```
Browser ──POST /build {scenario_id, override?}──▶ main.py
   validate (schema patterns + per-scenario bounds from the catalog)
   mutations.<fn>() ── RPC ──▶ bitcoind   builds payload_hex + baseline_hex
   decode.py        ── no RPC ──          labeled fields, changed-vs-baseline marked
   buildcache.store(payload_hex) ──▶ build_id   (opaque, expires in 120s)
◀── payload, baseline, decoded view, editable spec + hint, build_id

Browser ──POST /submit {build_id}──▶ main.py
   buildcache.get(build_id)           the ONLY source of bytes sent to the node
   block: getblocktemplate {mode: proposal}   tx: testmempoolaccept
   verdict = reject string | accepted;  SOURCES[verdict] ──▶ citation
◀── rpc request/response, elapsed_ms, verdict, rule_type, source
```

## Components

| Piece | Responsibility |
|---|---|
| `scenarios.py` | The catalog: pure data (title, kind, expected string, explanation, editable input, hint). |
| `mutations.py` | One builder per scenario. Transactions: node wallet signs, we edit bytes. Blocks: Core's vendored `test_framework`. |
| `sources.py` | Rejection string → file, function, lines, snippet, permalink, pinned to one Core commit. |
| `gen_sources.py` | Scans Core's source for every call site of a rejection string; diffs against `sources.py`. |
| `main.py` | HTTP API, validation, body cap, CORS, rate limits. |
| `buildcache.py` | Short-lived memory of what `/build` produced. A cache, not a store. |
| `ratelimit.py` | In-memory per-IP sliding window; picks the real client IP behind Fly/Caddy. |
| `decode.py` | Bytes → labeled fields with change markers (drives the UI diff). |
| `setup_chain.py` | Mines the frozen chain once, writes `fixtures.json` (UTXOs, fixed scratch addresses). |
| `vendor/test_framework/` | Bitcoin Core's own test code, verbatim. Never edited. |

## Why it is safe to expose

- **Read-only validation only.** `/submit` calls `getblocktemplate` (proposal mode) or `testmempoolaccept`. Neither mutates the node ([ADR 0001](decisions/0001-read-only-validation.md)). A unit test asserts no other RPC is reachable for any scenario.
- **Clients cannot supply bytes.** `/submit` takes an opaque token and looks up what this process built ([ADR 0003](decisions/0003-build-then-submit-by-token.md)).
- **Tight input schema.** Ids and tokens match strict patterns; unknown fields are rejected; bodies over 1 KB get 413; numeric/hex/choice overrides are bounded by the catalog.
- **Rate limits** per real client IP; `/health` is deliberately exempt so an orchestrator can always probe.
- **Errors don't leak.** Failures return a generic 502 and log the detail server-side.

## Deployment shape

One container, three processes supervised by `entrypoint.sh`:
`bitcoind` → `setup_chain.py` (re-mines every boot) → `uvicorn :8000` (localhost only)
→ `caddy :$PORT`. Caddy serves the built frontend and proxies `/api/*` to
uvicorn, so production is one origin and CORS never applies. If any process
dies the container exits and the orchestrator restarts it; boot is stateless, so
that is cheap and correct ([ADR 0002](decisions/0002-frozen-chain-stateless-boot.md)). Deployed on Fly.io with an always-on machine and a `/api/health` check.

## What "frozen chain" buys you

`setup_chain.py` mines once and records `frozen_tip_height` and fixture UTXOs.
Scenarios compute everything relative to that tip (e.g. the next block's height
is `frozen_tip_height + 1`), so boundaries are exact and repeatable: locktime 123
accepted, 124 rejected, always.
