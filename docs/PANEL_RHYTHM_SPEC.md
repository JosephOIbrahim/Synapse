# Panel Rhythm v2 - PD-LEVER

Hand-authored 2026-09-04 from `docs/PANEL_BATTLEPLAN_PD.md` sections 1, 3 and 4;
`/design` is unavailable in this runtime. This is the implementation spec for
LEVER, followed by CAMERA and the sweeps. Structural reference:
`docs/panel_pd/COHERE_REFERENCE.md`; no reference branding, palette or family
enters the panel. No token is added and `designsystem/fontload.py` is unchanged.

## 1 - Scope and measured input

CENSUS source base: `a5b975c1`, production base `6e3dd963`. Producers:
`docs/PANEL_REGION_MAP.md` and
`harness/panel_pd/runs/2026-09-04/rhythm_census.json`.
The latter records 107 spacing calls, 106 inline sheets, 135 raw six-digit hex
occurrences (75 distinct), zero exemptions, and four additional grid-spacing
calls. These are source sites, not runtime widget counts. Including factories,
24 distinct Ds names occur at 40 sites. Recall is ABSENT, not a measured widget.

The ownership table in `docs/panel_pd/SWARM_CONTRACT.md` controls writes.
LEVER builds the two appliers and their tests; adding properties to existing
regions belongs to CAMERA/SWEEP_A/SWEEP_B. Existing unmarked widgets retain
imperative layout values. This leg does not claim camera migration is complete.

## 2 - One property, two appliers

`rhythm_role` on a QWidget chooses the component pattern. QSS owns paint,
leaf padding, minimum dimensions and outer margins. `rhythm.apply(root, density)`
walks the QObject tree (including the root and through non-widget children),
changes only marked widget layouts, and derives inter-item spacing from the
role's base via `tokens.gap`. Layout content margins are fixed per role.
No QApplication or Qt import is required merely to import the rhythm module.

`compose()` stamps density before building, then repolishes the complete tree
and applies rhythm after all region builders return. `SynapsePanel._recompose`
already calls this same function on cached widgets. One shared call site serves
both initial compose and recompose; moving repolish after construction avoids
missing first-build descendants. No lifecycle edits or extra refresh path.

Repeated apply computes from bases, never from current spacing. Switching
airy -> tight -> standard -> airy restores exact values. Removing a role leaves
the current spacing and contents margins unchanged on subsequent calls; it does
not restore constructor values. Unmarked child layouts are never recursively
overwritten just because an ancestor is marked: mark each layout's owning widget.

Unknown nonempty role: warn once per distinct value and use group base 16 at
STANDARD density with zero contents margins. This is the stricter interpretation
of "unknown role -> standard" (not requested-density styling of an unknown role).
Unknown density supplied directly to apply: warn once and use standard;
manifest validation continues to reject unknown densities before composition.

## 3 - Density, type and docking bounds

Curious = airy x1.5; Expert = standard x1; ML = tight x0.75.
Only gaps scale. Standard emits no density selector. All density-selected QSS
declarations are margin or margin-*; the seven inherited density-padding blocks
are removed. Existing unconditional padding stays fixed. The existing BP2
DsTabRow/DsVerb/DsHeader gap rules remain for unmigrated widgets.

All dimensions below use existing `designsystem/tokens.py` vocabulary:
`SPACE_GRID=(4,8,12,16,24,32,48)`, `ROW_MIN_H`, `RADIUS_MD`, `RADIUS_CARD`,
`RADIUS_ROUND`, `SPACE_XL`, `FONT_FLOOR_PX`, and weight tokens from BP4-PANELFONT
(`git show 81f3fb08 --stat`). Ratios and arithmetic on these values are component
rules, not new tokens. No literal font size or family is introduced.

