"""V1 / PROBE D3 — what does primid IDENTIFY, and does it survive a mutation?

D2 settled that the ID plane can be made fully integral
(primidfilter=["minmax",{"mode":"max"}]). It also surfaced something the
integrality result hides: THREE spheres produced FIFTY-EIGHT distinct integral
ids. So primid is not "one integer per USD prim", and a mask built on the
assumption that it is would be wrong.

The blueprint names this exact failure: "Unstable IDs. Same prim, different frame
or different renderer -> same integer? Unknown, and already an open SideFX ask.
If IDs are unstable, the mask is wrong and every verdict is wrong."

Three questions, each decisive for whether V3's primitive can exist:
  S1  GRANULARITY  do ids scale with the number of OBJECTS, or with geometry?
                   render 1, 2, 3 spheres and count.
  S2  REPEATABILITY does an unchanged scene rendered twice give an IDENTICAL id
                   plane? If not, the mask is noise.
  S3  MUTATION STABILITY when ONE prim moves, do the OTHER prims keep their ids?
                   This is "I mutated X and only X changed" applied to the
                   instrument itself. If a mutation renumbers untouched prims,
                   every leak verdict V3 produces is fiction.

Controls (Law 1):
  positive  every case must render with a primid part, else UNVERIFIABLE.
  negative  S2's comparison must be able to report DIFFERENT: the S3 mutated
            render is compared with the same function, and it MUST differ from
            the baseline somewhere. A comparator that says "identical" for both
            an unchanged and a mutated scene cannot disagree and is worthless.
  FAILS IF  a case fails to render, or the comparator reports the mutated render
            identical to the baseline.
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

W, H = 320, 240
CLEAN_FILTER = '["minmax",{"mode":"max"}]'   # D2: the only spelling that is fully integral at 16spp


def set_if(n, name, v):
    p = n.parm(name)
    if p is None:
        return False
    try:
        p.set(v)
        return True
    except Exception:
        return False


def build(n_spheres, offsets=None, samples=16):
    stage = hou.node("/stage")
    for c in stage.children():
        c.destroy()
    offsets = offsets or [(-2.5, 0.0), (0.0, 0.0), (2.5, 0.0)][:n_spheres]
    prev = None
    for i, (tx, ty) in enumerate(offsets):
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
    set_if(cam, "tz", 12.0)
    cam.setInput(0, light)
    krs = stage.createNode("karmarendersettings")
    krs.setInput(0, cam)
    set_if(krs, "primid", 1)
    set_if(krs, "primidfilter", CLEAN_FILTER)
    set_if(krs, "primidprecision", "float")
    set_if(krs, "denoiser", "off")
    set_if(krs, "resolutionx", W)
    set_if(krs, "resolutiony", H)
    set_if(krs, "camera", "/scene/camera")
    set_if(krs, "samplesperpixel", samples)
    set_if(krs, "pathtracedsamples", samples)
    rop = stage.createNode("usdrender_rop")
    rop.setInput(0, krs)
    set_if(rop, "trange", 0)
    set_if(rop, "renderer", "BRAY_HdKarma")
    return rop


def render(tag, n_spheres, offsets=None, samples=16):
    out = os.path.join(SCRATCH, f"v1d3_{tag}.exr")
    if os.path.exists(out):
        os.remove(out)
    rop = build(n_spheres, offsets, samples)
    set_if(rop, "outputimage", out)
    t0 = time.perf_counter()
    rop.render(verbose=False)
    while not os.path.exists(out) and time.perf_counter() - t0 < 180:
        time.sleep(0.05)
    return out, round(time.perf_counter() - t0, 4)


def id_plane(path):
    h = read_exr_header(path)
    idx = next((i for i, p in enumerate(h.parts)
                if (p.name or "").lower() == "primid"), None)
    if idx is None:
        return None
    inp = oiio.ImageInput.open(path)
    if idx:
        inp.seek_subimage(idx, 0)
    spec = inp.spec()
    px = inp.read_image(oiio.FLOAT)
    inp.close()
    return np.asarray(px, dtype=np.float64).reshape(
        spec.height, spec.width, spec.nchannels)[..., 0]


def summarize(p):
    u = np.unique(p)
    nz = u[u != 0]
    return {
        "distinct_total": int(u.size),
        "distinct_nonzero": int(nz.size),
        "min": float(p.min()), "max": float(p.max()),
        "fully_integral": bool(np.all(u == np.round(u))),
        "values_sample": [float(x) for x in u[:30]],
    }


def compare(a, b):
    if a is None or b is None:
        return {"comparable": False}
    if a.shape != b.shape:
        return {"comparable": False, "shape_mismatch": [list(a.shape), list(b.shape)]}
    diff = a != b
    return {
        "comparable": True,
        "identical": bool(not diff.any()),
        "changed_pixels": int(diff.sum()),
        "changed_fraction": round(float(diff.mean()), 6),
    }


R = {
    "probe": "V1/D3 primid semantics: granularity, repeatability, mutation stability",
    "producer": "harness/notes/v1/probe_d3_id_semantics.py",
    "build": str(hou.applicationVersionString()),
    "primidfilter_used": CLEAN_FILTER,
    "resolution": [W, H],
    "S1_granularity": [],
    "S2_repeatability": {},
    "S3_mutation_stability": {},
    "controls": {},
}

try:
    # ---- S1: does id count scale with object count? ------------------------
    for n in (1, 2, 3):
        path, wall = render(f"gran{n}", n)
        p = id_plane(path)
        row = {"spheres": n, "wall_seconds": wall, "file": path,
               "rendered": os.path.exists(path)}
        row.update(summarize(p) if p is not None else {"no_primid_part": True})
        R["S1_granularity"].append(row)

    # ---- S2: unchanged scene, rendered twice -------------------------------
    p1, w1 = render("repeat_a", 3)
    p2, w2 = render("repeat_b", 3)
    a, b = id_plane(p1), id_plane(p2)
    R["S2_repeatability"] = {"wall_a": w1, "wall_b": w2, **compare(a, b)}

    # ---- S3: move ONE sphere; do the others keep their ids? ----------------
    BASE = [(-2.5, 0.0), (0.0, 0.0), (2.5, 0.0)]
    MUT = [(-2.5, 0.0), (0.0, 1.75), (2.5, 0.0)]   # only sphere1 moves, in Y
    pb, wb = render("mut_base", 3, BASE)
    pm, wm = render("mut_moved", 3, MUT)
    base, moved = id_plane(pb), id_plane(pm)
    R["S3_mutation_stability"] = {"wall_base": wb, "wall_moved": wm,
                                  "whole_plane": compare(base, moved)}
    if base is not None and moved is not None:
        base_ids = set(np.unique(base).tolist())
        moved_ids = set(np.unique(moved).tolist())
        R["S3_mutation_stability"]["id_set"] = {
            "base_count": len(base_ids), "moved_count": len(moved_ids),
            "preserved": len(base_ids & moved_ids),
            "lost": sorted(base_ids - moved_ids)[:20],
            "gained": sorted(moved_ids - base_ids)[:20],
            "id_vocabulary_identical": base_ids == moved_ids,
        }
        # The load-bearing test: restrict to the LEFT third of frame, which only
        # ever contains sphere0 -- an untouched prim. Its ids must not change.
        third = base.shape[1] // 3
        left_base, left_moved = base[:, :third], moved[:, :third]
        R["S3_mutation_stability"]["untouched_region_left_third"] = compare(
            left_base, left_moved)
        R["S3_mutation_stability"]["untouched_region_note"] = (
            "sphere0 sits at tx=-2.5 and never moves; sphere1 moves in Y only. If "
            "this region differs, an untouched prim's identity changed because a "
            "DIFFERENT prim moved -- which voids mask(X) for V3."
        )
except Exception:
    R["error"] = traceback.format_exc()[-2500:]

# ------------------------------------------------------------------ controls
s2 = R["S2_repeatability"]
s3 = R["S3_mutation_stability"].get("whole_plane", {})
R["controls"] = {
    "all_cases_rendered": all(r.get("rendered") for r in R["S1_granularity"]) and bool(s2.get("comparable")),
    "comparator_can_report_different": s3.get("identical") is False,
    "negative_detail": (
        "the SAME comparator that judged the unchanged pair must report the MUTATED "
        "pair as different. If it called both identical it cannot disagree (Law 1)."
    ),
    "stated_failure_condition": (
        "controls_ok is false if any case failed to render (verdicts UNVERIFIABLE), "
        "or if the comparator reported the mutated render identical to the baseline "
        "-- which would prove the comparator cannot detect change and every "
        "repeatability claim here is a decoration."
    ),
}
R["controls"]["controls_ok"] = bool(
    R["controls"]["all_cases_rendered"] and R["controls"]["comparator_can_report_different"])

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(f"controls_ok={R['controls']['controls_ok']} "
      f"comparator_can_differ={R['controls']['comparator_can_report_different']}")
print("S1 granularity (ids vs object count):")
for r in R["S1_granularity"]:
    print(f"   spheres={r['spheres']} distinct_nonzero={r.get('distinct_nonzero')} "
          f"max={r.get('max')} integral={r.get('fully_integral')} wall={r.get('wall_seconds')}s")
print("S2 repeatability (same scene twice):", json.dumps(s2))
print("S3 whole-plane after moving ONE sphere:", json.dumps(s3))
print("S3 untouched left third:", json.dumps(R["S3_mutation_stability"].get("untouched_region_left_third", {})))
print("S3 id vocabulary:", json.dumps(R["S3_mutation_stability"].get("id_set", {})))
print(f"wrote {OUT}")
