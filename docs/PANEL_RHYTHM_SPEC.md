# Panel Rhythm — the sec.7 spacing pass (BP2-PANELDESIGN, Session A spec)

> **What this is.** The handoff spec the implement session (Session B) builds from:
> the token table, the per-region QSS rules, the density multipliers, and
> before/after measurements in px for the five camera regions. It **adds rhythm,
> not colour** — zero new colours, zero new widgets, zero new font families.
>
> **Provenance.** Derived from `docs/BATTLEPLAN.md` §7 (the rhythm rules), the
> merged `BP2-PANELTRUTH` finding `harness/battleplan/runs/2026-09-01/profile_diff.json`
> (what actually differs per profile: density + prompt overlay + prominence — the
> widget-id set is identical in all three profiles, L5), and a first-person read
> of the live panel code (`python/synapse/panel/`, cited file:line throughout).
>
> **The referee catch, up front (honesty · runtime is truth).** sec.7 describes an
> aspirational surface. Measured against the live code, three of the five regions
> are only *partly* reachable through the design system alone (`designsystem/` +
> QSS + tokens, this leg's territory). Each region below carries a **Reachability**
> line stating exactly what this leg lands vs. what is a documented follow-up. No
> region is claimed done that is not.

---

## 1 · What differs per profile (the input finding)

From `profile_diff.json` (base prompt sha `d06fd7e21aa6f4f3`, identical in all three):

| Profile | density | prompt overlay | prominence deltas |
|---|---|---|---|
| **curious** | `airy` | gentle-narration (1137 chars) | activity_meter/token_meter collapsed+quiet; token_pill quiet |
| **expert** | `standard` | none | none — the v5.42.0 baseline |
| **ml** | `tight` | terse-technical (350 chars) | author_token/token_meter/token_pill → hero |

**The capability (widget-id set) is identical in all three; every widget stays
`visible=True`.** So the rhythm pass is a pure *density* story: one panel-wide
`density` dynamic property on `#DsRoot`, three values, driving descendant QSS.
Curious gets the airy multiplier; Expert reads the same tokens at ×1; ML gets
tight. Nothing about *what* is shown changes — only *how much air*.

---

## 2 · Token table — the 4-pt grid mapped onto the existing `SPACE_*` names

sec.7 grid: `SPACE  4 · 8 · 12 · 16 · 24 · 32 · 48`. The existing scale
(`designsystem/tokens.py:431-435`) is `XS=4 · SM=8 · MD=16 · LG=24 · XL=40` —
heavily consumed (SM ×44, XS ×25, MD ×23, LG ×9 call sites in `panel/`), so the
existing names keep their values **verbatim, never renamed**. The three grid
stops the ladder adds (12 / 32 / 48) are **new, additive** tokens named by px so
the spec and QSS read unambiguously. `SPACE_XL=40` is retained as a fixed
card-band height (a dimension, off the gap ladder).

| grid px | token | status |
|---|---|---|
| 4  | `SPACE_XS` | existing — kept |
| 8  | `SPACE_SM` | existing — kept |
| 12 | `SPACE_12` | **NEW** — row-breath / label-below rung |
| 16 | `SPACE_MD` | existing — kept |
| 24 | `SPACE_LG` | existing — kept |
| 32 | `SPACE_32` | **NEW** — parm-row section-head gap |
| 48 | `SPACE_48` | **NEW** — doubled group gap (verb rail); 2 × `SPACE_LG` |
| (40) | `SPACE_XL` | existing — kept (card-band height, off the gap ladder) |

`SPACE_GRID = (4, 8, 12, 16, 24, 32, 48)` is added as the documented ladder.

**Fixed dimensions (sec.7, additive, never scaled by density):**

| role | token | px | note |
|---|---|---|---|
| list-row min height / glyph cell | `ROW_MIN_H` | 44 | glyph cell 44×44, hairline right |
| row radius | `RADIUS_MD` (exists) | 8 | sec.7 "8 rows" |
| card radius | `RADIUS_CARD` | 10 | **NEW** — sec.7 "10 cards" |
| pill radius | `RADIUS_ROUND` | 999 | **NEW** — sec.7 "999 pills" (fully rounded) |
| hairline | `BORDER` token | 1 px | never 2 px, never a shadow |

Colour: **none added.** Every rule references an existing token
(`SIGNAL`, `HOT_SOFT`, `CONIFEROUS`, `BORDER`, `HAIR`, `TEXT_*` — most
host-seeded via `_derive_palette`, so referenced by name, never as a hex).

---

## 3 · Density multipliers — GAPS only, paddings fixed

sec.7: `airy ×1.5 · standard ×1 · tight ×0.75 — GAPS only, paddings fixed`.

```
DENSITY_GAP_SCALE = {"airy": 1.5, "standard": 1.0, "tight": 0.75}
gap(base, density) = round(base × DENSITY_GAP_SCALE[density])   # integer px
```

All gap bases are multiples of 4, so every stepped value is an exact integer:

| base | tight ×0.75 | **standard ×1** | airy ×1.5 |
|---|---|---|---|
| 4  | 3  | 4  | 6  |
| 8  | 6  | 8  | 12 |
| 12 | 9  | 12 | 18 |
| 16 | 12 | 16 | 24 |
| 24 | 18 | 24 | 36 |
| 32 | 24 | 32 | 48 |
| 48 | 36 | 48 | 72 |

**Mechanism (already proven by PANELTRUTH, 08-04).** The compositor stamps
`density` on `#DsRoot` (`compositor.py:242`) then repolishes the whole tree
(`compositor.py:248 _repolish_tree`) so `#DsRoot[density="airy"] <descendant>`
rules actually repaint. **Standard has no rule on purpose** — it is the
unconditional base, so `'density="standard"'` never appears in the sheet
(`test_rope_density.py:95`). airy/tight blocks carry **only** `margin`/`padding`
declarations (`test_rope_density.py:100`). This leg scales **gaps as `margin`**;
paddings stay in the base rules, fixed.

**Reachability of "gaps" in pure QSS (stated honestly).** Qt QSS can set a
widget's `margin`/`padding` but **cannot** set `QLayout.setSpacing()`. The live
inter-item gaps of these regions live in Python `setSpacing()` calls inside
`synapse_panel.py` (28 px tab row, 24 px verb rail, 18 px token rows) — outside
this leg's `designsystem/`-only territory and unreachable by QSS. So the density
rhythm this leg lands scales the **QSS-reachable outer/group margins** of the
reachable region widgets; the exact composite pixel result (QSS margin + the
residual Python layout spacing) is what the **GUI sign-off (Joe, gui_required)**
arbitrates. Zeroing the Python `setSpacing()` so QSS owns the gap outright is a
one-line-each panel-module follow-up, noted per region.

---

## 4 · The five camera regions — before / after, in order (stop at five)

Colour tokens below are host-seeded (`_derive_palette`, `tokens.py:123-166`) and
named by role, not hex — only `SIGNAL #8FB3D9` / `HOT_SOFT #D08A57` are literal.

### Region 1 — Profile tab strip · `DsTabRow` / `DsPill`
*sec.7: pill toggles, one active in SIGNAL (Setup/Style/Render idiom).*

**Build:** `synapse_panel.py:981 _build_mode_bar()` — one `QHBoxLayout` on
`#DsTabRow` carrying CHAT·TOKEN face pills (left) + CURIOUS·EXPERT·ML profile
pills (right), split by `addStretch`. Same `DsPill` class for both groups.

| | before (Expert ×1, live) | after (sec.7 rhythm) |
|---|---|---|
| row contentsMargins | 30, 24, 30, 0 (Python) | unchanged (Python; GUTTER-aligned) |
| inter-pill gap | `setSpacing(28)` (Python) | **follow-up**: zero it, let QSS own it |
| pill padding | `0 0 12 0` (QSS `qss.py:124`) | fixed (padding — never scales) |
| active marker | 2 px `SIGNAL` underline (`qss.py:129`) | **kept** — underline, *not* a fill (filled pill was retired `qss.py:113-116`; "one active in SIGNAL" = the underline) |
| row group gap (below) | none | **THIS LEG**: `#DsTabRow` `margin-bottom` = `gap(SPACE_MD=16, density)` → tight 12 / std 16 / airy 24 |

**Reachability:** ✅ group gap lands as a density-scaled `margin` on `#DsTabRow`.
The inter-pill 28 px is Python-layout (follow-up). Active-in-SIGNAL already
satisfied by the underline — no change, and **not** reverted to a fill.

### Region 2 — Verb rail · `DsVerb`
*sec.7: EXPLAIN / FIX / OPTIMIZE / BUILD HDA → label style, doubled gaps kept, hairline under the group.*

**Build:** `synapse_panel.py:1804 _build_act()` — `QHBoxLayout` on a `DsSection`
container; verbs are flat mono `#DsVerb` buttons (`qss.py:161`), uppercased,
`TEXT_SECONDARY`. Inter-verb `setSpacing(24)` = `SPACE_LG`, the deliberate
"doubled" rung (L5-21). Container top margin 16 (`synapse_panel.py:1809`).

| | before (Expert ×1, live) | after (sec.7 rhythm) |
|---|---|---|
| label style | flat mono LABEL 11px, `TEXT_SECONDARY`, uppercased | **kept** |
| inter-verb gap | `setSpacing(24)` "doubled" (Python) | **kept doubled**; QSS follow-up to own it |
| verb padding | `2 0` (QSS `qss.py:163`) | fixed |
| group vertical gap | container top 16 (Python) | **THIS LEG**: `#DsVerb` `margin-top`/`margin-bottom` = `gap(SPACE_SM=8, density)` → tight 6 / std 8 / airy 12 |
| hairline under the group | **none today** (container is plain `DsSection`) | **follow-up**: needs a unique objectName on the rail container (a panel-module change) to hang `border-bottom: 1px HAIR` — the idiom exists (`#DsActs`, `qss.py:345`) but on a different region |

**Reachability:** ✅ group breathing lands as density-scaled `#DsVerb` margins.
❌ the group hairline needs a container objectName (panel edit) — follow-up.
The 24 px doubled inter-verb gap is kept as sec.7 requires.

### Region 3 — Recall card (the beat) · **GREENFIELD**
*sec.7: three-band card (header/body/footer, hairlines between); footer carries one text action left + one status pill right; footer pill mirrors `HIT` / `NO HIT` / `UNAVAILABLE` / `BLOCKED` in the label style; never a colour for HIT; `HOT_SOFT` only for BLOCKED.*

**Build:** **does not exist.** No card, and the strings `HIT / NO HIT /
UNAVAILABLE / BLOCKED` appear nowhere in `panel/` or `tests/` (verified). The
only memory-status surface today is `health_strip.py` (a backend cell:
moneta/jsonl/fallback), a different grain from a per-query recall result.

**Target spec (for the build):**

| band | height / pad | radius | hairline |
|---|---|---|---|
| header | 40 (`SPACE_XL`) | card `RADIUS_CARD=10` | 1 px `BORDER` under |
| body | pad 16 (`SPACE_MD`), fixed | — | 1 px `BORDER` under |
| footer | 40 (`SPACE_XL`) | — | — |

- Footer text-action left → `#DsVerb` (`qss.py:161`).
- Footer status pill right → **label style**, `RADIUS_ROUND=999` (pill), padding 6/10:
  - `HIT` → label style, **no colour** (`TEXT_SECONDARY` / `DsBadge` default) — sec.7 explicit "never a colour for HIT".
  - `NO HIT` → label style, quiet (`TEXT_TERTIARY` / `DsBadge[prominence=quiet]`).
  - `UNAVAILABLE` → the honest-UNKNOWN calm grey (`SLATE`, mirroring `health_strip` UNKNOWN → never green).
  - `BLOCKED` → **the only coloured pill**: `HOT_SOFT #D08A57` (already wired as `DsVerb[tone="hot"]`, `qss.py:168`).
- Bands separated by `divider()` / `#DsDivider` 1 px `BORDER` hairlines (`components.py:327`).
- Density: body pad fixed; inter-band gap = `gap(SPACE_SM=8, density)` margins.

**Reachability:** ⛔ the card is a **net-new widget** → violates this leg's
"zero new widgets" + lands outside `designsystem/` territory. The **tokens are
provisioned** (`RADIUS_CARD`, `RADIUS_ROUND`, `HOT_SOFT`, `CONIFEROUS`,
`SPACE_XL`) so the build inherits the rhythm. The build itself is a **held
`spawn`** (see receipt).

### Region 4 — TOKEN face · parameter rows
*sec.7: parameter rows (label · value · bar); UNKNOWN rendered as text in the value column, never a bar at zero.*

**Build:** `face_token.py:444 _kv_block()` — a `QGridLayout` of **label (col0) ·
value (col1)**; there is **no bar/control column**. `hSpacing=18`, `vSpacing=6`,
no fixed column widths, no fixed row height. Rows are styled **inline**
(`setStyleSheet` per `QLabel`) with **no objectNames**.

| | before (live) | after (sec.7 target) |
|---|---|---|
| columns | content-sized label, stretch value (no fixed widths) | label col 128 · value 64 · control fills |
| row gap | `vSpacing(6)` (Python) | row 24, group gap 16, section head 32 |
| UNKNOWN | `set_row` → `"unknown"` text, never 0 (`face_token.py:480-485`) | **already correct** — text in the value column, never a bar at zero |

**Reachability:** ✅ **UNKNOWN-as-text is already honoured** (verified
`face_token.py:480-485`; the `TokenField` viz also stays empty-ground for a
`≤0`/None segment, never a zero-width fill). ❌ the parm-row grid rhythm (fixed
columns, row/section gaps) is **not QSS-reachable**: the rows have no objectNames
and are inline-styled, so QSS descendant rules cannot key on them. Adding
objectNames is a `face_token.py` panel-module change (outside territory) —
**follow-up**. The token scale + `gap()` are ready for it.

### Region 5 — `.hip` ribbon + header status line
*sec.7: one row, label style, the `?` glyph opens docs (08-04 decision).*

**Build:** ribbon `synapse_panel.py:927 _build_context_ribbon()` — one
`QHBoxLayout` on a `DsSection`, single `_ctx_label` (role `label`) + stretch.
Header status `synapse_panel.py:659 _header_status` (role `caption`) sits in the
rail's line-1 (`#DsHeader`).

| | before (Expert ×1, live) | after (sec.7 rhythm) |
|---|---|---|
| ribbon row | one label + stretch (label style) | **kept** — matches "one row, label style" |
| ribbon margins | 30, 8, 16, 8 (Python) | GUTTER-aligned; group gap density-scaled |
| header vertical | `#DsHeader` airy padding `SPACE_XS` (`qss.py:296`) | **THIS LEG**: extend to multiplier — `#DsHeader`/`#DsTabRow`-style `margin` group gaps by density |
| `?` glyph → docs | **none** — a text "Help" button (`synapse_panel.py:727`), in the rail not the ribbon | **follow-up**: the glyph affordance is unbuilt (panel-module change) |

**Reachability:** ✅ the ribbon is already "one row, label style"; header/ribbon
group gaps land as density-scaled `margin`. ❌ the `?` glyph is unbuilt (a text
"Help" button exists instead) — a panel-module follow-up.

---

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

## 6 · Chore (theme-seed-tokens split, sec.5)

`python .synapse/verify.py no-importers python/synapse/panel/tokens.py python/synapse/panel`
→ **does not pass**: legacy `panel/tokens.py` has 8 live importers (apex_recipes,
chat_panel, command_palette, context_bar, error_translator, hda_views,
quick_actions, recipe_book) beyond `styles.py`, and `panel/styles.py` has 3
production importers (chat_display, chat_panel, gate_widget). The delete premise
("only styles.py imports tokens.py and nothing imports styles.py") is **false** →
**leave the pair, name the importers** (bus finding + receipt). Host-scheme
seeding stays parked.

## 7 · Acceptance mapping

| predicate | how met |
|---|---|
| spec exists, px per region, token table, density multipliers | this file (§2–§4) |
| QSS/token diff: no colour token, no hex string | §5.1–2; grep attached at receipt |
| headless: gap tokens step by density multipliers per profile | §3 + the new test (T3) |
| `test_expert_resolved_equals_v5420_snapshot` green + `pytest -q` green | manifests untouched (pin is manifest-only, `test_rope_expert_pin.py:106`) |
| importer chore posted as a bus finding | §6 (leave the pair) |
| GUI sign-off on the five regions (Joe, Thu/Fri) | **gui_required → UNKNOWN** headless; Joe's eyes |

*Crucible pins honoured: no new hex (BROKEN), no new QFont family (BROKEN), no
structural change to the Expert manifest (BROKEN — manifests untouched), paddings
fixed / only gaps scale, no hardcoded pt size (font floor derives from the host,
W5L-PANEL T1 — this pass touches no font size).*
