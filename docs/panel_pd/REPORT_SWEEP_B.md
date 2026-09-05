# PD-SWEEP_B report — 2026-09-04

**BLOCKED delivery; implementation and source verification complete.** Branch
`pd/panel-sweep_b`, inherited revision `ce04dcb0`. Zero commits since that revision:
normal Git staging/committing cannot create this worktree's `index.lock`.
Qt, docking geometry, screenshots and independent CRUX are **NOT_RUN**.
This is not a green wave receipt.

Final targeted run: **252 passed / 119 skipped / 0 failed**. Full suite, run once:
**6967 passed / 19 failed / 317 skipped**. Eight failures were introduced by this
migration and repaired afterward; all eight pass in the final targeted run.
Eleven other failure identities match inherited REPORT_LEVER. No synthetic final
full-suite count or full-green claim is made.

## Deliverables and acceptance

| Criterion | Verdict and evidence |
|---|---|
| Four widget migrations | Source PASS: `python/synapse/panel/hda_views.py:22`, `tool_palette.py:147`, `command_palette.py:392`, `working_indicator.py:209`; roles own spacing and ids/properties select central QSS |
| Twelve-file census zero | PASS: each named module has 0 spacing / 0 inline sheet / 0 raw hex / 0 extra grid-spacing sites; producer and counts below |
| Every removed hex mapped | PASS: `docs/panel_pd/HEX_MAPPING_SWEEP_B.md:1`, 104 rows = 80 six-digit + 24 shorthand source sites; original file/line/value/token/rationale recorded against ce04dcb0 |
| Independent mapping audit | PASS: `tests/test_panel_sweep_b_hex.py:42` inventories inherited Git source and compares exact site multisets with the parsed table; unmapped/invented rows and remaining colors are rejected |
| No new tokens/fonts/widgets | PASS: token source and fontload unchanged; no raw hex or font-family declaration in appended QSS; widget-constructor inventory has no additions |
| QSS append-only | PASS: inherited byte prefix identical; sole SWEEP_B fence starts at `python/synapse/panel/designsystem/qss.py:450`; existing generator is chained |
| Spacing/state sequences | Source PASS; actual Qt NOT_RUN. Six isolated workers in `tests/test_panel_sweep_b_widgets.py:110` exercise airy -> tight -> standard -> airy, fixed margins, nested inheritance, idempotence, role removal and second actions |
| Owned docking failures | Implemented, geometry NOT_RUN: HDA options/chips reflow, shorter action labels with full accessible names/tooltips, text wrapping, stretching table columns, popup preferred sizes instead of hard minima. No exemption used to declare unmeasured geometry green |
| Legacy pair | KEEP: 7 exact tokens importers and 3 styles importers; both files unchanged; finding below |
| Residual only decreases | PASS: 348 -> 268 at M1 -> 226 final; original seed evidence unchanged; separate grid ceiling remains 4 |
| Rhythm owner guard | PASS: all 24 tests in `tests/test_panel_rhythm_owner.py` |
| Expert pin | PASS: both `tests/test_rope_expert_pin.py` tests |
| Density rule | PASS: all 16 `tests/test_bp2_paneldesign_density.py` tests; density declarations remain margin-only, standard emits no density selector |
| Repolish/typography/authority | PASS: `test_bp2_paneltruth_density_repolish.py`, `test_panel_typography.py`, `tests/panel/test_token_authority.py` in final targeted run |
| Docking suite | NOT_RUN geometry: 87 inherited PySide-absence skips; YAML-bound source check passes. The user's inherited 24 Qt docking reds are not reclassified as fixed |
| Full pytest green | NOT MET: recorded run had 19 failures; 8 owned regressions repaired and verified afterward; 11 inherited identities outside this write set. No assertion weakened |
| Screenshots/visual parity | NOT_RUN: no hython bound; no PNG generated. H22.0.400 appearance, host theme/font/DPI and Joe's GUI sign-off unverified |
| STATUS/commits | Dated STATUS written; M1/M2 staging and commit attempts failed with Permission denied. Final attempt recorded in STATUS; zero commits, no merge/push/tag or branch switch |

## Implementation choices

- DescribeView and ResultView use `parm_row` for compact forms; BuildingView
  uses `group`. ToolPalette and WorkingIndicator use `parm_row`; CommandPalette
  uses `group` with its existing inner container marked `parm_row`. HDA section
  text uses `label`; palette axis captions use `tag`.
