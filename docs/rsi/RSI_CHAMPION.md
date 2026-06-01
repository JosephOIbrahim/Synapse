# RSI CHAMPION — the loop-closure ratchet

> **Logical layer:** CHAMPION (the bar). **Authored at:** INGEST.
> **MODE:** SIMULATED TEAM — round-robin FORGE across open lines, report WHICH
> LINE, never simultaneity. **Line definitions:** `RSI_PLAN.md`.
>
> **The champion is a RATCHET, not a hill-climbed artifact.** Exactly one
> champion: the substrate's verified loop-closure state below. Advancing one
> loop one notch = a promotion. **No notch is ever given back** — regressing a
> closed loop is a showstopper, not a delta.

## State machine (per loop)

```
dormant      → the audit's starting state
claim-OK     → audit's file:line claim verified against live code   (L0 claim-check)
wired        → the change applied, compiles, symbol exists          (L0)
L1           → record → persist → reload reads back IN-PROCESS
L2 *CLOSED*  → knowledge survives a real process restart  ★THE GATE★
L3           → a persisted record alters a LATER decision vs. the static baseline
L4           → tier-safe: protected never decays/overwrites; decaying decays;
               concurrent writes don't corrupt
```

A loop counts as **CLOSED at L2**. L3 / L4 are the hardening notches.
**RESTART-AWARE PROMOTION:** the L2 claim is replicated on a SECOND fresh process
before it counts. One restart is a sample; two is a result. If a restart cannot
be run in this environment, the loop **cannot** be marked closed — say so.

## The ratchet (seeded at INGEST — all dormant)

| Loop | Line | ROI | Notch | Persistence axis | Next gate |
|---|---|---|---|---|---|
| Render-farm learning | **R** | 1 | `dormant` | **SUBSTRATE PRESENT** *(audit claim — confirm at L0)* — rides the SynapseMemory FEEDBACK store | `claim-OK`: confirm the `:858` guard is permanently false |
| §16 observability | **O** | 2 | `dormant` | needs wiring — JSONL ring exists, zero non-test callers | `claim-OK`: confirm the lower half is dormant, not wired elsewhere |
| Science registry | **S** | 3 | `dormant` | needs `deposit_fn` — registry on disk, `deposit_fn=None` | `claim-OK`: confirm `deposit_fn=None` at `run_apex_verify` |
| Router fast-paths | **F** | 4 | `dormant` | **NONE** — in-memory only, dies with the process | `claim-OK`: confirm promotion is live + storage is in-memory |
| FORGE engine | **E** | 5 | `dormant` | corpus seeded once (`created_cycle:0`), not per-cycle | `claim-OK`: confirm `:172-177` optimistic + `:214` hardcoded |
| Convergence (= INTEGRATE) | **C** | 6 | `dormant` | — (it IS the substrate) | depends on R–F + E closing first |

### Why R is "one notch ahead on persistence" but still `dormant`

The audit asserts render-fix learning is the **only** loop whose persistence is
already built and durable: `record_fix_outcome()` writes FEEDBACK to the memory
store, and `_warmup_from_memory()` reads it back. *(This persistence limb is
itself an audit claim — confirmed at R's L0 claim-check alongside the guard, not
treated as settled here.)* So on the *persistence axis* it starts ahead — no
substrate to build, only a guard to fix. But on the
*reachability axis* (the main ratchet) it is **`dormant`**: the dead `hasattr`
guard at `handlers_render.py:858` means the loop is never reached, the claim is
not yet verified against live code, and nothing is wired. The notch advances
only after the first EXECUTE confirms the claim — INGEST does not advance it.

## Champion metric

```
CLOSED (L2+):   0 / 6
Hardened (L3):  0
Hardened (L4):  0
```

## Promotion log

*(empty at INGEST — the first entry is written when the first line reaches
`claim-OK` in the first EXECUTE, after SPEC ratification.)*

---

**Regression rule:** if any future change moves a loop's verified notch
*backward*, STOP — that is a showstopper, reopen DELIBERATE on that loop. The
ratchet only turns one way.
