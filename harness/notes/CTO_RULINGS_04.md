# CTO RULINGS — CLOSEOUT-2026-09-15

**Ruled** 2026-09-15 · **Authority** Joe, "approved for the remainder … lets close out"
**Consumed by** the 2026-09-15 closeout (`harness/notes/closeout-2026-09-15/CLOSEOUT.md`).
These are decisions, not proposals. Where a ruling reverses or narrows the question as posed, the
reasoning is stated — a ruling that only answers the question asked is not doing the job.

---

## RULING 1 — `_MCPLocalClient.available`: the resilient contract STANDS. The test is re-aimed, not deleted.

**Posed:** #85 changed `available` so that losing discovery keeps the cached port instead of
clearing it. That contradicts
`tests/panel/test_doctor_button.py::test_transport_discovers_only_the_running_owner_and_tracks_reconnection`.
Which contract is right? Evidence: `harness/notes/release-5.71.0/SEAT_REDS.md`.

**Ruled: resilient.** Not because it is tidier — because the risk is asymmetric, and the asymmetry
is not close.

Strict costs an immediate, clean fallback. Resilient costs **one wasted round-trip** on an error
path, self-healing, with nothing rendering the flag (`available` has exactly one reader,
`tool_executor.py:772`, a pre-check before `call_tool` that falls back on `MCPUnavailable` anyway).

What strict would cost instead is the thing the change was made to avoid: an off-thread HOM probe.
This codebase has a documented class where `hdefereval`'s blocking marshal called from the main
thread self-deadlocks **permanently, every invocation, not a race**. One wasted request against a
possible unrecoverable hang is not a trade worth making for a tidier flag.

**Beyond the question.** The resilient contract is only safe *because* `_post` invalidates the
cached port on failure. **Nothing pins that.** Without it, "resilient" quietly degrades into "stale
forever, with no alarm" — which is strictly worse than the behaviour the test was protecting.

So the superseding test MUST assert the invalidation path, not merely the new caching behaviour.
Rewriting it to pin "discovery lost → port retained" and stopping there would ratify the risk and
delete the guard in the same edit. A test that cannot fail is decoration; a test that pins only the
convenient half is worse, because it looks like coverage.

Until that test exists, the red **stays red and stays named** in `SEAT_REDS.md`. Shipping it
documented, as v5.71.0 and v5.72.0 did, is the correct interim state.

---

## RULING 2 — PR #98: `_PANEL_BASE` is NOT re-anchored. Declared deltas instead.

**Posed:** #98 edits copy inside `_GrowingInput.__init__`, which `_PANEL_BASE = "47ffea0e"` pins.
The pin's own comment says that source stays byte-identical "unless a ruling says otherwise". A
ruling now exists. Re-anchor?

**Ruled: no.** The authority to move the pin is not the same as a reason to move it.

`_PANEL_BASE` is a literal precisely so it cannot compare the tree to itself — its comment says the
day it becomes `merge-base(master, HEAD)`, thirteen lifecycle pins go green regardless of edits.
Moving it so one branch passes is the same failure wearing a ruling as a hat. The previous
re-anchor (2026-09-05, Addendum 3) moved it because a *landing* redefined the baseline, not because
an edit wanted through.

There is already a better instrument, proved in this same wave. The type-ramp branch hit the
identical wall on the qss append-only guard and did not take a carve-out: it declared
`CRIT_20260915_QSS_AMENDMENTS`, a tuple of exact `(old, new)` text deltas applied to the baseline
before comparison, each asserted to occur **exactly once**. The guard keeps full strength — the
source must still equal baseline-plus-exactly-these-deltas, character for character; further drift
on the same rules still reddens; and a stale amendment reddens rather than silently no-opping.

#98 uses that. Spend the mechanism, not the ratchet.

**Beyond the question.** This generalises, and the generalisation is the valuable half: **declared
deltas are the default for any pinned-source change; re-anchoring is reserved for a landing that
genuinely redefines the baseline.** A carve-out list retires a guard permanently for that selector;
a declared delta retires nothing. Prefer the one that expires loudly.

---

## RULING 3 — `DsStop:hover`: restore hover feedback inside the one-family rule.

**Posed:** retiring `HOT_SOFT` (#100) left `DsStop`'s hover fill identical to its rest fill, so
hover feedback rides only on `:pressed`. Flagged by its own author as needing a ruling.

**Ruled:** point hover at the existing `WARM_HOVER` token. Hover is **state**, and the crit's own
principle is that state is carried in form rather than in a new hue — a second action hue would
undo exactly what #100 bought. Restoring the hover step inside the WARM family satisfies both.

**Beyond the question.** If no suitable hover token exists, this is not a repair and must stop:
inventing a colour is a design decision wearing a bug-fix label. Report and hold rather than pick.

---

## RULING 4 — Branch protection: required contexts ON, `enforce_admins` OFF.

**Posed:** `master` had no branch protection and `allow_auto_merge` false — zero required status
checks, so nothing structural stopped a red PR from landing.

**Ruled: enabled**, requiring the four `test (os, py)` matrix contexts, with `strict: false` and
`enforce_admins: false`.

Each of those three is a decision, not a default:

- **Required contexts** — the gate held all day only because a person was watching. The specific
  near-miss: on a fresh PR the sole registered check was CodeRabbit reporting `pass` *because it
  was rate limited*. Any gate written as "all registered checks are non-pending and none failed"
  reports green seconds after a PR opens. Naming the four jobs makes the gate structural.
- **`strict: false`** — requiring branches be up to date would force a rebase and a full CI
  re-run on every master move. On a day when master moved seventeen times that converts a merge
  train into a queue, and a gate that makes the work unbearable gets switched off.
- **`enforce_admins: false`** — deliberate and load-bearing. `cut.py` pushes `master` and the tag
  directly, under Gate C. Enforcing admins would brick the next release at its own push step. **A
  protection that breaks releases gets disabled, and a disabled protection protects nothing.**

**Beyond the question.** This is not belt and braces with the pre-commit fence — they cover
different verbs. The hook fences a *commit*; branch protection fences a *merge*; `pre-push` fences
the *push*. Today proved the commit half can be walked around by `git cherry-pick` and
`git revert`, which run no commit-half hook at all. Three fences, three verbs, and none of them
subsumes another.

---

## Not ruled here, and why

**The remaining panel-crit calls that depend on M1, M4, M5 or M6.** Authority is not the issue;
evidence is. `CRIT.md` marks these *pending measurement* and a ruling made on an unmeasured claim
is exactly how "the control pinned to the brief's figure" happens in this repo — a number copied
from the document under test, ratified, and wrong. M2, M3 and M7 landed
(`harness/design_review/2026-09-15/measure/numbers.json`) and one of them already overturned a
derivation: mono weight 500 renders **bold**, so `status 11/500` and `tag 12/500` were never a
middle weight. That is what measurement is for. The remaining four are being measured; they become
ruleable when they land, and not before.
