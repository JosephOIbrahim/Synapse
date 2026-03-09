# RELAY-SOLARIS Phase 4 — Saved State

## Connection Verified
- Houdini **21.0.631** live at `ws://localhost:9999/synapse`
- `execute_python` works but has scoping quirk: multi-line scripts with dict literals fail with "name not defined"
- **Workaround:** Use semicolon-separated single-line scripts, or avoid complex dict construction

## Component Builder Verification: NOT YET RUN
- Connection confirmed but the verification script hit the scoping bug
- Need to restructure as simpler sequential calls or use a different approach

## Smoke Tests T1-T7: NOT YET RUN

### Test Plan (from sprint)
| Test | Pattern | Pass Criteria | Blocker? |
|------|---------|--------------|----------|
| T1: Scene Template | P1 | Full chain Primitive→ROP, paths correct | YES |
| T2: Component Builder | P2 | Subnet with geo/material/output, exports .usd | YES |
| T3: Purpose Toggle | P3 | Proxy visible, render geo at render | NO |
| T4: Hierarchy Check | P4 | Outliner shows /shot/ tree | YES |
| T5: Variant Creation | P5 | Material variant set, Explore Variants works | NO |
| T6: Megascans Import | P6 | .usdc imports at scale with materials | NO |
| T7: Render Output | P1 | ROP produces .png (unless BL-007) | YES |

### Known Risks
- BL-007 (EXR not written) may block T7
- BL-008 (asset refs invisible in Karma) may block T6, T2

## Next Session Instructions
1. Run component builder verification as individual createNode calls (not one big script)
2. Run T1-T7 smoke tests sequentially
3. Write results to `synapse/validation/solaris/smoke_test_results.md`
4. If blockers pass, create `.gate_passed`
5. Commit and push
