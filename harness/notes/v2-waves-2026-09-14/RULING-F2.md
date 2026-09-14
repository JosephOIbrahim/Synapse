# RULING — F2 (the emergency-halt rail sentence)

**Date:** 2026-09-14 · **Ruled by:** CTO pass, on evidence re-measured in this session
**Branch under ruling:** `worktree-wf_51b5f8aa-295-1` @ `de325abd`
**Ruled against:** master `5424853a` (bd65e4b6 + five honesty/evidence merges + F4)

---

## The ruling in one line

**Park the F2 branch. Open a leg on the master-side defect F2 surfaced — a silently
dropped emergency halt — and fix that first.** F2 is not one seam from mergeable, and
the bug that matters is not F2's.

---

## Why this is not "F2 needs a Pass 4"

The Pass-3 review named one showstopper. I re-ran its probe myself on both trees
rather than rule from the report, because the review flagged the finding as
single-source and named the re-run as the cheapest confirmation available.

It reproduced. **And so did two more of the same shape that the report had filed as
lesser findings.** Together they are not three defects; they are one mechanism with a
missing half.

Producer, both trees, headless, no PySide:

```
python harness/notes/v2-waves-2026-09-14/probe_f2.py C:/Users/User/SYNAPSE
python harness/notes/v2-waves-2026-09-14/probe_f2.py C:/Users/User/SYNAPSE/.claude/worktrees/wf_51b5f8aa-295-1
```

| Path | master `5424853a` | F2 `de325abd` |
|---|---|---|
| **A** Cancel cook, then Emergency halt | rail `Still Emergency halt…`, then **`Not connected` after one tick** — recovers | rail `Halting…`, **still `Halting…` after a tick** — never recovers |
| **B** direct tool fails, sentence does not fit the rail | rail `Not cancelled`, mark `done` | rail **`Result ready`**, mark `done` — master could not reach this |
| **C** the call's constructor raises | held phrase `None`, rail recovers to `Not connected` | held phrase **kept forever**, rail `Working on it` with a tooltip for work that never started |

`halt actually dispatched: False` on **both** trees in path A.

**The pattern.** F2 replaces transient sentences with held ones. It added a release on
the happy path and on no other. Master's sentences were sometimes ambiguous and always
self-healed on the next 2000 ms tick, because nothing was held. F2's are legible and,
on three abnormal paths, permanently false.

That is worse on the exact axis F2 exists to improve. INTENT.md §3 — *a timeout or a
stop request alone is not proof that work has stopped.* Path A is stronger than that:
the stop request was never sent, and the rail states a clean `Halting…`.

**A Pass 4 scoped to the halt sentence would fix one of the three and leave the
mechanism unbalanced.** A Pass 4 scoped to all three is a rewrite of the hold/release
design, which is not a rework — it is the original build again.

---

## The defect that is actually worth a leg, and it is master's

Path A shows zero dispatch on **both** trees. F2 did not cause that. Master does, at
`python/synapse/panel/synapse_panel.py`:

```python
def _run_direct_tool(self, tool_name, arguments, busy_text, done_key=None):
    ...
    if self._direct_call is not None and self._direct_call.isRunning():
        self._set_header("working", "Still %s…" % busy_text)
        return                       # <- nothing is dispatched, nothing is said
```

The guard tests for **any** live direct-tool call, not a live call of the same tool.
So: a cancel-cook in flight, the artist opens the menu again and clicks Emergency
halt — the halt is dropped, silently, and the rail says `Still Emergency halt…`,
which reads as *in progress*.

**The menu already knows the rule and applies it to the lesser control.** Ten lines
above, at `:2760-2766`:

```python
# Cancel cook — state-gated exactly like Stop. An always-enabled
# cancel with nothing to cancel is the same lie as a consent gate
# that does not gate (R18).
cook_act.setEnabled(bool(node) and bool(self._was_busy))
```

and then, at `:2769-2770`:

```python
halt_act = menu.addAction("Emergency halt…")
halt_act.triggered.connect(self._on_emergency_halt)     # no setEnabled, no guard
```

R18 was applied to Cancel cook and not to Emergency halt — the more consequential of
the two, and the only take-control-back verb in that menu. `_on_emergency_halt`
(`:2857`) is the sole entry point and goes straight into `_run_direct_tool`.

**On how reachable this is, stated honestly.** It needs a specific sequence: a cook in
flight, Cancel cook clicked, then Emergency halt while the cancel thread is still
running. The window is short. But it is the *modal* path, not a contrived one — "I
cancelled the cook and it is not stopping" is precisely what sends an artist to
Emergency halt. **The window opens exactly when the control matters most.**

