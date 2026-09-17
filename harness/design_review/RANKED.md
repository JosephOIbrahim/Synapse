# The panel design backlog, ranked — 2026-09-16

**One index across all three review rounds.** The rounds are dated directories and each is
internally ordered, but nothing has ever ranked them *against each other*, so the most recent
findings sat behind two older rounds that were themselves waiting. This file is the cross-round
order, newest round first, priority within each.

**The split that matters more than the order.** Forty design calls were extracted from the four
review documents and each one checked individually against the code at HEAD. The verdicts:
**31 OPEN, 6 SHIPPED, 2 PARTIAL, 1 SUPERSEDED.** Those 40 contain cross-document duplicates — the
same call is often raised in two rounds — so the distinct open count is lower; the synthesis pass
put it at roughly 28 distinct items with 22 needing a ruling, and **that consolidation is the only
figure here not independently verified.** The raw 31-of-40 is.

Either way the shape is the same and it is the thing worth knowing: **this is a decision backlog,
not a build backlog.** An item waiting on implementation can be picked up by anyone. An item
waiting on a ruling cannot be started by anyone, at any priority, until it is ruled.

**Status vocabulary.** `APPLIED` — in the code as of this file. `RULE` — waiting on Joe.
`BUILD` — unblocked, waiting on hands. `DEFER` — deliberately not done, with the reason stated.
`BLOCKED` — waiting on another item, named.

---

## Round 3 — 2026-09-15 · `harness/design_review/2026-09-15/`

The most recent round, and the only one whose findings were measured on the **live** Houdini GUI
rather than offscreen alone. `CRIT.md` judged coherence, `READABILITY.md` judged whether the panel
can be read, `SECOND_LOOK.md` checked the mockups against the as-built panel.

### Applied 2026-09-16 (CTO, pre-approved)

