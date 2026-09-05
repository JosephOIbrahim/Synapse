# Panel region map - PD-CENSUS, 2026-09-04

VERIFIED-STATIC against product sources at `6e3dd963`, carried by branch base
`5e29bf9e`. Producer: `harness/notes/panel_rhythm_census.py`; site-by-site evidence:
`harness/panel_pd/runs/2026-09-04/rhythm_census.json`. Roles below are targets from
`docs/PANEL_BATTLEPLAN_PD.md` section 4, not claims that role properties exist.
All Python panel paths below are relative to `python/synapse/panel/` unless an
explicit prefix is given. A variable/attribute is a source widget id, not
necessarily a Qt objectName. `Ds*` names denote actual naming sites or a cited
component factory. Source-declared surfaces include state-gated and alternate
entry surfaces; runtime visibility and multiplicity are UNKNOWN.

## Six camera regions, in the requested review order

This is the plan's camera review order. It is not the current construction order:
`SynapsePanel._build_ui` at `synapse_panel.py:482` composes rail, ribbon, mode bar,
then faces (`compositor.py:45` names the builders).

| Camera region | Widget ids / objectNames | Spacing owners (file:line and source values) | Reach today | Target role |
|---|---|---|---|---|
| 1. Profile tab strip | `w` = `DsTabRow` (`synapse_panel.py:992`); `_face_pills.direct`, `_face_pills.token`, `_profile_pills[pid]` are `c.Pill` / `DsPill` (`designsystem/components.py:73`) | `synapse_panel.py:994` `lay` margins `(t.GUTTER,24,t.GUTTER,0)`; `:995` spacing `28` | Named, layout-owned; no direct inline sheet in builder. `DsTabRow` has density margin rules; pills inherit factory names. | `row` pills; `group` container |
| 2. Header/ribbon | Rail `w` = `DsHeader` (`synapse_panel.py:619`); `_author_lbl` = `DsAuthor`, `_meter_lbl` = `DsMeter`, `_palette_hint` = `DsKHint`, `_stop_btn` = `DsStop`, `_observe` = `DsRailMeter`; ribbon `w` inherits `DsSection` from `_section` (`:478`), `_ctx_label` is unnamed | `synapse_panel.py:622` `col` margins `(t.GUTTER,16,t.GUTTER,14)`; `:623`, `:628`, `:716` rail/top/bottom spacing `t.SPACE_SM`; `:935` ribbon margins `(t.GUTTER,t.SPACE_SM,t.SPACE_MD,t.SPACE_SM)` | Named shell, unnamed label children; 3 rail inline sheets at `:655`, `:660`, `:719`; layout-owned. Header density selector does **not** target the sibling ribbon's `DsSection`. | `group` rail/ribbon; `label` status/context; `tag` ids |
| 3. Chat transcript | `_chat` = `ChatDisplay` (`synapse_panel.py:944`) or plain browser fallback (`:946`), neither has an objectName; `_converse_stack` (`:965`); enclosing direct face `w` uses `DsSection` factory | `synapse_panel.py:1104` direct-face `col` margins `(t.GUTTER,24,t.GUTTER,24)`; `:1105` spacing `0`; document leading `_apply_leading` at `chat_display.py:401`, grouped bubble margin `_BUBBLE_MARGIN_Y` at `:69` | Named parent only; 2 inline stylesheet calls `chat_display.py:120`, `:155`; HTML and QTextDocument own inner typography/spacing, not QLayout. Type-selector density QSS reaches the browser. | `group` transcript/turn spacing; `label` turn headers |
| 4. Verb rail | `w` = shared `DsSection` factory; local `btn` instances and `_font_btn` use `_verb` (`synapse_panel.py:1787`) naming `DsVerb` at `:1792` | `synapse_panel.py:1809` rail `lay` margins `(0,t.SPACE_MD,0,t.SPACE_SM)`; `:1813` spacing `t.SPACE_LG` | Buttons named, generic group name; no direct inline sheet; layout-owned. Density changes button margins, not the rail's inter-button layout gap. | `label` verbs; `group` rail; group hairline via existing divider vocabulary |
| 5. Recall result | ABSENT: no `recall_card.py` or recall-specific card constructor; generic `c.Card` / `DsCard` exists at `designsystem/components.py:77`, naming site `:82` | No spacing owner exists. Proposed owner `recall_card.py` belongs to CAMERA under the contract. | ABSENT, not zero-clean. Existing memory health cell is not a per-query recall result. Names/styles/layout for the new card: UNKNOWN until built. | `card` three bands, footer action `label`, status `tag` |
| 6. TOKEN face | `_token_face` from `_build_token_face` (`synapse_panel.py:1053`); `FaceToken` root/body/scroll unnamed; `_field` is `TokenField` / `DsSection` (`face_token.py:107`); `_composition`, `_cache`, `_engine` tables; `key`/`val` labels unnamed | `face_token.py:324` outer margins `(0,0,0,0)`, `:325` spacing `0`; `:337` body margins `(t.GUTTER,20,t.GUTTER,20)`, `:338` spacing `18`; legend `:416` margins zero, `:417` gap `16`; grid `:447` margins zero, `:448` horizontal gap `18`, `:449` vertical gap `6` | Field named but parameter rows unnamed; 8 inline sheets, including late `set_engine` recolour at `:575`; layout-owned. Grid is label/value only. `token_readout.py:77` refreshes existing surfaces and owns no widget spacing. | `parm_row` key/value tables; `group` body/legend; `label` eyebrows/footnote |

