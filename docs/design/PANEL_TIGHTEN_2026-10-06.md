# Panel tightening · 2026-10-06

Three design rounds, run as part of the v5.95.0 hardening loops.

**The rule both rounds held:** subtract before you add, and prove every change by identity. Nothing on screen was meant to move. The composed stylesheet hashes the same before and after for three changes; the wordmark change is checked by QFont equality. The offscreen panel grab was compared for the radius and composer changes only.

---

## Where the principles came from

**The Pentagram case study for Cohere** (pentagram.com/work/cohere) was fetched and read. What the page says:

- **One idea carries the system.** Cohere's "new nature": the fluidity of nature meeting the rationality of computing. The symbol, the type and the palette all come from it.
- **Natural tones paired with synthetic ones.** Coniferous green, mushroom grey and volcanic black, with coral, quartz and acrylic blue.
- **Type is the identity.** A custom family with headline, outline, text and mono cuts. The mono cut is for code.
- **The system ships as tooling.** A Figma plug-in, component libraries and a Python tool for 3D.

**The page says nothing about grid, layout, motion or voice.** The principles below that touch those are Pentagram studio practice, not the Cohere case.

**The panel already carries Cohere by name.** The WARM coral, CONIFEROUS and MUSHROOM tokens come from it. Cohere's gradient atmospheres do not survive a dark Qt pane: the panel's gradient measured sub-perceptual and was removed earlier, and it is not proposed back.

---

## The principles, read on this panel

1. **One idea, carried by the system.** Monochrome restraint, one intelligent accent, warmth through type and voice.
2. **Two accents is the ceiling.** SIGNAL for connection and action, WARM for the agent's human moments.
3. **Type carries hierarchy before colour does.** Space Grotesk for words. Space Mono for data only.
4. **Contrast of scale beats a ladder of sizes.** The ramp stays at 12 / 15 / 19.
5. **One token authority.** A token nobody reads still teaches a size the panel never draws.
6. **Sit inside the host.** Grounds are seeded from the Houdini pane; the accent is earned.

---

## What shipped in v5.95.0

**Nine dead chat-layout tokens are gone** (`panel/tokens.py`). Nothing in the tree read them. One of them, a fourth "type size" of 18, contradicted the three-step ramp.

**The wordmark names its weight.** `weight=600` became `t.WEIGHT_BOLD`. Space Grotesk ships 400 / 500 / 700, and 600 already resolved to bold, so the font is identical.

**Three radius values name their tokens** in `designsystem/qss.py`: `#DsAuthor`, the gate body and the editorial `#DsStop` now read `RADIUS_LG` / `RADIUS_SM`. Raw radius literals left in the file: 30, held by a ratchet test.

**One composer builds the stylesheet.** Eight `stylesheet()` rebinds became plain section functions walked by one ordered tuple. The output string is byte-identical at every scale checked (0.75 to 2.25).

**Proof.** Each change has its own new test. The radius and composer changes match on composed-stylesheet hashes at six scales and on the offscreen panel grab. The token deletion matches on the stylesheet hash alone; the wordmark change on QFont equality at 1.0 and 2.25. The design reviewer and an adversarial reviewer each returned SOUND-WITH-NITS.

---

## Held back, and why

**An audit change was not shipped.** Round 2 also narrowed `audit_panel.py` so its font row reads only the stylesheet that ships. The output did not change, but it narrows what the gate measures. That needs Joe's sign-off, so it stays on its branch (`design/hour3-20261006`, commit `7e46da26`).

**Deleting the dead SWEEP_A blocks and `panel/styles.py`** needs existing test pins moved: `tests/test_panel_sweep_a.py`, `tests/test_hda_panel.py`, `tests/test_chat_panel.py` and two more. A loop may not edit an existing test. **Ruling needed:** permission to amend those pins.

**Four more radius and padding sites** wait on the same permission.

---

## Proposals that move pixels (Joe's eye)

| Move | What it does | Waits on |
|---|---|---|
| T2a | QSS weight 600 to the bold token at six sites | an ink-equality probe; if ink differs, renders |
| T3 | one tracking engine for every font role | renders at Aa 1.0 and 1.6 |
| T4 | labels and keys off mono, onto sans 500 | R3-B |
| T5 | drop inline letter-spacing from rich-text spans | R3-B; the probe showed Qt honours it (see round 3) |
| T6 | one font owner for the verdict label | R3-B, next to R1-Bold |
| M6 | press colour seeded from the host | renders on a dark and a light host |
| M7 | fold the model-picker's own radii and coral fill into the system | R2-C1, R2-C3, R1-Dir |

---

## Round 3: a probe said no

**T5 was tested before it was built, and the test refused it.** The proposal was to drop the inline `letter-spacing:1px` from three rich-text labels, on the belief that Qt ignores it. An offscreen probe at the real fonts shows Qt honours it: the grabs differ, and a 6px control proves the probe can see spacing.

**What the probe found instead:** on the RECEIPT and INTEGRITY eyebrows the span's 1px *replaces* the font's 112% tracking (73.0px against 71.45px on "INTEGRITY"). On the VIA row the span is the only tracking there is. So tracking has two owners today.

**Ruling R3-B, three options:**

- **A.** Keep the spans as they are.
- **B.** Drop them on RECEIPT and INTEGRITY only, so the font is the one owner there. About 0.83px per character instead of 1px. The design team leans B.
- **C.** Drop all three and give the VIA row the tracked font. That restyles a whole row and needs a fresh before/after.

---

## One thing to check

**`harness/design_review/RANKED.md` may be stale.** It lists R2-A1, R2-B1 and R3-A to R3-D as open. The panel legs that depend on them are merged, and the code cites those rulings as closed (`designsystem/tokens.py`, `designsystem/qss.py`, `chat_display.py`). Before the next design round, confirm which rulings are really open.

---

## Limits

- **Offscreen only.** Every render and audit ran under hython with Qt offscreen. Nothing was looked at in a live Houdini session.
- **`audit_panel.py --strict` is red before and after,** with the same rows: four model-token rows (the readout says "Sonnet 4.6", the audit expects `provider/short-id`) and two warnings. Which side drifted is a design call.
- **A design-token checker in `harness/notes/` now reports nine more missing names**, the deleted tokens. It was already red on v5.94.3.
