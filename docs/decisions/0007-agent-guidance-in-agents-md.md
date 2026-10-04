# 0007: One canonical agent guide (`AGENTS.md`), imported by `CLAUDE.md`

**Status:** Accepted

**Context.** This repo is built with AI coding agents. Guidance duplicated across
tool-specific files drifts; guidance that is too long stops being read.

**Decision.** `AGENTS.md` is the single canonical, deliberately short guide
(commands, repo map, always / ask first / never, provenance rule, gotchas). `CLAUDE.md`
imports it with `@AGENTS.md` and adds only Claude-Code-specific notes. Details live
in `docs/` and are linked, not inlined. Rules that can be tests are tests.

**Consequences.**
- Any tool that reads `AGENTS.md` gets the same rules as Claude Code.
- `AGENTS.md` must stay short; when it grows, move detail into `docs/` or a test.
- See `docs/agentic-development.md` for the reasoning behind each practice.
