---
leg: BP3-CORPUS
wave: BP3
build: 22.0.400
source_blueprint: docs/intake/blueprint-h22-worldlabs-intent.md (v0.3)
probe_evidence: harness/notes/h22wl/bp3_probes/stdout.txt  (BP3-PROBE, branch bp3/probe, product d6c6d9b3)
fulfils: blueprint D1.2 (dossier §9 merge worksheet)
---

# BP3 — H22 Solaris merge worksheet (D1.2)

One row per blueprint V0 claim **touched by P-1..P-9** (Intent 1): the §1.2
inventory, the §1.4 tool candidates, the Image Filter / Texture Material Library /
Render Pass type names, the P-9 scatter menus, the P-4 equiangular toggle, the
P-8 `mtlxflake3d`. Intent-2 fixture claims (B-1..B-9, the §2.3 WL-\* ledger) live
in the promotion proposal + open-questions doc, not here.

## Fallback & keying (mandatory header note)

- **`dossier_in_repo: false`** (BP3-RECON, T4). The dossier §9 merge worksheet is
  not in the repo, so these rows are **built from the blueprint's own claim-ID
  pointers** — §1.2 inventory table, §1.4 candidate table, §2.3 ledger, §7 register —
  exactly as the mission note directs when RECON reports the dossier absent.
- Rows are keyed by **runtime symbol**, not dossier ID (RECON **F-1**: the
  blueprint's `N-x` / `H22S-*` IDs are dossier-numbered and are **not resolvable
  in-repo**; the "pointer" column carries them as a *reference*, not a key).
- Build pinned **H22 22.0.400** (`stdout.txt:5`). Every anchor is `stdout.txt:<line>`.

## Status legend

- `named(<type|parm>)` — the runtime surfaced this exact symbol on 22.0.400.
- `UNKNOWN-AFTER-PROBE` — the probe ran but the surface was not found (skip ≠ pass).
- `BLOCKED(<probe id>)` — the probe raised; recorded with its traceback line.

---

