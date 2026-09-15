# The open design roster — 16 calls, all yours

**Date:** 2026-09-14 · **Against:** master `67625294` (v5.70.0 shipped) · **Status:** NOTHING BUILT

This file is a decision surface, not a proposal to build. Every entry is a question that
has been measured as far as measurement can take it and now needs your word. No code in
this PR touches `python/`.

---

## How to rule

Reply on the PR with the item id and your word. One line each is enough:

```
A1 ratify
B1 keep the accent, retarget the pin
C4 fallback
```

Anything you don't name stays open. **You are not expected to clear all sixteen.**

---

## If you only do one thing

**Rule A1.** It is the head of the chain: A1 gates B2, B2 gates A2, and A3 is a
conditional guard on A1. Answering it does not close them, but nothing downstream can
move until it is answered.

---

## The roster at a glance

Sorted by what the item costs *you*, not by importance.

### RATIFY — recommendation on file, one word closes it

| | item | the ask |
|---|---|---|
| **A1** | Airy is specification, not binding | supersede the contract lines |
| **A3** | Bar D1 from the airy reclassification | in writing |
| **A4** | Add the pin J4 lacks | `_select_profile` has zero production callers |
| **C5** | One counter, and it is the turn | four lenses converged unprompted |
| **C6** | The squared corner survives R6; the bleed does not | the filer already withdrew the bleed |

### FORK — a real choice, both legs have a cost

| | item | the tension |
|---|---|---|
| **B1** | Doctor yellow vs monochrome + one accent | two of your own rulings |
| **B2** | J5's edge air vs BC-5's airy share | two of your own rulings, 13px apart |
| **C1** | BORDER == SURFACE | record it, or rule it |
| **C2a** | The per-turn receipt line — ship it? | ships an audit texture that can't be turned off |
| **C2b** | Where the receipt lives — scroll content or widget? | the tree pulls toward the answer that costs 73–87px |
| **C3** | Square the receipt's corner | a card that stops reading as *waiting for you* |
| **C4** | The turn ordinal | 22–26px of a 264px column, or 0px and no scannability |

### ASSIGN — not a choice, a missing owner

| | item |
|---|---|
| **A2** | Encode BC-5's airy deficit as a number with an owner |
| **D1** | The faces-stack 400px red — red at **every** density, owner unnamed |
| **D2** | R3-01's remedy no longer exists — supersession needs its own artifact |
| **D3** | Two visible `← REVERT` controls on CHAT at once |
| **D4** | `UNDO SENT` is authored and hidden in the same beat |

---
---

# A · Airy, and the contracts that never got the memo

## A1 — Airy is specification, not binding **[RATIFY]**

**You already ruled this.** 2026-09-05, J4: profiles retired, composed profile is always
`expert`, machinery stays so it can return with a real difference. The code has enforced
it since. What is open is that several **contracts and suites** still treat airy as a
binding target.

**Verified four ways at `c217428b`:**

- `synapse_panel.py:732-733` hard-sets `profile = DEFAULT_PROFILE`, and the ordering is
  load-bearing — the persisted read at `:618` is overwritten at `:733` *before* the sole
  `compose()` at `:737`. The settings route is dead on arrival.
- `_select_profile` — the only route to `_recompose` — has **zero callers** in `python/`.
- `curious.py:44` is the only manifest carrying `"density": "airy"`, and it is never
  composed. Complete originator set: **one line**, `compositor.py:254`.
- No env var. Every other density writer propagates from an ancestor and defaults to
  `"standard"`.

**The precise wording, because "unreachable" is too strong:**

> Airy has no artist-reachable UI affordance and cannot be reached by settings, env, or
> any alternate entry point. The composing machinery stays public and live-callable —
> `houdini_execute_python` is ungated on the live path, so one chat message can reach
> `panel._select_profile("curious")`. **Dormant configuration, not deleted capability.**

**What it buys: one collision, not four.** An earlier framing of mine oversold this and
is corrected on file. Only BC-5's airy red genuinely dissolves. D4's airy figure is
*downgraded* (from a pixel budget to a spec value you still pick). SYSTEM's shell 16→24,
D4-vs-J5 at standard, the `row` deletion trap and D1 were **never airy problems** and
survive untouched.

**→ Ratify:** airy is specification, in an artifact that supersedes the affected contract
lines — not only in code.

---

