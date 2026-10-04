# 0006: Scenarios are data; conventions are enforced by tests

**Status:** Accepted

**Context.** The original plan said adding a scenario should be "one entry and one
mutation, nothing else." Prose rules like that erode: adding the Locktime scenario
still needed a frontend edit, because hints were hardcoded per scenario id.

**Decision.** Everything the UI shows per scenario (explanation, input spec, hint)
lives in `scenarios.py`; the frontend renders it generically. `test_catalog.py`
turns each convention into a test whose failure message says what to fix, and
`test_boundaries.py` requires an accept/reject edge for every scenario.

**Consequences.**
- Adding a scenario touches backend only; forgetting a piece fails fast with instructions.
- Conventions survive contributors who haven't read the docs, including AI agents.
- The catalog is a stable contract between backend and UI; changing its shape means updating both and the contract tests.
