# H22 tool candidates — signatures + preconditions only (D1.5)

**Status:** PROPOSAL · `ratified:false` · **implementation: none (D1.5)**.
This document stubs three `NEW_MCP_TOOL` candidates and two `RECIPE_CHANGE`
proposals **as signatures and preconditions only**. Nothing here is registered
in `mcp_server.py`, listed in a `mcp_tools_*.py` manifest, or added to
`python/synapse/mcp/_tool_registry.py`. No handler is written. Authoring a body
for any stub below is out of scope for this wave (D1.5, blueprint §1.3).

**Source:** `docs/intake/blueprint-h22-worldlabs-intent.md` v0.3 §1.3 (D1.5),
§1.4 (tool candidates, restated as intent + precondition), §1.1 I1.c (limits are
preconditions, not footnotes), I1.d (author as USD, never a HIP-only trick).

**Build pin:** H22.0.368 (drop), symbol table **22.0.400** (BP3-RECON live recon,
`harness/battleplan/notes/BP3_RECON.md @ 062669fe`). Every symbol, prim type, and
parm name named below is **V0** until a probe on the pinned build prints it
(blueprint §0.1). The three tool bodies are Claude Code's on the live repo, later,
gated — never written here as fact (blueprint §0.2).

**Claim-ID provenance caveat:** the `H22S-*`, `N-*`, `KAR-*`, `SOL-*` claim IDs
cited below are the dossier's (`Dossier — H22 Solaris and Karma (SYNAPSE Intake).md`,
blueprint §1.2 / §1.4). Per BP3-RECON, `dossier_in_repo = false` — the dossier is a
companion doc, **not** in this repository. The IDs are reproduced as stated in the
blueprint; their tier is STATED/DOC-STATED (blueprint §0.1), unverified in-repo.
`P-1..P-9` / `B-*` / `S-*` are probe IDs in `harness/probes/synapse_blueprint_probes.py`.

**House style:** each signature mirrors the canonical registry-tuple shape used in
`python/synapse/mcp/_tool_registry.py`
(`(name, handler_cmd, payload_fn, description, inputSchema, read_only, destructive, idempotent)`)
and the manifest shape in `mcp_tools_render.py` / `mcp_tools_usd.py`
(`TOOL_NAMES` + `DISPATCH_KEYS`). Defaults are carried in the parameter
description text, the repo convention. None of these rows is added to those files
in this wave.

---

## Precondition ledger (blueprint §1.4, restated)

The four preconditions the three tools must check, verbatim in intent from §1.4:

| # | Precondition | Applies to | Claim |
|---|---|---|---|
| PC-1 | Render **delegate is Karma** (XPU or CPU) | `synapse_author_light_blocker` | H22S-LB-03 |
| PC-2 | Product is a **Husk raster product** | `synapse_author_image_filters` | H22S-IF-06 |
| PC-3 | **`husk --pass` present** on the pinned build | `synapse_author_render_pass_chain` | KAR-04 |
| PC-4 | **One product per output file** | `synapse_author_render_pass_chain` | H22S-RP-03 |

A precondition that fails yields **refusal** (SYNAPSE declines to author) or a
**warning** (SYNAPSE authors but flags), in the collaborative "we" voice
(Synapse voice guide §2: errors are collaborative). I1.c requires these be
enforced as tool preconditions, not documented as footnotes.

---

## Candidate 1 — `synapse_author_light_blocker` (NEW_MCP_TOOL)

**Intent (§1.4):** Author a `KarmaBlockerLightFilter` prim, bind it to lights via
the `light:filters` relationship, and set the blocker's collection
includes/excludes. USD-authored (I1.d).

**Signature** (registry-tuple house style; **not** added to the registry):

```python
("synapse_author_light_blocker", "author_light_blocker", _identity,
 "Author a KarmaBlockerLightFilter prim and bind it to lights via the "
 "light:filters relationship; set the blocker's collection includes/excludes. "
 "USD-authored (I1.d), never a HIP-only trick.",
 {"type": "object", "properties": {
     "node":        {"type": "string", "description": "LOP node to wire after (optional; uses current selection if omitted)"},
     "filter_path": {"type": "string", "description": "USD prim path for the KarmaBlockerLightFilter (default: /Render/lightFilters/blocker)"},
     "light_paths": {"type": "array", "items": {"type": "string"}, "description": "USD prim paths of lights to bind via light:filters"},
     "shape":       {"type": "string", "description": "Blocker shape; must be in the probed KarmaBlockerLightFilter shape enum for the build (enum V0 until P-1; default: first probed shape)"},
     "include":     {"type": "array", "items": {"type": "string"}, "description": "Collection include paths — geometry the blocker affects"},
     "exclude":     {"type": "array", "items": {"type": "string"}, "description": "Collection exclude paths"},
 }, "required": ["light_paths"]},
 False, True, False),   # read_only=False, destructive=True, idempotent=False
```