## Real shelf, ribbon and header owner - CAMERA handoff

**The panel's real visual owner is `python/synapse/panel/synapse_panel.py`:**
`_build_rail` at line 608 builds the header, `_build_context_ribbon` at line 927
builds the context ribbon, and `_on_help` owns the Help action. CAMERA already
owns this file. **No additional panel module is needed to replace the nonexistent
`python/synapse/panel/synapse_shelf.py`.** `compositor.py:45` only dispatches those
builders and remains LEVER territory.

There **is** an external file named `houdini/scripts/python/synapse_shelf.py`:
`open_panel` at line 106 owns the docked-open entry path (existing-tab and docking
branches from line 133); `houdini/toolbar/synapse.shelf` invokes shelf callbacks.
These are not header/ribbon constructors, are outside the panel census, and are
not added to CAMERA's write set. The protected docked-open path remains untouched.
Thus the contract's broad phrase "does not exist" means absent under `panel/`,
not absent from the repository. Producer search:

```powershell
Select-String -Path python/synapse/panel/*.py -Pattern 'shelf|ribbon|header|DsHeader'
Get-ChildItem -Path . -Recurse -File -Filter '*shelf*'
```

The current header is two rows plus a separate ribbon (`synapse_panel.py:620`,
`:627`, `:715`, `:934`), not already the one-row target. `Help` is already wired
to `_on_help` at `:730`; changing its glyph is presentation work. `DsRailMeter`
is constructed but explicitly hidden (`:766`), so a naming site does not prove a
visible widget. Preserve lifecycle, completion refresh and shelf-open paths.

## Remaining source-declared widget regions

The appendix below expands **every one of the 107 primary spacing sites** and
the 4 additional grid sites into a source owner. This table gives their semantic
groupings and roles; it also covers painted/no-layout widgets. A plain shared
name does not prove a unique QSS hook. Shell zero margins are intentional source
facts; LEVER must preserve shell constraints when deciding how a role applies.

