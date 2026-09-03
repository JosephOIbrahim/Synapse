# BP3-RECON — V0-path reconciliation, hython + pref-dir pin, prior-artifact index

**Leg:** BP3-RECON (band TRUTH, tier reasoning) · branch `bp3/recon` · worktree `.claude/worktrees/bp3-recon`
**Build pinned:** **22.0.400** — `hou.applicationVersionString()` printed live from
`C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe` (T2 probe, 2026-09-03).
**Source under reconciliation:** `docs/intake/blueprint-h22-worldlabs-intent.md` v0.3 (§1.2, §1.3, §2.8, §3.2, §3.7, §6 step 2).
**Rule honoured:** no directory or file was created to make the blueprint true — a *no match* row **is** the finding (blueprint §6 step 2). Evidence column is `git ls-files` (authoritative for a fresh checkout: a fresh checkout contains exactly the tracked set).

> **Anchor discipline:** every row below is backed by a `git ls-files` line or a live probe. No anchor, no claim.

---

## T1 — V0 path reconciliation

### A. Existing surfaces the blueprint names (dirs + files that should already be in the repo)

| V0 path (blueprint) | actual path | evidence (`git ls-files` / probe) |
|---|---|---|
| intake docs dir (`docs/intake/`) | `docs/intake/` | `git ls-files docs/intake` → **6** files (blueprint, `world_manifest.schema.json`, 4× `adjudication-*.md`) |
| reviews dir (`docs/reviews/`) | `docs/reviews/` | `git ls-files docs/reviews` → **38** files |
| probe scripts dir | `harness/probes/` | `git ls-files harness/probes` → **18** files; incl. landed sidecar `harness/probes/synapse_blueprint_probes.py` |
| `harness/probes/synapse_blueprint_probes.py` (sidecar) | `harness/probes/synapse_blueprint_probes.py` | `git ls-files` → present (landed 2026-09-03) |
| `authoring_domains.json` (§3.2, §6) | `python/synapse/server/authoring_domains.json` | `git ls-files` → 1 match (blueprint names it bare; lives under `server/`) |
| `verified_lop_solaris_knowledge_*.json` (§6) | `harness/notes/verified_lop_solaris_knowledge_21.0.671.json` **and** `…_22.0.368.json` | `git ls-files` → 2 matches. **No `…_22.0.400.json` variant exists** (glob matches only 21.0.671 + 22.0.368) |
| `h22_doc_candidates.json` (§6) | `harness/notes/h22_doc_candidates.json` | `git ls-files` → 1 match |
| `scene_recipes.py` (§1.4 RECIPE_CHANGE, §6) | `python/synapse/routing/recipes/scene_recipes.py` | `git ls-files` → 1 match |
| `handlers_material.py` (§6; §1.4 `_handle_create_textured_material`) | `python/synapse/server/handlers_material.py` | `git ls-files` → 1 match |
| `world_manifest.schema.json` (sidecar) | `docs/intake/world_manifest.schema.json` | `git ls-files` → 1 match — **landed at `docs/intake/`, NOT the `schemas/` home the contract cites (see mismatch M-1)** |
| panel dir `python/synapse/panel/` (T1) | `python/synapse/panel/` | `git ls-files` → **98** files |
| `designsystem/manifests/qss` (T1) | **partial** → `python/synapse/panel/designsystem/` (dir, 14 files). **No `manifests/` subdir and no `.qss` files anywhere.** `qss` is the module `python/synapse/panel/designsystem/qss.py` | `git ls-files python/synapse/panel/designsystem` (14 files, incl. `qss.py`, `tokens.py`, `theme_source.py`); repo-wide `*.qss` → **0** |
| hython launcher SYNAPSE uses (§6) | `.synapse/hytest.py` (resolver shim) → an installed `hython.exe` | `git ls-files .synapse/hytest.py`; resolution detail in **T2** |
| D-track spatial/bbox helper (§6, §3.4) | **no dedicated helper** — nearest existing substrate: `python/synapse/server/introspection.py` (`geo.boundingBox()` @ L141, **hou-based**) + `python/synapse/panel/explain_mode.py` (`geo.boundingBox()` @ L96) | `grep`; the three §3.4 `synapse_spatial_describe/classify/frustum` tools are **UNBUILT** (0 matches in `python/synapse`) |

### B. Prospective output artifacts (dated `<date>` / templated `<slug>` — the *file* is a future Mile-1/2/3 output; reconcile the **home dir**)

