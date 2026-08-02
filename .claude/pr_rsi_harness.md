## What this is

Two additions with one theme: **make self-improvement claims falsifiable.**

- `harness/rsi/` — the RSI closure harness
- `harness/progress.py` — the all-harness progress board

Nothing here flips a gate, edits `VERSION`, touches `ratified`, or changes runtime behaviour. It is a harness plus a status tool.

---

## The finding that shaped it

Two prior RSI efforts exist and they **disagree**.

**June 2026** (`docs/rsi/`) ran on the thesis *"find the dormant apply half and wire it."* It closed lines R and O.

**July 2026** (`harness/notes/RSI_SURFACE_AUDIT.md`) audited three other mechanisms and concluded: *"nothing in this codebase has ever improved itself."*

The audit didn't just find more dormant loops. **It found that wiring one of them would have been actively harmful.**

`EpochAdapter`'s reward signal is a constant. `_record_metric` is declared `(self, tier, latency_ms, success: bool = True)` at `router.py:917`, and **not one of its eight call sites passes `success`** — `:285 :448 :515 :554 :584 :706 :742 :819`. Re-verified at HEAD `f427320`.

It's worse than one defect:

- `_try_tier0` hardcodes `RoutingResult(success=True)` at `:537` without consulting responses that can carry `success=False`
- the `no_tier_matched` fallback at `:367-373` never records **at all**, so genuine failures never enter the sample

Measured consequence (audit probe P4, 300 outcomes): a monotonic slide to the `0.10` clamp floor **in eight epochs**, flat thereafter.

That is not an adaptive controller. It's a one-way ratchet — safe today only because nothing reads its output.

---

## What the harness adds: one rung

**`L1 HONEST` — a loop may not be closed until it can observe its own failure.**

It sits *below* reachability, deliberately. An unreachable loop is inert. A reachable loop on a dishonest signal is a live actuator driven by noise.

```
L0 EXISTS  →  L1 HONEST  →  L2 REACHABLE  →  L3 CONSUMED  →  L4 DURABLE  →  L5 BENEFICIAL
                                                              (+ RATCHET, orthogonal)
```

**Three of nine registered loops fail L1 today — and all three would have been wired by the June thesis.**

---

## Contents

| File | What it holds |
|---|---|
| `SPEC.md` | The ladder, 9 predicates, human gates, falsification conditions |
| `REGISTRY.json` | 9 loops reconciled from both efforts, each with a `danger_if_closed_now` field |
| `verify.py` | The 9 predicates, headless (no `hou`, no bridge, no network) |
| `PLAN.md` | Six lines `RL-1`..`RL-6`, order forced by the ladder |
| `CHAMPION.md` / `LEDGER.md` / `DEADENDS.md` / `LOG.md` | Ratchet, recipes, refutations, run log |

**Two design choices worth review:**

`verify.py` P4 **greps `router.py`** instead of reading a status field, so it updates its own answer when the signal is really fixed. It fails in *both* directions — registry claiming honest while code is constant, and code fixed while registry is stale.

`REGISTRY.json` **records the ladder-number collision rather than importing across it.** June's `L2` meant *"survives a restart"* — this ladder's `L4`. Six loops therefore start with **no proven rung**, pending re-derivation in `RL-1`. That's deliberate, not a demotion of the June work.

---

## The progress board

`harness/progress.py` answers a question none of the four existing status tools do: *several harnesses exist — which are running, and how far along is each?*

It **discovers** any `harness/*/verify.py` rather than listing harnesses. That's per **R140**, the defect that retired `harness/heats_status.py`: it read *real* receipts into a *hardcoded* layout that had stopped describing anything, and it never errored and never looked stale.

Also renders live workflow runs, held locks, and armed worktrees. Every number names its producer. Unreadable renders `?`, never a guess.

```
python harness/progress.py            # all bars + what is running now
python harness/progress.py --fast     # skip verifiers, structure only
python harness/progress.py --json     # machine-readable
```

---

## Verification actually run

```
python harness/rsi/verify.py     →  9 PASS / 0 FAIL / 0 PENDING
python harness/progress.py       →  clear 5/8 · rsi 9/9
```

**The first verifier run was 7 PASS / 2 FAIL, and both failures were real:**

- **P1** named three genuinely unregistered surfaces — `shared/conductor_advisor.py`, `shared/constants.py`, `shared/evolution.py`. All confirmed and registered.
- **P4** caught a parser defect *in `verify.py` itself*: `"    def ".strip()` drops the trailing space, so `startswith("def ")` silently counted the signature at `:917` as a call site.

Both fixed, then 9/9. P4's live grep then **independently re-derived the audit's eight call sites with no shared source** — two independent derivations agreeing.

The board was cross-checked too: CLEAR reads `5/8 clear, 3 open`, matching CLEAR's own logged last run. The `rsi` harness then appeared on the board with **no edit to the tool**.

---

## Closure status is deliberately unflattering

> **0 of 9 loops beneficial. 0 of 9 reach L3 CONSUMED. Highest rung anywhere is `A3` at L2.**

A 9/9 verifier bar means **the registry is honest about the code** — not that anything is closed. Conflating those two is the exact failure `CHAMPION.md` exists to prevent, and it's called out at the top of that file.

---

## Gated on you

- **`SPEC.md` is `AWAITING RATIFICATION`** — no line executes until you ratify
- No loop advances past **L3** without a human flip (`P8` enforces)
- `RL-2` (fixing the signal) changes artist-facing routing behaviour — **human gate**
- `RL-3` holds two decisions that aren't engineering: `A2` **wire-or-delete**, and `C` **substrate before persistence**

🤖 Generated with [Claude Code](https://claude.com/claude-code)
