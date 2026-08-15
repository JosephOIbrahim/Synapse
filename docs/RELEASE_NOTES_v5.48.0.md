# v5.48.0 — work in Houdini while Synapse works

*Non-Synapse nodes no longer lock up while a Synapse operation is processing. The freeze was physical law — the main thread IS the UI thread, and Python cannot preempt running Python — so this release attacks the three places Synapse held that thread without a witness: unlabeled dispatch holds, blind retry loops, and an emergency halt that waited on the thread it was trying to free. 18 commits, PR #75, crucible-gated.*

---

## What you get, plainly

Mid-render or mid-tool-call, you can select nodes, edit parameters, and keep working. When a call goes long, the panel now tells you **what** is holding Houdini and **since when** — and the stop button reaches it.

If a tool call wedges twice in a row while a holder is registered, Synapse stops retrying it and tells you in plain words: which command, held how long, by what.

`Synapse → Emergency Halt` now works even while the main thread is frozen. It acts off the main thread — it never waits on the very thread it's freeing.

## The four fixes

**F4 — the in-flight register (`main_thread.py`).** Every dispatch that takes the main thread now writes its name and start time into a register — on entry, cleared on exit, on **both** dispatch paths (114 previously anonymous sites now carry labels; AST-verified). Everything else in this release reads that register. `collect_telemetry()` freeze dumps include the holder section.

**F2 — the retry breaker (`panel/retry_breaker.py`).** The worker used to re-fire the same command after a timeout even while Houdini was visibly held. Now the breaker only fires when BOTH are true: the same command abandoned twice in a row AND the register says a holder is live. The artist sees the honest sentence; the model sees a `is_error` result and stops.

**F3 — halt that reaches a frozen UI.** The emergency net is constructed at transport startup (never mid-freeze), and the WS-path halt reads the register as evidence and sweeps PDG from off the main thread. A halt mid-freeze can no longer deadlock on its own wait.

**F1 — update-mode sandwich (flag-gated).** `SYNAPSE_COOK_SANDWICH=1` opts into a per-operation snapshot → Manual → mutate → restore → `hou.ui.triggerUpdate()` envelope around cook-heavy mutations. Dev-default **OFF** until the live probe passes on 22.0.400: `scripts\live_verify_freeze.ps1` then one line in the Houdini Python shell.

## Numbers, with producers

| Figure | Producer |
|---|---|
| 6,297 passed · 5 failed · 170 skipped | local `python -m pytest tests/ -q` @ `86115ed5`; 4 failures are statusline-worktree environmental, 1 pre-existing (`test_backfill`, Py 3.14 vendored ABI) — zero forge-authored |
| CI all-pass on the merge commit | GH Actions run @ `eb0a4433` (macOS+Ubuntu × Py3.11/3.14, CodeRabbit) |
| 23 attacks, 2 FATALs caught pre-merge | `docs/reviews/crucible-full.json` (F2 rerooted onto the register; F5 default-flip killed → F5a probe-only) |
| 114 dispatch sites labeled | AST scan in the forge report (`docs/reviews/freeze-forge-report-2026-08-14.md`) |
| PR #75, merge `eb0a4433`, 18 commits | no squash, per-leg history preserved |

## Known limitations — what this release does not claim

- **Not yet live-verified.** Everything above is harness-green; the on-screen proof is live on Joe's 22.0.400 seat — two probe gates (`scripts\live_verify_freeze.ps1`) and the 5-step session protocol in the forge report. F1 stays dark until its probe passes.
- **F5 was NOT flipped.** Defaulting renders to background-mode was crucible-FATAL twice (the file-on-return contract in `handlers_render.py` and the GL flipbook fallback detonate). The render-offload design question is parked behind `docs/reviews/render-offload-f5a-design-gate.md` and the `--indie` husk probe matrix.
- **The websocket cancel gap is still open** (`websocket.py:471` serial read loop).
- **The SessionStart "connected" lie is still open** — ping-first remains the cure.

## Files Joe will run again

| Thing | Where |
|---|---|
| Live verification entry point | `scripts\live_verify_freeze.ps1` |
| F1 sandwich probe (GUI Python shell) | `harness\notes\probe_update_mode_sandwich.py` |
| F5a render probe (hython) | `harness\notes\probe_render_offload.py` |
| Spec + crucible + forge record | `docs\reviews\ui-freeze-fix-spec-2026-08-14.md` · `freeze-forge-report-2026-08-14.md` |