## A2 — Encode BC-5's airy deficit **[ASSIGN]**

Whatever B2 decides, the number has to land somewhere that carries an owner.

```
curious  density=airy      chat=367px   share=0.48289   headroom  -13.0px   FAIL
expert   density=standard  chat=407px   share=0.53553   headroom  +27.0px   PASS
ml       density=tight     chat=427px   share=0.56184   headroom  +47.0px   PASS
```

Composed at 340×760, 35 font families loaded, using `test_bc_wave`'s own helpers so the
method cannot drift from the assertion it mirrors. The airy row reproduces the known seat
failure exactly — 367 / 0.48289 — which validates the method against a figure nobody
chose for it. Producer: `bc5_headroom.py`, hython 22.0.400 offscreen.

**→ Assign:** a density-conditional assertion carrying **−13px** and a named owner.
**Never delete the branch** — J4 says *"tests still exercise it,"* and a deleted airy
branch violates J4 by name.

---

## A3 — Bar D1 from the reclassification **[RATIFY]**

D1's red is at **standard too**. It is not an airy artifact and must not ride A1's
coattails into "specification".

```
faces region minimumSizeHint height, against a flat 400px bound
  airy      454px   (+54)
  standard  438px   (+38)
  tight     430px   (+30)
```

Density moves the number 24px across its whole range against a 54px breach. **No
surviving density clears it.**

An adversarial pass argued the bound is really `PANEL_MIN_HEIGHT = 420`, which would
shrink the breaches to +34/+18/+10. **Checked, and wrong** —
`tests/test_panel_rhythm_docking.py::_bounds` deliberately reads the YAML contract and
says so in a comment, with a test named
`test_docking_bounds_read_the_contract_not_panel_height_token` asserting the contract
figure is the *stricter* of the two. 400 is on purpose. (The attacker's own re-measure
also reported `QFontDatabase.families() == 0`, and RULING-2A says a figure taken with an
empty font database is not a measurement.)

**→ Ratify:** D1 is explicitly excluded from the airy reclassification.

---

## A4 — Add the pin J4 lacks **[RATIFY]**

J4's existing pin proves the persisted-settings route is dead and the machinery survives.
It does **not** pin that `_select_profile` has zero production callers — only a code
comment guards that today.

**→ Ratify:** add the missing assertion. Cost: one test, zero pixels.

---
---

# B · Two seat reds that are rulings, not bugs

Both were first diagnosed as product defects with one-line fixes. An adversarial pass
inverted both: **the fixes would have reversed a ruling to green a test.** Nothing was
changed for either.

## B1 — The Doctor button's yellow vs "monochrome + one accent" **[FORK]**

```
tests/panel/test_bc_wave.py::test_chat_face_monochrome_one_accent_plus_state_marks
test_bc_wave.py:329    assert len(rest) <= 3  →  ('curious', [0, 2, 13, 14])
```

The fourth hue is the **Doctor** button — `HOUDINI_TAB_YELLOW #B98620`, hue 40°.
**139px of it** on the resting CHAT face, measured pixel by pixel. Producers:
`synapse_panel.py:1042` (`tone="doctor"`), `qss.py:198`, `tokens.py:255`.

**Why it isn't simply a defect.** `tests/test_panel_sweep_a.py:172-174` calls it *"the
**artist-approved** Doctor accent"* and pins the exact declaration under
`assert prefix.count(rule) == 1`, with a mutation guard at `:229` that fails if the
selector is broadened. So both obvious fixes are wrong:

- dropping the QSS rule **fails that existing pin** (`count == 1` → 0);
- deleting the `setProperty` line leaves the pin textually green over a rule matching no
  widget — a guard that stops measuring the thing it exists to measure.

**Know this before you rule: the instrument is coarser than the rule it enforces.** The
test's docstring names three allowed *tokens* `{WARM, CONIFEROUS, SIGNAL}`, but SIGNAL at
210.8° and its own sanctioned ink at 205.7° **straddle a 15° bucket boundary**, so the ink
silently eats one of the three slots. Even with the Doctor yellow gone, `rest` sits at
exactly 3 with **zero headroom**, against a stated design intent of two accents
(`tokens.py:225`).

And this is **not a SYNAPSE defect** — running the same instrument over the Pentagram
Cohere board, its PARAMETERS column measures 5.79% chroma across exactly two meaningful
buckets, `[18, 19]`: a **single orchid accent split across a 15° boundary**. The same
artifact, in reference work. One of your four buckets is the instrument, not the design.