**Params (type · required · default):**

| Param | Type | Required | Default |
|---|---|---|---|
| `node` | string | no | current selection |
| `filter_path` | string | no | `/Render/lightFilters/blocker` |
| `light_paths` | array[string] | **yes** | — |
| `shape` | string (enum, V0) | no | first probed shape |
| `include` | array[string] | no | `[]` |
| `exclude` | array[string] | no | `[]` |

**Preconditions checked:** PC-1 (render delegate is Karma, H22S-LB-03);
`shape ∈` probed `KarmaBlockerLightFilter` shape enum (enum is V0 until P-1 prints
it on the pinned build).

**Refusal / warning text SYNAPSE returns:**

- *Delegate not Karma (PC-1 fails → refusal):*
  > "A `KarmaBlockerLightFilter` only takes effect under the Karma delegate — the
  > active Hydra delegate here is `{delegate}`. I'm holding off on authoring the
  > blocker until we're on Karma (XPU or CPU); switch the delegate and I'll wire it
  > in. (H22S-LB-03)"

- *Shape not in probed enum (warning):*
  > "Heads up — `{shape}` isn't in the probed `KarmaBlockerLightFilter` shape enum
  > for build 22.0.400, so Karma may ignore it. I can author it as-is and flag it,
  > or fall back to a probed shape — your call."

**Source claims (§1.4):** N-3, H22S-LB-01..04.

**Implementation: none (D1.5).**

---

## Candidate 2 — `synapse_author_image_filters` (NEW_MCP_TOOL)

**Intent (§1.4):** Author an ordered `HoudiniImageFilterList` under `/Render` and
target it from a `RenderProduct` and/or `RenderSettings` via the
`husk:orderedImageFilters` relationship. USD-authored (I1.d).

**Signature** (registry-tuple house style; **not** added to the registry):

```python
("synapse_author_image_filters", "author_image_filters", _identity,
 "Author an ordered HoudiniImageFilterList under /Render and target it from a "
 "RenderProduct and/or RenderSettings via husk:orderedImageFilters. "
 "USD-authored (I1.d).",
 {"type": "object", "properties": {
     "node":          {"type": "string", "description": "LOP node to wire after (optional)"},
     "filters":       {"type": "array", "items": {"type": "string"}, "description": "Ordered image-filter identifiers; list order is the apply order (husk:orderedImageFilters)"},
     "target":        {"type": "string", "enum": ["render_product", "render_settings", "both"], "description": "Where husk:orderedImageFilters is authored (default: render_product; which relationship wins is OPEN — dossier §5 Q4)"},
     "product_path":  {"type": "string", "description": "USD prim path of the Husk raster RenderProduct to target"},
     "settings_path": {"type": "string", "description": "USD prim path of the RenderSettings to target (used when target includes render_settings)"},
 }, "required": ["filters"]},
 False, True, False),   # read_only=False, destructive=True, idempotent=False
```

**Params (type · required · default):**

| Param | Type | Required | Default |
|---|---|---|---|
| `node` | string | no | current selection |
| `filters` | array[string] | **yes** | — |
| `target` | string (enum: render_product / render_settings / both) | no | `render_product` |
| `product_path` | string | no | auto-discovered Husk raster product |
| `settings_path` | string | no | active RenderSettings |

**Preconditions checked:** PC-2 (product is a Husk **raster** product, H22S-IF-06).
**Open:** which relationship wins when both `RenderProduct` and `RenderSettings`
carry `husk:orderedImageFilters` is unresolved (dossier §5 Q4) — the `target`
default of `render_product` is a V0 choice, not a verdict.

**Refusal / warning text SYNAPSE returns:**

- *Product not a Husk raster product (PC-2 fails → refusal, I1.c):*
  > "Ordered image filters only run when **Husk** writes the raster product — this
  > `RenderProduct` isn't a Husk raster target, so the filter stack wouldn't fire.
  > I'm not going to author `husk:orderedImageFilters` onto a product Husk won't
  > process. Point me at a Husk raster `RenderProduct` and I'll order the filters
  > there. (H22S-IF-06)"

- *`target: both` while Q4 is open (warning):*
  > "One caveat — with the stack authored on both the `RenderProduct` and the
  > `RenderSettings`, which one Husk honours is still an open question (dossier §5
  > Q4). I'll author both and flag it so we can settle it against a render."

**Source claims (§1.4):** N-3, H22S-IF-01..08.

**Implementation: none (D1.5).**

---

## Candidate 3 — `synapse_author_render_pass_chain` (NEW_MCP_TOOL)

**Intent (§1.4):** Author a `UsdRender.Pass` chain with
`renderSource` → `RenderSettings` → `RenderProduct`, plus collections for
renderable / matte / camera-visible / pruned. USD-authored (I1.d).

