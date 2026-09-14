# Panel refinement — the Cohere board, 2026-09-14

**Method.** Four lenses (ORDINAL, EVIDENCE, LANGUAGE, GROUND) filed one transfer each
against the Pentagram Cohere case-study board, then critiqued each other by name and
conceded. Five concessions. One synthesis.

**Nothing here is built and nothing here is a ruling.** Panel design is gate joe.

---

## 0. The reference, measured — not just read

The lenses could not see the image; this section is the orchestrator's, and it is the
one number nobody else could produce. I ran **SYNAPSE's own restraint instrument**
(chroma = `max(r,g,b) - min(r,g,b) > 24`, hue bucketed at 15 degrees) over the
reference itself, filtering buckets carrying under 0.5% of chromatic pixels to
discount JPEG speckle.

```
WHOLE BOARD                 0.82% chromatic    8 meaningful buckets
phone (light list + dark)   2.74%              7
the dark OUTPUT region      4.06%              7
PARAMETERS column           5.79%              2
```

**Three things fall out of that, and two of them cut against a comfortable reading.**

**The board lands at 0.82% — exactly SYNAPSE's ratified floor.** That is a coincidence
worth naming and then distrusting, because the board is mostly empty beige. A poster's
average is not a tool's density.

**The right comparison is the panel against the dark OUTPUT region: 4.06% and seven
buckets.** Nearly five times SYNAPSE's floor and more than double its bucket ceiling.
So the honest statement is *the reference is far less restrained than SYNAPSE on any
comparable working surface* — and the transfer cannot be "look more like it".

**But the PARAMETERS column is the actual lesson: 5.79% chroma across only TWO
meaningful buckets.** High concentration, almost no variety. Pentagram spends heavily
on one hue family and nearly nothing on others. That suggests **bucket count, not
chromatic percentage, is the rule doing the work** — which is a finding about
SYNAPSE's own floor, arrived at from outside it.

**And one thing that bears directly on the live monochrome conflict:** those two
PARAMETERS buckets are `[18, 19]` — a single orchid accent split across a 15-degree
boundary. That is the same artifact as SYNAPSE's `SIGNAL` (210.8 deg, bucket 14) and
its sanctioned ink (205.7 deg, bucket 13) straddling into two. **The instrument's
coarseness is generic, not a SYNAPSE defect.** Any ruling on the four-bucket CHAT face
should know that one of its four buckets is an instrument artifact that Pentagram's own
work would also produce.

*Caveat: the reference is a q80 JPEG, so some chroma is compression artifact. The 0.5%
bucket filter removes the worst of it; the absolute percentages are still soft. The
bucket counts are the robust half of this measurement.*

**Producer.** The image itself is not tracked — `.gitignore:106` is a repo-wide `*.jpg`
rule and the sibling 2026-09-05 review tracks zero images across 61 files, so this
follows the house convention rather than forcing an exception. Reproduce it:

```bash
curl -sL -o ref.jpg "<the Pentagram imgix URL from the request>"
python - <<'EOF'
from PIL import Image
import colorsys, collections
im = Image.open("ref.jpg").convert("RGB")
def measure(box, label):
    px = list((im.crop(box) if box else im).getdata())
    chromatic, buckets = 0, collections.Counter()
    for r, g, b in px:
        if max(r, g, b) - min(r, g, b) > 24:          # SYNAPSE's own chroma rule
            chromatic += 1
            h, _, _ = colorsys.rgb_to_hsv(r/255, g/255, b/255)
            buckets[int((h*360)//15)] += 1
    real = sorted(k for k, c in buckets.items() if c >= max(1, chromatic*0.005))
    print("%-28s %6.2f%%  %d meaningful: %s"
          % (label, 100.0*chromatic/len(px), len(real), real))
measure(None,                "WHOLE BOARD")
measure((520, 455, 880, 910),  "the dark OUTPUT region")
measure((490, 1270, 840, 1900),"PARAMETERS column")
EOF
```

Crop boxes are for the 1480x1883 render the request's URL returns.

---

# REFINEMENT SCAFFOLD — Cohere board → SYNAPSE panel

Four lenses filed, four crits returned, five concessions made. What follows is the composed result. **Nothing here is built. Nothing here is a ruling.**

Four anchors I re-read to confirm they say what the filings say they say:

