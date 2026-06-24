# claude-progress.md — harness state continuity

> Read this first, every sprint. It is the whole mission in one screen. Append a one-line
> delta when a task passes; do **not** turn this into a diary — keep it short so it caches.

## MISSION
Be running natively in **Houdini 22 the day it drops** (~mid-July), with one new COPs
feature and one new Solaris feature in a working demo by end of that week. De-risk now, on
H21, so drop day is **verification, not surgery**.

## MODE RULE
- **MODE A (now):** `drop.json` absent → only Phase 0 (`0.x`) tasks run, on H21's hython.
- **MODE B (drop):** a human writes `harness/state/drop.json` with the three numbers →
  the `1.x`/`2.x`/`3.x` pipeline arms, pointed at H22's hython.

## THE THREE HUMAN GATES — never auto-handle these
1. **`0.1` architecture: sidecar vs abi3.** *Recommended: **sidecar*** (brain in its own
   pinned interpreter, immune to H22's Python). Undecided until you commit it. The harness
   verifies the property ("brain answers"), not the mechanism — either choice keeps the loop valid.
2. **The drop trigger** (`1.1`/`1.2`): install H22, read Python · USD · PySide, write `drop.json`.
3. **Merge to main:** the harness commits in worktrees only. Promotion is your call (tag the PR).

## NON-NEGOTIABLES (also in CLAUDE.md)
- Provenance or it didn't happen: every scene/stage action → `agent.usd` (decision + reasoning + revert), undo-wrapped.
- Probe truth beats H21-pinned constants wherever the probe shows drift.
- One source of UI truth (`panel/`). One source of version. Reach tools by verb × context.

## CURRENT TASK
<set by run.ts per sprint>

## LOG (deltas only)
- 2026-06-24 · Step 0: 10 files placed. COLLISIONS (existing repo files, NOT clobbered): CLAUDE.md→kept harness copy at `harness/CLAUDE.md` (root 42KB blueprint untouched); `.claude/settings.json` DEFERRED (existing wires guard-edit + hooks). `node run.ts --dry` clean (MODE A, queue 0.1–0.7, 0.1 gated). bun absent; node v24 runs run.ts. NOTE: `--dry` still creates 6 worktrees (cleaned up).
- 2026-06-24 · Step 2 WIRED+green (H21.0.671): import_panel (sys.path `<wt>/python`+`<wt>`; synapse 5.14.0), brain_answers (in-proc `synapse.get_bridge()._synapse`), doctor (`synapse.server.doctor.run_doctor`, green=summary.fail==0). Task 0.1 standalone PASS.
- 2026-06-24 · Step 3 WIRED: probe_runs→`scripts/run_apex_verify.py` (rc0, 16/16 champions = empty-delta proof); shot_login→`synapse.panel.shot_login.shot_login()` (+OCIO gate). version_single_source/hip_opens/clean_install/nodes_appear left as-authored (correct or honest-false).
- 2026-06-24 · Mode-A standalone truth: PASS 0.1/0.2/0.6 · FAIL(truthful) 0.3 (VERSION 5.8.0≠pyproject 5.14.0 = real drift), 0.4 (doctor amber=telemetry.json stale; cook_existing=no node), 0.5 (no demo hip; OCIO unset), 0.7 (hardcoded path `houdini/python_panels/synapse_panel.pypanel:20`; no native node types — MCP-driven).
- 2026-06-24 · Still ADAPT (Mode-B / not-buildable-now, NOT faked): cook_node, cook_existing, ledger, revert_clean, render, probe_clean, theme_ok. Real ledger schema = `/SYNAPSE/agent/ledger/<kind>_<ts>_<sha8>` Xform prims, `synapse:*` attrs (no SynapseAction/decision/reasoning/revertPath); agent.usd at `<claude_dir>/agent.usd`; no revert API exists.
- 2026-06-24 · GATE 0.1 evidence: `python/synapse/host/daemon.py` = IN-PROCESS threaded daemon (boot-gates on `hou.isUIAvailable()`, refuses headless) + cp311-win vendoring (`__init__.py:51`). Today's arch is the abi3-ish in-proc path, NOT an out-of-process sidecar. Decision still the human's.
- 2026-06-24 · Step 4 (loop on 0.3) PENDING human go: needs harness allowlist merged into `.claude/settings.json` (committed, so worktrees inherit) for headless agents; and 0.3 drift means the loop's fix regresses pyproject unless VERSION is aligned first (VERSION edit is human).
