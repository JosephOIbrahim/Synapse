# PD-SWEEP_A report ? 2026-09-04

Delivery **BLOCKED by Git metadata permissions and four out-of-scope source-test conflicts**. The six-module migration and
source verification are written in the assigned worktree. Qt geometry, painted
state checks, screenshots and independent CRUX are **NOT_RUN**. This is not a
green runtime or committed-delivery receipt.

Branch `pd/panel-sweep_a`, inherited `ce04dcb0` from LEVER. The orchestrator's
committed Qt receipt supersedes the older delivery-block wording in REPORT_LEVER:
`harness/panel_pd/runs/2026-09-04/qt_LEVER.txt` records 110 passed, 24 inherited
docking failures and 3 skips, with pre-LEVER controls.

## Acceptance and census

Producer: `harness/notes/panel_rhythm_census.py:census`, called in memory over
`python/synapse/panel`. The committed CENSUS artifacts are unchanged. The six
owned files now have **12 spacing / 0 inline sheets / 0 raw hex**, and every
remaining spacing call has a same-line reason. The strict raw 0/0/0 target is
**not met**: the brief's explicit structural-exemption route is used for 12
nested-layout sites. Untagged spacing / inline sheets / raw hex is **0/0/0**.
The raw census must not be represented as zero.

| File | Raw spacing | Inline sheets | Raw hex | Tagged exemptions |
|---|---:|---:|---:|---:|
| `chat_panel.py` | 4 | 0 | 0 | 4 |
| `face_review.py` | 2 | 0 | 0 | 2 |
| `gate_widget.py` | 2 | 0 | 0 | 2 |
| `context_bar.py` | 2 | 0 | 0 | 2 |
| `face_work.py` | 2 | 0 | 0 | 2 |
| `quick_actions.py` | 0 | 0 | 0 | 0 |

The panel-wide primary ceiling in `harness/panel_pd/RESIDUAL.json` falls from
348 to **236**: current 63 spacing + 42 inline sheets + 131 raw hex. Grid
spacing falls from 4 to **2** after Review's two-axis grid migration. The six
files removed 44 primary spacing calls, 64 inline-sheet calls and four old
palette literals in Context Bar comments. No other leg's source was swept.

| Criterion | Evidence / verdict |
|---|---|
| Every widget-owned imperative layout site becomes a role | PASS static: `test_every_former_widget_layout_owner_has_a_role_in_its_own_scope`, independently derives owners from the inherited source, including repeated local variable names in separate constructors |
| Same widgets, layout membership, parenting and signal connections | PASS static: `test_no_new_structure_and_every_residual_is_reasoned` compares AST inventories with ce04dcb0 |
| Scoped QSS, append-only, all state keys reachable | PASS static: `test_qss_is_append_only_and_every_style_key_has_rules`; entire inherited qss.py prefix unchanged, one fenced append grouped in requested file order |
| Hover and subcontrol selectors stay on their targets | PASS static: `test_scoped_rules_keep_pseudo_states_on_the_target` |
| Three densities and role-removal negative control on production widgets | NOT_RUN: 24 isolated real-Qt probes across eight constructors/factories, PySide6/PySide2 absent |
| Repeated gate/context/work/chat/quick-action state paint | NOT_RUN: six isolated real-Qt sequence probes, PySide absent |
| Owner guard, Expert pin, density rule | PASS in final targeted run; exact command below |
| Docking at 380 px | NOT_RUN here, with inherited red evidence and documented exemptions below; untouched docking tests remain strict |
| panel_shot.py rhythm-only before/after comparison | NOT_RUN: no bound hython; no PNGs created or copied into `design/rhythm_pd/sweep_a/{before,after}/` |
| GUI sign-off / independent CRUX | NOT_RUN: separate human/CRUX acts; builder does not certify either |
| Full suite once and baseline counts | See full-suite receipt below |
| Dated STATUS and milestone commits | STATUS written; each milestone staging/commit attempt denied at index.lock; no new commit exists |

## Implementation choices and boundaries

- Followed the six-file order in the brief. Widget-owned compact rows use the
  existing `parm_row` role (base 4); region containers use `group` (base 16);
  the proposal collection uses `card` (base 16). Their fixed layout margins
  come from LEVER's existing role table, without new role/token definitions.
- Nested QLayouts have no separate QWidget owner and LEVER only visits
  `widget.layout()`. Stamping their parent would affect the parent's own layout,
  not the nested layout. Wrappers would violate the fixed hierarchy. This is
  the stricter structural interpretation behind the exemptions below.
