# v5.39.0 — SYNAPSE can see

*Seven commits. The capture always worked and the file went nowhere; that gap is closed, proven twice, and it turned out to answer a question a whole leg had ruled unanswerable.*

---

## It can look at your viewport

Ask it what it sees and it will tell you — from pixels, not from the node graph.

```
YOU      what do you see in the viewport
SYNAPSE  the classic SideFX rubber toy (the little dragon/Nessie squeak toy)
         sitting on the grid... there's a rotate handle active around its
         midsection, so it looks like you're mid-transform on it. Framed from a
         three-quarter high angle.
```

**The node is called `sopcreate1`.** The graph says nothing about what geometry is inside it. Recognising that silhouette, the rotate handle, and the camera framing are all things only pixels carry.

`_handle_capture_viewport` has always worked — it drives Houdini's flipbook API because `QWidget.grab()` returns black on a GL surface. **What was missing was the last step:** `claude_worker` contained zero occurrences of `image` and zero of `base64`. The file was written and never shown to anyone.

---

## And it can tell you what changed

```
YOU      capture the viewport, add a distant light, capture it again,
         and tell me what changed
SYNAPSE  the face and chest that were bright before have fallen into shadow.
         The top of the head, back and tail are catching most of the light now.
         Light guide geometry appeared — those white wireframe lines are the
         distant light's viewport guide.
```

**A viewport guide is display-only** — not a prim, not geometry, absent from any render. Reporting that it *appeared* requires holding both frames.

**Nothing was built for this.** The worker collects every tool result from a turn into one user message and the attach fires per-result, so two captures place two images side by side automatically. The diff capability fell out of the attach. It needed asking for, not building.

---

## Which answers a question a whole leg had closed

V1 ruled: *"No usable per-object integer ID mask exists on Karma 22.0.368 via any path probed. **The scoped-delta primitive cannot be built as designed.**"*

That was correct, and it closed one road while the goal stayed open.

**V1's own findings say why the road wasn't needed.** V1-F10 measured renders as **deterministic** — pixel-identical across separate husk processes, sampling noise floor of zero — and filed it as a contradiction of RETINA's design premise. It is actually the licence for the whole approach: **if nothing else moved, the pixels that changed are the change.** Object identity was never required to attribute a delta, only confidence that the rest held still.

And the semantic half — *which* object a region is — is what a vision model does natively.

**The ID mask was solving a problem two other things already solve.** Determinism supplies the isolation; vision supplies the identity. And unlike a husk-rendered ID pass, this works on the **viewport**.

---

## Three fixes it took, and the third is the instructive one

**The attach** — read the path, base64 it, put an image block beside the text.

**The refusal reaches the panel, not just the model.** The first guard put *"the capture was NOT sent"* into the tool result and trusted the model to relay it. Measured live: `glm-5:cloud` absorbed it and answered *"here's what I can see from the viewport capture"* — a fluent, accurate, entirely graph-derived description. **A note in a tool result is a request, not enforcement.** The verdict now rides the tool-status rail to the result surface, where the model does not author the output.

**The second branch.** `_execute_tool_block` has two paths — MCP first, then a Qt-signal fallback — and only the first was wired. `houdini_capture_viewport` carries `readOnlyHint=True`, so it marshals whole and lands on exactly the branch that was missed. **Built and connected to nothing, with the connection half made** — harder to see than not making it at all, because the code is present, the tests pass, and it works on whichever path you happen to test.

---

## What this does not claim

**It does not measure.** The model gives a *semantic* difference. A measured one — changed-pixel count, bounding boxes, a threshold — still wants OpenCV in the sidecar, since `cv2` is absent from hython and present in system Python. That is the verification half and a different job.

**The per-object ID mask is still impossible** on Karma 22.0.368. `primid` is per-polygon and reused across objects; Karma refuses an integer render-var format outright. RETINA's originally-designed primitive remains unbuildable — this reached the goal by another route.

**Determinism is a strong prior, not a property.** V1-F10's own scope limit reads *one frame, one trivial scene, one machine, CPU engine, fixed samples, denoiser off.* Confirm it on a real scene before anything depends on it.

**A text-only model gets no image**, and says so on the panel. Vision is per-model, not per-provider — `glm-5:cloud` is the registry default and cannot see.

---

## Verifying it

```
harness/notes/vision_attach_control.py          13 assertions, refusals included
harness/notes/vision_both_branches_control.py   both dispatch paths, at the AST
harness/notes/vision_pair_probe.py              two captures, two image blocks
harness/notes/vision_loop_control.py            plants a token only the PIXELS
                                                contain and asks for it back
```

That last one is the loop closure: `SYN-B8VVNL` planted, `SYN-B8VVNL` returned. **A vision feature that cannot be told apart from scene inspection is not a vision feature** — so the control asks for something no inference can reach.

**Suite: 5,279 passed, 0 failed.**
