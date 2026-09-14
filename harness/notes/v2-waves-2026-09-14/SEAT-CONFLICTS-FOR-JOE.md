# Two seat failures that are rulings, not bugs

**Date:** 2026-09-14 · **Found by:** unblocking the panel seat suite
**Status:** BOTH GATE JOE. Nothing was changed for either. Branch is clean.

The seat suite now runs (201 passed, 5 failed, 76s, where it used to hang
forever). Two of the five failures are **collisions between rulings you already
made.** Each was first diagnosed as a product defect with a one-line fix, and an
adversarial pass inverted both. The fixes would have reversed a ruling to green
a test.

---

## Conflict 1 — the Doctor button's yellow vs "monochrome plus one accent"

`test_chat_face_monochrome_one_accent_plus_state_marks` · `test_bc_wave.py:329`
`assert len(rest) <= 3` → `('curious', [0, 2, 13, 14])`

The fourth hue is the **Doctor** button, `HOUDINI_TAB_YELLOW #B98620`, hue 40°.
Producers: `synapse_panel.py:1042` sets `tone="doctor"`, `qss.py:198` colours it,
`tokens.py:255`. Measured pixel-by-pixel: 139 px of it on the resting CHAT face.

**Why it is not simply a defect.** `tests/test_panel_sweep_a.py:172-174` calls it
*"the **artist-approved** Doctor accent"* and pins the exact declaration under
`assert prefix.count(rule) == 1`, with a mutation guard at `:229` that fails if
the selector is broadened.

So the two obvious fixes are both wrong:

- dropping the QSS rule **fails that existing pin** (`count == 1` → 0);
- deleting the `setProperty` line leaves the pin textually green over a rule that
  matches no widget — a guard that stops measuring what it exists to measure.

**The conflict:** sweep-A's approved Doctor accent versus BC/J1's *monochrome +
one accent + state marks*. Both are yours. Neither leg can be cut without you.

**One thing worth knowing before you rule.** The instrument is coarser than the
rule it enforces. The test's docstring names the allowed set as three *tokens*
`{WARM, CONIFEROUS, SIGNAL}`, but SIGNAL at 210.8° and its own sanctioned ink at
205.7° straddle a 15° bucket boundary, so the ink silently consumes one of the
three slots. Even with the Doctor yellow gone, `rest` sits at exactly 3 with
**zero headroom**, against a stated design intent of two accents
(`tokens.py:225`). The pin is doing its job by luck as much as by design.

---

## Conflict 2 — J5's edge air vs BC-5's airy share

`test_profile_row_retired` · `test_bc_wave.py:627`
`assert share >= 0.5` → `('curious', 367, 0.48289)` — the transcript gets 48.3%
of 760 at airy, needs 50%. **13 px short.**

The first diagnosis convicted `rhythm.py:84-86` of violating
`docs/PANEL_RHYTHM_SPEC.md:109` (*"contents margins… never scale"*). **Provenance
inverts that:**

```
rhythm.py:44-50   "Edge condition (Joe's five, J5, 2026-09-05): a shell that meets
                   the pane's TOP edge takes one grid step more air above ...
                   density-scaled through tokens.gap (24/16/12)"
  d46a061a  2026-09-05 18:41  design(j5): air above the identity row
  c9b1216c  2026-09-05 11:52  (last touch of PANEL_RHYTHM_SPEC.md)
```

**The spec is 6 hours 49 minutes older than the rule it supposedly forbids.** The
scaling is not a bug in routing a margin through `gap()`; it is J5's stated
mechanism, and the exact 24/16/12 triple is written into the comment. The §4
table cited against it predates the exception and never absorbed it.

**The conflict:** J5 grants airy 8 px more chrome at the top edge; BC-5 requires
the transcript to hold half of 760 in every density. At airy both cannot be true,
and the gap is 13 px.

**Also worth knowing:** J5's commit says it delivered *"wordmark top y 8 → 16"*,
and **nothing pins that.** `test_wordmark_lockup_measured` checks font size, the
horizontal gap, and non-elision — no vertical assertion. So any fix that reclaims
the header's top air silently undoes J5 and the suite stays quiet.

**Your options, as I read them:**

1. J5 outranks BC-5 at airy → give airy its own share figure, the way the docking
   width already has its own 393 (`PANEL_RHYTHM_SPEC.md:83`, *"Joe's word,
   editable as that one figure"*).
2. BC-5 outranks J5 → J5's edge air goes fixed or goes away, and something should
   pin the wordmark y so the next change is not silent.
3. Neither moves → the test records a known, accepted conflict rather than a red.

I did not pick one. A proposal that cleared it by 3 px was on the table and I
rejected it: clearing a ratified floor by three pixels by spending a ratified gap
is a number being met, not a defect being fixed.

---

## The other three failures, for completeness

Not rulings; not diagnosed here; recorded as named and open:

```
tests/panel/test_failure_trail.py::test_dead_verb_hidden
tests/panel/test_j1_token_liveness.py::test_connected_keyed_engine_is_live_then_working_then_live
tests/panel/test_j2_token_face.py::test_face_counts_an_ollama_task
```

`test_dead_verb_hidden` is worth a note: it was previously believed to be a
branch-local red carried by the Panel PD wave. It fails here on clean master
under real Qt, so that belief was wrong.
