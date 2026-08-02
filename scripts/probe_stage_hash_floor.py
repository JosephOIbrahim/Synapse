"""Stage-hash floor probe — the measurement behind the R1 size-gate DEFAULT.

Standalone (zero-``hou``): builds real in-memory pxr.Usd stages at parameterized
prim counts and times the two R1 stage-hash algorithms in shared/bridge.py:

  flatten     sha256(stage.Flatten().ExportToString())  — the proven full-fidelity
              path (byte-identical to the pre-gate algorithm)
  structural  LosslessExecutionBridge._structural_stage_signature(stage) — the
              COMPLETE traversal signature (digests every attribute value and
              every time sample). MEASURED NOT CHEAPER than Flatten — kept as
              an opt-in mode, not the gate default.
  reduced     LosslessExecutionBridge._reduced_stage_signature(stage) — the
              reduced-detail signature the size gate actually switches to
              (topology/typing/property structure, NO values; recorded on the
              IntegrityBlock as reduced fidelity)

plus the gate's own probe cost (_stage_exceeds at the candidate threshold).

Per-op envelope cost = 2x hash (scene_hash_before + scene_hash_after), which is
what shared/bridge.py pays on every stage-touching operation. Three stage
profiles, because the historical objection to a structural DEFAULT was
"can be SLOWER than Flatten on value-heavy stages":

  hierarchy    Xform/Sphere tree, ~4 small authored attrs per prim (typical
               scene-graph shape; prim count is the scaling axis)
  animated     same, but every 5th prim's attrs carry 24 time samples each
               (structural digests EVERY authored sample since the gap closure)
  value-heavy  same hierarchy plus a fixed payload of Mesh prims carrying
               ~400k points of array data total (tests repr-vs-USDA
               serialization cost independent of prim count)

Usage:  python scripts/probe_stage_hash_floor.py [--counts 100,10000,100000]
                                                 [--reps 5] [--threshold 20000]

Output: a table of median ms per algorithm per (profile, prim count), the
per-op (2x) envelope cost, and the flatten/structural ratio. The committed
default in shared/bridge.py cites the numbers this printed on the machine that
chose it — rerun it before retuning SYNAPSE_STAGE_HASH_PRIM_THRESHOLD.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from pxr import Sdf, Usd  # noqa: E402

from shared.bridge import LosslessExecutionBridge  # noqa: E402
from shared.constants import HASH_LENGTH  # noqa: E402


# ── stage builders ─────────────────────────────────────────────

def _add_attrs(prim, animated: bool) -> None:
    a = prim.CreateAttribute("scale", Sdf.ValueTypeNames.Double)
    a.Set(1.5)
    b = prim.CreateAttribute("intensity", Sdf.ValueTypeNames.Float)
    b.Set(0.75)
    c = prim.CreateAttribute("label", Sdf.ValueTypeNames.String)
    c.Set("probe")
    d = prim.CreateAttribute("radius", Sdf.ValueTypeNames.Double)
    if animated:
        for f in range(24):
            d.Set(1.0 + f * 0.1, Usd.TimeCode(float(f)))
    else:
        d.Set(1.0)


def build_stage(n_prims: int, profile: str) -> Usd.Stage:
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/root", "Xform")
    stage.SetDefaultPrim(root)
    # 16-wide groups keep the hierarchy shallow-but-real.
    group = None
    for i in range(n_prims):
        if i % 16 == 0:
            group = stage.DefinePrim(f"/root/g{i // 16}", "Xform")
        prim = stage.DefinePrim(f"{group.GetPath()}/p{i}", "Sphere")
        animated = profile == "animated" and (i % 5 == 0)
        _add_attrs(prim, animated)
    if profile == "value-heavy":
        # Fixed array payload (~400k points across 4 meshes) independent of
        # prim count — isolates big-array serialization cost.
        from pxr import Vt
        pts = Vt.Vec3fArray([(float(j), float(j) * 0.5, 0.0)
                             for j in range(100_000)])
        for m in range(4):
            mesh = stage.DefinePrim(f"/root/mesh{m}", "Mesh")
            mesh.CreateAttribute("points", Sdf.ValueTypeNames.Point3fArray).Set(pts)
    return stage


# ── timed subjects ─────────────────────────────────────────────

def t_flatten(stage) -> str:
    flat = stage.Flatten().ExportToString()
    return hashlib.sha256(flat.encode("utf-8")).hexdigest()[:HASH_LENGTH]


def _median_ms(fn, reps: int) -> float:
    samples = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return statistics.median(samples)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--counts", default="100,10000,100000")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--threshold", type=int, default=20000,
                    help="candidate default threshold for the _stage_exceeds probe cost row")
    args = ap.parse_args()
    counts = [int(c) for c in args.counts.split(",")]

    bridge = LosslessExecutionBridge()
    print(f"pxr USD; reps={args.reps} (median); per-op = 2x hash "
          f"(before+after); probe threshold={args.threshold}")
    hdr = (f"{'profile':<12} {'prims':>7} {'flatten ms':>11} {'struct ms':>10} "
           f"{'reduced ms':>10} {'probe ms':>9} {'flat/red':>9} "
           f"{'per-op flat':>12} {'per-op red':>11}")
    print(hdr)
    print("-" * len(hdr))
    for profile in ("hierarchy", "animated", "value-heavy"):
        for n in counts:
            build_t0 = time.perf_counter()
            stage = build_stage(n, profile)
            build_s = time.perf_counter() - build_t0
            f_ms = _median_ms(lambda: t_flatten(stage), args.reps)
            s_ms = _median_ms(lambda: bridge._structural_stage_signature(stage),
                              args.reps)
            r_ms = _median_ms(lambda: bridge._reduced_stage_signature(stage),
                              args.reps)
            p_ms = _median_ms(lambda: bridge._stage_exceeds(stage, args.threshold),
                              args.reps)
            ratio = (f_ms / r_ms) if r_ms > 0 else float("inf")
            print(f"{profile:<12} {n:>7} {f_ms:>11.1f} {s_ms:>10.1f} "
                  f"{r_ms:>10.1f} {p_ms:>9.1f} {ratio:>9.1f} "
                  f"{2 * f_ms:>12.1f} {2 * r_ms:>11.1f}   (build {build_s:.1f}s)")


if __name__ == "__main__":
    main()
