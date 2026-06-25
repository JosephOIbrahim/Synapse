# SYNAPSE → H22 harness

A long-running, self-verifying harness that grinds your H22 preparedness checklist.
Your own `probe → delta → patch` loop, made autonomous, with an adversarial gate.

It runs headless for cooks, renders, patches, and worktree commits. It will **not** merge
to main, decide your architecture, or fire the post-drop pipeline before H22 exists — those
are deliberate human gates.

## How it runs

**Now (Mode A, on H21):**
```bash
export HYTHON="/path/to/Houdini 21.x/bin/hython"   # Windows: ...\bin\hython.exe
bun run harness/run.ts            # grinds Phase 0
bun run harness/run.ts --dry      # plan only — see the queue + gates, spawn nothing
bun run harness/run.ts --task 0.3 # one task
```

**On drop (Mode B, mid-July):** install H22, read the three numbers, then write the trigger:
```bash
cat > harness/state/drop.json <<'JSON'
{ "python": "3.x.x", "usd": "x.y.z", "pyside": "6.x.x", "houdini": "22.0.xxx" }
JSON
export HYTHON="/path/to/Houdini 22.x/bin/hython"
bun run harness/run.ts            # probe fires, delta becomes the worklist, loop runs
```

## The loop
`fresh Generator (WIP=1) → checks.py (hython · doctor · ledger · render · probe) →
adversarial Evaluator → PASS or repair-ticket → loop`, capped at `MAX_ROUNDS` (default 3)
before a task is flagged for you. Passing features wait in worktrees for **your** merge.

## The three human gates
1. **`0.1` sidecar vs abi3** — architecture decision. Harness recommends sidecar, verifies the bridge, doesn't choose.
2. **The drop trigger** — install H22, read Python/USD/PySide, write `drop.json`.
3. **Merge to main** — harness commits in worktrees only.

## Files
| path | role |
|---|---|
| `harness/run.ts` | orchestrator — gate loop, worktree routing, Mode A/B switch |
| `harness/tasks.json` | machine source of truth (sync with the checklist — that's task 0.3) |
| `harness/prompts/generator.md` | fresh-instance builder, WIP=1 |
| `harness/prompts/evaluator.md` | adversarial Houdini TD — the keystone |
| `harness/verify/checks.py` | deterministic checks (the Playwright analog) |
| `harness/state/manifest.schema.json` | verdict / repair-ticket contract |
| `harness/state/claude-progress.md` | state continuity the Generator reads each boot |
| `.claude/settings.json` | pre-approved tool allowlist + format hook |
| `CLAUDE.md` | distilled conventions (<2,500 tokens, cached) |

## ADAPT — the only wiring you owe it
Search the tree for `ADAPT`. The real ones, all in `checks.py` unless noted:
1. **`claude` CLI flags** in `run.ts` `runAgent()` — verify against your `claude --help`.
2. **Module + bridge ping** — `check_import_panel` / `check_brain_answers` (your real `ping`).
3. **doctor + probe entrypoints** — how `server/doctor.py` signals green; how `apex_probes.py` writes its delta.
4. **`agent.usd` schema** — prim type + `decision`/`reasoning`/`revert` attr names in `check_ledger`, and the revert + stage-hash diff in `check_revert_clean`.
5. **Render** — the USD to render + a real non-black pixel check in `check_render`.

Until wired, those checks report `ok:false` with a reason — by design. Nothing here fakes a pass.
