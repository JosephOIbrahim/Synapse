# DEADENDS — the RSI closure harness

*What was tried, refuted, or ruled out, with the reason. Append-only. A dead end recorded is a dead end no
future agent has to re-walk.*

---

## D1 · "Find the dormant apply half and wire it" — REFUTED as a general rule

**Status:** refuted 2026-08-01 at FRAME. Not refuted as a *specific* action; refuted as a *policy*.

The June 2026 harness ran on this thesis and it was correct for lines `R` and `O`. Generalised, it is
dangerous.

`A1` (EpochAdapter) has a fully-built observe/analyze/record half and a dormant apply half. The thesis says
wire it. The July audit measured what that would produce: success rate is permanently `1.0` because the
reward signal is a hardcoded literal, so `adjust()` takes the "great performance" branch every epoch for
every tier, and probe P4 measured a monotonic slide to the `0.10` clamp floor in **eight epochs**, flat
thereafter.

Wiring the dormant half would not have produced self-improvement. It would have produced a confident,
persistent, irreversible drift — and it would have looked like progress on a champion board.

**Superseded by:** the `L1 HONEST` rung, which makes signal honesty a structural precondition for closure.

---

## D2 · Importing the June closure claims by their L-numbers — REFUTED

**Status:** refuted 2026-08-01 at FRAME, before any import was attempted.

June's ladder and this ladder both use `L0`–`L4` and **mean different things**:

| | June | this harness |
|---|---|---|
| "survives a real restart" | **L2** | **L4** |
| "alters a later decision" | **L3** | **L3** |

So "Line R closed at L2+L3" reads, under this ladder, as a claim about restart-durability that June's L2
does support — but the coincidence is accidental, not translatable, and `L1` did not exist in June at all.
Importing the numbers would have silently promoted six loops on evidence that was never gathered for these
rungs.

**Superseded by:** `RL-1 RECONCILE`, and `REGISTRY.json._ladder_collision_warning`.

---

## D3 · A per-harness progress bar for RSI — RULED OUT before building

**Status:** ruled out 2026-08-01 at FRAME.

The obvious move was `harness/rsi/progress.py`, mirroring `harness/clear/progress.py`. Ruled out: that is the
R140 defect that retired `harness/heats_status.py`, which baked seven legs into its print statements and went
on rendering that board for 23 legs and 115 rulings after they stopped existing — reading **real** receipts
into a layout that no longer described anything, never erroring and never looking stale.

**Superseded by:** `harness/progress.py`, which discovers any `harness/*/verify.py`. This harness appears on
the board because it *has a verifier*, not because a tool was edited to know about it.

---

## D4 · Trusting `~/.synapse/logs/synapse.log` as production RSI evidence — RULED OUT

**Status:** ruled out; inherited from `harness/notes/RSI_SURFACE_AUDIT.md`.

The production log holds **4,795 `Epoch N complete` records and every one is pytest**, because
`core/logfile.py:60` attaches the rotating file handler whenever it is called and the test suite exercises
the same modules. The audit's own first pass read those hits as production traffic and had to reverse itself
via epoch-size fingerprinting.

Sizes 2, 3 and 5 cannot be produced by the router (production always constructs `EpochAdapter()` with the
`DEFAULT_EPOCH_SIZE = 100`), and the size-100 lines are all `Epoch 0` or `Epoch 1` and never `Epoch 2` —
the exact signature of `test_adapter_thread_safety`.

**Superseded by:** predicate `P5`, which refuses a log-based `L2` claim that does not name its
test-exclusion.

---

## D5 · `.synapse/config.yaml` as the memory-backend selector — CONFIRMED ABSENT

**Status:** confirmed absent; inherited from the audit.

`.synapse/config.yaml:17` reads `memory_backend: "flat"`. The store selector never reads that key —
`store.py:810` reads the **environment variable** `SYNAPSE_MEMORY_BACKEND`, defaulting to `jsonl`. The YAML
key is not configuration, does not select moneta, and must not be cited as evidence of backend state.

Recorded because it is a live trap for `RL-3`, which decides the substrate.
