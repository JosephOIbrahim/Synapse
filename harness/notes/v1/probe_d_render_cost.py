"""V1 / PROBE D — one capture, TIMED, with the ID plane verified as identity (Q2 + Q3).

Q3 is the deliverable nobody in this repository has produced. harness/notes/
perception_truth_22.0.368.json (RETINA.M1, 2026-07-17) establishes that husk
writes a multi-part EXR with a primid part on this build under an Indie licence --
but every timing figure in it is a RELATIVE offset between callbacks, not a
wall-clock cost for a capture. "A verification that costs 40 seconds is a
different product from one costing 0.4" and that number does not exist yet.

Q2's real question is NOT "does a part named primid appear". A part that exists
and is uniformly zero would pass that check and be useless. So this probe renders
THREE prims at known separations and asserts the ID plane carries THREE DISTINCT,
INTEGRAL values. That is identity, not presence.

Controls (Law 1 — state the condition under which this fails):
  positive   the render must produce a file with a beauty part. No file => every
             verdict below is UNVERIFIABLE, not ABSENT.
  identity   the primid plane must hold >= 3 distinct non-background values, and
             every value must be integral (v == round(v)). A float AOV that is
             not integral is not an object id.
  negative   a control render with primid=0 must produce NO primid part. Without
             it, "the part appeared" could be an artifact of husk always writing
             it, and the toggle claim would be untested.
  FAILS IF   no file is produced, or the ID plane has < 3 distinct values, or the
             values are non-integral, or the primid=0 control still emits the part.

All output goes to a scratch directory outside the repository. Reads the EXR back
through the repo's own committed retina/exr_header.py -- which also answers
"does retina/ingest.py's ID path know how to read what Karma actually writes".
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback

OUT = sys.argv[1]
SCRATCH = sys.argv[2]
REPO = sys.argv[3]

sys.path.insert(0, REPO)

import hou  # noqa: E402
import numpy as np  # noqa: E402

from retina.exr_header import read_exr_header  # noqa: E402

R = {
    "probe": "V1/D one capture timed + ID plane verified as identity",
    "producer": "harness/notes/v1/probe_d_render_cost.py",
    "build": str(hou.applicationVersionString()),
    "license_category": str(hou.licenseCategory()),
    "scene": {},
    "renders": [],
    "controls": {},
    "id_identity": {},
}


def set_if(node, name, value):
    p = node.parm(name)
    if p is not None:
        try:
            p.set(value)
            return True
        except Exception:
            return False
    return False


def build_scene(res_x, res_y, samples, primid_on, denoiser="off", engine="cpu"):
    """Three spheres at known separations, one light, one camera, Karma settings.

    Three prims is the point: the ID plane must be able to tell them apart.
    """
    stage = hou.node("/stage")
    for c in stage.children():
        c.destroy()

    spheres = []
    for i, tx in enumerate((-2.5, 0.0, 2.5)):
        s = stage.createNode("sphere", f"sphere{i}")
        set_if(s, "primpath", f"/scene/sphere{i}")
        set_if(s, "t", (tx, 0.0, 0.0))
        set_if(s, "tx", tx)
        if spheres:
            s.setInput(0, spheres[-1])
        spheres.append(s)
    last = spheres[-1]

    light = stage.createNode("distantlight")
    set_if(light, "primpath", "/scene/light")
    light.setInput(0, last)

    cam = stage.createNode("camera")
    set_if(cam, "primpath", "/scene/camera")
    set_if(cam, "tz", 12.0)
    cam.setInput(0, light)

    krs = stage.createNode("karmarendersettings")
    krs.setInput(0, cam)
    applied = {}
    applied["primid"] = set_if(krs, "primid", 1 if primid_on else 0)
    applied["denoiser"] = set_if(krs, "denoiser", denoiser)
    applied["engine"] = set_if(krs, "engine", engine)
    applied["resolutionx"] = set_if(krs, "resolutionx", res_x)
    applied["resolutiony"] = set_if(krs, "resolutiony", res_y)
    for rname in ("resolution1", "res1"):
        applied[rname] = set_if(krs, rname, res_x)
    for rname in ("resolution2", "res2"):
        applied[rname] = set_if(krs, rname, res_y)
    set_if(krs, "camera", "/scene/camera")
    # keep it cheap and deterministic
    for sname in ("samplesperpixel", "pathtracedsamples", "primarysamples"):
        applied[sname] = set_if(krs, sname, samples)
    for sname in ("varianceaa", "enablevariance", "usevariance"):
        set_if(krs, sname, 0)

    rop = stage.createNode("usdrender_rop")
    rop.setInput(0, krs)
    set_if(rop, "trange", 0)          # single frame
    set_if(rop, "renderer", "BRAY_HdKarma")
    return {"rop": rop, "krs": krs, "applied": applied,
            "sphere_paths": [f"/scene/sphere{i}" for i in range(3)]}


def render_once(tag, res_x, res_y, samples, primid_on, denoiser="off"):
    out_exr = os.path.join(SCRATCH, f"v1_{tag}.exr")
    for stale in (out_exr,):
        if os.path.exists(stale):
            os.remove(stale)
    entry = {"tag": tag, "resolution": [res_x, res_y], "samples": samples,
             "primid_requested": primid_on, "denoiser": denoiser,
             "output": out_exr}
    try:
        built = build_scene(res_x, res_y, samples, primid_on, denoiser)
        rop = built["rop"]
        set_if(rop, "outputimage", out_exr)
        entry["parms_applied"] = built["applied"]

        t0 = time.perf_counter()
        rop.render(verbose=False)
        entry["render_call_seconds"] = round(time.perf_counter() - t0, 4)

        # husk may be a subprocess; wait (bounded) for the file to actually land.
        t_wait0 = time.perf_counter()
        while not os.path.exists(out_exr) and time.perf_counter() - t_wait0 < 180:
            time.sleep(0.05)
        entry["wait_after_call_seconds"] = round(time.perf_counter() - t_wait0, 4)
        entry["total_wall_seconds"] = round(
            entry["render_call_seconds"] + entry["wait_after_call_seconds"], 4)
        entry["file_exists"] = os.path.exists(out_exr)
        entry["file_bytes"] = os.path.getsize(out_exr) if entry["file_exists"] else 0

        if entry["file_exists"]:
            h = read_exr_header(out_exr)
            entry["exr"] = {
                "multipart": h.multipart,
                "parts": [
                    {"name": p.name,
                     "channels": [{"name": c.name, "pixel_type": c.pixel_type}
                                  for c in p.channels]}
                    for p in h.parts
                ],
            }
            entry["part_names"] = [p.name for p in h.parts]
            entry["has_primid_part"] = any(
                (p.name or "").lower() == "primid" for p in h.parts)
            # what does the repo's own ingest locator say?
            try:
                from retina.ingest import find_id_subimage
                entry["retina_find_id_subimage"] = find_id_subimage(out_exr)
            except Exception as exc:
                entry["retina_find_id_subimage_error"] = repr(exc)[:200]
    except Exception:
        entry["error"] = traceback.format_exc()[-2500:]
    return entry


# ---------------------------------------------------------------- the renders
CASES = [
    ("id_320x240_s16", 320, 240, 16, True, "off"),
    ("id_640x480_s16", 640, 480, 16, True, "off"),
    ("id_1920x1080_s16", 1920, 1080, 16, True, "off"),
    ("noid_320x240_s16", 320, 240, 16, False, "off"),   # negative control
]
for tag, w, h_, s, pid, dn in CASES:
    R["renders"].append(render_once(tag, w, h_, s, pid, dn))

primary = next((r for r in R["renders"] if r["tag"] == "id_320x240_s16"), None)
control = next((r for r in R["renders"] if r["tag"] == "noid_320x240_s16"), None)

# ------------------------------------------------- Q2: identity, not presence
try:
    if primary and primary.get("file_exists") and primary.get("has_primid_part"):
        from retina.ingest import oiio_available
        R["id_identity"]["oiio_available_in_hython"] = oiio_available()
        idx = primary.get("retina_find_id_subimage")
        vals = None
        try:
            import OpenImageIO as oiio
            inp = oiio.ImageInput.open(primary["output"])
            if idx:
                inp.seek_subimage(idx, 0)
            px = inp.read_image(oiio.FLOAT)
            inp.close()
            vals = np.asarray(px, dtype=np.float64).ravel()
            R["id_identity"]["reader"] = "OpenImageIO"
        except Exception as exc:
            R["id_identity"]["oiio_error"] = repr(exc)[:300]
        if vals is not None:
            uniq = np.unique(vals)
            R["id_identity"].update({
                "subimage_index": idx,
                "unique_count": int(uniq.size),
                "unique_sample": [float(x) for x in uniq[:20]],
                "min": float(vals.min()), "max": float(vals.max()),
                "all_integral": bool(np.all(uniq == np.round(uniq))),
                "nonzero_unique_count": int(np.unique(vals[vals != 0]).size),
            })
except Exception:
    R["id_identity"]["error"] = traceback.format_exc()[-1500:]

# -------------------------------------------------------------------- controls
ident = R["id_identity"]
R["controls"] = {
    "render_produced_file": bool(primary and primary.get("file_exists")),
    "id_part_present": bool(primary and primary.get("has_primid_part")),
    "id_distinct_values_ge_3": (ident.get("nonzero_unique_count") or 0) >= 3,
    "id_values_integral": ident.get("all_integral"),
    "toggle_control_no_part_when_off": (
        (control.get("has_primid_part") is False) if control and control.get("file_exists") else None
    ),
    "stated_failure_condition": (
        "controls_ok is false if no file was produced (every verdict UNVERIFIABLE), "
        "or the ID plane carried fewer than 3 distinct non-zero values (presence "
        "without identity is useless for a mask), or those values were not integral "
        "(a non-integral float AOV is not an object id), or the primid=0 control "
        "still emitted a primid part (which would mean the toggle claim is untested "
        "and the part appears regardless)."
    ),
}
R["controls"]["controls_ok"] = bool(
    R["controls"]["render_produced_file"]
    and R["controls"]["id_part_present"]
    and R["controls"]["id_distinct_values_ge_3"]
    and R["controls"]["id_values_integral"]
    and R["controls"]["toggle_control_no_part_when_off"]
)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(json.dumps(R["controls"], indent=1))
for r in R["renders"]:
    print(f"  {r['tag']:20} file={r.get('file_exists')} bytes={r.get('file_bytes')} "
          f"wall={r.get('total_wall_seconds')}s parts={r.get('part_names')} "
          f"err={'YES' if 'error' in r else 'no'}")
print("ID identity:", json.dumps({k: v for k, v in ident.items() if k != 'unique_sample'}))
print(f"wrote {OUT}")
