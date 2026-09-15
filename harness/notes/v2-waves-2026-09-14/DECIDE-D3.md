# D3 — RULED, 2026-09-14

**Decision:** the fixture task set is the ten tasks already in
`harness/v2-20260913/artifacts/v2-baseline/baseline.csv`.

**Ruled by:** Joe, 2026-09-14. Blueprint default was *"none — nothing measures
without it"* (`SYNAPSE_V2_BLUEPRINT_B.1.md:425`). That default is now retired.

## The set

| Task | Trips | Structural assertion |
|---|---|---|
| `exp-01` | 11 | Bound box: 8 points, 6 polygons, bounds [-1,-1,-1] to [1,1,1] |
| `exp-02` | 8 | Copy output: 8000 points, 6000 polygons; scatter-to-copy topology |
| `exp-03` | 8 | Transform output: one point, one Sphere primitive |
| `top-01` | 5 | Copy output: exactly 200 points and 200 Sphere primitives |
| `sop-01` | 9 | 1000 points with float `pscale` attribute |
| `sop-02` | 11 | 100 points, 81 polygons, float3 `Cd` on destination grid |
| `sop-03` | 8 | Two volumes `height` and `mask`; elevation bounds −62.969120 to 84.602806 |
| `ari-01` | 8 | Composed `/lights/LGT_area` is RectLight |
| `ari-02` | 7 | Composed LGT_key / LGT_fill / LGT_rim are SphereLight |
| `ctx-01` | 14 | Composed `/IMPORT_sphere/sphere_0` is Sphere, external SOP reference |

Families: exp ×3 · top ×1 · sop ×3 · ari ×2 · ctx ×1.
All rows `measurement_kind=proxy` — computer-use runs, never artist benefit.
Producer: `csv.DictReader` over `baseline.csv`.

## What this ruling unblocks

**Fully:** G0 and P1–P4. The re-instrument now has a named set to run, which is
what it was waiting on. Through it: C3's gate, guess 2, guess 6, Mile 4's
precondition, G4's second goalpost half, Mile 6's condition, a settling path for
guess 3, and a denominator for C2's coverage claim.

## What it does NOT cover — scope boundary, stated so nobody assumes it

The blueprint uses D3 for three things. This set serves the first two and only
partly the third.

| Rung | Covered? | Why |
|---|---|---|
| R1 two-node SOP (box → transform) | **substantially** | `exp-01` + `exp-03` |
| R2 ten-node chain, one APPLY dispatch | **partially** | `exp-02`, `sop-01`, `sop-02` are multi-node, but none is stated as ten-node and none asserts dispatch count |
| R3 Solaris lookdev, MaterialX surface | **NO** | `ari-*` are lighting, `ctx-01` is import. No material task, no MaterialX assertion. This is Mile 2's gate and INTENT §8's preferred first qualification area |
| R3b continuation after ten folded tasks | **NO** | a sequencing test, not a task |
| R4 structural recall across a restart | **NO** | Mile 6's gate |
| R5 APEX | n/a | explicitly parked |

**And the perturbation half is largely UNKNOWN even where structure is asserted.**
`exp-01` records *"radius-change behavior UNKNOWN"*, `exp-03` *"dynamic rotation
behavior UNKNOWN"*, `sop-01` and `sop-02` *"numeric samples unavailable"*.
Blueprint §11 defines a rung as *prompt → proposal → validate → apply → assert
structure → perturb → cook → assert downstream motion*. These ten assert
structure. They mostly do not assert downstream motion, which is the half that
makes it a perturbation bench.

**So:** D3 is ruled and the baseline is unblocked. The R-ladder is not — R3 and R4
need tasks this set does not contain, and that is a separate, smaller decision
when Mile 2 and Mile 6 come up.

## Not yet in the ledger

This ruling should reach `harness/state/DECISIONS.md`. That board is 44 days
stale and reports 286 open against a live 632 (`python harness/decisions.py`), so
writing there without reconciling it first would add to a count nobody trusts.
Recorded here; ledger entry is a separate act.
