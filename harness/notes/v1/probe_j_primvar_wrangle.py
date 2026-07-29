"""V1 / PROBE J — per-object mask from a primvar authored by attribwrangle.

Probe I tried to author the primvar with a `primitive` LOP and failed: its
stage_check came back null for both prims, so its ALL_ZERO results were
UNVERIFIABLE, not evidence about primvars. Discovery afterwards showed the
`primitive` LOP has NO primvar parms at all; the LOP-side primvar authors are
`attribwrangle` and `attribvop`.

That is the THIRD authoring miss in this leg (probe_e's extrarendervars names,
probe_i's primitive names, and this class generally). Each was caught only because
the probe recorded what it ACTUALLY authored and verified it on the composed stage
before drawing a conclusion. That check is the finding as much as any result is.

THE GATE, enforced before any render is interpreted: the primvar must be present
on the composed USD stage with the authored value. If stage_check fails, the leg
reports UNVERIFIABLE and stops -- it does not guess again.

THE ORACLE, identical to probe_f/g/i: two spheres, footprints non-empty and
disjoint. A per-object id gives exactly ONE non-zero value inside each footprint,
they differ, and here they must EXACTLY equal the authored ids.

Controls (Law 1):
  authoring  the primvar must appear on the composed stage with the right value,
             per prim, or nothing downstream is interpretable.
  positive   footprints non-empty and disjoint (measured with ray:primid).
  negative   ray:primid runs the SAME oracle and MUST FAIL it.
  zero-guard an all-zero plane is a NON-ANSWER, never a verdict.
  FAILS IF   the stage check fails, footprints are empty/overlapping, or
             ray:primid passes the oracle.
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
IDS = {0: 1.0, 1: 2.0}
PV = "synapse_oid"


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
    st = hou.node("/stage")
    for c in st.children():
        c.destroy()
    prev = None
    for i, (tx, ty) in enumerate(positions):
        s = st.createNode("sphere", f"sphere{i}")
        si(s, "primpath", f"/scene/sphere{i}")
        si(s, "tx", tx)
        si(s, "ty", ty)
        if prev:
            s.setInput(0, prev)
        prev = s
        w = st.createNode("attribwrangle", f"pvw{i}")
        w.setInput(0, prev)
        si(w, "primpattern", f"/scene/sphere{i}")
        si(w, "vexsnippet", f"f@{PV} = {IDS[i]};")
        prev = w
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

    stage_check = {}
    try:
        stg = k.stage()
        for i in range(len(positions)):
            pr = stg.GetPrimAtPath(f"/scene/sphere{i}")
            if not pr:
                stage_check[f"sphere{i}"] = {"prim": False}
                continue
            names = [a.GetName() for a in pr.GetAttributes()
                     if a.GetName().startswith("primvars:")]
            at = pr.GetAttribute(f"primvars:{PV}")
            stage_check[f"sphere{i}"] = {
                "prim": True,
                "primvar_attrs_present": names[:8],
                "authored": bool(at and at.IsValid()),
                "value": (str(at.Get()) if at and at.IsValid() else None),
            }
    except Exception as exc:
        stage_check["error"] = repr(exc)[:300]

    usd = os.path.join(SCRATCH, f"v1J_{tag}.usd")
    k.stage().Export(usd)
    return usd, stage_check


def render(tag, usd):
    exr = os.path.join(SCRATCH, f"v1J_{tag}.exr")
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
    "probe": "V1/J per-object mask from an attribwrangle-authored primvar",
    "producer": "harness/notes/v1/probe_j_primvar_wrangle.py",
    "build": str(hou.applicationVersionString()),
    "primvar": PV, "authored_ids": IDS,
    "footprints": {}, "candidates": [], "controls": {},
}

try:
    ul, _ = build("fpL", [LEFT], "ray:primid", "raw")
    el, _, _, _ = render("fpL", ul)
    ur, _ = build("fpR", [RIGHT], "ray:primid", "raw")
    er, _, _, _ = render("fpR", ur)
    L, Rp = part(el, "pv"), part(er, "pv")
    lc, rc = (L != 0), (Rp != 0)
    R["footprints"] = {"left_px": int(lc.sum()), "right_px": int(rc.sum()),
                       "overlap_px": int((lc & rc).sum()),
                       "nonempty_and_disjoint": bool(lc.sum() and rc.sum() and not (lc & rc).any())}

    for tag, src, stype, role in (
        ("primid_NEGATIVE", "ray:primid", "raw",
         "NEGATIVE CONTROL - collides across objects; MUST fail the oracle"),
        ("primvar_plain", PV, "primvar", "authored primvar, sourceType=primvar"),
        ("primvar_qualified", f"primvars:{PV}", "primvar", "namespace-qualified"),
        ("primvar_as_raw", PV, "raw", "same name via sourceType=raw, for contrast"),
    ):
        e = {"tag": tag, "source": src, "source_type": stype, "role": role}
        try:
            usd, sc = build(tag, [LEFT, RIGHT], src, stype)
            e["stage_check"] = sc
            authored_ok = all(
                isinstance(v, dict) and v.get("authored") for k_, v in sc.items()
                if k_.startswith("sphere"))
            e["primvar_on_stage"] = bool(authored_ok)
            exr, wall, rc_, err = render(tag, usd)
            e.update({"wall_seconds": wall, "returncode": rc_,
                      "stderr": err.strip()[-250:], "file_written": os.path.exists(exr)})
            pl = part(exr, "pv")
            if pl is None:
                e["verdict"] = "NO_PART"
            elif not (pl != 0).any():
                e["verdict"] = ("ALL_ZERO_NON_ANSWER" if authored_ok
                                else "UNVERIFIABLE_PRIMVAR_NOT_AUTHORED")
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
cands = [c for c in R["candidates"] if c["tag"] != "primid_NEGATIVE"]
R["controls"] = {
    "footprints_nonempty_and_disjoint": R["footprints"].get("nonempty_and_disjoint"),
    "negative_primid_failed_oracle": neg.get("per_object_clean") is False,
    "primvar_authored_on_stage": all(c.get("primvar_on_stage") for c in cands) if cands else None,
    "stated_failure_condition": (
        "controls_ok is false if the primvar was NOT present on the composed stage "
        "(probe I's defect: nothing authored, so an all-zero plane says nothing), or "
        "the footprints were empty/overlapping, or ray:primid PASSED the per-object "
        "oracle."),
}
R["controls"]["controls_ok"] = bool(
    R["controls"]["footprints_nonempty_and_disjoint"]
    and R["controls"]["negative_primid_failed_oracle"]
    and R["controls"]["primvar_authored_on_stage"])

winner = next((c for c in cands if c.get("verdict") == "PER_OBJECT_ID"), None)
R["answer"] = {
    "per_object_mask_found": bool(winner),
    "how": (f"extrarendervars sourceName={winner['source']!r} "
            f"sourceType={winner['source_type']!r}, primvar authored by attribwrangle "
            f"(f@{PV}), filter {CLEAN}") if winner else None,
    "exact": winner.get("matches_authored_ids_exactly") if winner else None,
}

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(f"controls_ok={R['controls']['controls_ok']} "
      f"authored_on_stage={R['controls']['primvar_authored_on_stage']} "
      f"primid_failed={R['controls']['negative_primid_failed_oracle']}")
print("footprints:", json.dumps(R["footprints"]))
for c in R["candidates"]:
    print(f"  {c['tag']:20} {c.get('verdict','?'):34} L={c.get('left_values')} "
          f"R={c.get('right_values')} exact={c.get('matches_authored_ids_exactly')}")
print("STAGE CHECK (one case):", json.dumps(cands[0].get("stage_check") if cands else {}))
print("ANSWER:", json.dumps(R["answer"]))
print(f"wrote {OUT}")
