"""V1 / Q3 cost curve + the controls the earlier phases owe.

Four phases, each answering something a previous phase left open:

A  COP CONTENT CONTROL. v1_q1_cop_readback proved the chain returns bytes of
   the right length, byte-identically, for all seven storage types. It did NOT
   prove the bytes track the IMAGE -- the buffer read back as all-1.0, which is
   also what a fixed default would look like. So: change the source, re-cook,
   re-read, and require the bytes to CHANGE and to match the new value. This is
   the second of the two verifications the brief demands for Copernicus.

B  INGEST CONTROL. v1_q2_ingest_check showed find_id_subimage() picks `element`
   over `primid` on a 3-part frame. Before that is stated as a defect it needs
   the R73 control: render with primid ONLY, and confirm the selection is
   correct there. That bounds the claim to its real precondition instead of
   broadening it.

C  COST CURVE. Q3 wants what one capture costs. One resolution is a data point,
   not a curve, and the per-render husk process spawn is a fixed overhead that
   only shows up when resolution varies.

D  FLIPBOOK HEADLESS. hou.SceneViewer.flipbook resolves as a symbol. Whether it
   RUNS without a GUI is a different claim (R50 / H3a-F5): if the class cannot
   be instantiated here, the verdict is UNVERIFIABLE, never ABSENT.

Run:   hython3.13.exe harness/notes/v1_q3_cost_and_controls.py <outdir>
Emits: harness/notes/v1_q3_cost_and_controls.json
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
import time
import traceback

import hou

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "v1_q3_cost_and_controls.json")
SCENE = os.path.join(HERE, "v1_scene_two_spheres.usda").replace("\\", "/")
OUTDIR = (sys.argv[1] if len(sys.argv) > 1
          else os.path.join(HERE, "_v1_out")).replace("\\", "/")
os.makedirs(OUTDIR, exist_ok=True)
sys.path.insert(0, REPO)

REPORT = {"schema": "v1-q3-cost-controls/1",
          "build": hou.applicationVersionString(),
          "license": str(hou.licenseCategory())}


def flush():
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(REPORT, fh, indent=2)


def p(m):
    print(m, flush=True)


# =====================================================================  A
def phase_a():
    p("\n===== A. COP content control =====")
    e = {}
    try:
        parent = hou.node("/obj").createNode("copnet", "_v1_copnet_a")
        node = parent.createNode("constant", "_v1_src")
        e["cop_node"] = node.path()
        e["parms"] = [q.name() for q in node.parms()]
        colour_parms = [q.name() for q in node.parms()
                        if "color" in q.name().lower() or "value" in q.name().lower()]
        e["colour_parms"] = colour_parms

        def read(ch=4):
            node.cook(force=True)
            lay = node.layer()
            b = lay.allBufferElements(hou.imageLayerStorageType.Float32, ch)
            n = min(len(b) // 4, 64)
            return b, struct.unpack(f"<{n}f", b[:n * 4])

        b0, v0 = read()
        e["before"] = {"sha256": hashlib.sha256(b0).hexdigest()[:32],
                       "first8": list(v0[:8])}

        # Drive the source to a value that cannot be confused with a default.
        target = 0.375
        applied = []
        for name in colour_parms:
            q = node.parm(name)
            if q is None:
                continue
            try:
                q.set(target)
                applied.append({"parm": name, "status": "set",
                                "readback": q.eval()})
            except Exception as exc:  # noqa: BLE001
                applied.append({"parm": name, "status": "error",
                                "error": str(exc)})
        e["applied"] = applied

        b1, v1 = read()
        e["after"] = {"sha256": hashlib.sha256(b1).hexdigest()[:32],
                      "first8": list(v1[:8])}
        e["bytes_changed"] = (b0 != b1)
        e["matches_target"] = any(abs(x - target) < 1e-5 for x in v1[:8])
        e["verdict"] = (
            "CONFIRMED: readback tracks the image"
            if e["bytes_changed"] and e["matches_target"]
            else "INCONCLUSIVE: buffer did not track the change")
        p(f"  before first8={e['before']['first8'][:4]} "
          f"after first8={e['after']['first8'][:4]}")
        p(f"  bytes_changed={e['bytes_changed']} "
          f"matches_target={e['matches_target']}")
        p(f"  -> {e['verdict']}")

        # Int32 readback of the same buffer -- the V2-relevant question.
        b32 = node.layer().allBufferElements(hou.imageLayerStorageType.Int32, 4)
        n = min(len(b32) // 4, 16)
        e["int32_first8"] = list(struct.unpack(f"<{n}i", b32[:n * 4]))[:8]
        e["int32_bytes"] = len(b32)
        p(f"  int32 readback bytes={len(b32)} first8={e['int32_first8']}")
    except Exception:  # noqa: BLE001
        e["error"] = traceback.format_exc()
        p(e["error"])
    REPORT["A_cop_content"] = e
    flush()


# =====================================================================  B/C
def build(case, resx, primid=True, element=True):
    st = hou.node("/stage")
    for c in st.children():
        c.destroy()
    rec = []
    sub = st.createNode("sublayer", "scene")
    sub.parm("filepath1").set(SCENE)
    krs = st.createNode("karmarendersettings", "krs")
    krs.setInput(0, sub)
    for name, val in (("primid", primid), ("element", element),
                      ("resolutionx", resx), ("camera", "/world/cam"),
                      ("engine", "cpu"), ("samplesperpixel", 4),
                      ("pathtracedsamples", 16)):
        q = krs.parm(name)
        if q is None:
            rec.append({"parm": name, "status": "ABSENT"})
            continue
        try:
            q.set(val)
            rec.append({"parm": name, "status": "set", "readback": q.eval()})
        except Exception as exc:  # noqa: BLE001
            rec.append({"parm": name, "status": "error", "error": str(exc)})
    img = f"{OUTDIR}/{case}.exr"
    if os.path.exists(img):
        os.remove(img)
    rop = st.createNode("usdrender_rop", "render")
    rop.setInput(0, krs)
    rop.parm("trange").set(0)
    rop.parm("outputimage").set(img)
    return rop, img, rec


def render_timed(case, resx, primid=True, element=True):
    rop, img, rec = build(case, resx, primid, element)
    t0 = time.perf_counter()
    status, err = "returned", None
    try:
        rop.render(verbose=False)
    except Exception as exc:  # noqa: BLE001
        status, err = "raised", f"{type(exc).__name__}: {exc}"
    dt = time.perf_counter() - t0
    entry = {"case": case, "resolutionx_requested": resx, "parms": rec,
             "render_status": status, "render_error": err,
             "wall_seconds": round(dt, 3), "output": img,
             "exists": os.path.exists(img)}
    if entry["exists"]:
        entry["bytes"] = os.path.getsize(img)
        try:
            import OpenImageIO as oiio
            i = oiio.ImageInput.open(img)
            entry["actual_resolution"] = [i.spec().width, i.spec().height]
            names, k = [], 0
            while True:
                names.append(i.spec().getattribute("oiio:subimagename") or "")
                k += 1
                if not i.seek_subimage(k, 0):
                    break
            i.close()
            entry["parts"] = names
        except Exception as exc:  # noqa: BLE001
            entry["oiio_error"] = str(exc)
    p(f"  {case:16s} resx={resx:5d} wall={entry['wall_seconds']:7.3f}s "
      f"res={entry.get('actual_resolution')} parts={entry.get('parts')}")
    return entry


def phase_b():
    p("\n===== B. ingest control: primid ONLY =====")
    e = {}
    try:
        e["render"] = render_timed("ctrl_primid_only", 160,
                                   primid=True, element=False)
        from retina import ingest
        img = e["render"]["output"]
        if e["render"]["exists"]:
            idx = ingest.find_id_subimage(img)
            parts = e["render"].get("parts", [])
            e["find_id_subimage"] = idx
            e["selected_part"] = parts[idx] if idx is not None and idx < len(parts) else None
            e["correct"] = (e["selected_part"] == "primid")
            p(f"  parts={parts} find_id_subimage={idx} "
              f"selected={e['selected_part']!r} correct={e['correct']}")
        e["verdict"] = (
            "find_id_subimage is CORRECT when primid is the only ID part; the "
            "misselection is CONDITIONAL on an earlier part whose channel name "
            "contains 'id' (e.g. element.id)"
            if e.get("correct") else
            "find_id_subimage misselects even with primid alone")
        p(f"  -> {e['verdict']}")
    except Exception:  # noqa: BLE001
        e["error"] = traceback.format_exc()
        p(e["error"])
    REPORT["B_ingest_control"] = e
    flush()


def phase_c():
    p("\n===== C. cost curve =====")
    rows = []
    for resx in (160, 320, 640, 1280):
        rows.append(render_timed(f"cost_{resx}", resx))
        flush()
    REPORT["C_cost_curve"] = rows
    ok = [r for r in rows if r["exists"]]
    if len(ok) >= 2:
        base = ok[0]
        REPORT["C_summary"] = {
            "note": "wall_seconds includes husk PROCESS SPAWN, which is fixed "
                    "overhead and dominates at small resolutions",
            "smallest": {"res": base.get("actual_resolution"),
                         "seconds": base["wall_seconds"]},
            "largest": {"res": ok[-1].get("actual_resolution"),
                        "seconds": ok[-1]["wall_seconds"]},
        }
    flush()


def phase_d():
    p("\n===== D. flipbook headless =====")
    e = {"symbol_present": hasattr(hou.SceneViewer, "flipbook")}
    try:
        panes = [pt for pt in hou.ui.paneTabs()] if hasattr(hou, "ui") else None
        e["hou_ui_present"] = hasattr(hou, "ui")
        e["scene_viewers"] = None if panes is None else len(panes)
    except Exception as exc:  # noqa: BLE001
        e["hou_ui_error"] = f"{type(exc).__name__}: {exc}"
        e["hou_ui_present"] = False
    e["verdict"] = (
        "UNVERIFIABLE (not ABSENT): hou.SceneViewer.flipbook resolves as a "
        "symbol, but hou.ui is unavailable in headless hython so no "
        "SceneViewer instance can be obtained to invoke it. R50/H3a-F5: where "
        "no control is possible the verdict is UNVERIFIABLE."
        if not e.get("hou_ui_present") else
        "GUI present -- flipbook invocability is testable here")
    p(f"  symbol_present={e['symbol_present']} "
      f"hou.ui={e.get('hou_ui_present')}")
    p(f"  -> {e['verdict']}")
    REPORT["D_flipbook"] = e
    flush()


def main() -> int:
    hou.hipFile.clear(suppress_save_prompt=True)
    phase_a()
    phase_b()
    phase_c()
    phase_d()
    p(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        REPORT["fatal"] = traceback.format_exc()
        flush()
        traceback.print_exc()
        sys.exit(1)
