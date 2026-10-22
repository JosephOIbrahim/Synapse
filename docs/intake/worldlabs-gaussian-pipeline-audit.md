# World Labs Gaussian Splat Pipeline — Blueprint Accuracy Audit

**Status:** VERIFIED-RUNTIME audit of an external blueprint. Authorizes no code change, no ratification, no scope change to `blueprint-h22-worldlabs-intent.md`.
**Subject:** *"SYNAPSE Automated Pipeline Blueprint (Gaussian Splats Parts 1 & 2).docx"* — an external artifact supplied to the seat on 2026-10-22. Not a repo document. Not a SideFX document.
**Build:** Houdini 22.0.400 (pinned). Every live result below was produced on that build.
**Verdict:** **The blueprint's script cannot run.** Eleven of its calls raise or silently no-op. Five of its prose claims are not implemented by its own code. The pipeline concept survives; the script does not.
**Producer:** `harness/probes/worldlabs_pipeline_corrected.py` — `--verify` mode. 11/11 corrections hold on 22.0.400.
**Companions:** `docs/intake/blueprint-h22-worldlabs-intent.md` (the repo's own World Labs intent, v0.3.1, `ratified:false`).

---

## 0. How to read this

The blueprint is a **proposal**, and the repo's own intake rules already say so: every node type and parm name in an intake document is **V0 until a probe on the pinned build prints it** (`blueprint-h22-worldlabs-intent.md` §0.1).

This audit ran that probe. The blueprint's script was executed call by call in `hython` against 22.0.400. What it actually did is recorded below.

**Three things to take away:**

1. **The script dies on line 109.** Not at the end — mid-build, inside the wrangle setup. Everything after that line never runs.
2. **The prose outruns the code.** The "Corrected Error Audit" section claims five fixes. The script implements none of them.
3. **The catalogue in this repo is wrong for three node types.** Anyone who builds from `rag/catalog/h22.0.400/` for `gltf`, `distantlight` or `usdrender` writes a broken script. This is the highest-impact finding, because it is not about the blueprint.

---

## 1. How the audit was produced

**Method.** Every call in the blueprint's §3 script was executed verbatim against the live build. Failures were recorded from the raised exception, not inferred from documentation. The raw records are `blueprint_live_probe.json` (67 records) and `blueprint_live_probe2.json` (38 records).

**Re-run the whole thing:**

```
env -u HOME "C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" \
    -s -P harness/probes/worldlabs_pipeline_corrected.py --verify
```

It prints one line per correction, writes `harness/probes/worldlabs_pipeline_verification.json`, and exits non-zero if any correction fails to hold. **A check that cannot fail is deleted** — every assertion in `--verify` is written to fail on the next build that changes the truth.

**Cross-checks used before running anything:**

- `rag/catalog/h22.0.400/` — the repo's live node catalogue (5,140 types indexed, 18 per-category JSONs).
- `python/synapse/cognitive/tools/data/h22_symbol_table.json` — the introspected dotted symbol table for build 22.0.400 (36,472 names).

Both were used as *hypothesis sources*. The live run overrode them where they disagreed — which is the point, and where the catalogue turned out to be wrong (§4).

---

## 2. The eleven defects

Each row was produced by running the blueprint's exact call and reading the exception. The "Correction" column is what the corrected script does instead.

| # | The blueprint calls | What actually happens on 22.0.400 | Correction |
|---|---|---|---|
| **F1** | `hou.Node.disconnect()` | `AttributeError: 'SopNode' object has no attribute 'disconnect'` | `node.setInput(0, None)` |
| **F2** | `createNode("labs::bake_gsplat")` | `OperationFailed: Invalid node type name` | `createNode("bakegsplat")` — a built-in H22 SOP, not a Labs node |
| **F3** | `createNode("labs::normals_from_gsplat")` | `OperationFailed: Invalid node type name` | `createNode("labs::normals_from_gsplats::1.0")` — plural **and** versioned |
| **F4** | `normals_jungle.setInput(1, color_jungle)` | `InvalidInput: Invalid input.` — the node has one input | The two-input relight node is `labs::relight_gsplats::1.1`, a **LOP**; it creates in `/stage`, not in a SOP |
| **F5** | `gltf.setParms({"filepath": ...})` | `Invalid parameter name: filepath` | `gltffile` |
| **F6** | `gltf.setParms({"import_geometry_as": 1})` | `Invalid parameter name: import_geometry_as` | `importnodegeometryas`, token `flattenedgeometry` (tokens are `packedprimitive`, `flattenedgeometry`) |
| **F7** | `wrangle.parm("strength").set(-1.0)` ×6 | `AttributeError: 'NoneType' object has no attribute 'set'` — **the parms do not exist**. The script dies here | Create them: `ParmTemplateGroup` + `FloatParmTemplate` + `setParmTemplateGroup` |
| **F8** | `krs.parm("renderer").set("XPU")` | `AttributeError` — `renderer` is not a parm | `parm("engine").set("xpu")` — the token is **lower case** |
| **F9** | `krs.parm("samples").set(256)` | `AttributeError` | `parm("samplesperpixel").set(256)` |
| **F10** | `stage.createNode("usdrender")` | `OperationFailed: Invalid node type name` — the only render node in `/stage` is `usdrender_rop` | `createNode("usdrender_rop")` |
| **F11** | `distantlight.setInput(0, fog_box)` | `distantlight inputs: []` — zero inputs | Do not wire geometry into the light. Intensity and exposure are USD-exposed parms, resolved by pattern at runtime |

**The script dies at F7.** Six parameter writes, in a row, on parameters that were never created. Everything after line 109 — the Solaris stage, the Karma settings, the render ROP, the whole Stage 3 — never executes.

### 2.1 What the blueprint gets right

An audit that only lists failures is half an audit. These calls were **verified to work**:

- `trange.set(1)` — `trange` is a menu stored as an index; index 1 evaluates to `normal`, which is "Render Specific Frame Range". The blueprint's intent is correct even though the mechanism is accidental.
- `usdrender_rop` has `f1`, `f2`, `f3`.
- `bakegsplat.setInput(0, file)` — works, and `bakegsplat` carries a `linearize` toggle (default 1), which is exactly right for a World Labs PLY whose `scale_0..2` values are stored in log space.
- `attribwrangle.parm("snippet")` — works.
- `sopimport.parm("soppath")` — works.
- `karmafogbox` and `karmarendersettings` both exist.
- `blast.parm("group").set("call")` — syntactically valid. Whether a group named `call` exists is a different question (§3.5).

The **architecture is sound**: SOP side for the splat animation, LOP side for the relight and the Karma render, `sopimport` bridging them. That structure survives the audit intact.

---

## 3. Five claims the code does not implement

The blueprint has a section called *"2. Corrected Error Audit Across Tutorials"*. It lists four fixes and the exec summary adds a fifth. **None of the five appears in the script.**

### 3.1 F-OPEN-1 — Coordinate space

> *"coordinate space mismatches … Replaced … with automated OpenUSD transform matrices (UsdGeom.XformOp)"*

The script contains no `XformOp`, no up-axis handling, no coordinate conversion of any kind.

This is not a new defect. The repo's own intake records that a **previous** World Labs blueprint was rejected for *"Y-up assumed where Marble is +Y-down (WL-EX-05)"* (`blueprint-h22-worldlabs-intent.md` §0.4, rejected-predecessor list). This blueprint repeats that exact rejection reason while claiming to have fixed it.

**To settle:** cook one World Labs export, read the point cloud's up axis, diff the pre- and post-conversion bounds.

### 3.2 F-OPEN-2 — VEX fragility

> *"Eliminated live-coding typo risks by replacing manual string-typed VEX wrangles with a pre-compiled, robust VEX AST template backed by Moneta v5 schema gates"*

The script sets a **raw VEX string** on the wrangle: `anim_wrangle.parm("snippet").set(vex_code)`. That is precisely the "manual string-typed VEX wrangle" the claim says it eliminated. There is no AST. There is no schema gate.

**To settle:** assert that a VEX fragment is compiled from a template, not concatenated from a string.

### 3.3 F-OPEN-3 — Graph disconnection

> *"Graph disconnection handled via programmatic traversal"*

The only disconnection API the script names is the phantom in F1, and the script contains **no traversal and no disconnection at all**. The graph as written has nothing to disconnect.

**To settle:** prove it or drop the claim.

### 3.4 F-OPEN-4 — Karma XPU render and FFmpeg export

> *"Karma XPU 4D Time-Sample Render & FFmpeg Export"*

`usdrender_rop` has **no video or ffmpeg output parm**. Its output-related parms are `outputimage`, `lopoutput`, and the `outputprocessor` group. `outputimage` is an image sequence.

Separately: the script never writes `output_mov`. It prints a line saying it is exporting. **The deliverable is never produced** — the blueprint's headline output does not exist.

**To settle:** render 2 frames to a real path and assert the file exists on disk afterwards.

### 3.5 F-OPEN-5 — The `call` group

The blast node targets a point group named `call`. **No node in the graph creates a group named `call`.** Nothing in the script names a collider group. The blast removes whatever happens to be there — possibly nothing.

**To settle:** cook the collider import and list the point groups it produces.

---

## 4. Two repo-level findings

These are not about the blueprint. They are about **this repo**, and they matter more.

### 4.1 The node catalogue mis-describes three types

`rag/catalog/h22.0.400/` is the repo's node-type authority per `CLAUDE.md` (*"the **node-type** authority is the live catalogue `rag/catalog/h22.0.400/`"*).

It carries **unversioned** entries for `gltf`, `distantlight` and `usdrender` whose parm names raise `Invalid parameter name` on the live build, and whose `usdrender` entry does not resolve at all.

The live defaults resolve to `gltf::2.0` and `distantlight::2.0` — 203 parms on the light, with USD-exposed names like `xn__inputsintensity_i0a`. The catalogue describes the superseded variants.

**Anyone building from the catalogue for these three types writes a broken script.** That is a live trap in the repo's own authority file.

### 4.2 `dir(hou.Node)` is not a valid phantom test

This one changes how the repo's phantom checks must be written.

`dir(hou.Node)` exposes **146 members**. `hasattr(hou.Node, 'parm')` is **False**. `'parm' in dir(node_instance)` is **True**, and `node.parm('snippet')` works fine.

Instance methods that work on every live node are **absent from the class-level `dir()`**. The symbol table's 116 `hou.Node.*` entries therefore under-represent the class.

**The rule this yields:** for `hou.Node` members, class-level `dir()` / `hasattr()` is not evidence of absence. The decisive test is **calling on an instance**.

> This is exactly the failure F1 looked like. "Is `disconnect` in `dir(hou.Node)`?" says no — and here it happens to be right. But the same method says no about `parm`, `setParms`, `cook` and `addParm`, which all work. A checker built on class-level `dir()` produces false positives *and* false negatives on the same class.

**To settle:** the phantom lint should gain a rule that `hou.Node` membership requires an instance-level probe, not a class-level `dir()`.

---

## 5. The corrected pipeline

`harness/probes/worldlabs_pipeline_corrected.py` is the blueprint with all eleven fixes applied.

- **`--verify`** asserts each correction against the live build. Currently **11/11**.
- **`--build`** constructs the graph, taking the three asset paths as arguments. No hardcoded paths.

The corrected shape:

```
/obj
  SYNAPSE_ENV_NETWORK (geo)
    file_desert_ply ──► bake_desert ──► normals_desert ──┐
    file_jungle_ply ──► bake_jungle ──► normals_jungle ──► anim_jungle_solver ──► blast_sky_blue ──► ENV_OUT
    gltf_jungle_collider ──► color_jungle  (collider; NOT wired into the normals node)

/stage
  import_synapse_env ◄── sopimport (soppath = ENV_OUT)
  fog_box
  sun_light            (distantlight — no inputs; intensity/exposure are USD-exposed parms)
  xpu_settings         (karmarendersettings — engine=xpu, samplesperpixel=256)
  rop_karma_xpu        (usdrender_rop — trange=1 'normal', f1, f2, outputimage)
```

**Two deliberate omissions.** The corrected script does not wire the collider colour into the SOP chain (F4 — the node has one input), and it does not implement an up-axis conversion (F-OPEN-1 — the conversion's *correct* form is not yet known, so inventing one would be worse than leaving it open).

**One resolution that is deliberate:** the Solaris light's intensity and exposure parms are resolved **by pattern at runtime**, not hardcoded. Their live names (`xn__inputsintensity_i0a`) carry a build-specific suffix. A hardcoded name is a phantom waiting for the next build.

---

## 6. What this means for the repo's own intake

`blueprint-h22-worldlabs-intent.md` is `ratified:false` and stays that way. **This audit does not change it**, and it does not add scope to it.

What it does do:

1. **Confirms the intake's epistemics were right.** The intake said every node name is V0 until probed. The blueprint's script had not been probed. Probing it broke it. The rule held.
2. **Adds two defects the intake's risk register should now carry** — the catalogue's three wrong types, and the class-level `dir()` trap. Both are repo-side and both affect any future World Labs work.
3. **Leaves F-OPEN-1..5 open on purpose.** They are unproven claims, and the probe that would settle each one is written down in §3.

---

## 7. Tier labels

| Claim | Tier |
|---|---|
| The eleven defects and their corrections | **VERIFIED-RUNTIME** — live exception text on 22.0.400 |
| The blueprint's script dies at F7 (line 109) | **VERIFIED-RUNTIME** |
| The five unimplemented claims (§3) | **VERIFIED-RUNTIME** — absence of the mechanism in the source, read directly |
| The catalogue's three wrong types (§4.1) | **VERIFIED-RUNTIME** — live `Invalid parameter name` on the catalogue's own names |
| `dir(hou.Node)` under-representation (§4.2) | **VERIFIED-RUNTIME** — 146 class members, `hasattr` False, instance True |
| The blueprint's *intent* for each stage | **STATED** — the document's claim, not the code's behaviour |
| The correct up-axis conversion for Marble | **UNKNOWN** — F-OPEN-1 |

---

## 8. Open items

| id | Open question | Blocking? | Probe that settles it |
|---|---|---|---|
| F-OPEN-1 | What is the correct up-axis conversion for a World Labs export? | Yes — the pipeline is wrong without it | Cook one export, read the up axis, diff bounds |
| F-OPEN-2 | Does a VEX AST template + Moneta v5 schema gate exist to use? | No | Check the Moneta v5 API surface |
| F-OPEN-3 | Is there anything to disconnect? | No | Read the graph — there is not |
| F-OPEN-4 | What produces the `.mp4`, given `usdrender_rop` has no video parm? | Yes — the deliverable | Render 2 frames, assert the file on disk |
| F-OPEN-5 | Does a group named `call` exist? | Yes — the blast may remove nothing | Cook the collider, list point groups |
| CAT-1 | The catalogue's `gltf` / `distantlight` / `usdrender` entries | No | Regenerate the catalogue against live defaults |
| PHANT-1 | The class-level `dir()` false-positive/negative class | No | Add an instance-probe rule to the phantom lint |

**No World Labs asset was available to this audit.** Every F-OPEN row is a claim the *code* fails to support — not a claim the *asset* would refute. The distinction matters: with a real export, F-OPEN-1 and F-OPEN-5 could close either way.
