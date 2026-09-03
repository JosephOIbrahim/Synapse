# BP4-SPATIAL — spatial lane probes (Mile 2, D3.3/D3.4)

**Leg:** BP4-SPATIAL · band BUILD · tier reasoning · branch `bp4/spatial`
**Build:** Houdini **22.0.400**, Python 3.13.10 (`hou.applicationVersionString()`, live)
**hython:** `C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe` (pinned; `BP3_RECON.md:57`)
**Pref dir:** `HOUDINI_USER_PREF_DIR=C:/Users/User/OneDrive/Documents/houdini22.0` (OneDrive redirect; `BP3_RECON.md:69`)
**Date:** 2026-09-03

> **Anchor discipline.** Every number below carries a producer path. Correctness
> anchors are PROBE's own output, re-read live. No anchor, no claim.

---

## TL;DR

Three read-only spatial tools built, **unregistered** (rule D-1), and green on
the pinned build.

- **`python/synapse/spatial/`** — `synapse_spatial_describe`,
  `synapse_spatial_classify`, `synapse_spatial_frustum`. Pure `pxr`, no `hou`,
  read-only (no prim authored, no file written).
- **`tests/test_spatial_lane.py`** — **14 passed in 3.29s** on hython 22.0.400.
- Every tool call is **~1000× under the 5 s budget** on the 46,993-tri collider
  (max 0.0051 s).