Label/tag nominal sizes are body x0.72/x0.68, rounded and clamped to
`FONT_FLOOR_PX` and the supplied host body scale, so a smaller nominal role never
undercuts that floor. QSS uses `WEIGHT_MEDIUM`; row/card/parameter content uses
`WEIGHT_REGULAR`. Mono uses the existing `fontload.apply_family(..., mono=True)`
path. Uppercase and tracking use QFont capitalization/PercentageSpacing in
rhythm, after QSS polish, without rewriting widget text. Tracking is +0.08 em
for labels and +0.06 em for tags; neither varies by density. Qt QSS does not
provide text-transform/letter-spacing in its documented property list:
[Qt QSS reference](https://doc.qt.io/qt-6/stylesheet-reference.html),
[QFont capitalization and tracking](https://doc.qt.io/qt-6/qfont.html).
No fontload change or family registration policy change.

**Docking:** 380 px width in all three densities. The ratified YAML
`.synapse/contracts/docking-minimums.yaml` requires no overflow at 400 px tall
and no child's hard minimum height above 200 px. The current `PANEL_MIN_HEIGHT`
token is 420, so the test takes the stricter YAML 400 rather than copying the
420 token. Horizontal minimum demand must be <=380; assembled vertical minimum
demand <=400; non-root hard minimum heights <=200. Test actual constructed
regions and all reachable faces, plus the five generic patterns. A generic
pattern fitting does not certify its downstream migrated region.

PySide absence produces explicit skips, recorded as NOT_RUN in the receipt.
Recall has its own absence skip until CAMERA supplies it. A live Houdini GUI is
never used by these tests. Screenshots require bound hython; no stand-in PNGs.
Host font floor provenance remains UNKNOWN until Joe's H22.0.400 GUI probe.

## 4 - Role table and the five component patterns

Pixel arithmetic: airy = base *3/2; standard = base; tight = base *3/4.
All bases belong to SPACE_GRID, hence these products are integral. Contents
margins below are (left, top, right, bottom); they never scale.

| role / gap owner | base | airy | standard | tight | fixed layout margins |
|---|---:|---:|---:|---:|---|
| label: contents / below | 12 | 18 | 12 | 9 | (0,0,0,0) |
| label: outer above (QSS) | 24 | 36 | 24 | 18 | unchanged |
| row: between contents/items | 12 | 18 | 12 | 9 | (16,12,16,12) |
| tag: from label / contents | 16 | 24 | 16 | 12 | (10,6,10,6) |
| card: between cards in a collection | 16 | 24 | 16 | 12 | (0,0,0,0) |
| parm_row: between rows/cells | 4 | 6 | 4 | 3 | (0,0,0,0) |
| group: between groups | 16 | 24 | 16 | 12 | (0,0,0,0) |
| parameter section head (label QSS override) | 32 | 48 | 32 | 24 | unchanged |

1. **Label.** Set `rhythm_role="label"` on section text: muted mono, upper,
   tracked, 24 above/12 below via QSS. No border on the label. Use the existing
   DsDivider under the group; no new divider widget class. A parameter section
   label named `DsParmSection` gets the 32-px section-head base.
2. **Row.** Set `rhythm_role="row"` on an item/container. Body normal-weight,
   minimum height 44, radius 8, one-pixel BORDER hairline. QWidget containers
   receive fixed 12/16 padding as layout margins; leaf labels/buttons get it
   through QSS, never both on the same component. A child named `DsRowGlyph`
   reserves a 44-by-44 cell with a right hairline. Parent collection spacing
   owns the between-row gap; no extra per-row bottom margin compounds it.
3. **Tag.** `rhythm_role="tag"`: neutral SURFACE, TEXT_SECONDARY, mono upper,
   tracked, radius RADIUS_ROUND, padding 6/10 (derived from existing rungs).
   Leaf padding is QSS; layout-bearing tag containers use fixed layout margins.
   The QSS leading margin has base 16; do not also add an explicit spacer before
   it. `status="BLOCKED"` selects HOT_SOFT. HIT/NO HIT/UNAVAILABLE stay neutral;
   UNKNOWN is text. No success-green tag. Existing DsBadge/tag combinations
   receive explicit role rules so old kind/prominence colors cannot win.
4. **Card.** `rhythm_role="card"` belongs to a collection whose layout separates
   cards by 16. The existing `DsCard` is the individual surface, radius 10.
   Its direct children are `DsCardHeader`, `DsCardBody`, `DsCardFooter`: header
   band 40, body padding 16, footer band 40, one-pixel hairlines below header
   and body. Header/footer content is inset 16 horizontally. The fixed-band
   interior is not a card collection: downstream construction must keep its
   inter-band spacing at zero (a reasoned structural exemption if necessary),
   instead of stamping the collection role on it. Footer text action left,
   neutral status tag right. This leg supplies rules, not the recall widget.
5. **Parameter row.** `rhythm_role="parm_row"`: body, minimum row height 24;
   direct child ids `DsParmLabel` and `DsParmValue` have widths 128/64
   (`SPACE_32*4`, `SPACE_32*2`). Optional `DsParmControl` fills remaining space
   through layout stretch supplied by the caller. Nested names are direct-child
   scoped to prevent leaking onto unrelated labels. A two-column source remains
   two columns; no control is invented. UNKNOWN stays a value string. Groups
   use `group` (16), section headers use the 32-px label override.

### CENSUS region map / migration handoff

Full authoritative source-site inventory: `docs/PANEL_REGION_MAP.md`, including
all 107 primary spacing calls, four grid calls, alternate/HTML surfaces and
unassigned regions. This compact mapping preserves its six camera regions:

| region | current ids / source owner | role target / remaining work |
|---|---|---|
| Profile strip | DsTabRow, DsPill; synapse_panel.py:994-995 | group container, row pills; CAMERA removes 28-px gap |
| Header/ribbon | DsHeader / unnamed ribbon label; synapse_panel.py:622,935 | group / label / tag; sibling ribbon is not reached by header selector |
| Chat transcript | unnamed ChatDisplay; synapse_panel.py:944,1104; chat_display.py | group turns, label headers; HTML is not a QWidget tree |
| Verb rail | DsVerb; synapse_panel.py:1809,1813 | group rail, label actions; group hairline in CAMERA |
| Recall result | ABSENT in census | DsCard bands / card collection / tag; CAMERA creates recall_card.py |
| TOKEN face | DsSection field, unnamed key/value grid; face_token.py:337,447-449 | parm_row / group / label; no pre-existing third control column |

Remaining widget surfaces map to group/row/label/tag/parm_row as recorded in the
region map: chat/HDA alternate entry, Work/Review, gate cards, context bar,
quick actions, HDA views, palettes, working indicator, health and integrity.
The eight rich-text generators and the unassigned HTML producers need HTML
styling at their own seam; a Qt dynamic property cannot reach document spans.
Header/ribbon visual ownership is synapse_panel.py. The external
houdini/scripts/python/synapse_shelf.py launcher is protected and untouched.

## 5 · What Session B lands vs. follow-ups (the honest ledger)

**Lands this leg (`designsystem/` only, in-territory, testable headless):**
1. `tokens.py`: `SPACE_12/32/48` + `SPACE_GRID` (additive, no renames);
   `ROW_MIN_H`, `RADIUS_CARD`, `RADIUS_ROUND` (additive); `DENSITY_GAP_SCALE` +
   `gap()` helper. Zero colour, zero font, existing values untouched.
2. `qss.py`: a **sec.7 five-region rhythm** block — density-keyed **`margin`**
   (gap) rules for the reachable region widgets (`#DsTabRow`, `#DsVerb`,
   `#DsHeader`), scaled by `gap()` (airy ×1.5 / tight ×0.75); paddings/radii/
   hairlines fixed in base rules; **no `density="standard"` rule**; **no new
   hex**; airy ≠ tight.
3. A headless test: gap tokens step by the density multipliers per profile
   (curious→airy, expert→standard, ml→tight); Expert manifest pin stays green.

**Follow-ups (out of `designsystem/` territory or "zero new widgets"):**
- **Recall card build** (Region 3) — net-new widget → held `spawn`. Tokens ready.
- **Parm-row objectNames** (Region 4) — `face_token.py` needs objectNames for the
  grid rhythm to be QSS-reachable. UNKNOWN-as-text already correct.
- **Verb-group hairline + `?` glyph** (Regions 2, 5) — panel-module additions.
- **Zero the Python `setSpacing()`** on the tab row / verb rail / token rows so
  QSS owns the inter-item gap outright (28/24/18 currently compound).

### v2 extension - PD-LEVER (the v1 ledger above is preserved verbatim)

- LEVER supplies opt-in layout rhythm, role QSS, guard and real-Qt docking tests.
  It does not mark camera/sweep widgets or claim their residual has fallen.
- QSS never owned QLayout inter-item spacing: v1's "so QSS owns" follow-up now
  means the rhythm Python applier; both read the same role and density.
- The old density-padding blocks are removed, resolving the CENSUS finding.
  Gaps alone vary; no new colors, type families, tokens, widgets or profile knobs.
- Residual seed: 107+106+135 = 348, plus separately guarded four grid sites.
  `harness/panel_pd/RESIDUAL.json` is explicitly authorized by the LEVER brief,
  despite omission from the ownership-table row. The guard rejects novel
  untagged sites by comparing normalized site identities to the committed census,
  as well as enforcing the checked-in ceiling. Removed sites cannot buy room for
  new untagged owners. Empty/fake comment tags do not exempt anything.
- The ceiling may only decrease relative to its latest committed version.
  CAMERA/sweeps must report reductions for the orchestrator to ratchet it down;
  the generic seed is not the final wave acceptance of <=20 tagged sites.
- CENSUS found 46 sites in twelve UNASSIGNED files, already above that wave goal.
  Ownership must be resolved by the orchestrator, not silently widened here.
- Font floor provenance, screenshots, runtime docking and independent CRUX
  remain unverified until the corresponding substrate/run supplies evidence.
  The Expert pin is structural/manifest-only, never pixel equivalence.

## 6 - Validation and delivery

`tests/test_panel_rhythm_owner.py`: census-based monotonic guard, independent
fixtures and negative controls, margin-only density, typography/pattern rules,
import without Qt, compositor initial/recompose sequencing.
`tests/test_panel_rhythm_docking.py`: real QWidget role spacing, idempotence,
role-removal negative control, font behavior, five component patterns and actual
panel regions at 380x400 in every density; explicit absence skips.
Required pins: tests/test_rope_expert_pin.py and tests/test_bp2_paneldesign_density.py.
Run the full suite once; compare counts against harness/panel_pd/BASELINE.md.
Mutate the implementation/fixtures and record red controls before restoring.

Evidence and limitations: docs/panel_pd/REPORT_LEVER.md.
Dated milestone handoff: harness/panel_pd/STATUS_LEVER.md. No separate bus under
this wave contract. Commit subject pd(lever): and required Codex trailer; no
merge, push, master write, release action or live Houdini GUI access.
