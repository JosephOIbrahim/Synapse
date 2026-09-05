# PD-LEVER report - 2026-09-04

**Delivery BLOCKED:** normal Git staging/committing is denied at this worktree's
`index.lock`. Implementation is written; no LEVER commit has been created.
Qt geometry/font measurements and screenshots are NOT_RUN because neither
PySide nor hython is bound. Independent CRUX and Joe's GUI sign-off are pending.
This is not a green wave receipt.

Branch: `pd/panel-lever`; inherited commit `a5b975c1` (CENSUS), product base
`6e3dd963`. The inherited CENSUS report describes an earlier commit blockage;
`git log -1 --oneline` confirms its artifacts are now committed on this branch.
No changes to master, another branch, or deployed files were made.

## Deliverables and acceptance

| Deliverable / criterion | Verdict and evidence |
|---|---|
| v2 spec: pixel table, five patterns, region map, docking bound | WRITTEN: `docs/PANEL_RHYTHM_SPEC.md:1`; full census map incorporated by reference and compact six-camera table; v1 section 5 preserved verbatim after UTF-8 decoding |
| Role gap table and applier | IMPLEMENTED: `python/synapse/panel/designsystem/rhythm.py:17`, `:57`; role bases drawn from SPACE_GRID, fixed margins, root/descendant traversal, no top-level Qt import |
| Spacing by role/density, idempotence, removal negative control | PASS for recording protocol: `tests/test_panel_rhythm_owner.py:316`; real QLayout/QFont verification **NOT_RUN**: `tests/test_panel_rhythm_docking.py:82` (18 explicit PySide skips) |
| Unknown role uses standard, warns once | PASS recording control: `tests/test_panel_rhythm_owner.py:296`; direct unknown density also falls back; malformed manifest density remains rejected by existing rope tests |
| Compose and recompose wiring | PASS: `tests/test_panel_rhythm_owner.py:331` executes initial compose and the actual AST-extracted `SynapsePanel._recompose` method, then checks airy/tight/standard/airy on the same widget identities; `compositor.py:268` has one shared post-build repolish/apply pair |
| Compositor diff <=20 lines | PASS: `git diff --numstat -- python/synapse/panel/compositor.py` => 5 additions / 1 deletion = 6 changed lines |
| Generic role QSS, card bands, parm columns | IMPLEMENTED: `designsystem/qss.py:355`; existing tokens only; component structure/property tests at owner test `:196`; real pattern geometry **NOT_RUN** (15 skips) |
| Density carries margin only; standard has no block | PASS: owner test `:184`; seven inherited density-padding blocks removed; existing BP2 camera margin targets retained |
| Guard green at measured residual | PASS: owner test `:109`; `harness/panel_pd/RESIDUAL.json` seeds 348 primary sites = 107 spacing + 106 sheets + 135 raw hex; four grid sites guarded separately |
| No new untagged owners, ceiling only decreases | PASS: owner tests `:127`, `:142`, `:151`, `:164`, `:169`; identity multiset prevents deletion-funded new owners; history compares working tree, latest committed cap and predecessor |
| Every source-declared widget region at 380px, all densities | **NOT_RUN**: 3 composed-panel probes (all regions, five face/substates), 48 alternate-region probes, 3 recall probes skip without PySide; worker code at docking test `:250`, `:294`; recall also has an explicit absence seam |
| YAML height/minimums | PASS source binding: docking test `:49`; real bounds **NOT_RUN**; reads YAML's 400px total / 200px child limit, not the conflicting 420px token |
| Expert structural pin | PASS: 2 tests in `tests/test_rope_expert_pin.py` |
| BP2 density rule | PASS: 16 tests in `tests/test_bp2_paneldesign_density.py` |
| Typography and repolish pins | PASS: 6 `test_panel_typography.py`, 7 `test_bp2_paneltruth_density_repolish.py`, 11 `test_rope_density.py` |
| Zero new hex / family / token / production widget | PASS source diff and scan; both changed/new design-system Python files and both new test files contain zero raw six-digit hex literals; no font-family declaration added; no token file edit or new widget class |
| Protected files untouched | PASS: Git comparisons for fontload, tokens, synapse_panel, face_token, token_readout and external shelf launcher; lifecycle and refresh paths consequently unchanged |
| Full suite once / baseline | RUN: **6945 passed / 11 failed / 311 skipped**; raw pass-count floor met by 4, suite **not green**; comparison below |
| Dated STATUS and milestone commits | STATUS written; both milestone staging/commit attempts **BLOCKED** by filesystem denial; no merge/push attempted |

