# HD1 physical frame: review (2026-11-15)

**What this is.** The HD1-M4 report for wave HD1: one posed RGBD frame, from an analytic fixture
with known answers, made metric, level and collidable, with a rest test in headless hython and a
`.usdc` out. Every number below names its producer. This report gives numbers and evidence; it
judges none of them. D-1 decides each gate and each tolerance.

**Producers.** M2 = the HD1-M2 report (the pure-Python chain and its tests; its final HD1 log is
`fix-final-hd1.log`, cited as FH:line). M3 = the HD1-M3 report (the hython probe; its final run
log is cited as L3:line). M3V = the independent re-run of M3 (VERIFY-HD1-M3). The three reports
live in the build's working set outside the repository; the probe and its receipts are in this
commit (`harness/probes/hd1_physical_frame.py`, `harness/notes/hd1/metrics.json`,
`harness/notes/hd1/hashes.sha256`).

---

## 1. Build pin, base commit, files

- **Houdini:** 22.0.400, headless hython, Indie licence, `ui_available` False (L3; M3V `run.json`).
  Python 3.13.10, numpy 2.3.2, USD 0.26.5 inside hython. Tests: CPython 3.14.2, numpy 2.2.6 (M2).
- **Branch and base:** `hd1/physical-frame` at `f58acb4ff1a344c51601e58d035a8feee056b235`, which was
  `origin/master` when the worktree was made. Nothing on the branch is committed yet.
- **Files (16):**
  - package `python/synapse/worldlabs/physical/`: `__init__.py`, `cloud.py`, `depth.py`, `level.py`,
    `scale.py`;
  - fixture `tests/fixtures/hd1_scene.py` (sha256 `db476e70…`);
  - tests `tests/test_hd1_boundary.py`, `_cloud.py`, `_depth.py`, `_fixture.py`, `_level.py`,
    `_scale.py`;
  - probe `harness/probes/hd1_physical_frame.py` (sha256 `4b44e5e4…`). The runs used `099f38ef…`;
    the only change since is the `--finalize` step, which now writes repository-relative paths,
    redacts the account folder to `Users/Example` and hashes the receipts' committed LF bytes;
  - receipts `harness/notes/hd1/metrics.json` (`1164c714…`, rebuilt by that step from the same run
    folders) and `hashes.sha256`;
  - this report.
- **The four World Labs modules are unchanged.** `git diff --stat` over `worldlabs/client.py`,
  `importer.py`, `atlas.py`, `atlas_contracts.py` and `docs/intake/atlas/` prints nothing (M2 section 6;
  re-run for this report).

## 2. Tests

- **HD1 tests, final run:** 175 passed, 0 failed, 0 skipped (FH:474): boundary 11, cloud 31, depth 58,
  fixture 33, level 26, scale 16.
- **Regression set (SPEC 10 plus two files):** 183 passed, 6 skipped, 0 failed, equal to the baseline
  taken on the untouched worktree (M2 section 3.1).
- **Tree-wide scanners (10):** 74 passed, 8 skipped, 0 failed, equal to the baseline (M2 section 3.2).
- **The probe's own checks:** `--verify` on variants A and C, 71 asserted, 0 failed (L3:278). M3V re-ran
  it and got the same: identical `.usdc` bytes, bit-identical trajectories, and the same metrics
  except the 12 wall-clock timings.
- **Not run:** the CI matrix (Linux, macOS, Windows on Python 3.11 and 3.14) and the full suite (M2
  section 9.1).

## 3. SPEC 9 metrics beside their truth and proposed tolerance

The tolerances are SPEC 9's proposals for D-1; no verdict is given here.