**Options**

1. **Keep the accent, retarget the pin** — the monochrome rule counts *tokens*, not
   buckets, and the test is rewritten to measure what it names.
2. **Drop the accent** — and sweep-A's pin is superseded in the same commit, not left
   green over a dead rule.
3. **Record as an accepted conflict** — the test asserts a known figure rather than a
   goal.

**→ My read:** (1). The measurement says the rule was never really about bucket count, and
fixing the instrument is cheaper and more honest than spending one of your rulings.

---

## B2 — J5's edge air vs BC-5's airy share **[FORK]**

```
tests/panel/test_bc_wave.py::test_profile_row_retired
test_bc_wave.py:627    assert share >= 0.5  →  ('curious', 367, 0.48289)
```

The transcript gets 48.3% of 760 at airy and needs 50%. **13px short.**

The first diagnosis convicted `rhythm.py:84-86` of violating
`docs/PANEL_RHYTHM_SPEC.md:109` (*"contents margins… never scale"*). **Provenance inverts
that:**

```
rhythm.py:44-50   "Edge condition (Joe's five, J5, 2026-09-05): a shell that meets
                   the pane's TOP edge takes one grid step more air above ...
                   density-scaled through tokens.gap (24/16/12)"

  d46a061a   2026-09-05 18:41   design(j5): air above the identity row
  c9b1216c   2026-09-05 11:52   last touch of PANEL_RHYTHM_SPEC.md
```

**The spec is 6 hours 49 minutes older than the rule it supposedly forbids.** The scaling
isn't a bug in routing a margin through `gap()` — it is J5's stated mechanism, and the
exact 24/16/12 triple is written into the comment. The §4 table cited against it predates
the exception and never absorbed it. *(That reconciliation shipped today in
`PANEL_RHYTHM_SPEC.md` §4.1.)*

**Also worth knowing:** J5's commit says it delivered *"wordmark top y 8 → 16"*, and
**nothing pins that.** `test_wordmark_lockup_measured` checks font size, horizontal gap
and non-elision — no vertical assertion. Any fix that reclaims the header's top air
**silently undoes J5** and the suite stays quiet.

**Options**

