"""V1 / PROBE E — is there a PER-OBJECT integer id at all? (Q2, the gate)

D4 settled that `primid` COLLIDES across objects: two identical spheres rendered
alone produced 50 ids each and shared 49 of them. So primid does not name a prim.

The recon strand found SideFX's own ray-import reference saying exactly that:
    ray:primid   int, over "Polygon, point, and curve elements of each gprim"
    ray:objectid int, over "Individual gprims"
`primid` is per-ELEMENT by documented design. `ray:objectid` is the per-object
one -- and karmarendersettings has NO objectid toggle (the complete 402-parm list
carries primid/primidfilter/primidprecision and element/elementfilter/
elementprecision, and nothing matching objectid).

perception_truth_22.0.368.json item 1 concluded "toggle required; rendervar
redundant" after a bare rendervar produced no ID buffer. But the five spellings it
tried were primId/primid/id/instanceId/elementId -- NOT objectid, and a bare
rendervar LOP may simply never have been wired into the render products. This
probe uses karmarendersettings' own `extrarendervars` multiparm instead, which is
the built-in attachment point.

THE ORACLE (the same test for every candidate):
    two spheres, footprints proven non-empty and disjoint.
    a per-object id means: exactly ONE distinct value inside the left footprint,
    exactly ONE inside the right, and the two differ.

Controls (Law 1):
  negative  `primid` is run through the SAME oracle and MUST FAIL it. D4 proved
            primid collides, so an oracle that passes primid cannot discriminate
            and every PASS it reports is worthless.
  positive  footprints must be non-empty and disjoint, or the case is
            UNVERIFIABLE rather than a verdict.
  FAILS IF  primid passes the per-object oracle, or footprints are empty/overlapping.
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


def scene(positions, toggles=None, extravars=None):
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
    for name, val in (toggles or {}).items():
        si(k, name, val)
    applied_vars = []
    if extravars:
        si(k, "extrarendervars", len(extravars))
        for i, spec in enumerate(extravars, start=1):
            got = {}
            for base, val in spec.items():
                for pattern in (f"{base}{i}", f"{base}_{i}", f"{base}#{i}"):
                    if si(k, pattern, val):
                        got[pattern] = val
                        break
            applied_vars.append(got)
    rop = stage.createNode("usdrender_rop")
    rop.setInput(0, k)
    si(rop, "trange", 0)
    si(rop, "renderer", "BRAY_HdKarma")
    return k, rop, applied_vars


def render(tag, positions, toggles=None, extravars=None):
    out = os.path.join(SCRATCH, f"v1e_{tag}.exr")
    if os.path.exists(out):
        os.remove(out)
    k, rop, av = scene(positions, toggles, extravars)
    si(rop, "outputimage", out)
    t0 = time.perf_counter()
    try:
        rop.render(verbose=False)
    except Exception as exc:
        return out, None, av, repr(exc)[:300]
    while not os.path.exists(out) and time.perf_counter() - t0 < 240:
        time.sleep(0.05)
    return out, round(time.perf_counter() - t0, 3), av, None


def parts(path):
    return [p.name for p in read_exr_header(path).parts] if os.path.exists(path) else []


def plane(path, name):
    h = read_exr_header(path)
    idx = next((i for i, p in enumerate(h.parts)
                if (p.name or "").lower() == name.lower()), None)
    if idx is None:
        return None
    inp = oiio.ImageInput.open(path)
    if idx:
        inp.seek_subimage(idx, 0)
    sp = inp.spec()
    px = inp.read_image(oiio.FLOAT)
    inp.close()
    return np.asarray(px, dtype=np.float64).reshape(sp.height, sp.width, sp.nchannels)[..., 0]


R = {
    "probe": "V1/E per-object integer id: does one exist on 22.0.368?",
    "producer": "harness/notes/v1/probe_e_objectid.py",
    "build": str(hou.applicationVersionString()),
    "license_category": str(hou.licenseCategory()),
    "oracle": ("a per-object id gives exactly ONE distinct value inside each of two "
               "disjoint object footprints, and the two values differ"),
    "footprints": {},
    "candidates": [],
    "husk_delegate_test": {},
    "controls": {},
}

try:
    # ---- footprints from solo renders (the isolation control) --------------
    pl, _, _, _ = render("solo_left", [LEFT], {"primid": 1, "primidfilter": CLEAN})
    pr, _, _, _ = render("solo_right", [RIGHT], {"primid": 1, "primidfilter": CLEAN})
    L, Rp = plane(pl, "primid"), plane(pr, "primid")
    lc, rc = (L != 0), (Rp != 0)
    R["footprints"] = {
        "left_px": int(lc.sum()), "right_px": int(rc.sum()),
        "overlap_px": int((lc & rc).sum()),
        "nonempty_and_disjoint": bool(lc.sum() and rc.sum() and not (lc & rc).any()),
    }

    CANDIDATES = [
        {"tag": "primid_NEGATIVE_CONTROL", "part": "primid",
         "toggles": {"primid": 1, "primidfilter": CLEAN}, "extravars": None,
         "role": "NEGATIVE CONTROL - D4 proved this collides; it MUST fail the oracle"},
        {"tag": "element_toggle", "part": "element",
         "toggles": {"element": 1, "elementfilter": CLEAN}, "extravars": None,
         "role": "the second shipped ID toggle"},
        {"tag": "rendervar_objectid", "part": "objectid",
         "toggles": {}, "role": "ray:objectid via extrarendervars (documented per-gprim)",
         "extravars": [{"rendervarname": "objectid", "rendervarsourcename": "objectid",
                        "rendervarsourcetype": "raw", "rendervardatatype": "int"}]},
        {"tag": "rendervar_ray_objectid", "part": "objectid",
         "toggles": {}, "role": "same, spelled ray:objectid",
         "extravars": [{"rendervarname": "objectid", "rendervarsourcename": "ray:objectid",
                        "rendervarsourcetype": "raw", "rendervardatatype": "int"}]},
    ]

    for c in CANDIDATES:
        e = {"tag": c["tag"], "role": c["role"], "requested_part": c["part"]}
        try:
            p, wall, av, err = render(c["tag"], [LEFT, RIGHT], c["toggles"], c.get("extravars"))
            e["wall_seconds"] = wall
            e["render_error"] = err
            e["parts"] = parts(p)
            e["extravar_parms_applied"] = av
            pl_ = None
            for cand_name in (c["part"], c["part"].replace("ray:", "")):
                pl_ = plane(p, cand_name)
                if pl_ is not None:
                    e["part_found_as"] = cand_name
                    break
            if pl_ is None:
                e["verdict"] = "NO_SUCH_PART"
                e["note"] = ("the requested AOV did not appear as an EXR part; "
                             "licensed because the COMPLETE part list is recorded above")
            else:
                lv = set(np.unique(pl_[lc]).tolist())
                rv = set(np.unique(pl_[rc]).tolist())
                e["left_values"] = sorted(lv)[:12]
                e["right_values"] = sorted(rv)[:12]
                e["left_distinct"] = len(lv)
                e["right_distinct"] = len(rv)
                e["shared_values"] = len(lv & rv)
                e["all_integral"] = bool(np.all(np.unique(pl_) == np.round(np.unique(pl_))))
                e["per_object_clean"] = bool(len(lv) == 1 and len(rv) == 1 and lv != rv)
                e["verdict"] = ("PER_OBJECT_ID" if e["per_object_clean"]
                                else "NOT_PER_OBJECT")
        except Exception:
            e["verdict"] = "ERROR"
            e["error"] = traceback.format_exc()[-1200:]
        R["candidates"].append(e)

    # ---- husk delegate-id test: settle the "Indie no-ops husk" contradiction
    # Four shipped artifacts assert husk cannot load Karma on Indie. Every failing
    # record passed `--renderer karma`; every passing one used BRAY_HdKarma. That
    # confound was never tested. Test it.
    usd = os.path.join(SCRATCH, "v1e_delegate.usd")
    k, rop, _ = scene([LEFT, RIGHT], {"primid": 1, "primidfilter": CLEAN})
    si(rop, "lopoutput", usd)
    si(rop, "savetodirectory_directory", "")
    try:
        rop.parm("execute").pressButton() if rop.parm("execute") else None
    except Exception:
        pass
    # husk needs a usd on disk; export the stage directly instead
    try:
        k.stage().Export(usd)
        R["husk_delegate_test"]["usd_exported"] = os.path.exists(usd)
    except Exception as exc:
        R["husk_delegate_test"]["usd_export_error"] = repr(exc)[:200]

    husk = os.path.join(os.environ.get("HFS", ""), "bin", "husk.exe")
    if not os.path.exists(husk):
        husk = r"C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\husk.exe"
    R["husk_delegate_test"]["husk_path"] = husk
    R["husk_delegate_test"]["husk_exists"] = os.path.exists(husk)
    if os.path.exists(usd) and os.path.exists(husk):
        for label, flag in (("delegate_id_BRAY_HdKarma", ["-R", "BRAY_HdKarma"]),
                            ("plain_name_karma", ["--renderer", "karma"])):
            o = os.path.join(SCRATCH, f"v1e_husk_{label}.exr")
            if os.path.exists(o):
                os.remove(o)
            cmd = [husk, "--make-output-path", "-o", o, "-f", "1"] + flag + [usd]
            t0 = time.perf_counter()
            try:
                pr_ = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                R["husk_delegate_test"][label] = {
                    "argv_flag": " ".join(flag),
                    "returncode": pr_.returncode,
                    "wall_seconds": round(time.perf_counter() - t0, 3),
                    "file_written": os.path.exists(o),
                    "file_bytes": os.path.getsize(o) if os.path.exists(o) else 0,
                    "stderr_tail": (pr_.stderr or "")[-600:],
                    "stdout_tail": (pr_.stdout or "")[-400:],
                }
            except Exception as exc:
                R["husk_delegate_test"][label] = {"error": repr(exc)[:300]}
except Exception:
    R["error"] = traceback.format_exc()[-2500:]

neg = next((c for c in R["candidates"] if c["tag"].startswith("primid_")), {})
R["controls"] = {
    "footprints_nonempty_and_disjoint": R["footprints"].get("nonempty_and_disjoint"),
    "negative_control_primid_failed_oracle": neg.get("per_object_clean") is False,
    "stated_failure_condition": (
        "controls_ok is false if the two footprints were empty or overlapping (no "
        "verdict licensed), or if primid PASSED the per-object oracle -- D4 proved "
        "primid collides across objects, so an oracle that passes it cannot "
        "discriminate and every PER_OBJECT_ID verdict here would be worthless."
    ),
}
R["controls"]["controls_ok"] = bool(
    R["controls"]["footprints_nonempty_and_disjoint"]
    and R["controls"]["negative_control_primid_failed_oracle"])

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(f"controls_ok={R['controls']['controls_ok']} "
      f"disjoint={R['controls']['footprints_nonempty_and_disjoint']} "
      f"primid_failed_oracle={R['controls']['negative_control_primid_failed_oracle']}")
print("footprints:", json.dumps(R["footprints"]))
for c in R["candidates"]:
    print(f"  {c['tag']:26} {c.get('verdict','?'):16} parts={c.get('parts')} "
          f"Ldistinct={c.get('left_distinct')} Rdistinct={c.get('right_distinct')} "
          f"shared={c.get('shared_values')} integral={c.get('all_integral')}")
print("husk delegate test:")
for k_ in ("delegate_id_BRAY_HdKarma", "plain_name_karma"):
    v = R["husk_delegate_test"].get(k_)
    if v:
        print(f"   {k_}: rc={v.get('returncode')} written={v.get('file_written')} "
              f"bytes={v.get('file_bytes')} wall={v.get('wall_seconds')}")
        if v.get("stderr_tail"):
            print("     stderr:", v["stderr_tail"][-260:].replace("\n", " | "))
print(f"wrote {OUT}")
