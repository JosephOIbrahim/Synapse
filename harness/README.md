# SYNAPSE → H22 harness  (v2 — boundary-synthesized)

A long-running, self-verifying harness that grinds your H22 preparedness checklist.
Your own `probe → delta → patch` loop, made autonomous, with an adversarial gate.

It runs headless for cooks, renders, patches, and worktree commits. It will **not** merge
to main, decide your architecture, or fire the post-drop pipeline before H22 exists — those
are deliberate human gates.

**v2 synthesizes `docs/SYNAPSE_H22_BOUNDARY.md`:** orchestrating H22's native APEX MCP is now a
first-class, drop-week-critical leg (not a stretch), and the boundary's non-goals are enforced
as cross-cutting guardrails that fail any sprint that erodes the moat.

## How it runs

**Now (Mode A, on H21):**
```bash
export HYTHON="/path/to/Houdini 21.x/bin/hython"   # Windows: ...\bin\hython.exe
bun run harness/run.ts            # grinds Phase 0 (incl. 0.8/0.9 against the mock MCP)
bun run harness/run.ts --dry      # plan only — see the queue + gates, spawn nothing
bun run harness/run.ts --task 0.8 # one task
bun run harness/run.ts --force    # re-run tasks the completion ledger (done.json) already banked
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
`fresh Generator (WIP=1) → checks.py (hython · doctor · ledger · render · probe · MCP) →
deterministic guardrail gate → adversarial Evaluator → PASS or repair-ticket → loop`, capped
at `MAX_ROUNDS` (default 3) before a task is flagged for you. Passing features wait in
worktrees for **your** merge. Two facts the arrow compresses: a task already banked in
`done.json` (refs byte-identical) is **skipped** before generation, and a guardrail `ok:false`
short-circuits to a repair ticket **before** the Evaluator runs.

## Guardrails (boundary non-goals — run every sprint)
`checks.py` runs the `guardrails` set on **every** task in addition to its own `verify` list:
`scout_no_apex_corpus`, `no_rigging_drift`, `provenance_not_bypassed`, and `phantom_clean` (no
newly-introduced phantom `hou.*` API in the sprint's changed `.py`, dir()-symbol-table-gated). A guardrail with
`ok:false` is a **deterministic FAIL** — run.ts writes a repair ticket and loops *before*
the Evaluator is called. A guardrail with `ok:null` ("not wired yet") only **warns**. This is
how `SYNAPSE_H22_BOUNDARY.md §8` stays true no matter what any Generator round does.

## The three human gates
1. **`0.1` sidecar vs abi3** — architecture decision. Harness recommends sidecar, verifies the bridge, doesn't choose.
2. **The drop trigger** — install H22, read Python/USD/PySide, write `drop.json`.
3. **Merge to main** — harness commits in worktrees only.

The harness also adds one **read-only** touchpoint that is *not* a gate: at run end it surfaces
flywheel candidates awaiting ratification — each `ratified:false` cycle with its evidence and the
exact `harness/state/flywheel_queue.json` line to flip. It never writes `ratified` itself; the flip
is yours, but nothing blocks on it.

## Files
| path | role |
|---|---|
| `harness/run.ts` | orchestrator — gate loop, guardrail short-circuit, completion-ledger skip, ratification surface, worktree routing, Mode A/B switch |
| `harness/tasks.json` | machine source of truth (sync with the checklist — that's task 0.3); holds `guardrails` |
| `harness/prompts/generator.md` | fresh-instance builder, WIP=1 |
| `harness/prompts/evaluator.md` | adversarial Houdini TD — the keystone; 5 rubrics incl. boundary |
| `harness/verify/checks.py` | deterministic checks (the Playwright analog) + MCP checks + guardrails |
| `harness/state/manifest.schema.json` | verdict / repair-ticket contract (incl. `boundary` score) |
| `harness/state/claude-progress.md` | state continuity the Generator reads each boot |
| `harness/state/done.json` | completion ledger — per-task PASS + refs-hash; skips already-banked work on re-run (runtime state, untracked) |
| `harness/state/flywheel_queue.json` | flywheel cycle candidates; a human flips `ratified`, the harness only surfaces them read-only |
| `.claude/settings.json` | pre-approved tool allowlist + format hook |
| `docs/SYNAPSE_H22_BOUNDARY.md` | the boundary doc this harness enforces (the "why") |
| `docs/SYNAPSE_H22_PROVIDER_APEX.md` | provider-registration spec — what 0.8/2.7 implement |
| `CLAUDE.md` | distilled conventions (<2,500 tokens, cached) |

## ADAPT — the only wiring you owe it
Search the tree for `ADAPT`. The real ones, mostly in `checks.py`:
1. **`claude` CLI flags** in `run.ts` `runAgent()` — verify against your `claude --help`.
2. **Module + bridge ping** — `check_import_panel` / `check_brain_answers` (your real `ping`).
3. **doctor + probe entrypoints** — how `server/doctor.py` signals green; how `apex_probes.py` writes its delta.
4. **`agent.usd` schema** — prim type + `decision`/`reasoning`/`revert` attr names in `check_ledger`, and the revert + stage-hash diff in `check_revert_clean`.
5. **Render** — the USD to render + a real non-black pixel check in `check_render`.
6. **MCP provider** — `server/providers/apex_mcp.py` registry accessor + tool round-trip envelope (`check_mcp_registered` / `check_mcp_truth_contract`); the mock at `science/mcp_mock.py`; the shipped-surface probe `science/mcp_surface_probe.py` (`check_mcp_surface_probe`).
7. **Scout federation** — `server/scout_sources.json` (APEX source = federated `provider`) and the query API in `check_scout_federates`.
8. **Guardrail anchors** — `server/scout_sources.json`, `server/authoring_domains.json`, and the provenance-gateway sentinel in `check_provenance_not_bypassed`.

Until wired, those checks report `ok:false` (or `ok:null` for guardrails) with a reason — by design. Nothing here fakes a pass.
