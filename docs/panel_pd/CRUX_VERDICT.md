# PD-CRUX — round 2, 2026-09-04

**Integrated wave: BROKEN. No merge recommendation.** The QSS splice introduced at
`0998cc9e` is **FIXED in source at `38cd9b46`**. This is not a certificate that the
three previously failing Qt state-colour cases are green: their round-2 execution
is **NOT_RUN**, because the bound Python cannot import PySide6. Other acceptance
failures remain below.

Reviewed source: `38cd9b4668c8e494ec6ce8d1717b570602d21072`, current branch
`pd/panel-integrate`. The round-2 addendum controls the branch and exact three-file
write grant. `REPORT_CRUX.md` is **NOT_WRITTEN: excluded by that final grant**;
this verdict and `harness/panel_pd/runs/2026-09-04/crux.json` carry the report.
No tracked production or existing test file in the checkout was edited. No merge, push,
tag, install, branch change, or live Houdini action was performed.

## Verdicts and acceptance ledger

These judge the composed source against the strict accepts, not an author's
intent or the isolated branch. An exemption explains a residual; it does not
change a raw-zero requirement or waive docking. `chain_broken_at` identifies the
source of the surviving defect/acceptance gap; the old integration splice is
tracked separately as repaired.

| Leg | Verdict | chain_broken_at | Evidence and unmet accepts |
|---|---|---|---|
| CENSUS | SOUND | null | Fresh source-only census and 21 census tests pass. Base archive independently reproduces 107 spacing / 106 sheets / 135 six-digit sites / 75 distinct values. Map has all six camera regions and names the real external shelf separately (`docs/PANEL_REGION_MAP.md:13`). The plan's discrepant figures are reported, not pinned as expectations. |
| LEVER | BROKEN | `7b17c0c3` — global guard definition, `tests/test_panel_rhythm_owner.py:79` | Layout recording/role removal/recompose, Expert and density accepts pass. Six-line compositor change; protected tokens/fontload unchanged. The global guard permits an exact deleted seed owner to return; the current 226 ceiling does not enforce the measured 62-site residual. Docking is not green; local Qt accepts NOT_RUN and historical receipts contain width failures. |
| CAMERA | BROKEN | `da5aac31` — strict raw-zero gap | Actual camera census is **2 spacing / 1 sheet / 0 hex**, at `recall_card.py:114`, `:115`, `synapse_panel.py:333`. T1–T6 source/display controls pass; completion, lifecycle, worker and shelf protections pass. Twelve profile PNGs exist and match REPORT_CAMERA hashes, but predate this review. Current 380px docking, host rendering, and Joe's H22.0.400 sign-off are NOT_RUN; the earlier integrated docking log is red. |
| SWEEP_A | BROKEN | `ed41ce61` — raw-zero and test migration gaps | Actual six-file census is **12 / 0 / 0**, all twelve spacing sites tagged. Source structure/role controls pass. Four obsolete chat CSS pins and the whole-tail append pin fail. Historical Qt state-colour failures motivated the now-repaired splice; current colour tests NOT_RUN. A current rhythm-only PNG comparison is NOT_RUN. |
| SWEEP_B | BROKEN | `ae046513` — HDA visual parity | All twelve owned files are **0 / 0 / 0**, with zero grid sites. All 104 removed six-digit/shorthand sites are mapped; targets exist in unchanged tokens. Legacy deletion condition remains false. HDA Result surfaces and button treatment changed beyond gaps/labels/tags; four historical sequence probes abort at layout checks before geometry/actions. Two isolated-only source pins fail. Full pytest green accept is not met. |

Source paths abbreviated in this table are under `python/synapse/panel/`.
Wave-wide completion also fails: **62 residual sites**, **15 tags**, against
the plan's **at most 20, all tagged**. Of the 62, 47 have no exemption tag.
Producer: fresh `panel_rhythm_census.py` output, embedded in `crux.json` as
`census_current`, with every source site and line. Not all of those 47 sites
introduce a distinct colour: comments and inherited literals are deliberately
counted by the census.

## Repaired splice and protected neighbours

At `python/synapse/panel/designsystem/qss.py:498`, `sweep_a_style` now sets both
properties, then unpolishes, polishes and updates the target. Its complete
SWEEP_A tail equals `ed41ce61`; the complete SWEEP_B tail equals `ae046513`,
after stripping only separator whitespace. The LEVER prefix is byte-exact.
`crux.json.static_audit.qss_blocks` records both tail hashes and comparisons.

