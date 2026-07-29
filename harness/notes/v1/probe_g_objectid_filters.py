"""V1 / PROBE G — was ray:objectid's collapse the FILTER's fault?

Probe F, controls green, found ray:objectid gives ONE value per object footprint
(per-object granularity, unlike ray:primid's 50) but BOTH spheres carried the SAME
value 525459712 under filter ["minmax",{"mode":"max"}] -- a filter chosen for
primid, not for objectid. Under the default ["ubox",{}] an earlier sweep saw two
distinct clusters (~3.28e7 and ~3.50e7), which is what two objects should look
like.

So the collapse may be the filter, not the id. This sweeps the filter and applies
the same per-object oracle each time. Deciding this matters: it is the difference
between "a per-object mask exists on 22.0.368 with the right filter" and "no
per-object mask is available".

Controls (Law 1):
  positive  footprints non-empty and disjoint (measured with ray:primid, known good).
  negative  a plane that is ALL ZERO is a non-answer, never a verdict (an
            unrecognised source emits silent zeros -- Probe F's zero guard).
  oracle    per-object means exactly ONE non-zero value in each footprint, differing.
  FAILS IF  footprints empty/overlapping, or every case is all-zero.
"""

from __future__ import annotations

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


def si(n, k, v):
    p = n.parm(k)
    if p is None:
        return False
    try:
        p.set(v)
        return True
    except Exception:
        return False


def go(tag, xs, src, filt, samples=16):
    st = hou.node("/stage")
    for c in st.children():
        c.destroy()
    prev = None
    for i, tx in enumerate(xs):
        s = st.createNode("sphere", f"sphere{i}")
        si(s, "primpath", f"/scene/sphere{i}")
        si(s, "tx", tx)
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
    si(k, "denoiser", "off")
    si(k, "res_mode", "manual")
    si(k, "resolutionx", 320)
    si(k, "resolutiony", 240)
    si(k, "camera", "/scene/camera")
    si(k, "samplesperpixel", samples)
    si(k, "extrarendervars", 1)
    si(k, "name1", "pv")
    si(k, "sourceName1", src)
    si(k, "sourceType1", "raw")
    si(k, "filter1", filt)
    si(k, "enable1", 1)
    usd = os.path.join(SCRATCH, f"v1G_{tag}.usd")
    k.stage().Export(usd)
    exr = os.path.join(SCRATCH, f"v1G_{tag}.exr")
    if os.path.exists(exr):
        os.remove(exr)
    t0 = time.perf_counter()
    p = subprocess.run([HUSK, "--make-output-path", "-o", exr, "-f", "1",
                        "-R", "BRAY_HdKarma", usd],
                       capture_output=True, text=True, timeout=300)
    wall = round(time.perf_counter() - t0, 3)
    if not os.path.exists(exr):
        return None, wall, p.returncode, (p.stderr or "")[-300:]
    h = read_exr_header(exr)
    i = next((j for j, q in enumerate(h.parts) if q.name == "pv"), None)
    if i is None:
        return None, wall, p.returncode, "no pv part"
    inp = oiio.ImageInput.open(exr)
    if i:
        inp.seek_subimage(i, 0)
    sp = inp.spec()
    a = np.asarray(inp.read_image(oiio.FLOAT), dtype=np.float64)
    inp.close()
    return a.reshape(sp.height, sp.width, sp.nchannels)[..., 0], wall, p.returncode, ""


FILTERS = [
    ("ubox", '["ubox",{}]'),
    ("minmax_min", '["minmax",{"mode":"min"}]'),
    ("minmax_max", '["minmax",{"mode":"max"}]'),
    ("minmax_zmin", '["minmax",{"mode":"zmin"}]'),
    ("minmax_zmax", '["minmax",{"mode":"zmax"}]'),
]

