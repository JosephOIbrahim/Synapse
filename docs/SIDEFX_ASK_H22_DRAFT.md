# SideFX ask — Houdini 22.0.368

**Status: DRAFT v2. Not sent. Joe sends this, not an agent.**

**v1 was wrong and is superseded.** It claimed Houdini exposes no way to cancel an in-flight
render. A full sweep of the local 22.0.368 reference plus runtime probes found `rkill` — an
hscript command that stops a render, present and working. The claim below is narrower and every
part of it survives your own verification.

All claims are `VERIFIED-RUNTIME` on 22.0.368, 2026-07-26, by live `dir()` / `hou.hscript()`,
cross-checked against the reference shipped with the build (`$HFS/houdini/help/hom.zip`) rather
than the web docs — the unpinned `/docs/houdini/` path serves 21.0 and the pinned
`/docs/houdini22.0/` path is robots-disallowed to automated fetch.

Context: we run an in-process agent inside Houdini's Python interpreter. It mutates live scenes
containing an artist's unsaved work, so we need to stop what we started.

---

## 1 — A custom render var with no `ray:` prefix emits a correctly-named AOV full of zeros, silently

**This is the one we would most like fixed.**

On 22.0.368, the `ray:` namespace prefix is required on a custom render var's `sourceName`. Without
it, `objectid`, `primid`, `Ci`, `C` and `color` each produce **a correctly-named EXR part filled
entirely with zeros**. No error, no warning, no diagnostic.

A pipeline reading that part gets zeros and has no way to know it asked wrong. We lost a day to it,
and the failure is indistinguishable from "the render legitimately produced nothing there."

**The ask:** warn on an unresolvable `sourceName`, or fail the render. Either is better than a
silent, well-formed, empty AOV.

Two related observations from the same probe, offered as feedback:

- **`format=int32` is refused outright** — *"Unsupported image data format int32 in RenderVar."* So
  an ID-style AOV can only be float, and the shipped `primidfilter` default
  `['minmax', {'mode':'idcover'}]` then blends 7.4% of pixels, 91.9% of those on prim boundaries.
  For anything using an ID plane as a mask, the boundary is exactly where correctness matters.
- **`primid` is per-polygon and collides across objects.** Two solo spheres produced 50 ids each
  with 49 shared. We are not asking for this to change — but the documentation does not make clear
  that it is not an object identifier, and it reads like one.

---

## 2 — `hou.ActiveRender` is documented but not implemented


`hom.zip:hou/ActiveRender.txt` documents a full class — `kill()`, `suspend()`, `resume()`,
`isSuspended()`, `processId()`, `host()`, `frame()`, `command()` — and marks it
`#replaces: /commands/rkill /commands/rps`. Same for the module-level `hou.activeRenders()`.

Every member carries `#status: ni`, and both are absent at runtime:

```
hasattr(hou, "ActiveRender")   -> False
hasattr(hou, "activeRenders")  -> False
```

**The ask, either is fine:**
- implement it — it is the documented HOM path to render control and the hscript commands it
  replaces already work, or
- mark it clearly enough in the published reference that an integrator reading the docs does not
  build against it.

**Why it matters to us.** We found this only because we probed runtime after reading the
reference. A team that trusted the documentation would write `hou.activeRenders()` and get an
`AttributeError` in production. `#status: ni` is visible in the raw help source but not, as far as
we can tell, on the rendered page.

---

## 3 — `hou.RopNode` has no cancel method, which forces integrators out to hscript

Complete public method list on 22.0.368:

```
addRenderEventCallback   bypass   inputDependencies   isBypassed   isLocked
setLocked   removeAllRenderEventCallbacks   removeRenderEventCallback   render
```

Nothing inherited from `OpNode`, `Node`, `NetworkMovableItem` or `NetworkItem` reaches a running
render. `render()` takes no timeout, no handle, and no callback that can refuse continuation.

**We are not claiming render cancellation is impossible** — `rkill` works, and we will use it.
The friction is that a Python integrator holding a `RopNode` has nothing to call on it, and has to
drop to `hou.hscript("rkill ...")` with a process pattern rather than a node reference.

`hou.InterruptableOperation` and `addRenderEventCallback` both look like the answer and are not:
the first wraps our own Python block, the second observes without controlling.

**The ask:** a `cancel()` on `RopNode`, or a documented pointer from `RopNode.render()` to
`rkill` / `ActiveRender` so the path is discoverable from where an integrator actually starts.

---

## 4 — `hdefereval.executeInMainThread` is absent on 22.0.368

Re-probed and reproduced, not carried forward from an earlier build's notes.

**Caveat stated plainly:** the `hdefereval` marshal layer is not fully probeable under headless
`hython`, so our verdict for the *layer* is "unverifiable headless" rather than "absent". The
specific symbol is absent; we are not claiming the module is.

**The ask:** confirmation of the supported main-thread marshal for 22.0, documented.

---

## 5 — `hou.TopNode.dirtyAllTasks` — two small documentation corrections

`inspect.signature` on 22.0.368:

```
dirtyAllTasks(self, remove_outputs: bool) -> void
"This method is deprecated in favor of hou.TopNode.dirtyAllWorkItems."
```

1. **The keyword is `remove_outputs`.** `remove_files` circulates widely, including in our own
   code, where it raised `TypeError` on every call — entirely our bug, and found only because we
   probed the signature rather than reading it.
2. **The deprecation is only discoverable at runtime**, in the docstring — not flagged anywhere a
   static reader or the published reference surfaces.

**Feedback rather than a request:** we cross-referenced every `hou.*` symbol we touch against the
shipped reference and found 19 we use that are deprecated and 48 present but undocumented. A
phantom API fails loudly on first call; a deprecated one works perfectly until the release that
removes it. **A machine-readable deprecation list, or a `deprecated` flag on the reference pages,
would let integrators catch decay before an upgrade rather than after.** Happy to share our
census.

Two related observations from the same exercise, offered in the same spirit:

- **`karma` and `karmarenderproperties` are flagged deprecated at runtime, and their help pages
  (~70KB and ~96KB) do not mention it.** An artist reading the documentation has no way to know.
- **`#status: ni` and runtime-only deprecation are the same problem from opposite directions** —
  in one the docs describe what does not exist, in the other runtime knows what the docs do not.

---

## What we are not asking for

We are not asking for a workaround, and we have not built one. Where a capability is absent we
record it as absent and stop, rather than substituting an assumed API — that is how a missing verb
becomes a phantom in someone's codebase two versions later.

Reproduction scripts available for any of the above.
