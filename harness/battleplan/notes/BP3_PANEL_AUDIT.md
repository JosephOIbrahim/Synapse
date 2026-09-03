# BP3-PANEL — Design-system audit of the SYNAPSE Python panel

> **What this is.** The read-only audit (T2) that the BP3-PANEL change set (T3)
> is traceable to, row by row. It inventories every hardcoded design value in
> `python/synapse/panel/` (colors, spacing, typography), names where token names
> disagree with the rhythm spec, ticks component completeness, and ranks the
> fixes by instances-per-edit. Every count is grep-derived with a `file:line`.
>
> **Method.** `scratchpad/audit_scan.py` walks `python/synapse/panel/**/*.py`,
> imports `designsystem/tokens.py` to build the value→token map, and for every
> line flags: hex literals (`#rrggbb` / 3-digit), `rgb()/rgba()` literals, `Npx`,
> `Npt`, `font-size:` occurrences, and `setPointSize/setPixelSize`. A hex is
> `hex_sub` when it exactly equals a defined token value (substitutable) and
> `hex_unique` otherwise (no token — a genuine coverage hole or an off-palette
> colour). Regex-derived, so `{t.SPACE_MD}px` is NOT counted (token already);
> only bare literals are. Numbers below are that scan (2026-09-03, HEAD `master`).
>
> **Referee catch up front (honesty · runtime is truth).** The design system is
> near-complete *inside its own module* (`designsystem/`), and largely *not yet
> adopted* across the wider panel. The change set this leg lands is confined to
> `designsystem/qss.py` (in-territory, byte-identical output — see §Priority
> Actions and the receipt). The much larger legacy + inline-styled surface is
> audited here and handed forward as ranked follow-ups + spawns, exactly as
> BP2-PANELDESIGN deferred the out-of-`designsystem/` regions. No file is claimed
> fixed that is not.

---

## 1 · Summary

**Components reviewed:** the full `python/synapse/panel/` tree — 90 modules, of
which **37 carry at least one hardcoded design value**. The design-system core
(`designsystem/tokens.py`, `designsystem/qss.py`, `designsystem/components.py`)
is the token authority; the remaining 34 are the legacy stylesheet
(`styles.py`) + inline-styled feature/face modules.

**Issue totals (raw scan, all 37 files):**

| category | count | what it is |
|---|---|---|
| hex literals matching a token (`hex_sub`) | **69** | a colour token exists — pure substitution |
| hex literals with NO token (`hex_unique`) | **168** | coverage hole or off-palette colour (incl. 3-digit) |
| `rgb()/rgba()` literals | **18** | mostly `styles.py` alpha washes |
| literal `Npx` | **492** | spacing/radius/dimension not on a token |
| literal `Npt` | **14** | hardcoded point sizes (mostly `context_bar.py`) |
| `font-size:` occurrences | **164** | most token-driven; ~a dozen literal sizes |
| `setPointSize/setPixelSize` | **6** | 5 parameterised, 1 literal |

**Score (evidence-backed, two axes — they diverge sharply):**

- **Design-system core (`designsystem/`): 8.5 / 10.** `qss.py` is ~99 %
  tokenised — one 18 KB generated stylesheet with exactly **5 substitutable
  literals** left (§4). `tokens.py` is a single, well-documented source of truth
  with a solved contrast ramp. `components.py` has zero code-level literals (its
  px hits are all comments/docstrings; `setPixelSize` is parameterised).
- **Panel-wide adoption: 3.5 / 10.** The token table exists but is **not yet
  worn** by the panel: `styles.py` alone holds 127 literal `px` + 39 literal
  font-sizes + 7 rgba washes, and ~30 feature/face modules inline-style HTML/QSS
  with hardcoded hex — including hexes that exactly equal `GROW/WARN/ERROR/
  PANEL/CARBON/BONE`. This is the two-token-system, non-native-fit gap the H22
  design review calls out (`SYNAPSE_PANEL_DESIGN_REVIEW_H22_LENS.md` §2.2).

