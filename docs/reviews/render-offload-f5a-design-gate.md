# F5a design gate — what F5b would have to be

**Status:** gate document. F5b is explicitly NOT in the freeze-relief forge. It opens only when the F5a probe (`harness/notes/probe_render_offload.py`) has been run live on H22.0.400 **and** Joe has signed off on the result.

This note exists so that when F5b is designed, it starts honest — it does not re-derive the premise the crucible already ruled FATAL.

---

## Why the naive flip died

`_handle_render`'s contract is **synchronous file-on-return**: render on the main thread, poll the output path for ~15s, then fall back to a **GL flipbook capture** on the main thread, then raise a RuntimeError that lies about success ("the viewport validated it").

A naive "automation renders default to background/husk" flip therefore manufactures three failures on every render over 15s:

- a flipbook freeze **on the thread you were trying to unfreeze**,
- a viewport image masquerading as a render,
- a false error when neither lands.

And the load-bearing premise — "`node.render()` under `soho_foreground=0` returns immediately" — **was never probed.** The husk-on-Indie evidence inside the tree is contested: `handlers_render.py:336-338` records a failing delegate load with `--indie`; `perception_truth_22.0.368.json` records husk writing real multi-part EXRs headless on the same license, same day, no `--indie`. The probe's with/without-`--indie` matrix names the differing invocation.

## What F5b must rework (all four, or don't start)

1. **The `_handle_render` return contract.** Automation-class renders move to async token/poll semantics. The machinery already exists — `_handle_render_bounded` ships single-flight + `render_token` + bounded wait. F5b routes automation renders through that contract; it does not invent a second one, and it does not touch the foreground/interactive path (`render_progressively`'s 256px layout pass and `safe_render`'s force-foreground stay exactly as they are).

2. **No GL flipbook fallback for automation renders.** The fallback is deleted *for that class* — it is not kept as a "best effort." Interactive viewport capture keeps its own path; automation never gets a viewport image dressed up as a render.

3. **Failure surfaces as failure.** Delegate load failure, husk exit-code != 0, timeout, missing EXR — all become real errors in the result. Never a viewport-validated fake, never a RuntimeError that lies.

4. **Killability is the point — verify it per build.** The F5 zombie class exists because no API cancels an in-flight foreground render, while `synapse_render_stop` can kill background husk rows. But "killable" is build/OS/delegate-specific: it holds only where the probe confirmed the delegate loads and the completed render actually lands pixels. A verified kill path on the wrong build is still a zombie.

## Sequencing, if and when F5b opens

1. F5a probe results in `harness/notes/` — items (a), (b), (c) all PASS with recorded invocations.
2. Joe reads the result, signs off. No probe, no design.
3. Contract rework (item 1) lands first, behind a flag, with `render_progressively`-style callers pinned to the old contract until migrated.
4. The flag flips for automation-class only after a live kill test: start a background render, `synapse_render_stop` it, confirm no partial EXR and no zombie process.

## Out of scope, unchanged

- `safe_render` force-foreground path — untouched by any F5 work.
- `render_progressively`'s 256px foreground layout hatch — untouched.
- H21-era Indie husk no-op history — superseded by the 22.0.368 perception truth; F5b targets 22.0.400+ only.
