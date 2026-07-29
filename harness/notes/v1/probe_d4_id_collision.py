"""V1 / PROBE D4 (v2) — does primid IDENTIFY an object, and what does a capture cost?

D3 produced two results that must not be reported as-is:

  * 1 sphere -> 30 distinct ids, 2 -> 53, 3 -> 57, max ALWAYS 99. Sub-additive
    growth against a fixed ceiling is the signature of ids that COLLIDE between
    objects, not ids that enumerate them.
  * moving sphere1 changed 232 pixels in the "untouched left third" -- but that is
    evidence of instability ONLY IF sphere1 could not reach the left third, and at
    tx=-2.5/0/+2.5 it could. Reporting instability on that control would be R50's
    error one level up: a negative claim whose control does not license it.

v1 of this probe then made a WORSE mistake, and its own controls caught it: it
framed the spheres OUT OF VIEW (the Solaris camera LOP's default horizontal
aperture is ~20.955mm, so half-width at tz=14 is ~2.9 units, and tx=+-4 is
outside it). Every footprint was empty, which made "footprints_disjoint" pass
VACUOUSLY -- the exact D1-218/218 defect Law 1 names. Two fixes, both structural:

  * the scene is now SELF-VALIDATING: each solo render must produce a non-empty
    footprint or that case is UNVERIFIABLE and no verdict is drawn from it.
  * "disjoint" now REQUIRES both footprints to be non-empty. An empty set is
    disjoint from everything, and that must not read as success.

  T1 COLLISION  a sphere alone on the left, a sphere alone on the right. If the
                two id SETS intersect, one integer names two different objects and
                primid alone cannot address a prim.
  T2 ISOLATION  footprints proven non-empty AND disjoint, then move the right
                sphere and ask whether ANY pixel inside the left sphere's own
                measured footprint changed.
  T3 COST       one husk invocation, several resolutions and sample counts, to
                separate fixed startup from marginal pixel cost.

Controls (Law 1):
  positive   each solo render must yield a NON-EMPTY footprint.
  isolation  both footprints non-empty AND their intersection empty.
  negative   the comparator must report change inside the footprint of the object
             that provably moved. A comparator finding change nowhere cannot
             disagree, and every "stable" verdict would be worthless.
  FAILS IF   any footprint is empty, the footprints overlap, or the comparator
             finds no change where change certainly occurred.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback

OUT, SCRATCH, REPO = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, REPO)

import hou  # noqa: E402
import numpy as np  # noqa: E402
import OpenImageIO as oiio  # noqa: E402

from retina.exr_header import read_exr_header  # noqa: E402

CLEAN_FILTER = '["minmax",{"mode":"max"}]'
# Framing chosen against the MEASURED aperture, not an assumed one: half-width at
# tz=14 is ~2.9 units, so +-1.5 with radius-1 spheres leaves a 1-unit gap and sits
# comfortably inside frame. The probe still verifies this rather than trusting it.
LEFT = (-1.5, 0.0)
RIGHT = (1.5, 0.0)
RIGHT_MOVED = (1.5, 0.6)


def set_if(n, name, v):
    p = n.parm(name)
    if p is None:
        return False
    try:
        p.set(v)
        return True
    except Exception:
        return False


def build(positions, res=(320, 240), samples=16, frames=1):
    stage = hou.node("/stage")
    for c in stage.children():
        c.destroy()
    prev = None
    for i, (tx, ty) in enumerate(positions):
        s = stage.createNode("sphere", f"sphere{i}")
        set_if(s, "primpath", f"/scene/sphere{i}")
        set_if(s, "tx", tx)
        set_if(s, "ty", ty)
        if prev:
            s.setInput(0, prev)
        prev = s
    light = stage.createNode("distantlight")
    set_if(light, "primpath", "/scene/light")
    light.setInput(0, prev)
    cam = stage.createNode("camera")
    set_if(cam, "primpath", "/scene/camera")
    set_if(cam, "tz", 14.0)
    cam.setInput(0, light)
    krs = stage.createNode("karmarendersettings")
    krs.setInput(0, cam)
    set_if(krs, "primid", 1)
    set_if(krs, "primidfilter", CLEAN_FILTER)
    set_if(krs, "denoiser", "off")
    set_if(krs, "res_mode", "manual")
    set_if(krs, "resolutionx", res[0])
    set_if(krs, "resolutiony", res[1])
    set_if(krs, "camera", "/scene/camera")
    set_if(krs, "samplesperpixel", samples)
    set_if(krs, "pathtracedsamples", samples)
    rop = stage.createNode("usdrender_rop")
    rop.setInput(0, krs)
    set_if(rop, "trange", 0)
    set_if(rop, "renderer", "BRAY_HdKarma")
    return rop


def render(tag, positions, res=(320, 240), samples=16):
    out = os.path.join(SCRATCH, f"v1d4b_{tag}.exr")
    if os.path.exists(out):
        os.remove(out)
    rop = build(positions, res, samples)
    set_if(rop, "outputimage", out)
    t0 = time.perf_counter()
    rop.render(verbose=False)
    while not os.path.exists(out) and time.perf_counter() - t0 < 300:
        time.sleep(0.05)
    return out, round(time.perf_counter() - t0, 4)


def id_plane(path):
    h = read_exr_header(path)
    idx = next((i for i, p in enumerate(h.parts)
                if (p.name or "").lower() == "primid"), None)
    if idx is None:
        return None, None
    inp = oiio.ImageInput.open(path)
    if idx:
        inp.seek_subimage(idx, 0)
    spec = inp.spec()
    px = inp.read_image(oiio.FLOAT)
    inp.close()
    arr = np.asarray(px, dtype=np.float64).reshape(
        spec.height, spec.width, spec.nchannels)[..., 0]
    return arr, (spec.width, spec.height)


R = {
    "probe": "V1/D4v2 primid collision + isolation-controlled stability + capture cost",
    "producer": "harness/notes/v1/probe_d4_id_collision.py",
    "build": str(hou.applicationVersionString()),
    "license_category": str(hou.licenseCategory()),
    "primidfilter_used": CLEAN_FILTER,
    "framing_note": (
        "v1 of this probe framed the spheres out of view and its controls caught "
        "it. Positions are now inside the MEASURED aperture and every solo render "
        "must prove a non-empty footprint before any verdict is drawn."
    ),
    "T1_collision": {},
    "T2_isolation_stability": {},
    "T3_cost": [],
    "controls": {},
}

try:
    # ---------------- T1: do two separate objects share id values? ----------
    pl, wl = render("solo_left", [LEFT])
    pr, wr = render("solo_right", [RIGHT])
    L, dimL = id_plane(pl)
    Rp, dimR = id_plane(pr)
    lc, rc = (L != 0), (Rp != 0)
    lset = set(np.unique(L[lc]).tolist())
    rset = set(np.unique(Rp[rc]).tolist())

    R["T1_collision"] = {
        "rendered_dimensions": {"left": list(dimL), "right": list(dimR)},
        "left_footprint_px": int(lc.sum()),
        "right_footprint_px": int(rc.sum()),
        "footprints_nonempty": bool(lc.sum() > 0 and rc.sum() > 0),
        "left_ids_count": len(lset), "right_ids_count": len(rset),
        "shared_ids_count": len(lset & rset),
        "shared_ids_sample": sorted(lset & rset)[:20],
        "left_max": float(L.max()), "right_max": float(Rp.max()),
        "wall_left": wl, "wall_right": wr,
    }
    if lc.sum() and rc.sum():
        R["T1_collision"]["ids_globally_unique_per_object"] = len(lset & rset) == 0
        R["T1_collision"]["interpretation"] = (
            "ids COLLIDE across objects: the SAME integer appears on two different "
            "objects, so an integer alone does not name a prim -- a mask needs "
            "(id + something else), or a different render var"
            if len(lset & rset) > 0 else
            "ids are DISJOINT across these two objects: an integer addresses one object")
    else:
        R["T1_collision"]["interpretation"] = (
            "UNVERIFIABLE: a solo footprint was empty, so no collision claim is licensed")

    # ---------------- T2: isolation-controlled mutation stability -----------
    overlap = int((lc & rc).sum())
    disjoint = bool(overlap == 0 and lc.sum() > 0 and rc.sum() > 0)
    R["T2_isolation_stability"] = {
        "footprint_overlap_px": overlap,
        "footprints_disjoint_AND_nonempty": disjoint,
        "why_this_wording": (
            "an empty set is disjoint from everything; v1 passed this check "
            "vacuously on two empty footprints (Law 1)"),
    }
    if disjoint:
        pbase, wb = render("pair_base", [LEFT, RIGHT])
        pmut, wm = render("pair_moved", [LEFT, RIGHT_MOVED])
        base, _ = id_plane(pbase)
        mut, _ = id_plane(pmut)
        d = base != mut
        R["T2_isolation_stability"].update({
            "wall_base": wb, "wall_moved": wm,
            "changed_px_whole_frame": int(d.sum()),
            "changed_px_inside_LEFT_footprint": int((d & lc).sum()),
            "changed_px_inside_RIGHT_footprint": int((d & rc).sum()),
            "left_untouched": bool((d & lc).sum() == 0),
            "verdict": (
                "STABLE: moving the right object changed ZERO ids inside the "
                "untouched left object's own measured footprint"
                if (d & lc).sum() == 0 else
                "UNSTABLE: moving one object changed ids inside an UNTOUCHED "
                "object's own footprint -- mask(X) would be wrong for V3"),
        })
        R["controls"]["comparator_saw_the_real_change"] = bool((d & rc).sum() > 0)
    else:
        R["T2_isolation_stability"]["verdict"] = (
            "UNVERIFIABLE: footprints empty or overlapping; no stability claim licensed")
        R["controls"]["comparator_saw_the_real_change"] = None

    # ---------------- T3: what does ONE capture cost? -----------------------
    for res, samples in (((320, 240), 16), ((640, 480), 16), ((1280, 720), 16),
                         ((1920, 1080), 16), ((1920, 1080), 64), ((1920, 1080), 256)):
        p, w = render(f"cost_{res[0]}x{res[1]}_s{samples}", [LEFT, RIGHT], res, samples)
        plane, dim = id_plane(p)
        R["T3_cost"].append({
            "requested_resolution": list(res),
            "actual_resolution": list(dim) if dim else None,
            "samples": samples,
            "wall_seconds": w,
            "file_bytes": os.path.getsize(p) if os.path.exists(p) else 0,
            "id_footprint_px": int((plane != 0).sum()) if plane is not None else None,
        })
except Exception:
    R["error"] = traceback.format_exc()[-2500:]

R["controls"].update({
    "footprints_nonempty": R["T1_collision"].get("footprints_nonempty"),
    "footprints_disjoint_AND_nonempty": R["T2_isolation_stability"].get(
        "footprints_disjoint_AND_nonempty"),
    "stated_failure_condition": (
        "controls_ok is false if either solo footprint was EMPTY (the v1 defect: an "
        "out-of-frame scene makes every downstream verdict vacuous), or the "
        "footprints overlapped (no isolation claim licensed), or the comparator "
        "found no change inside the footprint of the object that provably moved."
    ),
})
R["controls"]["controls_ok"] = bool(
    R["controls"].get("footprints_nonempty")
    and R["controls"].get("footprints_disjoint_AND_nonempty")
    and R["controls"].get("comparator_saw_the_real_change"))

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(f"controls_ok={R['controls']['controls_ok']} nonempty={R['controls'].get('footprints_nonempty')} "
      f"disjoint={R['controls'].get('footprints_disjoint_AND_nonempty')} "
      f"comparator_saw_change={R['controls'].get('comparator_saw_the_real_change')}")
print("T1:", json.dumps({k: v for k, v in R["T1_collision"].items() if k != "shared_ids_sample"}))
print("T1 shared sample:", R["T1_collision"].get("shared_ids_sample"))
print("T2:", json.dumps(R["T2_isolation_stability"]))
print("T3 cost:")
for c in R["T3_cost"]:
    print("   ", json.dumps(c))
print(f"wrote {OUT}")
