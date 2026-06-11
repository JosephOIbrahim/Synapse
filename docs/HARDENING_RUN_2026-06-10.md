# Hardening Run Ledger — 2026-06-10

**Source:** `docs/SYNAPSE_VFX_PRODUCTION_HARDENING_2026-06-09.md` · **Base:** `d1abe21` (v5.12.0, suite 3,415 green)
**Discipline:** reproduce ([F] findings) → fix → re-verify → full suite per milestone. M1 → M2 → M3.

## Mile map

| Mile | Scope | Status |
|---|---|---|
| 1 | Verify all M1 findings (10 WPs, read-only fleet) | DONE — 7 confirmed, 3 adjusted, 0 refuted (`wf_15f3454d-a92`) |
| 2 | Implement M1 — four P0s + truth contract + sharp ones + registry test | DONE — 8 implementers (disjoint file sets) + orchestrator-reserved `handlers.py`/`_tool_registry.py`/`mcp_tools_cops.py` edits |
| 3 | Full suite green + commits | DONE — **3,467 passed / 68 skipped / exit 0 (~51 s)**, incl. `test_m1_truth_contract.py` |
| 4 | Verify all M2 findings (10 WPs, read-only fleet) | FAILED — `wf_0c2a040b-843`: all 10 agents killed by the account's monthly spend limit (0/10 verdicts, ~1.08M tokens of partial work lost). Pivot: solo sequential verify→implement per WP (sharpest P1s first), commit per group. |
| 5 | Implement M2 — display/rewire policy, cook-verify, `_safe_node_name`, path/token policy, OCIO previews, recipe rollback, show-config | RUNNING (solo) — order: M2-B cook-verify → M2-F flipbook path → M2-C safe-node-name → rest as budget allows |
| 6–7 | M3 — UPGRADE.md, env conformance, logs/bundle, telemetry flush, keys/egress, autonomy bounds | pending |
| — | M3 item 11 (SEC-1/RBAC) | SKIPPED — gate, not work (per report §5) |

## M1 work packages

| WP | Finding | Files | Verdict | Fixed |
|---|---|---|---|---|
| WP1 | P0 §3#1 recipe-execution fiction | `routing/router.py`, `handlers.py:1357` | confirmed — panel never executes; "Executed" reaches artist over untouched scene | wave 1 |
| WP2 | P0 §4.4 autonomy contract broken | `autonomy/planner.py`, `driver.py` | adjusted — leg (b) INVERTED: false PASS 1.0, not false fail; +replan render_settings break found | wave 1 |
| WP3 | P0 §4.1 compose tier: no main-thread/undo/consent | `handlers_solaris_compose.py`, `solaris_compose_tools.py`, `bridge_adapter.py` | confirmed — worse: bridge path never marshals either | wave 1 |
| WP4 | P0 §4.1 render destroys output-path tokens | `handlers_render.py` | confirmed — +loppath autoset & flipbook playhead unrestored; loppath decision: RESTORE (Option A) | wave 1 |
| WP5 | §3#2+#9 evaluator unverifiable=1.0; quality_threshold ignored | `autonomy/{models,evaluator,driver}.py`, `handlers.py` | confirmed — worse: missing-frame metrics default 1.0 into the mean; fiction test-pinned | wave 1 |
| WP6 | §3#3+#4 + §4.2 playhead + §4.1 orphan nodes (COPs) | `handlers_cops.py`, `handlers.py:202` | adjusted — read-only bypass is 3 layers (C5+audit+Floor); pinned at test_cops.py:833 | wave 1 |
| WP7 | §3#5 planner AOV/denoise stubs | `routing/planner.py` | confirmed — exactly 2 stubs file-wide; real-work path would be a #7-class dangling branch → scaffold-mark | wave 1 |
| WP8 | §3#6 scheduler_type fiction | `handlers_tops/cook.py` + 3 docs | confirmed byte-accurate — fail-loudly; param is parked design, not removed | wave 1 |
| WP9 | §3#10 APEX phantom recipes + guess-prompt | `panel/apex_recipes.py` | adjusted — dormant (no live caller) but loaded gun; 3/12 targets are Vop graph-internal → rename+caveat; 4 names unmappable → removed/marked | wave 1 |
| WP10 | Truth-contract registry-wide test | `tests/test_m1_truth_contract.py` (new) | adjusted — grep unimplementable; AST design validated, 0 false positives on 117 handlers; §3#8 partially refuted (7/9 USD mutators DO cook; 2 don't) | DONE — 4 pins green; flagged set == {`tops_configure_scheduler`} exactly; `SHAPE_FICTION_DEBT` = {manage_collection, configure_light_linking} (COPs exited via honest markers); allowlist EMPTY |

**Orchestrator-reserved edits (post-wave):** `handlers.py` (WP1 route_chat keys · WP5 clamp+thread · WP6 declassify+audit-cat) · `mcp/_tool_registry.py` + `mcp/mcp_tools_cops.py` (WP6/WP8 description honesty).

## Mile 3 forensics — the exit-137 suite kills (2026-06-10 night)

Three `python -m pytest tests/` attempts died with exit 137. Diagnosis (2026-06-11):

- **Not a suite hang.** The full suite runs end-to-end in ~51 s. No Windows OOM/crash events
  (System + Application logs clean). The 137s were process kills from the dying chat session /
  harness timeouts. The "died after `test_blast_radius.py`" read was a **block-buffering
  artifact** — pytest output redirected to a file lags the live position by a buffer, so the
  log tail does not localize a kill.
- **What the kills were masking — 10 real failures, both order-dependence, both wave-exposed:**
  1. `test_capture.py` ×7 — the wave's `test_autonomy_live_contract.py` sorts earlier and stole
     the *first `hou`-planter + first handlers importer* position; its skeletal fake (no `.ui`)
     became `handlers_render.hou`. Fix: autouse fixture in `test_capture.py` patches
     `handlers_render.hou`/`HOU_AVAILABLE` directly (residency is order-fragile).
  2. `test_compose_offmain_wp3.py` ×3 — `test_main_thread.py:56-59` (pre-existing) swaps a
     private instance into `sys.modules["synapse.server.main_thread"]` at collection; the
     compose handlers' call-time `from .main_thread import run_on_main` resolves the
     replacement, so the spy patched on the test's collection-time reference never fired.
     Fix: `_wire` patches the **live** `sys.modules` entry via `importlib.import_module`.
- **Standing trap (suite-wide):** 46 test files plant `hou` fakes in `sys.modules` at module
  level (mostly `setdefault`, no cleanup). The suite is only guaranteed green in **full
  alphabetical order** — subset runs reshuffle the first-planter and can fail spuriously
  (e.g. `test_chat_panel.py` + `test_cops.py` alone → 34 fails on `hou.undos`). Subset runs
  are diagnostics, not gates; the CI gate is the full run. Durable fix idiom: patch the
  handler module's globals (`monkeypatch.setattr(handler_mod, "hou", fake)`), never rely on
  residency.

## Constraints

- `handlers.py` is shared across WP1/2/5/6 — orchestrator applies those edits, agents return specs.
- Real gate: `python -m pytest tests/` headless (CI command). New tests per WP in `tests/test_m1_*.py`.
- No new `hou.*` APIs without in-repo precedent (CLAUDE.md §11.15 — scout/dir() gate).
- Surgical: M1 fixes touch only M1 scope; M2 items in same files wait for Mile 4.
