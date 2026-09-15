# Panel readability against Pentagram standards — measured 2026-09-15

Three lenses, all **FALLS_SHORT**. Measured on the composed panel at 340×760 (hython offscreen,
three density profiles) and cross-checked on the **live** Houdini 22.0.400 GUI at 192 DPI over the
bridge. Producers: `measure/producers/`. Distinct from `CRIT.md`, which judged *coherence* — this
judges whether the panel can be **read**.

---

## The headline

**It is a one-size panel wearing a four-size scale.** Of 15 visible text elements, **13 are 11px**.
`SIZE_HERO` is used **zero** times. `SIZE_TITLE` once, on the wordmark — branding, not navigation.
There is nothing for the eye to feel.

And 11 vs 12 is not a hierarchy step. Not by arithmetic (×1.09) but by **raster**: the letter `x`
occupies **six pixel rows at both sizes**; cap-height differs by one row. A label at 11 beside a
body at 12 — which happens in `gate_widget.py`, `saved_recipes.py`, `connection_dialog.py` — reads
as one level.

---

## Defects (not design questions)

| # | defect | measured |
|---|---|---|
| 1 | **A unit character inverts four rungs.** Five context-bar rules emit `pt` where every other rule emits `px`, so `SIZE_LABEL` — the smallest token — renders at **15px**, exactly `SIZE_TITLE`. | rendered |
| 2 | **SEND fails contrast at rest, passes on hover.** `SIGNAL_DEEP #627A93` under ink `#0F1F2B` = **3.78:1**; `:hover` swaps to `SIGNAL` = 7.69. The ink is commented "AA-safe" in `tokens.py` — true only of the colour it is never filled with. | WCAG 2.1 |
| 3 | **The quiet ramp was never solved.** `TEXT_TERTIARY` **3.94:1** across 11 selectors; disabled **2.01:1**; the input placeholder — the first thing read in an empty panel — **3.44:1**, and set by a Qt palette alpha the design system does not own. | WCAG 2.1 |
| 4 | **Weights asking for faces that do not ship.** Sans 600 is byte-identical to 700 (`fontload.py:174` routes ≥600 to `setBold`), and mono 500 is byte-identical to mono 400 (Space Mono ships two static files). Sans 500 *is* real (+14.6% ink from the variable face) and is being thrown away. | raster ink counts |

Body contrast is genuinely fine and should be left alone: `TEXT_PRIMARY` 8.32, `TEXT_SECONDARY`
5.49, `TEXT_BRIGHT` 10.67 on the panel ground.

---

## Measure — the answer to "why is it hard to read"

**28.6 characters per line**, counted from rendered `QTextLine`s, identical across all three
densities. The comfortable band is 45–75.

**The cause is not the 340px pane.** Message bodies render in **Space Mono with 15% added
tracking** — 8.0469px per character, uniform for every glyph. Monospace plus tracking, spent on
running prose, is the most expensive possible way to fill a narrow column.

Untracked sans measures 5.751px/char:

- sans, today's 248px column → **43.1 cpl**
- plus `setDocumentMargin(0)` (+8px) and a halved speaker indent (+8px) → **45.9 cpl — inside the band**

without taking one pixel from the artist's pane.

**Line height is already right**: 18.0px on a 12px body = **1.50**, dead centre, on every line and
every density. Do not touch it.

**Turn rhythm does not group.** A new speaker gets 16px, another message from the same speaker 12px
— ratio 1.333. Four pixels against an 18px line is a quarter of a line; the eye cannot feel it. The
constants M4 proved dead encoded 3.0×. The beat that survived the collision is the flatter one.

---

## The floor is below the host

The measurement the provenance string has owed since the beginning is now taken, live, read-only:
the host UI font is **SideFX Source Sans Pro, pixelSize 27, pointSize 10, at 192 DPI**.

`FONT_FLOOR_PX = 11` is **4.12pt on this seat — 40.7% of the chrome the artist's eye is calibrated
to.** Even at 96 DPI it sits under the host's 10pt/13.3px.

