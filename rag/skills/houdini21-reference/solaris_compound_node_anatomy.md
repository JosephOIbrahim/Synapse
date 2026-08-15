# Solaris Compound Node Anatomy — What Lives Inside Nested LOPs

## Triggers
nested nodes, inside node, dive inside, internal network, compound node, locked HDA internals,
component builder internals, componentgeometry inside, componentmaterial inside, componentoutput inside,
sopcreate inside, sopnet, material library inside, kmb internals, edit subnet, extras subnet,
default proxy simproxy, node internals, subchildren, allSubChildren, see inside node,
internal sop network, dive into lop

## Context
Internal structure of Solaris compound LOP nodes. A flat `children()` walk at the /stage level
sees NONE of this — these nodes are locked HDAs whose internals only appear via
`node.allSubChildren()` or explicit `hou.node("<path>")` addressing. Every internal node
reports `isInsideLockedHDA() == True`; the user-editable islands inside are the exception
and are listed per node below. Knowing these canonical paths lets an agent navigate
purposefully instead of walking blind.

**Provenance: verified live on Houdini 22.0.400 (hython probe, 2026-08-15)** except where
marked doc-derived. Node counts are for a freshly created node and can grow as users edit.

## The three user-editable islands (memorize these paths)

| Compound node | User-editable path inside | What goes there |
|---|---|---|
| `componentgeometry` | `<node>/sopnet/geo` (subnet) | The model's SOP geometry, wired to output nodes |
| `componentmaterial` | `<node>/edit` (subnet) | Optional LOP edits to the auto-assignment |
| `componentoutput` | `<node>/extras` (subnet) | Extra LOP edits under /ASSET, saved to `extras.usdc` |

Everything else inside these nodes is locked machinery — read it for understanding,
never edit it.

## componentgeometry — 87 internal nodes (fresh)

- **`<node>/sopnet/geo`** is the artist SOP subnet. It contains FOUR output nodes in H22:
  - `default` (green) — the real render geometry
  - `proxy` (yellow) — simplified viewport geometry (when wired, `default` becomes render-purpose)
  - `simproxy` (pink) — collision geometry for Edit LOP physics mode / Drop LOP / sims
  - `alternative` — NEW in H22 (not present in H19-21 docs; verified live 22.0.400)
- The surrounding `sopnet` machinery: `file_default` / `file_proxy` / `file_simproxy` (File mode),
  `externalsop_*` (object_merge for External SOP mode), `attrs_*_purpose` wrangles that stamp
  USD purpose, `autobindmaterialsubsets` (subset binding), `TO_LOPs` nulls (the actual import taps).
- LOP-side: `base_geo` / `proxy_geo` / `points` are internal `sopimport` nodes;
  `root_prim` + `geo` primitive nodes author `/ASSET/geo`; `set_simproxy_relationship`
  authors the physics:collisionEnabled relationship.
- The **Source** parm switches Internal SOP / Imported Files / External SOP / Referenced Files —
  it drives `switch_source_type` inside; the sopnet is only cooked in Internal mode.
- **Fix SOP Outputs** button recreates deleted output nodes.

## componentmaterial — 47 internal nodes (fresh)

- Auto-assignment machinery: `mtl_assign` + `mtl_assign_real3/4/5` (assignmaterial),
  `foreach_assignment_*` / `foreach_geo_scope_*` loops, `mtl_variant_begin/end` (addvariant —
  this is where material variants are authored), `pick_geo_variant` (setvariant).
- **`<node>/edit`** is the user subnet (contains only `output0` when fresh).
- Second-input (material library) plumbing: `graft_hidden_input_materials`, `reference_hidden_graft`,
  `flatten_second_input`. Geometry on input 0, material library on input 1.
- Convention for auto-matching materials by name (doc-derived, tokeru):
  vexpression `return '/ASSET/mtl/'+@primname;` on the assignment.

## componentoutput — 93 internal nodes (fresh)

- Contains a full **ropnet**: `<node>/rop` is a `usd_rop`, plus `glropnet/houdinigl` (an OpenGL
  ROP for the thumbnail) — "Save to Disk" on this LOP is driving a real ROP inside.
- Layer assembly: `fetch_geo`/`configure_geo_layer` → `geo.usdc`; `fetch_mtls`/`configure_mtl_layer`
  → `mtl.usdc`; `payload` (reference) + `configure_payload_layer` → `payload.usdc`;
  `asset_layer` → the main `<name>.usd`; `extras_layer` → `extras.usdc`.
- `class_prim` + `setup_class_prim` author `/__class__/<component>` which the root prim inherits —
  the hook for shot-level overrides.
- **`<node>/extras`** is the user subnet for post-assembly edits under /ASSET.
- Root Prim parm defaults to `/$OS` — renaming the node renames the asset.
- Output layout on disk (doc-derived): `<name>/<name>.usd` + `payload.usdc` + `geo.usdc` +
  `mtl.usdc` (+ `extras.usdc`, `thumbnail.png`, `variants/`).

## sopcreate — 10 internal nodes (fresh)