| Visible/state-dependent region | Widget ids / naming evidence | Spacing owner / other producer | Target role | Wave owner |
|---|---|---|---|---|
| Panel root and stacked faces | `self` / `DsRoot`; `_faces`, `_converse_stack` | `synapse_panel.py:484`, `:485`; `:1076` stacks | `group` (shell) | CAMERA |
| Input, Send and resize grip | `_input` / `DsInput`, `_send_btn` / `DsSend`, grip / `DsGrip` | `synapse_panel.py:1832`, `:1833`, `:1845`; naming `:124`, `:209`, `:1857` | `group`, action `row`/`label` | CAMERA |
| Build-HDA chat page / buttons | `_hda_prompt` / `DsInput`; `row` actions | `synapse_panel.py:1698`, `:1699`, `:1711` | `group`, `row` actions | CAMERA |
| Work face shell, receipts fallback, done fallback | `DsSection` from `_section`; `_work`, `_review` when components available | `synapse_panel.py:1124`, `:1125`, `:1136`, `:1168` | `group` / `label` fallback | CAMERA |
| Alternate chat/HDA entry, toolbar, input controls, connection bar | `ModeStack`, `HdaModeWidget`, mode toggle names; `connection_frame`, `status_dot`, `status_label`, `connect_button` | `chat_panel.py:163`, `:177`, `:205`, `:398`, `:407`, `:423`, `:437`, `:628`, `:729`; full sites below | `group` shells; `row` toolbar/input; `label` status | SWEEP_A |
| Work hero/bucket grid/plan | `FaceWork`, `BucketGrid`; `DsSection`, `DsCookBar`, `DsActs` | `face_work.py:184`, `:185`, `:189`, `:223`; painted `BucketGrid` at `:55` | `group` work/plan; `row` acts; `label` plan rows | SWEEP_A |
| Review hero/credit/flags/receipts/dendrites/actions | `FaceReview`, `RenderHero`; shared `DsSection`, `DsVerb` | `face_review.py:204`, `:236`, `:258`, `:261`, `:262`, `:268`, `:280`, `:293`, `:296`, `:321` | `group`, credits `parm_row`, flags/receipts `row`, actions `label` | SWEEP_A |
| Consent proposal cards / gate body / integrity summary | `_ProposalCard` / `gateCard`; `GateWidget` | `gate_widget.py:168`, `:173`, `:224`, `:426`, `:451`, `:459`, `:469` | `card` proposal shell; `group` body; `label` actions | SWEEP_A |
| Context bar / context chips | `context_bar_v2`, `ctx_*`, `ws_path_button`; `ContextChips` | `context_bar.py:410`, `:415`, `:465`, `:471`, `:595` | `group` shell; `row` context/actions; `tag` chips | SWEEP_A |
| Quick action expander and pills | `QuickActionPills`; unnamed outer/pill containers | `quick_actions.py:120`, `:121`, `:142`, `:143` | `group` shell; `row` action rail; `tag` pills | SWEEP_A |
| HDA Describe / Building / Result | `DescribeView`, `BuildingView`, `ResultView`; `HdaPromptInput`, `HdaContextSelector`, `HdaGenerateBtn`, `HdaProgressBar`, `StageLabel`, `CancelBtn`, `SectionLabel`, `NodePathLabel`, `ParamTable`, `HdaActionBtn` | `hda_views.py:35`, `:67`, `:158`, `:184`, `:278`, `:328` | `group` pages; `row` actions; `parm_row` parameter table; `label` stages | SWEEP_B |
| Tool palette, filter chips, results | `ToolPalette` / `DsSection`, `DsField`, `DsList`, `DsChip` | `tool_palette.py:193`, `:194`, `:229` | `group` shell; `tag` chips; `row` results | SWEEP_B |
| Command palette overlay/search/results | `CommandPaletteWidget`, `PaletteContainer` | `command_palette.py:430`, `:434`, `:435` | `group`, `row` results | SWEEP_B |
| Working dot and status text | `workingIndicatorDot`, `workingIndicatorText` | `working_indicator.py:229`, `:230` | `group` indicator; `label` text | SWEEP_B |
| Health strip cells | `health_strip`; named label children from cell keys | `health_strip.py:412`, `:413`; inline sheet `:417`; cell HTML `:375` | `group` strip; `tag`/`label` cells | UNASSIGNED |
| Integrity transcript / claims | `IntegrityReadout` / `DsSection`; `_box` | `integrity_readout.py:81`, `:82`; widget `:73` | `group` claims; `row` entries | UNASSIGNED |
| Health infographic | `HealthInfographic` / `DsSection` | `health_infographic.py:52`; painted geometry, no counted layout calls | `group` surface; no implied layout migration | UNASSIGNED |
| Shared component primitives | `DsButton`, `DsPill`, `DsCard`, `DsBadge`, `DsProgress`, `DsDivider`; unnamed `StatusDot`, `MarkDot`, labels | `designsystem/components.py:54`, `:68`, `:77`, `:92`, `:107`, `:138`, `:307`, `:319`, `:327`; excluded from primary census | `row`, `tag`, `card`, `label`, `group` as used | Existing factories; no CENSUS edits |

