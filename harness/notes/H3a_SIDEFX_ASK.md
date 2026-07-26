# SideFX ask — no programmatic cancel for an in-flight ROP render (Houdini 22.0.368)

**Raised by** SYNAPSE leg H3a (probe-only), 2026-07-26 · **Build** 22.0.368 · **Python** 3.13.10
**Evidence tier** VERIFIED-RUNTIME — live `dir()`/`hasattr` introspection on the running build,
two independent producers, positive and negative controls green in both.
**Producer paths** `harness/notes/h3a_probe.py`, `harness/notes/h3a_placement.py`,
`harness/notes/h3a_reconcile.py` · **Artifacts** `harness/notes/h3a/*.json`

> This document reports an absence. Ruling R44 directs that where the symbols are absent, the
> absence **is** the deliverable, and that no workaround is to be invented in its place. Nothing
> below proposes a mechanism, a substitute, or an implementation.

---

## 1 · The ask, in one sentence

**Houdini 22.0.368 exposes no HOM API by which a script can request cancellation of a render
already in flight through `hou.RopNode.render()`** — while the PDG surface in the same build
exposes a complete one. We are asking for the symmetric affordance on ROPs.

---

## 2 · Why it matters to us

SYNAPSE drives Houdini from an agent. The artist-facing panel has a **Stop** button. Today that
Stop aborts the agent's own loop and says so honestly, but it **cannot stop a running Karma
render** — the artist presses Stop and the render continues. We have kept the button honest
rather than making it lie, and the limitation is stated plainly in our shipped release notes.

We would rather close the gap than document it. This probe was run to find out which half of
that gap is ours to fix. The PDG half is: the API is there and we are not using it. The render
half is not: there is nothing to call.

---

## 3 · What the probe establishes

### 3.1 The ROP surface carries no cancel affordance

`hou.RopNode` exposes **318 attributes**. Filtering the complete `dir()` for
`cancel | abort | interrupt | kill | stop | background` returns exactly **one** name:

| Match | Note |
|---|---|
| `_cookNoInterruptInternal` | private; inherited from `hou.OpNode`; semantically a **non**-interruptible cook |

Zero matches for `cancel`, `abort`, `kill`, `stop`, `background`.

Ten candidate spellings were probed by name and are **ABSENT** on this build:

```
hou.RopNode.interrupt          hou.RopNode.abortRender     hou.RopNode.cancelRender
hou.RopNode.killRender         hou.RopNode.stopRender      hou.RopNode.isRendering
hou.RopNode.renderInBackground hou.interruptRender         hou.abortRender
hou.killRender
```

The module namespace `hou` (**853 names**) likewise contains **zero** names matching
`abort`, `kill`, `cancel`, or `stop`.

### 3.2 `render()` itself takes no cancel-shaped parameter

The build's own docstring gives the full signature:

```
render(self, frame_range=(), res=(), output_file=None, output_format=None,
       to_flipbook=False, quality=2, ignore_inputs=False, method=RopByRop,
       ignore_bypass_flags=False, ignore_lock_flags=False, verbose=False,
       output_progress=False)
```

No timeout, no cancellation token, no interrupt callback, no completion handle.

### 3.3 The two interrupt affordances that DO exist are Escape-driven and cooperative

| Symbol | Verdict | The build's own documentation |
|---|---|---|
| `hou.InterruptableOperation` | CONFIRMED | *"turn any Python code block into an interruptable operation … allows the user to press [Esc]"* |
| `hou.InterruptableOperation.updateProgress` | CONFIRMED | the call that observes the interrupt |
| `hou.updateProgressAndCheckForInterrupt` | CONFIRMED | *"**Deprecated**: Use InterruptableOperation … Return True if the user pressed Escape"* |
| `hou.OperationInterrupted` | CONFIRMED | the exception type |

Both are documented around a **keyboard gesture by a human at the machine**, and both require the
running code to **poll**. Neither is described as a programmatic, cross-thread cancel request.

### 3.4 Render *observation* hooks exist; whether they can cancel is not established here

| Symbol | Verdict |
|---|---|
| `hou.RopNode.addRenderEventCallback` | CONFIRMED |
| `hou.RopNode.removeRenderEventCallback` | CONFIRMED |
| `hou.RopNode.removeAllRenderEventCallbacks` | CONFIRMED |
| `hou.ropRenderEventType` | CONFIRMED |

`addRenderEventCallback` is documented as registering a callback run *"immediately before or after
the corresponding script callback on the ROP node, such as the Pre Frame or Post Frame script."*
That is an **observation** contract. Whether raising from such a callback aborts the render is a
**behavioural** question this leg did not test and does not assert either way (see §5).

### 3.5 The contrast — PDG already has exactly the affordance we are asking for

All CONFIRMED on the same build, in the same probe run:

| Symbol | The build's own documentation |
|---|---|
| `hou.TopNode.cancelCook` | *"Cancels the current cook"* |
| `hou.TopNode.pauseCook` | *"Pauses the current cook … work items already scheduled are allowed to continue"* |
| `pdg.GraphContext.cancelCook` | *"Cancels cooking"* |
| `pdg.GraphContext.canceling` | *"[read only] Set to True when the graph is canceling"* |
| `pdg.GraphContext.cooking` | *"[read only] Set to True when the graph is cooking"* |
| `pdg.WorkItem.cancel` | *"Cancels the work item, if it is cooking"* |

A cancel verb, a distinct pause verb, and two read-only state flags to observe the transition.
**That shape, on ROPs, is the request.**

---

## 4 · The request

1. A programmatic way to request cancellation of an in-flight ROP render — callable while
   `render()` has not yet returned, and safe to call from a thread other than the one that
   started it.
2. An observable state flag pair in the manner of `pdg.GraphContext.cooking` / `.canceling`, so a
   caller can tell *rendering*, *cancel requested*, and *stopped* apart rather than inferring
   them.
3. Whatever guarantee you can offer about granularity — "the in-flight frame/bucket completes,
   then it stops" is entirely workable and is the same contract PDG's `pauseCook` already
   documents. **A documented coarse guarantee beats an undocumented fine one.**
4. Failing all of the above: a statement of the sanctioned pattern for this on 22.x, so that
   integrators stop rediscovering the gap independently. If the sanctioned answer is
   "render out-of-process and terminate the process," we would rather be told that plainly than
   infer it.

---

## 5 · What this leg deliberately did NOT determine

Stated so nobody reads more into the above than it supports. These are behavioural questions
requiring a live cook; H3a was read-only introspection and did not run one:

- whether an Escape keypress interrupts a render started by `hou.RopNode.render()` from a script;
- whether raising an exception inside a render event callback aborts the render;
- whether wrapping a `render()` call in `hou.InterruptableOperation` has any effect on it;
- whether any out-of-process render path is externally terminable safely.

Each remains **UNVERIFIED**. None was assumed in either direction anywhere in this document.

---

## 6 · Reproducing this

```
# authoritative — live GUI session, 22.0.368
python harness/notes/h3a_probe.py --self-test        # controls; exits 1 if the probe cannot fail
hython3.13 harness/notes/h3a_placement.py out.json   # the namespace sweep in §3.1

# artifacts backing every table above
harness/notes/h3a/live_gui.json                 68 symbols, controls_ok true
harness/notes/h3a/live_gui_placement.json       full dir() sweep, 530 hou classes
harness/notes/h3a/live_gui_docs.json            the verbatim docstrings quoted here
harness/notes/h3a/reconciled.json               both producers merged, 0 conflicts
```

Both producers report build `22.0.368`. Symbol verdicts: **0 conflicts across 68 symbols.**