**CORRECTED 2026-09-15, same day, by re-probing the live session.** The first version of this
section got the finding right and three supporting claims wrong. Recording both, because a document
that silently fixes itself cannot be audited:

- It cited `synapse_panel._host_font_scale` **twice. That symbol does not exist.** What exists is
  `chat_display._font_scale`, a *user*-adjustable transcript scale seeded from
  `tokens.FONT_SCALE_DEFAULT = 1.0`. A fabricated citation is the worst defect a record like this
  can carry, and it was in the paragraph arguing that someone else's number was unverified.
- It said the body "runs 12% smaller than host chrome" and elsewhere that 12px "resolves to exactly
  the host's 27px". Both false, and mutually contradictory. `tokens.scaled()` is
  `max(8, round(size_px * scale))` with `scale` defaulting to 1.0 — **no host-derived scaling exists
  anywhere in the panel.**
- It said `probe_ui_font.py` "does not exist". **It exists**, at
  `python/synapse/panel/scripts/probe_ui_font.py`. It was looked for at the repo root and declared
  absent.

**The correction makes the finding worse, not better.** Because nothing scales, an authored 11px is
eleven actual pixels beside host chrome of twenty-seven. The body token at 12px is **44.4% of host
size — 56% smaller**, not 12%. The floor is not slightly low; the whole panel is rendering at a
little over four tenths the size of the application it lives inside, on this seat.

**An absolute pixel constant cannot be a floor relative to a host that moves.** `tokens.py:338`
already records that the default UI font size is "a MEASURED, GUI-only fact — `QApplication.font()`",
so the project knows. The instrument to read it exists and is not wired to the floor.

Measured live twice, independently: `QFontInfo(QApplication.font())` → family SideFX Source Sans Pro,
pixelSize 27, pointSize 10; screen logical DPI 192.0, physical 218.66, devicePixelRatio 1.0.

---

## Restraint

Four chromatic buckets at rest, all three profiles. The panel's own guard agrees and is **red**:
`test_chat_face_monochrome_one_accent_plus_state_marks` → `('curious', [0, 2, 13, 14])`. The fourth
is Houdini tab yellow `#B98620` on **Doctor** — a destination wearing a brand colour rather than a
state mark, and at 4.44:1 a contrast question too. That is B1, and it is Joe's.

---

## Proposal — three levels, not four

Keep **12** as the body anchor (Houdini-native 9pt; `_host_font_scale` resolves it to exactly the
host's 27px). Keep **15** and **19** at their existing 1.25 ratio. **Retire 11 as a size rung** by
aliasing `SIZE_SMALL` → `SIZE_BODY`, preserving its ~30 legacy consumers. Caption and status then
differentiate by **form** using signals the system already owns and is not spending: the EYEBROW
tracking entry at +0.22em, caps, and the mono family.

The off-token **14 and 18 are deliberate** — glyph sizes for status dots and chevrons, computed
inline as `SIZE_UI*3//2` and `SIZE_UI*7//6`. They should be named `GLYPH_MD` / `GLYPH_SM` and taken
**off the type scale explicitly**, not folded into it.

**The cost that makes this decidable: +1px at scale 1, +2.25px live — 0.3% of the 760px column.**
Eleven of twelve 11px widgets carry 12–22px of slack; only the "Enter sends" hint grows, by one
pixel. *"A 340px panel cannot afford larger type" does not survive measurement.*

---

## Method note, recorded because it is the day's recurring failure

The offscreen instrument reported the chat transcript's font resolving to **Courier** — which would
have been a blocker on the panel's most-read surface. The **live** read showed the transcript's
`QTextDocument` default font is Space Grotesk: the widget-level font is unset, but the document
paints correctly. A confident finding about the wrong property was one step from being written down
as fact. The live check caught it, and produced the host-font number above as a by-product.

Third time today an instrument reported confidently and measured the wrong thing.