**Overall:** the design system is *authoritative in its own module and
under-adopted everywhere else.* That is a distribution problem, not a token-table
problem — and the fix is migration (token substitution across modules), not more
tokens. This leg closes the last literals in the authority module; the migration
of the 34 consumer modules is ranked + spawned below.

---

## 2 · Naming Consistency (token names vs the rhythm spec)

Reference: `docs/PANEL_RHYTHM_SPEC.md` §2 (the 4-pt grid token table) and
`designsystem/tokens.py` §5–§6. The spacing/radius ladder **agrees** with the
spec (SPACE_XS/SM/12/MD/LG/32/48/XL and RADIUS_MD/CARD/ROUND/ROW_MIN_H all
present and correctly valued). The disagreements are alias proliferation and
defined-but-unused stops:

| token | issue | evidence | canonical | disposition |
|---|---|---|---|---|
| `SIZE_LABEL` | back-compat alias of `SIZE_MICRO` (both = 10). Two names for one size; **21+ live call sites** prefer the alias over the canonical. | `tokens.py:316` (`SIZE_LABEL = SIZE_MICRO`); consumers: `gate_widget.py` ×11, `styles.py` ×12, `message_formatter.py:42,58`, `context_bar.py:70`, `quick_actions.py:187` | `SIZE_MICRO` (spec §5 names roles, not `LABEL`) | **document only** — canonicalising touches 6+ feature modules (out of territory); [spawn BP3-NAME-CANON] |
| `OK_SOFT` | deprecated alias of `CONIFEROUS`; kept for resolution but **zero live consumers** outside `tokens.py`. | `tokens.py:272` (`OK_SOFT = CONIFEROUS`); grep of `panel/` → none | `CONIFEROUS` | **document only** — already dead; safe to retire in a later cleanup |
| `RADIUS_PILL` (14) | the spec's canonical pill radius is `RADIUS_ROUND` (999, fully-rounded); `RADIUS_PILL=14` is **defined but has zero consumers**. | `tokens.py:488`; grep of `panel/` → none | `RADIUS_ROUND` for pills | **document only** — stale stop; retire with the name-canon spawn |
| legacy `panel/tokens.py` vs `designsystem/tokens.py` | **two token modules** with divergent names (`t.HOVER` in `styles.py`/`quick_actions.py` resolves against the legacy module; `designsystem` uses `HOVER_BG`/`HOVER_WASH`). | `styles.py:7` (`from . import tokens as t`) + `:11` (`from .designsystem import tokens as _ds`); `quick_actions.py:187` `hover=_t.HOVER` | one authority: `designsystem/tokens.py` | **document only** — BP2 ruled "leave the pair" (8+3 live importers, `BP2-PANELDESIGN.md` §Chore); consolidation is a spawn |

**Verdict:** the *rhythm/grid* names are canonical and spec-conformant. The
naming debt is (a) an alias (`SIZE_LABEL`) that out-competes its canonical at the
call sites, and (b) a legacy second token module. Neither is fixable within
`designsystem/`-only territory without editing consumer modules, so both are
documented, not touched, this leg.

---

## 3 · Token Coverage (defined vs hardcoded instances, per file)

Full per-file counts (all 37 files with ≥1 hit), ranked by actionable weight
(`hex_sub + px + rgba + pt + font_size`). `hex_sub`/`hex_uniq`/`rgba`/`px`/`pt`/
`fsz`/`sp` map to the categories in §1.

