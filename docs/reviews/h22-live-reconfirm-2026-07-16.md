# H22 Live-Reconfirm — Drop-Cycle Verdict Flip

**Date:** 2026-07-16
**Build:** `22.0.368` — **VERIFIED-LIVE** (`hou.applicationVersionString()` returned verbatim by every probe in this run)
**Path:** the real SYNAPSE WS bridge (`ws://localhost:9999/synapse`), protocol **4.0.0** — a live, running Houdini 22.0.368 GUI session, **not** hython. (The W.1 planes/drift probe drove the same live in-process interpreter through a harness that reported protocol `5.4.0`; the build string `22.0.368` is identical and authoritative — protocol string differs by client harness, the interpreter does not.)
**Scene state:** empty / `untitled.hip`, never saved. Every behavioral probe created scratch nodes, cooked, and destroyed them in a `finally`; each report verified `/obj` and `/stage` children `[]` and the hip untouched afterward. All symbol/quarantine/pdg probes were introspection-only (zero nodes created).
**Runtime deps:** Python `3.13.10` · pxr USD `0.26.5`.

> **Purpose.** This drop cycle merged several waves on **PROVISIONAL-headless** verdicts (hython PASS = provisional per protocol; H21 is uninstalled and no baseline artifact was ever captured, so the H21→H22 side of any *delta* cannot be A/B'd live). This document reconfirms every one of those provisional verdicts against the live bridge and records the flip. **Net: 32 verdicts flipped PROVISIONAL-headless → VERIFIED-LIVE, 6 → REFUTED-LIVE, 1 remains STILL-UNKNOWN** (the H21 baseline half of the pdg Scheduler removal delta — a known, unfixable-this-session limitation, not an open risk on H22).

---

## 1. Verdict-Flip Table

Every verdict that entered this reconfirm PROVISIONAL-headless, and where it landed live. "REFUTED-LIVE" here means the *claimed presence* was refuted (symbol absent) — which for the removed-quartet and `hou.secure` is the **desired** outcome, i.e. the removal/phantom is confirmed real.

### 1.1 Merged cycle W.1 / W.1b — COP node API delta + drift discipline

| Verdict (PROVISIONAL-headless) | Live result | Evidence (live bridge, 22.0.368) |
|---|---|---|
| `hou.CopNode.cable` present | **VERIFIED-LIVE** | `node.cable()` → `CopCable` on cooked `ramp` cop |
| `hou.CopCable.wireNames` / `.wireCount` / `.layerByIndex` present | **VERIFIED-LIVE** (×3) | `.wireNames()` → `['ramp']`, `.wireCount()` → `1`, `layerByIndex(0)` → `ImageLayer` |
| `hou.ImageLayer.bufferResolution` / `.storageType` / `.allBufferElements` / `.channelCount` present | **VERIFIED-LIVE** (×4) | `.bufferResolution()` → `[1024,1024]`, `.storageType()` → `imageLayerStorageType.Float32` |
| `hou.CopNode.planes` / `.xRes` / `.yRes` / `.depth` present | **REFUTED-LIVE — ABSENT** (×4) | `hasattr == False` on all four. Runtime confirmation of the H22 COP-node API delta (the api-delta pass had missed it; doc-scout HOM-02 caught it; now live-confirmed). |
| `hou.Cop2Node.planes` / `.depth` survive on legacy compat class | **VERIFIED-LIVE** (×2) | both `hasattr == True` on `Cop2Node` |
| **W.1 behavioral:** planes truthfully populated (not silently `[]`) | **VERIFIED-LIVE** | Both merged handlers (`_handle_cops_read_layer_info`, `_handle_cops_analyze_render`) drove the live cooked node → envelopes report `planes:['ramp']`. The exact W.1 crucible sev-3 failure class (silent `[]`) is **gone**. |
| **W.1b behavioral:** loud `api_drift` when a replacement symbol vanishes | **VERIFIED-LIVE** | Proxy raising `AttributeError` on `CopCable.wireNames` → `api_drift` entry fires end-to-end in `_copernicus_image_info` (`severity:'warning'`, `symbol:'hou.CopCable.wireNames'`), `analyze_render` → `overall_quality:'warning'` + honest `planes:[]`, `read_layer_info` → additive `api_drift` key, `_WARNED_COP_DRIFT` warn-once fired. Healthy node carries **no** `api_drift` key — golden envelope frozen. |

**Signature nuance captured (not a new candidate — already fixed + pinned):** `hou.Cop2Node.depth` is a **per-plane query**, not a bare property — `depth(self, plane: 'char const *') -> hou.imageDepth`. Any port treating it as a no-arg attribute breaks. Already handled in `python/synapse/server/handlers_cops.py:592/600` and pinned by `tests/test_cops.py:140`.

### 1.2 Merged cycle W.3 — setdressing

| Verdict | Live result | Evidence |
|---|---|---|
| W.3 setdressing create+cook | **VERIFIED-LIVE (at merge)** | Its own assay already ran a live **create + cook** during the merge cycle — the PROVISIONAL flag was discharged there, not carried into this reconfirm. No re-probe needed; recorded here as confirmed for completeness. |

### 1.3 Merged cycle W.5 — Karma light relationships (`light:filters` seam)

| Verdict (PROVISIONAL-headless) | Live result | Evidence (live bridge) |
|---|---|---|
| `Usd.Prim.GetRelationship` / `.GetRelationships` / `.CreateRelationship` present | **VERIFIED-LIVE** (×3) | all `hasattr == True` on live pxr 0.26.5 |
| `Usd.Relationship.GetTargets` / `.SetTargets` present | **VERIFIED-LIVE** (×2) | all present |
| **W.5 behavioral:** merged `handlers_usd` get/set falls back to the relationship surface on the migrated `light:filters` seam | **VERIFIED-LIVE** | Built `/stage` chain (`light` → `karmablockerlightfilter` ×2 → `pythonscript` assign → `karmarendersettings`), cooked. On the cooked stage `GetAttribute('light:filters').IsValid()` = **False** but `GetRelationship('light:filters').IsValid()` = **True** with targets. Merged get returned `['/_recon_karma_filter']` + `property_kind='relationship'` (did **not** raise); set round-tripped `['/_recon_karma_filter','/_recon_karma_filter2']` identically on readback. Old attribute-only get would have missed/raised. |

### 1.4 Quarantine re-pins + `hou.secure`

| Verdict (PROVISIONAL-headless / GUI-caveat) | Live result | Evidence (live GUI session) |
|---|---|---|
| `hou.secure` present as an auth surface | **REFUTED-LIVE** | `hasattr(hou,'secure')` → **False**; `import_module('hou.secure')` → `ModuleNotFoundError`. No `dir()`, no auth surface. |
| `hou.secure` GUI-caveat ("maybe GUI-lazy like `hou.qt`, appears on a real GUI session") | **CLOSED / REFUTED-LIVE** | Decisive calibration on this **live GUI** session: GUI-lazy `hou.qt` resolves **True** via getattr (would be False headless) and non-GUI-lazy `hou.text` resolves **True** — the introspection hook is working and *would* have surfaced a GUI-lazy `hou.secure`. It did not. `hou.secure` is a genuine phantom, not GUI-lazy. The `h22-quarantine-repin.md` caveat is retired. |
| SYNAPSE auth resolver auto-adopts `hou.secure` | **NO — VERIFIED-LIVE** | The resolver cannot adopt a symbol that does not exist in the runtime. No behavior change from the headless finding. |
| `hou.pdg` / `hou.lopNetworks` / `hou.updateGraphTick` / `hou.pdg.*` still absent | **VERIFIED-LIVE** (×4) | all `hasattr == False`; `hou.pdg.*` absent-by-consequence. The #1-failure-class phantoms stay phantom on H22. |

### 1.5 pdg event surface

| Verdict (PROVISIONAL-headless) | Live result | Evidence (live bridge) |
|---|---|---|
| `pdg` module present | **VERIFIED-LIVE** | `import pdg` succeeds |
| `pdg.PyEventHandler(fn)` has **no** constructor (R8 truth) | **VERIFIED-LIVE** | `hasattr` True but `pdg.PyEventHandler(fn)` → `TypeError('_pdg.PyEventHandler: No constructor defined!')`. Register a raw callable via `addEventHandler(fn, EventType)`; keep the returned wrapper for teardown. The CLAUDE.md phantom-constructor warning extends from "H21.0.671" to include 22.0.368. |
| `pdg.Graph.workItemById` exists | **VERIFIED-LIVE** | `hasattr(pdg.Graph,'workItemById')` → True |
| `pdg.GraphContext.workItemById` exists (per SideFX doc example) | **REFUTED-LIVE — ABSENT** | `hasattr(pdg.GraphContext,'workItemById')` → **False**. The doc-scout-caught **SideFX documentation error** is confirmed live — `GraphContext` has only add/commit/serialize verbs. Anyone porting from the doc's `GraphContext.workItemById` example breaks. (Already tracked as candidate **TOPS-02**.) |
| `pdg.EventType` members resolve (R8 event names) | **VERIFIED-LIVE** | full `CookComplete`/`CookError`/`WorkItem*` set intact and resolvable |
| 2 `pdg.Scheduler` removals (`onWorkItemFileResult`, `onWorkItemSetAttribute`) | **VERIFIED-LIVE on H22 · STILL-UNKNOWN on H21 baseline** | On H22 `pdg.Scheduler` has 101 members; both named symbols **absent**, superseded by the type-split family (`onWorkItemSetDictAttrib/SetFileAttrib/SetFloatAttrib/SetIntAttrib/SetPyObjectAttrib/SetStringAttrib` + `onWorkItemAddOutput(s)`). **Honest caveat:** absence-in-H22 is solid; the *H21→H22 removal* rests on the prior H21 doc reading, not a live A/B (H21 uninstalled). **Zero repo references to either removed name** (`h22-pdg-perception-reaudit.md:34`) → no SYNAPSE breakage either way. |

---

## 2. Pending-Behavioral Resolutions

### 2.1 W.4 — Copernicus solver-block binding (drives SB-3 fix shape)

This was **PENDING-BEHAVIORAL #2 / roadmap N-4** — the one question headless could not answer: *do Cop solver blocks bind implicitly now that `block_end` lost `blockpath`/`method`?* Answered live:

| Sub-verdict | Live result | Evidence (live bridge, deterministic A/B/C/D) |
|---|---|---|
| `block_end` lost `method` / `blocktype` / `blockpath` | **VERIFIED-LIVE (doc claim CONFIRMED)** | live `block_end` parm surface is a sim/iteration driver (`simulate`, `iterations`, `startframe`, `cacheenabled`, …) — none of the three removed parms present. `blockpath` now lives on **`block_begin`**. |
| Implicit binding "just works" (pair wired in the same `copnet`, `block_begin.blockpath` empty) | **REFUTED-LIVE** | cook raises `hou.OperationFailed` → `"Cannot do simulate if the block doesn't have a begin node at the same level."` The end cannot discover its begin without the begin declaring the pairing. |
| Explicit binding via `block_begin.blockpath` → paired `block_end` | **VERIFIED-LIVE** | `blockpath='../sb_end'` (relative) and `blockpath='/obj/.../sb_end'` (absolute) both cook clean (`be.errors()==[]`). Bare-name relative (`'sb_end'`) fails only because a node-ref parm resolves against the node's own children — a path detail, not a binding limit. |

**What it means for SB-3.** SB-3's fix shape was explicitly deferred to "decided by the N-4 live-bridge behavioral probe." **It is now decided:**

> **SB-3 fix = RE-AUTHOR WITH EXPLICIT BINDING.** Author `block_begin.parm("blockpath")` → the paired `block_end` (relative `../name` or absolute both valid). The "implicit binding just works" branch is dead.

**Concrete code impact (grounded).** `_handle_cops_create_solver` and its three siblings (`growth_propagation`, `reaction_diffusion`, `wetmap`) currently do the inverse and on the wrong node — `handlers_cops.py:1066` (and `:1233`, `:1357`, `:1698`):

```python
path_parm = block_end.parm("blockpath") or block_end.parm("block_begin")
if path_parm:
    path_parm.set(block_begin.path())
```

On H22, `block_end` has **neither** `blockpath` nor `block_begin` → `path_parm` is `None` → the guard skips silently → the block is left **unbound** → cook fails exactly as the W.4 probe showed. (The adjacent `method`/`blocktype` write at `:1060` is likewise a silent no-op on H22.) The fix is to point `block_begin.parm("blockpath")` at `block_end.path()` instead, in all four builders, before the cops-1/cops-2 golden capture.

### 2.2 Scaffold cook-through

No standalone scaffold-cook probe was dispatched, but cook-through was exercised incidentally and passed everywhere a scaffold was built this session: W.1 (`copnet` + `ramp` cop, `cook(force=True)` clean), W.4 (`copnet` solver block cooks clean once bound), W.5 (`/stage` light→filter→rendersettings chain cooked), and W.3's own assay create+cook. **Every scaffold built on 22.0.368 this session cooked through.**

---

## 3. CTO-01 — Memory-Evolution Fidelity

**Concern:** the USD 0.26.5 pxr reorg could break the Charmander→Charmeleon memory-evolution round-trip (the moat). **Result: VERIFIED-LIVE PASS — `fidelity == 1.0`. CTO-01 REFUTED-LIVE. Moat intact.**

- **Native path exercised, not the fallback:** `_PXR_AVAILABLE == True` → `_build_usd_native` ran. Every pxr symbol USD 0.26.5 could have broken is present live: `Tf.MakeValidIdentifier`, `Sdf.ValueTypeNames.String/StringArray/Asset`, `Vt.StringArray`, `Usd.Stage.CreateInMemory`.
- **Full evolve:** fixture tripped real triggers (`structured_data_count 5≥5`, `asset_references 3≥3`), parsed 2 sessions / 3 decisions / 3 assets / 2 parameters, returned `evolved=true, stage="charmeleon", fidelity=1.0, reason=""`, `verify_stage_detail = {fidelity:1.0, failures:[]}`.
- **Independent round-trip (the strength check):** reopened the written `memory.usd` on live pxr via `Usd.Stage.Open` → valid stage, 15 prims, default prim `/SYNAPSE`, `customLayerData` counts intact (session=2 / decision=3 / asset=3 / parameter=2), 3920 bytes.
- **Scope note (honest):** the `fidelity==1.0` gate itself (`_verify_lossless`) is a markdown→companion→reparse hash-diff and does **not** re-parse the USDA. But `_build_usd_native` sits in the critical path (raises on any broken pxr symbol — it did not), and the independent `Usd.Stage.Open` traversal confirms the emitted USDA is a valid, reopenable stage on 0.26.5. Both halves pass.
- **Minor, non-defect:** asset `ground.usda` sanitizes to prim name `grounda` (`.usd`/`.usda` stripped, then `Tf.MakeValidIdentifier` collapses the dot). Cosmetic; round-trips fine; fidelity unaffected.

**Wave impact: memory-1 / memory-2 are NOT blocked** by this gate.

---

## 4. `hou.secure` Auth Verdict + Phantom Re-Pin Confirmations

**`hou.secure` auth verdict: NO — VERIFIED-LIVE.** The SYNAPSE auth resolver does **not** auto-adopt `hou.secure` on H22.0.368, for the strongest possible reason: the symbol does not exist in the live runtime, and the calibration control (`hou.qt` resolving True on this live GUI session) proves a real GUI-lazy attribute *would* have surfaced. The GUI caveat is retired.

**Phantom re-pins, live-confirmed absent (the #1-failure-class guard holds on H22):**

| Symbol | Live | 
|---|---|
| `hou.secure` (as auth surface) | ABSENT — `hasattr False` + `ModuleNotFoundError` |
| `hou.pdg` | ABSENT — `hasattr False` |
| `hou.lopNetworks` | ABSENT — `hasattr False` |
| `hou.updateGraphTick` | ABSENT — `hasattr False` |
| `hou.pdg.*` | ABSENT — by consequence of `hou.pdg` absent |

---

## 5. What This Unblocks

- **W.4 fix shape is decided.** SB-3's "fix shape decided by N-4 live-bridge probe" precondition is satisfied. The four COP solver-block builders can be re-authored to bind explicitly on `block_begin.blockpath` and proceed to the cops-1 / cops-2 golden capture. The "implicit binding" branch is dead — do not build against it.
- **Every merged cycle's PROVISIONAL flag is cleared.** W.1/W.1b (planes + drift), W.3 (setdressing, already discharged at its assay), and W.5 (karma light relationships) are now VERIFIED-LIVE on 22.0.368 — no residual provisional debt on those merges.
- **CTO-01 moat is proven live.** memory-1 / memory-2 waves are unblocked (`fidelity == 1.0`).
- **Quarantine + pdg surfaces are settled.** The one verdict headless couldn't reach (`hou.secure` GUI caveat) is closed REFUTED-LIVE; all four phantom re-pins and the R8 event-bridge truths hold on H22.

### New findings needing a flywheel candidate

**No net-new phantom / API finding emerged from this reconfirm.** Every actionable maps to an already-tracked item:

- `Cop2Node.depth(plane)` signature → already fixed + pinned (`handlers_cops.py:592/600`, `test_cops.py:140`).
- `pdg.GraphContext.workItemById` doc error → already candidate **TOPS-02**.
- pdg Scheduler 2 removals → zero repo references, no breakage (no candidate warranted).

The one code-level realization worth an explicit, sharpened spec is the SB-3 create_solver binding-node defect that the W.4 probe exposed. It belongs inside existing **SB-3** rather than a brand-new independent finding — proposed here (ratified:false) for the human to fold into SB-3 or mint separately. **Not written to `flywheel_queue.json`.**

```json
{
  "id": "SB-3-fixshape",
  "ratified": false,
  "parent": "SB-3",
  "title": "SB-3 fix shape (decided by W.4/N-4 live probe): re-author COP solver-block binding onto block_begin.blockpath",
  "spec": "On H22.0.368, block_end lost method/blocktype/blockpath; blockpath now lives on block_begin and binding is NOT implicit (empty block_begin.blockpath -> hou.OperationFailed 'Cannot do simulate if the block doesn't have a begin node at the same level'). _handle_cops_create_solver (handlers_cops.py:1066) and the growth_propagation (:1233), reaction_diffusion (:1357), and wetmap (:1698) siblings currently set block_end.parm('blockpath') (and block_end method/blocktype at :1060), all of which resolve to None on H22 -> silent no-op -> unbound block -> cook failure. Fix: in all four builders, set block_begin.parm('blockpath') to the paired block_end path (relative '../<name>' or absolute both valid; bare name fails). Drop the dead block_end blockpath/method writes. Verify with a live create_solver + cook returning be.errors()==[]. Land before cops-1 (create_solver) and cops-2 (growth/RD/wetmap/stylize) golden capture.",
  "evidence": "docs/reviews/h22-live-reconfirm-2026-07-16.md §2.1 (live bridge 22.0.368, deterministic A/B/C/D: empty blockpath fails, '../sb_end' and absolute path cook clean)",
  "severity": "warn",
  "waves_gated": ["cops-1", "cops-2"]
}
```

---

*Provenance: synthesized from Phase-1 read-only probes (`hou.secure`/quarantine, merged-cycle symbols, pdg surface) and Phase-2 behavioral probes (W.4 solver-block, CTO-01 evolution, W.1/W.1b planes+drift, W.5 karma-rels), all executed against the live SYNAPSE WS bridge on Houdini 22.0.368, 2026-07-16. Cross-referenced: `docs/reviews/h22-quarantine-repin.md`, `h22-cop-audit-verification.md`, `h22-pdg-perception-reaudit.md`, `h22-cto-roadmap-2026-07-16.md` (SB-3/N-4/W-4), `h22-doc-intel-2026-07-16-wave2.md` (TOPS-02), `python/synapse/server/handlers_cops.py`, `shared/evolution.py`, `harness/state/flywheel_queue.json`.*