Three independent **recording-protocol** cases exercise first → second → first
transitions through the real helper: **3 passed**. Removing the repaired calls
again in scratch gives **3 failed**. These are deliberately not Qt paint tests.
The actual GateWidget / ContextChips / SynapseChatPanel colour cases remain
NOT_RUN locally; no post-`38cd9b46` Qt receipt is present.

The neighbours pass the protected-source checks: fontload, design tokens,
token_readout, claude_worker, external shelf, and the retained legacy token/style
pair are byte-identical to `6e3dd963`. Thirteen protected panel methods and three
FaceToken refresh/measurement methods equal `ce04dcb0`; CAMERA's existing tests
also check timer/lifecycle source. `git diff 6e3dd963 38cd9b46 --numstat --
python/synapse/panel/compositor.py` is **5 additions / 1 deletion**. The generated
sheet contains twelve density blocks, carrying only margin-top, margin-bottom
or margin-left; it has no standard-density selector. Added panel diff lines
contain no six-digit hex or Cohere/Voronoi text; no token/font-family definition
was added. Evidence: `crux.json.static_audit`, `supplemental_audit`, and green
owner/typography/density/CAMERA controls.

## Scratch binding, commands and suite counts

The archive was made from the reviewed commit with `git archive`, extracted by
Python `tarfile` to avoid binary corruption through a PowerShell text pipe.
All mutation copies, logs, bytecode-disabled runs and pytest temporary paths are
under `harness/panel_pd/runs/2026-09-04/crux_scratch/`. The bound runner is
`C:/Python314/python.exe`, Python 3.14.2, pytest 8.4.2. Each pytest process inserts
the archive's `python/` first and **asserts that `synapse.__file__` is inside the
archive** before invoking pytest via `runpy`. Full commands, environment,
bindings and raw transcripts are embedded in `crux.json`; its
`reproduction_scripts` preserve the temporary runner and mutation driver.

Every Qt-capable invocation uses `QT_QPA_PLATFORM=offscreen` and
`SYNAPSE_REDUCED_MOTION=1`. PySide6 import fails with `No module named 'PySide6'`;
no hython is bound on PATH. No new screenshot is claimed.

| Run | Passed | Failed | Skipped | Result |
|---|---:|---:|---:|---|
| Initial census/owner/Expert/density/repolish control | 70 | 0 | 0 | Baseline-green before mutations |
| Expanded leg accepts and neighbours | 312 | 7 | 161 | The seven panel source-pin failures below |
| Full `tests -q -p no:cacheprovider`, once | 7014 | 30 | 351 | Exit 1; pytest elapsed 186.92s |
| Published `harness/panel_pd/BASELINE.md:8` | 6941 | 1 | 192 | Comparison floor, not same-environment control |
| Full-run delta versus published baseline | +73 | +29 | +159 | Raw pass floor met; suite not green |
| Restored targeted controls, including Expert/density | 86 | 0 | 0 | After the main mutation sequence |

The 30 full-run failures are: known backfill (1), panel source-pin conflicts (7),
archive/worktree-metadata checks (12: five harness-lock, four statusline, three
worktree-guard), orchestration (eight), ACL probe (one), and decisions aging
gate (one). The archive's missing Git metadata is explicit in the twelve traces;
root causes of the other environmental failures are not established here.
All identities and traces are retained. Versus the older orchestrator full run
(7069/8/318), this is -55 passes, +22 failures, +33 skips; do not substitute the
older counts for this run. That old receipt's `exit 0` does not make its eight
pytest failures green (`fullsuite_integrate.txt:15`).

The archived source and existing test files were checked against Git after
mutation restoration: **537 files, zero differences**. Later supplemental
mutations also restore and record their original SHA-256. The untouched worktree
HEAD stayed `38cd9b46` throughout. Archive Git-history queries are a separate
limitation below, not a false claim of full isolation from parent Git discovery.

## Mutations: measured outcomes

All edits below occurred only in scratch, one at a time, with byte restoration
in `finally`. Selected controls were green first (7 passed / 15 Qt skips).
Full commands and red assertions are in `crux.json.mutations`.