## Rendered transcript subregions (HTML, not standalone widgets)

Each output is hosted in the chat browser; objectName and QLayout ownership do
not exist inside the HTML. Target roles describe the intended visual hierarchy,
not Qt properties that can be attached to a text span. Counted foreign hex is
listed per file in JSON; these producers also contain CSS attributes which the
`setStyleSheet` counter deliberately does not count.

| Output region | Source producer | Target role | Wave owner |
|---|---|---|---|
| User/assistant/system turns, timestamp labels, code/list blocks | `message_formatter.py:307`, `:331`, `:356`, `:365`, `:95`, `:157`; `chat_display.py:80` | `group` turn, `label` header, `row` list | CAMERA T3 + SWEEP_B formatter |
| VEX reference and highlighted snippets | `vex_tutor.py:811`, `:856` | `group`, `label`, `row` reference | SWEEP_B |
| APEX trace / explanation | `apex_trace.py:641`; `apex_explainer.py:796` | `group`, `label`, `row` | SWEEP_B |
| Scene diagnosis / performance / network trace / cross-scene context | `scene_doctor.py:686`; `performance_profiler.py:335`; `network_trace.py:436`; `cross_scene.py:424` | `group`, `label`, `row`, `tag` status | SWEEP_B |
| Agent health | `agent_health.py:161` | `group`, `row`, `tag` | UNASSIGNED |
| APEX recipes and recipe details | `apex_recipes.py:724`, `:763` | `group`, `row`, `label` | UNASSIGNED |
| Bookmarks and dependencies | `bookmarks.py:160`; `dependency_map.py:434` | `row`, `tag`, `label` | UNASSIGNED |
| Error translation | `error_translator.py:476` | `group`, `label` | UNASSIGNED |
| Recipe categories and details | `recipe_book.py:765`, `:795`, `:843` | `group`, `row`, `label` | UNASSIGNED |
| Render preflight | `render_preflight.py:871` | `group`, `row`, `tag` | UNASSIGNED |
| Saved shots and snapshot list | `save_shot.py:368`, `:452` | `group`, `row`, `label` | UNASSIGNED |
| Session integrity and journal | `session_integrity.py:182`; `session_journal.py:233` | `group`, `row`, `label` | UNASSIGNED |

## Findings for LEVER / CAMERA / sweeps

- Primary spacing is **107 in 14 files**, not the plan's 108 in 12. The plan's
  printed per-file list itself sums to **103**; `health_strip.py` and
  `integrity_readout.py` add 2 each. Source counts reproduce the contract's 107.
- There are **4 additional grid-spacing calls** (`face_review.py:261`, `:262`;
  `face_token.py:448`, `:449`). Primary guard counts do not cover these methods.
  `addSpacing`, fixed dimensions, painted geometry and rich-text margins are
  also outside that counter; zero primary sites alone cannot prove all rhythm.
- `chat_display.py` is hex-free but has **2 setStyleSheet calls**. Its 4 HTML
  `style=` attributes are a different count. CAMERA's T3 includes both lifecycles
  of the browser sheet; `message_formatter.py` and legacy `styles.py` are SWEEP_B.
- **135 raw hex sites / 75 distinct values**, not approximately 60 distinct.
  Raw sites include comments and token-equivalent fallbacks by design.
