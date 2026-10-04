# 0004: Vendor Bitcoin Core's test_framework verbatim

**Status:** Accepted

**Context.** Building valid-but-mutated blocks needs correct serialization,
coinbase construction, merkle roots, and witness commitments. Hand-rolling these
is where subtle bugs live, and a bug would make a "rejection" meaningless.

**Decision.** Copy the needed files from `test/functional/test_framework/` at the
pinned tag into `backend/vendor/`, unmodified, plus their dependency closure. If an
import is missing, vendor the dependency; never patch the vendored files.
`VENDORED.md` records the tag and commit.

**Consequences.**
- Payloads are built by the same code Core's own tests use.
- Upgrading Core means re-vendoring and re-verifying (see the roadmap's re-pin procedure).
- Vendored code is excluded from our style expectations and must not be edited.
