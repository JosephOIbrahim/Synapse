# RELAY-SOLARIS Phase 4 — Smoke Test Results

**Agent:** AGENT-SUP (VFX Supervisor)
**Date:** 2026-03-08
**Houdini:** 21.0.631 at ws://localhost:9999/synapse
**Synapse Protocol:** 4.0.0

## Component Builder Verification

**Result: SUBNET strategy**
- `componentbuilder` — NOT a native H21 node (createNode fails with "Invalid node type name")
- `componentgeometry` — EXISTS, creates and destroys cleanly
- `componentmaterial` — EXISTS, creates and destroys cleanly
- `componentoutput` — EXISTS, creates and destroys cleanly
- **Decision:** Dual-path implementation confirmed correct. Runtime detection will select SUBNET path on H21.0.631.

## Smoke Test Results

| Test | Pattern | Result | Blocker? | Notes |
|------|---------|--------|----------|-------|
| T1: Scene Template | P1 | **PASS** | YES | Full chain: primitive→camera→materiallibrary→karmaphysicalsky→karmarendersettings→usdrender_rop. All wired sequentially. |
| T2: Component Builder | P2 | **PASS** | YES | Subnet `component_test_chair` with componentgeometry→componentmaterial→componentoutput wired internally. |
| T3: Purpose Toggle | P3 | **PASS** | NO | componentgeometry exposes `sourceproxy`, `sourcesimproxy`, `sourcesopproxy`, `sourcesopsimproxy` + USD ref variants. |
| T4: Hierarchy Check | P4 | **PASS** | YES | `/shot` primpath with Kind=group, Type=UsdGeomXform. Camera resolves to `/shot/cam/cam1` via `$OS`. |
| T5: Variant Creation | P5 | **PASS** | NO | Duplicate componentmaterial created as `componentmaterial_red`. explorevariants node creates successfully. |
| T6: Megascans Import | P6 | **PASS** | NO | SOP chain (usdimport→xform→matchsize→polyreduce) created in /obj. Reference LOP created in /stage. No .usdc file to test actual import, but pipeline verified. |
| T7: Render Output | P1 | **PASS** | YES | usdrender_rop produced 26,300-byte PNG at C:/Users/User/render/synapse_T7_test.0001.png (320x720, 4spp). BL-007 (EXR not written) did NOT manifest for PNG output. |

## Known Issues Encountered

1. **execute_python scoping bug**: Multi-line scripts with dict literals fail with "name not defined". Workaround: use semicolon-separated single-line scripts or expression-return style.
2. **karmarendersettings resolutiony locked**: `resolutiony` parm throws permission error on `.set()` even when `res_mode="manual"` and parm reports `isDisabled=False, isLocked=False`. Likely auto-driven by aspect ratio. `resolutionx` sets fine.
3. **materiallibrary has no primpath parm**: Unlike other Solaris nodes, materiallibrary doesn't expose a `primpath` parameter directly. Tool implementation should skip primpath assignment for this node type.
4. **print() output not captured**: `execute_python` returns "executed" for print() calls but doesn't capture stdout. Must use expression-return style (bare expression as last statement) to get values back.

## Blocker Status

- **BL-007 (EXR not written)**: NOT triggered — PNG output works. EXR untested.
- **BL-008 (asset refs invisible in Karma)**: NOT triggered — Reference LOP creates successfully. Full Karma visibility untested (would require actual .usdc asset).

## Gate Decision

**ALL 4 BLOCKER TESTS PASSED (T1, T2, T4, T7).**
All 7 tests passed total.
Phase 4 gate: **PASSED**.
