@AGENTS.md

## Claude Code specifics

The shared guide above is the single source of truth (imported, not copied, so
it cannot drift). Only Claude-Code-specific notes live here.

- `.claude/settings.json` holds the shared permission guardrails: destructive or
  outward-facing commands (`make reset-chain`, `git push`, `docker`, `fly`) prompt;
  force-push is denied; the fast verify commands run without a prompt.
- `.claude/launch.json` defines the `backend` and `frontend` dev servers for the
  preview pane. Use it to verify UI changes instead of asking the user to look.
- For a change that touches more than a couple of files, or anything on the
  "Ask first" list, plan first and confirm before editing.
- After a UI change, run the app and check the actual page; type-checks and unit
  tests do not prove the UI works.
- Keep sessions to one task. Durable knowledge belongs in `docs/` or `AGENTS.md`,
  not in chat history: when you learn a repo-specific gotcha, add it there.
