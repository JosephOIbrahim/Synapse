# Design crit 2026-09-14 — decision brief

**Written:** 2026-09-14, against master `8ad347a1`
**What this is:** the crit said *"nothing here has been built"* and listed five claims as
code-verified but never driven. The seat suite was unrunnable at the time — it hung on a
modal — so those probes could not run. It runs now. **Four of the five were measured.**

**Nothing in the crit has been built. Nothing here proposes building it.** Every design
call below is still yours. What changed is that they are now decidable.

---

## The roster grew, and it grew because blockers cleared

The crit ends §8 with *"Two decisions cannot be put to him yet … both blocked on a probe
that has never run."* Both probes ran. **The roster is 8 live decisions, not 6.**

---

## What the measurements closed

**The consent card's chroma — CLOSED, clean.** The rebuilt card measures **0.19 %
chromatic pixels across 2 hue buckets**, against a restraint floor of 0.82–0.84 % and a
3-bucket ceiling. The old card was 3.15 % / 12 buckets. It is now the most restrained
surface in the panel, **4.3× under** its own floor. F4's colour half needs no ruling.
*The method was validated before it was trusted: re-run against the untouched 2026-09-05
baseline it reproduced that review's published 0.84 % to the pixel.*

**F4's verb half — NOT a live defect. Re-file as latent.** The crit says `mark_decided`
hides `_revert_btn` *"including on REVIEW's auto-resolve path."* Driven, ×3 profiles:
**0 `mark_decided` calls, 0 `_on_remote_decision` calls, 0 `HumanGate.decide` calls.** A
REVIEW card is built with no approve button, no reject button and no countdown timer —
and those are the only three routes in. The question you are actually handed is *"do we
guard a verb that nothing currently removes?"* — different decision, different urgency.

**The turn receipt clears on send — MEASURED.** REVERT count 1 → 2 at the receipt → 1
after a second send, 3/3 profiles. §4.3's blocker is discharged; its design question
survives.

---

## What the measurements escalated

**D1's prerequisite came back RED — and it breaks D1's own framing.**

D1 asks *"is airy red at HEAD?"* and treats the answer as the gate on retiring the
density axis. Measured:

```
faces region minimumSizeHint height, against a flat 400px bound
  airy      454px   (+54)
  standard  438px   (+38)
  tight     430px   (+30)
```

**All three densities are red, and the axis is height, not width.** Density moves the
number 24px across its whole range against a 54px breach — **no surviving density clears
it.** D1 was written as a gate on the retirement; it is an independent red the retirement
cannot dispose of. It needs a named owner either way: page 0 of the faces stack.

**R3-01's remedy no longer exists.** `docking-minimums.yaml` carries your ruling with the
named fix *"a verb rail that collapses to icons below ~360px."* F1 retired the verb rail.
Its option (b) is dead, option (a) is widening a bound, option (c) — a narrower gutter —
is the only one left standing. Superseding R3-01 takes its own ruling artifact.

---

## The one question that unblocks the most

> ### Does airy **bind**, or is it **specification**?

Answered *specification*, four collisions stop being collisions in the same sentence:
D4's +12px becomes an annotation, SYSTEM's airy seam cost stops competing with BC-5,
BC-5's 13px red becomes a specification note with an owner, and D1's own 454 stops being
the worst of three figures.

Answered *binds*, all four become hard blockers that have to be paid in pixels — out of
the same three faces that are already 30–54px over their height bound at **every** density.

**What it does not unblock**, so it is not oversold: the `row` KeyError below (a product
defect, not a design call), and D4-vs-J5, which is live at standard whatever airy turns
out to be.

---

## One item on this file is NOT yours — it is a live product defect

**Deleting `ROLE_GAPS["row"]` raises `KeyError` on every grouped message in the
transcript.** Both F12 options delete it.

```python
# python/synapse/panel/chat_display.py:183
bf.setProperty(QtGui.QTextFormat.UserProperty, "row" if grouped else "group")
# python/synapse/panel/chat_display.py:190-191
if role in ("group", "row"):
    bf.setTopMargin(t.gap(rhythm.ROLE_GAPS[role], density))
```

