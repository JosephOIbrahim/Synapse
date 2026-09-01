# BP2-PANELDESIGN — leg notes (decisions · reachability · mutations · spawns)

Branch `bp2/paneldesign`. Spec-then-implement of the sec.7 spacing pass on the
five camera regions. Spacing tokens + QSS on the `density` root property, zero
new colours/widgets/families, Expert pin green.

## Gate
PANELTRUTH **merged** to master (`0d63f206`, on `master` + `origin/master`) — not
merely receipted — so the HELD condition (sec.12 R-6) is cleared. Input
`harness/battleplan/runs/2026-09-01/profile_diff.json` read from master; finding:
the three profiles differ ONLY in density + prompt overlay + prominence; widget
set identical (L5). No manifest change is needed — the density lever is already
wired (curious=airy / expert=standard / ml=tight).

## Key decisions (why the pass is shaped this way)
1. **The Expert pin is manifest-only.** `test_rope_expert_pin.py:106` compares
   `compositor.resolve(get_manifest("expert"))` against a hardcoded resolved
   dict — it reads NO QSS and NO tokens. So the pin stays green iff the Expert
   MANIFEST structure is untouched. This leg touches no manifest → pin green
   trivially, and tokens/qss are free to change. (The qss-snapshot fan-out
   confirmed: no test snapshots the stylesheet string and no test pins a
   SPACE_*/RADIUS_* value.)
2. **Gaps = QSS `margin`; paddings = QSS `padding` (fixed).** Qt QSS cannot set
   `QLayout.setSpacing()`. The one gap lever QSS owns is `margin`. So the density
   rhythm scales margins; paddings stay in the base rules, fixed — satisfying
   sec.7 "GAPS only, paddings fixed" AND `test_rope_density`'s margin/padding-only
   guard on density blocks.
3. **Standard has NO density rule.** The base (unconditional) `margin` rules ARE
   the ×1 rhythm; the sheet never emits a standard density block, so
   `test_rope_density.py:test_no_rule_for_standard` holds. (Bug caught + fixed
   in-session: an early qss.py comment carried the literal `density="standard"`,
   which the substring test would have failed — reworded.)
4. **SPACE scale is additive, never renamed.** Existing rungs are heavy
   consumers (SPACE_SM ×44 / XS ×25 / MD ×23 / LG ×9). Kept verbatim; the three
   grid stops the sec.7 ladder adds (12/32/48) are new, named by px. SPACE_XL
   (40) retained as the card-band height (a dimension, off the gap ladder).
5. **gap() is a pure multiplier** (`round(base × {airy 1.5 / std 1 / tight 0.75})`);
   every rung is a ×4 multiple so all stepped values are exact integers. An
   unknown density resolves to ×1 — a malformed manifest can never invert the
   rhythm.

## Region reachability ledger (runtime is truth)
| # | region | reachable this leg? | what landed / why not |
|---|---|---|---|
| 1 | profile tab strip (`DsTabRow`/`DsPill`) | ✅ partial | density-scaled group-gap margin on `#DsTabRow`. Inter-pill gap is Python `setSpacing(28)` (synapse_panel.py:995) — QSS-unreachable (follow-up). Active-in-SIGNAL already = the underline (filled pill retired qss.py:113-116); NOT reverted. |
| 2 | verb rail (`DsVerb`) | ✅ partial | density-scaled group margins on `#DsVerb`. Doubled inter-verb gap kept (Python `setSpacing(24)`, synapse_panel.py:1813). Group hairline needs a container objectName (panel edit) — follow-up. |
| 3 | recall card | ⛔ greenfield | NO widget exists; HIT/NO HIT/UNAVAILABLE/BLOCKED absent from panel/. Building it = new widget → violates "zero new widgets" + outside designsystem territory. Tokens provisioned (RADIUS_CARD/ROUND, HOT_SOFT). **Held spawn.** |
| 4 | TOKEN face rows (`face_token.py:444`) | ⚠ already-correct + unreachable | UNKNOWN-as-text ALREADY honoured (`face_token.py:480-485`, never a bar at zero). Rows are inline-styled QGridLabels with NO objectNames → QSS descendant rules can't key on them. Adding objectNames = panel edit (follow-up). |
| 5 | .hip ribbon + header (`DsHeader`) | ✅ partial | density-scaled group-gap margin on `#DsHeader`. Ribbon is already "one row, label style". The `?` glyph is unbuilt (a text "Help" button exists, synapse_panel.py:727) — follow-up. |

## Mutation teeth (candidates — CRUX verifies these turn RED)
- `gap()` → `return base_px` (drop the multiplier) ⇒ `TestGapMultiplier` +
  `TestRegionRhythmStepsByDensity` RED.
- `SPACE_12 = 11` ⇒ `TestSpaceGrid::test_grid_is_the_sec7_4pt_ladder` +
  `test_three_new_stops_added` RED.
- add `#DsRoot[density="standard"] ... {}` to qss ⇒ `TestGuardrails::
  test_no_standard_density_rule_in_the_sheet` + `test_rope_density::
  test_no_rule_for_standard` RED.
- put a `{t.SIGNAL}` (hex) in a region rhythm rule ⇒ `test_region_rhythm_
  introduces_no_hex` + `test_rope_prominence_visible::test_no_rule_introduces_
  a_hex_absent_from_tokens` (only if absent from tokens) RED.
- change an airy `#DsVerb` margin to a non-`gap()` value ⇒
  `TestRegionRhythmStepsByDensity::test_each_reachable_region_gap_steps_by_the_
  multiplier` RED.
- put `color`/`border` inside a density block ⇒ `TestGuardrails::
  test_density_blocks_are_spacing_only` + `test_rope_density::
  test_density_rules_step_spacing_only` RED.

## Chore (T4)
`python .synapse/verify.py no-importers python/synapse/panel/tokens.py python/synapse/panel`
→ **exit 1** (verify.py:70, importer found ⇒ not retired). Legacy pair kept: 8
live importers of panel/tokens.py + 3 of panel/styles.py. Host-scheme seeding
parked. (Gotcha logged: a `| grep` pipeline masked the exit code — read the raw
`$?`, not the pipe's.)

## Follow-up spawns (out of this leg's designsystem-only territory)
1. **Recall-card build** (Region 3) — net-new three-band `DsCard` widget with the
   footer status pill (HIT / NO HIT / UNAVAILABLE / BLOCKED; HOT_SOFT only for
   BLOCKED; never a colour for HIT). Tokens ready. Class outside `probe` → lands
   `held` for Joe.
2. **Parm-row objectNames** (Region 4) — add objectNames to `face_token._kv_block`
   rows so the sec.7 grid rhythm (label col 128 / value 64 / row 24 / section 32)
   is QSS-reachable. UNKNOWN-as-text already correct.
3. **Verb-group hairline + `?` glyph** (Regions 2, 5) — panel-module additions.
4. **Zero the Python `setSpacing()`** on the tab row (28) / verb rail (24) / token
   rows (18) so QSS owns the inter-item gap outright rather than compounding.