**One headline finding (runtime beat the brief's premise).** PROBE's
`b6_wl_component.usdc` does **not** contain the 46,993-tri collider — its proxy
is a **4-face auto-proxy**. The 46,993-tri collider lives in the **GLB**. So
`describe` runs on the `.usdc` (its bounds are exact); `classify`/`frustum`
run on the collider materialized from the GLB (the substrate the S-2/S-3
anchors actually measured). See **Finding F-1**.

---

## D-DEP-03 — pxr, not hou (said, per the brief)

The tools answer questions about a **USD component at rest** (a `.usdc`, or any
live LOP `.stage()`), so the native reader is **OpenUSD (`pxr`)**. The closest
*published spatial* method in the repo is already pxr — PROBE's S-1 walk uses
`UsdGeom.BBoxCache` (`harness/probes/synapse_blueprint_probes.py:419`). RECON's
D-DEP-03 note (`BP3_RECON.md:71`) records that the *existing* bounds code is
`hou`-based, but that code introspects a **live `hou.Geometry`** in a running
session — a different context. For a read-only query on a USD stage, pxr is the
honest fit; the module never imports `hou`.

---

## The three tools

| Tool | Answers | Key output |
|---|---|---|
| `synapse_spatial_describe(stage, prim_path, purposes)` | world bounds + extent of a subtree | `bounds_m [[min],[max]]`, `size_m`, `center_m`, `up_axis` |
| `synapse_spatial_classify(stage, prim_path, max_angle_deg=45, up)` | floor/wall/ceiling/slope **fractions** at a Max Angle + a ground-plane candidate | `surface_classes`, `counts`, `ground_y`, `floor_area_m2` |
| `synapse_spatial_frustum(stage, eye, forward, up, half_fov_deg=45, aspect=0.5625)` | face count inside a camera frustum | `inside`, `total`, `fraction` |

Output shape mirrors the manifest `space` object
(`docs/intake/world_manifest.schema.json`: `bounds_m`, `surface_classes`
`{max_angle_deg, floor, wall, ceiling, slope}`, `provenancedNumber`).

`classify`'s **`max_angle_deg` default = 45.0** = the scatterinstances
`maxangle` ('Max Angle', folder `/Scattering/Masks/Up Axis Direction`) parm
default — **live-introspected** on 22.0.400 (P-5): `defaultValue() == (45.0,)`,
`parm('maxangle').eval() == 45.0`.

---

## Correctness — anchors vs. tool, live

Fixture (raw frame, +y DOWN per WL-EX-05). `classify`/`frustum` use `up=(0,-1,0)`.

| Predicate (T2) | Anchor (producer) | Tool result | Verdict |
|---|---|---|---|
| describe bounds == B-3 bbox (≤1e-3) | `min[-5.339412,-5.957128,-19.709951] max[2.660879,0.696587,21.513170]` (`supplementary.txt` v2 L91 + S-1 `stdout.txt:399`) | **identical** (0.0 err), 0.0051 s | **PASS** |
| classify counts == S-2 (46,993 tris) | @20 `4919/26900/350/14824` · @35 `6414/34415/963/5201` · @45 `7733/37441/1819/0` (`supplementary.txt` v2 L94–96) | **byte-exact** at all three angles, 0.0011 s @45 | **PASS** |
| floor fraction covers the lane | — | floor z-span = **99.1%** of lane z-extent | **PASS** |
| walls present both sides (sign of x) | — | x<0: 22664, x>0: 11751 → **both** | **PASS** |
| dominant floor height == S-2 bin (±bin width) | method: `histogram(floor_y, bins=50).argmax()` (`synapse_blueprint_probes.py:440`) | tool `ground_y=0.6008` == independent re-derivation within bin width `0.1129` (bin `0.5609..0.6738`, 3030 faces) | **PASS** |
| frustum count == S-3 (≤2%) | **stdout S-3 = 0/2 is DEGENERATE** (2 packed prims, `stdout.txt:416`). Re-derived on 46,993 tris via S-3's published method (`synapse_blueprint_probes.py:453`) | tool **20146/46993** == independent oracle within 2%, 0.0009 s, same eye `[-1.339,-0.999,0.902]`/fov | **PASS** (against re-derived anchor; see F-2) |

Fixture-independent known-answer tests also pass (authored unit cube: floor 1/6,
wall 4/6, ceiling 1/6, slope 0; empty stage → honest `UNAVAILABLE`).

---

## Timing — each call < 5 s on the fixture collider (46,993 tris)

| Call | seconds (tool `seconds` field) |
|---|---|
| describe (component `.usdc` proxy) | **0.0051** |
| classify @45 (46,993-tri collider) | **0.0011** |
| frustum (46,993-tri collider) | **0.0009** |

Budget is 5 s; the slowest call is **~980× under**. The brief's "collider as it
is = 46,993 tris" (not 200k) is confirmed (`supplementary.txt` v2 L92: TRIANGULATED prim count 46993). Producer: `C:/Users/User/bp4_scratch/capture_out.json` (re-runnable — see §Re-run).

---

## Findings

### F-1 (headline) — `b6_wl_component.usdc` carries a 4-face proxy, not the collider

The component export decimated the collider into an auto-proxy. Live pxr read of
the `.usdc` (probe 1):

```
/wl_import/WL_fixture/geo/proxy/world            Mesh  faces=4  points=6  orient=leftHanded
/wl_import/WL_fixture/geo/proxy/world/geometry_0 Mesh  faces=4  points=6
/wl_import/WL_fixture/geo/proxy/autoproxy        Mesh  faces=4  points=8
```

The 46,993-tri collider is in the **GLB**
(`…/narrow_european_cobblestone_lane_collider.glb`), which B-6 fed through
`usdcreateproxygeometry` — that node builds a *proxy*, so the full mesh never
reached the `.usdc`. The `.usdc` bounds still equal B-3 exactly (bounds survive;
geometry does not), which is why `describe` is exact on the `.usdc` while
`classify`/`frustum` must use the GLB collider.

**Reconciliation (runtime is truth):** `describe` → `b6_wl_component.usdc`;
`classify`/`frustum`/timing → the 46,993-tri collider materialized from the GLB
(`gltf → unpack → sopimport`, validated to reproduce the S-2 anchor **byte-exact**).
The brief's "tests on `b6_wl_component.usdc`" assumed the `.usdc` held the
collider; it does not. This did not weaken any anchor — every S-2/S-3 number is
still reproduced on the geometry those numbers were measured on.

### F-2 — stdout S-2/S-3 are degenerate; the real numbers live in `supplementary.txt`

`stdout.txt` S-2 (`floor=0 wall=2`) and S-3 (`0/2`) ran on the **2 packed prims**
of the gltf SOP import, not the unpacked mesh. The authoritative per-face numbers
are the **CORRECTION RUN v2** in `supplementary.txt` (L86–96). The frustum
predicate's "== S-3 count" therefore anchors to the **re-derived** count (20146),
not the degenerate stdout 0 — computed by an independent oracle inside the test
using S-3's own published formula, so the crucible can re-run it.

### F-3 (for_ruling) — the fixture binaries are uncommitted

`b6_wl_component.usdc` (19.8 MB) and the collider GLB are **uncommitted** —
PROBE deliberately left them unstaged (`run_meta.txt`: "reproducible from
stdout+probe script"). They exist on this machine (sibling `bp3-probe`
worktree), so the live run is real, but a **fresh checkout does not have them**.
The fixture-anchored tests therefore **skip with a reason** when the binaries are
absent (visible skip, never a hidden pass); the **fixture-independent** tier
(authored geometry) always runs and is the reproducible core. **Ruling wanted:**
commit the collider GLB (≈0.9 MB) as a lane fixture, or add a regen script, so
the anchored tests execute in CI. Committing was out of this leg's `touches` and
a 19.8 MB binary to a public repo is a human decision, so it was not done here.

---

## Registry — no default-on registration (rule D-1)

The World Labs lane is `ratified:false`, so the tools are unregistered. Live grep
(`2026-09-03`, from the worktree root):

```
$ grep -rn "synapse_spatial_(describe|classify|frustum)|import synapse.spatial" python/ mcp_server.py | grep -v python/synapse/spatial/
(none)
$ grep -rn "SYNAPSE_SPATIAL_LANE" python/ mcp_server.py
python/synapse/spatial/__init__.py:21   # inside the module docstring (opt-in example), not executed
```

Nothing outside the package imports or registers the tools; the
`SYNAPSE_SPATIAL_LANE` flag is documented but **unread** in code. Pinned by
`tests/test_spatial_lane.py::test_no_default_on_registration`.

---

## D3.4 — second stage without code change

`fixtures/solaris.basic.json` is built live (`sopcreate → domelight → materials
→ camera → karmarendersettings`) and all three tools run on its `.stage()`
**unmodified**. Its geometry is empty, so `describe`/`classify`/`frustum` return
an honest **`UNAVAILABLE`** (not a SUCCESS with zero payload) — the point is
portability, and the tools handle a different stage gracefully. Pinned by
`tests/test_spatial_lane.py::test_D34_solaris_basic_runs_without_code_change`.
A second, fixture-free portability proof (authored cube) returns real numbers.

---

## Re-run (operator)

```
# from the worktree root; fixtures resolved from the sibling bp3-probe worktree
export HOUDINI_USER_PREF_DIR="C:/Users/User/OneDrive/Documents/houdini22.0"
HYTHON="C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe"
"$HYTHON" -m pytest tests/test_spatial_lane.py -v -o addopts=""
```

- Pin **22.0.400** (22.0.429 has no symbol table and fails the hytest gate; `BP3_RECON.md:67`).
- Fixture-anchored tests read `SYNAPSE_WL_COMPONENT_USDC` / `SYNAPSE_WL_COLLIDER_GLB`
  env vars, then known locations; absent → visible skip.

---

## Acceptance

| # | Predicate | Evidence | Verdict |
|---|---|---|---|
| 1 | three tools return correct answers per T2 tolerances | 14/14 tests green; anchors byte-exact | **PASS** |
| 2 | each call < 5 s on the fixture collider (46,993 tris), recorded | 0.0051 / 0.0011 / 0.0009 s (above) | **PASS** |
| 3 | tools run on a second stage without code change (D3.4) | solaris.basic + authored cube | **PASS** |
| 4 | no default-on registration | grep (above) + registration test | **PASS** |

**Status: green_with_findings** — all four predicates pass; F-1 (substrate) and
F-3 (uncommitted fixtures) are surfaced for the ruling, not blockers.
