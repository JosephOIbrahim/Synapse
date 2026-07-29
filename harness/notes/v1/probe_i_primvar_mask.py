"""V1 / PROBE I — a per-object mask from a PRIMVAR, sidestepping Karma's id vocabulary.

Q2 came back negative on every Karma-supplied id: primid is per-polygon, element is
finer, ray:objectid returns one value for two distinct gprims at a magnitude float32
cannot hold exactly, and Karma refuses an integer AOV format outright.

But none of that constrains an id WE author. USD primvars are per-prim by
construction, and `rendervar.sourceType` offers `primvar` alongside `raw`. If a
constant float primvar authored per prim survives to an AOV, the harness gets a
mask whose vocabulary IT controls -- chosen small (1.0, 2.0, ...) so float32
exactness is never in question, which is the defect that sank ray:objectid.

THE ORACLE, identical to probe_f/probe_g so results are comparable: two spheres,
footprints proven non-empty and disjoint. A per-object id gives exactly ONE
non-zero value inside each footprint, and the two differ.

Controls (Law 1):
  positive   footprints non-empty and disjoint (measured with ray:primid, known good).
  negative   `ray:primid` runs the SAME oracle and MUST FAIL it -- proven to collide
             across objects. An oracle that passes primid cannot discriminate.
  zero-guard a plane that is ALL ZERO is a NON-ANSWER, never a verdict. Probe F
             established that an unrecognised source emits a silently-zero part,
             so this guard is mandatory, not decorative.
  exactness  the authored values are read back and compared EXACTLY (==), not
             within a tolerance. The whole point is an id that survives float32.
  FAILS IF   footprints empty/overlapping, or ray:primid passes the oracle, or the
             candidate plane is all zero.
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
CLEAN = '["minmax",{"mode":"max"}]'
LEFT, RIGHT = (-1.5, 0.0), (1.5, 0.0)
# Small, exactly-representable ids. The ray:objectid failure was a magnitude
# problem; choosing the vocabulary removes it entirely.
IDS = {0: 1.0, 1: 2.0}
PRIMVAR = "synapse_oid"


def si(n, k, v):
    p = n.parm(k)
    if p is None:
        return False
    try:
        p.set(v)
        return True
    except Exception:
        return False


def build(tag, positions, source, source_type, filt=CLEAN):
    """Two spheres, each carrying a DIFFERENT constant primvar value."""
    st = hou.node("/stage")
    for c in st.children():
        c.destroy()
    prev = None
    applied = []
    for i, (tx, ty) in enumerate(positions):
        s = st.createNode("sphere", f"sphere{i}")
        si(s, "primpath", f"/scene/sphere{i}")
        si(s, "tx", tx)
        si(s, "ty", ty)
        if prev:
            s.setInput(0, prev)
        prev = s
        # author the per-object primvar with a primitive LOP
        pv = st.createNode("primitive", f"pv{i}")
        pv.setInput(0, prev)
        si(pv, "primpattern", f"/scene/sphere{i}")
        n = si(pv, "num_primvars", 1) or si(pv, "primvars", 1)
        got = {}
        for base, val in (("primvars_name", PRIMVAR), ("primvars_type", "float"),
                          ("primvars_interpolation", "constant"),
                          ("primvars_value_float", IDS[i]),
                          ("primvars_value", IDS[i])):
            for pat in (f"{base}1", f"{base}_1", base):
                if si(pv, pat, val):
                    got[pat] = val
                    break
        applied.append({"prim": f"/scene/sphere{i}", "multiparm_set": bool(n), **got})
        prev = pv
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
    si(k, "denoiser", "off")
    si(k, "res_mode", "manual")
    si(k, "resolutionx", 320)
    si(k, "resolutiony", 240)
    si(k, "camera", "/scene/camera")
    si(k, "samplesperpixel", 16)
    si(k, "extrarendervars", 1)
    si(k, "name1", "pv")
    si(k, "sourceName1", source)
    si(k, "sourceType1", source_type)
    si(k, "dataType1", "float")
    si(k, "format1", "float")
    si(k, "filter1", filt)
    si(k, "enable1", 1)
    # verify the primvar actually landed on the composed stage
    stage_check = {}
    try:
        stg = k.stage()
        for i in range(len(positions)):
            pr = stg.GetPrimAtPath(f"/scene/sphere{i}")
            attr = pr.GetAttribute(f"primvars:{PRIMVAR}") if pr else None
            stage_check[f"sphere{i}"] = (
                None if attr is None or not attr
                else {"exists": True, "value": str(attr.Get())})
    except Exception as exc:
        stage_check["error"] = repr(exc)[:200]
    usd = os.path.join(SCRATCH, f"v1I_{tag}.usd")
    k.stage().Export(usd)
    return usd, applied, stage_check


def render(tag, usd):
    exr = os.path.join(SCRATCH, f"v1I_{tag}.exr")
    if os.path.exists(exr):
        os.remove(exr)
    t0 = time.perf_counter()
    p = subprocess.run([HUSK, "--make-output-path", "-o", exr, "-f", "1",
                        "-R", "BRAY_HdKarma", usd],
                       capture_output=True, text=True, timeout=300)
    return exr, round(time.perf_counter() - t0, 3), p.returncode, (p.stderr or "")[-400:]


def part(exr, name):
    if not os.path.exists(exr):
        return None
    h = read_exr_header(exr)
    i = next((j for j, q in enumerate(h.parts) if (q.name or "") == name), None)
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
    "probe": "V1/I per-object mask from an authored primvar",
    "producer": "harness/notes/v1/probe_i_primvar_mask.py",
    "build": str(hou.applicationVersionString()),
    "primvar": PRIMVAR, "authored_ids": IDS,
    "oracle": "exactly ONE non-zero value in each of two disjoint footprints, differing, and EXACTLY equal to the authored ids",
    "footprints": {}, "candidates": [], "controls": {},
}

try:
    # footprints via the known-good ray:primid
    ul, _, _ = build("fpL", [LEFT], "ray:primid", "raw")
    el, _, _, _ = render("fpL", ul)
    ur, _, _ = build("fpR", [RIGHT], "ray:primid", "raw")
    er, _, _, _ = render("fpR", ur)
    L, Rp = part(el, "pv"), part(er, "pv")
    lc, rc = (L != 0), (Rp != 0)
    R["footprints"] = {"left_px": int(lc.sum()), "right_px": int(rc.sum()),
                       "overlap_px": int((lc & rc).sum()),
                       "nonempty_and_disjoint": bool(lc.sum() and rc.sum() and not (lc & rc).any())}

    for tag, src, stype, role in (
        ("primid_NEGATIVE", "ray:primid", "raw",
         "NEGATIVE CONTROL - proven to collide across objects; MUST fail the oracle"),
        ("primvar_plain", PRIMVAR, "primvar", "the authored per-object primvar"),
        ("primvar_prefixed", f"primvars:{PRIMVAR}", "primvar", "same, namespace-qualified"),
        ("primvar_as_raw", PRIMVAR, "raw", "same name via sourceType=raw, for contrast"),
    ):
        e = {"tag": tag, "source": src, "source_type": stype, "role": role}
        try:
            usd, applied, stage_check = build(tag, [LEFT, RIGHT], src, stype)
            e["primvar_authoring"] = applied
            e["stage_check"] = stage_check
            exr, wall, rc_, err = render(tag, usd)
            e.update({"wall_seconds": wall, "returncode": rc_, "stderr": err.strip()[-300:],
                      "file_written": os.path.exists(exr)})
            pl = part(exr, "pv")
            if pl is None:
                e["verdict"] = "NO_PART"
            elif not (pl != 0).any():
                e["verdict"] = "ALL_ZERO_NON_ANSWER"
            else:
                lnz = sorted(x for x in set(np.unique(pl[lc]).tolist()) if x != 0)
                rnz = sorted(x for x in set(np.unique(pl[rc]).tolist()) if x != 0)
                clean = len(lnz) == 1 and len(rnz) == 1 and lnz[0] != rnz[0]
                e.update({
                    "left_values": [float(x) for x in lnz[:6]],
                    "right_values": [float(x) for x in rnz[:6]],
                    "left_nonzero_distinct": len(lnz), "right_nonzero_distinct": len(rnz),
                    "shared_nonzero": len(set(lnz) & set(rnz)),
                    "per_object_clean": bool(clean),
                    "matches_authored_ids_exactly": bool(
                        clean and {lnz[0], rnz[0]} == {IDS[0], IDS[1]}),
                    "max_value": float(np.unique(pl).max()),
                })
                e["verdict"] = "PER_OBJECT_ID" if clean else "NOT_PER_OBJECT"
        except Exception:
            e["verdict"] = "ERROR"
            e["error"] = traceback.format_exc()[-1000:]
        R["candidates"].append(e)
except Exception:
    R["error"] = traceback.format_exc()[-2000:]

neg = next((c for c in R["candidates"] if c["tag"] == "primid_NEGATIVE"), {})
R["controls"] = {
    "footprints_nonempty_and_disjoint": R["footprints"].get("nonempty_and_disjoint"),
    "negative_primid_failed_oracle": neg.get("per_object_clean") is False,
    "stated_failure_condition": (
        "controls_ok is false if the footprints were empty or overlapping, or if "
        "ray:primid PASSED the per-object oracle -- it is proven to collide across "
        "objects, so an oracle that accepts it cannot discriminate and every "
        "PER_OBJECT_ID verdict here would be worthless."),
}
R["controls"]["controls_ok"] = bool(
    R["controls"]["footprints_nonempty_and_disjoint"]
    and R["controls"]["negative_primid_failed_oracle"])

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(f"controls_ok={R['controls']['controls_ok']} "
      f"disjoint={R['controls']['footprints_nonempty_and_disjoint']} "
      f"primid_failed={R['controls']['negative_primid_failed_oracle']}")
print("footprints:", json.dumps(R["footprints"]))
for c in R["candidates"]:
    print(f"  {c['tag']:20} {c.get('verdict','?'):22} L={c.get('left_values')} R={c.get('right_values')} "
          f"exact={c.get('matches_authored_ids_exactly')}")
    print(f"      stage_check={json.dumps(c.get('stage_check'))}")
print(f"wrote {OUT}")
