## What this is

The code for `harness/notes/FREEZE_FORENSICS_20260731.md` §5, items 1–3.

That document was **diagnosis-only**. Commit `f427320` added 347 lines across 3 files — all docs and workflow, **zero source changes**. The freeze was mapped in detail and repaired in none of it.

---

## Why a guard and not a timeout

v5.40.1 shipped as *"the chat no longer grips the UI."* It bounded the caller's **wait** and never the running **payload**.

So the freezes continued. On **2026-07-31**, under that release, the main thread froze **8 times**, up to **44.4 s**, one escalating to SUSTAINED FREEZE — with the dump showing `main_thread_direct.count = 0`, meaning the class-3 mechanism never even fired.

A payload cannot be timed out once it is running, and the codebase already says why, verbatim at `handlers_render.py:109-113`:

> nothing in Python can interrupt the main thread from the main thread

So the only mechanism available is **refusing before entry** — the same shape as the render `foreground_guard`, which is already the sole protection on that path.

---

## The three fixes

**§5.1 PRIMARY — the h7 inline guard.** `_dispatch` now reads **real thread identity**, not a proxy for which entrypoint was used. When a dispatch is genuinely on the main thread *and* the pre-flight predicts a heavy payload, it is refused with an actionable error naming `execute_tool_off_main`. `_allow_heavy_inline = True` is the explicit opt-out.

This makes the pre-flight **enforcing** on the inline path where §5.1(b) called it *"advisory-only."* The advisory contract is unchanged on the off-main path, which is what the worker actually uses.

**§5.2 SECONDARY — honest thread attribution.** `_dispatch` is reached from *both* `execute_tool` (Qt slot, main thread) and `execute_tool_off_main` (daemon thread), and only the first can stall the Qt loop. The old `finally` recorded **both** into the main-thread counters and logged both as *"ran on the main thread (Qt loop stalled this long)."*

The forensics recorded that this *"corrupted forensics this run and will corrupt the next one."* Off-main samples now go to separate `offmain_*` counters and log *"Qt loop NOT stalled."* Durations are kept, just no longer misattributed.

**§5.3 HAZARD — the armed class-3 wire.** `synapse_panel.py:1938` connects `worker.tool_requested → execute_tool`. The wire is live with **zero emitters**, which is the only thing keeping class 3 closed; one `.emit` re-arms it and nothing in CI would notice. Pinned by a source scan rather than disconnected, because the slot contract is still used by tests and direct callers — and with the §5.1 guard in place, an accidental re-arm now degrades to a **refusal** instead of a freeze.

---

## What this does NOT fix — stated plainly

A payload dispatched off-main still marshals back to the main thread via `run_on_main` and occupies it for its duration. **The Qt loop still stalls for that long.**

Closing that requires chunking or timeboxing the individual cook-heavy handlers — `handlers_node.py:79`, `handlers_material.py:90/:246/:508`, `handlers_usd.py` (13 sites), `handlers_cops.py:929/:1987/:2127` — a per-handler refactor needing live verification each. **Not attempted here.**

**Freeze class 1 remains MITIGATED, not CLOSED.** What is closed is the unbounded *inline* path and the attribution defect that would mislead the next investigation.

---

## Tests

`tests/test_panel_preflight_h7_guard.py` — 9 new tests: refusal on main, light tools unaffected, heavy tools still run genuinely off-main, the escape hatch, no verdict leak between requests, off-main time not counted as main-thread time (**with a paired positive control** so it cannot pass vacuously), log discrimination, and the h9 emitter scan.

`tests/test_panel_preflight.py` — two tests moved onto a **real thread**. Calling `execute_tool_off_main` from the test's own thread is still main-thread execution, so the guard correctly fires there; exercising the off-main contract requires a genuine thread. The module docstring records the contract change rather than leaving the old "advisory ONLY" claim stale.

### One thing worth reviewing carefully

The new test file's **filename is load-bearing**, and this was found the hard way. The first draft was named `test_freeze_h7_inline_guard.py`, which made it the alphabetically-first panel test. That pulled `from synapse.panel import tool_executor` forward in collection, so the class bound `QObject` from whatever stub existed at that earlier moment — and **six previously-green tests started failing** with `_last_preflight` returning a MagicMock attribute instead of `None`.

I assumed those were pre-existing, then checked against a clean-master worktree instead of trusting the assumption. They passed on master. **The rename fixed them, not a code change.** The header comment records this so the next person doesn't re-break it.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
