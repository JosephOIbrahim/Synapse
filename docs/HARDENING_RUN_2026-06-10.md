# Hardening Run Ledger — 2026-06-10

**Source:** `docs/SYNAPSE_VFX_PRODUCTION_HARDENING_2026-06-09.md` · **Base:** `d1abe21` (v5.12.0, suite 3,415 green)
**Discipline:** reproduce ([F] findings) → fix → re-verify → full suite per milestone. M1 → M2 → M3.

## Mile map

| Mile | Scope | Status |
|---|---|---|
| 1 | Verify all M1 findings (10 WPs, read-only fleet) | DONE — 7 confirmed, 3 adjusted, 0 refuted (`wf_15f3454d-a92`) |
| 2 | Implement M1 — four P0s + truth contract + sharp ones + registry test | DONE — 8 implementers (disjoint file sets) + orchestrator-reserved `handlers.py`/`_tool_registry.py`/`mcp_tools_cops.py` edits |
| 3 | Full suite green + commits | DONE — **3,467 passed / 68 skipped / exit 0 (~51 s)**, incl. `test_m1_truth_contract.py` |
| 4 | Verify all M2 findings (10 WPs, read-only fleet) | DONE — first fleet `wf_0c2a040b-843` killed by spend limit (0/10); 6 WPs verified solo; remaining 4 verified by relaunched fleet `wf_d42b78b1-7d6` after limit lift (2 confirmed, 2 adjusted) |
| 5 | Implement M2 — all 10 WPs | **DONE — suite 3,567 green.** 6 solo (B/C/E/F/H/J) + 3 agent waves (I+A parallel → D → G); see M2 WP table |

## M2 work packages (solo verify→implement; fleet died on spend limit)

| WP | Finding | Status |
|---|---|---|
| M2-B | §3#8 residue — cook+readback in `manage_collection`/`configure_light_linking` | ✅ `00fa6ee` — confirmed (embedded `if prim:` silently skips, cook alone proves nothing → stage readback added); SHAPE_FICTION_DEBT retired |
| M2-F | §3#11 — flipbook GL grab at the beauty path | ✅ `d83360b` — confirmed WORSE (.jpg replace no-ops on EXR → grab lands AT beauty path verbatim; fallback also claimed `output_file` for a never-written file) → `_glpreview` sidecar + honest keys |
| M2-C | §4.3 — `_safe_node_name()` | ✅ `a029afb` — 11 derived-name sites (10 usd + 1 material) had half-sanitizers missing hyphens/brackets; one helper now owns the rule. Front doors (create_node/cops_create_node) intentionally passthrough — explicit-name raising is feedback, not a derived crash |
| M2-H | §4.2 — recipe/plan rollback | ✅ `2f9d92d` — `_try_recipe` stopped continue-on-failure; `_try_plan` was pre-M1 fiction intact (unconditional success=True) → full truth contract. **Flagged follow-on:** per-recipe server-side undo group (router can't safely auto-undo: read-only steps create no undo entries; `_READ_ONLY_COMMANDS` unimportable router-side without circular) |
| M2-J | §4.1 rider — render_farm `initial_settings` never re-applied | ✅ `294efd9` — confirmed WORSE (warmup's `initial_settings.update()` destroyed the only baseline record). `artist_baseline` snapshot + `_changed_parms` tracking + restore on every terminal state; BatchReport gains settings_changed/restored/restore_error |
| M2-E | §4.3 — frame-token expander | ✅ `8d87b33` — `_expand_frame_tokens` ($F/$Fn) at 3 render sites; TOPS validator padding-agnostic (zfill(4) hardcode made 3/5-digit shows all-missing). Collateral: test_render `_setup_render` hou.node blanket mock made 3 pins pass VACUOUSLY (MagicMock.endswith truthy) — harness now path-aware |
| M2-A | §3#7 — dangling LOP display/rewire policy | ✅ `5704dfe` — confirmed, SHARPER post-M2-B ("verified:True" was true-but-invisible); 12 handlers wired via `_wire_display` (display moves only when extending the chain; forks return `needs_rewire` honestly; auto-rewire rejected — input order is opinion strength); reference_usd island fixed; `set_display` opt-out + registry passthrough |
| M2-I | item 7b — show-config lookup | ✅ `5704dfe` — `synapse/core/show_config.py`: env > `$HIP` > `$JOB` > defaults (scene-over-show adjudication accepted); defaults are today's exact hardcodes (zero-change pinned); `naming.versioning=increment` retires the timestamped-reruns rider; project_setup surfaces + reloads. Deferred consumers (recipes/COPs/predictor/fps) listed in fleet output `w19iu2lcc` |
| M2-D | §4.3 — path policy core | ✅ `5bf9a3a` — ADJUSTED UP: eval-at-playhead WROTE frame N pixels into the playhead filename (silent overwrite). Tokens-stay-raw in compose parms; productName cook-time per-frame ($F4); resolver-URI passthrough marked unverified; `evalAsStringAtFrame` + artist parms never rewritten; `path_warnings` at 3 surfaces. **Live-verify owed on bridge restore:** per-frame productName under husk; ROP-reads-own-picture assumption |
| M2-G | §4.3 — OIIO+`$OCIO` color-managed previews | ✅ wave 3 — `_convert_preview` (hoiiotool `--ociodisplay` w/ env-injected OCIO → `--tocolorspace "sRGB - Display"` → iconvert `-g auto`); `color_managed=True` ONLY on the verified OCIO leg; `color_transform`/`preview_tool`/`preview_error` result keys; format honesty (unconverted EXR ships labeled `exr`); flipbook leg marked `viewport_display (unverified)`. **Deferred:** capture_viewport static color keys (blocked by test_capture exact-shape pin); evaluator pixel-verdicts don't inherit the transform (separate finding) |

**Fleet/wave machinery:** verification fleet `wf_d42b78b1-7d6` (4 verdicts: 2 confirmed, 2 adjusted) → wave 1 `wf_39f6e6d5-ff0` (I+A parallel, disjoint) → wave 2 (D solo) → wave 3 (G solo). Orchestrator-reserved registry edits applied between waves. **Registry follow-up:** the 9 `_identity`-mapped display-policy tools still lack the `set_display` schema property (functional already; docs-honesty pass pending).
| 6 | Verify M3 findings (5 WPs: A upgrade-surface · B env-conformance · C logs/doctor/telemetry · D multiseat/egress · E bounded-autonomy) | RUNNING — fleet `wf_d5b0f370-ccc` |
| 7 | Implement M3 | pending — waves from the ownership matrix |
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