- `qss.sweep_a_style` sets paint-selection properties and repolishes the target;
  it does not create per-widget sheets. QSS emits all existing color-state
  variants from the token table. Gate UNKNOWN/unreachable/decision logic and
  timers stay in their existing methods. Late proposal cards inherit density
  through `qss.sweep_a_refresh_rhythm` after insertion.
- The alternate `SynapseChatPanel` entry has no compositor. It gets DsRoot and
  installs the same QSS authority plus initial standard rhythm through
  `qss.install_sweep_a_root`, after construction. Main-panel composition still
  owns normal profile/recompose rhythm; compositor.py is untouched.
- Legacy declarations were moved, including existing hover/pressed ramps and
  dimensions; the final QSS repairs preserve numeric type values and color
  channels while expressing them through the authority (details below). Existing `FONT_MONO_CSS` / `FONT_SANS_CSS` replace repeated family
  strings. No family or token definition was added. Actual fallback-font and
  stylesheet-cascade equivalence remain unverified without Qt/PNGs.
- No new widget, hex literal, font family, token, lifecycle path, host API,
  connection start, gate decision, shelf path, or memory accessor was added.
  Fontload, tokens, compositor, synapse_panel, face_token, shelf, master and all
  other branches are untouched (`git diff --name-only`).
- RESIDUAL.json is expressly authorized by this brief despite omission from
  the table. Temporary test/log output is confined to `.tmp_sweep_a` in this
  worktree. No baseline, ownership contract or ratification was changed.
- Applied the using-superpowers, brainstorming and local synapse-feature
  workflow guidance. The user's supplied file-by-file design and autonomous
  implementation authorization supersede extra skill approval/spec-path steps.
  No additional design document or permission gate was invented.
- SWARM_CONTRACT replaces the general bus with STATUS/REPORT. Worktree/PID/status
  inventory found one matching worktree and no previous SWEEP_A status. Exact
  process-to-worktree attribution was unavailable; other leg worktrees exist.

## Every retained rhythm exemption

Paths below are relative to `python/synapse/panel/`.

- `chat_panel.py:395`: `input_row.setSpacing(8)` ? nested layout has no widget owner; wrapping changes the hierarchy
- `chat_panel.py:411`: `controls_layout.setSpacing(4)` ? nested layout has no widget owner; wrapping changes the hierarchy
- `chat_panel.py:425`: `size_row.setSpacing(2)` ? fixed font-choice cluster has no separate widget owner
- `chat_panel.py:426`: `size_row.setContentsMargins(0, 0, 0, 0)` ? fixed font-choice cluster has no separate widget owner
- `face_review.py:268`: `self._flags_box.setSpacing(1)` ? nested flags layout has no widget owner; wrapping changes the hierarchy
- `face_review.py:296`: `self._via_box.setSpacing(1)` ? nested provenance layout has no widget owner; wrapping changes the hierarchy
- `gate_widget.py:166`: `top_row.setSpacing(8)` ? nested badge-operation row has no widget owner; wrapping changes the hierarchy
- `gate_widget.py:201`: `btn_row.setSpacing(8)` ? nested decision row has no widget owner; wrapping changes the hierarchy
- `context_bar.py:395`: `row1.setSpacing(SPACE_SM)` ? nested breadcrumb-status row has no widget owner; wrapping changes the hierarchy
- `context_bar.py:431`: `row2.setSpacing(SPACE_XS)` ? nested actions-frame row has no widget owner; wrapping changes the hierarchy
- `face_work.py:189`: `head.setSpacing(t.SPACE_SM)` ? nested activity row has no widget owner; wrapping changes the hierarchy
- `face_work.py:223`: `self._plan_box.setSpacing(2)` ? nested plan layout has no widget owner; wrapping changes the hierarchy

These 12 sites still count toward the primary residual. No tag conceals an
inline sheet or hex site; no new exemption is used to expand the ceiling.

## Docking exemptions / handoff

- `chat_panel.py:195`: child HDA view minimums belong to SWEEP_B
- `chat_panel.py:651`: connection actions and full URL share one fixed row; structural wrapping is out of scope
- `quick_actions.py:134`: five full action labels occupy one row; wrapping or scrolling changes the hierarchy

The connection row keeps the full URL, status and both actions, and Quick
Actions keeps five full labels in its existing horizontal row. Wrapping,
scrolling, dropping labels or adding a widget would change the required
structure. The brief explicitly permits a documented exemption for inherited
width debt. These are exemptions, **not a claim that the widgets fit 380 px**.
HDA descendants are SWEEP_B-owned. No inherited assertion was weakened.
The orchestrator/CRUX must measure the final widths after integration; old
720 px and 462..720 px measurements are not estimates of this tree.

## Verification commands and results

