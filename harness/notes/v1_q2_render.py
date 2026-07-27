"""V1 / Q2 + Q3 + Q4 — the crux. Does Karma emit a usable per-object integer ID
AOV; what does one capture cost; does the denoiser behave.

SCENE  harness/notes/v1_scene_two_spheres.usda
       two unit spheres separated in X, one dome light, one camera at z=+9.
       Trivial by design: Q3's cost number is only meaningful if the scene can
       be described in one sentence, and Q2's collision test needs two prims
       that are unambiguously different OBJECTS in disjoint screen regions.

CASES  (one render each, each writing its own EXR + its own timing)
  base        primid + element on, shipped defaults, denoiser off
  noise       byte-identical repeat of base -> determinism / V2's noise floor
  bare_names  custom render vars WITHOUT the ray: prefix   -> silent-zero test
  ray_names   the same vars WITH the ray: prefix           -> the control
  int_format  husk per-AOV format = int32                  -> is int refused?
  denoise_on  denoiser = oidn                              -> Q4 behaviour

Law 3: every parm set records what actually happened. A parm that does not
exist is reported ABSENT, never skipped silently. A case that raises records
the exception and the matrix continues.

Parm spellings come from harness/notes/v1_q2_parmdetail.json (a live dump), not
from memory.

Run:   hython3.13.exe harness/notes/v1_q2_render.py <outdir>
Emits: harness/notes/v1_q2_render.json  (+ EXRs under <outdir>)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import traceback

import hou

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v1_q2_render.json")
SCENE = os.path.join(HERE, "v1_scene_two_spheres.usda").replace("\\", "/")

OUTDIR = (sys.argv[1] if len(sys.argv) > 1
          else os.path.join(HERE, "_v1_out")).replace("\\", "/")
os.makedirs(OUTDIR, exist_ok=True)

RESX, RESY = 160, 120
SPP = 4                 # samplesperpixel
PTS = 16                # pathtracedsamples

REPORT = {
    "schema": "v1-q2-render/1",
    "build": hou.applicationVersionString(),
    "license": str(hou.licenseCategory()),
    "scene": SCENE,
    "outdir": OUTDIR,
    "config": {"resolution": [RESX, RESY], "samplesperpixel": SPP,
               "pathtracedsamples": PTS},
    "cases": {},
}


def flush():
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(REPORT, fh, indent=2)


def p(msg):
    print(msg, flush=True)


def setp(node, name, value, rec, required=True):
    """Set a parm and RECORD what happened (Law 3)."""
    parm = node.parm(name)
    if parm is None:
        rec.append({"parm": name, "status": "ABSENT", "wanted": value,
                    "required": required})
        p(f"      ! ABSENT parm {node.path()}.{name}")
        return False
    try:
        parm.set(value)
        rec.append({"parm": name, "status": "set", "wanted": value,
                    "readback": parm.eval()})
        return True
    except Exception as exc:  # noqa: BLE001
        rec.append({"parm": name, "status": "error", "wanted": value,
                    "error": f"{type(exc).__name__}: {exc}"})
        p(f"      ! SET FAILED {name}: {exc}")
        return False


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def karma_delegate():
    """The exact Karma CPU delegate string, read from the live menu."""
    st = hou.node("/stage")
    tmp = st.createNode("usdrender_rop", "_delegate_probe")
    try:
        items = list(tmp.parm("renderer").parmTemplate().menuItems())
        labels = list(tmp.parm("renderer").parmTemplate().menuLabels())
    finally:
        tmp.destroy()
    REPORT["renderer_menu"] = dict(zip(items, labels))
    for it in items:
        if "karma" in it.lower() and "xpu" not in it.lower():
            return it
    return None


def build(case, extra_vars, krs_over):
    """Fresh LOP network per case -- no state leaks between renders."""
    st = hou.node("/stage")
    for c in st.children():
        c.destroy()

    rec = []
    sub = st.createNode("sublayer", "scene")
    setp(sub, "filepath1", SCENE, rec)
    tail = sub

    for spec in extra_vars:
        rv = st.createNode("rendervar", spec["node"])
        rv.setInput(0, tail)
        setp(rv, "primpath", f"/Render/Products/Vars/{spec['node']}", rec)
        setp(rv, "sourceName", spec["sourceName"], rec)
        setp(rv, "sourceType", spec.get("sourceType", "raw"), rec)
        setp(rv, "dataType", spec.get("dataType", "float"), rec)
        if "huskformat" in spec:
            setp(rv, "xn__driverparametersaovhuskformat_control_c1bkde",
                 "set", rec)
            setp(rv, "xn__driverparametersaovhuskformat_bobkde",
                 spec["huskformat"], rec)
        tail = rv

    krs = st.createNode("karmarendersettings", "krs")
    krs.setInput(0, tail)
    setp(krs, "primid", True, rec)
    setp(krs, "element", True, rec)
    setp(krs, "resolutionx", RESX, rec)
    setp(krs, "resolutiony", RESY, rec)
    setp(krs, "camera", "/world/cam", rec)
    setp(krs, "engine", "cpu", rec)
    setp(krs, "samplesperpixel", SPP, rec)
    setp(krs, "pathtracedsamples", PTS, rec)
    for k, v in (krs_over or {}).items():
        setp(krs, k, v, rec)

    img = f"{OUTDIR}/{case}.exr"
    if os.path.exists(img):
        os.remove(img)

    rop = st.createNode("usdrender_rop", "render")
    rop.setInput(0, krs)
    setp(rop, "trange", 0, rec)
    setp(rop, "outputimage", img, rec)
    deleg = REPORT.get("karma_delegate")
    if deleg:
        setp(rop, "renderer", deleg, rec)
    return rop, img, rec


def run_case(case, extra_vars=(), krs_over=None):
    p(f"\n=== CASE {case} ===")
    entry = {"case": case, "extra_vars": list(extra_vars),
             "krs_over": krs_over or {}}
    try:
        rop, img, rec = build(case, list(extra_vars), krs_over)
        entry["parms"] = rec
        entry["is_RopNode"] = isinstance(rop, hou.RopNode)
        t0 = time.perf_counter()
        try:
            rop.render(verbose=False)
            entry["render_status"] = "returned"
        except Exception as exc:  # noqa: BLE001
            entry["render_status"] = "raised"
            entry["render_error"] = f"{type(exc).__name__}: {exc}"
            p(f"   render RAISED: {type(exc).__name__}: {exc}")
        entry["wall_seconds"] = round(time.perf_counter() - t0, 3)
        entry["output"] = img
        entry["output_exists"] = os.path.exists(img)
        if entry["output_exists"]:
            entry["output_bytes"] = os.path.getsize(img)
            entry["output_sha256"] = sha256(img)
        p(f"   status={entry['render_status']} "
          f"wall={entry['wall_seconds']}s exists={entry['output_exists']} "
          f"bytes={entry.get('output_bytes')}")
    except Exception:  # noqa: BLE001
        entry["harness_error"] = traceback.format_exc()
        p("   HARNESS ERROR\n" + entry["harness_error"])
    REPORT["cases"][case] = entry
    flush()
    return entry


def main() -> int:
    hou.hipFile.clear(suppress_save_prompt=True)
    REPORT["karma_delegate"] = karma_delegate()
    p(f"karma delegate -> {REPORT['karma_delegate']}")
    p(f"renderer menu  -> {REPORT.get('renderer_menu')}")
    flush()

    # 1. the shipped path
    run_case("base")
    # 2. determinism / noise floor -- identical inputs, second render
    run_case("noise")
    # 3. silent-zero test: custom vars with BARE names (no ray: prefix)
    run_case("bare_names", extra_vars=[
        {"node": "bare_objectid", "sourceName": "objectid", "dataType": "float"},
        {"node": "bare_primid", "sourceName": "primid", "dataType": "float"},
    ])
    # 4. the control: same vars, ray: prefixed
    run_case("ray_names", extra_vars=[
        {"node": "ray_objectid", "sourceName": "ray:objectid", "dataType": "float"},
        {"node": "ray_primid", "sourceName": "ray:primid", "dataType": "float"},
    ])
    # 5. is an integer AOV format accepted at all?
    run_case("int_format", extra_vars=[
        {"node": "int_objectid", "sourceName": "ray:objectid",
         "dataType": "int", "huskformat": "int32"},
    ])
    # 6. Q4: denoiser on
    run_case("denoise_on", krs_over={"denoiser": "oidn"})

    flush()
    p(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        REPORT["fatal"] = traceback.format_exc()
        flush()
        sys.exit(1)
