"""V1 / PROBE E2 — the per-object id question, asked with the RIGHT parm names.

Probe E asked whether `ray:objectid` can be emitted, guessed the extrarendervars
multiparm instance names, and recorded `extravar_parms_applied: [{}]` -- NOTHING
APPLIED. Its NO_SUCH_PART result was therefore UNVERIFIABLE, not ABSENT: the probe
never authored the render var it claimed to test. That is R50's exact failure mode
(five ABSENT verdicts in H3a were artifacts of asking the wrong class) and it was
caught only because the probe recorded what it actually set instead of assuming.

The real instance parm names, discovered by diffing the parm list before and after
extrarendervars=1:
    name1  sourceName1  sourceType1  dataType1  format1  filter1  enable1
with sourceType1 menu = raw|primvar|lpe|intrinsic, dataType1 default color3f,
format1 default float, filter1 default ["ubox",{}].

THE ORACLE, unchanged: two spheres, footprints non-empty and disjoint. A per-object
id gives exactly ONE distinct value inside each footprint, and the two differ.

Controls (Law 1):
  authoring  every case records the parms it ACTUALLY set. A case that authored
             nothing is UNVERIFIABLE and may not produce an ABSENT verdict.
  negative   `primid` runs through the SAME oracle and MUST FAIL it (D4 proved it
             collides). An oracle that passes primid cannot discriminate.
  positive   a control var with sourceName=Ci (a name Karma certainly knows) must
             actually produce an extra part -- proving the extrarendervars
             mechanism works at all before any absence is claimed of objectid.
  FAILS IF   nothing was authored, primid passes the oracle, or the mechanism
             control produces no extra part.
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

LEFT, RIGHT = (-1.5, 0.0), (1.5, 0.0)
RES = (320, 240)
CLEAN = '["minmax",{"mode":"max"}]'


def si(n, k, v):
    p = n.parm(k)
    if p is None:
        return False
    try:
        p.set(v)
        return True
    except Exception:
        return False


def scene(positions, toggles=None, evars=None):
    stage = hou.node("/stage")
    for c in stage.children():
        c.destroy()
    prev = None
    for i, (tx, ty) in enumerate(positions):
        s = stage.createNode("sphere", f"sphere{i}")
        si(s, "primpath", f"/scene/sphere{i}")
        si(s, "tx", tx)
        si(s, "ty", ty)
        if prev:
            s.setInput(0, prev)
        prev = s
    lg = stage.createNode("distantlight")
    si(lg, "primpath", "/scene/light")
    lg.setInput(0, prev)
    cam = stage.createNode("camera")
    si(cam, "primpath", "/scene/camera")
    si(cam, "tz", 14.0)
    cam.setInput(0, lg)
    k = stage.createNode("karmarendersettings")
    k.setInput(0, cam)
    si(k, "denoiser", "off")
    si(k, "res_mode", "manual")
    si(k, "resolutionx", RES[0])
    si(k, "resolutiony", RES[1])
    si(k, "camera", "/scene/camera")
    si(k, "samplesperpixel", 16)
    for nm, v in (toggles or {}).items():
        si(k, nm, v)
    applied = []
    if evars:
        si(k, "extrarendervars", len(evars))
        for i, spec in enumerate(evars, start=1):
            got = {}
            for base, val in spec.items():
                pn = f"{base}{i}"
                got[pn] = val if si(k, pn, val) else "FAILED_TO_SET"
            # read back what the node actually holds -- never trust the write
            got["_readback"] = {f"{b}{i}": (k.parm(f"{b}{i}").eval()
                                            if k.parm(f"{b}{i}") else None)
                                for b in ("name", "sourceName", "sourceType",
                                          "dataType", "format", "filter", "enable")}
            applied.append(got)
    rop = stage.createNode("usdrender_rop")
    rop.setInput(0, k)
    si(rop, "trange", 0)
    si(rop, "renderer", "BRAY_HdKarma")
    return k, rop, applied


def render(tag, positions, toggles=None, evars=None):
    out = os.path.join(SCRATCH, f"v1e2_{tag}.exr")
    if os.path.exists(out):
        os.remove(out)
    k, rop, ap = scene(positions, toggles, evars)
    si(rop, "outputimage", out)
    t0 = time.perf_counter()
    err = None
    try:
        rop.render(verbose=False)
    except Exception as exc:
        err = repr(exc)[:300]
    while not os.path.exists(out) and time.perf_counter() - t0 < 240:
        time.sleep(0.05)
    return out, round(time.perf_counter() - t0, 3), ap, err


def part_names(p):
    return [q.name for q in read_exr_header(p).parts] if os.path.exists(p) else []


def plane(p, name):
    h = read_exr_header(p)
    i = next((j for j, q in enumerate(h.parts)
              if (q.name or "").lower() == name.lower()), None)
    if i is None:
        return None
    inp = oiio.ImageInput.open(p)
    if i:
        inp.seek_subimage(i, 0)
    sp = inp.spec()
    px = inp.read_image(oiio.FLOAT)
    inp.close()
    return np.asarray(px, dtype=np.float64).reshape(
        sp.height, sp.width, sp.nchannels)[..., 0]


R = {
    "probe": "V1/E2 per-object integer id, authored with the discovered parm names",
    "producer": "harness/notes/v1/probe_e2_objectid_correct.py",
    "build": str(hou.applicationVersionString()),
    "multiparm_instance_names": ["name#", "sourceName#", "sourceType#", "dataType#",
                                 "format#", "filter#", "enable#"],
    "footprints": {}, "candidates": [], "controls": {},
}

def V(name, source, dtype="int", fmt="int32", filt=CLEAN):
    return {"name": name, "sourceName": source, "sourceType": "raw",
            "dataType": dtype, "format": fmt, "filter": filt, "enable": 1}

CANDIDATES = [
    {"tag": "primid_NEGATIVE_CONTROL", "look_for": ["primid"],
     "toggles": {"primid": 1, "primidfilter": CLEAN}, "evars": None,
     "role": "NEGATIVE CONTROL - D4 proved primid collides; MUST fail the oracle"},
    {"tag": "mechanism_control_Ci", "look_for": ["mechcheck", "Ci"],
     "toggles": {}, "evars": [V("mechcheck", "Ci", "color3f", "float", '["ubox",{}]')],
     "role": "POSITIVE CONTROL on the mechanism - Ci is a name Karma certainly "
             "knows; if THIS produces no extra part, extrarendervars does not work "
             "and no absence claim about objectid is licensed"},
    {"tag": "objectid_plain", "look_for": ["objectid"], "toggles": {},
     "evars": [V("objectid", "objectid")], "role": "ray:objectid, plain spelling"},
    {"tag": "objectid_ray_prefixed", "look_for": ["objectid"], "toggles": {},
     "evars": [V("objectid", "ray:objectid")], "role": "ray-prefixed spelling"},
    {"tag": "objectid_intrinsic", "look_for": ["objectid"], "toggles": {},
     "evars": [dict(V("objectid", "objectid"), sourceType="intrinsic")],
     "role": "sourceType=intrinsic instead of raw"},
]

try:
    pl, _, _, _ = render("solo_left", [LEFT], {"primid": 1, "primidfilter": CLEAN})
    prr, _, _, _ = render("solo_right", [RIGHT], {"primid": 1, "primidfilter": CLEAN})
    L, Rp = plane(pl, "primid"), plane(prr, "primid")
    lc, rc = (L != 0), (Rp != 0)
    R["footprints"] = {"left_px": int(lc.sum()), "right_px": int(rc.sum()),
                       "overlap_px": int((lc & rc).sum()),
                       "nonempty_and_disjoint": bool(lc.sum() and rc.sum() and not (lc & rc).any())}

    for c in CANDIDATES:
        e = {"tag": c["tag"], "role": c["role"]}
        try:
            p, wall, ap, err = render(c["tag"], [LEFT, RIGHT], c["toggles"], c.get("evars"))
            e.update({"wall_seconds": wall, "render_error": err,
                      "parts": part_names(p), "authored": ap})
            e["authored_something"] = bool(ap is None or any(
                v != "FAILED_TO_SET" for a in ap for k_, v in a.items() if k_ != "_readback"))
            pl_ = None
            for nm in c["look_for"]:
                pl_ = plane(p, nm)
                if pl_ is not None:
                    e["found_part"] = nm
                    break
            if pl_ is None:
                e["verdict"] = ("NO_EXTRA_PART" if e["authored_something"]
                                else "UNVERIFIABLE_NOTHING_AUTHORED")
                e["note"] = ("the complete part list is recorded above, so this is a "
                             "read of the whole list, not a keyword miss"
                             if e["authored_something"] else
                             "no parm was actually set; no absence claim licensed (R50)")
            else:
                lv = set(np.unique(pl_[lc]).tolist())
                rv = set(np.unique(pl_[rc]).tolist())
                e.update({
                    "left_values": sorted(lv)[:12], "right_values": sorted(rv)[:12],
                    "left_distinct": len(lv), "right_distinct": len(rv),
                    "shared_values": len(lv & rv),
                    "all_integral": bool(np.all(np.unique(pl_) == np.round(np.unique(pl_)))),
                    "per_object_clean": bool(len(lv) == 1 and len(rv) == 1 and lv != rv),
                })
                e["verdict"] = "PER_OBJECT_ID" if e["per_object_clean"] else "NOT_PER_OBJECT"
        except Exception:
            e["verdict"] = "ERROR"
            e["error"] = traceback.format_exc()[-1200:]
        R["candidates"].append(e)
except Exception:
    R["error"] = traceback.format_exc()[-2000:]

neg = next((c for c in R["candidates"] if c["tag"].startswith("primid_")), {})
mech = next((c for c in R["candidates"] if c["tag"] == "mechanism_control_Ci"), {})
R["controls"] = {
    "footprints_nonempty_and_disjoint": R["footprints"].get("nonempty_and_disjoint"),
    "negative_control_primid_failed_oracle": neg.get("per_object_clean") is False,
    "mechanism_control_produced_extra_part": mech.get("verdict") not in
        (None, "NO_EXTRA_PART", "UNVERIFIABLE_NOTHING_AUTHORED", "ERROR"),
    "mechanism_control_parts": mech.get("parts"),
    "stated_failure_condition": (
        "controls_ok is false if the footprints were empty/overlapping, or primid "
        "PASSED the per-object oracle (an oracle that cannot reject a known-colliding "
        "id proves nothing), or the extrarendervars MECHANISM control (sourceName=Ci) "
        "produced no extra EXR part -- in which case the mechanism itself is not "
        "working and NO absence claim about objectid is licensed."
    ),
}
R["controls"]["controls_ok"] = bool(
    R["controls"]["footprints_nonempty_and_disjoint"]
    and R["controls"]["negative_control_primid_failed_oracle"]
    and R["controls"]["mechanism_control_produced_extra_part"])

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(f"controls_ok={R['controls']['controls_ok']} "
      f"disjoint={R['controls']['footprints_nonempty_and_disjoint']} "
      f"primid_failed={R['controls']['negative_control_primid_failed_oracle']} "
      f"mechanism_ok={R['controls']['mechanism_control_produced_extra_part']}")
for c in R["candidates"]:
    print(f"  {c['tag']:26} {c.get('verdict','?'):28} parts={c.get('parts')}")
    if c.get("left_distinct") is not None:
        print(f"      Ldistinct={c['left_distinct']} Rdistinct={c['right_distinct']} "
              f"shared={c['shared_values']} integral={c['all_integral']} "
              f"L={c['left_values'][:4]} R={c['right_values'][:4]}")
    if c.get("authored"):
        print(f"      readback={c['authored'][0].get('_readback')}")
print(f"wrote {OUT}")