| Metric | Measured | Truth | Proposed tolerance | Producer |
|---|---|---|---|---|
| Levelling rotation, variant B | 5.828991157608686° recovered; error 1.10e-13° (1280×720), -2.40e-14° (160×90) | 5.828991157608...° | within 1.0° | M2 R.numbers#11, #14 |
| Floor height, A / B / C / D (1280×720) | -5.43e-17 / error 6.28e-14 / 6.92e-16 units / -5.45e-17 | 0 (B: the fixture's offset) | within 2 cm | M2 R.numbers#10-13 |
| `derived:camera-height` scale, variant C | 0.4000000000000001 (relative error 1.39e-16) at 1280×720; 0.40000000000000013 (2.78e-16) at 160×90 | 0.4 m per unit | within 2% | M2 R.numbers#15, #16 |
| Rest height at frame 120, S1 | -2.69700217 m (A and C) | 0.10 m | within 5 cm | L3:127, :233 |
| Rest height at frame 120, S2 | -1.9747026 m (A), -1.31616163 m (C) | 0.85 m | within 5 cm | L3:146, :252 |
| S3 | fell through: -120.149994 m, never touched the collider | falls through | falls through | L3:164-167, :270-273 |
| Numpy cloud against the contract's unprojection | max abs difference 0.0 m over 14,196 pixels, variants A and C at 160×90, both scale claims | 0 | within 1e-9 | FH:203-208 |

**What sits beside the S1 and S2 rest numbers.** Both spheres touched on frame 9 and first rested on
site: median height 0.104444236 m at S1 (+0.00444 m over truth) and 0.85308069 m at S2 (+0.00308 m).
They then rolled off: S1 drifted 2.44 m, S2 3.32 m (A) or 3.56 m (C), and each crossed below the floor
plane 0.166-0.190 m (xz) from the nearest observed point (L3:116-145, :222-251). SPEC 9 measures
the final height at frame 120 only, so the table above carries those, and the on-site heights are a
diagnostic beside them (section 5, item 3).

## 4. HD1.1 to HD1.8

| ID | Done when | Status | Evidence |
|---|---|---|---|
| HD1.1 | worktree on `hd1/physical-frame` off `origin/master`; main checkout untouched | evidence found | branch and base in section 1; main checkout's porcelain count 176 before and after (M2 section 1.4) |
| HD1.2 | package, fixture, tests and probe exist; the import rule holds | evidence found | the 15 files in section 1; `test_hd1_boundary.py` 11 passed (pure modules import neither `hou` nor `pxr`; importing registers nothing) |
| HD1.3 | the four World Labs modules byte-identical | evidence found | empty `git diff --stat` (section 1) |
| HD1.4 | new tests pass; regression set unchanged | evidence found | section 2 |
| HD1.5 | cross-check holds; half pixel reported as a number | evidence found | 0.0 m over 14,196 pixels; half pixel in section 6 |
| HD1.6 | level, ground and scale for variants A to D | evidence found | M2 R.numbers#10-16 (all four variants, both grids); `metrics.json` carries the chain for A and C, the variants the probe ran |
| HD1.7 | collider, three rest tests, `.usdc` written and re-opened | evidence found, except HD-04's stated condition, which is UNKNOWN | L3 and M3V; HD-04 in section 5 |
| HD1.8 | review doc, receipts and a G-8 promotion proposal; nothing committed without Joe | evidence found on this report's commit, which waits for Joe | this file; `harness/notes/hd1/`; section 7 |

## 5. Conflicts with the SPEC and other findings (each dated 2026-11-15)

1. **V0, what the live build said.** All 10 node types instantiated on 22.0.400: `file`,
   `vdbfromparticles`, `convertvdb`, `sphere`, `pack`, `name`, `merge`, `rbdbulletsolver`,
   `attribwrangle`, `grid`. 40 parm rows checked on live instances; the node catalogue agrees on every
   default. The probe changed eight parms from their live defaults and left the rest:
   `file.file` (the cloud's points), `vdbfromparticles.voxelsize` (item 2), `convertvdb.conversion`
   (volume to `poly`), `sphere.rad` (0.1), `sphere.t` (the release point), `name.name1` (S1 to S3),
   and the solver's two settings in item 3 (L3 parm ledger; M3V checked all 40 independently).
   `cook`, `parm`, `parms` and `NodeType.definition` live on the `Op*` subclasses on 22.0.400; calls on
   live instances work.
2. **SPEC 7.2 voxel size.** The SPEC names no voxel size. At the live default (0.1 m) the VDB of this
   cloud has 0 active voxels (L3:102, :208). The probe used `min(pscale) / minvoxelradius` =
   0.0022109868 m, chosen before any rest result: 62,220,665 active voxels, 16,767,118 polygons,
   33,534,236 triangles, and a 238 MB `.usdc` per variant. Only those two voxel sizes were run, so
   M3's wording that this is "the only setting that keeps every particle" has no producer (M3V R2).
3. **SPEC 7 rest metric: a reporting gap.** Final height and "fell through" at frame 120 do not tell a
   sphere that passed through a surface from one that rested on site and then rolled off the observed
   collider. Both are recorded (section 3); D-1 picks the metric.
4. **SPEC 7.3 solver defaults.** `collision_bullet_georep` defaults to `convexhull` and
   `collision_initialstate` to `animatedstatic`; the probe set `concave` and `static`. Bullet's 0.02 m
   paddings stayed at their defaults.
5. **Settle threshold.** 0.01 m/s on the last 12 frames is the probe's proposal for the SPEC's "small
   threshold"; no site met it (maxima 5.14-48.44 m/s, L3).
6. **HD-04 is UNKNOWN for its stated condition.** The SOP-level bullet solve cooked headless in all
   three batches, but no Houdini GUI was running in any process snapshot, so "while the GUI holds a
   seat" was never tested.
7. **HD-05, the depth mask.** The contract's `mask_depth` keeps finite depths above 65504 and HD1's mask
   drops them: on variant D, 1,024 pixels at 1280×720 (contract 920,576 valid, HD1 919,552) and 16 at
   160×90; none the other way (FH:310-311). Reported, not resolved.
8. **The `vdbfromparticles` warning count varies** ("Ignored N small particles": 17,039, 12,605, 3,957,
   and 15,254 in M3V) for the same 229,991-point input, even within one process. Cause UNKNOWN.
9. **Two corrections to M3's report from M3V.** "43 of the 44 hou calls checked are present" has no
   producer: the recorded lists give 25/25, 33/33 and 56/60 (M3V R1). And `customData`'s
   `fixture_sha256` holds the per-variant fixture digest, not the fixture file's sha256.
10. **Process.** The probe's first hython import wrote 107 git-ignored `.pyc` files into this worktree's
    `__pycache__` folders; no tracked file changed (M3, M3V).

## 6. D-HD-04: the half pixel, and the floor fit it moves

- **The half pixel** between the landed `x - cx` and AT1 SPEC 7.3's `x + 0.5 - cx`, at the median depth
  of the kept pixels: **2.713489778781218e-03 m** at 1280×720 (z = 3.8374540465 m, fx = fy = 1000) and
  **2.191868994553073e-02 m** at 160×90 (z = 3.8747135738 m, fx = fy = 125). The measured medians differ
  from the closed form `0.5 · z · hypot(1/fx, 1/fy)` by -1.5e-16 m and -7.6e-17 m (FH:265, :268).
- **What it does to the floor fit** when the frame is rendered through pixel centres and the landed
  chain is unchanged: tilt 0.0253° and camera height -0.24 mm at 1280×720; tilt 0.2021° and -1.94 mm
  at 160×90 (FH:271, :274). Unresolved; the convention is D-HD-04's.

## 7. G-8 promotion proposal (a proposal only)

G-8 holds any real World Labs frame. This report proposes the conditions under which D-1 might move
HD1 from the fixture to one real frame; it moves nothing.

1. **D-1 rules first** on the SPEC 9 tolerances, the rest metric (final height, on-site height, or
   both; section 5, item 3), the settle threshold, and the proposed constants M2 lists
   (`FOOTPRINT_K`, `CONFIDENCE_MIN`, `EDGE_REL_MAX`, `FLOOR_INLIER_REL`, `FLOOR_ITERATIONS`,
   `FLOOR_SEED`).
2. **The rolling is explained on the fixture before a real frame:** a ruled probe varies the collider
   (voxel size, adaptivity, the footprint's missing obliquity term, which leaves gaps between floor rows
   0.018 m apart against a 0.011 m inflated footprint) and Bullet's paddings and friction, and reports
   which change keeps S1 and S2 on site.
3. **The collider budget is ruled:** 33.5 million triangles and 238 MB per frame, or a coarser rule.
4. **D-HD-04 and HD-05 are decided**, because a real frame inherits both.
5. **HD-04 is measured** with the GUI holding a seat, or ruled unnecessary.
6. **The real frame's own gates hold:** EXR decoding (AT1's D-AT-06), and any network call, key or
   spend, each by its own ruling.

Proposed order: 1, then 2 and 3 together, then 4 and 5, and only then a single saved real frame run
offline through the same probe.
