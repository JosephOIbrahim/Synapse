# SYNAPSE 2.0 — Verification Ledger

**Target Runtime:** Houdini 21.0.631
**Daily Driver:** 21.0.631 (confirmed 2026-04-18)
**Lock Duration:** Sprints 1–4
**Ledger Status:** LOCKED
**Sprint 2 Week 1 Schema:** v1.0.0

---

## Sprint 1 — Runtime Verification Gate (CLOSED)

| # | Check | Status | Evidence | Notes |
|---|---|---|---|---|
| 1 | `dir(hou)` — `lop` present | **GREEN** | `"lop" in dir(hou)` → True | hou.lop module exists |
| 2 | `hou.LopNode` — `stage` method | **GREEN** | `"stage" in dir(hou.LopNode)` → True | LOP API surface confirmed |
| 3 | USD attr round-trip | **GREEN** | `synapse:test` authored via PythonScript cook → read from downstream null `.stage()` → 1 | Attribute survives cook boundary into downstream composed stage |
| 4 | `InputDataChanged` on LOPs | **GREEN** | `fired=[]; n1.parm('tx').set(1.0); _=n2.stage(); len(fired)>0` → True | Fires **synchronously** during `.stage()` evaluation. No event-loop pumping needed |
| 5 | `hdefereval` headless | **RED-MITIGATED** | `ImportError: hdefereval is only available in a graphical Houdini` | Source: hdefereval.py line 241. SYNAPSE 2.0 operates graphical via WebSocket only. Headless deferred to post-2.0 |
| 6 | `pxr.Usd.Stage` type | **GREEN** | `type(n.stage()).__module__=='pxr.Usd' and type(n.stage()).__name__=='Stage'` → True | String-compare caveat: false-negative possible if Houdini wraps Stage class |
| 7 | Transport stability | **GREEN (implicit)** | All payloads executed without WebSocket errors | |
| 8 | Sublayer multiparm | **GREEN** | Count parm: `num_files`. Entry parms: `filepath#` (1-indexed) | Discovery-first validated |

### Footnotes

- `hou.ui.processEvents()` does NOT exist in H21.0.631. If future sprints need event pumping, this method is unavailable.
- Claude Code Hooks deferred to post-2.0. Seven API questions remain open in that blueprint. Sprint 1 finding (`hdefereval` headless RED) confirms the deferral was correct.

---

## Sprint 2a — Parameter Discovery (CLOSED)

### Payload E.0: MaterialLibrary + Reference Discovery

```
MatLib parms: ['genpreviewshaders', 'allowparmanim', 'referencerendervars',
  'parentprimtype', 'matpathprefix', 'fillgroup', 'matnet', 'containerpath',
  'fillmaterials', 'materials', 'enable1', 'matflag1', 'matnode1', 'matpath1',
  'assign1', 'geopath1', 'tabmenufolder', 'tabmenumask', 'fillgroup2']
MatLib child cat: Vop
principled exists: True
mtlx exists: True
Ref parms: ['files_group', 'num_files', 'handlemissingfiles',
  'filepath1', 'filerefprim1', 'filerefprimpath1']
```

**Decisions:**
- Shader type: `mtlxstandard_surface` (H21 standard, cross-renderer)
- MatLib auto-fill parm: `fillmaterials` (confirmed)
- Reference file parm: `filepath1` (1-indexed multiparm)
- Assignment multiparm: `matnode#`, `matpath#`, `assign#` (reserved)

### Payload F: hou.LopNode API Surface

```
hou.LopNode matches: ['_OpNode__modificationTime', 'activeLayer',
  'addHeldLayer', 'addSubLayer', 'editableLayer', 'inEditLayerBlock',
  'inputPrims', 'lastModifiedPrims', 'layersAboveLayerBreak',
  'modificationTime', 'setLastModifiedPrims', 'sourceLayer',
  'sourceLayerCount', 'stagePrimStats']
hou.lop matches: ['defaultCamerasPrimPath', 'defaultCollectionsPrimPath',
  'defaultCollectionsPrimType', 'defaultLightsPrimPath',
  'defaultNewPrimPath', 'makeValidPrimName', 'makeValidPrimPath',
  'panesShowPostLayers', 'reloadLayer', ...]
```

### Payload F2: lastModifiedPrims() Verification

```
/stage/geo (sopcreate):  lastModifiedPrims: [Sdf.Path('/geo')]
/stage/mats (materiallibrary): lastModifiedPrims: []
/stage/xf (xform): lastModifiedPrims: [Sdf.Path('/geo')]
/stage/ref (reference::2.0): stage() fails (missing file)
/stage/comp (sublayer): stage() fails (upstream error)
```

**Decision:** `usd_prim_paths` populated via `node.lastModifiedPrims()`. Native Houdini API. No hardcoded dict. No provenance reverse-map.

**Bonus:** `inputPrims()` requires positional arg `inputidx`. Available for future enrichment.

### Fixture Generation

- `sopcreate` and `materiallibrary` are **locked HDAs** in H21.0.631
- `allowEditingOfContents()` required before `createNode()` inside them
- Week 1 flat fixture does not create internal children (deferred to Week 2)
- Fixture saved: `C:\Users\User\SYNAPSE\tests\fixtures\inspector_week1_flat.hip`

---

## Sprint 2 Week 1 — Architecture Decisions (LOCKED)

1. **usd_prim_paths:** Option D (discovery-first). Plural list. Via `lastModifiedPrims()`.
2. **Transport:** Server-side orchestrator. Base64 payload injection wrapper.
3. **AST Schema:** display_flag, bypass_flag, error_state, error_message, indexed inputs. Self-referential children for Week 2.
4. **Test Fixture:** 8 nodes at `/stage` covering all edge cases.
5. **Daily Driver:** 21.0.631 (matches target lock — no post-ship smoke pass needed).
6. **Schema Versioning (v4.7):** SCHEMA_VERSION="1.0.0" envelope on extraction payload. Prevents silent drift. Bumped on breaking schema changes.