INTENT.md §7 asks four questions of the interface. One is *how do I take control
back.* Today, on master, the answer is sometimes "you did not, and we told you that
you had."

---

## Why fixing this first also dissolves most of F2

If the halt dispatches, F2's `Halting…` becomes **true**, and path A stops being a
false statement. Fixing in the other order — patching F2's sentence — repairs the
symptom and leaves the halt still dropped.

Three further reasons the order matters:

1. F2's inversion pin at `tests/test_panel_header_sentence_floor.py:294-301` has to be
   rewritten either way (LAW 6: rewrite, never delete). Its correct assertion depends
   on what the seam does *after* the fix. Writing it now pins the wrong thing twice.
2. F2's three genuine repairs (B1 held detail, B2 at its named site, B8 the single
   tooltip writer) are real and rebase cheaply onto a fixed seam. Patching them around
   a broken one is the more expensive order.
3. Paths B and C are unresolved on F2 regardless, and path B's trigger is a glyph
   comparison nobody has measured — `Not cancelled` is 13 glyphs against a floor whose
   widest members are also 13. That needs a seat, not another headless pass.

---

## What the leg is

**HALT-1 — make the emergency halt dispatch, or say plainly that it did not.**

Scope, and nothing beyond it:

- `_run_direct_tool`'s re-entry guard distinguishes a live call of the *same* tool
  from a live call of a *different* one, **or** the halt is exempted from the guard.
  Which of those is a design call with artist-visible consequences — **gate joe.**
- Whichever is chosen, a dropped request says so in chat. A silent return is the
  defect, not the mechanism.
- `halt_act` gets the state gate its neighbour already has, or a stated reason why an
  emergency control must stay always-enabled. Both are defensible; picking silently is
  not.
- Pinned by a test that fails against `5424853a` and asserts on **dispatch count**,
  not on the sentence. A sentence assertion is what let the F2 pin certify its own
  broken branch.

Out of scope: the rail's wording, the hold/release mechanism, and every F2 repair.

---

## Disposition

| Item | State |
|---|---|
| `de325abd` (F2) | **PARKED.** Branch intact, nothing deleted. Revisit after HALT-1 lands; expect a rebase, not a merge |
| Its three genuine repairs | Not lost — named above, re-land on the fixed seam |
| HALT-1 | **CLOSED 2026-09-14** — `b8aa22da` (a dropped request says so) + `eab47244` (the guard is per-verb). Re-measured with this ruling's own probe: `halt actually dispatched` **False &rarr; True**, `calls_started` delta **0 &rarr; 1**. The design call went to per-verb, not exempt-by-name |
| Paths B and C | Carried into HALT-1's follow-on, seat-required |
| `probe_f2.py` | Tracked beside this ruling. The re-runnable producer for all three paths; re-run it on any tree that touches this seam |

## Closure note (2026-09-14)

HALT-1 was built the same day and its design call did not need a judgment: the rule was
already ratified one layer down. `server/handlers.py:236-241` excludes `emergency_halt`
from the C5 mutation lock because *"a mutating-classified stop or halt would queue behind
the very operation it exists to interrupt — which is the difference between a kill switch
and a decoration."* The panel's single-slot guard re-imposed exactly that at the UI layer,
and dropped the request rather than queueing it. Per-verb keying was the faithful
translation; exempting the halt by name would have hard-coded one of only two verbs.

Measured on both trees with `probe_f2.py`, unchanged except for being made shape-agnostic:

```
5424853a   EMERGENCY HALT   rail 'Still Emergency halt…'   calls_started 1 (delta 0)   dispatched False
eab47244   EMERGENCY HALT   rail 'Emergency halt…'         calls_started 2 (delta 1)   dispatched True
```

**Still true after HALT-1, and not claimed otherwise:** the panel's halt marshals
(`handlers_render._handle_emergency_halt` → `run_on_main(..., timeout=60.0)`), so it fires
but does not survive a frozen main thread. The freeze-proof `emergency_halt_live` is
reached only from `freeze_chain.py:236`. Paths B and C remain open and belong to the
parked F2 branch.

---

**What this ruling does not say.** It does not say F2 was bad work — three of its four
repairs are genuine and were measured. It does not say the halt bug is new; it is
pre-existing and F2 surfaced it. It does not rule on when HALT-1 is built. And it does
not claim paths B or C were measured in pixels — neither was, and both say so.
