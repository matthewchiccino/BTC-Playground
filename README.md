# BTC Playground

[![CI](https://github.com/matthewchiccino/BTC-Playground/actions/workflows/ci.yml/badge.svg)](https://github.com/matthewchiccino/BTC-Playground/actions/workflows/ci.yml)

Break Bitcoin's consensus rules on purpose. A sandbox that builds deliberately
invalid Bitcoin blocks/transactions and submits them to a real local
`bitcoind` (regtest), showing the node's verbatim rejection string and the
exact C++ source line that produced it.

Seven scenarios today (coinbase oversubsidy, double spend, bad merkle root,
coinbase maturity, locktime, dust, fee too low). Each has an input you can nudge
to walk right up to the accept/reject boundary and watch the verdict flip.

## Quickstart

Prerequisites: macOS or Linux, Python 3, Node.js/npm, and Bitcoin Core
(`brew install bitcoin`; this project is verified against **v31.1**).

```bash
make setup   # one-time: Python venv, backend deps, frontend deps
make dev     # starts the regtest node (mining the frozen chain on first run),
             # the backend on :8000 and the frontend on :5173
```

Open **http://localhost:5173**. `make help` lists every command. Stop the node
with `make node-stop`.

<details>
<summary>Doing it by hand (what <code>make dev</code> wraps)</summary>

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
npm install --prefix frontend

./scripts/start_node.sh                       # regtest node
(cd backend && python3 setup_chain.py)        # mines the frozen chain, writes fixtures.json
(cd backend && uvicorn main:app --port 8000)  # backend, own terminal
npm run dev --prefix frontend                 # frontend, own terminal
```

Full reset (new chain, new fixtures): `make node-stop && make reset-chain && make node`.
</details>

## Testing

Three tiers, by what they need. CI runs all of them on every push.

```bash
make test               # unit: no node, no network, ~1s. Run constantly.
make check              # lint + build + unit: the pre-commit gate
make test-integration   # needs the node: every scenario + exact accept/reject boundaries
make test-sources       # needs internet: cited Core source lines still contain their strings
```

See [`docs/testing.md`](docs/testing.md).

## Working on this repo (humans and AI agents)

This repo is set up for AI-assisted development: a short agent guide, one-command
verification, contract tests that enforce conventions, decision records, and a
roadmap of scoped next steps.

| Start here | |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Commands, repo map, boundaries, conventions. (`CLAUDE.md` imports it.) |
| [`ROADMAP.md`](ROADMAP.md) | What's shipped, what's next, open decisions. |
| [`docs/`](docs/README.md) | Architecture, "add a scenario" playbook, testing, decision records. |
| [`docs/agentic-development.md`](docs/agentic-development.md) | The practices used here and why. |

## Running it as one container

`Dockerfile` builds a single image with bitcoind, the backend, and the built
frontend, all served through Caddy on one port -- no separate dev servers,
no CORS (frontend and API are same-origin behind Caddy's `/api/*` proxy).

```bash
make docker
docker run -d -p 8080:8080 --name btc-playground btc-playground
```

Then open **http://localhost:8080**. `PORT` is configurable (defaults to
8080; set `-e PORT=3000 -p 3000:3000` etc. to change it).

The chain is re-mined from scratch on every boot -- there's no persistent
volume for the bitcoin datadir, by design (see `setup_chain.py`,
`entrypoint.sh`, and [ADR 0002](docs/decisions/0002-frozen-chain-stateless-boot.md)).
That's what makes it safe for an orchestrator to just restart the whole
container on a failed `/api/health` check, instead of needing anything smarter.

```bash
docker stop btc-playground && docker rm btc-playground   # tear down
```

## Keeping `sources.py` honest

`gen_sources.py` scans Bitcoin Core's actual source tree at the pinned commit
(no local clone, no build -- fetches files individually and greps for
rejection call sites) and diffs the result against the hand-maintained
`sources.py`. Run it whenever re-pinning to a new Core tag, or just to audit:

```bash
cd backend
python3 gen_sources.py scan   # writes backend/sources_candidates.json
python3 gen_sources.py diff   # compares candidates against sources.py
```

`make test-sources` additionally asserts every cited line range still contains
its rejection string. Why it works this way: [ADR 0005](docs/decisions/0005-hand-verified-pinned-source-map.md).