1. **J5 outranks BC-5 at airy** → airy gets its own share figure, the way docking width
   already has its own 393 (`PANEL_RHYTHM_SPEC.md:83`, *"Joe's word, editable as that one
   figure"*).
2. **BC-5 outranks J5** → J5's edge air goes fixed or goes away, **and** something pins
   the wordmark y so the next change is not silent.
3. **Neither moves** → the test records a known accepted conflict rather than a red.

**→ My read:** (1), and it is the same act as A2. A proposal that cleared the floor by 3px
was on the table and I rejected it: clearing a ratified floor by three pixels by spending
a ratified gap is a number being met, not a defect being fixed.

---
---

# C · The Cohere refinements

Four lenses filed against the Pentagram Cohere board, critiqued each other by name, and
conceded five times. Full round: `REFINEMENT-COHERE.md`.

> **R1 and R2 are CLOSED — they shipped in v5.70.0 today.** The tool-label fallback and
> the four dead curated keys, with the registry-reading guard R2's conditions demanded.
> They are struck from this roster.

**The vertical budget, for everything below:**

```
reserve (standard density)               +27px
R3  no pixel proposal                       0
R4  receipt, as scroll content              0     ← conditional, see C2
R5  squared corner                          0, or −2 (a gain)
R6  turn ordinal                            0
                                         -------
remaining                                +27px, or +29px
```

They fit. The reason is uniform and worth stating: **every one had an "obvious" placement
that would have landed in fixed chrome, and all four refused it independently.** The
distinction that makes the zero real: *the +27px is pane geometry — fixed chrome versus
the transcript's share of 760. Scroll content does not draw on it.*

---

## C1 — BORDER == SURFACE **[FORK]**

`tokens.py:139` — `"surface": step(12)` and `"border": step(12)`, identical by
construction at every host seed. Pinned by the tree's own fixture at
`tests/panel/test_theme_source.py:54` (both `#363636`).

**Every hairline on every card in this panel is invisible against its own fill.** The
card's outer border, `#DsCardHeader`'s border-bottom, `#DsCardBody`'s — all of them.

It was filed as evidence, not a request; two critics said it should be a ruling, and the
argument is short: **the reference's "unsoftened edge" is unreachable while the panel has
no edges at all.** This is not a softening problem — it is a missing-edge problem.

Cost to state: 0px, 0 buckets. Cost to fix: **unpriced** — nobody proposed a fix.

**→ Fork:** record it as a known finding, or rule it and have someone price a fix. It
also changes C3's stakes — see there.

---

## C2a — The per-turn receipt line **[FORK]** · *ship / don't ship*

One line appended to the tail of every turn that **mutated the scene**. Read-only turns
get nothing.

```
   Undoable                      mcp · 4/4
```

Plain word first, technical second, right-aligned tabular. Three verdicts:
`Undoable` / `Partial` / `Not recorded`. Exactly one row governs, marked in **value**
(TEXT_PRIMARY against TEXT_TERTIARY), never hue.

**The finding underneath it is the best observation of the round and stands independent of
the proposal.** `claude_worker._track_integrity` records **one integrity dict per tool
call** into `SessionIntegrityTracker._blocks` (`session_integrity.py:46,56`).
`integrity_readout` collapses the whole list into `"fidelity 100% · N verified"` —
session-scoped, both branches. `face_work.set_tool_status` does a bare `setText`
(`face_work.py:266`), so each tool call overwrites the last.

> **SYNAPSE's differentiator is per-action receipts, and the panel shows a session mean.**
> The data is recorded. The surface throws it away.

## C2b — Where the receipt lives **[FORK]** · *scroll content / widget*

**This one needs your word either way, because the tree pulls the wrong direction.** R4's zero is purchased *entirely* by living in scroll content. The
nearest pattern in the tree (`GateWidget`, in the same layout) pulls an implementer toward
the expensive answer:

```
reserve                                          +27px
R4 as a widget, collapsed          −18 to −19  →  +8 to +9px left
R4 as a widget, expanded          −100 to −114  →  −73 to −87px
```

**BC-5 would fail by 73–87px the first time the artist clicked a chevron.** And HTML
expansion means `insertHtml` mid-document, which the file's own comments
(`chat_display.py:27`, `:502`, `:611`) call an O(document) re-layout **on an instrumented
freeze surface** — the cost moves from pixels to latency on a path with a freeze ledger.

**Costs if it ships**

| | |
|---|---|
| px, fixed chrome | **0** under the placement ruling |
| px, scroll content | **+18–19px per mutating turn** (UNKNOWN on the exact Qt line box; 13–14px is derived from `SIZE_MICRO=10`, not measured) |
| buckets | **0** |
| scrollback | **~30% fewer visible mutating turns** — 4.4 → 3.1 in a 380px transcript |
| artist cost | a permanent low-grade audit texture that can't be switched off without making receipts invisible again |

**Two language problems, both open**

1. **"Not recorded" is already spoken, one row down.** `gate_widget.py:360` ships
   `_show_decision_tag("NOT RECORDED")` for *a decision that never reached the gate*. The
   receipt's verdict means *this op produced no integrity block*. Same two words, two
   scopes, one nested in the other.
2. **"Undoable" reads both ways in English.** *Un-doable* = cannot be done. CLAUDE.md §1.8
   mandates the word — but mandated it **in a sentence**, where the ambiguity can't bite.
   As a standalone 10px verdict on a dark ground it is the one word most artists will ever
   read.

**→ Fork.** And whichever way it goes: **rule the placement explicitly.** Leaving it in a
filing's UNKNOWN is how the expensive version gets built by accident.

---

## C3 — Square the receipt's corner **[FORK]**

`RADIUS_CARD = 10` (`tokens.py:546`) rounds all four corners of `#DsCard`, so the
GROUND→SURFACE boundary is never a straight line and the block reads as a floating object
rather than a band of different ground. Set radius 0 on an in-flow variant. **Value does
the separating; straightness is what makes the eye read "region" instead of "object."**

Cost: **0px**, or **−2 on the contested ledger** if the no-op border goes with it — the
only proposal in the round that *returns* pixels, found without knowing the ledger was
contested.

**The trade cuts against the card's job.** A consent card exists to **get a decision**.
Roundness is part of why it reads as *waiting for you*. Square it and it reads as a log
entry — sitting directly above the composer, where chrome is what the eye stops seeing.

**And it is entangled with C1.** Given BORDER == SURFACE, the radius is not one of the
card's few boundaries — **it is the only one.** Two stacked square receipts with an
invisible border and ΔL* 11.6 don't get a faint seam; they get one continuous grey field.

**→ Fork.** Rule C1 first if you can; this one's stakes depend on it.

---

## C4 — The turn ordinal **[FORK]**

A session ordinal in the existing unpainted spacer cell of `_ruled_turn`, right-aligned
mono, `TEXT_TERTIARY`, **right of the 2px speaker rule.** The placement is the most
disciplined decision in the round — putting it left of the rule would read closer to
Cohere and would make J3's own sentence a lie.

**What it buys.** `synapse_panel.py:2315` is the evidence — and the code already knows the
problem. The REVERT verb sends *"Undo the last change using houdini_undo"*, then, when it
has an operation name, hedges in the prompt itself: *"the change I mean is the %s you just
ran; if the last undo step is a different change, say so instead of undoing it."* **The
referent is recency, and the prompt asks the model to check identity it was never given.**
With an ordinal it can be given: *"Undo the change made in turn 14; if the last undo step
belongs to a different turn, say so instead of undoing it."*

**What it does not buy:** the undo is still one global step. The ordinal makes the
*request* addressable, not the *undo* targeted.

**The horizontal cost is contested three ways** — all from the same confirmed fact,
`cellpadding="0"`:

| source | cell | delta | reasoning |
|---|---|---|---|
| ORDINAL | 22px | −8 | 3 mono digits |
| LANGUAGE | 26px | −12 | Space Mono 0.6em → 18.0px for 3 digits, +4 air, +4 slack. *22px has zero slack; the failure boundary is turn **100**, not turn 1000.* |
| GROUND | 24 / 34px | −10 / −20 | 4px rule-gap + digits + 8px body-gap. *ORDINAL priced the digits and not the gaps.* |

Against a base body column that is itself contested — **264px** (340 − 2×GUTTER(30) − 16)
or **256px** (plus Qt's default 4px-per-side document margin; no `setDocumentMargin` call
exists). All three agree on the mechanism: right-aligned digits in a zero-padded cell sit
**flush against the prose**, so the air has to come from inline `padding-right` on the
`<td>` — and whether QTextDocument honours that is **unmeasured and load-bearing**.

**The transcript is already at 39 delivered chars against its own stated
`_MEASURE_CHARS = 90` — 43% of its own target measure.**

**Zero-pixel fallback:** append the ordinal to the timestamp — `● SYNAPSE  14 · 2:14 PM`.
**0px, 0 buckets, 0 assertions touched.** Buys *sayability* but not *scannability*.

**→ My read: take the fallback.** Not because the proposal is weak — its reasoning is the
best in the round. Because its cost is contested three ways and largest on the axis already
furthest below spec; its value is contingent on a behaviour nobody has observed (whether
you'd type "undo 14" with the REVERT verb sitting right there on the card); and its filer
conceded the load-bearing half of its own evidence — the claimed "second surface" doesn't
hold, since cards are per-**operation** and a turn raising three cards would stamp all
three "14".

---

## C5 — One counter, and it is the turn **[RATIFY]**

R6 counts **turns** (one per group head). R4 counted **integrity blocks** (one per tool
call). A turn running four tools is **14** to one lens and **07, 08, 09, 10** to the other.
Both cite the same reference principle. Both claim identity.

Ship both and *"undo 07"* is ambiguous — **the exact disease the principle exists to cure,
reintroduced by curing it twice.**

All four lenses converged on the same resolution, unprompted:

> **One counter. It is the turn** — because the turn is the unit the artist *speaks* and
> the unit the undo request names. The receipt cites `14.2` — turn, op — or nothing.

This resolves both filings' drop conditions in one move: R6 needed a second surface to cite
its number or the gutter is decoration; R4 needed an address it did not have to mint. **The
receipt line is R6's second surface.**

**→ Ratify.** Applies whichever of C2/C4 ship, including if neither does.

---

## C6 — The squared corner survives R6; the bleed does not **[RATIFY]**

R5's full-bleed and R6's gutter cannot both ship at full strength: a full-bleed receipt's
straight edge would run *through* the ordinal gutter and under the speaker rule.

The filer already withdrew the bleed, on two grounds: the 280px figure is the **rail's**
documented interior (`synapse_panel.py:907-908`) applied to the transcript without reading
the transcript's container — **UNKNOWN under Law 2** — and if the ordinal ships, body text
starts ~54px from the panel edge while a full-bleed receipt starts at 0, *arguing for
straightness while adding raggedness* on the narrowest surface in the product.

**→ Ratify the withdrawal** so it doesn't get re-proposed.

---
---

# D · Named, unowned

## D1 — The faces-stack 400px red **[ASSIGN]**

`+54 / +38 / +30` at airy / standard / tight. **Red at every density** (see A3). It was
written as a gate on retiring the density axis; it is an **independent red the retirement
cannot dispose of.**

**→ Assign:** page 0 of the faces stack, with a named owner. Not a design choice — a
defect with no one on it.

---

## D2 — R3-01's remedy no longer exists **[ASSIGN]**

`docking-minimums.yaml` carries your ruling with the named fix *"a verb rail that collapses
to icons below ~360px."* **F1 retired the verb rail.**

- option (b) — the named remedy — is **dead**
- option (a) is widening a bound
- option (c) — a narrower gutter — is the only one still standing

**→ Assign:** superseding R3-01 takes its own ruling artifact. It cannot ride A1.

---

## D3 — Two visible `← REVERT` controls at once **[ASSIGN]**

On the CHAT face: the turn receipt's and the consent card's. **Same label, same consent
slot, different scopes.** Reproduced 3/3 profiles. Surfaced by *driving* the panel rather
than reading it; no finding names it.

**→ Assign.** Changes what the artist sees; needs an owner and a decision about which one
keeps the word.

---

## D4 — `UNDO SENT` is authored and hidden in the same beat **[ASSIGN]**

The tag merged today in `5424853a`. On the sent path the card settles and
`_sync_consent_slot` retires it. **That is the documented design** — but it means an
honesty fix may never reach the screen.

**→ Assign.** Worth your eye. Not filed as a defect claim.

---
---

# Not on this list, and why

**The `row` KeyError is a product defect, not a design call.** Deleting `ROLE_GAPS["row"]`
raises `KeyError` on every grouped message in the transcript —
`chat_display.py:190-191` hard-indexes it from a QTextDocument *block* property, with no
`.get()` and no fallback. Both F12 options delete it, and **F12's own acceptance probe
greens on exactly the deletion that breaks the transcript.** Two tests pin the key
(`test_panel_rhythm_owner.py:233`, `test_panel_camera_rhythm_qt.py:201`). Whoever goes
first remaps those two lines in the same commit. **Not gate joe.**

**SUBTRACT and SYSTEM are not mutually exclusive.** The README says *"only one can land;
whichever merges second silently overwrites the first."* `SCAFFOLD.html` §7 ruling 3
supersedes that **inside the same document** — *"both, in order."* SUBTRACT's deletion set
is a strict prefix of SYSTEM's. They conflict in merge text, not in design. The README
sentence is pre-crucible framing that was never updated.

**The live dock at 340 beside the network editor is still blocked.** Everything above is
offscreen. Whether the host offers the floor, and how the pane behaves at it, needs a seat
with a GUI. It stays on the GUI gate list.

**Three seat reds are not rulings** and are not diagnosed here — recorded as named and
open:

```
tests/panel/test_failure_trail.py::test_dead_verb_hidden
tests/panel/test_j1_token_liveness.py::test_connected_keyed_engine_is_live_then_working_then_live
tests/panel/test_j2_token_face.py::test_face_counts_an_ollama_task
```

`test_dead_verb_hidden` is worth a note: it was believed to be a branch-local red carried
by the Panel PD wave. It fails on clean master under real Qt, so that belief was wrong.

---

## Measurement conditions

Every number in this file was measured under **hython 22.0.400 offscreen**, with the
bundled fonts loaded, at **devicePixelRatio 1**. HiDPI behaviour is **UNKNOWN** and was not
inferred. The seat suite must be run alone — it shares a rotating log handler with the
stock suite and the loser of that race reports a phantom failure.

**Sources:** `DECISION-BRIEF.md` · `AIRY-ANSWER.md` · `REFINEMENT-COHERE.md` ·
`../../notes/v2-waves-2026-09-14/SEAT-CONFLICTS-FOR-JOE.md`