- **34 direct Ds naming sites / 18 distinct names outside designsystem**;
  including factory definitions: **40 sites / 24 distinct names**. The plan's
  "24 widgets" is reproducible as distinct names, not runtime cardinality.
- QSS has **13 density rule blocks / 15 selectors**: 7 existing padding blocks,
  6 margin blocks (3 camera targets times airy/tight). No standard-density block.
  `designsystem/qss.py:293` begins padding rules; `:336` begins camera margins.
  The plan's "3 rules" means 3 margin targets, not all current rule blocks.
- Twelve unassigned files carry **4 spacing + 1 inline + 41 raw hex = 46**
  primary counted sites. Their untouched residue already exceeds the wave's
  panel-wide 20-site target; exemptions currently number zero. This is an
  ownership finding, not authority to edit them. They are the UNASSIGNED rows
  above with nonzero counts (health infographic has zero and is not in the 12).
- All visible regions cannot be proven at 380 px from AST. Docking, real font
  metrics, actual tree visibility, screenshots and GUI sign-off remain NOT_RUN
  in CENSUS; LEVER/CAMERA/CRUX own those checks. No host or Qt import is needed
  to reproduce this map's source claims.

## Complete spacing-owner appendix

Every row is a lexical scope in the census. Receiver names refer to the source
layout; a constructor parent is listed where statically explicit. `UNKNOWN`
means a parentless nested layout or a later attachment, not a missing widget.
Names list explicit objectNames in that scope; shared/inherited names are
documented in the semantic tables above. Values are source expressions. Role
families are inherited from the matching semantic region above.

