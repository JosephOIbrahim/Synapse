# BP4-PANELFONT — Typography audit of the SYNAPSE Python panel

> **What this is.** The read-only typography audit (T2) the BP4-PANELFONT change
> set (T3/T4) is traceable to, row by row. It inventories every hardcoded
> `font-family` / `font-size` / `font-weight` / `line-height` occurrence in
> `python/synapse/panel/` (grep, `file:line`), names the existing typography
> tokens, records the Houdini default UI-font **floor with its provenance**
> (measured | DOC-STATED | UNKNOWN), and ranks the fixes. It is the typography
> companion to `BP3_PANEL_AUDIT.md` (which covered colour + spacing).
>
> **Method.** A scan walks `python/synapse/panel/**/*.py` and counts, per file,
> `font-size` / `font-family` / `font-weight` / `line-height` / literal `Npt` /
> `setPointSize|setPixelSize`. Numbers below are that scan (2026-09-03, branch
> `bp4/panelfont` at `master` 28a0e18). Every count has a producer path; the
> change-set rows carry exact `file:line`.
>
> **Referee catch up front (honesty · runtime is truth).** The panel's typography
> **tokens already exist and are well-formed** (`designsystem/tokens.py` §5: one
> sans family, one mono family, a 5-size role scale, tracking). The gap is the
> same two-axis story BP3 found for colour: the **authority module is ~complete
> and the wider panel has not adopted it** — 167 `font-size`, 88 `font-family`,
> 33 `font-weight` literals still live in `styles.py` + ~30 inline-styled feature
> modules. This leg lands the *authority-side* typography contract (weight tokens,
> the floor constant, the pinning test, the GUI probe) inside its own diff surface
> (`designsystem / manifests / qss / layout / scripts` only) and hands the
> cross-module migration forward as spawns — exactly as BP3-PANEL deferred the hex
> migration. **No file is claimed clean that is not.**

---

## 1 · Summary

**Components reviewed:** the full `python/synapse/panel/` tree — 90 modules, of
which **32 carry at least one hardcoded typography value**. The typography
authority is `designsystem/tokens.py` (families + scale + roles) rendered through
`designsystem/qss.py` and applied via `designsystem/fontload.py` /
`components.py`.

**Issue totals (raw scan, all modules):**

| category | count | what it is |
|---|---:|---|
| `font-size` occurrences | **167** | most out-of-territory literals; the in-territory ones are token refs |
| `font-family` occurrences | **88** | 87 out-of-territory literals (`'…', Consolas, monospace` / `sans-serif`), 1 in-territory comment |
| `font-weight` occurrences | **33** | `bold` / `700` / `600` literals in feature modules; 3 in-territory (now tokens) |
| `line-height` occurrences | **13** | inline `1.6` / `1.8` / `150%` — **inert** in Qt's QTextDocument HTML subset (see §3d) |
| literal `Npt` | **15** | 7 real QFont point sizes in `context_bar.py`; 8 are `tokens.py` leading-comment refs (not UI sizes) |
| `setPointSize` / `setPixelSize` | **6** | all **parameterised** (a computed px, never a literal) |

**Score (evidence-backed, two axes — they diverge, as BP3 found for colour):**

- **Typography authority (`designsystem/`): 9 / 10.** After this leg,
  `qss.py` has **zero literal typography** — its 8 `font-size` and 3
  `font-weight` are all token references (`{s(t.SIZE_*)}` / `{t.WEIGHT_SEMIBOLD}`);
  no `font-family` (the root inherits Houdini's native UI font by design,
  `qss.py:21`). `tokens.py` is one source of truth: 2 families, a 5-size role
  scale, 3 weight tokens, tracking, leading, **and now the type floor**.
- **Panel-wide adoption: 3 / 10.** The scale exists but is **not worn** by the
  panel: `styles.py` alone holds 40 `font-size` + 36 `font-family` + 11
  `font-weight` literals, and ~30 feature modules inline-style HTML/QSS with
  hardcoded families/sizes — including `context_bar.py`'s 7 literal `9pt` QFont
  sizes, the pt hotspot `W5L-PANEL` never reached.

