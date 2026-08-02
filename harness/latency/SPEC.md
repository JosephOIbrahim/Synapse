# LATENCY HARNESS — the scale-parameterized cost ledger

**Status:** scaffold ratified by the human · registry populated by the scout fan-out
**Discovered by:** `harness/progress.py` (any `harness/*/verify.py` appears on the board)

---

## Why this harness exists

Two rigorous findings in this repo contradict each other, and the contradiction is
the whole reason for the harness.

**Finding A** — `docs/reviews/synapse-latency-report-2026-07-27.md` derives a five-bin
cost ledger and concludes: T1 (the LLM turn) dominates by one to two orders of
magnitude; Houdini-side work is **1–70 ms per op**; therefore Houdini-side latency
work is *"tuning the 5%"*.

**Finding B** — commit `98b556f` (BRIDGE-FLOOR) measured a 100k-prim scene paying
**6.9–7.7 seconds** of Houdini-side stage serialization per bridge op, cut to
**1.8–1.9 s** by making the size gate real (`shared/bridge.py:427`).

Seven seconds is not 1–70 ms.

Both can be true if Finding A's ledger was derived on **small scenes** and carries no
scene-scale dimension. If so there is a **crossover scene size** above which the "5%"
bin stops being 5% — and nobody has mapped it. Every latency decision above that
crossover is currently being made with a ledger that does not model it.

**This harness exists to make scene scale a first-class axis of the cost ledger, and
to keep won latency won.**

---

## The ladder

A latency claim earns rungs. It does not skip them. The failure mode this prevents is
documented: a prior "Mile 4" was worked before it reached L2 and was later refuted as
PHANTOM.

| Rung | Name | Earned when |
|---|---|---|
| **L0** | CLAIMED | A number exists in a doc or a commit message. |
| **L1** | REPRODUCIBLE | A named producer command re-derives the number on demand. |
| **L2** | ATTRIBUTED | The cost is localized to one cost bin **and one scene-scale regime**, with `file:line` evidence. |
| **L3** | BOUNDED | The irreducible floor is known (Houdini cook, provider turn) — so the *available* win is known, not the total cost. |
| **L4** | REDUCED | A change moves the number, measured before/after on the **same input at the same scale**. |
| **L5** | HELD | A regression gate keeps it reduced. A win with no ratchet is a loan. |

**No rung may be claimed on a different scene scale than the one it was measured at.**
Scale is part of the claim, not context around it.

---

## Predicates

`verify.py --json` emits one row per predicate. `PENDING` is honest and expected while
the harness is young — it is never a synonym for `PASS`.

| id | Predicate |
|---|---|
| **P1** | The ledger is scale-parameterized — `LEDGER.md` exists and every cost row carries a scale term. |
| **P2** | Every open hypothesis carries a runnable probe (no hypothesis without a falsifiable test). |
| **P3** | No registry entry re-proposes refuted ground — each is checked against the refuted list. |
| **P4** | Instrument state is recorded with locators — U1–U4 landed/partial/absent, evidenced. |
| **P5** | The scale bench runs **offline** (no Houdini) so it can gate CI. |
| **P6** | The perf ratchet is armed — a floor exists and a test pins it. |
| **P7** | The ratchet floor is read at **merge-base**, so a branch cannot lower its own bar. |
| **P8** | Law 2 holds inside this harness — every number in its own docs carries a producer path. |

---

## Standing rulings (do not re-litigate)

- **Batching for latency is refuted.** Adversarially killed at PR #28: the worker
  already multiplexes N tool calls from one assistant turn into **one** round-trip
  (`claude_worker.py:139-185`). `synapse_batch` exists for atomicity, not speed.
- **U5/U6/U7 stay parked** behind their numeric reopen-gates. Re-state the U6 anchor
  before trusting it — it was already flagged stale.
- **Cold start is a hide-it, not an optimize-it** (report §2 #4). One-time per session.

A hypothesis that lands on this list is **killed with a citation**, not quietly dropped.

---

## Non-goals

- Optimizing T4 micro-costs on small scenes. That is the 5%, and the report is right
  about it. This harness exists for the regime where that claim stops holding — it does
  not overturn the claim inside its own range.
- Wall-clock assertions in CI. Timing in CI flakes; a deterministic counter (e.g.
  full-stage traversals per op) is a more honest gate than a timer. See P5/P6.
- Any claim of a live number without a live bridge. `REQUIRES LIVE BRIDGE` is a
  legitimate verdict and is preferred over an estimate wearing a number's clothes.

---

## Human gates

The harness stops and asks at each of these. No agent crosses one.

1. **Ratifying a hypothesis as work** — moving an entry to `accepted` in `REGISTRY.json`.
2. **Arming the ratchet floor** — the first floor value is a human decision; a floor
   set by the thing being measured is not a floor.
3. **Any merge to master.**
4. **Re-opening a parked U-item** — requires the numeric gate to be met *and* re-stated.
