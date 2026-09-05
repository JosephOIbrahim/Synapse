# Panel PD wave -- Integration report

Orchestrator: Claude (Fable 5.1), 2026-09-04 22:40. Branch `pd/panel-integrate` = `pd/panel-lever` + camera + sweep_a + sweep_b, then the QSS splice repair, then CRUX round 2. Head c9429bdd. Nothing pushed; merge to master is Joe's word and **CRUX says no merge**.

## Wave result

| Leg | Commit | CRUX round-2 verdict | chain_broken_at |
|---|---|---|---|
| CENSUS | a5b975c1 | SOUND | -- |
| LEVER | 7b17c0c3 | BROKEN | global residual guard lets an exact removed owner return below the 226 cap |
| CAMERA | da5aac31 | BROKEN | strict raw-zero not met: 2 spacing / 1 sheet in recall_card.py + synapse_panel.py |
| SWEEP_A | ed41ce61 | BROKEN | raw census 12 / 0 / 0 (all tagged); four obsolete chat CSS pins; whole-tail append pin |
| SWEEP_B | ae046513 | BROKEN | HDA Result visual parity beyond gap/label/tag; four sequence probes stop at layout spacing |
| CRUX | 20094e1b | delivered (round 1 verdict captured verbatim, round 2 written by the referee) | -- |

Every worker was committed on its behalf (the Codex sandbox cannot write the worktree index; writable_roots did not help, ACL deny entries).

## The one defect that was the orchestrator's

Merge 0998cc9e resolved the qss.py conflict by keeping A-then-B per hunk; the second hunk had split `sweep_a_style`, so SWEEP_B's block was spliced mid-function and the unpolish/polish/update calls vanished. That was the real cause of the three state-colour failures. Repaired at 38cd9b46 (LEVER prefix + complete SWEEP_A tail + complete SWEEP_B tail, both tails hash-equal to the leg commits per CRUX). Post-repair Qt receipt `harness/panel_pd/runs/2026-09-04/qt_INTEGRATE_post_repair.txt` (Houdini 22.0.400 python313 + PySide6 6.8.3, module bound to this tree): **243 passed, 22 failed**; all three state-colour cases green.

## Suite counts

| Run | passed | failed | skipped |
|---|---:|---:|---:|
| base 6e3dd963 (orchestrator shell) | 6941 | 1 | 192 |
| integrate c5c086cb (orchestrator shell, Python 3.14, no Qt) | 7069 | 8 | 318 |
| CRUX fresh archive (sandbox, Python 3.14) | 7014 | 30 | 351 |

The 8 in the orchestrator shell: 1 pre-existing (test_backfill), 4 obsolete chat-panel CSS-consolidation pins, 3 isolated-green sweep pins. CRUX's extra 22 are archive/sandbox environment classes it names (no git metadata in the archive, orchestration, ACL probe, aging gate) and are not substituted for the shell run.

## Qt tier on the repaired tree (22 reds)

- **15 docking widths**, inherited and unchanged: composed panel 433, QuickActionPills 587-602, HDA ResultView 382-388, HealthStrip 708, SynapseChatPanel 502-514, all vs the 380 px bound, all three densities. Identical widths on the pre-LEVER tree, so the debt predates the wave, but the strict accept is still unmet.
- **4 SWEEP_B sequence probes** stop at layout spacing before geometry; CRUX says the probe conflates control-internal layouts with owned ones. Probe needs splitting by real owner.
- **3 isolated-green test pins** (block order, block prefix, sibling-file freeze) that contradict the append-only contract. CRUX: fix the pins at their real seams, do not delete or weaken.

## CRUX rulings that need Joe (crux.json `for_ruling`)

