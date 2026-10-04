# Decision records

Short records of choices that shaped the system, so they are not re-litigated
by accident. Format: context → decision → consequences. To change one, write a
new record that supersedes it (and say so here); don't silently edit history.
AI agents: treat these as constraints. If your task conflicts with one, stop and ask.

| # | Decision | Status |
|---|---|---|
| [0001](0001-read-only-validation.md) | Validate with read-only RPCs; never mutate the node | Accepted |
| [0002](0002-frozen-chain-stateless-boot.md) | Frozen chain, stateless boot, re-mine every start | Accepted |
| [0003](0003-build-then-submit-by-token.md) | `/submit` accepts a token, never client bytes | Accepted |
| [0004](0004-vendor-core-test-framework.md) | Vendor Bitcoin Core's test_framework verbatim | Accepted |
| [0005](0005-hand-verified-pinned-source-map.md) | Source citations are hand-verified, pinned to a commit, and audited | Accepted |
| [0006](0006-catalog-as-data-with-contract-tests.md) | Scenarios are data; conventions are enforced by tests | Accepted |
| [0007](0007-agent-guidance-in-agents-md.md) | One canonical agent guide (`AGENTS.md`), imported by `CLAUDE.md` | Accepted |
