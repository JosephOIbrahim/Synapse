# CLAUDE.md — SYNAPSE conventions

Keep this short. Short = cached = cheap. Conventions only, no history.

## What this is
SYNAPSE is an agentic Houdini plugin: plain-English prompts → real Houdini work (COPs
networks, Solaris/USD set-dressing, Karma renders), every action **reversible and recorded**.
The differentiator vs. Houdini's native MCP is the receipts. Protect that.

## Survival rule (the one that fails silently)
The brain must wake up regardless of Houdini's Python version. **Default architecture:
sidecar** — brain in its own pinned interpreter, panel/host on Houdini's. Never assume
cp311; the embedded version is whatever the live interpreter reports.

## Hard conventions
- **Provenance or it didn't happen.** Any scene/stage mutation is undo-wrapped AND written
  to `agent.usd` with `decision` + `reasoning` + `revert` path. No ledger entry ⇒ incomplete.
- **Probe truth > pinned constants.** Where the probe reports API drift, use the
  live-introspected op. Never hardcode an H21-era constant the probe flagged.
- **One source of UI truth:** `panel/`. The legacy `ui/` tree is dead — never add to it.
- **One source of version.** `VERSION` is canonical; `pyproject.toml` and the demo script
  follow it. Don't edit `VERSION` from an agent.
- **Reach tools by verb × context** (texture, scatter) × (COP, LOP) — palette, not buried menus.
- **No hardcoded user paths.** Install must work via the package on a clean machine. The
  `C:\Users\User\SYNAPSE` fallback is a bug, not a convenience.

## Commits
One atomic commit per sprint. `feat(area): <id> <what>` / `fix(area): <id> <what>`. Never
squash unrelated work. Never `git push` or `git merge` — promotion to main is human.

## When stuck
Write the blocker to `.claude/remediation_ticket.md` and stop. A clean stop beats a broken
guess; the Evaluator and the human gates exist for exactly this.