| V0 output path (done-condition) | home dir status | file status |
|---|---|---|
| `docs/reviews/h22-pieke-probes-<date>.md` (D1.1) | `docs/reviews/` **exists** | no match (future output) |
| `docs/reviews/h22-pieke-promotion-<date>.md` (D1.3) | `docs/reviews/` **exists** | no match |
| `harness/notes/scatterinstances_parms_22.0.x.json` (D1.4) | `harness/notes/` **exists** (722 files) | no match (P-5 output, not yet produced) |
| `docs/intake/h22-tool-candidates-<date>.md` (D1.5) | `docs/intake/` **exists** | no match |
| `docs/reviews/wl-bridge-probes-<date>.md` (D2.1) | `docs/reviews/` **exists** | no match |
| `harness/scenes/wl_fixture_lane.hip` (D2.4) | `harness/scenes/` → **no match** (0 tracked) | no match |
| `harness/fixtures/worldlabs/<slug>/world_manifest.json` (D2.6) | `harness/fixtures/` + `…/worldlabs/` → **no match** (0 tracked) | no match |
| `docs/reviews/spatial-lane-probes-<date>.md` (D3.3) | `docs/reviews/` **exists** | no match |
| `schemas/` schema home (§3.2 `contract`, D3.2) | **no match** (0 tracked) — schema actually at `docs/intake/` | see M-1 |
| `harness/scenes/demo_wl_lane.hip` (§4.3, demo) | `harness/scenes/` → **no match** | no match |
| `frames/hires_t_MMSS.jpg` (companions, §1.2) | `frames/` → **no match** (0 tracked; parameter panes not in repo) | no match |

**Do-not-mkdir note:** `harness/fixtures/worldlabs/`, `harness/scenes/`, `schemas/`, `frames/` are all **absent by design** at this stage. The download/build/demo legs create them at the moment of use. BP3-RECON creates none of them (constitution + §6 step 2).

---

## T2 — hython, hytest shim, and the pref dir

**Canonical build (pin this in every probe output):** **22.0.400**
`"C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" -c "import hou; print(hou.applicationVersionString())"` → `22.0.400` (live, 2026-09-03).
Matches the GUI/live SYNAPSE server, the `22.0.400` symbol table (`python/synapse/cognitive/tools/data/h22_symbol_table.json`), and the node-catalog scripts.

**Installed builds with `hython.exe`** (`ls "…/Houdini */bin/hython.exe"`): **21.0.773, 22.0.400, 22.0.413, 22.0.417, 22.0.429**. (Dirs `Houdini 22.0.368` and `Houdini 22.0.397` exist but carry **no** `hython.exe`.)

**hytest shim discipline** (`.synapse/hytest.py`, skip ≠ pass): resolves hython **first-usable-wins** —
1. `$SYNAPSE_HYTHON` (explicit pin, recommended, skips the scan)
2. `hython` on `PATH`
3. **newest** installed Houdini whose python imports `pytest` + `PySide6`.

⚠ **Pinning hazard (M-2).** In this lane `SYNAPSE_HYTHON` is **unset** and there is **no `hython` on PATH** — so the shim falls to rule 3 and would pick the **newest** install (**22.0.429**), which has **no 22.0.429 symbol table**. **Peers must pin `SYNAPSE_HYTHON` to the 22.0.400 hython** so probe output matches the recon'd symbol table. (Skip ≠ pass: a shim that resolves a build without `pytest`+`PySide6` SKIPs, which the harness reads green — hence the pin.)

**Pref dir (verified):** `C:/Users/User/OneDrive/Documents/houdini22.0` → **EXISTS** (OneDrive known-folder redirect confirmed). The pre-redirect `C:/Users/User/Documents/houdini22.0` → **ABSENT**. hython launched from an agent lane has looked at the pre-redirect path before, so **set `HOUDINI_USER_PREF_DIR` explicitly** to the OneDrive path (done for the T2 probe above).

**D-DEP-03 hint (which the reconciliation section owes, per §11):** the *existing* SYNAPSE bounds code is **`hou`-based** (`hou.Geometry.boundingBox()` in `introspection.py` + `explain_mode.py`), **not** `pxr` `UsdGeom.BBoxCache`. So D-DEP-03 leans option **(a) match existing = `hou`** — recorded, not decided (D-1 is a human word).