| Required mutation | Test that went red / result |
|---|---|
| Remove shared compose/recompose `rhythm.apply` | `test_panel_rhythm_owner.py::test_initial_compose_and_actual_recompose_share_post_build_rhythm`: **1 failed**, at the real `_recompose` sequence's spacing assertion. |
| Set density to an unknown value | Curious manifest → `crux-unknown`; `test_rope_density.py::TestManifestDensity::{test_each_manifest_declares_expected_density,test_declared_manifests_validate_clean}`: **2 failed**. Direct `rhythm.apply` fallback remains intentionally standard, not a schema allowance. |
| Add one untagged `setStyleSheet` in a migrated file | New call in working_indicator: global owner ratchet and SWEEP_B zero-owner control both red, **2 failed**. |
| Add one six-digit hex in a migrated file | vex_tutor: global owner ratchet and SWEEP_B no-hex control both red, **2 failed**. |
| Widen airy until 380px fails | Multiplier 1.5 → 100.0 applied and restored; component/composed docking selection gives **18 skipped**, exit 0. **NOT_RUN for geometry: no real PySide6.** This proves neither width nor a biting docking guard. |

Additional falsification:

- Recreate the missing QSS repolish tail: three new protocol controls go red;
  restored helper is green. Real state colour remains unmeasured.
- Restore pre-migration `self._dot.setStyleSheet(sheet)` in
  `WorkingIndicator._apply`: the global owner ratchet stays green. A second
  variant initializes `sheet` locally and confirms **global guard passes while
  SWEEP_B's local zero-owner guard fails**. This is a global-ratchet hole, not a
  claim that the whole suite accepts the regression. `_seed` retains every
  original identity indefinitely, and 226 leaves 164 sites of count slack.
- Raise the archive's cap 226 → 227: both global/history controls stay green.
  `git log -- harness/panel_pd/RESIDUAL.json`, run in the nested archive, returns
  no commits; `test_residual_cannot_increase_against_git_history` iterates zero
  times. This is an **archive verification gap**. Independent history from the
  real worktree confirms cap 226 and grid cap 2; no cap was changed there.

## Rulings on the seven panel test conflicts

The four `tests/test_chat_panel.py::TestCSSConsolidation` failures at
`:1048`, `:1065`, `:1073`, `:1082` require the old `get_*_stylesheet()` calls in
method source. SWEEP_A correctly routes these sites through design-system
properties/QSS and the root installer. **The pins are obsolete, not evidence
that restoring inline sheets is correct.** Their behavioural assertions must
move to the real QSS seam, with negative controls; do not delete, weaken, skip,
or satisfy them with dead calls. They remain red in this verdict.

The three isolated-only pins also require correction by their owners:

1. `test_panel_sweep_a.py:115` demands that the whole appended file end with
   END SWEEP_A; the contract requires SWEEP_B afterward. Fence-scope the check.
2. `test_panel_sweep_b_widgets.py:64` demands that the first post-LEVER block be
   SWEEP_B; the contract requires SWEEP_A first. Check the actual B fence.
3. `test_panel_sweep_b_hex.py:105` freezes all of synapse_panel and face_token
   against LEVER. CAMERA owns permitted changes in those files. Keep protection
   for lifecycle/completion methods and globally frozen files, and test each
   leg's own diff against its parent instead of forbidding its sibling's work.

## Qt receipt audit and the fifteen widths

Historical evidence: `qt_LEVER.txt`, `qt_SWEEP_A.txt`, `qt_INTEGRATE.txt` in
`harness/panel_pd/runs/2026-09-04/`. The integrated receipt names source
`0998cc9e`, Houdini .400 bundled Python 3.13.10 / PySide6 6.8.3 and headless
settings. Worker source explicitly inserts its tree's Python path. These are
credible historical runs, with no post-repair execution or printed module
binding to elevate them into current CRUX runtime evidence. LEVER's claimed
baseline-equal width control is narration in its receipt, not a new CRUX run.

The raw integrated traces (`qt_INTEGRATE.txt:33` through `:203`) give:

| Failed docking region | airy | standard | tight |
|---|---:|---:|---:|
| Composed panel | 433 | 433 | 433 |
| QuickActionPills | 602 | 592 | 587 |
| HDA ResultView | 388 | 384 | 382 |
| HealthStrip | 708 | 708 | 708 |
| SynapseChatPanel | 514 | 506 | 502 |

That is **five regions × three densities = 15 failed docking tests**. All exceed
380; inherited debt is still an unmet accept. The integrated receipt's prose
conflates these with the four SWEEP_B sequence failures. Those four instead
fail at `test_panel_sweep_b_widgets.py:176` or `:179`: DescribeView, ResultView,
ToolPalette and CommandPalette traverse layouts with unexpected spacing (three
traces show QBoxLayout spacing 0). Their `geometry()` and second-action checks
are downstream and unexecuted. Since `findChildren(QLayout)` also includes Qt
control internals, these traces alone do **not** identify a failing owned nested
layout. REPORT_SWEEP_B's universal inheritance assertion is unproved; split the
probe by real layout owner before certifying either layout or action behaviour.

