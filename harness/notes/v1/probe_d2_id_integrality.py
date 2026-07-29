"""V1 / PROBE D2 — is the object-ID AOV actually a MASK? (Q2, the crux)

Probe D produced the ID part and then went red on the control that matters: the
values are NOT integral. 1382 distinct values from 3 spheres. husk logged the
reason on every frame:

    Pixel filter 'minmax' - Mode idcover requires PrimId channel

harness/notes/perception_truth_22.0.368.json item 1 recorded that same message as
a "nonfatal_warning ... EXR + primid AOV still written" and stopped there. It is
not nonfatal for this harness: an ID plane whose values are blended across prim
boundaries is not an identity, and mask(X) built from it is wrong at exactly the
pixels a leak test cares about -- the edges.

This probe asks the actionable question instead of the binary one:
  * what FRACTION of pixels carry an integral id under each filter setting?
  * does any primidfilter spelling produce a fully integral plane?
  * are the non-integral pixels confined to prim boundaries (recoverable by
    erosion) or scattered (not recoverable)?

Controls (Law 1):
  positive  every case must render a file with a primid part, else that case is
            UNVERIFIABLE rather than a filter verdict.
  negative  the beauty plane C must NOT be integral. If the integrality test
            reports the CONTINUOUS beauty plane as integral, the test cannot
            disagree and every "integral" verdict here is worthless.
  FAILS IF  no case rendered, or the beauty-plane negative control reads integral.
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


def set_if(n, name, v):
    p = n.parm(name)
    if p is None:
        return False
    try:
        p.set(v)
        return True
    except Exception:
        return False


def build(primidfilter, samples, primid=1):
    stage = hou.node("/stage")
    for c in stage.children():
        c.destroy()
    prev = None
    for i, tx in enumerate((-2.5, 0.0, 2.5)):
        s = stage.createNode("sphere", f"sphere{i}")
        set_if(s, "primpath", f"/scene/sphere{i}")
        set_if(s, "tx", tx)
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
    set_if(krs, "primid", primid)
    set_if(krs, "denoiser", "off")
    set_if(krs, "resolutionx", W)
    set_if(krs, "resolutiony", H)
    set_if(krs, "camera", "/scene/camera")
    set_if(krs, "samplesperpixel", samples)
    set_if(krs, "pathtracedsamples", samples)
    applied_filter = set_if(krs, "primidfilter", primidfilter) if primidfilter is not None else None
    rop = stage.createNode("usdrender_rop")
    rop.setInput(0, krs)
    set_if(rop, "trange", 0)
    set_if(rop, "renderer", "BRAY_HdKarma")
    return rop, applied_filter


def read_part(path, want):
    h = read_exr_header(path)
    idx = None
    for i, p in enumerate(h.parts):
        if (p.name or "").lower() == want:
            idx = i
            break
    if idx is None:
        return None, [p.name for p in h.parts]
    inp = oiio.ImageInput.open(path)
    if idx:
        inp.seek_subimage(idx, 0)
    spec = inp.spec()
    px = inp.read_image(oiio.FLOAT)
    inp.close()
    a = np.asarray(px, dtype=np.float64).reshape(spec.height, spec.width, spec.nchannels)
    return a, [p.name for p in h.parts]


def integrality(a):
    flat = a[..., 0].ravel()
    integral = np.isclose(flat, np.round(flat), atol=0.0, rtol=0.0)
    uniq = np.unique(flat)
    uniq_int = np.unique(np.round(flat[integral]))
    return {
        "pixels": int(flat.size),
        "integral_pixels": int(integral.sum()),
        "integral_fraction": round(float(integral.mean()), 6),
        "distinct_values": int(uniq.size),
        "distinct_integral_values": int(uniq_int.size),
        "integral_values_sample": [float(x) for x in uniq_int[:24]],
        "min": float(flat.min()), "max": float(flat.max()),
    }


def edge_confined(a):
    """Are non-integral pixels adjacent to a change in the rounded id?

    If yes they are prim boundaries -> recoverable by eroding the mask. If no they
    are scattered through prim interiors -> the id is not a usable identity.
    """
    p = a[..., 0]
    r = np.round(p)
    frac = ~np.isclose(p, r, atol=0.0, rtol=0.0)
    if frac.sum() == 0:
        return {"non_integral_pixels": 0, "on_boundary_fraction": None}
    dx = np.zeros_like(r, dtype=bool)
    dy = np.zeros_like(r, dtype=bool)
    dx[:, :-1] |= (r[:, :-1] != r[:, 1:])
    dx[:, 1:] |= (r[:, :-1] != r[:, 1:])
    dy[:-1, :] |= (r[:-1, :] != r[1:, :])
    dy[1:, :] |= (r[:-1, :] != r[1:, :])
    boundary = dx | dy
    return {
        "non_integral_pixels": int(frac.sum()),
        "on_boundary_fraction": round(float((frac & boundary).sum() / frac.sum()), 6),
        "interpretation": ("boundary-confined => mask recoverable by erosion"
                           if (frac & boundary).sum() / frac.sum() > 0.95
                           else "scattered into prim interiors => not a usable identity"),
    }


R = {
    "probe": "V1/D2 object-ID AOV integrality under primidfilter variants",
    "producer": "harness/notes/v1/probe_d2_id_integrality.py",
    "build": str(hou.applicationVersionString()),
    "license_category": str(hou.licenseCategory()),
    "resolution": [W, H],
    "cases": [],
    "controls": {},
}

CASES = [
    ("default_idcover_s16", '["minmax",{"mode":"idcover"}]', 16),
    ("minmax_max_s16", '["minmax",{"mode":"max"}]', 16),
    ("minmax_min_s16", '["minmax",{"mode":"min"}]', 16),
    ("box_s16", '["box"]', 16),
    ("default_idcover_s1", '["minmax",{"mode":"idcover"}]', 1),
    ("minmax_max_s1", '["minmax",{"mode":"max"}]', 1),
]

for tag, filt, samples in CASES:
    out = os.path.join(SCRATCH, f"v1d2_{tag}.exr")
    if os.path.exists(out):
        os.remove(out)
    e = {"tag": tag, "primidfilter": filt, "samples": samples, "output": out}
    try:
        rop, applied = build(filt, samples)
        set_if(rop, "outputimage", out)
        e["filter_parm_set"] = applied
        t0 = time.perf_counter()
        rop.render(verbose=False)
        while not os.path.exists(out) and time.perf_counter() - t0 < 180:
            time.sleep(0.05)
        e["wall_seconds"] = round(time.perf_counter() - t0, 4)
        e["file_exists"] = os.path.exists(out)
        if e["file_exists"]:
            a, parts = read_part(out, "primid")
            e["parts"] = parts
            if a is None:
                e["verdict"] = "NO_PRIMID_PART"
            else:
                e["integrality"] = integrality(a)
                e["edges"] = edge_confined(a)
                e["verdict"] = ("FULLY_INTEGRAL"
                                if e["integrality"]["integral_fraction"] == 1.0
                                else "BLENDED")
    except Exception:
        e["error"] = traceback.format_exc()[-1500:]
    R["cases"].append(e)

# negative control: the CONTINUOUS beauty plane must not read as integral
try:
    first = next(c for c in R["cases"] if c.get("file_exists"))
    beauty, _ = read_part(first["output"], "c")
    if beauty is None:
        h = read_exr_header(first["output"])
        beauty, _ = read_part(first["output"], (h.parts[0].name or "").lower())
    R["controls"]["beauty_integrality"] = integrality(beauty)
    R["controls"]["negative_ok"] = (
        R["controls"]["beauty_integrality"]["integral_fraction"] < 0.99
    )
except Exception:
    R["controls"]["negative_ok"] = None
    R["controls"]["negative_error"] = traceback.format_exc()[-800:]

R["controls"]["any_case_rendered"] = any(c.get("file_exists") for c in R["cases"])
R["controls"]["controls_ok"] = bool(
    R["controls"]["any_case_rendered"] and R["controls"].get("negative_ok"))
R["controls"]["stated_failure_condition"] = (
    "controls_ok is false if no case rendered (every filter verdict UNVERIFIABLE), "
    "or if the CONTINUOUS beauty plane read as integral -- which would prove the "
    "integrality test cannot disagree and every verdict here is a decoration."
)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(f"controls_ok={R['controls']['controls_ok']} negative_ok={R['controls'].get('negative_ok')} "
      f"beauty_integral_frac={R['controls'].get('beauty_integrality',{}).get('integral_fraction')}")
for c in R["cases"]:
    i = c.get("integrality", {})
    ed = c.get("edges", {})
    print(f"  {c['tag']:22} {c.get('verdict','ERR'):15} int_frac={i.get('integral_fraction')} "
          f"distinct_int={i.get('distinct_integral_values')} max={i.get('max')} "
          f"on_boundary={ed.get('on_boundary_fraction')} wall={c.get('wall_seconds')}s")
print(f"wrote {OUT}")