| Source region / target role family | Widget/receiver and explicit names | Every spacing site |
|---|---|---|
| `SynapseChatPanel.createInterface` / group / row / label (see region table) | main_layout -> self._root; chat_layout -> self._chat_widget; hda_layout -> self._hda_container; objectNames: HdaModeWidget, ModeStack | `chat_panel.py:163` `main_layout.setContentsMargins(0, 0, 0, 0)`; `chat_panel.py:164` `main_layout.setSpacing(0)`; `chat_panel.py:177` `chat_layout.setContentsMargins(0, 0, 0, 0)`; `chat_panel.py:178` `chat_layout.setSpacing(0)`; `chat_panel.py:205` `hda_layout.setContentsMargins(0, 0, 0, 0)`; `chat_panel.py:206` `hda_layout.setSpacing(0)` |
| `SynapseChatPanel._build_input_area` / group / row / label (see region table) | outer_layout -> container; input_row -> UNKNOWN; controls_layout -> UNKNOWN; size_row -> UNKNOWN | `chat_panel.py:398` `outer_layout.setContentsMargins(8, 6, 8, 8)`; `chat_panel.py:399` `outer_layout.setSpacing(4)`; `chat_panel.py:407` `input_row.setSpacing(8)`; `chat_panel.py:423` `controls_layout.setSpacing(4)`; `chat_panel.py:437` `size_row.setSpacing(2)`; `chat_panel.py:438` `size_row.setContentsMargins(0, 0, 0, 0)` |
| `SynapseChatPanel._build_connection_bar` / group / row / label (see region table) | layout -> frame; objectNames: connect_button, connection_frame, status_dot, status_label, ws_path_button | `chat_panel.py:628` `layout.setContentsMargins(12, 6, 12, 6)`; `chat_panel.py:629` `layout.setSpacing(8)` |
| `SynapseChatPanel._build_mode_toolbar` / group / row / label (see region table) | layout -> toolbar; objectNames: ModeToggleActive, ModeToggleInactive | `chat_panel.py:729` `layout.setContentsMargins(8, 4, 8, 4)`; `chat_panel.py:730` `layout.setSpacing(6)` |
| `CommandPaletteWidget.__init__` / group / row / label (see region table) | outer -> self; layout -> container; objectNames: PaletteContainer | `command_palette.py:430` `outer.setContentsMargins(0, 0, 0, 0)`; `command_palette.py:434` `layout.setContentsMargins(12, 10, 12, 10)`; `command_palette.py:435` `layout.setSpacing(6)` |
| `build_context_bar_widget` / group / row / label (see region table) | outer -> root; row1 -> UNKNOWN; row2 -> UNKNOWN; actions_layout -> actions_container; objectNames: context_bar_v2, ctx_actions, ctx_breadcrumb, ctx_frame, ctx_health, ctx_memory | `context_bar.py:410` `outer.setContentsMargins(16, SPACE_XS, 16, SPACE_XS)`; `context_bar.py:411` `outer.setSpacing(SPACE_XS)`; `context_bar.py:415` `row1.setSpacing(SPACE_SM)`; `context_bar.py:465` `row2.setSpacing(SPACE_XS)`; `context_bar.py:471` `actions_layout.setContentsMargins(0, 0, 0, 0)`; `context_bar.py:472` `actions_layout.setSpacing(SPACE_XS)` |
| `ContextChips.__init__` / group / row / label (see region table) | lay -> self | `context_bar.py:595` `lay.setContentsMargins(0, 0, 0, 0)` |
| `FaceReview.__init__` / group / row / label (see region table) | col -> self; loc -> self._locator; self._credit_grid -> credit_wrap; self._flags_box -> UNKNOWN; self._receipt_box -> self._receipt_wrap; dcol -> self._detail; self._via_box -> UNKNOWN; acts -> acts_wrap; objectNames: DsActs, DsCookBar, DsSection | `face_review.py:204` `col.setContentsMargins(26, 20, 26, 20)`; `face_review.py:205` `col.setSpacing(t.SPACE_SM)`; `face_review.py:236` `loc.setContentsMargins(0, 0, 0, 0)`; `face_review.py:237` `loc.setSpacing(t.SPACE_SM)`; `face_review.py:258` `self._credit_grid.setContentsMargins(0, 0, 0, 0)`; `face_review.py:261` `self._credit_grid.setVerticalSpacing(8)`; `face_review.py:262` `self._credit_grid.setHorizontalSpacing(0)`; `face_review.py:268` `self._flags_box.setSpacing(1)`; `face_review.py:280` `self._receipt_box.setContentsMargins(0, 0, 0, 0)`; `face_review.py:281` `self._receipt_box.setSpacing(1)`; `face_review.py:293` `dcol.setContentsMargins(0, 0, 0, 0)`; `face_review.py:294` `dcol.setSpacing(1)`; `face_review.py:296` `self._via_box.setSpacing(1)`; `face_review.py:321` `acts.setContentsMargins(0, 20, 0, 0)`; `face_review.py:322` `acts.setSpacing(22)` |
| `FaceToken.__init__` / group / row / label (see region table) | outer -> self; lay -> body | `face_token.py:324` `outer.setContentsMargins(0, 0, 0, 0)`; `face_token.py:325` `outer.setSpacing(0)`; `face_token.py:337` `lay.setContentsMargins(t.GUTTER, 20, t.GUTTER, 20)`; `face_token.py:338` `lay.setSpacing(18)` |
| `FaceToken._legend` / group / row / label (see region table) | row -> w | `face_token.py:416` `row.setContentsMargins(0, 0, 0, 0)`; `face_token.py:417` `row.setSpacing(16)` |
| `FaceToken._kv_block` / parm_row / group | grid -> w | `face_token.py:447` `grid.setContentsMargins(0, 0, 0, 0)`; `face_token.py:448` `grid.setHorizontalSpacing(18)`; `face_token.py:449` `grid.setVerticalSpacing(6)` |
| `FaceWork.__init__` / group / row / label (see region table) | col -> self; head -> UNKNOWN; self._plan_box -> UNKNOWN; objectNames: DsCookBar, DsSection | `face_work.py:184` `col.setContentsMargins(26, 20, 26, 20)`; `face_work.py:185` `col.setSpacing(t.SPACE_SM)`; `face_work.py:189` `head.setSpacing(t.SPACE_SM)`; `face_work.py:223` `self._plan_box.setSpacing(2)` |
| `_ProposalCard.__init__` / group / row / label (see region table) | layout -> self; top_row -> UNKNOWN; btn_row -> UNKNOWN; objectNames: gateCard | `gate_widget.py:168` `layout.setContentsMargins(10, 8, 10, 8)`; `gate_widget.py:169` `layout.setSpacing(4)`; `gate_widget.py:173` `top_row.setSpacing(8)`; `gate_widget.py:224` `btn_row.setSpacing(8)` |
| `GateWidget._build_ui` / group / row / label (see region table) | layout -> self; body_layout -> self._body; self._proposals_layout -> self._proposals_container; integrity_layout -> self._integrity_row | `gate_widget.py:426` `layout.setContentsMargins(0, 0, 0, 0)`; `gate_widget.py:427` `layout.setSpacing(0)`; `gate_widget.py:451` `body_layout.setContentsMargins(8, 4, 8, 4)`; `gate_widget.py:452` `body_layout.setSpacing(4)`; `gate_widget.py:459` `self._proposals_layout.setContentsMargins(0, 0, 0, 0)`; `gate_widget.py:460` `self._proposals_layout.setSpacing(4)`; `gate_widget.py:469` `integrity_layout.setContentsMargins(8, 4, 8, 4)`; `gate_widget.py:470` `integrity_layout.setSpacing(8)` |
| `DescribeView._build_ui` / group / row / label (see region table) | layout -> self; options_row -> UNKNOWN; objectNames: HdaContextSelector, HdaGenerateBtn, HdaPromptInput, SectionLabel | `hda_views.py:35` `layout.setContentsMargins(16, 16, 16, 16)`; `hda_views.py:36` `layout.setSpacing(12)`; `hda_views.py:67` `options_row.setSpacing(8)` |
| `BuildingView._build_ui` / group / row / label (see region table) | layout -> self; self.dots_layout -> UNKNOWN; objectNames: CancelBtn, HdaProgressBar, StageLabel | `hda_views.py:158` `layout.setContentsMargins(16, 16, 16, 16)`; `hda_views.py:159` `layout.setSpacing(12)`; `hda_views.py:184` `self.dots_layout.setSpacing(4)` |
| `ResultView._build_ui` / group / row / label (see region table) | layout -> self; btn_row -> UNKNOWN; objectNames: HdaActionBtn, HdaGenerateBtn, NodePathLabel, ParamTable | `hda_views.py:278` `layout.setContentsMargins(16, 16, 16, 16)`; `hda_views.py:279` `layout.setSpacing(12)`; `hda_views.py:328` `btn_row.setSpacing(8)` |
| `HealthStrip.__init__` / group / row / label (see region table) | row -> self; objectNames: health_strip | `health_strip.py:412` `row.setContentsMargins(0, 0, 0, 0)`; `health_strip.py:413` `row.setSpacing(t.SPACE_MD)` |
| `IntegrityReadout.__init__` / group / row / label (see region table) | self._box -> self; objectNames: DsSection | `integrity_readout.py:81` `self._box.setContentsMargins(0, 0, 0, 0)`; `integrity_readout.py:82` `self._box.setSpacing(1)` |
| `QuickActionPills._build_ui` / group / row / label (see region table) | self._outer_layout -> self; self._pills_layout -> self._pills_container | `quick_actions.py:120` `self._outer_layout.setContentsMargins(8, 6, 8, 6)`; `quick_actions.py:121` `self._outer_layout.setSpacing(0)`; `quick_actions.py:142` `self._pills_layout.setContentsMargins(4, 0, 0, 0)`; `quick_actions.py:143` `self._pills_layout.setSpacing(6)` |
| `SynapsePanel._build_ui` / group / row / label (see region table) | root -> self | `synapse_panel.py:484` `root.setContentsMargins(0, 0, 0, 0)`; `synapse_panel.py:485` `root.setSpacing(0)` |
| `SynapsePanel._build_rail` / group / row / label (see region table) | col -> w; top -> UNKNOWN; bot -> UNKNOWN; objectNames: DsAuthor, DsHeader, DsKHint, DsMeter, DsRailMeter, DsStop | `synapse_panel.py:622` `col.setContentsMargins(t.GUTTER, 16, t.GUTTER, 14)`; `synapse_panel.py:623` `col.setSpacing(t.SPACE_SM)`; `synapse_panel.py:628` `top.setSpacing(t.SPACE_SM)`; `synapse_panel.py:716` `bot.setSpacing(t.SPACE_SM)` |
| `SynapsePanel._build_context_ribbon` / group / row / label (see region table) | lay -> w | `synapse_panel.py:935` `lay.setContentsMargins(t.GUTTER, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)` |
| `SynapsePanel._build_mode_bar` / group / row / label (see region table) | lay -> w; objectNames: DsTabRow | `synapse_panel.py:994` `lay.setContentsMargins(t.GUTTER, 24, t.GUTTER, 0)`; `synapse_panel.py:995` `lay.setSpacing(28)` |
| `SynapsePanel._build_direct_face` / group / row / label (see region table) | col -> page | `synapse_panel.py:1104` `col.setContentsMargins(t.GUTTER, 24, t.GUTTER, 24)`; `synapse_panel.py:1105` `col.setSpacing(0)` |
| `SynapsePanel._build_work_face` / group / row / label (see region table) | col -> page; _l -> cook | `synapse_panel.py:1124` `col.setContentsMargins(0, 0, 0, 0)`; `synapse_panel.py:1125` `col.setSpacing(0)`; `synapse_panel.py:1136` `_l.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)` |
| `SynapsePanel._build_done_substate` / group / row / label (see region table) | col -> page | `synapse_panel.py:1168` `col.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)` |
| `SynapsePanel._build_hda_form` / group / row / label (see region table) | lay -> page; row -> UNKNOWN; objectNames: DsInput | `synapse_panel.py:1698` `lay.setContentsMargins(t.SPACE_MD, t.SPACE_MD, t.SPACE_MD, t.SPACE_MD)`; `synapse_panel.py:1699` `lay.setSpacing(t.SPACE_SM)`; `synapse_panel.py:1711` `row.setSpacing(t.SPACE_SM)` |
| `SynapsePanel._build_act` / group / row / label (see region table) | lay -> w | `synapse_panel.py:1809` `lay.setContentsMargins(0, t.SPACE_MD, 0, t.SPACE_SM)`; `synapse_panel.py:1813` `lay.setSpacing(t.SPACE_LG)` |
| `SynapsePanel._build_input` / group / row / label (see region table) | col -> w; row -> UNKNOWN; objectNames: DsSend | `synapse_panel.py:1832` `col.setContentsMargins(0, 0, 0, 0)`; `synapse_panel.py:1833` `col.setSpacing(t.SPACE_XS)`; `synapse_panel.py:1845` `row.setSpacing(t.SPACE_SM)` |
| `ToolPalette.__init__` / group / row / label (see region table) | lay -> self; objectNames: DsField, DsList, DsRoot | `tool_palette.py:193` `lay.setContentsMargins(t.SPACE_SM, t.SPACE_SM, t.SPACE_SM, t.SPACE_SM)`; `tool_palette.py:194` `lay.setSpacing(t.SPACE_XS)` |
| `ToolPalette._build_chip_row` / group / row / label (see region table) | row -> UNKNOWN; objectNames: DsChip | `tool_palette.py:229` `row.setSpacing(t.SPACE_XS)` |
| `WorkingIndicator.__init__` / group / row / label (see region table) | row -> self; objectNames: workingIndicatorDot, workingIndicatorText | `working_indicator.py:229` `row.setContentsMargins(0, 0, 0, 0)`; `working_indicator.py:230` `row.setSpacing(getattr(t, 'SPACE_XS', 4))` |