The other six integrated reds are three source pins and three state-colour
cases. Thus 25 = 15 widths + 4 layout-sequence checks + 3 pins + 3 paint checks.
Current dimensions/paint are UNKNOWN; none of this table is relabelled as a
post-`38cd9b46` measurement.

## Neighbour and exemption audit; nits for consolidation

All fifteen rhythm tags have a substantive rationale. The two recall-band
seams and root sheet installation are necessary under the current role/installer
API. The twelve SWEEP_A nested-layout explanations match `rhythm.apply`'s
widget-layout-only ownership (`rhythm.py:74`); they justify keeping honest
residuals within the local write set, not calling them migrated. Their exact
paths, lines and individual rulings are in `crux.json.exemption_audit`. The three
docking tags describe ownership/structure constraints, not passing widths.

The 104 hex mapping rows match the independently inventoried removed sites,
including 24 shorthand sites. Role spot-checks distinguish VEX type emphasis
→ SIGNAL (`vex_tutor.py:817`), APEX attribute metadata → TEXT_SECONDARY
(`apex_trace.py:631`), and cross-scene category fills → SURFACE
(`cross_scene.py:415`, `:420`); these line numbers refer to `ce04dcb0`, as the
mapping table states. No cyan/blue source is selected merely by RGB proximity.
Six exact panel.tokens importers and one panel.styles importer remain in the
integrated AST; both `no-importers` commands exit 1. Keeping the legacy pair is
correct. Sibling unswept HTML producers retain the same colour-owner class:
agent_health 14 hex sites, render_preflight 6, and other files listed in the
census. HealthStrip retains two spacing calls/one sheet; integrity_readout two
spacing calls. They need named ownership; the 20-site target is not met.

**HDA visual parity is BROKEN.** The committed before/after ResultView images
are 368×420 and 340×420, so a raw pixel diff is not a geometry oracle. Even with
that limitation, the white table/native buttons become dark table surfaces and
a filled SIGNAL action. This is plainly beyond gaps/labels/tags.
`hda_views.py:317` adds standalone root-sheet installation; `qss.py:808` onward
adds DsHda surface, table and button rules. The same fallback serves DescribeView
and BuildingView, so audit their sibling surfaces too. The fallback may be an
intentional theme repair, but no parity waiver is present. Post-repair captures
and Joe's GUI judgement are NOT_RUN.

Suggested entries for `harness/notes/panel_nits_pd.md` (not written by CRUX):

- **Blocking:** settle the 62-site residual, 47 untagged sites, 226 ceiling and
  resurrectable seed identities; keep the guard sensitive after every migration.
- **Blocking:** update the seven obsolete/composition-conflicting tests at their
  real behaviour seams, prove them red, then rerun the integrated accepts.
- **Blocking:** identify owned layouts in SWEEP_B probes; rerun all four
  geometry/action sequences and all three repaired state-colour cases under Qt.
- **Blocking:** resolve the fifteen historical widths and HDA visual-parity
  change; exemptions and inherited status do not satisfy the strict accepts.
- **Verification:** archive Git-history tests must fail/declare unavailable on
  empty history, or use an explicit read-only history source. Do not fabricate
  a Git worktree or relax production assertions to green this archive run.
- **Inherited nit:** `styles.py:120` emits a doubled-brace ParamTable item rule;
  `qss.py:535` preserves the malformed input and `_sweep_a_rule` drops it. No
  emitted item selector remains. Paint effect UNKNOWN; do not claim exact CSS
  equivalence based only on selector-key existence.
- **Evidence hygiene:** prior REPORT delivery-block wording is stale relative
  to the orchestrator's commits; Qt/full-suite receipts need bound revision,
  module path and real pytest exit status. Preserve their historical failures.

## Delivery and honest limits

The three authorized outputs are written. Milestone staging attempts failed:
`fatal: Unable to create 'C:/Users/User/SYNAPSE/.git/worktrees/pd-panel-integrate/index.lock': Permission denied`.
This is a Git filesystem denial, not a human merge gate or an automatic approval
review rejection. **No CRUX commit exists.** Required prefix/trailer were kept
ready for the authorized commit; no alternate index, ACL change or bypass was
attempted. Scratch is deliberately uncommitted for orchestrator cleanup.

Could not verify: current Qt layout/font/paint and width mutation; current
before/after screenshots; live backend delivery; host theme/DPI/font provenance;
Joe's .400 GUI sign-off; exact PID-to-worktree ownership (CIM denied command-line
access); baseline-environment equivalence and all unrelated failure root causes;
full-suite green; successful Git delivery. No human gated act is requested.
