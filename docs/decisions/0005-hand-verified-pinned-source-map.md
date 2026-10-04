# 0005: Source citations are hand-verified, pinned to a commit, and audited

**Status:** Accepted

**Context.** The product's claim is "this exact line of C++ produced that
rejection." Citing `master` rots; citing from memory is wrong. The same string
can come from several checks (e.g. `dust` from `PreCheckEphemeralTx` and
`IsStandardTx`; the first citation here was wrong for exactly that reason).

**Decision.** Every entry in `sources.py` is found by triggering the scenario on
the live node and reading the source, and its permalink is pinned to one commit
(the v31.1 tag). `gen_sources.py` scans the whole tree for every call site and diffs
against the catalog; `make test-sources` checks each cited range contains its string.

**Consequences.**
- Citations are stable and checkable; moving to a new Core release is a deliberate re-pin.
- Tooling proves a range contains the string, not that it is the *right* site; human review of which site fires is still required.
- The scanner is a heuristic, not a C++ parser; its output is candidates to review.