1. **Residual.** 62 sites remain (18 spacing, 2 sheets, 42 hex), 47 untagged, against the plan's "at most 20, all tagged"; the guard cap sits at 226 with 164 sites of slack and a seed that lets a removed owner come back. Assign the remaining colour/rhythm owners (health_strip, integrity_readout, agent_health, render_preflight are the named unowned files) or waive the 20-site target explicitly.
2. **Docking scope + HDA parity.** The fifteen widths and SWEEP_B's HDA Result surface/button change (white table + native buttons became dark surfaces + a filled SIGNAL action, also serving Describe/Building) need a decision: fix, or waive with a written parity exemption. No GUI approval is requested by the receipt; your eyes on .400 remain the red gate.

## Blocking nits before any merge word (CRUX R2-01..07)

R2-01 residual/guard seed (LEVER + integrator) · R2-02 move the four chat CSS oracles to the QSS seam (SWEEP_A) · R2-03 fence-scope the three pins (sweep test owners) · R2-04 the fifteen widths (CAMERA/SWEEP_A/SWEEP_B/unassigned health_strip) · R2-05 split the SWEEP_B probes by owned layout · R2-06 HDA parity · R2-07 CLOSED by the post-repair Qt receipt above. Non-blocking: R2-08 archive git-history loop is vacuous (verification gap), R2-09 inherited doubled-brace rule, R2-10 receipt provenance wording.

## What the wave did deliver

One owner of rhythm: `designsystem/rhythm.py` + role rules in `designsystem/qss.py` + a compositor hook (5 lines added / 1 removed), spec v2, guard + docking tests, the census CLI + region map, five camera regions on roles, the recall card, 18 modules migrated, 104 hex sites mapped to existing tokens (no new tokens, no new fonts, no Cohere branding, verified by CRUX), before/after screenshot sets (now un-gitignored under design/rhythm_pd), and receipts for everything. Panel-wide imperative spacing went 107 -> 18, inline sheets 106 -> 2, raw hex 135 -> 42.

## Next actions

1. Joe rules on the two `for_ruling` items.
2. A follow-up leg (or legs) for R2-01..06 on top of `pd/panel-integrate`, then CRUX round 3.
3. Joe's GUI sign-off on H22.0.400: profile tab strip, header/ribbon, chat transcript, verb rail, recall card, TOKEN face, in three profiles.
4. Merge word.

## Landing r3 - CTO rulings 2026-09-05

Branch `pd/panel-integrate-r3` (master e8913f83 merged first, tree 99079e48; then
one commit per landing step, `pd(r3): <step>`). Forge: Claude (FORGE), session
`01UocCW68SG5wixf9s9aZ1Bv`. The Houdini GUI was not available (bridge down);
everything only Joe's eyes can judge is listed under GUI-GATE below, never claimed.

### Standard verdict (CTO, verbatim)

DOES-NOT-MEET on pd/panel-integrate (aca05ccb) as it stands; LANDABLE on
pd/panel-integrate-r3 after the nine forge steps, with two written waivers and one
GUI gate. The reach claim is real (census 107/106/135 -> 18/2/42, camera path 0
untagged, one accent, no new family, G3 WCAG/type-floor/chrome-frozen green). The
Pentagram bar fails on evidence the wave never reported: (1) the 30px GUTTER token
has zero consumers on the branch while master consumes it - CAMERA's own diff
deleted them to reach raw-zero, which is the census being gamed, not a design; (2)
parm_row is used as a 4px utility on 30 of 52 hook sites that are not parameter
rows, so the 'roles, not sizes' principle is inverted; (3) the profile pills carry
`row` (min-h 44, hairline box) and render as 116x70 blocks - section 4 puts pills
under `tag`, and the stretch that right-aligned them was dropped; (4) verbs and
header controls take two type appliers and no longer match their CHAT/TOKEN
siblings; (5) tokens.py TYPE_ROLES['label'] (sans, BP4 ratified) and rhythm.py
'label' (mono/upper/tracked, battleplan section 4 ratified) run on the same
widgets. Every one of these is a cheap code fix inside designsystem/ plus a role
reassignment; none needs Joe's word before landing, because in each case the
ratified doc already says what the design is and the wave departed from it.