- Nested layouts have no explicit spacing. Qt documents inheritance from the
  parent layout when spacing is unset, allowing the marked owning widget to
  control them without adding containers. Actual inheritance is asserted by
  the unrun workers: [Qt 6.8 QLayout](https://doc.qt.io/qt-6.8/qlayout.html#spacing-prop),
  [Qt 6.8 QGridLayout](https://doc.qt.io/qt-6.8/qgridlayout.html#horizontalSpacing-prop).
- The inherited docking finding requires reflow beyond the mechanical reading:
  existing options/chips move into grids; HDA action text becomes Inspect /
  Parameters / Save HDA. Full descriptions remain in tooltips and accessible
  names; signals/actions are unchanged. No control, fold, profile knob or widget
  was added. Actual geometry remains NOT_RUN.
- Dynamic HDA success/error and stage-dot states, and busy/stalled indicator
  states, select QSS properties and repolish. The indicator's pure state machine,
  liveness inputs and STATUS color source remain unchanged.
- Separate popup windows use `qss.prepare_sweep_b_popup` to install the shared
  generator, copy the opener's density on opening and run the role applier.
  Preferred sizes replace hard minima; available screen/opener width bounds
  the requested size. Real constraints at all host scales remain unverified.
- Disjoint DsHda ids prevent retained legacy selectors overriding the new rules.
  Review found the alternate Chat/HDA entry installs only its legacy sheet
  (`chat_panel.py:217`). At show time `qss.ensure_sweep_b_view` supplies the central
  sheet on the existing view when there is no DsRoot ancestor; modern roots
  supply it by inheritance. Both paths are in the unrun real-Qt workers.
- Blue/cyan is chosen by purpose: actionable/type emphasis -> vendored SIGNAL;
  metadata -> seeded neutral text; badge background -> SURFACE. Historical
  sources and per-site reasoning are in the mapping table. No RGB-distance
  calculation or off-repo import. Existing warning/error and speaker semantics
  remain authoritative.
- The stricter raw-site census includes comments, redundant fallback literals,
  command_palette's five sites and shorthand HTML colors; numeric HTML entities
  are excluded. Old colors in the mapping table are evidence, not declarations.
- The brief explicitly authorizes RESIDUAL.json despite its omission from the
  ownership table. Only its ceiling changes. PD STATUS/REPORT replace general
  bus/receipt locations; source edits and evidence remain in this worktree.
- Used using-superpowers and `.claude/skills/synapse-feature/SKILL.md` for source
  and validation discipline. The user's approved brief supplies authorization
  and supersedes the skill's extra approval step.
- Ownership sweep: one matching SWEEP_B worktree, no prior STATUS, PID inventory
  read via Get-Process. CIM command-line attribution returned Access denied;
  exact PID-to-worktree attribution remains unknown. No duplicate conductor
  on this leg was identified.

## Census and residual

Producer: `harness/notes/panel_rhythm_census.py::census`, source-only. Re-run
without overwriting the previous leg's artifacts:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
@'
from pathlib import Path
import importlib.util
s = importlib.util.spec_from_file_location('pd_census', 'harness/notes/panel_rhythm_census.py')
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
r = m.census(Path('python/synapse/panel'))
print(r['totals'])
owned = {'hda_views', 'tool_palette', 'command_palette', 'working_indicator',
         'vex_tutor', 'apex_trace', 'apex_explainer', 'scene_doctor',
         'performance_profiler', 'network_trace', 'cross_scene', 'message_formatter'}
for f in r['files']:
    if Path(f['path']).stem in owned:
        print(f['path'], {k: len(f[k]) for k in ('spacing', 'inline_styles', 'hex_sites', 'grid_spacing')})
'@ | python -
```

| Source | Spacing | Inline | Six-digit hex | Extra grid |
|---|---:|---:|---:|---:|
| Inherited panel | 107 | 106 | 135 | 4 |
| Final panel | 90 | 81 | 55 | 4 |
| Removed by SWEEP_B | 17 | 25 | 80 | 0 |
| Each of twelve owned modules, final | 0 | 0 | 0 | 0 |

Primary ceiling: 90 + 81 + 55 = **226**. Zero exemptions needed or added.
Remaining sites are outside the twelve migrated files. The wave-wide <=20 goal
is not claimed by this leg.

## Legacy pair finding

Both commands returned **exit 1**, no stdout:

```text
python .synapse/verify.py no-importers python/synapse/panel/tokens.py python/synapse/panel
python .synapse/verify.py no-importers python/synapse/panel/styles.py python/synapse/panel
```

The verifier matches stems. A separate AST census resolved relative imports to
full package names, excluding designsystem.tokens from panel.tokens importers.

| Imported module | Exact final importers under python/synapse/panel |
|---|---|
| tokens | apex_recipes.py:32; chat_panel.py:63; context_bar.py:54; error_translator.py:23; quick_actions.py:102; recipe_book.py:32; styles.py:7 |
| styles | chat_display.py:27; chat_panel.py:46; gate_widget.py:22 |

HDA and command palette now import vendored roles directly. The conditional
deletion predicate is false; both legacy files stay unchanged. Other owners'
importers were not edited.

## Validation

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:SYNAPSE_REDUCED_MOTION='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TEMP=Join-Path (Get-Location) 'harness/panel_pd/.tmp_sweep_b'
$env:TMP=$env:TEMP
$env:TMPDIR=$env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
python -m pytest tests/test_panel_sweep_b_hex.py tests/test_panel_sweep_b_widgets.py tests/test_panel_rhythm_owner.py tests/test_panel_rhythm_docking.py tests/test_rope_expert_pin.py tests/test_bp2_paneldesign_density.py tests/test_bp2_paneltruth_density_repolish.py tests/test_working_indicator.py tests/test_panel_typography.py tests/test_chat_panel.py tests/test_w2s2_format_offmain.py tests/panel/test_token_authority.py tests/test_hda_panel.py -q -p no:cacheprovider --basetemp harness/panel_pd/.tmp_sweep_b/final --tb=short -rs
python -m pytest tests -q -p no:cacheprovider --basetemp harness/panel_pd/.tmp_sweep_b/full --tb=short
git diff --check
```

Chronology: mapping/pins 35 passed; widget/pins 101 passed / 95 skipped; full
suite once; final repair and expanded targeted run. Commands above reproduce
each result, rather than describe chronological order.

Final targeted result: **252 passed / 119 skipped**, 1 ABI warning, 5.74s, exit 0.
All 31 current SWEEP_B non-Qt tests pass; six SWEEP_B Qt workers skip honestly.
All eight formerly failing formatting tests and the new regression check pass.
HDA fallback changes are included in this final targeted run. The full suite
started before that fallback review and before the final formatter repair;
there was no second full run.

Transient raw logs: `harness/panel_pd/.tmp_sweep_b/final_targeted.txt` and
`harness/panel_pd/.tmp_sweep_b/full.txt`. They and temporary pytest fixtures are
not deliverables to stage; commands, counts and failure identities are preserved
here. `git diff --check` passes. Nine sources compared against Git are unchanged:
fontload, designsystem tokens/rhythm, compositor, synapse_panel, face_token,
external shelf, legacy tokens and legacy styles. QSS inherited byte prefix is
identical; only its appended fence changes.

### Full suite — once, not green

Python 3.14.2, 84 warnings, 202.60s, exit 1:

| Source | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Published harness/panel_pd/BASELINE.md | 6941 | 1 | 192 |
| Inherited docs/panel_pd/REPORT_LEVER.md | 6945 | 11 | 311 |
| Recorded SWEEP_B full run | 6967 | 19 | 317 |
| Delta vs published baseline | +26 | +18 | +125 |
| Delta vs inherited LEVER | +22 | +8 | +6 |

The raw pass floor is met. Thirty new non-Qt tests passed in the full run;
those additions must not hide the eight existing tests this migration broke.
A thirty-first non-Qt test was added after that failure. No recalculated final
full-suite result is asserted.

**Owned regression, repaired:** color replacement turned the documentation
string in `message_formatter._speaker_label` into an f-string referencing
undefined `_ds`. Restored a plain docstring with token names as text. New test
`test_existing_message_output_remains_byte_identical` was first observed red,
then green after the repair. It compares actual inherited and migrated user/
agent output across grouping, timestamps and HTML escaping. Eight full-run
failures reported this NameError and all pass in the final targeted run:

```text
tests/test_chat_panel.py::TestUserMessageFormat::test_user_message_has_signal_rule
tests/test_chat_panel.py::TestUserMessageFormat::test_user_message_has_no_bubble
tests/test_chat_panel.py::TestUserMessageFormat::test_user_message_escapes_html
tests/test_chat_panel.py::TestSynapseMessageFormat::test_synapse_no_bubble
tests/test_chat_panel.py::TestSynapseMessageFormat::test_synapse_uses_canonical_signal
tests/test_w2s2_format_offmain.py::test_pipeline_output_is_byte_equal_to_direct_format
tests/test_w2s2_format_offmain.py::test_grouped_and_ungrouped_differ_NEGATIVE_CONTROL
tests/test_w2s2_format_offmain.py::test_format_synapse_message_zero_qt_zero_hou_at_boundary
```

**Inherited failure identities, outside this leg's write set:**

```text
tests/test_backfill.py::test_backup_is_taken_and_source_intact
tests/test_m2_path_policy.py::test_compose_parms_keep_tokens
tests/test_orchestrate_close_gate.py::test_receipt_uncommitted_holds_at_closing
tests/test_orchestrate_close_gate.py::test_receipt_not_head_holds_at_closing
tests/test_orchestrate_close_gate.py::test_receipt_head_but_no_release_holds_at_closing
tests/test_orchestrate_close_gate.py::test_clean_leg_passes_end_to_end_in_dry_run
tests/test_orchestrate_close_gate.py::test_operator_harvested_main_tree_receipt_is_done
tests/test_orchestrate_close_gate.py::test_manifest_pinned_done_bypasses_gate
tests/test_orchestrate_liveness.py::test_subagent_workflow_write_moves_last_write
tests/test_orchestrate_liveness.py::test_fresh_subagent_beats_stale_main_transcript
tests/test_write_plane_health.py::test_probe_bounded_on_real_acl_denied_dir
```

These identities appear in inherited REPORT_LEVER; their environmental root
causes are not established here. Existing full-suite logging attempted the
user-level `.synapse/logs` path and the sandbox denied it. No permission, ACL,
baseline, assertion, skip or other owner's source was altered.

## Proved it bites

Command form: `python -m pytest <test-node> -q -p no:cacheprovider --tb=line`.
Intentional source/table mutations were restored byte-for-byte in finally.

| Mutation / actual defect | Test node (under tests/) | Red result |
|---|---|---|
| Delete first mapping row | test_panel_sweep_b_hex.py::test_every_removed_hex_has_an_exact_mapping_site | 1 failed, exit 1 |
| Append raw six-digit color to vex_tutor | test_panel_sweep_b_hex.py::test_migrated_source_has_no_remaining_hex[vex_tutor] | 1 failed, exit 1 |
| Remove WorkingIndicator role | test_panel_sweep_b_widgets.py::test_each_real_constructor_declares_its_layout_role[working_indicator.WorkingIndicator-parm_row] | 1 failed, exit 1 |
| Append unused inline-sheet owner | test_panel_sweep_b_widgets.py::test_migrated_widget_has_zero_imperative_rhythm_owners[working_indicator] | 1 failed, exit 1 |
| Actual speaker f-docstring defect | test_panel_sweep_b_hex.py::test_existing_message_output_remains_byte_identical | 1 failed, exit 1 before repair |

Intermediate checks also caught nonexistent weight/selection token references
and an encoding change in the inherited QSS prefix. Existing tokens were chosen
and the original prefix restored. Neither defect survives. Real Qt/docking
mutations remain NOT_RUN.

## Git delivery and receipt

Intended subjects, each with trailer
`Co-Authored-By: Codex (gpt-6-astra) <noreply@openai.com>`:

- pd(sweep_b): migrate report colors to existing semantic tokens
- pd(sweep_b): centralize widget rhythm and constrain docking demand
- pd(sweep_b): record final sweep verification and delivery limits

Normal M1/M2 staging and commit attempts returned:

```text
fatal: Unable to create 'C:/Users/User/SYNAPSE/.git/worktrees/pd-panel-sweep_b/index.lock': Permission denied
```

Final attempt is recorded in STATUS. This is a filesystem denial, not a human
merge gate. No alternate index, permission bypass, branch switch, merge, push,
tag, release edit or live Houdini action. Normal Git metadata writes must become
available before already-authorized commits can be delivered.

The 19 deliverables are the twelve census-listed modules, designsystem/qss.py,
tests/test_panel_sweep_b_hex.py, tests/test_panel_sweep_b_widgets.py,
docs/panel_pd/HEX_MAPPING_SWEEP_B.md, this REPORT,
harness/panel_pd/RESIDUAL.json and harness/panel_pd/STATUS_SWEEP_B.md.
Do not stage `.tmp_sweep_b`.

Receipt: `leg=panel_pd:SWEEP_B:BUILD`; `verdict=BLOCKED`; touched/artifacts/
commands above; proved_it_bites in table;
`could_not_verify=[real Qt spacing/state/docking, final full-suite green,
H22.0.400 appearance and host font/theme/DPI, screenshots, Joe's GUI sign-off,
independent CRUX, exact PID attribution, inherited failure root causes,
Git commit delivery]`; `needs_human=[]` (no gated act requested).

Orchestrator handoff: run Qt under offscreen/reduced-motion settings and CRUX on
the integrated tree. Other owners' inherited docking failures remain outside
this leg. No wave-green receipt is asserted.
