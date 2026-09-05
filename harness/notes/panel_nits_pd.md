# Panel PD - nits, exemptions and deferred items (landing r3, 2026-09-05)

One file, one owner. Every entry names the doc it defers to and the day it was
written. Nothing here is a waiver unless the word appears.

## Exemptions (CTO, 2026-09-05, verbatim)

**DOCKING EXEMPTION - unshipped alternate entry.** quick_actions.QuickActionPills
and chat_panel.SynapseChatPanel are the legacy Chat/HDA alternate entry. No
.pypanel under houdini/python_panels builds them (synapse_panel.pypanel:45 builds
synapse.panel.synapse_panel only) and synapse.panel.synapse_panel does not import
chat_panel or quick_actions; tests/test_panel_alt_entry_unshipped.py pins that
premise and returns both regions to the docking list the day it fails. Their
width drivers (five full-label pills in one row; a connection frame showing the
raw ws:// URL, HALT and a 100px Connect) are scheduled for the single-panel
collapse and the voice rules (SYNAPSE_PANEL_REDESIGN.md section 2 decision 1,
section 3 Voice: hide raw ws:// URLs, HALT -> Stop). This is not a PD docking
accept for those widgets; it is a statement that no artist can dock them.

**HDA PARITY EXEMPTION.** The parity target for hda_views.py is the legacy
styles.py rule set at ce04dcb0 (QTableWidget#ParamTable bg CARBON / fg SILVER /
GRAPHITE borders; QPushButton#HdaGenerateBtn bg SIGNAL / fg VOID; HdaActionBtn
hairline), not the un-sheeted offscreen render in
design/rhythm_pd/before/hda_result.png - that PNG shows the absence of any sheet
in the legacy host, which SWEEP_B's ensure_sweep_b_view (qss.py) repairs.
SWEEP_B's DsHda rules re-express the ce04dcb0 design in existing designsystem
tokens (no new hex, no new family - CRUX verified). "Beyond gap/label/tag" is
accepted for hda_views.py DescribeView/BuildingView/ResultView only, on this
evidence. Copy shortening (Inspect / Parameters / Save HDA) is accepted because
the full verbs remain as tooltip and accessible name (hda_views.py). Open GUI
item: single-accent-per-view on ResultView; revert is hda_views.py
DsHdaGenerate -> DsHdaAction.

## Open word (not a waiver, not fixed by the forge)

- **Composed panel at AIRY: 393 > 380** (2026-09-05). Driver: the verb rail - five
  verbs (237px) + four `group` gaps at 24 + the 30px gutter both sides. Master's
  own geometry (`setSpacing(24)` + GUTTER = 393); fits at standard (361) and
  tight (345). The ratified T2 verb-rail rhythm and RULING-3's gutter conflict
  with the interim 380 bound at airy. Options for the word: (a) accept the
  design's own number and write the YAML interim feature per density; (b) a
  tighter verb-rail role (departs from battleplan T2); (c) GUTTER 26 (still
  385). Producer: `python313 -m pytest tests/test_panel_rhythm_docking.py`
  -> test_every_composed_region_and_face_at_docking_bound[airy].
- **Verb rail at PANEL_PREF_WIDTH 340** (2026-09-05). panel_shot.py renders at
  the preferred width 340; at standard the verb rail needs 361 (237 + 4x16 +
  60), so OPTIMIZE / BUILD HDA elide in design/rhythm_pd/after_r3/expert/
  panel_direct_chat.png (and airy at 393). The 'before' set shows the same
  rail clipped worse (master's 24px gaps + a visible Stop + a clipped strip).
  Same root as the item above: the verb rail's five verbs and the gutter
  against a 340-380 pane. One word settles both.
- **280 contract follow-ups** (RULING-2A: regions that fit 380 but not 280 carry
  a dated follow-up, not an exemption). The verb rail needs 345 at tight, the
  header row 334; the face at 393/361/345. Dated 2026-09-05; owner: the
  single-panel collapse leg.

## Deferred with a dated pointer (2026-09-05)

- Rename rhythm role `label` -> `eyebrow` when tokens.py next opens under a
  ratified change (CAMERA freezes tokens.py vs ce04dcb0; the doctrine line in
  docs/PANEL_RHYTHM_SPEC.md section 4 and the no-double-applier pin in
  tests/test_panel_camera_rhythm.py carry the design until then).
- docs/design/SYNAPSE_PANEL_REDESIGN.md section 3 still names SIGNAL as #00D4FF
  vs tokens.py #8FB3D9 - doc drift, the known 3-source gremlin; fix in its own
  commit with the full suite green, never inside this landing.
- A census 'reachable-from-shipped-panel' column (nice to have; RULING-1 made
  it unnecessary for this wave by migrating or deleting every side-module site;
  tests/test_panel_alt_entry_unshipped.py::reachable_panel_modules is the
  producer if it is ever wanted).
- The manifests list `stop` as present in the rail with `visible: True`; the
  compositor honours it and `_regate_stop()` re-asserts the runtime gate after
  compose. A cleaner long-term shape is a manifest spec that distinguishes
  presence from runtime state; that is a compositor (L5) change and waits for
  its own leg.
- FaceReview / RecallCard DsVerbs keep their L5 type (LABEL_SM / default); the
  one-applier parity pin covers the panel's own verbs and rail controls. If Joe
  wants every DsVerb byte-identical, it is one setFont per site.

## Pre-existing reds carried as the known floor (not this wave's)

- tests/panel/test_failure_trail.py::test_dead_verb_hidden (master baseline).
- tests/test_backfill.py::test_backup_is_taken_and_source_intact (master
  baseline per harness/notes/h22/pytest_v5630_master.txt).
- G3 WARN 'interactive targets: 3 under 26px' (master baseline; GUI-gate item 8).