- `python/synapse/panel/message_formatter.py:394-408` — `_ruled_turn` is `cellpadding="0"`, `<td width="2">` rule, `<td width="14">` spacer, `<td>` body. **Confirmed.**
- `python/synapse/panel/activity.py:2-16` — eight curated keys, four of them dead; fallback is `removeprefix("houdini_").replace("_"," ").capitalize()`. **Confirmed.**
- `python/synapse/panel/chat_panel.py:170-180` — `ChatDisplay` at `stretch=1`, then pills, then `GateWidget` as a **sibling widget**, then the input container. **Confirmed.**
- `python/synapse/panel/designsystem/tokens.py:139` — `"surface": step(12)` and `"border": step(12)` in the same dict literal. **Confirmed.**

---

## 1. What the reference is actually doing

Strip the pixels off the Cohere board and five mechanisms remain. Only the mechanisms can cross.

**Addressability.** A row has a name, and the name is reused on a second surface. The number in the gutter is the same number on the scatter chip. Identity is *established by recurrence* — a number that appears once is decoration wearing identity's clothes.

**One winner, marked once.** A distribution collapses to a single line with exactly one accent. Everything else is neutral. The accent is not "important" — it is *the answer*, and there is only ever one.

**Disclosure per row, not per panel.** Collapsed shows the verdict. Expanded shows the evidence behind that verdict. The unit of expansion is the thing being answered for.

**Provenance by ground.** "What you asked" and "what came back" sit on different grounds with a straight unsoftened edge between. Not different boxes — different grounds. The edge is a region boundary, not an object outline.

**Plain word leads, jargon follows.** "Randomness · Temperature · 180". Human word in normal weight first; technical name smaller, second; value right-aligned on the same line.

Underneath all five: **the board has no time axis.** Everything is simultaneous and co-visible. That single fact is what forces the reference to encode authorship in ground and identity in numbers — and it is the fact that does not hold in SYNAPSE.

---

## 2. What transfers to 340px dark — and what does not

### Transfers

| Principle | How it lands in SYNAPSE | Evidence |
|---|---|---|
| Plain word first | Already half-shipped: `setToolTip(str(name))` carries the technical name at zero pixels (`face_work.py:267`, `:348`). Only the plain half is broken. | LANGUAGE, verified by EVIDENCE against the live registry |
| One winner, marked once | Survives **only translated from hue to value**. Zero chroma is available. TEXT_PRIMARY governs, TEXT_TERTIARY recedes. | EVIDENCE |
| Disclosure per row | The *collapsed* half transfers as HTML. The *expanded* half does not — see below. | EVIDENCE, conceded |
| Region boundary | One real pair exists: agent prose vs. machine receipt. GROUND→SURFACE is ΔL* ~11.6, 1.36:1 (`tokens.py:137-141`). | GROUND |
| Addressability | Transfers **conditionally** — only if a second surface cites the number. | ORDINAL, conceded |

### Does not transfer — and the lenses that said so were right

**The input/output tonal split is dead. GROUND refused its own headline transfer and the refusal is the strongest single call of the round.**

Three reasons, all measured:

- GROUND→PANEL is **1.148:1** (`tokens.py:137-141`, recomputed independently by two critics against the reference board's ~17:1).
- The tree already ran this experiment and recorded the answer: `message_formatter.py:356-362` — *"Twenty-five points of grey on a dim panel is not a speaker signal."* An 11-point step cannot carry what a 25-point step already failed to carry.
- The transcript scrolls and interleaves. "What you asked" is not a region here; it is a recurring turn. **A region-ground cannot chase a scrolling turn.**

SYNAPSE gets for free what the reference had to buy with ground: **order in time.** Asked is always above came-back. Nobody should re-propose this split.

**Proportional bars over booleans are a lie.** EVIDENCE dropped them correctly — anchors are booleans-with-applicability, not a continuous distribution. Then partly smuggled them back as a "value-banded hairline" split by anchor tally. GROUND's crit lands: *a tally of 17 held / 2 N/A / 1 failed is a proportion over booleans, one pixel tall.* Cut on the honesty argument, not the legibility one.

**The chevron does not transfer. There is no per-turn widget.** `chat_display.py:80` is `class ChatDisplay(QtWidgets.QTextBrowser)` — one QTextDocument, every turn arriving via `cursor.insertHtml`. EVIDENCE filed this as a load-bearing UNKNOWN and named it a drop condition. **The condition fired.** Three lenses independently confirmed it. Per-row progressive disclosure via a child widget does not exist to be built.

**A visible second name does not fit.** `synapse_solaris_shotsetup_karma_xpu` is 35 chars of mono ≈ 210px before the plain name gets a pixel, in a body column of ~256-264px. Law 4. The tooltip already carries it.

**A new section-label band does not fit.** GROUND priced it and refused it: 14px ink + 20px of legal grid air + 1px rule = **35px**, an 8px overrun on its own; an INPUT/OUTPUT pair overruns by 43px. The generalisation is worth adopting verbatim: *section labels may only ride bands that already exist, never a new band.*

### One structural fact that reorders everything

**The consent card is not in the transcript.** `chat_panel.py:178-180` — `GateWidget` is a sibling band between the scrolling transcript and the composer. Its height comes out of the transcript's stretch, which is **exactly what BC-5 measures**.

Consequences, both directions:

- GROUND's premise ("in-flow receipts inside the same scrolling column") is **factually wrong**. The region boundary it wants to straighten already exists as a widget boundary; only `RADIUS_CARD` softens it. The transfer shrinks to a corner change.
- GROUND's −2px is therefore **not incidental**. It is the only proposal in the round that *returns* pixels to the contested ledger — found without knowing the ledger was contested.

---

## 3. The refinements, ordered by artist value / cost

### R1 — Repair the tool-label fallback (LANGUAGE (b)1 + (b)2)

Strip **every** namespace prefix (`houdini_`, `synapse_`, `cops_`, `tops_`), uppercase the first letter only, restore domain capitals from a small table (USD, VEX, PDG, XPU, COPs, TOPs, LOP, SOP, ROP, MaterialX, Karma, Solaris, APEX, OpenCL, MCP).

Today `.capitalize()` lowercases all of them. `houdini_create_usd_prim` ships as **"Create usd prim"** (`activity.py:16`, confirmed).

| | |
|---|---|
| **px** | **0 vertical, non-positive horizontal.** Same label, same font, same row, same count. Worst case narrows. |
| **buckets** | **0.** Reads no colour token at all. |
| **artist cost** | Near zero. Every label stays **mechanically reversible** to its tool id by re-underscoring. |

This is the cheapest true thing in the round and it needs no owner, no map, no ceiling, and no pinning test.

---

### R2 — Re-key the four dead entries (LANGUAGE (a))

Confirmed dead at `activity.py:2-11`, against the live registry:

| `_TOOLS` key | live name |
|---|---|
| `houdini_get_scene_info` | `houdini_scene_info` |
| `houdini_set_parameter` | `houdini_set_parm` |
| `network_explain` | `houdini_network_explain` |
| `capture_viewport` | `houdini_capture_viewport` |

**The map is running at 4/8 and nothing reports it.** EVIDENCE found the cause: the dead keys are the *wire command names* — the second column of the same registry tuples. Not written against a stale registry; written against the wrong column of the live one.

| | |
|---|---|
| **px** | **0 / 0.** |
| **buckets** | **0.** |
| **artist cost** | **A curated name can be confidently wrong; a derived one cannot.** "Set up a Karma XPU shot" claims to know what the tool does. If the tool changes, the panel lies fluently. And the identifier moves to a hover-only channel — **a tooltip does not survive a screenshot.** For a system whose posture is citable evidence, that is a real loss. |

**Conditions, both raised by the filer or a critic:**

- (b)3 as filed **cancels itself.** "Show the raw tool id if the derived name exceeds the ceiling" — the derivation is a character-for-character swap, so the escape hatch is the same width as the overflow. Needs replacing with a plain elide-check at whatever width the row happens to be.
- Clause (c), the `QFontMetrics` ceiling, is **withdrawn by its own author.** Caption role is Space Grotesk 11px, zero tracking; the longest proposed label ≈148px in a ≥252px column. The apparatus measures a wall nothing touches.
- Three entries were **invented** where shipped strings exist. The overflow menu's stop verbs must be read and reused verbatim.
- Without the pinning test in (d), R2 **quadruples the existing rot surface** — 8 curated names to ~20.

---

### R3 — The BORDER == SURFACE finding *(filed as evidence, not as a request)*

`tokens.py:139` — `"surface": step(12)` and `"border": step(12)`, identical by construction at every host seed. Pinned by the tree's own fixture at `tests/panel/test_theme_source.py:54` (both `#363636`).

**Every hairline on every card in this panel is invisible against its own fill.** The card's outer border, `#DsCardHeader`'s border-bottom, `#DsCardBody`'s — all of them.

GROUND found it and explicitly declined to ask for a ruling. Two critics said it should be one, and the argument is short: **the reference's "unsoftened edge" is unreachable while the panel has no edges at all.** This is not a softening problem in SYNAPSE; it is a missing-edge problem.

Cost to state: 0px, 0 buckets. Cost to *fix*: unpriced, because nobody proposed a fix.

---

### R4 — The receipt line, collapsed only (EVIDENCE, post-concession)

One line appended to the tail of every turn that **mutated the scene**. Read-only turns get nothing.

```
   Undoable                      mcp · 4/4
```

Plain word first, technical second, right-aligned tabular. Three verdicts: `Undoable` / `Partial` / `Not recorded`. Exactly one row governs, marked in **value** (TEXT_PRIMARY against TEXT_TERTIARY), never hue. The governing-row rule is deterministic and pinnable the way `_fidelity_color` is pinned.

**The finding underneath it is the best observation of the round, and it stands independent of the proposal.** `claude_worker._track_integrity` records one integrity dict per tool call into `SessionIntegrityTracker._blocks` (`session_integrity.py:46,56`). `integrity_readout` collapses the whole list into `"fidelity 100% · N verified"` — session-scoped, both branches. `face_work.set_tool_status` does a bare `setText` (`face_work.py:263-265`), so each tool call overwrites the last. **SYNAPSE's differentiator is per-action receipts and the panel shows a session mean.** Data recorded, surface throws it away.

| | |
|---|---|
| **px, fixed chrome** | **0** — under the placement ruling (scroll content, HTML inside `_ruled_turn`'s body cell). |
| **px, scroll content** | **+18–19px per mutating turn.** UNKNOWN on the exact Qt line box for a 10px mixed sans/mono row; 13–14px is derived from `SIZE_MICRO=10`, not measured. |
| **buckets** | **0 as specified.** Two unfenced doors — see §5. |
| **artist cost** | ~1.35 fewer turns visible per mutating turn in a ~380px transcript. A permanent low-grade audit texture that cannot be switched off without making receipts invisible again. And `STAGE HASH reduced` is currently true and hidden — showing it produces a support question the first time it appears. Hiding it is what SYNAPSE's own docs forbid. |

**Struck by the filer during crit:**

- The **18px ordinal gutter** — conceded entirely to ORDINAL. One counter, not two.
- The **chevron and the expanded stack** — the per-turn widget does not exist. Replacement offered: the evidence stack rides `setToolTip`, at zero pixels, inheriting LANGUAGE's honest cost (*a tooltip does not survive a screenshot* — worse for a receipt than for a label).
- The **value-banded hairline** — recommended cut by GROUND on the honesty argument.

**Two open language problems:**

1. **"Not recorded" is already spoken, one row down.** `gate_widget.py:360` ships `_show_decision_tag("NOT RECORDED")` for *a decision that never reached the gate*. EVIDENCE's verdict means *this op produced no integrity block*. Same two words, two scopes, one nested inside the other.
2. **"Undoable" reads both ways in English.** *Un-doable* = cannot be done. CLAUDE.md §1.8 mandates the word — but mandated it *in a sentence*, where the ambiguity cannot bite. As a standalone 10px verdict on a dark ground it is the one word most artists will ever read.

**Corrected number:** EVIDENCE priced the text column at "~308 → ~290px." There is no 308px column. See §4.

---

### R5 — Square the receipt's corner (GROUND, post-concession)

`RADIUS_CARD = 10` (`tokens.py:546`) rounds all four corners of `#DsCard`, so the GROUND→SURFACE boundary is never a straight line and the block reads as a floating object rather than a band of different ground.

Set radius 0 on an in-flow variant. **Value does the separating; straightness is what makes the eye read "region" instead of "object."**

| | |
|---|---|
| **px** | **0**, or **−2 on the contested ledger** if the no-op border goes with it. |
| **buckets** | **0.** Both greys are neutral off the same host seed. |
| **artist cost** | The real trade, and it cuts against the card's job. A consent card exists to **get a decision**. Roundness is part of why it reads as *waiting for you*. Square it and it reads as a log entry — sitting directly above the composer, where chrome is what the eye stops seeing. |

**The full-bleed to 280px is withdrawn**, on two grounds the filer conceded:

- The 280 figure is the **rail's** documented interior (`synapse_panel.py:907-908`), applied to the transcript without reading the transcript's container. Under Law 2 it reads **UNKNOWN**.
- If ORDINAL ships, body text starts ~54px from the panel edge and a full-bleed receipt starts at 0. That is a 54px ragged step on the narrowest surface in the product — *arguing for straightness while adding raggedness.*

**And the stacking case is a consequence, not a risk.** Given R3, the radius is not one of the card's few boundaries — **it is the only one.** Two stacked square receipts with an invisible border and ΔL* 11.6 do not get a faint seam; they get one continuous grey field.

---

### R6 — The turn ordinal (ORDINAL)

A session ordinal in the existing unpainted spacer cell of `_ruled_turn`, right-aligned mono, `TEXT_TERTIARY`, **right of the 2px speaker rule.** One counter, incremented once per group head.

The placement is the most disciplined decision in the round: putting the number left of the rule would read closer to Cohere and would make J3's own sentence a lie.

**Value:** `synapse_panel.py:2315` is the evidence. The REVERT verb sends *"Undo the last change using houdini_undo"* and its own docstring admits the referent is recency, not identity. With an ordinal: *"Undo the change made in turn 14; if the last undo step belongs to a different turn, say so instead of undoing it."*

**States plainly what it does not buy:** the undo is still one global step. The ordinal makes the *request* addressable, not the *undo* targeted.

| | |
|---|---|
| **px, vertical** | **0.** A column in a table that already renders. |
| **px, horizontal** | **CONTESTED — 8, 12 or 20.** See §4. |
| **buckets** | **0.** `test_bc_wave.py:282` buckets on `max−min > 24`; `TEXT_TERTIARY` is chroma 0. The filer named the one trap before anyone else could: `_warm_bias` lands at chroma ≈24, **exactly** on the threshold — a warm number is a coin-flip bucket. |
| **artist cost** | ~1–3 characters per line on a transcript already delivering ~39 chars against its own stated `_MEASURE_CHARS = 90` — **43% of its own target measure.** Plus a glyph per turn that is not what was said: this shifts the transcript's register from *conversation* toward *log*. And it is **pure overhead unless the numbers actually get spoken.** |

**Two things the round did to this proposal:**

- **The filer conceded the load-bearing half.** The claimed "second surface, already built" — the consent card's tag taking the same integer — does not hold. Cards are per-**operation**; a turn raising three cards would stamp all three "14", re-creating the exact ambiguity the proposal cites as the problem.
- **The filer's own withdrawal condition is a category error, corrected in its favour.** It said a wrap "lands in the +27px headroom and collides with BC-5 — at which point I withdraw." It does not. A wrap adds *document* height inside a `QTextBrowser`, which scrolls. It costs scrollback, not pane geometry. The wrap test is still worth running — as a scrollback measurement.

**Zero-pixel fallback, if the column is refused:** append the ordinal to the timestamp — `● SYNAPSE  14 · 2:14 PM`. **0px, 0 buckets, 0 assertions touched.** Buys *sayability* but not *scannability*.

---

## 4. The combined budget

### Vertical, against the +27px standard-density headroom

```
reserve                              +27px
R1  LANGUAGE fallback                   0
R2  LANGUAGE curated map                0
R4  EVIDENCE receipt (scroll content)   0      ← conditional
R5  GROUND squared corner               0, or −2  (a gain)
R6  ORDINAL turn gutter                 0
                                     -------
remaining                            +27px, or +29px
```

**They fit. The +27px is not contested by anything filed this round.**

The reason is uniform and worth stating as the finding: **every one of the four had an "obvious" placement that would have landed in fixed chrome** — ORDINAL's gutter as a sibling widget, EVIDENCE's receipt beside `IntegrityReadout`, GROUND's section-label band — and all four refused it independently.

**The distinction that makes the zero real** is EVIDENCE's, and it is worth adopting as a ruling: *the +27px is pane geometry — fixed chrome versus the transcript's share of 760. Scroll content does not draw on it.*

### The one conditional that breaks it

R4's zero is purchased **entirely** by its placement ruling, and the nearest pattern in the tree (`GateWidget`, sitting in the same layout) pulls an implementer toward the expensive answer.

```
reserve                                      +27px
R4 as a widget, collapsed     −18 to −19  →   +8 to +9px left
R4 as a widget, expanded     −100 to −114 →  −73 to −87px
```

**BC-5 would fail by 73–87px the first time the artist clicked a chevron.** This should be ruled explicitly, not left in a filing's UNKNOWN.

And the other door has its own unpriced cost: HTML expansion means `insertHtml` mid-document, which the file's own comments (`chat_display.py:27`, `:502`, `:611`) call an O(document) re-layout on an **instrumented freeze surface**. The cost moves from pixels to latency on a path with a freeze ledger.

### The budget nobody was told to meter — horizontal

Body column inside `_ruled_turn` = interior − 2 (rule) − 14 (spacer).

**The base is contested:**

| source | base body column | reason |
|---|---|---|
| ORDINAL / LANGUAGE / GROUND | **264px** | 340 − 2×GUTTER(30) − 16 |
| EVIDENCE | **256px** | plus Qt's default 4px-per-side document margin; no `setDocumentMargin` call exists |
| EVIDENCE as filed, for receipts | ~308px | **refuted by two lenses.** No 308px column exists in this panel. |

**And the gutter width is contested three ways, all from the same confirmed fact — `cellpadding="0"`:**

| source | cell | delta | reasoning |
|---|---|---|---|
| ORDINAL (filed) | 22px | −8 | 3 mono digits |
| LANGUAGE | 26px | −12 | Space Mono 0.6em → 18.0px for 3 digits, +4 air, +4 slack. *Filed 22px has zero slack; the failure boundary is turn **100**, not turn 1000.* |
| GROUND | 24 / 34px | −10 / −20 | 4px rule-gap + digits + 8px body-gap. *ORDINAL priced the digits and not the gaps.* |

All three agree on the mechanism: **right-aligned digits in a zero-padded cell sit flush against the prose.** The air has to come from inline `padding-right` on the `<td>`, and whether QTextDocument honours that is unmeasured and load-bearing.

**Stacked worst case, two-ordinal world (now resolved — see below):** 280 interior − 2 rule − 26 turn gutter − 18 receipt gutter = **234px**, with **40px of a 280px interior (14.3%) spent on digits in two incompatible numbering systems.**

### The scrollback budget — real, and invisible to the 27px meter

GROUND's arithmetic (INFERENCE on the group-margin value; the rest read from source):

```
three-line mutating turn today                   ≈ 87px
  + R4 collapsed receipt (19px)                  ≈106px
  + R6 wrap, if the repriced 20px fires it       ≈124px

380px transcript ÷ 87  = 4.4 mutating turns visible
380px transcript ÷ 124 = 3.1
```

**~30% loss of visible scrollback on exactly the turns that changed the scene.** Paid in the scroll axis. Nobody was told to watch it.

### The one genuine collision — resolved by concession, needs ratifying

**Two ordinal systems.** R6 counts **turns** (one per group head). R4 counted **integrity blocks** (one per tool call). A turn running four tools is **14** to one lens and **07, 08, 09, 10** to the other. Both cite reference item 1. Both claim identity.

Ship both and *"undo 07"* is ambiguous — **the exact disease item 1 exists to cure, reintroduced by curing it twice.**

All four lenses converged on the same resolution, unprompted:

> **One counter. It is the turn**, because the turn is the unit the artist *speaks* and the unit the undo request names. R4's receipt cites `14.2` — turn, op — or nothing.

This resolves both filings' drop conditions in one move: R6 needed a second surface to cite its number or the gutter is decoration; R4 needed an address it did not have to mint. **The receipt line is R6's second surface.**

### The one mutual exclusion — needs ruling as an either/or

**R5's full-bleed and R6's gutter cannot both ship at full strength.** A full-bleed receipt's straight edge would run *through* the ordinal gutter and under the speaker rule. Either the bleed stops at 256px (and the region read weakens to roughly what it already is), or the gutter is not a fixed column (and R6's identity promise breaks the first time a receipt crosses it).

GROUND already withdrew the bleed. **The squared corner survives R6; the bleed does not.**

### If one has to go — a recommendation, not a ruling

**I would drop R6's 22–26px column and keep its 0px fallback.**

Not because it is weak — the placement reasoning is the best in the round. Because:

- Its cost is the only one that is **contested three ways and largest on the axis already furthest below its own spec** (39 chars delivered against `_MEASURE_CHARS = 90`).
- Its value is **contingent on a behaviour nobody has observed** — whether Joe would type "undo 14" when the REVERT verb is sitting on the card.
- Its filer conceded the load-bearing half of its own evidence.
- **The fallback keeps the entire sayable vocabulary at 0px and 0 buckets.** `● SYNAPSE  14 · 2:14 PM` gives up scannability — which matters only if the ordinals ever get dense enough to compare, and does not matter if the artist only ever needs to find one.

Second on the drop list, if anything else must go: **R4's tooltip-borne evidence stack.** Not the collapsed line — the line is the differentiator. The stack behind it, because a tooltip does not survive a screenshot and a receipt that cannot be screenshotted is a weak receipt.

---

## 5. What must not be touched

### The two live conflicts

**(a) The Doctor button's artist-approved yellow vs. the monochrome ceiling.**

Nothing proposed here touches it. No proposal spends chroma.

**One path to watch, not a spend:** R2 makes `synapse_doctor` → "Check SYNAPSE" byte-identical to the Doctor button's `accessibleName`. Good discipline, but it creates a naming tie to the one control wearing `HOUDINI_TAB_YELLOW`. *"The button and the row say the same words, so should they not look the same?"* is a two-step path from here to yellow on a Work row. **The shared string is a word tie, never a colour tie.**

**(b) J5's density-scaled top-edge air vs. BC-5's "transcript ≥ 50% of 760".**

Untouched by everything filed, at 0px combined. R5 arguably *helps* by −2px.

**But note the ledger correction:** GROUND believed its pixels were scroll content and felt safe on that basis. They are **fixed chrome**, on the same ledger as the +27px. The conclusion holds; the reasoning that produced it does not. Any later refinement of R5 that adds so much as `SPACE_XS` of padding is spending the pane's only reserve.

### The frozen seam

Two ratified J3 assertions decide R6's placement, and Law 1 holds whichever counter wins:

- `tests/test_j3_panel_formatter.py:53,60` — `TEXT_TERTIARY not in` an **unstamped** `_speaker_label`. Any grey ordinal prefixed into that div goes **RED**. Staying in `_ruled_turn` leaves the label's return string byte-identical.
- `tests/panel/test_j3_speakers.py:157-160` — `_first_char_colour(label_block)` must equal SIGNAL / CONIFEROUS exactly.

**No relaxation is proposed. The tests govern the design, not the reverse.**

One more seam, in a different file: `tests/test_panel_sweep_a.py:71` pins the **call site** in `face_work.py`, not the label content. R1/R2 touch `activity.py` internals only and stay green — which is exactly why the change must not be "improved" into the call site later.

### The restraint floor, and the fourth-bucket problem

The CHAT face measures **four hue buckets `[0, 2, 13, 14]` against a ceiling of three.** It is already over.

**Four lenses, and not one of them moves the face off four.** Everyone routed around the measured violation. **Nobody proposed retiring a bucket.** That is a gap in the round, stated plainly.

**Two unfenced doors to a fifth bucket, both in R4, both at implementation time:**

| door | what it costs | status |
|---|---|---|
| `integrity_readout._fidelity_color` | returns SLATE / CONIFEROUS / HOT_SOFT / NO_SOFT — hues ≈127°, ≈25°, ≈354°, none in `[0,2,13,14]`. **4 + 3 = 7 buckets.** | **Fenced by the filer, by name, sharply.** Correct where it lives, on the Work face, where it is already counted. |
| `gate_widget._show_decision_tag(blocked=)` | `gate_widget.py:155,176,346,360,372,396` — the REJECTED tag carries `property("status","BLOCKED")`, named as **HOT_SOFT**. Hue ≈25° → **bucket 1, a new bucket.** | **NOT fenced.** "Reuse gate_widget's exact strings" is precisely the instruction an implementer reads as "reuse the tag." |

**Reusing the string is free. Reusing the tag is a fifth bucket.** Two critics found this independently; one flagged it UNKNOWN-but-probably-not-zero because they had not read the tag's paint. It needs the same hard line R4 wrote for the dot.

**One more meter, and it is the one already over.** The floor has **two** numbers: bucket count *and* 0.82–0.84% chromatic pixels. R5 asserts "chromatic-pixel share unchanged — it changes the geometry of an existing neutral fill." Geometry change is area change. `step(d)` adds the same delta to R, G and B, so SURFACE carries **exactly the host seed's chroma** — achromatic under UIDark, but not by construction. On a tinted seed, a wider fill paints more chromatic pixels at the same hue. No new bucket; the share claim is *"unchanged under an achromatic seed."*

---

## 6. The decisions for Joe

Each one answerable on its own. None depends on (a) or (b) resolving.

**D1.** Would you ever type **"undo 14"** — or when you reach to undo, is the card already on screen with REVERT on it?
*Decides R6 entirely. No measurement can settle it.*

**D2.** Does the turn own the integer, with the receipt citing **`14.2`** rather than minting its own sequence?
*All four lenses recommend yes. Needs ratifying, because it is the only thing preventing two numbering systems on one 340px column.*

**D3.** Must the tool identifier stay readable **in a screenshot**, without hover?
*If yes: R2 dies and R1 ships alone. That is a legitimate ruling — SYNAPSE's posture is citable evidence, and a hover-only identifier is not citable.*

**D4.** Does the collapsed receipt line ship as **HTML inside the transcript**, never as a widget?
*If left to the implementer, `GateWidget` is the nearest precedent and it lands in fixed chrome — 19 of 27px at rest, 73–87px over when expanded.*

**D5.** Is **"Undoable"** the standalone verdict word, given that *un-doable* reads as "cannot be done" at 10px on dark?
*CLAUDE.md §1.8 mandates the word in a sentence. This asks whether the mandate extends to a bare label.*

**D6.** Is **BORDER == SURFACE** (`tokens.py:139`) a bug to open, or a fact to live with?
*Costs 0px and 0 buckets to state. Every hairline on every card is currently invisible.*

**D7.** Does a **squared, object-less consent card** still read as *waiting for your decision* — or as a log entry?
*Seat judgment, not measurement. If it reads as a log entry the proposal dies there; do not negotiate it down by half-rounding.*

**D8.** Does anyone **own** the curated tool-name map, with the pinning test?
*Without an owner, R2 quadruples a rot surface that already ran at 4/8 undetected.*

**D9.** Pin the reserve rule: *at standard density the +27px is a **reserve**, not a budget — nothing proposed in this round may enter it.*
*Three lenses refused fixed chrome independently. Worth making explicit.*

**D10.** Pin the band rule: *section labels may only ride bands that already exist, never a new band.*
*GROUND's own refused item — 35px for one band, an 8px overrun alone.*

---

## 7. What nobody measured

Explicit. Every one of these was flagged UNKNOWN by at least one lens, or discovered unflagged during crit. **None was resolved.**

### Load-bearing and unmeasured

- **The transcript's actual content width.** Nobody read `ChatDisplay`'s container. 280 is the *rail's* documented interior (`synapse_panel.py:907-908`), applied to the transcript by two lenses without checking. One lens argues Qt's default 4px document margin makes it 256. **Every horizontal cost in §4 inherits this.**
- **Whether QTextDocument honours inline `padding-right` on a `<td>`.** `cellpadding="0"` is confirmed; raising it would pad the 2px rule cell and destroy the rule. This is the whole difference between a column and a number glued to a word.
- **Whether R4 as HTML can expand without breaking scroll-to-bottom**, and what an O(document) `insertHtml` costs on a surface with a four-class freeze taxonomy. Also: `setMaximumBlockCount` (`chat_display.py:627`) evicts from the top, so evidence reachable only by re-render is reachable only until the cap eats it.
- **The gate tag's paint under `blocked=True`.** Asserted HOT_SOFT from `gate_widget.py:176`; not read at the tag. **UNKNOWN buckets, probably not zero.**

### Tests cited but not run

- `tests/panel/test_j3_speakers.py` — nobody ran it. Specifically: **whether an extra `<td>` shifts which block `_apply_turn_rhythm` tags as the speaker block** (`UserProperty + 1`, pinned at `:155`).
- Whether any design-conformance guard **pins card radius.** One targeted grep found nothing. A grep is not a run.

### Numbers derived, not measured

- **The Qt line box for a 10px mixed sans/mono row.** R4's 13–14px comes from `SIZE_MICRO=10` plus assumed leading. Until a seat capture, 18px is not a number.
- **Whether 8–20px of gutter pushes a common node path (`/stage/lights/key_fill_01`) across a wrap.** Measurable today with the existing offscreen 340×760 grab. If it wraps, the cost converts from horizontal to scrollback — one extra line per turn, on top of R4's 19px.
- **Chromatic-pixel share under a tinted host seed** for a widened neutral fill. The share meter is the one already at ceiling.
- **The group-margin value** in the scrollback arithmetic. Flagged INFERENCE by its author; the rest of that chain is read from source.

### One grep that decides a whole proposal

- **Does the model's prose already name the tool id in the turn?** If it does, the citable receipt survives on the same surface as the screenshot and D3's objection weakens to a preference. If it does not, the objection stands and R2 falls back to R1. **Nobody ran it.**

### Unexamined entirely

- **The streaming path.** `begin_stream` / `end_stream` — an ordinal must be issued at stream *open*, or the number appears after the answer it names. No lens looked.
- **`format_system_message`.** Centred italic interjections are not turns and get no cell, so a session with many of them shows a number column **with holes in it.** Needs a stated rule; a gutter with gaps reads as a bug.
- **The overflow menu's three shipped stop-verb strings.** R2 invented "Stop the render" without reading them. Conceded by the filer, not yet corrected.
- **`SessionIntegrityTracker._blocks` is unbounded and append-only** (`session_integrity.py:46`). Not a design collision — but making it artist-visible turns an internal buffer into an addressable index, and any future eviction policy becomes a user-facing change.