Run from this worktree, using the bound Python. For real Qt, the orchestrator
must supply its Houdini-bundled Python lane; tests reject Qt stubs and never
activate the chat bridge or show a live Houdini window.

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:SYNAPSE_REDUCED_MOTION='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TEMP=Join-Path (Get-Location) 'harness/panel_pd/.tmp_sweep_a'
$env:TMP=$env:TEMP
$env:TMPDIR=$env:TEMP
$env:SYNAPSE_LOG_DIR=Join-Path $env:TEMP 'logs'
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
python -m pytest tests/test_panel_sweep_a.py tests/test_panel_rhythm_owner.py tests/test_rope_expert_pin.py tests/test_bp2_paneldesign_density.py tests/test_gate_fidelity_honesty_sourcepin.py tests/test_panel_rhythm_docking.py tests/test_panel_typography.py tests/test_rope_prominence_visible.py -q -p no:cacheprovider --tb=short
python -m pytest tests -q -p no:cacheprovider --basetemp harness/panel_pd/.tmp_sweep_a/full --tb=short
git diff --check
```

Final targeted result: **87 passed, 117 skipped**, one inherited ABI warning,
7.93s, exit 0. SWEEP_A alone: **17 passed, 30 skipped**. The 30 new skips and
87 inherited docking skips mean NOT_RUN, never runtime green. Stock Python
3.14.2 `find_spec` found no PySide6, PySide2 or hou; `Get-Command hython` found
no executable. No install or host launch was attempted.

### Controls proved red

Applied one mutation at a time, ran the named test with
`python -m pytest tests/test_panel_sweep_a.py::<name> -q -p no:cacheprovider --tb=line`,
then restored original bytes in a finally block.

| Mutation / defect | Test | Observed result |
|---|---|---|
| Add untagged `self.setStyleSheet("")` to QuickActionPills construction | `test_no_new_structure_and_every_residual_is_reasoned[quick_actions.py]` | 1 failed, exit 1 |
| Rename the emitted work_note QSS key without changing the widget | `test_qss_is_append_only_and_every_style_key_has_rules` | 1 failed, exit 1 |
| Put the state property after :hover/::item instead of on its target | `test_scoped_rules_keep_pseudo_states_on_the_target` | 1 failed, exit 1 |
| Real omission: GateWidget._build_ui lacked its root role because a local layout name also occurred in _ProposalCard | `test_every_former_widget_layout_owner_has_a_role_in_its_own_scope[gate_widget.py]` | 1 failed / 5 passed before repair, all six pass after adding the missing role |

| Force the migrated legacy ARGB alpha to 255 | `test_legacy_argb_conversion_preserves_all_four_channels` | 3 failed, exit 1; restored green |

The final targeted run above is after restoration, the missing-role repair and
the QSS typography/serialized-color repairs described below.
Real-Qt mutation/geometry proof is NOT_RUN. The six per-scope controls were added
while the already-collected full suite was running; that full run does not
include those six additional cases. The three ARGB controls were added after
the full run. The final targeted run includes all nine additional cases.

## Full-suite receipt

Measured full-run result: **6947 passed, 17 failed, 341 skipped**, 84 warnings,
200.88s, exit 1. Raw output remains at
`harness/panel_pd/.tmp_sweep_a/full.txt` (UTF-16 PowerShell capture). The full
suite was run **once**. Repairs afterward were verified with the final targeted
command above; there is no fabricated post-repair full-suite count.

| Run | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Published `harness/panel_pd/BASELINE.md` | 6941 | 1 | 192 |
| Inherited `docs/panel_pd/REPORT_LEVER.md` | 6945 | 11 | 311 |
| SWEEP_A measured full run | 6947 | 17 | 341 |
| Delta vs published baseline | +6 | +16 | +149 |
| Delta vs inherited LEVER | +2 | +6 | +30 |

The raw pass floor is met, but the suite is **not green**. Eleven failure
identities match REPORT_LEVER. Six additional failures appeared in this run:

- `test_panel_typography.py::test_qss_stylesheet_source_has_no_literal_typography`:
  moving legacy sheets initially moved literal font sizes/weights into the
  authority. FIXED within SWEEP_A: derive unchanged values from existing size
  and weight tokens (18px = UI * 3/2, 14px = UI * 7/6, 9pt = UI * 3/4,
  10px/pt = LABEL, bold = SEMIBOLD + MEDIUM - REGULAR). No token added.
- `test_rope_prominence_visible.py::test_no_rule_introduces_a_hex_absent_from_tokens`:
  inherited token-plus-suffix expressions emitted unsanctioned eight-digit
  hex strings. FIXED within SWEEP_A: `_sweep_a_legacy_argb` expresses identical
  channels via the existing `tokens.rgba` helper and integer alpha. Qt's
  eight-digit parser uses ARGB; the migration deliberately preserves that
  existing interpretation instead of silently recoloring the old suffix
  idiom. The packed-word control checks all four channels. References:
  [QColor parsing](https://doc.qt.io/qt-6/qcolor.html#fromString) and
  [QSS color forms](https://doc.qt.io/qt-6/stylesheet-reference.html#list-of-property-types).
  Actual rendered equality is still NOT_RUN.
- Four `test_chat_panel.py::TestCSSConsolidation` tests remain **FAIL**:
  `test_no_inline_css_in_chat_panel_root` (assertion line 1048),
  `test_no_inline_css_in_build_input_area` (1065),
  `test_no_inline_css_in_connection_bar` (1073), and
  `test_no_inline_css_in_mode_toolbar` (1082). Each requires a specific
  `get_*_stylesheet()` legacy call in method source. This contradicts this
  leg's required removal of those per-widget sheet applications. The new
  tests verify the actual role/QSS seam, but do not replace or weaken those
  tests. They are outside SWEEP_A's write set. No dummy call, comment string,
  skip or assertion edit was added to manufacture a pass. Orchestrator needs
  to migrate those four assertions with ownership authorization.

All full-run failure identities (verbatim):

```text
FAILED tests/test_backfill.py::test_backup_is_taken_and_source_intact - Asser...
FAILED tests/test_chat_panel.py::TestCSSConsolidation::test_no_inline_css_in_chat_panel_root
FAILED tests/test_chat_panel.py::TestCSSConsolidation::test_no_inline_css_in_build_input_area
FAILED tests/test_chat_panel.py::TestCSSConsolidation::test_no_inline_css_in_connection_bar
FAILED tests/test_chat_panel.py::TestCSSConsolidation::test_no_inline_css_in_mode_toolbar
FAILED tests/test_m2_path_policy.py::test_compose_parms_keep_tokens - Attribu...
FAILED tests/test_orchestrate_close_gate.py::test_receipt_uncommitted_holds_at_closing
FAILED tests/test_orchestrate_close_gate.py::test_receipt_not_head_holds_at_closing
FAILED tests/test_orchestrate_close_gate.py::test_receipt_head_but_no_release_holds_at_closing
FAILED tests/test_orchestrate_close_gate.py::test_clean_leg_passes_end_to_end_in_dry_run
FAILED tests/test_orchestrate_close_gate.py::test_operator_harvested_main_tree_receipt_is_done
FAILED tests/test_orchestrate_close_gate.py::test_manifest_pinned_done_bypasses_gate
FAILED tests/test_orchestrate_liveness.py::test_subagent_workflow_write_moves_last_write
FAILED tests/test_orchestrate_liveness.py::test_fresh_subagent_beats_stale_main_transcript
FAILED tests/test_panel_typography.py::test_qss_stylesheet_source_has_no_literal_typography
FAILED tests/test_rope_prominence_visible.py::test_no_rule_introduces_a_hex_absent_from_tokens
FAILED tests/test_write_plane_health.py::test_probe_bounded_on_real_acl_denied_dir
```

The two repaired QSS failures pass in the final 87-pass targeted run. The
remaining four source-test conflicts and eleven inherited full-run failures
are not reclassified as success. Their environment/root causes, beyond the
specific source-test conflict above, are not established by this leg.


## Delivery and receipt

Normal staging/commit attempts at each milestone returned:

```text
fatal: Unable to create 'C:/Users/User/SYNAPSE/.git/worktrees/pd-panel-sweep_a/index.lock': Permission denied
```

This is a filesystem denial, not an automatic approval-review rejection. No
ACL changes, alternate index, branch changes, merge, push, release, GUI action,
or permission bypass was attempted. Authorized subjects use `pd(sweep_a):`
and the required trailer `Co-Authored-By: Codex (gpt-6-astra) <noreply@openai.com>`.
The orchestrator must not treat the uncommitted working tree as completed delivery.

Touched deliverables: six modules above; append-only designsystem/qss.py;
`tests/test_panel_sweep_a.py`; `harness/panel_pd/RESIDUAL.json`;
`harness/panel_pd/STATUS_SWEEP_A.md`; this REPORT. Disposable `.tmp_sweep_a`
outputs are not source deliverables and must not be staged.

Receipt: `leg=panel_pd:SWEEP_A:BUILD`; `verdict=BLOCKED`; touched/commands/artifacts
and mutation evidence above; `could_not_verify=[real Qt layout/font/paint,
380px docking, before/after PNG equivalence, independent CRUX, Joe H22.0.400
GUI sign-off, precise PID ownership, causes of inherited suite failures, full-suite green, Git commit delivery]`; `needs_human=[]`
for gated repository acts (none requested).
