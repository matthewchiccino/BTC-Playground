# 0002: Frozen chain, stateless boot, re-mine every start

**Status:** Accepted

**Context.** Scenarios need a stable chain: fixed UTXOs, an already-spent output,
a known tip height. In a container, orchestrators restart processes freely.

**Decision.** `setup_chain.py` mines once (120 blocks plus fixtures) and records
`frozen_tip_height` and fixture UTXOs in `fixtures.json`; nothing mines after that.
In the container there is no volume for the datadir and `FORCE_SETUP=1`, so every
boot re-mines from scratch. `entrypoint.sh` exits the whole container if any of
bitcoind, uvicorn, or caddy dies.

**Consequences.**
- Boundaries are exact and repeatable (the next block is always `frozen_tip_height + 1`).
- Restart-on-failure is cheap and correct: there is no state to corrupt or migrate. Cost: ~15-20s boot, hence an always-on Fly machine and a 90s health grace period.
- `fixtures.json` is generated, gitignored, and excluded from the image; a stale copy would reference UTXOs that no longer exist.
- Never mine at serve time; it would shift every height-relative scenario.
