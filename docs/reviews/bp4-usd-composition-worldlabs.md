---
ratified: false
leg: BP4-USDKNOW
wave: BP4
build: 22.0.400
source_blueprint: docs/intake/blueprint-h22-worldlabs-intent.md (v0.3, sec.2 + sec.4)
vocabulary:
  - harness/battleplan/notes/skills/solaris-usd-composition.md
  - harness/battleplan/notes/skills/composition-deep-dive.md
probe: harness/probes/bp4_usd_composition_probes.py
probe_evidence: harness/notes/h22wl/bp4_usdknow/stdout.txt
fixture: b6_wl_component.usdc (SOP USD Create Component, 19.8 MB; from BP3-PROBE, bp3/probe)
seed: harness/bench/corpus/usd/usd_composition_worldlabs_22.0.400.json
checker: harness/battleplan/notes/bp4_usdknow_check.py
---

# BP4 — USD composition decision record for the World Labs component (`ratified: false`)

**This record proposes a composition structure and explains it. It ratifies
nothing.** Promoting any tier or writing this into a live corpus is a human + CTO
act (blueprint rule **D-1**, "two keys"). No file under `python/synapse/` is
touched; nothing is registered.

**Runtime is truth; the blueprint is a proposal; the shipped skill is the
referee, not the truth.** Every choice below states an **arc**, the **LIVRPS
reason** each neighbour arc is rejected, the **failure it prevents**, and an
**evidence tier + anchor**. VERIFIED-RUNTIME / FIXTURE-VERIFIED rows anchor to a
line of `harness/notes/h22wl/bp4_usdknow/stdout.txt`; PROPOSED / DOC-STATED rows
carry a blueprint or reasoning anchor and are proven by nobody here.

---

## 0. The ladder every choice reasons from (confirmed, not recited)

The synthetic LIVRPS stage (probe Part C) put a **local, inherit, variant,
reference, payload and specialize opinion on one attribute** and read the
resolved order:

```
local > inherit > variant > reference > payload > specialize          stdout.txt:60
STRONGEST                                                     WEAKEST
```

This **matches** the shipped skill's stated order
(`solaris-usd-composition.md`) — now confirmed on 22.0.400, not taken on faith.

Two lines in `composition-deep-dive.md` were flagged by the CTO note at its top.
The probe settled both:

| Deep-dive line | Claim | Verdict | Anchor |
|---|---|---|---|
| **L138** (Specialize) | "if base changes to 0.5, spot1 gets 0.5 (**base is stronger**)" | **REFUTED** — spot1 keeps its own local 2.0 after base→0.5. A prim's local opinion always wins over what it specializes; specialize only supplies fallbacks. | stdout.txt:76 |
| **L201** (Inherit list-edit) | "first added = strongest inherit" | **CONFIRMED true** on 22.0.400 — `/Obj` inheriting A(=10) then B(=20) composes to 10.0. | stdout.txt:83 |

Specialize being the **weakest** arc (stdout.txt:68) is the single fact behind
"never put something on specialize that must survive an override."

---

## 1. What the SOP build actually authored (fixture ≠ proposal)

The blueprint §2.5 draws a proposed layout. The **real** component
(`b6_wl_component.usdc`, built by the H22 *USD Create Component* SOP) authored
this — walked live in probe Part A:

```
/wl_import                                     Xform   kind=component            stdout.txt:20
/wl_import/WL_fixture                           Xform   kind=component            stdout.txt:21
/wl_import/WL_fixture/geo                        Scope                            stdout.txt:22
/wl_import/WL_fixture/geo/proxy                  Scope   purpose=proxy   <collider> stdout.txt:23
/wl_import/WL_fixture/geo/proxy/world            Mesh    purpose=proxy            stdout.txt:24
/wl_import/WL_fixture/geo/proxy/world/geometry_0 Mesh    purpose=proxy            stdout.txt:25
/wl_import/WL_fixture/geo/proxy/autoproxy        Mesh    purpose=proxy            stdout.txt:26
/wl_import/WL_fixture/geo/render                 Scope   purpose=render  <splat>  stdout.txt:27
/wl_import/WL_fixture/geo/render/points_0        Points  (purpose inherited)      stdout.txt:28
```

**Three divergences from the §2.5 sketch, each a finding:**

1. **Purpose is authored on the `/geo/proxy` and `/geo/render` Scopes, and
   inherited down to the leaves** — the splat `Points` prim authors **no**
   purpose (authored=`default`) yet **computes** `render` (stdout.txt:33). The
   §2.5 sketch draws `purpose=render` on `/splat` itself; the shipped SOP path
   sets it once on the ancestor Scope. Purpose is an inherited-down attribute.