| # | Change | Effect | Where |
|---|---|---|---|
| R3-1 | **Root gradient deleted; the root is flat.** | 8 levels of 255 over 760px — one level per 95px, sub-perceptual. Both rendered directions agreed on removing it, so no contested call. | `designsystem/qss.py` root block |
| R3-2 | **Transcript document margin 0.** | Returns **8px** of reading height (Qt's default 4 on top and bottom) and puts the left content edge on `GUTTER` instead of an anonymous Qt constant. *Caveat:* READABILITY.md reports the edge as 50→46 via a 16px speaker indent; no such indent was found in `message_formatter.py`, so the vertical 8px is verified and the exact horizontal figure is not. | `chat_display.py` `__init__` |
| R3-3 | **`GLYPH_MD` / `GLYPH_SM` named.** | 18 and 14 were bare arithmetic in QSS, so a type census counted them as two extra ramp rungs. **Zero pixels change.** | `designsystem/tokens.py`, 3 sites in `qss.py` |
| R3-4 | **`FONT_FLOOR_PROVENANCE` corrected.** | Said UNKNOWN and "awaiting the paste" for a measurement taken 2026-09-15, and cited the probe at a path it has never been at. No value changed. | `designsystem/tokens.py` |

### Deferred, with the reason

| # | Item | Why not |
|---|---|---|
| R3-5 | **Delete the three dead `#DsHeader` margin rules.** They paint nothing (Qt ignores margin on a bare `QWidget` selector) and perturb the rail's measured height with an inconsistent sign — airy −8, standard 0, tight +4, which inverts the density lever. | Removing them needs `QWidget#DsHeader` in `test_panel_sweep_a`'s ruled-selector list, and that list strips whole rule blocks **by selector**. Measured: that selector matches **4** blocks including the live background/hairline rule. The exemption would stop guarding a rule that still ships. Trading a real guard on a live rule for deleting one that paints nothing is a bad trade. Needs a by-declaration exemption. Nothing visible either way — expert is the only composable profile. |

### Waiting on a ruling — Round 3

| Priority | # | The call | What makes it decidable |
|---|---|---|---|
| **1** | R3-A | **Retire 11px as a text size.** Alias `SIZE_SMALL` → `SIZE_BODY`; caption and status differentiate by *form* (tracking, caps, mono). | The letter `x` occupies **six pixel rows at both 11 and 12** — the raster cannot show the step. 13 of 15 visible elements are 11px. Cost: **+1px on one widget**, 0.13% of a 760px column. Note it partly reverses PR #100, shipped four hours earlier. |
| **1** | R3-B | **What carries "quiet" now that value cannot.** Tertiary `#9E9E9E` and secondary `#A0A0A0` are two levels apart out of 255 — one grey — and both are pinned at the AA floor, so neither can move. | Shipping the AA ramp *created* this. Pick one: tracking, caps, mono, or weight. **Rule with R3-A in one breath** — they are the same argument from two sides, and separate answers give the panel two half-systems for quiet hierarchy. |
| **2** | R3-C | **Is an absolute pixel floor legitimate against a host that moves?** | Host UI font measured live: SideFX Source Sans Pro, **pixelSize 27** at 192 DPI. Nothing in the panel scales — `scaled()` defaults to 1.0 — so an authored 11px is 11 actual pixels beside 27. About **41%**. The instrument to read the host exists at `panel/scripts/probe_ui_font.py` and is not wired to the floor. |
| **2** | R3-D | **The transcript reads 28.6 characters per line** against a comfortable 45–75. | Cause is not the narrow pane: Space Mono **plus 15% tracking**, 8.05px per glyph. Untracked sans + `setDocumentMargin(0)` + a halved speaker indent measures **45.9 cpl — inside the band, costing zero pane width.** R3-2 above already banked one third of that fix. |
| **3** | R3-E | **Speaker spacing.** New speaker 16px, same-speaker follow-up 12px — a quarter of an 18px line; the eye cannot feel it. The dead constants encoded 3.0×. | Two linked questions: the ratio, and whether the transcript gets its own gap keys. `group` and `row` in `rhythm.ROLE_GAPS` are **shared** by six surfaces, which is why the nesting-spacing change is not free and was not applied. |
| **3** | R3-F | **Mockup truth bugs** — boards draw a grey status dot; the panel draws a warm 300° open arc. Empty context ribbon. An impossible disconnected-mid-conversation state. | **Zero shipping pixels.** These are stale drawings, not a capability gap — filing them as "panel work remaining" overstates the backlog. One procedural blocker: the published page carries later edits, so a republish must read and merge, never push blind. |

---

## Round 2 — 2026-09-14 · `harness/design_review/2026-09-14/` + `harness/notes/v2-waves-2026-09-14/`

Sixteen calls, explicitly staged as a decision surface: *"This file is a decision surface, not a
proposal to build. No code in this PR touches `python/`."* Two of its items are the reason two panel
tests are red.

| Priority | # | The call | Why it ranks here |
|---|---|---|---|
| **1** | R2-A1 | **"Airy is a spec, not a target."** The panel only ever builds expert, but a test and a contract still grade it against airy. | **One word unsticks four items** — A1 gates B2, B2 gates A2, A3 guards it. Highest leverage item in the entire backlog. Record it with `python scripts/ingest_rulings.py "A1 ratify" --who joe`. |
| **1** | R2-B1 | **The Doctor button's yellow** vs monochrome-plus-one-accent. Keep / drop / promote. | The item most others queue behind. Both legs are ruled positions of yours: sweep-A pins it as the *artist-approved* accent, BC/J1 forbids a fourth hue. **Measurement settled 2026-09-16:** the guard is genuinely red at HEAD — `('curious', [0, 2, 13, 14])`, four buckets. The claim that shipping the black SEND ink removed the fourth is refuted. |
| **2** | R2-B2 | **J5's header air vs BC-5's 50% transcript share** — they fight by **13px** (48.289% of 760). | May dissolve without you: ranked change #11 is derived to close it to zero. Also cheaper than documented — the doc warns a fix could silently undo J5, but the wordmark y **is** pinned, at `test_j5_rail_air.py:120, :157, :173`. |
| **2** | R2-C1 | **Card borders are the same grey as the card** — `surface` and `border` both built from `step(12)`. | Stakes rose: v5.73.0 deleted the dead tone-border rows, so the consent card now has **zero** painted edges. Real scope is **5** SURFACE-backed selectors, not the 21 the "every hairline" framing implies. |
| **2** | R2-C3 | **Square off the receipt card's corners.** | **Rule C1 first.** With borders invisible, the 10px radius is the card's *only* remaining boundary — two squared receipts would merge into one grey field. Trap: there are **two** `QWidget#DsCard` rules, later wins. |
| **3** | R2-C2 | **A per-turn receipt line.** Today every tool call collapses into a session mean and each overwrites the last. | Needs **two** words: ship-or-not, *and* explicitly that it lives in scroll content, not fixed chrome. Do not skip the second as obvious — the nearest sibling is fixed chrome, so an implementer copying the local idiom builds the expensive version: **−73 to −87px** against BC-5. |
| **3** | R2-C4 | **Turn numbers in the transcript.** | The Undo button currently asks the model to verify an identity it was never given. Recommendation on file twice for the zero-pixel fallback. |
| **3** | R2-D1 | **The faces stack is 30–54px too tall** at the panel's declared 400px minimum. | **An assignment, not a design call** — the contract has `passing: false` and no `owner:` on any failing feature. One word: who owns page 0. |
| **3** | R2-D2 | **A ratified contract points at a deleted feature** — R3-01 names a verb rail that F1 retired. | Ask for a re-measurement *first*: the 393 that R3-01 ruled on included the rail's 237px. Also literally unowned. |
| **4** | R2-misc | Naming collision (Palette / Commands), "Connect" → "Bridge", hidden-widget deletion. | Cheap, but none safe to assume: *a crit is not a ruling*. The hidden-widget item needs scoping first — three of the six have live readers and deleting them breaks the overflow menu. |

---

## Round 1 — 2026-09-05 · `harness/design_review/2026-09-05/`

The original Pentagram-practice review — `REVIEW.md`, the direction comps, the type and rhythm
censuses. Its findings were largely absorbed by Rounds 2 and 3, which re-measured them on better
instruments. **It ranks last not because it is least important but because it is least current**:
several of its numbers were taken before the AA ramp and the mono unification shipped, and ruling
against a stale baseline is how a "yes" quietly reverses a shipped fix.

| Priority | # | The call |
|---|---|---|
| **2** | R1-Dir | **Direction A or Direction B** — keep the blue/warm identity, or let Houdini's yellow become the accent. Unblocks three items. Direction B requires superseding J1/J3, pinned by four test files. **The Direction B description needs refreshing before it goes to you** — it describes Consolas mono and the pre-AA grey ramp, both changed in v5.73.0. |
| **3** | R1-Bold | Should the SYNAPSE speaker name be bold while YOU stays 500? Filed and declined by the room. |

---

## What shipped already, so it is not re-litigated

v5.73.0 (tagged 2026-09-16) carried the last batch: the four measured readability defects
(`85c8fe29` — a unit, a fill, the quiet ramp, four weights), one type scale 11/12/15/19 and one
action family SIGNAL (#100), the gate card phrases (#99), DsStop's hover (#102), and the CRIT copy
pass with one mono (`7f2fa460`). All four `design/*` branches were squash-merged; the local copies
are stale leftovers, not pending work.

v5.74.0 contained **no panel code at all** — documentation and tests only.

---

## The order I would take them in

1. **R2-A1** — one word, four items unstick. Nothing else has that ratio.
2. **R3-A + R3-B together** — the type ramp and what carries quiet. One breath, or two half-answers.
3. **R2-B1** — the yellow. Most things queue behind it, and the measurement is now settled.
4. **R2-C1 → R2-C3** — borders then radius, in that order; the second depends on the first.
5. Everything else, once those four have cleared the queue they are blocking.