| # | blueprint V0 claim (symbol) | blueprint pointer | status | anchor |
|---|---|---|---|---|
| 1 | USD version | §1.2 (USD 0.26.5, drop.json) | `named(USD 0.26.5)` | stdout.txt:6 |
| 2 | MaterialX version | §1.2 (N-6) | `named(MaterialX 1.39.5)` | stdout.txt:7 |
| 3 | `paintinstances` LOP | §1.2 (N-5 rename/alias) | `named(paintinstances)` | stdout.txt:12 |
| 4 | `scatterinstances` LOP | §1.2 (N-5/SOL-03); §1.4 scatter recipe | `named(scatterinstances)` | stdout.txt:13 |
| 5 | `pointinstancer` LOP | §1.4 (raw PointInstancer, replaced by scatter) | `named(pointinstancer)` | stdout.txt:14 |
| 6 | `copytopoints` LOP | P-1 cited surface | `named(copytopoints)` | stdout.txt:15 |
| 7 | `edit` LOP (edit-state layer) | §1.2 (`edit` in probe_confirmed_types); I1.b | `named(edit)` | stdout.txt:16 |
| 8 | `karmablockerlightfilter` LOP | §1.2 (N-3); §1.4 `synapse_author_light_blocker` | `named(karmablockerlightfilter)` | stdout.txt:17 |
| 9 | `karmarendersettings` LOP | P-1 cited (Karma settings) | `named(karmarendersettings)` | stdout.txt:18 |
| 10 | `usdrender_rop` LOP | P-1 cited; B-7 render path | `named(usdrender_rop)` | stdout.txt:19 |
| 11 | `renderpass` LOP — **Render Pass** type name | §1.4 `synapse_author_render_pass_chain` | `named(renderpass)` | stdout.txt:20 |
| 12 | `imagefilter` LOP — **Image Filter** type name | §1.4 `synapse_author_image_filters` | `named(imagefilter)` | stdout.txt:21 |
| 13 | `texturemateriallibrary` LOP — **Texture Material Library** type name | §1.4 textured-material upgrade (ptr H22S-TM-03) | `named(texturemateriallibrary)` | stdout.txt:22 |
| 14 | `apexanimate` LOP | §1.5 out-of-lane (record, do not author) | `named(apexanimate)` | stdout.txt:23 |
| 15 | `cache` LOP | P-1 cited surface | `named(cache)` | stdout.txt:24 |
| 16 | `karmafogbox` LOP | P-1 cited surface | `named(karmafogbox)` | stdout.txt:25 |
| 17 | `materiallibrary` LOP | §1.2 (`materiallibrary` in probe_confirmed_types) | `named(materiallibrary)` | stdout.txt:26 |
| 18 | `light::2.0` LOP | §1.4/KAR-12 (equiangular target) | `named(light::2.0)` | stdout.txt:27 |
| 19 | **Image Filter** label ↔ name | T1 explicit (type name) | `named(imagefilter \| Image Filter)` | stdout.txt:33 |
| 20 | **Texture Material Library** label ↔ name | T1 explicit (type name) | `named(texturemateriallibrary \| Texture Material Library)` | stdout.txt:37 |
| 21 | **Render Pass** label ↔ name | T1 explicit (type name) | `named(renderpass \| Render Pass)` | stdout.txt:35 |
| 22 | Karma Blocker Light Filter label ↔ name | §1.4 blocker candidate | `named(karmablockerlightfilter \| Karma Blocker Light Filter)` | stdout.txt:34 |
| 23 | Scatter Instances label ↔ name | §1.4 scatter recipe | `named(scatterinstances \| Scatter Instances)` | stdout.txt:36 |
| 24 | COP Image Filter List label ↔ name | P-6 blocker cause (sorts before `imagefilter`) | `named(copnet_filterlist \| COP Image Filter List)` | stdout.txt:32 |
| 25 | `usdcreatecomponent` SOP — **USD Create Component** | §2.4 (SOP-side component) | `named(usdcreatecomponent \| USD Create Component)` | stdout.txt:42 |
| 26 | `usdcreateproxygeometry` SOP — **USD Create Proxy Geometry** | §2.4 (proxy input) | `named(usdcreateproxygeometry \| USD Create Proxy Geometry)` | stdout.txt:43 |
| 27 | equiangular MIS / volume-sampling toggle on `light::2.0` | T1 explicit (equiangular toggle, P-4); KAR-12 | `UNKNOWN-AFTER-PROBE` (P-4 ran, no equiangular/volume-sampling label found) | stdout.txt:46-48 |
| 28 | `scatterinstances` parm surface (labels ↔ names) | §1.2 ("167 parms"); §1.4 ("parm names from P-5") | `named(138 rows → harness/notes/scatterinstances_parms_22.0.400.json)` | stdout.txt:52 |
| 29 | `imagefilter` prim type + `husk:orderedImageFilters` targets | §1.2 (N-3 orderedImageFilters); §1.4 image-filters (§5 Q4 open) | `BLOCKED(P-6)` — `AttributeError('OpNode' … no attribute 'stage')`; label-search picked `copnet_filterlist` first | stdout.txt:230 |
| 30 | `UsdRender.Pass` define + `renderSource` rel | §1.2 (KAR-04/N-7); §1.4 render-pass chain | `named(Pass defined:True \| renderSource rel:True)` | stdout.txt:235 |
| 31 | `husk --pass` CLI present | §1.2/KAR-04 | `named(husk --pass — confirmed)` (+ `husk_pass_check.txt`) | stdout.txt:236 |
| 32 | `mtlxflake3d` VOP | T1 explicit (mtlxflake3d, P-8) | `named(mtlxflake3d)` | stdout.txt:241 |
| 33 | `scatterinstances.executionmode` menu | T1 explicit (scatter menus, P-9); §5 Q2 | `named(executionmode: Deferred\|Immediate)` | stdout.txt:246 |
| 34 | `scatterinstances.scattertargetmotion` menu (Animation Beta) | T1 explicit (scatter menus, P-9) | `named(scattertargetmotion: Static\|Rigid Transforms\|Deforming Transforms)` | stdout.txt:247 |

---

## Notes carried to the promotion proposal / ruling

- **Row 28 — 167 vs 138.** §1.2 calls `scatterinstances` a "167-parm" class; the P-5
  label-walk surfaces **138** `name | label` rows (`stdout.txt:52-218`). Both are
  correct: 167 = full parmTemplate count (incl. multiparm templates / hidden), 138 =
  the stdout rows the seed JSON mirrors. Neither is a phantom. (Seed provenance block
  records the same.)
- **Row 27 — P-4 empty.** No equiangular / volume-sampling parm was surfaced on
  `light::2.0` by the P-4 walk. Recorded UNKNOWN-AFTER-PROBE, not absent — a
  different walk (or the GUI parm pane) may still find it.
- **Row 29 — P-6 defect.** The block is a *probe* defect (the LOP-category label
  search for `('image filter',)` matches "COP Image Filter List" / `copnet_filterlist`
  first, whose node has no `.stage()`), recorded not patched (BP3-PROBE §11.1). The
  `husk:orderedImageFilters` relationship question (§5 Q4) is therefore still open.
- Promotion of any `named(...)` row to VERIFIED-RUNTIME is the promotion proposal's
  job (`docs/reviews/bp3-h22-promotion-proposal.md`, `ratified:false`) and is D-1's to ratify.