2. **The component authors ZERO variant sets** (stdout.txt:34). `splatTier`,
   `surface` and `physics` are **proposed authoring**, not present in the
   fixture — so their rows are PROPOSED, not FIXTURE-VERIFIED.
3. **No `customData:worldlabs`** — the root carries only `customData:userDocBrief`
   (stdout.txt:35). The provenance block is proposed, not authored.

The component is a **flattened, self-contained `.usdc`** (no internal
payload/reference arc — every prim's arc is `root`, stdout.txt:19-28). The
**payload is a shot-layer choice**: the shot composes this file *by payload*,
proven by round-trip below.

---

## 2. The decisions (blueprint sec.2)

### 2.1 Payload for the world (splat + collider together) — arc = **payload**

**Chosen:** the shot composes `/WL_<world_id>` by **payload**.

**LIVRPS reason — why not each neighbour:**
- **not Reference** — identical namespace encapsulation, one step *stronger*
  (stdout.txt:60), but a reference **cannot be unloaded**: the same
  `stage.Unload()` that drops a payload's subtree does nothing to a reference
  (`reference_unloadable=False`, stdout.txt:46). A referenced 2M-splat world is
  resident for the life of the stage.
- **not Sublayer** — sublayers merge prim paths directly with **no namespace
  encapsulation**; a world is an encapsulated asset with its own root, which is
  exactly what payload/reference give and sublayer does not.
- **not inline authoring** — 360 MB of spherical harmonics living in the shot
  layer, re-saved on every shot edit. Disk-first (blueprint §2.5 property 1)
  exists to forbid this.

**Failure prevented:** *payload unpacked in memory* — the whole appearance
resident when only the collider is needed for layout. Payloading the real 19.8 MB
component then `Unload` **drops 9 prims** and `Load` restores them
(`loaded=10 unloaded=1 reloaded=10`, stdout.txt:43); the composed shot prim
carries a payload arc (stdout.txt:44).

**Tier:** FIXTURE-VERIFIED (`payload-splat-collider`, stdout.txt:43;
`payload-arc-present`, stdout.txt:44) + VERIFIED-RUNTIME
(`payload-vs-reference-unloadable`, stdout.txt:46). The "~2M splats / ~360 MB SH
is heavy" rationale is DOC-STATED (blueprint §2.5 property 3).

### 2.2 Purpose split — splat=render, collider=proxy — arc = **local** (inherited-down)

**Chosen:** collider subtree under a Scope `purpose=proxy`; splat subtree under a
Scope `purpose=render`; the splat leaf inherits `render` from its Scope.

**LIVRPS reason — purpose is not a composition arc**, it is a local,
inherited-down attribute. The "neighbours" are the other purpose *values*:
- **collider not `default`** — a default-purpose collider **draws AND renders**;
  the collider mesh would appear in the beauty pass. `proxy` draws in a
  proxy-set viewport but is skipped by the final render.
- **collider not `guide`** — guides are for non-renderable annotation and several
  viewers hide them by default; too weak for the layout/scatter substrate.
- **splat not `default`** — a default-purpose splat is drawn in the interactive
  viewport on every refresh: 2M points, the **viewport re-cook** failure.
  `render` defers the splat to the renderer that wants it.

**Failure prevented:** *viewport re-cook* (2M splats drawn interactively) **and**
the collider bleeding into the beauty render. With this split a proxy-purpose
viewport moves ~47k collider tris while Karma XPU consumes the splat.

**Tier:** FIXTURE-VERIFIED — collider `purpose=proxy` (stdout.txt:31), render
Scope `purpose=render` (stdout.txt:32), splat leaf **authored=default /
computed=render** (stdout.txt:33). The inheritance nuance corrects the §2.5
sketch.

### 2.3 variantSet `splatTier { full | low }` — arc = **variant**

**Chosen:** a `splatTier` variant set on `/WL_<world_id>` selecting the 2M-splat
`full` tier vs the 500k `low` tier.

**LIVRPS reason — why not each neighbour:**
- **not reference-swap** (author two files, swap the reference) — a variant
  selection switches representation **without recomposing the layer stack or
  re-resolving an asset path**; a reference swap forces a recomposition.
- **not two payloads** (load one or the other) — workable, but the selection is
  then a load-state, not a single portable metadata opinion the shot can set and
  travel.
- **variant sits ABOVE reference/payload in the ladder** (stdout.txt:60), so the
  **shot's** tier selection wins over anything the component's own payload ships.
  That is the correct authority direction: the shot decides the tier.

**Failure prevented:** a stack recomposition per LOD switch; and the component
overriding the shot's tier choice.

**Tier:** **PROPOSED** (`variantset-splattier`) — the SOP build authored 0 variant
sets (FIXTURE-VERIFIED `variantsets-absent-in-sop-build`, stdout.txt:34). This is
proposed authoring, not an observed fact.

### 2.4 variantSet `physics { none | collision }` — arc = **variant** (gated G-1)

**Chosen:** a `physics` variant set applying `UsdPhysicsCollisionAPI` to
`/geo/collider` under the `collision` variant, nothing under `none`.

**LIVRPS reason:** variant so a sim-ready export toggles the collision schema
**without a second asset or a render/sim fork**; `none` is the default so the
render path never carries physics metadata. Same authority argument as §2.3 —
the consumer selects.

**Failure prevented:** a permanently sim-encumbered asset; a fork between the
render export and the sim export.

**Tier:** **PROPOSED, behind gate G-1** (blueprint §9). No Isaac Sim evidence is
sought here — opening G-1 is D-1's, not this leg's (`variantset-physics`).

### 2.5 kind = component — arc = **local** (metadata)

**Chosen:** `kind=component` on the world root.

**LIVRPS reason — kind is local metadata, not an arc.** Neighbour kinds:
- **not `assembly` / `group`** — those own sub-models; a Marble world has no
  sub-model children to own. It **is** the leaf model.
- **not absent** — `Usd.ModelAPI` model-hierarchy traversal and the spatial
  lane's organization walk (blueprint §3.3 I3.a/I3.b) rely on `kind` to stop at
  the world as one queryable unit; without it, model iteration never sees the
  world as a model.

**Failure prevented:** the world not being recognised as a model unit — an
organization walk that can't find the component.

**Tier:** FIXTURE-VERIFIED (`kind-component`, stdout.txt:30) — the SOP build
authors it on the wrapper Xform.

### 2.6 customData:worldlabs provenance — arc = **local** (metadata dict)

**Chosen:** `customData:worldlabs = {world_id, model, frame, semantics_metadata,
source_urls, applied}` on `/WL_<world_id>`.

**LIVRPS reason — why not each neighbour:**
- **not a typed USD schema / applied API schema** — the provenance is
  SYNAPSE-private, not a USD standard; a typed schema risks colliding with vendor
  schemas and needs registration. `customData` is a free-form local dict that
  **travels with the prim through reference and payload**.
- **not sidecar-manifest only** — the manifest (§2.6) *is* the sidecar;
  `customData` puts the essential provenance **on the composed prim** so a
  spatial query has it without loading the sidecar.

**Failure prevented:** provenance divorced from the prim (lost across a payload);
schema collision with vendor USD.

**Tier:** **PROPOSED** (`customdata-worldlabs-provenance`) — the SOP build
authored only `userDocBrief`, **not** `worldlabs` (FIXTURE-VERIFIED
`customdata-worldlabs-absent-in-sop-build`, stdout.txt:35). The `applied`
sub-block is what makes the frame conversion idempotent (§2.8).

### 2.7 instanceable — chosen **false** — arc = **local** (metadata flag)

**Chosen:** the world component is **not** marked `instanceable`.

**LIVRPS reason — why not `true`:**
- there is exactly **one instance of each world**; instancing shares nothing.
- an instanceable prim becomes a shared prototype whose **per-instance variant
  selection (splatTier/surface) and per-instance overrides are blocked** — the
  shot could no longer pick a tier or override per placement (directly at odds
  with §2.3/§2.4).
- instance proxies complicate the payload unload path (§2.1).

**Failure prevented:** frozen variant selection and blocked shot overrides on the
world.

**Tier:** **PROPOSED** (`instanceable-false`) — a design decision, no runtime
anchor. *Caveat:* if the **same** world were placed many times, a per-placement
`instanceable` reference is a different, legitimate structure; "one world = one
component" (§2.5) is what makes `false` correct here.

### 2.8 Where the metric / ground / chirality transforms live — arc = **local** (baked + `applied` ledger)

**Chosen:** the metric+ground and axis (chirality) conversions are **baked into
the exported splat/collider geometry** and recorded in
`customData:worldlabs.applied`. They are **not** re-applied as a live `Xform` op
on `/WL_<world_id>` in the shot.

**LIVRPS reason — why not a live Xform on the payloaded prim:**
- a payloaded file already in metric + Y-up, then wrapped in a live `Xform` that
  converts again, is scaled and flipped **twice** — the **double transform**.
- an `Xform` op is a *local* opinion the shot could clobber, decoupling the
  geometry from its own frame.
- the **`applied` ledger** (idempotent per blueprint I2.d) means a re-open **never
  re-converts**: each conversion step is recorded once, checked before re-applying.

**Placement is separate.** Positioning the world *within the shot* is a
legitimate, distinct **shot-layer `Xform`** — do not read "no Xform for the frame
conversion" as "no placement Xform." The frame conversion is baked; the placement
is authored live in the shot.

**Failure prevented:** *double transform* (scaled/flipped twice) and a
non-idempotent re-conversion on every re-open.

**Tier:** **PROPOSED** for the baked-not-Xform placement of the transforms
(`transforms-baked-not-xform`); **DOC-STATED** for the conversion **order**
(metric+ground → axis → Houdini Y-up; `frame-conversion-order`, blueprint §2.7 /
WL-API-03). No fixture round-trip through the full conversion was run in this leg.

---

## 3. The demo layer (blueprint sec.4) adds no composition arc

The demo (§4) is a **composition layer that authors nothing upstream** (rule
D-0). Its beats **consume** the §2.5 component; none of them introduce a new
composition choice. Two beats are load-bearing evidence *for the choices above*:

- **Beat 3** ("land on the stage as **one component**, right way up, metric,
  ground at y=0") is the demo floor — it is exactly the §2.1 payload +
  §2.8 baked-frame + §2.5 kind decision, exercised end to end.
- **Fallback F-1** (§4.2 / §10 R-1: if the splat will not render, the **collider +
  pano dome light** carry beats 4-8, splat viewport-only) is why the **collider is
  the substrate** (BLU-03): the `purpose=proxy` collider (§2.2) is the queryable,
  render-independent half the demo can always fall back to. This reinforces the
  purpose split — the collider must stand alone.

So sec.4's contribution to this record is confirmation, not new structure: the
component is the demo's floor and the proxy collider is the load-bearing half.

---

## 4. Evidence tiers — summary

| Tier | Count | Meaning |
|---|---|---|
| VERIFIED-RUNTIME | 7 | a probe stdout line proves it on hython 22.0.400 (pxr resolution) |
| FIXTURE-VERIFIED | 8 | the b6 SOP component proves it on the actual file |
| DOC-STATED | 2 | read from the blueprint / shipped skill; unverified here |
| PROPOSED | 5 | a design choice not present in the SOP build and not runtime-proven |

Machine-readable in `harness/bench/corpus/usd/usd_composition_worldlabs_22.0.400.json`
(`ratified: false`). Gate: `python harness/battleplan/notes/bp4_usdknow_check.py`
→ exit 0 iff every VERIFIED-RUNTIME / FIXTURE-VERIFIED row's anchor greps clean
(and carries its `arc=` and `verify` tokens). Exit code pasted in the receipt.

---

## 5. Proposed final destination (UNEXECUTED — D-1)

RECON T1 names the LOP-knowledge home as
`harness/notes/verified_lop_solaris_knowledge_<build>.json`; **no `22.0.400`
variant exists yet** (RECON mismatch). When a human + CTO ratify this seed, it
moves there. **Do not run** — recorded, not executed:

```
git mv harness/bench/corpus/usd/usd_composition_worldlabs_22.0.400.json \
       harness/notes/verified_lop_solaris_knowledge_22.0.400.json
```

---

## 6. Reproduce

The `b6_wl_component.usdc` is **gitignored** (19.8 MB). Point the probe at it and
pin the build (RECON T2):

```
export SYNAPSE_HYTHON="C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe"
export HOUDINI_USER_PREF_DIR="C:/Users/User/OneDrive/Documents/houdini22.0"
export BP4_WL_USDC=".../worktrees/bp3-probe/harness/notes/h22wl/bp3_probes/b6_wl_component.usdc"
"$SYNAPSE_HYTHON" harness/probes/bp4_usd_composition_probes.py > harness/notes/h22wl/bp4_usdknow/stdout.txt 2>&1
python harness/battleplan/notes/bp4_usdknow_check.py
```

Part C (LIVRPS) needs no fixture and reproduces deterministically; a missing b6
degrades Parts A/B to BLOCKED while the LIVRPS winners still print.

---

## 7. Findings / for_ruling

- **F-1 (fixture ≠ sketch).** The SOP build authors purpose on the `geo/proxy`
  and `geo/render` **Scopes** and inherits it down; §2.5 draws it on the leaves.
  The record follows the runtime.
- **F-2 (proposed, not built).** `splatTier`/`surface`/`physics` variant sets and
  `customData:worldlabs` are **not** in the SOP output — PROPOSED, pending an
  authoring step. A human may not read them as FIXTURE-VERIFIED.
- **F-3 (deep-dive correction).** `composition-deep-dive.md:138` is wrong
  (specialize is weakest; local wins) and `:201` is right on 22.0.400. If that
  skill is ever promoted to corpus, L138 must be fixed first.
- **for_ruling:** promotion of any row's tier, and the `git mv` to the LOP
  knowledge home, are D-1 acts — held for human + CTO.
