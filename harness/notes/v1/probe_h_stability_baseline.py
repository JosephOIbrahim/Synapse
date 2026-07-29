"""V1 / PROBE H — the same-scene repeat baseline D4 never took. (Adversarial BLOCKER)

The hostile pass found a real defect and it is mine:

    D4 T2 rendered pair_base ONCE and pair_moved ONCE, then attributed all 18
    changed pixels inside the untouched left footprint to the mutation. It never
    established that two renders of the IDENTICAL pair scene give zero changed
    pixels at THIS camera distance with THESE parms. It imported that baseline
    from D3 S2 -- n=1, a DIFFERENT scene (3 spheres, tz=12, different filter).

That is R73 exactly: the oracle answered "did the plane change" when the question
was "did it change BECAUSE of the mutation". Until the same-scene repeat is
measured, "UNSTABLE" is not licensed and neither is "STABLE".

This probe takes the missing baseline, and takes it more than once so the answer
is not itself n=1.

  BASELINE   render the identical pair scene N times. Pairwise-compare every id
             plane. Any non-zero difference here is RENDER NONDETERMINISM and is
             the floor against which a mutation delta must be judged.
  MUTATION   render the moved scene N times too, then compare base-vs-moved.
  ATTRIBUTION the mutation-attributable delta inside the untouched footprint is
             (base-vs-moved change) MINUS (base-vs-base change). If the baseline
             already accounts for 18 px, the D4 claim collapses.

Controls (Law 1):
  positive   footprints non-empty and disjoint (measured, not assumed).
  negative   the comparator must report change inside the footprint of the object
             that provably MOVED. A comparator that finds change nowhere cannot
             disagree.
  self-check the baseline comparison and the mutation comparison use the SAME
             function, so a comparator that always says "identical" would show up
             as a mutation delta of zero -- caught by the negative control.
  FAILS IF   footprints empty/overlapping, or the comparator finds no change in
             the moved object's own footprint.
"""

from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
import time
import traceback

OUT, SCRATCH, REPO = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, REPO)

import hou  # noqa: E402
import numpy as np  # noqa: E402
import OpenImageIO as oiio  # noqa: E402

from retina.exr_header import read_exr_header  # noqa: E402

HUSK = r"C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\husk.exe"
CLEAN = '["minmax",{"mode":"max"}]'
LEFT, RIGHT, RIGHT_MOVED = (-1.5, 0.0), (1.5, 0.0), (1.5, 0.6)
N_REPEATS = 3


def si(n, k, v):
    p = n.parm(k)
    if p is None:
        return False
    try:
        p.set(v)
        return True
    except Exception:
        return False


def build_usd(tag, positions):
    """Identical authoring every time -- same parms, same order, same everything."""
    st = hou.node("/stage")
    for c in st.children():
        c.destroy()
    prev = None
    for i, (tx, ty) in enumerate(positions):
        s = st.createNode("sphere", f"sphere{i}")
        si(s, "primpath", f"/scene/sphere{i}")
        si(s, "tx", tx)
        si(s, "ty", ty)
        if prev:
            s.setInput(0, prev)
        prev = s
    lg = st.createNode("distantlight")
    si(lg, "primpath", "/scene/light")
    lg.setInput(0, prev)
    cam = st.createNode("camera")
    si(cam, "primpath", "/scene/camera")
    si(cam, "tz", 14.0)
    cam.setInput(0, lg)
    k = st.createNode("karmarendersettings")
    k.setInput(0, cam)
    si(k, "primid", 1)
    si(k, "primidfilter", CLEAN)
    si(k, "primidprecision", "float")
    si(k, "denoiser", "off")
    si(k, "res_mode", "manual")
    si(k, "resolutionx", 320)
    si(k, "resolutiony", 240)
    si(k, "camera", "/scene/camera")
    si(k, "samplesperpixel", 16)
    si(k, "pathtracedsamples", 16)
    usd = os.path.join(SCRATCH, f"v1H_{tag}.usd")
    k.stage().Export(usd)
    return usd


def render(tag, usd):
    exr = os.path.join(SCRATCH, f"v1H_{tag}.exr")
    if os.path.exists(exr):
        os.remove(exr)
    t0 = time.perf_counter()
    p = subprocess.run([HUSK, "--make-output-path", "-o", exr, "-f", "1",
                        "-R", "BRAY_HdKarma", usd],
                       capture_output=True, text=True, timeout=300)
    return exr, round(time.perf_counter() - t0, 3), p.returncode


def idp(exr):
    if not os.path.exists(exr):
        return None
    h = read_exr_header(exr)
    i = next((j for j, q in enumerate(h.parts) if (q.name or "") == "primid"), None)
    if i is None:
        return None
    inp = oiio.ImageInput.open(exr)
    if i:
        inp.seek_subimage(i, 0)
    sp = inp.spec()
    a = np.asarray(inp.read_image(oiio.FLOAT), dtype=np.float64)
    inp.close()
    return a.reshape(sp.height, sp.width, sp.nchannels)[..., 0]


R = {
    "probe": "V1/H same-scene repeat baseline for the ID plane (fixes the D4 T2 blocker)",
    "producer": "harness/notes/v1/probe_h_stability_baseline.py",
    "build": str(hou.applicationVersionString()),
    "why": ("D4 T2 attributed 18 changed pixels to a mutation without ever measuring "
            "the same-scene repeat floor for that scene. This measures it."),
    "n_repeats": N_REPEATS,
    "footprints": {}, "baseline": {}, "mutation": {}, "attribution": {}, "controls": {},
}

