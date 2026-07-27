# SYNAPSE — RETINA VERIFY

**Harness ID** `RETINA-VERIFY` · **Authored** 2026-07-27
**Governed by** `harness/AGENT_CONSTITUTION.md` · **Ruled by** `harness/notes/CTO_RULINGS_01.md`
**Builds on** the existing `retina/` package — `events.py`, `ingest.py`, the T0/T1 tiers

---

## 0 · First principles

SYNAPSE has perfect scene access. It can enumerate every node, parm, prim and transform. **Any
CV-derived belief about "what is in the scene" is strictly worse than what it already knows.**

So vision is not for seeing the scene. It is for one claim the scene graph structurally cannot
make:

> **"I mutated X, and only X changed."**

Everything below exists to make that sentence checkable, or to prove it cannot yet be checked.

### What the claim requires

```
1  a render BEFORE
2  a mutation
3  a render AFTER
4  a way to know WHICH PIXELS BELONG TO X     <- the crux
5  a comparison that separates CHANGED from NOISE
```

Step 4 is the whole difficulty. Without it you can only say *"something changed"*, which is
useless. With it:

```
delta    = |after - before| > noise_floor
expected = mask(X)                       from the integer object-ID AOV
leak     = delta AND NOT expected         <- pixels that changed and should not have
miss     = expected AND NOT delta         <- pixels that should have changed and did not
```

Four set operations. **`leak` is the finding this harness exists to produce.**

### Five ways this lies, each of which has killed a check in this repository already

**Sampling noise.** Two renders of the *same* scene differ — Monte Carlo. So `delta > 0` means
nothing. The noise floor is not a constant to be assumed; it is **measured, per scene, by
rendering twice with no mutation.**

**Unstable IDs.** Same prim, different frame or different renderer → same integer? Unknown, and
already an open SideFX ask ("stable integer object-ID render-var contract across Karma CPU/XPU").
**If IDs are unstable, the mask is wrong and every verdict is wrong.**

**Colour management.** Comparing display-transformed pixels measures the transform, not the render.
`retina/ingest.py` already handles this — ID/data AOVs read Raw, never colour-transformed. Do not
undo it.

**Denoising.** A denoiser makes two identical renders differ *non-locally*. With it on, a
one-prim mutation can move pixels anywhere in frame. It must be off, or the primitive is void.

**Capture path.** How pixels leave Houdini is UNVERIFIED on 22.0.368. Flipbook, Karma-to-disk,
Copernicus readback — none confirmed, and Copernicus buffer-to-numpy is itself an open SideFX ask.

---

## 1 · Where OpenCV belongs, and where it does not

`retina/ingest.py` deliberately rejects `cv2.imread` — *"CVE-gated, colour-blind"*. That decision
stands. **cv2 is not an I/O library here.**

`cv2` is also **absent from `hython3.13`** (verified 2026-07-27; OIIO 2.5.18 and OCIO 2.5.0 are
present). That is not an obstacle — RETINA's worker already runs in **its own venv**, which is
exactly where cv2 belongs.

```
hython3.13          hou.* access, capture, no cv2
retina worker venv  OIIO ingest -> float arrays -> cv2 ANALYSIS
```

**What cv2 earns on float arrays OIIO has already read:**

| operation | what it answers | why numpy is not enough |
|---|---|---|
| `connectedComponentsWithStats` | *"3 disjoint regions changed, expected 1"* | the single highest-value sentence this harness can produce |
| `morphologyEx` (open/close) | single-pixel sampling noise vs real change | otherwise every delta reads dirty |
| `findContours` | the SHAPE of what moved, so a leak can be localised | a bare pixel count cannot be pointed at |
| `Laplacian` variance | focus / blur drift | secondary, cheap |
| `compareHist` | exposure / white-balance drift | secondary, cheap |

The core diff is numpy. **cv2 earns its place on the delta MASK, not on the pixels.**

---

## 2 · The mile structure, and why it is ordered this way

Each mile makes the next one *measurable*. No mile builds on an unverified predecessor — that is
the rule this repository learned the hard way (R91: a composition dispatched as two independent
legs; R64: a ruling built on a stale design brief).

```
V0  reconcile      the orphaned RETINA M2 - 1,966 lines on archive/retina-m2-orphan
V1  capture probe  READ-ONLY. what capture APIs exist live on 22.0.368, and what do they cost
V2  the controls   noise floor + ID stability. THE GATE - if these fail, V3 is meaningless
V3  scoped delta   the primitive: leak and miss, per mutation
V4  cv2 mask kit   connected components, morphology, contours - in the worker venv
```

**V2 is the gate, and it is the whole harness in miniature.** It renders the same scene twice with
no mutation and asks: *is the delta empty?* If it is not — beyond a measured floor — **the
instrument cannot measure anything**, and V3 would produce confident nonsense.

That is the positive control this project has learned to demand, applied before the thing it
guards is built rather than after.

---

## 3 · The standing rules that apply

- **Probes beat memory.** Every `hou.*` symbol confirmed by live `dir()` before code is written
  against it. `ABSENT` requires a positive control on the same class (R50).
- **A check must be able to fail** (Law 1), and its READER must be calibrated too (R60).
- **Every number carries a producer path and an interpreter** (Law 2, R31).
- **Commit product before writing the receipt** (R93). `green` with zero commits is not a
  terminal state.
- **Declare `touches`** so a collision is detectable before dispatch, not at merge (R92).
- Never push, never merge to master, never tag.