**Bus finding posted** (T2/T4, addressed `*`, 2026-09-03T14:38:28, `n=18d1e389e49cfc98`): `hython`, `build`, `pref_dir`, `fixtures_dir`, `reviews_dir`, `notes_dir`, `schema_home`, `spatial_helpers`, `dossier_in_repo` — anchor = this file.

---

## T3 — prior H22 Solaris probe artifacts (re-check existence only; never re-derive — §1.2)

> **ID-numbering caveat (finding F-1):** the blueprint's `N-3/N-5/N-6/N-7` are **dossier** claim/probe IDs, and the **dossier is not in the repo** (T4). The repo *also* has `N-3..N-7` — but those are a **distinct** numbering from `docs/reviews/h22-cto-roadmap-2026-07-16.md` (a July wave-2 probe-candidate list), **not** the same probes. So the "not-to-be-re-derived" evidence resolves by **symbol**, not by blueprint ID. Both are indexed below.

### By symbol (what §1.2 says is already VERIFIED-RUNTIME → where it actually lives)

| Symbol / claim (§1.2) | blueprint ID | repo artifact(s) | line evidence |
|---|---|---|---|
| `paintinstances` rename + alias | N-5 | `harness/notes/verified_lop_solaris_knowledge_22.0.368.json` | `paintinstances` @ ~L238 (×5) |
| `scatterinstances` type + `instancer`→`pointinstancer` rename | N-5, SOL-03 | `harness/notes/h22_probe_results.json` (SOL-03) · also `harness/notes/h22_doc_candidates.json` | `SOL-03` @ L51; `instancer`/`scatterinstances`/`pointinstancer` @ L55–64 |
| `scatterinstances` **167-parm surface** (P-5 target) | N-5, SOL-03 | **not yet in repo** — future D1.4 output `harness/notes/scatterinstances_parms_22.0.x.json` | no match (P-5 has not run) |
| `karmablockerlightfilter` + `KarmaBlockerLightFilter` + `light:filters` | N-3 | `docs/reviews/h22-doc-intel-2026-07-16-wave2.md` (KAR-07, **DOC-CLAIM tier**) + census `harness/notes/h22/{h22_node_corpus_400.i1.json, w5_delta_368_baseline.json, w5_delta_census.json, _w5_runtime_400.json}` | `KarmaBlockerLightFilter` @ L108,110 |
| `husk:orderedImageFilters` (RenderSettings + RenderProduct) / `HoudiniImageFilterList` | N-3 | `docs/reviews/h22-doc-intel-2026-07-16-wave2.md` + `harness/notes/h22/` census files | `HoudiniImageFilterList` @ L108 |
| `UsdRender.Pass` symbols + `husk --pass` | KAR-04, N-7 | `docs/reviews/h22-doc-intel-2026-07-16-wave2.md` (KAR-04, 4 schema symbols table-VERIFIED) · `docs/reviews/h22-cto-roadmap-2026-07-16.md` C-9 | `UsdRender.Pass`/`husk --pass` @ L34, L103–105 |
| MaterialX 1.39.5 | N-6 | `docs/reviews/h22-doc-intel-2026-07-16-wave2.md` (KAR-06 → `handlers_material.py:465-598`) | KAR-06 rows |
| USD 0.26.5 | `drop.json` | `harness/state/drop.json` | (per §1.2; `drop.json` is a human word — not read/modified here) |

### By blueprint ID (per acceptance predicate 3 — repo path, or 'not found')