try:
    # footprints
    ul = build_usd("fpL", [LEFT])
    el, _, _ = render("fpL", ul)
    ur = build_usd("fpR", [RIGHT])
    er, _, _ = render("fpR", ur)
    L, Rp = idp(el), idp(er)
    lc, rc = (L != 0), (Rp != 0)
    R["footprints"] = {"left_px": int(lc.sum()), "right_px": int(rc.sum()),
                       "overlap_px": int((lc & rc).sum()),
                       "nonempty_and_disjoint": bool(lc.sum() and rc.sum() and not (lc & rc).any())}

    # BASELINE: the identical scene, N times
    base_usd = build_usd("base", [LEFT, RIGHT])
    base_planes, base_walls = [], []
    for i in range(N_REPEATS):
        e, w, _ = render(f"base_{i}", base_usd)
        base_planes.append(idp(e))
        base_walls.append(w)

    pairs = []
    for i, j in itertools.combinations(range(N_REPEATS), 2):
        a, b = base_planes[i], base_planes[j]
        d = a != b
        pairs.append({
            "pair": [i, j],
            "changed_px_whole_frame": int(d.sum()),
            "changed_px_inside_LEFT": int((d & lc).sum()),
            "changed_px_inside_RIGHT": int((d & rc).sum()),
            "identical": bool(not d.any()),
        })
    R["baseline"] = {
        "walls": base_walls, "pairwise": pairs,
        "max_changed_inside_LEFT": max(p["changed_px_inside_LEFT"] for p in pairs),
        "all_identical": all(p["identical"] for p in pairs),
        "note": ("this is RENDER NONDETERMINISM for this exact scene/parms. Any "
                 "mutation delta must exceed it to be attributable."),
    }

    # MUTATION: move only the right sphere
    mut_usd = build_usd("moved", [LEFT, RIGHT_MOVED])
    mut_planes, mut_walls = [], []
    for i in range(N_REPEATS):
        e, w, _ = render(f"moved_{i}", mut_usd)
        mut_planes.append(idp(e))
        mut_walls.append(w)

    cross = []
    for i in range(N_REPEATS):
        for j in range(N_REPEATS):
            d = base_planes[i] != mut_planes[j]
            cross.append({
                "base_i": i, "moved_j": j,
                "changed_px_whole_frame": int(d.sum()),
                "changed_px_inside_LEFT": int((d & lc).sum()),
                "changed_px_inside_RIGHT": int((d & rc).sum()),
            })
    R["mutation"] = {
        "walls": mut_walls, "cross": cross,
        "min_changed_inside_LEFT": min(c["changed_px_inside_LEFT"] for c in cross),
        "max_changed_inside_LEFT": max(c["changed_px_inside_LEFT"] for c in cross),
        "min_changed_inside_RIGHT": min(c["changed_px_inside_RIGHT"] for c in cross),
    }

    floor = R["baseline"]["max_changed_inside_LEFT"]
    lo = R["mutation"]["min_changed_inside_LEFT"]
    R["attribution"] = {
        "untouched_footprint_px": int(lc.sum()),
        "baseline_noise_px_inside_LEFT": floor,
        "mutation_change_px_inside_LEFT_min": lo,
        "excess_over_baseline": lo - floor,
        "verdict": (
            "NO EVIDENCE OF MUTATION-INDUCED ID INSTABILITY: the change inside the "
            "untouched footprint does not exceed the same-scene repeat floor"
            if lo <= floor else
            "MUTATION-ATTRIBUTABLE ID CHANGE inside an untouched object's footprint: "
            f"{lo - floor} px beyond the {floor}px same-scene floor"),
        "d4_claim_status": (
            "D4 T2's 'UNSTABLE' verdict is WITHDRAWN -- it had no same-scene baseline"
            if lo <= floor else
            "D4 T2's 'UNSTABLE' verdict SURVIVES, now with a measured baseline"),
    }
except Exception:
    R["error"] = traceback.format_exc()[-2000:]

R["controls"] = {
    "footprints_nonempty_and_disjoint": R["footprints"].get("nonempty_and_disjoint"),
    "comparator_saw_the_real_change": (R["mutation"].get("min_changed_inside_RIGHT") or 0) > 0,
    "stated_failure_condition": (
        "controls_ok is false if the footprints were empty or overlapping, or if the "
        "comparator found NO change inside the footprint of the sphere that provably "
        "moved -- a comparator that reports no change anywhere cannot disagree, and "
        "both the baseline and the attribution would be meaningless."),
}
R["controls"]["controls_ok"] = bool(
    R["controls"]["footprints_nonempty_and_disjoint"]
    and R["controls"]["comparator_saw_the_real_change"])

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(f"controls_ok={R['controls']['controls_ok']}")
print("footprints:", json.dumps(R["footprints"]))
print("BASELINE (same scene x%d):" % N_REPEATS)
for p in R["baseline"].get("pairwise", []):
    print("   ", json.dumps(p))
print("MUTATION (base vs moved):")
for c in R["mutation"].get("cross", [])[:9]:
    print("   ", json.dumps(c))
print("ATTRIBUTION:", json.dumps(R["attribution"], indent=1))
print(f"wrote {OUT}")