**Signature** (registry-tuple house style; **not** added to the registry):

```python
("synapse_author_render_pass_chain", "author_render_pass_chain", _identity,
 "Author a UsdRender.Pass chain (renderSource -> RenderSettings -> RenderProduct) "
 "with collections for renderable / matte / camera-visible / pruned. "
 "One product per output file (H22S-RP-03). USD-authored (I1.d).",
 {"type": "object", "properties": {
     "node":          {"type": "string", "description": "LOP node to wire after (optional)"},
     "passes":        {"type": "array", "items": {"type": "object"}, "description": "Ordered pass specs: {name, render_source, settings_path, product_path, output_file}. Each pass resolves to exactly one product per output file (H22S-RP-03)"},
     "render_source": {"type": "string", "description": "renderSource prim path feeding the first pass (a RenderSettings prim or an upstream UsdRender.Pass)"},
     "collections":   {"type": "object", "description": "Per-pass collection membership: renderable / matte / camera_visible / pruned prim-path lists"},
 }, "required": ["passes"]},
 False, True, False),   # read_only=False, destructive=True, idempotent=False
```

**Params (type · required · default):**

| Param | Type | Required | Default |
|---|---|---|---|
| `node` | string | no | current selection |
| `passes` | array[object] | **yes** | — |
| `render_source` | string | no | first pass's RenderSettings |
| `collections` | object | no | `{}` (all renderable) |

**Preconditions checked:** PC-3 (`husk --pass` present, KAR-04); PC-4 (one product
per output file, H22S-RP-03).

**Refusal / warning text SYNAPSE returns:**

- *`husk --pass` not confirmed on the build (PC-3 fails → refusal):*
  > "The `UsdRender.Pass` chain is driven by `husk --pass`, and I couldn't confirm
  > `--pass` on the Husk for build 22.0.400 — a chain I author wouldn't be
  > renderable end to end. I'm holding off until `husk --pass` is verified on the
  > pinned build (P-7 / KAR-04)."

- *More than one product on one output file (PC-4 fails → refusal):*
  > "Each render pass needs to resolve to **one** product per output file, and I'm
  > seeing `{n}` products pointed at `{output_file}`. I won't author a chain that
  > collides two passes onto one file. Give each pass its own product/output path
  > and I'll build the `renderSource` → settings → product chain. (H22S-RP-03)"

**Source claims (§1.4):** KAR-04, N-7, H22S-RP-01..05.

**Implementation: none (D1.5).**

---

## Change proposals (RECIPE_CHANGE, from §1.4)

These are **not** new tools — they modify existing SYNAPSE surfaces. Restated as
change proposals with the probe each depends on. **No edit is made to either file
in this wave**; the parm/type names below are V0 until the named probe prints them.

### RC-1 — scatter recipe upgrade (`RECIPE_CHANGE`)

- **Target file (exists):** `python/synapse/routing/recipes/scene_recipes.py`
  (scatter recipe).
- **Change:** replace raw `PointInstancer` authoring with `scatterinstances`
  + masks where the source is static.
- **Precondition:** static source (H22S-SI-14).
- **Parm-name dependency — P-5:** the `scatterinstances` parameter surface (labels
  ↔ internal names) is unresolved until **P-5** writes
  `harness/notes/scatterinstances_parms_22.0.x.json` (D1.4). The recipe cannot be
  authored against guessed parm names — the internal names (e.g. the Up-Axis and
  Camera mask parms) come from P-5 output, not from the frames.
- **Source claims (§1.4):** SOL-03, H22S-SI-* .
- **Implementation: none (change proposal; blocked on P-5).**

### RC-2 — textured-material upgrade (`RECIPE_CHANGE`)

- **Target handler (exists):** `_handle_create_textured_material` in
  `python/synapse/server/handlers_material.py` (backs tool
  `houdini_create_textured_material`).
- **Change:** native path via the **Texture Material Library LOP**.
- **Precondition:** the LOP **type name** is P-2's result (H22S-TM-03).
- **Parm-name dependency — P-2:** the Texture Material Library LOP type string is
  V0 until **P-2** prints it on the pinned build. The upgrade cannot be authored
  against a guessed type name — mirrors the §0.4 rejection of guessed LOP types.
- **Source claims (§1.4):** KAR-07.
- **Implementation: none (change proposal; blocked on P-2).**

---

## Non-goals for this document (blueprint §1.5, D-3)

No implementation, no registration, no corpus write, no ratification. APEX
Animate in Hydra, Hydra hair/fur, physics layout mode, and per-instance shader
variation internals are recorded elsewhere and **not** authored (§1.5,
H22S-LIM-10). This document adds no scope to the blueprint (rule D-3).