## Choices, constraints and handoff

- The explicit LEVER brief authorizes `harness/panel_pd/RESIDUAL.json`, although
  that file was omitted from the ownership-table row. No other production
  ownership was widened. Test-created temporary fixtures are confined to
  `harness/panel_pd/.tmp_lever/`, not part of the source deliverables.
- PD's STATUS/REPORT convention replaces the general bus/receipt locations.
  Before writing STATUS, `git worktree list` showed one `pd/panel-lever` checkout,
  no LEVER status file existed, and process IDs were inspected. CIM command-line
  attribution was denied; precise PID-to-worktree ownership could not be proven.
- The brainstorming and `.claude/skills/synapse-feature/SKILL.md` workflows
  informed specification/validation. The user's explicit autonomous brief and
  named output path supplied the implementation authorization and superseded
  their extra approval/spec-path steps. No new approval gate was invented.
- Initial construction and profile switching already share `compose()`.
  Applying before builders would miss initial widgets. Repolish and rhythm now
  run after builders on both paths through one shared pair of call sites.
  `synapse_panel.py` is not edited to add a redundant second path.
- Unknown role uses group spacing at **standard** density, fixed zero margins,
  and one warning per distinct unknown value. Unmarked widgets are untouched;
  removing a role preserves the current layout values, not constructor values.