Hard index, no `.get()`, no fallback. The crit's evidence for the deletion being free was
*"zero Python set-sites for `rhythm_role="row"`."* That grep is correct **and scoped to
the wrong mechanism** — `row` is consumed as a QTextDocument *block* role, which no
`rhythm_role` grep can reach. Two tests pin it too
(`test_panel_rhythm_owner.py:233`, `test_panel_camera_rhythm_qt.py:201`).

The `card` half is clean exactly as filed: two set-sites, both already `SPACE_GRID[3]`,
zero pixels move.

**This is a prerequisite for either F12 option and it is not gate joe.** Whoever goes
first remaps `chat_display.py:190-191` in the same commit.

---

## Two corrections to the crit's own framing

**SUBTRACT and SYSTEM are not mutually exclusive.** The README says *"only one can land;
whichever merges second silently overwrites the first."* `SCAFFOLD.html` §7 ruling 3
supersedes that **inside the same document** — *"both, in order."* SUBTRACT's deletion set
is a strict prefix of SYSTEM's. They conflict in merge text, not in design. The README's
sentence is the pre-crucible framing and was never updated.

**J5 and BC-5 were already reconciled — at one density.**
`tests/panel/test_j5_rail_air.py:139-148` carries BC-5's own predicate inside J5's test:

```python
# BC-5's measured goal still holds with the rail 8px taller
share = p._chat.height() / H
assert share >= 0.5, (p._chat.height(), share)
```

That panel is `_panel("expert")` — **standard only.** So this was settled deliberately on
2026-09-05, and **the airy failure is the density the reconciliation skipped**, not new
evidence against J5. That is a materially smaller claim than "two rulings collide."

---

## The order the dependencies permit

Stated as a constraint graph, not a recommendation:

1. **You answer the airy question.** Nothing on `rhythm.py` is safely orderable before it.
2. **The `row` remap** — prerequisite for both F12 options, not gate joe.
3. **SUBTRACT-`card` alone**, the genuinely free zero-delta commit.
4. **BC-5's airy reconciliation**, if airy binds — it sets the budget steps 5–6 spend.
5. **SYSTEM's table and D4's `_EDGE_TOP` as one ratified commit.** Separable in code, not
   in effect: both spend the same vertical budget on the same three faces, and pricing
   either alone gives a number the other invalidates.

---

## The cheapest unrun probe left

**BC-5's headroom at standard is UNMEASURED.** `test_j5_rail_air.py:148` proves the
assertion passes but prints no margin. D4 costs +8px at standard. **If that margin is
under 8px, D4 turns BC-5 red at standard too** — independent of the airy question, and
nobody has looked.

---

## Two gate-joe items that no finding names

Both surfaced by driving the panel rather than reading it, both change what the artist sees:

- **Two visible `← REVERT` controls on the CHAT face at once** — the receipt's and the
  card's. Same label, same consent slot, different scopes. 3/3 profiles.
- **`UNDO SENT` is authored and hidden in the same beat.** The tag merged today in
  `5424853a`; on the sent path the card settles and `_sync_consent_slot` retires it. That
  is the documented design — but it means an honesty fix may never reach the screen. Worth
  your eye, not a defect claim.

---

## What is still genuinely blocked

**The live dock at 340 beside the network editor.** Everything above is offscreen. Whether
the host offers the floor, and how the pane behaves at it, needs a seat with a GUI. It was
on the crit's GUI gate list and it stays there.

---

## Producers

```
harness/notes/v2-waves-2026-09-14/probe_f2_pixels.py   <tree>   # the rail's pixel floor
sed -n '26,50p'   python/synapse/panel/designsystem/rhythm.py
sed -n '175,195p' python/synapse/panel/chat_display.py
sed -n '105,175p' tests/panel/test_j5_rail_air.py
export SYNAPSE_HYTHON="C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe"
python .synapse/hytest.py tests/test_panel_rhythm_docking.py --tb=short
```

Every number in this brief was measured under hython 22.0.400 offscreen with the bundled
fonts loaded, at devicePixelRatio 1. HiDPI behaviour is UNKNOWN and was not inferred.