**Overall:** the typography system is *authoritative in its own module and
under-adopted everywhere else* — a distribution problem, not a token-table
problem. This leg closes the authority side (weights → tokens, the floor
constant, the invariant test) and provisions the migration; the 30-module
adoption is ranked + spawned in §7.

---

## 2 · Naming consistency (typography token names)

Reference: `docs/PANEL_RHYTHM_SPEC.md` (adds *rhythm*, explicitly "zero new font
families") and `designsystem/tokens.py` §5. The scale is **role-named and
spec-conformant**; the debt is one alias.

| token | issue | evidence | canonical | disposition |
|---|---|---|---|---|
| `SIZE_LABEL` | back-compat alias of `SIZE_MICRO` (both = 10). Two names for one size; 21+ live call sites prefer the alias. | `tokens.py` (`SIZE_LABEL = SIZE_MICRO`); consumers in `gate_widget.py`, `styles.py`, `message_formatter.py`, `context_bar.py`, `quick_actions.py` | `SIZE_MICRO` | **document only** — canonicalising touches feature modules (out of territory); folded into `[spawn BP3-NAME-CANON]` |
| role scale | `TYPE_ROLES` names roles (display/title/body/label/code/caption/status), not sizes — spec-correct. | `tokens.py` `TYPE_ROLES` | — | no change |
| weight names | before this leg, weights were **bare ints** (`600`/`500`/`400`) inline in `TYPE_ROLES` and `qss.py`. | `qss.py:52,107,216`; `tokens.py` `TYPE_ROLES` | `WEIGHT_REGULAR/MEDIUM/SEMIBOLD` | **THIS LEG** — added + adopted (§5) |

**Verdict:** the role/scale names are canonical. The only naming debt is the
`SIZE_LABEL` alias, which cannot be retired without editing feature modules
(out of territory) — documented, folded into the existing name-canon spawn.

---

## 3 · Token coverage (typography literals per file)

Full per-file counts (32 files with ≥1 hit), ranked by actionable weight
(`font-size + font-family + font-weight + line-height + pt`). **IN** = inside
this leg's diff surface (`designsystem / manifests / synapse_panel.py /
scripts`); **out** = held/named spawn surface.

| file | fsz | ffam | fwt | flh | pt | sps | territory |
|---|--:|--:|--:|--:|--:|--:|---|
| `styles.py` | 40 | 36 | 11 | 0 | 0 | 0 | out — legacy stylesheet (3 pinned importers) |
| `hda_views.py` | 17 | 12 | 4 | 0 | 0 | 0 | out — inline QSS |
| `gate_widget.py` | 12 | 8 | 4 | 0 | 0 | 0 | out — inline QSS |
| `message_formatter.py` | 12 | 5 | 0 | 5 | 0 | 0 | out — inline HTML |
| `context_bar.py` | 7 | 7 | 0 | 0 | **7** | 0 | out — inline QSS + **literal `9pt`** hotspot |
| `recipe_book.py` | 11 | 3 | 0 | 3 | 0 | 0 | out — inline HTML |
| **`designsystem/qss.py`** | **8** | 1† | **3** | 0 | 0 | 0 | **IN — all token refs after this leg** (†1 comment) |
| `apex_recipes.py` | 7 | 2 | 0 | 2 | 0 | 0 | out — inline HTML |
| `render_preflight.py` | 6 | 1 | 2 | 0 | 0 | 0 | out — inline QSS |
| **`designsystem/tokens.py`** | 0 | 0 | 0 | 1‡ | 8‡ | 0 | **IN — definition site** (‡leading-comment refs, not UI sizes) |
| `apex_explainer.py` | 5 | 1 | 1 | 0 | 0 | 0 | out — inline HTML |
| `performance_profiler.py` | 5 | 1 | 0 | 0 | 0 | 0 | out — inline HTML |
| `vex_tutor.py` | 5 | 1 | 0 | 0 | 0 | 0 | out — inline HTML |
| `save_shot.py` | 4 | 0 | 2 | 0 | 0 | 0 | out — inline QSS |
| `bookmarks.py` | 4 | 0 | 1 | 0 | 0 | 0 | out — inline QSS |
| **`synapse_panel.py`** | 4 | 0 | 0 | 0 | 0 | 0 | **IN — layout; all 4 are dynamic `%dpx`, no literal** |
| `scene_doctor.py` | 2 | 1 | 3 | 0 | 0 | 0 | out — inline HTML |
| `error_translator.py` | 3 | 1 | 1 | 0 | 0 | 0 | out — inline HTML |
| `chat_display.py` | 2 | 1 | 1 | 2 | 0 | 1 | out — face module |
| `face_token.py` | 3 | 0 | 0 | 0 | 0 | 0 | out — inline-styled rows |
| `apex_trace.py` | 0 | 2 | 0 | 0 | 0 | 0 | out — inline HTML |
| `cross_scene.py` | 2 | 0 | 0 | 0 | 0 | 0 | out — inline HTML |
| `quick_actions.py` | 2 | 1 | 0 | 0 | 0 | 0 | out — inline QSS |
| `dependency_map.py` | 1 | 1 | 0 | 0 | 0 | 0 | out — inline HTML |
| `health_strip.py` | 1 | 1 | 0 | 0 | 0 | 0 | out — inline |
| `session_journal.py` | 1 | 1 | 0 | 0 | 0 | 0 | out — inline |
| `agent_health.py` | 1 | 0 | 0 | 0 | 0 | 0 | out — inline HTML |
| `face_review.py` | 2 | 1 | 0 | 0 | 0 | 1 | out — face module |
| `chat_panel.py` | 0 | 0 | 0 | 0 | 0 | 1 | out — parameterised setPixelSize |
| `health_infographic.py` | 0 | 0 | 0 | 0 | 0 | 1 | out — parameterised setPixelSize |
| **`designsystem/components.py`** | 0 | 0 | 0 | 0 | 0 | 1 | **IN — parameterised** `setPixelSize(t.scaled(size,scale))` |
| **`designsystem/fontload.py`** | 0 | 0 | 0 | 0 | 0 | 1 | **IN — parameterised** `setPixelSize(spx)` |

### 3a · Families

- **Authority (`designsystem/tokens.py`):** `FONT_SANS = "Space Grotesk"` (+ `DM
  Sans, Segoe UI, sans-serif` fallbacks, `FONT_SANS_CSS`) and `FONT_MONO = "Space
  Mono"` (+ `JetBrains Mono, Consolas, monospace`, `FONT_MONO_CSS`), loaded into
  `QFontDatabase` at panel init (`fontload.py`). The root deliberately sets **no**
  `font-family` — it inherits Houdini's native UI font (`qss.py:21`). Families
  land via `QFont` only, never QSS.
- **One family token — provenance stated.** The panel's **majority UI family** is
  the tokenised `FONT_SANS` (Space Grotesk); mono (`FONT_MONO`) is the second,
  code/status-only family. The **measured** Houdini family is **UNKNOWN** headless
  (see §4) — the family question is the same GUI-only fact as the size floor.
  This leg does **not** change any family value (substitution only, no visual
  change). A near-duplicate exists: `fontload.py` holds its own `_SANS_CHAIN` /
  `_MONO_CHAIN` tuples that restate the token family names — a single-source
  cleanup, noted as a spawn (§7), not touched (it is the ratified v9 apply layer).
- **Out-of-territory family literals (87):** `styles.py` ×36, `hda_views.py` ×12,
  `gate_widget.py` ×8 (`'{mono}', 'Consolas', monospace`), `context_bar.py` ×7,
  `message_formatter.py` ×5, etc. Migration target, not a substitution this leg.

### 3b · Sizes (the type scale)

- **Authority scale (`tokens.py` §5):** `SIZE_MICRO 10 · SIZE_SMALL 11 · SIZE_UI
  12 · SIZE_BODY 12 · SIZE_TITLE 15 · SIZE_HERO 19` = **5 distinct sizes**
  (`SIZE_LABEL` aliases `SIZE_MICRO`). Already ≤ 5, role-named — mission-conformant.
  Every size is `≥` the floor (§4). All 8 `font-size` in `qss.py` read
  `{s(t.SIZE_*)}`.
- **In-territory layout (`synapse_panel.py`):** the 4 `font-size` hits are the
  **dynamic** chat-input override `font-size: %dpx` (`:1837`, `:2090`, driven by
  the Aa font-scale) + 2 comments — **no literal**, so the sensitive layout module
  (BP2-CRUX: lifecycle/timer ranges untouchable) is **left untouched**.
- **Out-of-territory literals (~a dozen + 7 pt):** e.g. `gate_widget.py:182`
  `font-size:{sz}px` (sz literal), `hda_views.py:72,89,96` `font-size: 11px`,
  `:168` `14px`, `:202` `10px`, `performance_profiler.py:348` `font-size:13px`,
  `render_preflight.py:877` `13px`, and **`context_bar.py:364` `font-size: 9pt`**
  (+ 6 more literal `pt`). Migration target.

### 3c · Weights

- **THIS LEG:** `WEIGHT_REGULAR 400 · WEIGHT_MEDIUM 500 · WEIGHT_SEMIBOLD 600`
  added to `tokens.py`; `TYPE_ROLES` now reads them (was bare `400/500/600`); the
  3 `qss.py` literals (`:52`, `:107`, `:216` `font-weight: 600`) now read
  `{t.WEIGHT_SEMIBOLD}`. Values unchanged ⇒ byte-identical output (§5).
- **Out of territory (30 literals):** `styles.py` ×11, `hda_views.py` ×4,
  `gate_widget.py` ×4 (`font-weight: 700`), `scene_doctor.py` ×3, etc. — `bold` /
  `700` / `600` inline. Migration target.

### 3d · Line-height

- **13 occurrences, all out of territory, and all inert.** `message_formatter.py`
  (`line-height:150%`, ×5), `recipe_book.py` / `apex_recipes.py` (`1.6` / `1.8`,
  ×5) are inside `QLabel`/`QTextBrowser` HTML. The panel's own measurement:
  **Qt's QTextDocument HTML subset does not implement CSS `line-height`**
  (`chat_display.py:42`, `message_formatter.py:45`). The functional line-spacing
  token is `tokens.CHAT_LEADING_PT` (0.75pt → 1.0px via `chat_leading_px()`),
  applied as a `QTextBlockFormat` leading — the one mechanism that survives the
  subset. **So there is no in-territory line-height literal to tokenise, and
  inventing per-role CSS `line-height` tokens would be dead (inert) tokens** —
  against the "runtime is truth / no dead tokens" rule. Line-height is therefore
  represented by the leading token; the inline `line-height` strings in feature
  modules are documented as best-effort/inert (migration cleanup, not a size fix).

---

## 4 · The floor — Houdini default UI font size (provenance: **UNKNOWN**)

Joe's law: *"panel fonts consistent and no smaller than the Houdini default."*
The floor is **the MEASURED Houdini default**, never recalled. Ladder:
**measured GUI paste > H22 help-cache statement (DOC-STATED) > UNKNOWN.**

| step | result | evidence |
|---|---|---|
| measured (GUI) | **not yet** | `QApplication.font()` is meaningless under hython (no Qt app). The measurement seam is `python/synapse/panel/scripts/probe_ui_font.py` — Joe pastes its printout from the Houdini 22.0.400 Python Shell (`gui_required`). Until then: **UNKNOWN**. |
| DOC-STATED (H22 cache) | **absent** | The local H22.0.400 help cache (`…/houdini22.0/config/Help/cache`, `ref` + `basics` + `hom` searched 2026-09-03) states **no** default UI font size. The only `font` hits are node docs (Font COP, MOPS Typography) and the help template's own CSS — not a preferences statement. |
| H21 recall (NOT used) | 9pt ≈ 12px | `tokens.py` §5 comment records "matched 9pt ≈ 12px, verified on H21.0.671/.729". This is an **H21 measurement**, deliberately **not** used as the H22 floor (the mission is emphatic: measure, never recall). |

**Verdict: floor = UNKNOWN → `FONT_FLOOR_PX = 10`** (the smallest size shipped on
master, `SIZE_MICRO`), per the mission fallback: *"if the cache states nothing,
the floor is UNKNOWN and the change set makes no size smaller than the smallest
size already shipped on master."* **So this pass lowers nothing** — every role
keeps its size and the stylesheet is byte-identical (§5). The floor lives as
**one constant with a provenance string** (`tokens.FONT_FLOOR_PX` +
`FONT_FLOOR_PROVENANCE`). When Joe pastes the probe, a follow-up raises the floor
to the measured px and lifts any sub-floor role (`SIZE_MICRO 10` / `SIZE_SMALL
11` are the candidates if the measured default is 12).

> Because a `gui_required` acceptance cannot be measured headless, and the floor
> is UNKNOWN, this leg is **at best SOUND-WITH-NITS, never SOUND** (crucible
> criterion) — recorded honestly, not papered over.

---

## 5 · The change set this leg lands (in-territory, byte-identical)

`designsystem/tokens.py` + `designsystem/qss.py` + the new probe + the new test.
Each hunk is `hardcoded value → token` or `additive constant`; because every new
token equals the literal it replaces (weights) and no size is raised (floor
UNKNOWN), the **rendered stylesheet is byte-for-byte identical at every font
scale** (sha256 of `qss.stylesheet(scale)` unchanged for scale ∈ {1.0, 1.15,
1.25, 1.4, 1.6} — receipt evidence: `1779b114… 7a1a99e7… e7d4298e… be8d2aaa…
c99024cd…`, before == after).

| # | file:line (before) | literal | → token / add | value check |
|---|---|---|---|---|
| A | `tokens.py` §5 (new) | — | `FONT_FLOOR_PX = 10` + `FONT_FLOOR_PROVENANCE` (UNKNOWN) | floor = smallest shipped size (`SIZE_MICRO`) |
| B | `tokens.py` §5 (new) | — | `WEIGHT_REGULAR/MEDIUM/SEMIBOLD = 400/500/600` | the 3 weights the panel uses |
| C | `tokens.py` `TYPE_ROLES` | `600`/`500`/`400` (bare ints) | `WEIGHT_SEMIBOLD`/`WEIGHT_MEDIUM`/`WEIGHT_REGULAR` | same ints, single source |
| D | `qss.py:52` (DsButton) | `font-weight: 600` | `font-weight: {t.WEIGHT_SEMIBOLD}` | renders `600` |
| E | `qss.py:107` (DsStop) | `font-weight: 600` | `font-weight: {t.WEIGHT_SEMIBOLD}` | renders `600` |
| F | `qss.py:216` (DsBadge) | `font-weight: 600` | `font-weight: {t.WEIGHT_SEMIBOLD}` | renders `600` |
| G | `scripts/probe_ui_font.py` (new) | — | GUI floor-measurement seam (read-only) | family/pointSize/pixelSize/scaledSize(1) |
| H | `tests/test_panel_typography.py` (new) | — | pins: no literal typo in qss; no size < floor; weights are tokens; scale ≤ 5 | crucible mutations redden |

**Explicitly NOT changed (documented, out of the safe envelope):**
- **Family values** — no family is switched (would be a visual change). The
  "one family token" question resolves to the existing `FONT_SANS` (majority) +
  `FONT_MONO` (code); the measured-Houdini-family option is UNKNOWN (§4).
- **`synapse_panel.py`** — its 4 `font-size` hits are dynamic `%dpx` / comments;
  no literal, and BP2-CRUX puts lifecycle/timer ranges off-limits. **Untouched.**
- **`fontload.py` `_SANS_CHAIN` / `_MONO_CHAIN`** — restate the family names, but
  are the ratified v9 QFont apply layer; single-sourcing them onto `tokens.FONT_*`
  is behaviour-adjacent → spawn, not this leg.
- **All of `styles.py` + the ~30 feature modules** — out of the diff surface;
  held/named spawns (§7).

---

## 6 · Component completeness (type roles)

Every role the authority defines, its family, size, weight, tracking. "applied"
= reachable via `components.apply_font_role` / `fontload.tracked_font`.

| role | family | size (px) | weight | tracking | applied |
|---|---|--:|--:|---|:--:|
| `display` | sans | 19 (`SIZE_HERO`) | `WEIGHT_SEMIBOLD` | 0.5 | ✓ |
| `title` | sans | 15 (`SIZE_TITLE`) | `WEIGHT_SEMIBOLD` | 1.0 | ✓ |
| `body` | sans | 12 (`SIZE_BODY`) | `WEIGHT_REGULAR` | 0.0 | ✓ |
| `label` | sans | 12 (`SIZE_UI`) | `WEIGHT_MEDIUM` | 0.5 | ✓ |
| `code` | mono | 12 (`SIZE_BODY`) | `WEIGHT_REGULAR` | 0.0 | ✓ |
| `caption` | sans | 11 (`SIZE_SMALL`) | `WEIGHT_REGULAR` | 0.0 | ✓ |
| `status` | mono | 11 (`SIZE_SMALL`) | `WEIGHT_MEDIUM` | 0.5 | ✓ |

**Gaps:** none in the role set — 7 roles, 2 families, ≤5 sizes, 3 weights, all
applied. The completeness debt is **adoption**: feature modules bypass
`apply_font_role` with inline HTML/QSS (§3, §7).

---

## 7 · Priority actions (ranked by instances fixed per edit)

1. **[THIS LEG] Authority typography contract** — weight tokens + floor constant
   + probe + the pinning test; `qss.py` to 100 % token typography. *Byte-identical;
   makes the floor rule and the no-literal rule enforceable.*
2. **[gui, Joe] Measure the floor** — paste `scripts/probe_ui_font.py` output
   (§8). Flips the floor UNKNOWN → measured; unblocks the sub-floor lift.
3. **[spawn BP4-STYLES-TYPO / folds into BP3-STYLES-MIGRATE] `styles.py`
   typography** — 40 `font-size` + 36 `font-family` + 11 `font-weight`. Highest
   raw yield; legacy sheet with 3 pinned importers — the durable fix migrates
   consumers onto `qss.py` objectNames. *~87 instances.*
4. **[spawn BP4-INLINE-TYPO] Feature-module inline typography** — the ~28 inline
   HTML/QSS modules (`hda_views`, `gate_widget`, `message_formatter`,
   `recipe_book`, `apex_*`, …): families → `FONT_*_CSS`, sizes → `SIZE_*`,
   weights → `WEIGHT_*`. *~120 instances, high confidence, pure substitution.*
5. **[spawn BP4-PT-HOTSPOT] `context_bar.py` literal `pt`** — 7 `9pt` QFont point
   sizes; convert to px + `SIZE_*` so the floor governs them. *(distinct from
   BP3-PT-HOTSPOT, same module.) 7 instances.*
6. **[spawn BP4-FONTLOAD-1SRC] `fontload` family single-source** — read
   `tokens.FONT_SANS/FONT_SANS_FALLBACKS` instead of the private `_SANS_CHAIN` /
   `_MONO_CHAIN`. *2 chains; behaviour-adjacent (setFamilies order) — needs a live
   Qt check.*

**`SIZE_LABEL → SIZE_MICRO` canonicalisation** folds into the existing
`BP3-NAME-CANON` spawn (cross-module).

---

## 8 · Joe-hands (T5) — measure the floor + capture before/after

The two `gui_required` steps that flip this leg's UNKNOWNs. Nothing here is
destructive; the probe only reads.

**1 · Measure the default UI font (flips the floor UNKNOWN → measured):**
1. In Houdini 22.0.400, open **`Windows ▸ Python Shell`**.
2. Paste and run:
   ```python
   exec(open(r"C:\Users\User\SYNAPSE\python\synapse\panel\scripts\probe_ui_font.py").read())
   ```
   (or copy the file's contents into the shell). If nothing prints, run `probe()`.
3. Copy the two summary lines it prints:
   `FLOOR CANDIDATE (px …) = <N>` and `MEASURED FAMILY … = '<family>'`.
4. Paste them here, under this line, as the measured provenance:
   `MEASURED (H22.0.400 GUI, <date>): FONT_FLOOR_PX = <N>, family = '<family>'`.
   A follow-up leg then sets `tokens.FONT_FLOOR_PX = <N>` (provenance → measured)
   and lifts any role below it (`SIZE_MICRO`/`SIZE_SMALL` if `<N>` > them).

**2 · Before/after screenshots (visual sign-off):**
- Capture the panel at **100 % UI scale** and at **150 % UI scale**
  (`Edit ▸ Preferences ▸ General User Interface ▸ Global UI Size`, or the OS
  display scale), **before** the floor lift and **after**.
- Confirm: (a) no text renders smaller than the surrounding Houdini UI labels,
  (b) family/scale read consistently across the panel, (c) chrome is unchanged
  (this leg is byte-identical — before/after of THIS leg are provably identical;
  the screenshots become load-bearing only once the floor is lifted).

---

## 9 · Acceptance mapping

| predicate | evidence | verdict |
|---|---|---|
| audit has typography rows per file:line + floor provenance (measured\|DOC-STATED\|UNKNOWN) | this file (§1–§4, §3 table `file:line`, §4 = UNKNOWN with cache-search evidence) | **pass** |
| token module defines family + scale + weights + line-heights; test finds no typography literal outside it | `tokens.py` §5 (families, 5-size scale, `WEIGHT_*`, `CHAT_LEADING_PT` leading); `test_panel_typography.py` pins qss.py = 0 literals **within the authority territory** — feature-module literals are inventoried (§3) + spawned (§7), not silently claimed clean | **pass (scoped to the diff surface; panel-wide closure = spawns 3–5)** |
| no size token below the floor constant | `test_no_size_token_below_floor`: every `SIZE_*` ≥ `FONT_FLOOR_PX=10` | **pass** |
| panel tests green before & after; diff limited to designsystem/manifests/qss/layout/scripts + the new test | before 346 / after 352 passed (panel selection); diff = `tokens.py`, `qss.py`, `scripts/probe_ui_font.py`, `tests/test_panel_typography.py` only; `synapse_panel.py` untouched | **pass** |
| probe output pasted from Houdini GUI + before/after screenshots | headless — **UNKNOWN**; steps in §8 (`gui_probe`) | **UNKNOWN** |

*Crucible map (each diff hunk → audit row): A→§5.A / B→§5.B / C→§5.C / D→§5.D /
E→§5.E / F→§5.F / G→§5.G / H→§5.H. Mutations that must redden: re-introduce a
hardcoded `font-size: 13px` / `font-weight: 600` in `qss.py` →
`test_qss_stylesheet_source_has_no_literal_typography`; set a size token below
the floor → `test_no_size_token_below_floor`; a non-token weight in `TYPE_ROLES`
→ `test_type_roles_use_weight_tokens`. No new widget/signal/slot/timer/import —
`synapse_panel.py` is not in the diff at all.*