```
<node>/sopnet          [sopnet]     — contains create (the user subnet) + OUT null
<node>/sopnet/create   [subnet]     — WHERE THE USER'S SOPs LIVE
<node>/sopimport                    — internal importer reading sopnet
<node>/xform, assignmaterial, materiallibrary, loftpayloadinfo, output
```
- `sopcreate` is itself a wrapper: an internal `sopimport` pointed at its own `sopnet`,
  plus optional internal material assignment. The quick-add viewport primitives (grid etc.)
  are sopcreates with the shape inside `sopnet/create`.

## materiallibrary — empty container, VOP context

- Fresh node: **0 children**. Child category is **Vop** (1,305 types in 22.0.400, 239 of them `mtlx*`).
- **There is NO `karmamaterial*` VOP node type in 22.0.400** — the "Karma Material Builder"
  tab entry creates a configured `subnet` VOP (verified: `subnet` contains `subinput1`/`suboutput1`).
  Do not try `createNode("karmamaterialbuilder")` — it fails. Create `subnet` and build inside,
  or author flat `mtlx*` VOPs + `collect` for multi-output materials.
- Auto-fill Materials scans the library and populates per-material `matpathN`/`geopathN` parms;
  binding is authored as a material:binding relationship on the target prim.

## Other compounds probed (22.0.400)

- `instancer` — tab name resolves to type **`copytopoints`**, 0 subchildren fresh
  (its internal-SOP mode grows a sopnet when used; doc-derived).
- `karmarendersettings` — 0 subchildren; it is a parameter node, not a container.
  The "Karma" tab SETUP entry drops TWO sibling nodes (`karmarendersettings` + `usdrender_rop`)
  wired together — a network-level pattern, not a nested one.

## Agent navigation rules

1. `children()` at /stage NEVER shows compound internals. Use `allSubChildren()` or address
   the known paths above directly with `hou.node()`.
2. Check `isInsideLockedHDA()` before editing: True = machinery (read-only by convention);
   the three user islands (`sopnet/geo`, `edit`, `extras`) are the sanctioned edit points.
3. To put geometry in a Component Builder: `hou.node(".../componentgeometry1/sopnet/geo")`,
   create SOPs, wire into the `default` output node (and `proxy`/`simproxy` if wanted).
   A polyreduce feeding `proxy` + `simproxy` is the standard cheap-proxy pattern
   (Foundations Solaris Market, doc-derived).
4. Component Builder wiring: componentgeometry → componentmaterial (input 0),
   materiallibrary → componentmaterial (input 1), → componentoutput. componentoutput
   expects its upstream to be component-family nodes (tokeru, doc-derived).
5. H22 note: component/proxy/pivot prep can now also start SOP-side before Solaris
   (H22 What's New; workflow detail UNKNOWN — not yet probed live).

## Variants, layers, and consumption (Rydalch SideFX workshop, H19-era, doc-derived)

- **Layer composition of a published component**: the asset layer PAYLOADS the payload
  layer, which REFERENCES the geometry, material, and extras layers, ordered weakest
  to strongest. `.usd` extension on purpose (ASCII/binary swappable without re-referencing).
- **componentgeometryvariants** is multi-input: every input becomes a geometry variant,
  named from each componentgeometry's Advanced > geo variant name (default: node name).
  Material variants AFTER the geo-variants node apply across ALL geometry variants when
  prim paths match (5 geo x 5 mtl = 25 combos in Explore Variants LOP). componentmaterial
  nodes INSIDE the geo variants instead = nested variants (5, not 25).
- **Material variant subtlety**: the assignments are part of the variant; the materials
  themselves are NOT — every input-2 material stays available to every variant. Edits made
  inside componentmaterial's `edit` dive target are exclusive to that variant.
- Inside componentgeometry's SOP net, **all SOP Import rules apply**: `name` attribute
  names prims, primitive groups become geometry subsets.
- **Procedural variants**: for-each LOP loop, rename its context option, reference it for
  the variant name + primvars + SOP-side seeds.
- **Per-variant instancing prototypes**: no direct parm — Explore Variants LOP into an
  instancer with "only copy specified prototype primitives" OFF.
- **Scene Import as componentoutput source**: fix the Scene Import material destination
  path first — componentoutput processes ONE object at a time, so materials must share
  the geometry's parent prim.
- **USD rules stated outright**: `class` is a specifier (with `def`/`over`) and class prims
  are not traversed by default; use `Scope` not `Xform` for organizational prims — on an
  instanceable reference, transforms only take effect on the top primitive.
- Full cleaned transcript: `G:\VideoDecoder\Chris Rydalch - Creating USD Assets with
  Component Builder\`.

## Sources
- Live hython probes, Houdini 22.0.400, 2026-08-15 (anatomy, counts, paths, flags)
- SideFX docs: solaris/component_builder, nodes/lop/componentgeometry (doc-derived)
- tokeru cgwiki HoudiniLops (conventions, vexpressions)
- SideFX Houdini Foundations "Solaris Market" PDF, doc v1.0 Jan 2024, written for H20.5
  (workflow recipes; stored at rag/documentation/_raw_documentation/)
