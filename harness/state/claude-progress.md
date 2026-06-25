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
- 2026-06-24 · Step 4 DONE — full loop PROVEN PASS on 0.3 on the **Max-20x subscription (zero API credits)**. Generator edited (DEMO_SCRIPT.md + pyproject.toml), checks PASS, Evaluator PASS (9/7/9/7), atomic commits in worktree `harness/0.3`, master untouched (NO merge). VERSION aligned→5.14.0 first (human-authorized); harness allowlist merged into `.claude/settings.json` (Option A, user-applied).
- 2026-06-24 · Max-20x auth fix: global `~/.claude/settings.json` env-block forces a credit-starved ANTHROPIC_API_KEY onto every `claude`. runAgent now passes `--settings harness/agent-settings.json` (blanks the key → subscription login). Verified AUTHOK.
- 2026-06-24 · Windows arg fix (run.ts): shell:true concatenates args WITHOUT escaping (DEP0190) → shredded prompts + spaced HYTHON. runAgent now uses `--append-system-prompt-file` + stdin (`-p` last); runChecks quotes+fwd-slashes `--worktree`/`--hython`; all spawn paths forward-slashed.
- 2026-06-24 · CAVEATS (worktree-only, NOT merged): round-0 Evaluator output missed parseVerdict's regex once (transient; repair round recovered). The repair-round Generator over-reached and edited `harness/run.ts` (WIP=1 scope violation; no effect on the already-loaded orchestrator). Inspect `harness/0.3` before any merge — 0.3's real fix is the VERSION bump already on the branch.

- 2026-06-24 18:17 · 0.3 BLOCKED after 1 rounds — needs a human — Single-source the version
- 2026-06-24 18:26 · 0.3 BLOCKED after 1 rounds — needs a human — Single-source the version
- 2026-06-24 18:37 · 0.3 BLOCKED after 1 rounds — needs a human — Single-source the version
- 2026-06-24 18:54 · 0.3 PASS — Single-source the version
- 2026-06-24 · POST-STEP-5 (user asked to advance the real work; product edits authorized):
- 2026-06-24 · GATE 0.1 brief written → `harness/notes/gate-0.1-sidecar-vs-abi3.md`. Key: only 2 vendored deps ABI-locked (pydantic_core, jiter; cp311 wheels, NOT abi3) → abi3 needs a fork = off the table. Real choice = sidecar vs in-process+re-vendor-on-drop. Recommendation surfaced; decision still the human's.
- 2026-06-24 · 0.7/0.4 clean_install GREEN: dropped hardcoded `C:\Users\User\SYNAPSE` from synapse_panel.pypanel + synapse_chat.pypanel (rely on SYNAPSE_ROOT/PYTHONPATH) and system_prompt.py (fixed an off-by-one repo-root derivation the hardcode masked). checks.py check_clean_install now scans only the shipped product surface (houdini/, packages/, python/synapse). Verified PASS + test_agent_loop 18-passed.
- 2026-06-24 · 0.5 GREEN (with OCIO set): created `demo/synapse_demo.hip` (minimal /stage scene) → hip_opens green; shot_login green once OCIO is set (artist pipeline prereq, documented in demo/README.md; the check only verifies OCIO is configured).
- 2026-06-24 · 0.4 ui→panel fold NOT done (deliberate): live UI truth is ALREADY `panel/synapse_panel` (the .pypanel loads it, not ui/). Legacy `ui/` is dead-but-test-pinned — `test_v5_features.py:54-82` asserts ui/ modules exist; panel/ has no `create_panel`. Full removal = a real refactor needing test_v5_features edits + full-suite verification. Flagged, not rushed.