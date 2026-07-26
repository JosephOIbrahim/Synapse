# SideFX ask — Houdini 22.0.368

**Status: DRAFT. Not sent. Joe sends this, not an agent.**
**Every claim below is VERIFIED-RUNTIME by live `dir()` / `inspect.signature` against
22.0.368 on 2026-07-26.** Doc URLs are given as the pinned `/docs/houdini22.0/` path so they are
checkable, but the primary evidence is the probe — the automated fetch could not read the pinned
tree (`ROBOTS_DISALLOWED`), and the unpinned `/docs/houdini/` path served a page whose breadcrumb
read "Houdini 21.0", so it is not a stable citation for a version-specific claim.

Context in one line: we run an in-process agent inside Houdini's Python interpreter. It mutates
live scenes containing an artist's unsaved work, so we need to be able to stop what we started.

---

## 1 — There is no way to cancel an in-flight `hou.RopNode.render()`

**The ask:** a cancellation surface for a running ROP render, reachable from Python.

**What we found.** `hou.RopNode`'s complete public method list on 22.0.368:

```
addRenderEventCallback   bypass   inputDependencies   isBypassed   isLocked
setLocked   removeAllRenderEventCallbacks   removeRenderEventCallback   render
```

No cancel, abort, interrupt, stop or kill — on `RopNode`, or inherited from `OpNode`, `Node`,
`NetworkMovableItem`, `NetworkItem`. `render()` itself takes no timeout, no handle, and no
callback that can refuse continuation.

**Two things we checked and ruled out** rather than assuming they were the answer:

- `hou.InterruptableOperation` — real and documented, but it wraps *our own* Python block and
  polls `updateProgress()`. It has no reach into a `render()` already blocking inside Houdini.
- `addRenderEventCallback` — delivers `hou.ropRenderEventType` notifications around frames.
  Observation, not control; no documented return value that refuses continuation.

**Why it matters to us.** An artist mid-Karma-render has a Stop control that cannot stop the
render. We can abort our own agent loop cooperatively, and we do, but the tool already running is
beyond reach. Any shape would help — a `cancel()` on the node, an interruptable variant of
`render()`, or a callback whose return value can halt the sequence.

**Note:** the PDG/TOPS side is complete by comparison — `cancelCook()` and the node-level cancel
verb are both present and usable. This ask is specifically about ROP renders.

---

## 2 — `hdefereval.executeInMainThread` does not exist on 22.0.368

**The ask:** confirmation of the supported main-thread marshal for 22.0, and a note in the docs if
`hdefereval` has moved or been renamed.

**What we found.** `hdefereval.executeInMainThread` is absent on 22.0.368, re-probed and
reproduced rather than carried forward from an earlier build's notes.

**Caveat we want to state plainly:** the `hdefereval` marshal layer is not fully probeable under
headless `hython`, so our verdict for the *layer* is "unverifiable headless" rather than "absent".
The specific symbol above is absent; we are not claiming the whole module is.

**Why it matters.** Every `hou.*` call we make marshals to the main thread. Knowing the supported
entry point for 22.0 — and having it documented — removes a class of guesswork for anyone doing
in-process work.

---

## 3 — `hou.TopNode.dirtyAllTasks` — deprecated, and the docs and signature disagree with common usage

**The ask:** two small documentation corrections.

**What we found**, via `inspect.signature` on 22.0.368:

```
SIGNATURE: dirtyAllTasks(self, remove_outputs: bool) -> void
DOC:       This method is deprecated in favor of hou.TopNode.dirtyAllWorkItems.
```

Two things worth surfacing:

1. **The keyword is `remove_outputs`.** `remove_files` appears widely in circulation, including in
   our own code, where it raises `TypeError` on every call — a bug that was entirely ours, and
   found only because we probed the signature rather than reading it.
2. **The deprecation is only discoverable at runtime.** It is in the docstring, not flagged
   anywhere a static reader or the published node reference would surface it.

**The general point, offered as feedback rather than a request:** we built a cross-reference of
every `hou.*` symbol we touch against the published reference, and found 19 symbols we use that
are deprecated and 48 that are undocumented but present. A phantom API fails loudly on first call;
a deprecated one works perfectly until the release that removes it. **A machine-readable
deprecation list — or a `deprecated` flag on the node/HOM reference pages — would let integrators
catch decay before an upgrade rather than after.** We are happy to share our census if useful.

---

## What we are not asking for

We are not asking for a workaround, and we have not built one. Where a capability is absent we
have recorded it as absent and stopped, rather than substituting an assumed API — that is how a
missing verb becomes a phantom in someone's codebase two versions later.

Happy to provide reproduction scripts for any of the above.