| file | hex_sub | hex_uniq | rgba | px | pt | fsz | sp | in territory? |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| `styles.py` | 1 | 0 | 7 | 127 | 0 | 39 | 0 | ✗ legacy stylesheet (3 pinned importers) |
| `designsystem/tokens.py` | 30 | 5 | 8 | 19 | 7 | 0 | 0 | ✓ **definition site** (values are source of truth) |
| `designsystem/qss.py` | 0 | 0 | 0 | 38 | 0 | 8 | 0 | ✓ **THIS LEG** (5 substitutable — §4) |
| `hda_views.py` | 0 | 0 | 0 | 24 | 0 | 17 | 0 | ✗ inline HDA views |
| `performance_profiler.py` | 3 | 10 | 1 | 29 | 0 | 5 | 0 | ✗ inline HTML |
| `message_formatter.py` | 5 | 8 | 0 | 13 | 0 | 12 | 0 | ✗ inline HTML |
| `apex_explainer.py` | 2 | 10 | 0 | 20 | 0 | 5 | 0 | ✗ inline HTML |
| `agent_health.py` | 11 | 7 | 0 | 12 | 0 | 1 | 0 | ✗ inline HTML |
| `gate_widget.py` | 0 | 0 | 0 | 12 | 0 | 12 | 0 | ✗ inline QSS |
| `save_shot.py` | 2 | 12 | 0 | 17 | 0 | 4 | 0 | ✗ inline QSS |
| `render_preflight.py` | 0 | 11 | 0 | 16 | 0 | 6 | 0 | ✗ inline QSS |
| `vex_tutor.py` | 1 | 14 | 0 | 16 | 0 | 5 | 0 | ✗ inline HTML |
| `context_bar.py` | 0 | 4 | 0 | 6 | 7 | 7 | 0 | ✗ inline QSS + literal `pt` |
| `bookmarks.py` | 1 | 9 | 0 | 14 | 0 | 4 | 0 | ✗ inline QSS |
| `apex_trace.py` | 1 | 20 | 0 | 16 | 0 | 0 | 0 | ✗ inline HTML |
| `dependency_map.py` | 0 | 12 | 0 | 15 | 0 | 1 | 0 | ✗ inline HTML |
| `face_review.py` | 0 | 0 | 0 | 13 | 0 | 2 | 1 | ✗ face module |
| `synapse_panel.py` | 0 | 0 | 0 | 13 | 0 | 2 | 0 | ⚠ layout module — lifecycle/timer ranges untouchable |
| `face_token.py` | 6 | 3 | 0 | 5 | 0 | 3 | 0 | ✗ inline-styled rows (BP2 follow-up) |
| `chat_display.py` | 0 | 0 | 0 | 11 | 0 | 2 | 1 | ✗ face module |
| `command_palette.py` | 3 | 2 | 1 | 9 | 0 | 0 | 0 | ✗ inline QSS |
| `quick_actions.py` | 0 | 0 | 1 | 9 | 0 | 2 | 0 | ✗ inline QSS |
| `cross_scene.py` | 0 | 11 | 0 | 9 | 0 | 2 | 0 | ✗ inline HTML |
| `error_translator.py` | 0 | 1 | 0 | 8 | 0 | 3 | 0 | ✗ inline HTML |
| `recipe_book.py` | 0 | 2 | 0 | 0 | 0 | 11 | 0 | ✗ inline QSS |
| `apex_recipes.py` | 1 | 2 | 0 | 0 | 0 | 7 | 0 | ✗ inline HTML |
| `network_trace.py` | 0 | 14 | 0 | 5 | 0 | 0 | 0 | ✗ inline HTML |
| `scene_doctor.py` | 0 | 8 | 0 | 3 | 0 | 2 | 0 | ✗ inline HTML |
| `designsystem/components.py` | 0 | 0 | 0 | 3 | 0 | 0 | 1 | ✓ core — hits are comments/parameterised (no code literal) |
| `session_journal.py` | 0 | 2 | 0 | 2 | 0 | 1 | 0 | ✗ inline |
| `face_work.py` | 0 | 0 | 0 | 2 | 0 | 0 | 0 | ✗ face module |
| `integrity_readout.py` | 0 | 0 | 0 | 2 | 0 | 0 | 0 | ✗ inline |
| `session_integrity.py` | 2 | 1 | 0 | 0 | 0 | 0 | 0 | ✗ inline |
| `voice_contract.py` | 0 | 0 | 0 | 2 | 0 | 0 | 0 | ✗ inline |
| `chat_panel.py` | 0 | 0 | 0 | 1 | 0 | 0 | 1 | ✗ face module |
| `health_strip.py` | 0 | 0 | 0 | 0 | 0 | 1 | 0 | ✗ inline |
| `tool_palette.py` | 0 | 0 | 0 | 1 | 0 | 0 | 0 | ✗ inline |

