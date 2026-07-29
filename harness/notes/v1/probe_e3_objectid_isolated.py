"""V1 / PROBE E3 — objectid vs dataType: isolate the variable that actually failed.

E2 got the authoring right (readback confirms name1/sourceName1/sourceType1 were
really set) and all three objectid cases failed with hou.OperationFailed and no
file. But E2 changed TWO things at once relative to its working control:

    working control : sourceName=Ci        dataType=color3f  format=float
    failing cases   : sourceName=objectid  dataType=int      format=int32

So "objectid is not a valid render var source" is NOT licensed by that evidence --
the int/int32 pair is an equally good suspect. Concluding otherwise would be the
single-confound error the recon caught in the husk-on-Indie record, repeated here
by me.

A 2x2 isolates it:

    A  Ci        color3f/float   -> expected PASS (replicates the control)
    B  objectid  color3f/float   -> if PASS, objectid is FINE and int/int32 was the fault
    C  Ci        int/int32       -> if FAIL, int/int32 is the fault, independent of sourceName
    D  objectid  float/float     -> second read on objectid with a scalar type

Renders go through husk as a SUBPROCESS rather than rop.render(), for two reasons:
its stderr is capturable (rop.render() raises an opaque hou.OperationFailed and
the real message goes to the process console), and a subprocess can be bounded by
a timeout -- rop.render() cannot, which is why E2 spent 240s per failure waiting
for a file that a raised call was never going to produce.

Controls (Law 1):
  positive  case A must render. If the replication of the known-good control
            fails, the harness changed under us and nothing here is interpretable.
  negative  at least one case must FAIL. If every case passes, the probe cannot
            distinguish a working config from a broken one.
  FAILS IF  A fails, or all four pass.
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
LEFT, RIGHT = (-1.5, 0.0), (1.5, 0.0)
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


def export_usd(tag, var):
    """Author the scene + one extra render var, export the composed stage to USD."""
    stage = hou.node("/stage")
    for c in stage.children():
        c.destroy()
    prev = None
    for i, (tx, ty) in enumerate((LEFT, RIGHT)):
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
    si(k, "resolutionx", 320)
    si(k, "resolutiony", 240)
    si(k, "camera", "/scene/camera")
    si(k, "samplesperpixel", 16)
    si(k, "extrarendervars", 1)
    for base, val in var.items():
        si(k, f"{base}1", val)
    readback = {f"{b}1": (k.parm(f"{b}1").eval() if k.parm(f"{b}1") else None)
                for b in ("name", "sourceName", "sourceType", "dataType",
                          "format", "filter", "enable")}
    usd = os.path.join(SCRATCH, f"v1e3_{tag}.usd")
    k.stage().Export(usd)
    return usd, readback


def husk_render(tag, usd):
    exr = os.path.join(SCRATCH, f"v1e3_{tag}.exr")
    if os.path.exists(exr):
        os.remove(exr)
    cmd = [HUSK, "--make-output-path", "-o", exr, "-f", "1",
           "-R", "BRAY_HdKarma", usd]
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        rc, so, se = p.returncode, p.stdout or "", p.stderr or ""
        timed_out = False
    except subprocess.TimeoutExpired:
        rc, so, se, timed_out = None, "", "TIMEOUT after 180s", True
    return {
        "exr": exr, "returncode": rc, "timed_out": timed_out,
        "wall_seconds": round(time.perf_counter() - t0, 3),
        "file_written": os.path.exists(exr),
        "file_bytes": os.path.getsize(exr) if os.path.exists(exr) else 0,
        "stdout_tail": so[-900:], "stderr_tail": se[-900:],
    }


def parts_of(p):
    try:
        return [q.name for q in read_exr_header(p).parts]
    except Exception:
        return []


def plane(p, name):
    try:
        h = read_exr_header(p)
    except Exception:
        return None
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


CASES = [
    ("A_Ci_color3f", {"name": "probevar", "sourceName": "Ci", "sourceType": "raw",
                      "dataType": "color3f", "format": "float",
                      "filter": '["ubox",{}]', "enable": 1},
     "POSITIVE CONTROL - replicates E2's known-good config"),
    ("B_objectid_color3f", {"name": "probevar", "sourceName": "objectid",
                            "sourceType": "raw", "dataType": "color3f",
                            "format": "float", "filter": '["ubox",{}]', "enable": 1},
     "isolates sourceName: only the source differs from A"),
    ("C_Ci_int32", {"name": "probevar", "sourceName": "Ci", "sourceType": "raw",
                    "dataType": "int", "format": "int32",
                    "filter": CLEAN, "enable": 1},
     "isolates dataType/format: only the type differs from A"),
    ("D_objectid_float", {"name": "probevar", "sourceName": "objectid",
                          "sourceType": "raw", "dataType": "float",
                          "format": "float", "filter": CLEAN, "enable": 1},
     "second read on objectid with a scalar float type"),
]

R = {
    "probe": "V1/E3 isolate objectid vs dataType (2x2), husk driven as a bounded subprocess",
    "producer": "harness/notes/v1/probe_e3_objectid_isolated.py",
    "build": str(hou.applicationVersionString()),
    "license_category": str(hou.licenseCategory()),
    "why": ("E2 changed sourceName AND dataType/format together, so its objectid "
            "failure was confounded and licensed no conclusion about objectid."),
    "cases": [], "controls": {},
}

# footprints for the per-object oracle
try:
    fu, _ = export_usd("fp_left", {"name": "probevar", "sourceName": "Ci",
                                   "sourceType": "raw", "dataType": "color3f",
                                   "format": "float", "filter": '["ubox",{}]',
                                   "enable": 1})
except Exception:
    pass

for tag, var, role in CASES:
    e = {"tag": tag, "role": role, "requested": var}
    try:
        usd, readback = export_usd(tag, var)
        e["readback"] = readback
        e["usd_exported"] = os.path.exists(usd)
        res = husk_render(tag, usd)
        e.update(res)
        e["parts"] = parts_of(res["exr"]) if res["file_written"] else []
        e["extra_part_present"] = "probevar" in [p.lower() for p in e["parts"]]
        e["verdict"] = (
            "RENDER_FAILED" if not res["file_written"] else
            ("EXTRA_PART_EMITTED" if e["extra_part_present"] else "RENDERED_NO_EXTRA_PART"))
        if e["extra_part_present"]:
            pl_ = plane(res["exr"], "probevar")
            if pl_ is not None:
                u = np.unique(pl_)
                e["distinct_values"] = int(u.size)
                e["value_sample"] = [float(x) for x in u[:12]]
                e["all_integral"] = bool(np.all(u == np.round(u)))
    except Exception:
        e["verdict"] = "ERROR"
        e["error"] = traceback.format_exc()[-1200:]
    R["cases"].append(e)

A = next((c for c in R["cases"] if c["tag"] == "A_Ci_color3f"), {})
R["controls"] = {
    "positive_A_rendered": A.get("file_written") is True,
    "positive_A_emitted_extra_part": A.get("extra_part_present") is True,
    "at_least_one_case_failed": any(c.get("verdict") == "RENDER_FAILED" for c in R["cases"]),
    "stated_failure_condition": (
        "controls_ok is false if case A (the replication of the known-good config) "
        "did not render and emit its extra part -- nothing else would be "
        "interpretable -- or if EVERY case passed, which would mean the probe "
        "cannot tell a working config from a broken one."
    ),
}
R["controls"]["controls_ok"] = bool(
    R["controls"]["positive_A_rendered"]
    and R["controls"]["positive_A_emitted_extra_part"]
    and R["controls"]["at_least_one_case_failed"])

# the isolation read-off, stated explicitly so it is not inferred later
B = next((c for c in R["cases"] if c["tag"] == "B_objectid_color3f"), {})
C = next((c for c in R["cases"] if c["tag"] == "C_Ci_int32"), {})
R["isolation_verdict"] = {
    "A_Ci_color3f": A.get("verdict"),
    "B_objectid_color3f": B.get("verdict"),
    "C_Ci_int32": C.get("verdict"),
    "reads_as": (
        "objectid is the fault (B failed while C passed)"
        if B.get("verdict") == "RENDER_FAILED" and C.get("verdict") != "RENDER_FAILED"
        else "int/int32 is the fault (C failed while B passed)"
        if C.get("verdict") == "RENDER_FAILED" and B.get("verdict") != "RENDER_FAILED"
        else "BOTH failed - the two causes are not separable by this matrix alone"
        if B.get("verdict") == "RENDER_FAILED" and C.get("verdict") == "RENDER_FAILED"
        else "NEITHER failed - E2's failure was caused by something else entirely"),
}

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(f"controls_ok={R['controls']['controls_ok']}")
for c in R["cases"]:
    print(f"  {c['tag']:22} {c.get('verdict','?'):22} rc={c.get('returncode')} "
          f"bytes={c.get('file_bytes')} parts={c.get('parts')} wall={c.get('wall_seconds')}")
    st = (c.get("stderr_tail") or "").strip().replace("\n", " | ")
    if st:
        print(f"      stderr: {st[-320:]}")
print("ISOLATION:", json.dumps(R["isolation_verdict"], indent=1))
print(f"wrote {OUT}")