| ID | resolves to (repo path) — *July-roadmap numbering, see F-1* |
|---|---|
| **N-3** | `docs/reviews/h22-cto-roadmap-2026-07-16.md:103` (roadmap "KAR-08 identification probe"; also `h22-now-probes-2026-07-16.md`, `h22-per-context-postmortem-2026-07-17.md`) — **≠ blueprint's N-3** (blocker/imagefilter). Blocker/imagefilter symbols themselves: see symbol table above. |
| **N-5** | `docs/reviews/h22-cto-roadmap-2026-07-16.md:105` (roadmap "Solaris layout-successor catalog probe") — **≠ blueprint's N-5** (paint/scatter). Paint/scatter symbols: `verified_lop_solaris_knowledge_22.0.368.json` + `h22_probe_results.json`. |
| **N-6** | `docs/reviews/h22-cto-roadmap-2026-07-16.md:106` (roadmap "KAR-06 MaterialX probe") — aligns with blueprint N-6 (MaterialX). |
| **N-7** | `docs/reviews/h22-cto-roadmap-2026-07-16.md:107` (roadmap "KAR-01 husk frame-range probe") — aligns with blueprint N-7 (husk). |
| **KAR-04** | `harness/notes/h22_doc_candidates_wave2.json` · `docs/reviews/h22-doc-intel-2026-07-16-wave2.md:34` · `docs/reviews/h22-cto-roadmap-2026-07-16.md:154` (C-9) |
| **KAR-07** | `harness/notes/h22_doc_candidates_wave2.json` · `docs/reviews/h22-doc-intel-2026-07-16-wave2.md:108,281` |
| **KAR-12** | `harness/notes/h22_doc_candidates_wave2.json` · `docs/reviews/h22-doc-intel-2026-07-16-wave2.md:171` |
| **SOL-03** | `harness/notes/h22_probe_results.json:51` · `harness/notes/h22_doc_candidates.json` · `docs/reviews/h22-cto-roadmap-2026-07-16.md:78` |
| `verified_lop_solaris_knowledge_22.0.368.json` | `harness/notes/verified_lop_solaris_knowledge_22.0.368.json` — **present** |

**h22-notes surfaces naming the 4 target symbols** (`scatterinstances`/`blocker`/`orderedImageFilters`/`UsdRender.Pass`) under `harness/notes/h22/`: `h22_node_corpus_400.i1.json`, `HARDENING_BACKLOG.md`, `w5_delta_368_baseline.json`, `w5_delta_census.json`, `_w5_runtime_400.json`.

**Consequence for CORPUS/PROBE:** existence of every §1.2 symbol is already pinned in-repo (above) — **P-1 re-checks existence only (free, pins the build); nothing above is re-derived.** The one genuine gap is the **167-parm scatterinstances surface** (D1.4), which is a Mile-1 output, not a prior artifact.

---

## T4 — dossier + coffee notes in repo?

**`dossier_in_repo`: false.** `docs/intake/` holds exactly: `blueprint-h22-worldlabs-intent.md`, `world_manifest.schema.json`, `adjudication-h22-release-notes.md`, `adjudication-resource-aware-cache.md`, `adjudication-sidefx-h22-memo.md`, `adjudication-syn-next-001.md`. A repo-wide `git ls-files | grep -i 'dossier|coffee'` → **0 matches**.

- `Dossier - H22 Solaris and Karma (SYNAPSE Intake).md` → **not in repo**
- `Coffee Shop Notes - Solaris and Karma in Houdini 22.md` → **not in repo**

**CORPUS falls back to the blueprint's own pointers** (§1.2 inventory table, §2.3 ledger, §7 register). Joe drops the dossier + coffee files on his word (per mission T4).

---

## Mismatches / findings surfaced (for the review doc + ruling)

- **M-1 — schema home moved.** Blueprint §3.2 `contract: "schemas/world_manifest.schema.json"` and D3.2 "(V0 path `schemas/`)" cite a `schemas/` dir that **does not exist** (0 tracked). The schema **landed at `docs/intake/world_manifest.schema.json`** (line-10 "Repo landing" says so for the sidecar; the §3.2/D3.2 path was not updated). SPATIAL/schema-consuming legs must read `docs/intake/world_manifest.schema.json`, or a human ruling moves it to `schemas/`.
- **M-2 — hython pin hazard.** `SYNAPSE_HYTHON` unset + no `hython` on PATH ⇒ hytest shim picks newest = **22.0.429** (no symbol table). Pin to 22.0.400. (T2.)
- **F-1 — dossier `N-x` ≠ repo `N-x`.** Blueprint IDs are dossier-numbered; the dossier is absent; the repo's `N-3..N-7` are a July-roadmap numbering. Reconcile §1.2 by **symbol**, not ID. (T3.)
- **`verified_lop_solaris_knowledge_22.0.400.json` absent.** Only 21.0.671 + 22.0.368 exist; the 22.0.400 build (the pin) has no matching knowledge file — a probe-output gap Mile 1 fills.
- **`authoring_domains.json` is under `server/`**, not repo root — the §3.1/D3.1 diff target is `python/synapse/server/authoring_domains.json`.

---

*BP3-RECON created nothing outside `touches` (this file + its receipt). `harness/fixtures/`, `harness/scenes/`, `schemas/`, `frames/` remain absent by design.*
