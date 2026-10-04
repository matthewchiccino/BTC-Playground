# Agentic development in this repo

This project is built with AI coding agents, and the repo is arranged so that
doing so is safe, fast, and checkable. This page lists the practices, **where
each one lives in the repo**, and why. It is a description of what is here, not a
claim that this is the only way.

The through-line: **an agent is only as good as its feedback loop.** Everything
below is a way to make "is this right?" cheap to answer, objective, and hard to
skip.

## 1. A short map, not a manual

- [`AGENTS.md`](../AGENTS.md) is about 100 lines: commands, repo map, boundaries, gotchas. It links to detail instead of inlining it.
- [`CLAUDE.md`](../CLAUDE.md) *imports* it (`@AGENTS.md`) and adds only tool-specific notes, so there is one source of truth and nothing to drift ([ADR 0007](decisions/0007-agent-guidance-in-agents-md.md)).
- **Why:** instructions that are too long stop being followed; instructions that are duplicated disagree. A rule that can be a test should be a test (next sections), so the guide stays short.

## 2. One command, fast, honest verification

- `make test` runs the unit tier in about a second with **no node and no network**; `make check` adds lint and build; `make help` lists everything. CI runs the same commands.
- Tests are tiered by what they need (`unit` / `integration` / `network`), selected by directory, so the cheap loop is the default and an agent can't accidentally depend on a running node.
- **Why:** an agent that can't verify cheaply either skips verification or burns context on it. "Green locally" must mean "green in CI".

## 3. Make the rules executable

- [`test_catalog.py`](../backend/tests/unit/test_catalog.py) turns "a scenario is one catalog entry plus one mutation" into failures that say what to fix: unknown mutation, missing source entry, `editable.field` that isn't a parameter of the mutation, hint with an unsupported placeholder.
- [`test_boundaries.py`](../backend/tests/integration/test_boundaries.py) requires an exact accept/reject edge for every scenario, and checks the number printed in the UI against the live node.
- A unit test asserts `/submit` can only reach the two read-only RPCs, for every scenario ([ADR 0001](decisions/0001-read-only-validation.md)).
- **Why:** prose conventions erode. The Locktime scenario originally still needed a frontend edit despite the "one entry, one mutation" rule; making hints catalog data and adding a contract test closed that gap permanently ([ADR 0006](decisions/0006-catalog-as-data-with-contract-tests.md)).

## 4. Ground truth over model memory

- The provenance rule (in `AGENTS.md`): a rejection string, line number, or consensus-vs-policy claim is written only after triggering it on the live node and reading the **pinned** source.
- The system enforces this mechanically: `make test-sources` checks every cited line range in Core's source; `gen_sources.py` finds *other* call sites for the same string ([ADR 0005](decisions/0005-hand-verified-pinned-source-map.md)).
- **Why this matters here specifically:** the `dust` citation was first written pointing at the wrong function (`IsStandardTx`) because the same string is produced in two places. A model asserting Core internals from memory fails in exactly this way, confidently. The fix is a loop that checks reality, not a better prompt.

## 5. Check that the checks work

- [`scripts/mutation_check.py`](../scripts/mutation_check.py) breaks the code on purpose (inverts a comparison, reverses a byte order, swaps in a write RPC, drops a bound check) in a scratch copy and requires the unit suite to go red for each one. It exists because AI-written tests commonly pass on the first run, which proves nothing by itself.
- The CI integration job was dry-run end to end against a fresh node on a different port, and the unit tier against a clone with no `fixtures.json`, before being trusted.
- **Why:** green is only meaningful if red was possible.

## 6. Small vertical slices, each verified, one commit each

- A scenario lands as one coherent slice: catalog entry, mutation, source citation, boundary test, UI check. `git log` reads as a sequence of small, reviewable commits with the *why* in the body.
- Prefer a vertical slice that works end to end over a broad scaffold that works nowhere.
- **Why:** small diffs are reviewable; a wrong turn costs minutes, not a day.

## 7. Explicit autonomy boundaries

- `AGENTS.md` has **Always / Ask first / Never** lists. Ask-first includes re-pinning Core, touching deployment files, `make reset-chain`, adding dependencies, loosening a recorded decision, and committing/pushing.
- [`.claude/settings.json`](../.claude/settings.json) backs the most important ones with real permission rules: destructive or outward-facing commands prompt, force-push is denied.
- Secrets stay out of the repo by construction (`regtest.conf` has no credentials; `entrypoint.sh` generates one per boot; `fixtures.json` and the node log are gitignored).
- **Why:** autonomy should be granted deliberately and per risk, not all-or-nothing.

## 8. Durable memory lives in the repo, not in chat

- [`docs/decisions/`](decisions/) records *why* constraints exist so they aren't re-litigated by accident. [`ROADMAP.md`](../ROADMAP.md) holds scoped next steps and an **Open decisions for a human** list.
- The original build plan introduced **DECIDE gates**: sections an agent must not fill in by inventing an answer ([history](history/build-plan.md)). That idea is kept: when the spec is open, the right move is to ask.
- When a session discovers a gotcha (e.g. the regtest node dying with `Operation not permitted`), it goes into `AGENTS.md` or the roadmap, not just the transcript.
- **Why:** a fresh session has no memory. Whatever isn't written down is lost.

## 9. Review by evidence

- [`.github/pull_request_template.md`](../.github/pull_request_template.md) asks "how I verified it" (commands and results), a dedicated line for Bitcoin Core claims, and an optional note on AI assistance.
- UI changes are verified by running the app and looking (`.claude/launch.json` defines the dev servers for the preview pane), not by assuming a green build means a working page.
- **Why:** reviewers (and the next agent) need evidence, not assurances.

## 10. Failures that explain themselves

- Contract-test messages say what to do ("add the function to `MUTATIONS`", "new scenario: add its edge to `EDGES`"). The scanner reports `<unknown>` rather than guessing. `make reset-chain` is labelled DESTRUCTIVE in `make help`.
- **Why:** an agent (or a tired human) acts on the error text. Make it the right instruction.

## Briefing an agent: a template that works here

> Add a scenario for **\<rule\>**. Read `AGENTS.md` and `docs/adding-a-scenario.md` first.
> Trigger the failure on the live node and read the pinned Core source before writing
> any string or line number. Plan the slice, then implement it, then run `make check`,
> `make test-integration`, `make test-sources`, and check the page in the browser.
> Tell me what you verified and what you could not. Don't commit.

Good briefs name the goal, the playbook, the verification, and the stopping point.

## What humans still own

Which scenarios are worth building; whether a consensus-vs-policy claim is
*pedagogically* right, not just technically true; the open decisions in the
roadmap; deployment; and reading the diff. The tooling here makes review faster
and better-informed. It does not replace it.
