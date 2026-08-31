# My BTC Playground

Break Bitcoin's consensus rules on purpose. A sandbox that builds deliberately
invalid Bitcoin blocks/transactions and submits them to a real local
`bitcoind` (regtest), showing the node's verbatim rejection string and the
exact C++ source line that produced it.

## Prerequisites

- macOS with [Homebrew](https://brew.sh)
- Python 3
- Node.js / npm

Install Bitcoin Core if you haven't already:

```bash
brew install bitcoin
```

## First-time setup

Run these once.

```bash
# 1. Python environment + backend deps
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn requests pytest

# 2. Frontend deps
npm install --prefix frontend
```

## Starting the app

You need three things running: the regtest node, the backend, and the frontend.

**1. Start the node** (mines the frozen chain and writes `fixtures.json` the
first time you run it):

```bash
./scripts/start_node.sh
source .venv/bin/activate
cd backend && python3 setup_chain.py && cd ..
```

**2. Start the backend** (from `backend/`, in its own terminal tab):

```bash
source .venv/bin/activate
cd backend
uvicorn main:app --port 8000
```

**3. Start the frontend** (from `frontend/`, in another terminal tab):

```bash
npm run dev --prefix frontend
```

Then open **http://localhost:5173**.

## Stopping / resetting

Stop the node:

```bash
./scripts/stop_node.sh
```

To fully reset the chain (new fixtures, new frozen tip), delete the local
node data and fixtures, then redo setup:

```bash
rm -rf .bitcoin-regtest backend/fixtures.json
./scripts/start_node.sh
source .venv/bin/activate && cd backend && python3 setup_chain.py
```

## Sanity check without the web app

```bash
source .venv/bin/activate
cd backend
python3 manual_check.py   # prints each scenario's verdict
python3 -m pytest test_scenarios.py -v   # asserts verdicts match the catalog
python3 -m pytest test_sources.py -v     # asserts sources.py still cites real lines
```

## Keeping `sources.py` honest

`gen_sources.py` scans Bitcoin Core's actual source tree at the pinned commit
(no local clone, no build -- fetches files individually and greps for
rejection call sites) and diffs the result against the hand-maintained
`sources.py`. Run it whenever re-pinning to a new Core tag, or just to audit:

```bash
python3 gen_sources.py scan   # writes backend/sources_candidates.json
python3 gen_sources.py diff   # compares candidates against sources.py
```