- Nominal label/tag ratios are clamped to BP4 FONT_FLOOR_PX and supplied host
  body scale. Existing fontload applies mono; QFont applies uppercase/tracking.
  QSS cannot supply those latter properties in its documented list. Sources:
  [Qt stylesheet reference](https://doc.qt.io/qt-6/stylesheet-reference.html),
  [QFont capitalization/tracking](https://doc.qt.io/qt-6/qfont.html).
  Actual host-floor provenance remains UNKNOWN; no claim of H22 measurement.
- `rhythm_role="card"` denotes a collection's between-card gap. Individual
  DsCard interiors use zero fixed seam spacing and the three named bands.
  CAMERA must not stamp a collection role onto the fixed-band interior.
  Layout-bearing row/tag containers use fixed layout margins; leaf QLabel /
  QPushButton variants use QSS padding. Do not combine both on one widget.
- Parameter widths are opt-in child ids DsParmLabel/DsParmValue (128/64);
  DsParmControl's stretch is supplied by the caller. No third column is invented
  in the existing two-column TOKEN grid. UNKNOWN remains text.
- No existing source region is marked with a new rhythm_role in this leg.
  Camera/sweep migration remains downstream. A fresh in-memory census still
  measures **107 spacing / 106 inline / 135 raw hex / 4 grid / 0 exemptions**.
  The guard is an enforcement tool, not evidence that those sites were migrated.
- The 348 ceiling is provisional grandfathering, not the wave's final <=20
  tagged-site goal. CENSUS found 46 sites in twelve unassigned files; the
  orchestrator must resolve ownership. The residual cannot honestly reach 20
  solely through the existing assigned write sets.
- Rich-text subregions from the census are rendered inside transcript widgets;
  source inventories do not turn HTML spans into Qt widgets. The docking tests
  cover source-declared constructors and the composed faces, not every possible
  content/state, host font, DPI, runtime size, or scrolling document.

## Re-runnable validation

Run from this worktree. No substrate installation or GUI launch is needed for
the source checks. Qt worker processes explicitly force offscreen mode and
reduced motion, reject stubs, and have a 60-second timeout.

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:SYNAPSE_REDUCED_MOTION='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TEMP=Join-Path (Get-Location) 'harness/panel_pd/.tmp_lever'
$env:TMP=$env:TEMP
$env:TMPDIR=$env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
python -m pytest tests/test_panel_rhythm_owner.py tests/test_panel_rhythm_docking.py tests/test_panel_rhythm_census.py tests/test_rope_expert_pin.py tests/test_bp2_paneldesign_density.py tests/test_panel_typography.py tests/test_bp2_paneltruth_density_repolish.py tests/test_rope_density.py -q -p no:cacheprovider --tb=short -rs --basetemp harness/panel_pd/.tmp_lever/restored
python -m pytest tests -q -p no:cacheprovider --basetemp harness/panel_pd/.tmp_lever/full --tb=short
git diff --check
git diff --numstat -- python/synapse/panel/compositor.py
```

Restored targeted result: **88 passed, 87 skipped**, 1 warning, 1.60s, exit 0.
The 87 skips explicitly report PySide6/PySide2 absence. This includes all 24
new owner tests, one new source-bound docking test, and the 63 inherited tests
listed in the command. Python is 3.14.2; the warning reports the existing
vendored cp311/cp313 ABI mismatch. No binding for `hython` was found.

The first import control erroneously forbade the parent package's optional
`hou` import. That tested `synapse.__init__`, beyond the rhythm module's Qt-free
contract. The corrected control forbids PySide6/PySide2/qtpy and proves rhythm
imports under `python -I -S` with no Qt or QApplication; it does not claim the
entire parent package never attempts a host import. No existing test was weakened.

### Full suite - run once

Command is the full `python -m pytest tests ...` line above. Result: **6945
passed, 11 failed, 311 skipped**, 84 warnings, 189.42s (3m09s), exit 1.
All LEVER non-Qt checks and the required pins also passed in this composed run.

| Source | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Published `harness/panel_pd/BASELINE.md:8` | 6941 | 1 | 192 |
| Inherited `docs/panel_pd/REPORT_CENSUS.md` full run | 6920 | 11 | 224 |
| This LEVER run | 6945 | 11 | 311 |
| Delta versus published baseline | +4 | +10 | +119 |
| Delta versus inherited CENSUS | +25 | 0 | +87 |

The raw pass floor is met, but adding tests has not repaired inherited failures.
Existing-test passes remain 6899 after excluding 21 CENSUS and 25 LEVER passes;
that is 42 below the baseline (10 extra failures plus 32 extra skips). The 87
additional LEVER skips are explicit Qt absence. No baseline was edited and no
skip/failure was reclassified as a pass.

Every failure identity matches the inherited CENSUS report:

| Test | Observed failure |
|---|---|
| `test_backfill.py::test_backup_is_taken_and_source_intact` | Source byte equality fails at line 62; the one published baseline failure |
| `test_m2_path_policy.py::test_compose_parms_keep_tokens` | SimpleNamespace has no ComposeError (`solaris_compose_tools.py:165`) |
| `test_orchestrate_close_gate.py::test_receipt_uncommitted_holds_at_closing` | Empty state instead of closing (`:124`) |
| `test_orchestrate_close_gate.py::test_receipt_not_head_holds_at_closing` | Empty state instead of closing (`:141`) |
| `test_orchestrate_close_gate.py::test_receipt_head_but_no_release_holds_at_closing` | Empty state instead of closing (`:155`) |
| `test_orchestrate_close_gate.py::test_clean_leg_passes_end_to_end_in_dry_run` | Empty state instead of done (`:180`) |
| `test_orchestrate_close_gate.py::test_operator_harvested_main_tree_receipt_is_done` | Empty state instead of done (`:196`) |
| `test_orchestrate_close_gate.py::test_manifest_pinned_done_bypasses_gate` | Same identity as inherited CENSUS; no LEVER edit to this test or producer |
| `test_orchestrate_liveness.py::test_subagent_workflow_write_moves_last_write` | Same identity as inherited CENSUS (`:101`) |
| `test_orchestrate_liveness.py::test_fresh_subagent_beats_stale_main_transcript` | Same identity as inherited CENSUS (`:129`) |
| `test_write_plane_health.py::test_probe_bounded_on_real_acl_denied_dir` | Same identity as inherited CENSUS (`:388`) |

No new failure identity appeared. This does not establish the environmental root
cause of those failures/skips. They are outside this leg's exclusive write set;
no source repair, weakened assertion or additional full-suite run was attempted.
Existing full-suite logging also attempted the user-level `.synapse/logs` path
and received PermissionError from the sandbox. Test TEMP/TMP/TMPDIR remained
inside the worktree; no logging permission or path policy was changed.

## Proved the controls bite

Each mutation below was applied one at a time to an owned production file,
the named test was run, and original bytes were restored in a `finally` block.
The restored targeted run above then passed. Commands:

```text
python -m pytest tests/test_panel_rhythm_owner.py::<test-name> -q -p no:cacheprovider --tb=line
```

| Mutation | Test name | Observed red result |
|---|---|---|
| Remove `rhythm.apply(panel, resolved["density"])` from compose | `test_initial_compose_and_actual_recompose_share_post_build_rhythm` | 1 failed, exit 1 |
| Replace `tokens.gap(ROLE_GAPS[role], level)` with `tokens.gap(ROLE_GAPS[role], "standard")` | `test_recorded_layout_sequence_is_derived_from_base_not_current` | 6 failed, exit 1 |
| Replace unknown-role assignment `role, level = "group", "standard"` with `role = "group"` | `test_unknown_role_density_and_removed_role` | 1 failed, exit 1 |
| Append unused `_negative_owner(widget)` calling `widget.setStyleSheet("")`, untagged, to compositor | `test_panel_rhythm_owner_ratchet` | 1 failed, exit 1 |
| Change parameter-head density `margin-top` to `padding-top` in qss | `test_density_blocks_are_margin_only` | 1 failed, exit 1 |

Additional negative fixtures reject a new raw hex (assembled in memory, no new
palette literal), a duplicated existing call, a replacement owner at unchanged
count, an empty exemption, a fake string exemption, a multiline-call exemption
on the wrong line, and an increased residual ceiling. Real Qt mutations,
including widening airy until 380px fails, are **NOT_RUN** without PySide.

## Git delivery blocker

The Session A, Session B and final receipt staging/commit commands all returned:

```text
fatal: Unable to create 'C:/Users/User/SYNAPSE/.git/worktrees/pd-panel-lever/index.lock': Permission denied
```

These were the authorized subjects, each with trailer
`Co-Authored-By: Codex (gpt-6-astra) <noreply@openai.com>`:

- `pd(lever): specify role rhythm and strict docking bounds`
- `pd(lever): apply role rhythm and guard measured ownership`
- `pd(lever): record verification and delivery limits`

This is a filesystem denial, not an automatic approval-review rejection. No
ACL edit, alternate index, permission bypass, branch switch, merge, push, tag,
VERSION edit or live Houdini action was attempted. Normal Git metadata writes
must become available before the user's already-authorized commits can happen.

## Files / receipt

The exact deliverable set is:

1. `docs/PANEL_RHYTHM_SPEC.md`
2. `python/synapse/panel/designsystem/rhythm.py`
3. `python/synapse/panel/designsystem/qss.py`
4. `python/synapse/panel/compositor.py`
5. `tests/test_panel_rhythm_owner.py`
6. `tests/test_panel_rhythm_docking.py`
7. `harness/panel_pd/RESIDUAL.json`
8. `harness/panel_pd/STATUS_LEVER.md`
9. `docs/panel_pd/REPORT_LEVER.md`

Do not stage the disposable test fixtures under `.tmp_lever`.

Receipt: `leg=panel_pd:LEVER:BUILD`; `verdict=BLOCKED`; touched/artifacts/commands
above; `proved_it_bites` is the five-mutation table; `could_not_verify=[real
QLayout/QFont behavior, 380x400 docking, actual host font floor, PNGs, Joe's
H22.0.400 GUI sign-off, independent CRUX, precise process-to-worktree ownership,
root causes of inherited full-suite failures, Git commit delivery]`;
`needs_human=[]` for gated repository acts (none requested). The Git denial is
an environment blocker, not a request for merge or permission to widen scope.
