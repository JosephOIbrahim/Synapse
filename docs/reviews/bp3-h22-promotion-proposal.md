---
ratified: false
leg: BP3-CORPUS
wave: BP3
build: 22.0.400
source_blueprint: docs/intake/blueprint-h22-worldlabs-intent.md (v0.3)
probe_evidence: harness/notes/h22wl/bp3_probes/stdout.txt  (BP3-PROBE, branch bp3/probe, product d6c6d9b3)
checker: harness/battleplan/notes/bp3_promotion_check.py
---

# BP3 — H22 Solaris + World Labs promotion proposal (`ratified: false`)

**This proposal proposes tier moves. It ratifies nothing.** Flipping a tier in
any live corpus file is a human + CTO act (blueprint §6 "No ratification / No
corpus writes"; wave rule D-1). The only new corpus artifact this leg writes is
the scatter-instances parm seed (`harness/notes/scatterinstances_parms_22.0.400.json`).

## Provenance & keying

- **`dossier_in_repo: false`** (BP3-RECON, T4). The dossier
  (`Dossier - H22 Solaris and Karma (SYNAPSE Intake).md`) is **not in the repo**,
  so rows are keyed by **runtime symbol** (node type / parm name), not by dossier
  claim ID. RECON **F-1**: the blueprint's `N-x` / `H22S-*` IDs are dossier-numbered
  and are **not resolvable in-repo**; where cited below they are a *pointer*, not a
  dereferenceable key. Reconcile by symbol.
- Build pinned **H22 22.0.400** / USD 0.26.5 / MaterialX 1.39.5 (`stdout.txt:5-7`).
- Every anchor below is `stdout.txt:<line>` into the BP3-PROBE probe output.

## Promotion channels (this leg's rule)

1. **→ VERIFIED-RUNTIME** — only where a **stdout line proves it** on 22.0.400
   (node-type / parm / menu *existence*; behaviour is out of scope).
2. **§2.3 WL-\* rows → FIXTURE-VERIFIED** — only where **B-1..B-4 confirm on the
   fixture**. B-5..B-9 are runtime evidence but are **outside** the B-1..B-4
   window and do **not** move a WL-\* tier here.
3. **Every other row stays put.** Recorded in Table B, promoted by nobody here.

## Verification

```
python harness/battleplan/notes/bp3_promotion_check.py
```
Exit 0 ⇔ every VERIFIED-RUNTIME / FIXTURE-VERIFIED row below has an anchor that
resolves to a real, non-blank, non-BLOCKED line in `stdout.txt`. Exit code is
pasted in the leg receipt (`harness/notes/receipts/BP3-CORPUS.json`).

---

## Table A — Proposed promotions (checker-validated)

<!-- PROMOTION-TABLE-A -->

| claim id (symbol) | current tier | proposed tier | anchor | note |
|---|---|---|---|---|
| `imagefilter` — Image Filter LOP type | DOC-STATED (dossier §3 IF; not in-repo) | VERIFIED-RUNTIME | stdout.txt:21 | P-1 True; label `Image Filter` at P-2 stdout.txt:33. **Type existence only** — the `husk:orderedImageFilters` relationship (which of RenderProduct/RenderSettings wins, §5 Q4) is still OPEN (P-6 BLOCKED). |
| `texturemateriallibrary` — Texture Material Library LOP (ptr H22S-TM-03) | DOC-STATED / V0 (P-2-gated) | VERIFIED-RUNTIME | stdout.txt:22 | P-1 True; label `Texture Material Library` P-2 stdout.txt:37. Unblocks the §1.4 `_handle_create_textured_material` precondition (type name from P-2). |
| `usdcreatecomponent` — USD Create Component SOP | V0 (§2.4) | VERIFIED-RUNTIME | stdout.txt:42 | P-3; Pieke SOP-side component path. |
| `usdcreateproxygeometry` — USD Create Proxy Geometry SOP | V0 (§2.4) | VERIFIED-RUNTIME | stdout.txt:43 | P-3. Second-input index defect (B-6 stdout.txt:322 "proxy SOP second input failed") is a *probe/recipe* defect, not a type defect — see for_ruling. |
| `mtlxflake3d` — flake VOP (MaterialX 1.39.5) | DOC-STATED (P-8-gated) | VERIFIED-RUNTIME | stdout.txt:241 | P-8 True. |
| `scatterinstances.executionmode` menu {Deferred, Immediate} | V0 (dossier §5 Q2 open) | VERIFIED-RUNTIME | stdout.txt:246 | P-9; answers dossier §5 Q2 (execution mode enum). |
| `scatterinstances.scattertargetmotion` menu {Static, Rigid Transforms, Deforming Transforms} | V0 (Animation Beta) | VERIFIED-RUNTIME | stdout.txt:247 | P-9. |
| `WL-EX-02` — splat export **PLY 500k** schema + count | DOC-STATED | FIXTURE-VERIFIED | stdout.txt:252 | B-1: 500000 points, PLY DC-only schema (`f_dc_0..2`, `scale_0..2`, `rot_0..3`, `opacity`; **no `f_rest_*`**). **Scope = the 500k.ply fixture only**; SPZ and the ~2M tier are untested. |

<!-- /PROMOTION-TABLE-A -->

## Build re-pin (already VERIFIED-RUNTIME on a prior build; re-anchored to 22.0.400 — *no tier change*)

Per §1.2 these are **not to be re-derived**; P-1..P-9 re-check existence only, to
pin the build. Listed as evidence, **not** as promotions (no 22.0.400 knowledge
file exists yet — RECON):

- `scatterinstances` type (N-5/SOL-03) — stdout.txt:13; full parm surface P-5 (seed written).
- `karmablockerlightfilter` + `Karma Blocker Light Filter` (N-3) — stdout.txt:17 / label stdout.txt:34.
- `renderpass` / `UsdRender.Pass` define + `renderSource` rel (KAR-04/N-7) — stdout.txt:20 / :235; `husk --pass` present (`husk_pass_check.txt`).
- `paintinstances`, `edit`, `materiallibrary`, `karmarendersettings`, `usdrender_rop`, `pointinstancer`, `copytopoints`, `apexanimate`, `cache`, `karmafogbox`, `light::2.0` — all True, stdout.txt:12-27.
- USD 0.26.5 / MaterialX 1.39.5 (N-6) — stdout.txt:6-7.

---

## Table B — Stays put (evidence recorded, **not** promoted here)

Proposed-tier column is deliberately **not** a promotable tier — the checker
skips these, and any attempt to flip one to VERIFIED-RUNTIME / FIXTURE-VERIFIED
either points at a non-stdout artifact (→ FAIL) or a BLOCKED line (→ FAIL).

<!-- STAYS-PUT-TABLE-B -->

| claim id (symbol) | current tier | proposed tier | anchor | reason it stays |
|---|---|---|---|---|
| `WL-EX-03` — collider mesh GLB, 100–200k tris | DOC-STATED | REFUTED-ON-FIXTURE | review §5 D2.2 / supplementary.txt v2 L90-92 | Real count **46,993 tris** (< 100k) on the lane fixture — **below** the doc window. Not a stdout figure (B-3 stdout only shows 2 packed prims, stdout.txt:283). The "100–200k" claim does not hold for this fixture; do **not** promote. |
| `WL-EX-05` — frame OpenCV (+y down, +z fwd) | DOC-STATED + open | UNKNOWN (gui) | stdout.txt:277 | B-2 numeric bounds are consistent with +y-down, but **handedness is "not decidable numerically"** — needs viewer A/B against the Marble world. Mirror unknown. (Open Q4.) |
| `BLU-04` — app exports carry no scale/ground metadata | UNKNOWN | UNKNOWN | stdout.txt:300 | B-4 **resolved it TRUE** (no PLY-header / GLB-extras metadata). It is **not** a §2.3 WL-\* row, so this leg's rule holds it put; promotion to FIXTURE-VERIFIED is human/CTO's — flagged in Open Q3 + for_ruling. |
| `BLU-01` — one `kind=component`; splat=render / collider=proxy; payload | PROPOSAL | PROPOSAL | stdout.txt:326 | B-6 built the structure (stage stdout.txt:326-335; usdc 19.8 MB stdout.txt:336) **but** B-7 render FAILED (RGB flat-zero, 6 no-camera errors). Structure ✓, render ✗ → not verified. R-1 TRIGGERED. |
| `WL-HOU-02` / `WL-HOU-03` — native splat nodes (`bakegsplat`, `labs::relight_gsplats::1.0/1.1`, `rasterizegsplats`) | DOC-STATED | DOC-STATED | stdout.txt:305 | B-5 confirms these node types **exist** on 22.0.400 (stdout.txt:305-316), clearing R-4. But B-5 is **outside** the B-1..B-4 promotion window, so it stays here. for_ruling: a human may promote node-existence to VERIFIED-RUNTIME. |

<!-- /STAYS-PUT-TABLE-B -->

---

## Open questions (D1.6) — blueprint §8 items 1–5

Verdicts + anchors mirror the BP3-PROBE review doc (`docs/reviews/bp3-h22-worldlabs-probes-2026-09-03.md` §10). `answered(anchor)` | `unanswered(blocked by <probe/gui>)`.

| # | Question (probe) | Status | Anchor |
|---|---|---|---|
| 1 | Does `scatterinstances` accept a `purpose=proxy` source prim? (B-9) | **unanswered (blocked by gui — Karma/Hydra viewport)** — recipe prim built (`/wl_scatter` GenerativeProcedural + PointInstancer, stdout.txt:388-391) but source was **not** set to the proxy prim (`coll=None`, stdout.txt:376); instance expansion + purpose acceptance is Hydra-time. | stdout.txt:374-392 |
| 2 | Karma XPU splat layout after SOP Import — does Bake GSplat output survive to LOPs, or is the Labs LOP path the only route? (B-7) | **unanswered (blocked by B-7 render defect + native path unexercised)** — 500k splat loaded into Karma XPU but rendered 0 RGB on the plain SOP-Import → `usdrender_rop` path; native tools exist (B-5) but were not run. | stdout.txt:339-362; B-5 stdout.txt:303-316 |
| 3 | Do Marble app exports carry `metric_scale_factor` / `ground_plane_offset`? (B-4) | **answered: NO** — neither PLY header nor GLB extras carry them → BLU-04 = TRUE. | stdout.txt:300 (block 291-300) |
| 4 | Handedness after the Y/Z flip — is the lane mirrored? (B-2) | **unanswered (blocked by gui — viewer A/B)** — not decidable numerically. | stdout.txt:277 |
| 5 | Chisel template GLB — expected units / frame for uploads? (B-8, manual) | **unanswered (blocked by Marble app + manual checklist)** — B-8 is a printed manual checklist, not a headless probe. | stdout.txt:365-371 |

## Open questions (D1.6) — dossier §5 tensions

**RECON listed no dossier §5 tensions** — the dossier is not in the repo
(`dossier_in_repo: false`; RECON T4), so the full §5 Q1–Q10 tension set is
**not reachable in-repo**. Only the two §5 tensions the *blueprint itself* surfaces
(via its probe pointers) are addressable this session; the rest await the human
dropping the dossier + coffee notes (RECON: "Joe drops the dossier … on his word").

| dossier §5 tension (blueprint pointer) | Status | Anchor |
|---|---|---|
| §5 Q2 — scatter execution / animation menus | **answered** — `executionmode` {Deferred, Immediate}; `scattertargetmotion` {Static, Rigid Transforms, Deforming Transforms} (P-9). | stdout.txt:246-247 |
| §5 Q4 — image filters: which relationship wins, RenderProduct vs RenderSettings (`husk:orderedImageFilters`) | **unanswered (blocked by P-6 BLOCKED)** — P-6 raised `AttributeError('OpNode' … no attribute 'stage')` before it could traverse; the stage-traversal that would answer it never ran. | stdout.txt:230 |
| §5 Q1, Q3, Q5–Q10 | **unanswered (blocked by dossier absent)** — not in-repo; re-open when the dossier is dropped. | — (no in-repo pointer) |