R = {
    "probe": "V1/G ray:objectid per-object oracle across pixel-filter settings",
    "producer": "harness/notes/v1/probe_g_objectid_filters.py",
    "build": str(hou.applicationVersionString()),
    "oracle": "exactly ONE non-zero value in each of two disjoint footprints, differing",
    "cases": [], "controls": {},
}

try:
    Lp, _, _, _ = go("fpL", (-1.5,), "ray:primid", '["minmax",{"mode":"max"}]')
    Rp, _, _, _ = go("fpR", (1.5,), "ray:primid", '["minmax",{"mode":"max"}]')
    lc, rc = (Lp != 0), (Rp != 0)
    R["footprints"] = {"left_px": int(lc.sum()), "right_px": int(rc.sum()),
                       "overlap_px": int((lc & rc).sum()),
                       "nonempty_and_disjoint": bool(lc.sum() and rc.sum() and not (lc & rc).any())}

    for name, filt in FILTERS:
        e = {"filter_name": name, "filter": filt}
        try:
            pl, wall, rc_, err = go(f"oid_{name}", (-1.5, 1.5), "ray:objectid", filt)
            e.update({"wall_seconds": wall, "returncode": rc_, "stderr": err})
            if pl is None:
                e["verdict"] = "RENDER_FAILED"
            elif not (pl != 0).any():
                e["verdict"] = "ALL_ZERO_NON_ANSWER"
            else:
                lnz = sorted(x for x in set(np.unique(pl[lc]).tolist()) if x != 0)
                rnz = sorted(x for x in set(np.unique(pl[rc]).tolist()) if x != 0)
                e.update({
                    "left_nonzero_distinct": len(lnz),
                    "right_nonzero_distinct": len(rnz),
                    "left_values": [float(x) for x in lnz[:5]],
                    "right_values": [float(x) for x in rnz[:5]],
                    "shared_nonzero": len(set(lnz) & set(rnz)),
                    "per_object_clean": bool(len(lnz) == 1 and len(rnz) == 1 and lnz[0] != rnz[0]),
                    "max_value": float(np.unique(pl).max()),
                    "all_integral": bool(np.all(np.unique(pl) == np.round(np.unique(pl)))),
                })
                e["verdict"] = "PER_OBJECT_ID" if e["per_object_clean"] else "NOT_PER_OBJECT"
        except Exception:
            e["verdict"] = "ERROR"
            e["error"] = traceback.format_exc()[-800:]
        R["cases"].append(e)
except Exception:
    R["error"] = traceback.format_exc()[-1500:]

R["controls"] = {
    "footprints_nonempty_and_disjoint": R.get("footprints", {}).get("nonempty_and_disjoint"),
    "not_every_case_all_zero": any(c.get("verdict") not in
                                   ("ALL_ZERO_NON_ANSWER", "RENDER_FAILED", "ERROR")
                                   for c in R["cases"]),
    "stated_failure_condition": (
        "controls_ok is false if the footprints were empty or overlapping (no oracle "
        "licensed), or if EVERY filter produced an all-zero plane -- in which case "
        "the sweep says nothing about ray:objectid and the correct verdict is "
        "UNVERIFIABLE, not a filter conclusion."),
}
R["controls"]["controls_ok"] = bool(
    R["controls"]["footprints_nonempty_and_disjoint"] and R["controls"]["not_every_case_all_zero"])

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(f"controls_ok={R['controls']['controls_ok']}")
print("footprints:", json.dumps(R.get("footprints", {})))
for c in R["cases"]:
    print(f"  {c['filter_name']:12} {c.get('verdict','?'):22} "
          f"Lnz={c.get('left_nonzero_distinct')} Rnz={c.get('right_nonzero_distinct')} "
          f"shared={c.get('shared_nonzero')} max={c.get('max_value')}")
    if c.get("left_values"):
        print(f"       L={[f'{x:.0f}' for x in c['left_values'][:3]]} "
              f"R={[f'{x:.0f}' for x in c['right_values'][:3]]}")
print(f"wrote {OUT}")