### RULING-1 RESIDUAL - OWN-NOW, no cap waiver

The plan's Done ('panel-wide residual <= 20 tagged sites, guarded') is met inside
this forge, not re-dated. (a) The two dead HTML producers are deleted:
agent_health.format_agent_health_html (14 hex sites) and
render_preflight.format_preflight_html + _STATUS_ICONS (6 sites, incl. the retired
cyan). (b) health_strip.py takes rhythm_role='group' (gap SPACE_GRID[3]=16 /
margins 0 reproduces today's values exactly at standard); the per-label sheet is
one '#health_strip QLabel' rule inside the SWEEP_B fence in qss.py. (c)
integrity_readout.py:81-82 -> '# rhythm-exempt: 1px hairline stack between claim
rows; no role expresses 1px'. (d) The remaining side-module hex sites migrate by
the SWEEP_B mapping-table method: comment hits reworded, colour strings mapped to
existing tokens with rows appended to docs/panel_pd/HEX_MAPPING_SWEEP_B.md and
each module added to tests/test_panel_sweep_b_hex.py MIGRATED. (e) Guard re-seed:
a fresh census of the landing tree at
harness/panel_pd/runs/2026-09-05/rhythm_census.json; RESIDUAL.json points at it,
seed_counts = its totals, allowed_residual == measured residual (exact, asserted
==, not <=), allowed_grid_residual = 0; the git-history test fails loud on an
empty log.

Rationale: waive-with-cap keeps 164 sites of slack and a seed that resurrects
removed owners (CRUX proved it with WorkingIndicator's setStyleSheet). Two of the
four named unowned modules are dead code; one is a one-line role; one is an honest
1px tag. A target the forge can hit in a morning is not a thing to waive.

**Landed:** census 18 / 2 / 42 (aca05ccb) -> 16 / 1 / 0. 17 sites, 17 tagged, 0
untagged, 0 hex, 0 grid. Cap == 17 == measured. Mapping rows appended: 48 (every
three- and six-digit hex in the nine side modules at ce04dcb0, comments included;
the table's own precedents kept per hex, so the same colour never maps two ways).
Mutation (restore `self._dot.setStyleSheet(sheet)` in working_indicator._apply):
the ratchet fails 'new untagged rhythm owners: [working_indicator.py ...]' - it
stayed green under the old seed.

### RULING-2A DOCKING CONTRACT + MEASUREMENT

The docking width contract is tokens.PANEL_MIN_WIDTH = 280 (what synapse_panel.py
promises the host). The PD wave's 380px is an interim bound written into
.synapse/contracts/docking-minimums.yaml as a feature; the docking test reads it
from the YAML like it reads the heights, never a literal. No width is signed until
the measurement is valid: the worker loads the bundled fonts after QApplication,
exits 78 -> pytest.fail (never skip) on an empty font database, prints runner +
family + families count into every PD_QT line; -I is passed only to a non-hython
runner so the Houdini interpreter can run the worker.

**Landed:** PD_QT provenance under python313: families 2, family 'Space Grotesk';
under hython the worker starts (no 'encodings' error). ResultView measured 388
wide with NO font and 260 with the design's fonts - the wave's fifteen reds were
measured with an empty font database.

### RULING-2B DOCKING DISPOSITIONS

FIX: HealthStrip cells take QSizePolicy(Ignored, Preferred) horizontally (full
text already in the tooltip) and the strip takes rhythm_role='group'.
RE-MEASURE: hda_views.ResultView fits 380 at every density under the valid font
DB - no source change. WAIVE with a reachability pin: quick_actions.QuickActionPills
and chat_panel.SynapseChatPanel leave ALTERNATE_REGIONS under the exemption below;
tests/test_panel_alt_entry_unshipped.py pins the premise and the docking test
returns them to the list the day it fails. Mutation (`from synapse.panel import
chat_panel` in synapse_panel.py): the pin fails on two counts; reverted, green.

**Two further drivers the valid measurement exposed, both fixed at their seam:**

1. The rail's header row (twelve chrome items, five of them zero-width Ignored
   labels) inherited the shell's 16/24 gap and paid it twelve times: 446/494/590
   wide. It is a toolbar, so it now owns its own `stack` role (gap 4/6/3) inside
   the shell rail - RULING-4a's own list names the header rail among the stack
   sites.
2. The compositor applied the manifests' `visible: True` to the state-gated Stop
   and un-hid a DISABLED Stop at rest after every compose - a pre-existing master
   defect: tests/test_panel_faces.py::test_stop_gated_to_working_state was red
   under hython. `_regate_stop()` re-asserts the runtime gate after compose
   (`_build_ui` and `_recompose`); presence in a profile and runtime state are two
   different things. That test is green now, and 64px + a gap left the header row.

**The one docking red that stands, honestly:** the composed panel at AIRY only
measures 393 > 380. Driver: the verb rail - five verbs (237px) + four `group`
gaps at 24 + the 30px gutter both sides. That is master's own geometry
(`setSpacing(24)` + GUTTER = 393 at its single density) surfaced by a valid
measurement; it fits at standard (361) and tight (345). The ratified T2 verb-rail
rhythm (`group`, x1.5 at airy) and RULING-3's gutter conflict with the interim
bound at airy. Not weakened, not waived by the forge - it needs a word:
(a) accept the design's own number and write the interim feature per density;
(b) a tighter verb-rail role (departs from T2); (c) a narrower GUTTER (the token
says 26-36 is safe; 26 still gives 385). None fits 280 at any density (345 min) -
the 280 contract for the verb rail is a dated follow-up either way.

### RULING-2C HDA PARITY - KEEP with the written exemption

SWEEP_B's DsHda rules and ensure_sweep_b_view stay. The parity target for
hda_views.py is the legacy rule set at ce04dcb0 styles.py, not the un-sheeted
offscreen render in design/rhythm_pd/before/hda_result.png. Copy shortening
(Inspect / Parameters / Save HDA) is accepted because the full verbs remain as
tooltip and accessible name. GUI-gate item: whether the SIGNAL fill on
ResultView's 'Create Another HDA' is the view's single accent; one-line revert is
hda_views.py DsHdaGenerate -> DsHdaAction.

### RULING-3 GUTTER (STD-01) - restored, not re-opened

A new `shell` role in designsystem/rhythm.py: ROLE_GAPS['shell'] = SPACE_GRID[3],
_MARGINS['shell'] = (GUTTER, SPACE_SM, GUTTER, SPACE_SM), applied to the four edge
containers (rail, context ribbon, tab row, direct face). The root stack takes a
`band` role (gap 0, margins 0: chrome bands own their hairlines via
DsHeader/DsTabRow rules) so the B4 composer cap holds; act + divider + input sit in
one band. If Joe wants the gutter narrower or zero, that is a one-token change to
tokens.py with his word.

**Landed:** `hython audit_panel.py --strict` -> 'input not clipped: send bottom
410px / panel 420px [ok]' (was 444 FAIL on the merged tree); G3 pass, 1 WARN
(master's 3-targets baseline). tests/panel/test_docking.py::
test_send_never_clips_below_the_pane_at_min_height green under hython.

### RULING-4 ROLES AND THE LABEL DOCTRINE (STD-02/03/04/05/07)

(a) New `stack` role (gap 4, no margins, no QSS, no type); the 22 non-grid
parm_row sites moved to it; parm_row stays on face_token's real label/value grid.
(b) Profile pills take `tag`, not `row`; the DsTabRow got its addStretch(1) back
before the pills (right-aligned: profile is chrome). (c) One type applier per
widget: verbs and the rail controls drop rhythm_role='label' and take the LABEL
tracked font (mono) so they match CHAT/TOKEN byte-for-byte; the context label
keeps c.label(role='label') (sans, BP4) only; the recall header and the TOKEN
section heads keep rhythm_role='label' and drop c.label's role='label'.
(d) Doctrine, in PANEL_RHYTHM_SPEC.md section 4: `rhythm_role="label"` is the
section eyebrow (mono, upper, tracked); `TYPE_ROLES['label']` is UI label text
(sans, BP4). Different things, never both on one widget; a stock test pins that no
source line pair applies both. (e) The dead 0.72x / 0.68x ratios are gone from
qss.py and the spec; tracking stays numerically as is with a comment naming the
section-4 values behind the borrowed SEND / DATA*2 entries; tokens.py untouched.

**Landed and pinned (tests/test_panel_camera_rhythm_qt.py, real Qt, both
runners):** four shell insets == (30, 8, 30, 8); root band spacing 0 / inset 0;
act band gap 0; CHAT, TOKEN, every act-bar verb and every rail control share
QFontInfo pixelSize + letterSpacing; tag pills sit at the CHAT pill's height;
context label family == sans, recall eyebrow family == mono; the header row is a
stack; Stop hidden at rest. Stock pins: no widget takes both label appliers, shell
consumes GUTTER, no role_size in qss.py, no stray parm_row. Scope note: FaceReview
and RecallCard verbs keep their own ratified L5 type; the ruling names the panel's
two sites (verbs at _verb, rail controls).

### Waivers (verbatim, dated 2026-09-05, CTO)

DOCKING EXEMPTION - unshipped alternate entry (also in
tests/test_panel_rhythm_docking.py DOCKING_EXEMPT_UNSHIPPED):
'quick_actions.QuickActionPills and chat_panel.SynapseChatPanel are the legacy
Chat/HDA alternate entry. No .pypanel under houdini/python_panels builds them
(synapse_panel.pypanel:45 builds synapse.panel.synapse_panel only) and
synapse.panel.synapse_panel does not import chat_panel or quick_actions;
tests/test_panel_alt_entry_unshipped.py pins that premise and returns both regions
to the docking list the day it fails. Their width drivers (five full-label pills
in one row; a connection frame showing the raw ws:// URL, HALT and a 100px
Connect) are scheduled for the single-panel collapse and the voice rules
(SYNAPSE_PANEL_REDESIGN.md section 2 decision 1, section 3 Voice: hide raw ws://
URLs, HALT -> Stop). This is not a PD docking accept for those widgets; it is a
statement that no artist can dock them. Dated 2026-09-05, CTO.'

HDA PARITY EXEMPTION (also in harness/notes/panel_nits_pd.md): 'The parity
target for hda_views.py is the legacy styles.py rule set at ce04dcb0
(QTableWidget#ParamTable bg CARBON / fg SILVER / GRAPHITE borders;
QPushButton#HdaGenerateBtn bg SIGNAL / fg VOID; HdaActionBtn hairline), not the
un-sheeted offscreen render in design/rhythm_pd/before/hda_result.png - that PNG
shows the absence of any sheet in the legacy host, which SWEEP_B's
ensure_sweep_b_view repairs. SWEEP_B's DsHda rules re-express the ce04dcb0 design
in existing designsystem tokens (no new hex, no new family - CRUX verified).
"Beyond gap/label/tag" is accepted for hda_views.py DescribeView/BuildingView/
ResultView only, on this evidence. Copy shortening (Inspect / Parameters / Save
HDA) is accepted because the full verbs remain as tooltip and accessible name.
Open GUI item: single-accent-per-view on ResultView; revert is hda_views.py
DsHdaGenerate -> DsHdaAction. Dated 2026-09-05, CTO.'

NOT WAIVED, for the record: the residual cap (owned to 17, cap == measured), the
gutter (restored via the shell role), the 380px width for shipped regions (fixed
or re-measured, YAML-sourced; the airy verb-rail case is recorded above as an open
word, not a waiver), the nine wave-caused Qt reds (fixed at their seams, no oracle
weakened), the pre-existing tests/panel dead-verb red and tests/test_backfill red
(master baseline), the G3 '3 targets under 26px' WARN (master baseline, GUI-gate
item 8).

### Roles added (designsystem/rhythm.py)

| role | gap (airy / standard / tight) | fixed margins | where |
|---|---|---|---|
| shell | 24 / 16 / 12 | (GUTTER, SPACE_SM, GUTTER, SPACE_SM) = (30, 8, 30, 8) | rail, context ribbon, tab row, direct face |
| stack | 6 / 4 / 3 | (0, 0, 0, 0) | the header row, toolbars, input rows, card interiors (former parm_row utility sites) |
| band | 0 / 0 / 0 | (0, 0, 0, 0) | the panel root; act + divider + input |

### Census, before and after

| tree | spacing | inline sheets | raw hex | grid | tagged | untagged |
|---|---|---|---|---|---|---|
| pre-wave (2026-09-04 seed) | 107 | 106 | 135 | 4 | - | - |
| pd/panel-integrate aca05ccb | 18 | 2 | 42 | 0 | 15 | 47 |
| pd/panel-integrate-r3 (landing) | 16 | 1 | 0 | 0 | 17 | 0 |

Producer: `python harness/notes/panel_rhythm_census.py --panel-dir
python/synapse/panel --json harness/panel_pd/runs/2026-09-05/rhythm_census.json`.

### Test oracles moved to the wave's seams (no oracle weakened)

- tests/test_chat_panel.py TestCSSConsolidation: builder selects
  qss.sweep_a_style(<widget>, "<key>"), the sheet carries the declaration inside
  the scoped rule, no setStyleSheet( in the builder.
- tests/panel/test_gate_fidelity_unknown.py: the dot's sweep_a_color property.
- tests/panel/test_font_scale.py + audit_panel.py: the composer document's
  defaultFont().pixelSize().
- test_panel_camera_rhythm.py: synapse_panel.py lifecycle vs the master merge-base
  (B4); the rest at ce04dcb0. test_panel_sweep_b_hex.py: SWEEP_B's own-diff check
  for the CAMERA files. test_panel_sweep_a.py / test_panel_sweep_b_widgets.py:
  fence-scoped to their own marked blocks; the LEVER role block
  (_rhythm_stylesheet) is the one upstream region the landing edits (RULING-4e),
  everything else before the first sweep marker stays byte-identical to ce04dcb0.
- test_panel_sweep_b_widgets.py sequence probes: owned layouts walked by widget
  (Qt-internal sub-layouts excluded), an unmarked probe layout as the negative
  control, bundled fonts loaded, popup-window minimums reported not counted
  against the docked-child rule.

### Receipts (harness/panel_pd/runs/2026-09-05/)

qt_R3.txt (hython tests/panel), docking_R3.txt (python313 docking, PD_QT
provenance), g3_R3.txt (audit_panel --strict), fullsuite_R3.txt (stock full
suite), crux_r3.json (round 3), rhythm_census.json / .md; design/rhythm_pd/after_r3/
PNG sets per profile with manifest.json.

## Repair round - CRUX round 3 must-fix (2026-09-05)

CRUX round 3 ruled the landing tree BROKEN on five items. Four are fixed at
their seams on this branch; the fifth is the open word, now a one-figure edit.
Every fix carries a test shown red before the source change.

1. **Settings-path pin read the live override** -
   tests/test_panel_settings.py::test_settings_path_is_repo_dot_synapse went
   red under the gate's own ENV line (SYNAPSE_PANEL_SETTINGS=<scratch>). Fixed:
   monkeypatch.delenv before the call; sibling test pins that the override IS
   honoured and that a blank one falls back. Red 1 failed -> 9 passed.
2. **Camera lifecycle pins compared the tree to itself** -
   _panel_base() ran `git merge-base master HEAD`, which is HEAD the day this
   lands (vacuous; errors without a local master ref). Fixed: literal
   _PANEL_BASE = "e8913f83". Non-vacuity shown by mutation: a line added to
   _on_done -> 1 failed, 13 passed; reverted.
3. **Gate widget type regression (F-C1)** - d26d2703 purged the QSS families
   on the claim "families travel by QFont", but GateWidget applied none: every
   gate element rendered in the app font (Courier offscreen) where master
   rendered Space Mono. Fixed: fontload.apply_family(mono=True) at the nine
   elements master rendered mono (badge, operation, countdown, Reject,
   Approve; header, fidelity label, counts, violations); agent / description /
   critical carried no family on master and stay on the host face.
   tests/panel/test_gate_widget_type.py (hython) pins gate_badge and the other
   eight in the composed panel across a state transition: 3 failed -> 3 passed.
   The unshipped SWEEP_A widgets (chat_panel, context_bar, quick_actions,
   hda_views; none reachable from synapse.panel.synapse_panel) render in the
   QApplication font until wired, and take a family by QFont at that seam -
   stated in qss.py's SWEEP_A header.
4. **WORK and REVIEW faces flush at x=0** - SWEEP_A gave both faces role
   'group' (no _MARGINS entry -> 0,0,0,0) where master had a 26px inset.
   Fixed: rhythm_role="shell" on the FaceWork / FaceReview column owner (the
   RULING-3 mechanism; census unchanged at 17/17/0). The Qt pin covers both
   faces at (GUTTER, SPACE_SM, GUTTER, SPACE_SM) at every density: 3 failed ->
   3 passed. Both faces fit the docking bound with the inset at every density
   (python313 docking, face_work / face_review 6/6 green).
5. **R3-01, the composed AIRY panel at 393 > 380** - the open word. The forge's
   part: (a) the brand never elides - synapse_panel.py gives the wordmark a
   hard minimum from its own hint (Qt takes width from the biggest items
   first below a layout's minimum; the wordmark was the biggest and drew as
   'SYNAPS' at PANEL_PREF_WIDTH under airy; the Ignored chrome labels give way
   instead). Pin: wordmark.width() >= sizeHint at 340 in every density, red
   (0, 69) -> green (69/69). (b) the docking width contract now carries one
   figure per density (.synapse/contracts/docking-minimums.yaml; _bounds
   (density) in the test), every density still at the ratified 380, so the
   word is one figure in one YAML line: option (a) accept 393 at airy; (b) a
   tighter verb-rail role at airy vs battleplan T2; (c) GUTTER 26 (still 385).
   Until it lands test_every_composed_region_and_face_at_docking_bound[airy]
   stays red on purpose under both runners - protect green, never move the
   bar by hand. Its visible face at 340/airy after the wordmark fix: the verbs
   elide (design/rhythm_pd/after_r3/curious/panel_direct_chat.png).

Receipts on tree a196b555 (harness/panel_pd/runs/2026-09-05/*_R3rep.txt):
qt_R3rep.txt hython tests/panel 1 failed (test_dead_verb_hidden, master
baseline) / 120 passed; docking_R3rep.txt python313 1 failed (airy composed)
/ 90 passed, PD_QT family Space Grotesk; docking_hython_R3rep.txt hython
composed/alternate 1 failed (same) / 44 passed, 0 encodings errors;
g3_R3rep.txt pass, 1 WARN (3 targets under 26px, master baseline);
stock_R3rep.txt 332 passed / 54 skipped; sweepb_R3rep.txt python313 18
passed; targeted_R3rep.txt hython 24 passed; mutations_R3rep.txt both red
and reverted; census 17 residual / 17 tagged / 0 grid, cap == measured;
design/rhythm_pd/after_r3/{curious,expert,ml} regenerated 16/16 each. The
full suite was not re-run this round (assignment: acceptance commands and
targeted files only); fullsuite_R3.txt on cd98b5c6 is the last full receipt.