### 3a · Colors

- **`designsystem/tokens.py`** is the authority (§1 palette, §4 interaction ramp,
  §8 status grammar). Its 30 `hex_sub` are alias/`PALETTE`-dict re-references
  (`OK_SOFT`, the `PALETTE` map) and its 5 `hex_unique` are unique brand hexes
  (`SIGNAL #8FB3D9`, `WARM #FF7759`, etc.) — **definitions, not instances to
  fix.** (The H22 review flags these `.hcs`-matched hexes as an *architecture*
  concern — seed from `hou.qt.color()` — which is a behaviour change, out of
  this leg's scope.)
- **Inline hardcoded token-equal hexes (coverage holes):** the clearest are
  `agent_health.py:177` `"#00E676"/"#FFAB00"/"#FF3D71"` (== `GROW/WARN/ERROR`),
  `performance_profiler.py:352,387` `#2a2a2a/#1a1a1a` (== `PANEL/CARBON`),
  `apex_explainer.py:825,835` `#2a2a2a/#cccccc` (== `PANEL/BONE`). 69 such
  substitutable hexes total — every one is `hardcoded → existing token`, but
  **all live outside `designsystem/`** (feature modules).
- **Off-palette hexes (168):** genuinely no token — `apex_explainer.py:806,819`
  `#cc6666/#7799cc`, `agent_health.py:180` `#AAAAAA`, `performance_profiler.py:343`
  `#aaa`, `message_formatter.py:141` `&#160;/&#183;` (HTML entities, false
  positives). These are the "second colour authority" the H22 review warns grows
  when widgets paint their own hex (§2.2). Migration target, not a substitution.

### 3b · Spacing

- **In-territory (`designsystem/qss.py`):** 38 literal `px`. Most are **fixed 1px
  hairlines** (`qss.py:39,43,53,61,66,70,119,147,206,231,377,388` — the rhythm
  spec's "hairline 1px, never 2px" constant; no numeric width token exists) and
  **intentional off-grid comp paddings** (`DsSend 9/15` `:244`, `DsInput 16/15`
  `:232`, `DsKHint 3/7` `:148`, `DsChip 3/8/7` `:187`) that the density block
  comment (`qss.py:287`) explicitly protects from stepping. **5 are cleanly
  substitutable to an existing token** — see §4.
- **Out of territory:** 492 literal `px` panel-wide, concentrated in `styles.py`
  (127) and the inline modules. Many equal `SPACE_*`/`RADIUS_*` values
  (`styles.py:27` `border-radius: 4px` = `RADIUS_SM`, `:28` `padding: 12px` =
  `SPACE_12`) — substitution targets for the migration spawn.

### 3c · Typography

- **In-territory:** `designsystem/qss.py` has **2 literal font sizes** —
  `qss.py:164` `{s(11)}px` and `qss.py:188` `{s(10)}px` — where `SIZE_SMALL`
  (11) and `SIZE_MICRO` (10) exist. Fixed in §4. The other 6 `font-size:` lines
  in qss.py already read `{s(t.SIZE_*)}`.
- **Out of territory:** 164 `font-size:` occurrences panel-wide; ~a dozen are
  literal (e.g. `performance_profiler.py:348` `font-size:13px`), the rest
  token-driven. **14 literal `pt`** sizes, all in `context_bar.py` (`:` QFont
  point sizes) — a hardcoded-pt hotspot the font-floor work (`W5L-PANEL`) never
  reached. Migration target.

---

## 4 · The change set this leg lands (in-territory, byte-identical)

`designsystem/qss.py` only. Each row is `hardcoded value → existing token`, and
because every token's value equals the literal it replaces, the **rendered
stylesheet string is byte-for-byte identical at every font scale** (proof: the
sha256 of `qss.stylesheet(scale)` is unchanged for scale ∈ {1.0, 1.15, 1.25,
1.4, 1.6} — receipt evidence). Zero visual/behaviour change; pure token coverage.

| # | line (before) | literal | → token | value check |
|---|---|---|---|---|
| A | `:124` `padding: 0 0 12px 0;` (DsPill) | `12px` | `{t.SPACE_12}px` | 12 == `SPACE_12` |
| B | `:164` `font-size: {s(11)}px;` (DsVerb) | `11` | `{s(t.SIZE_SMALL)}` | 11 == `SIZE_SMALL` |
| C | `:188` `font-size: {s(10)}px;` (DsChip) | `10` | `{s(t.SIZE_MICRO)}` | 10 == `SIZE_MICRO` |
| D | `:232` `padding: 16px 15px;` (DsInput/DsField) | `16px` | `{t.SPACE_MD}px 15px` | 16 == `SPACE_MD` (15 left: off-grid comp value) |
| E | `:382` `min-height: 24px;` (DsScrollBar handle) | `24px` | `{t.SPACE_LG}px` | 24 == `SPACE_LG` |

**Explicitly NOT changed (documented, out of the safe envelope):**
- 1px hairlines (no width token — inventing one is a NEW token, outside T3's
  "existing token" rule; candidate for a `HAIRLINE`/`BORDER_PX` additive token,
  see spawn).
- `DsSend 9/15`, `DsInput 15`, `DsKHint 3/7`, `DsChip 3/8/7`, radius `2px`/`0px`
  — intentional off-grid comp paddings/radii; `qss.py:287` protects them from
  stepping, and snapping them would change ratified paint (a visual change).
- Everything in `styles.py` + the 34 consumer modules — out of `designsystem/`
  territory + (for `styles.py`) 3 pinned importers.

---

## 5 · Component Completeness (design-system widget classes)

Every `#Ds*` class the QSS authority styles, with its states / variants / doc
tick. "docs" = has an explanatory comment block in `qss.py`.

| component | variants | states | prominence | docs | note |
|---|---|---|---|:--:|---|
| `DsButton` (`qss.py:48`) | primary/secondary/ghost/danger | hover/pressed/disabled | hero/quiet | ✓ | complete |
| `DsStop` (`:103`) | — (mark's 2nd surface) | hover/pressed/disabled | — | ✓ | complete |
| `DsPill` (`:121`) | — | hover/disabled/active | — | ✓ | underline-active (filled retired) |
| `DsAuthor` (`:135`) | — | hover | — | ✓ | engine·model click target |
| `DsMeter` (`:144`) | — | — | hero/quiet | ✓ | token meter |
| `DsKHint` (`:145`) | — | — | hero/quiet | ✓ | ⌘K chip |
| `DsVerb` (`:161`) | tone ok/hot/accent | hover | hero/quiet | ✓ | type-set verbs |
| `DsChip` (`:184`) | — | hover/active | — | ✓ | two-axis palette cell |
| `DsList` (`:197`) | — | item/selected | — | ✓ | command palette |
| `DsCard` (`:205`) | tone warn/approve/critical | — | — | ✓ | complete |
| `DsBadge` (`:214`) | kind grow/warn/error/signal | — | hero/quiet | ✓ | complete |
| `DsInput`/`DsField` (`:229`) | — | focus | — | ✓ | field-inset |
| `DsSend` (`:241`) | — | hover/pressed/disabled | — | ✓ | embedded composer send |
| `DsProgress` (`:351`) | — | ::chunk | — | ✓ | complete |
| `DsCookBar` (`:358`) | — | ::chunk | — | ✓ | complete |
| `DsRailMeter` (`:365`) | busy | — | hero | ✓ | observe strip |
| `DsActs` (`:375`) | — | — | — | ✓ | acts row (HAIR top rule) |
| `role` labels (`:251`) | title/body/caption/label/accent | — | hero/quiet | ✓ | font set in Python from `TYPE_ROLES` |

**Gaps:** (a) `DsTabRow`/`DsHeader` group-hairline + `?`-glyph affordance are
BP2 follow-ups (`PANEL_RHYTHM_SPEC.md` §4 Regions 2/5), not styling holes. (b)
The recall card (`DsCard` three-band variant, Region 3) is greenfield — a held
spawn from BP2, tokens already provisioned. Component coverage of the *styled*
surface is otherwise complete; the completeness debt is **adoption** (feature
modules bypass these classes with inline HTML/QSS), not missing variants.

---

## 6 · Priority Actions (ranked by instances fixed per edit)

1. **[THIS LEG] Close the last literals in `designsystem/qss.py`** — 5
   substitutions (§4), byte-identical output. *Fixes 5 instances in the authority
   module; brings qss.py to 100 % token coverage for substitutable values.*
2. **[spawn BP3-STYLES-MIGRATE] Migrate `styles.py` literals to tokens** — 127
   `px` + 39 font-sizes + 7 rgba. Highest raw yield, but legacy module with 3
   pinned importers (`chat_display`, `chat_panel`, `gate_widget`); the durable
   fix is migrating those consumers onto `designsystem/qss.py` objectNames, not
   editing the legacy sheet. *~173 instances.*
3. **[spawn BP3-INLINE-HEX] Replace token-equal inline hexes across feature
   modules** — 69 `hex_sub` (e.g. `agent_health.py:177` `GROW/WARN/ERROR`,
   `performance_profiler.py:352` `PANEL`). Pure substitutions, but each module is
   inline-styled HTML/QSS (out of `designsystem/`). *~69 instances, high
   confidence.*
4. **[spawn BP3-NAME-CANON] Canonicalise `SIZE_LABEL`→`SIZE_MICRO`, retire
   `OK_SOFT`/`RADIUS_PILL`** — 21+ call sites, mechanical but cross-module. *~24
   references.*
5. **[spawn BP3-PT-HOTSPOT] De-hardcode the 14 literal `pt` sizes in
   `context_bar.py`** — the font-floor migration (`W5L-PANEL`) never reached this
   module. *14 instances.*
6. **[candidate additive token] `HAIRLINE`/`BORDER_PX = 1`** — enforce the spec's
   "hairline 1px, never 2px" in one place (8+ sites in qss.py). *Deferred: adding
   a token is outside T3's "existing token" rule; belongs to a rhythm-extension
   leg like BP2.*

**Off-palette colours (168 `hex_unique`)** are a separate, non-mechanical
workstream (they need a design decision per colour: map to a token or add one) —
tracked, not ranked as a substitution.

---

## 7 · Acceptance mapping

| predicate | how met |
|---|---|
| audit exists in the audit shape with file:line per token category | this file (§1 summary/score, §2 naming, §3 token coverage w/ file:line, §5 completeness, §6 priority actions) |
| diff touches only designsystem/manifests/qss/layout files; synapse_panel.py lifecycle/timer ranges unchanged | change set = `designsystem/qss.py` ONLY (§4); `synapse_panel.py` untouched (`git diff` in receipt) |
| panel test target green before and after | `pytest tests/panel + rope/design guards` = 123 passed / 25 skipped before; re-run after (receipt) |
| before/after screenshots show only spacing/typography/colour-token changes | **gui_required → UNKNOWN** headless; byte-identical stylesheet ⇒ screenshots are provably identical (no visual delta) — the substitutions cannot move a pixel. Live capture steps for Joe in the receipt. |

*Crucible map (each diff hunk → audit row): A→§4.A / B→§4.B / C→§4.C / D→§4.D /
E→§4.E. Mutations that must redden: re-introduce `12px`/`s(11)`/`s(10)`/`16px`/
`24px` → the removed-literal count regresses; add a QWidget subclass/new signal →
whitespace-only checker; touch a `synapse_panel.py` timer range → red (that file
is not in the diff at all).*
