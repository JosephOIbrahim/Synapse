"""V1 / PROBE F — ray:objectid: is THIS the per-object mask? (Q2, resolved)

The chain that got here, recorded because each step was a wrong turn that a
control caught:

  D4  `primid` COLLIDES across objects (50 ids per sphere, 49 shared) -> not an
      object id. SideFX's ray-import reference agrees: ray:primid is per POLYGON.
  E2  tried `objectid` via extrarendervars with dataType=int/format=int32 ->
      render failed. CONFOUNDED: two variables changed at once.
  E3  2x2 isolation -> the fault was `format=int32`, which Karma rejects outright
      ("Unsupported image data format 'int32'"). `objectid` itself was innocent.
      But every extra var emitted an ALL-ZERO part, including the Ci control, so
      nothing was licensed either way.
  F0  sourceName sweep -> the `ray:` NAMESPACE PREFIX is required. Bare
      `objectid`, `primid`, `Ci`, `C`, `color` all emit a named part filled with
      zeros -- SILENTLY. `ray:objectid` and `ray:primid` carry real data.

A render var that emits a silently-zero plane for an unrecognised source is the
nastiest failure mode in this whole leg: it looks like a working AOV.

This probe answers the remaining question with the same oracle used throughout:
two spheres, footprints proven non-empty and disjoint. A per-object id gives
exactly ONE distinct value inside each footprint, and the two differ.

It also measures the precision problem F0 surfaced: ray:objectid values reached
5.25e8, and float32 represents integers exactly only to 2^24 = 16777216. Karma
refuses int32 for a render var, so the id can ONLY be carried as float. If the
ids exceed 2^24 they are quantised on write, and two distinct objects could
collide into one float. That is measured here, not assumed.

Controls (Law 1):
  positive   footprints non-empty and disjoint, else UNVERIFIABLE.
  negative   `ray:primid` runs through the SAME oracle and MUST FAIL it (D4 proved
             it collides). An oracle that passes primid cannot discriminate.
  zero-guard each candidate plane must be NON-ZERO somewhere. F0 showed an
             unrecognised source yields a silently-zero plane; a zero plane is a
             non-answer, never a verdict.
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
F32_EXACT_INT_MAX = 2 ** 24  # 16777216


def si(n, k, v):
    p = n.parm(k)
    if p is None:
        return False
    try:
        p.set(v)
        return True
    except Exception:
        return False


def export(tag, positions, source, filt=CLEAN):
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
    si(k, "samplesperpixel", 16)
    si(k, "extrarendervars", 1)
    si(k, "name1", "pv")
    si(k, "sourceName1", source)
    si(k, "sourceType1", "raw")
    si(k, "filter1", filt)
    si(k, "enable1", 1)
    usd = os.path.join(SCRATCH, f"v1F_{tag}.usd")
    k.stage().Export(usd)
    return usd


def render(tag, positions, source, filt=CLEAN):
    usd = export(tag, positions, source, filt)
    exr = os.path.join(SCRATCH, f"v1F_{tag}.exr")
    if os.path.exists(exr):
        os.remove(exr)
    t0 = time.perf_counter()
    p = subprocess.run([HUSK, "--make-output-path", "-o", exr, "-f", "1",
                        "-R", "BRAY_HdKarma", usd],
                       capture_output=True, text=True, timeout=300)
    return exr, round(time.perf_counter() - t0, 3), p.returncode, (p.stderr or "")[-500:]


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
    "probe": "V1/F ray:objectid as a per-object mask, with the float32 precision test",
    "producer": "harness/notes/v1/probe_f_objectid_mask.py",
    "build": str(hou.applicationVersionString()),
    "license_category": str(hou.licenseCategory()),
    "key_discovery": ("the `ray:` namespace prefix is REQUIRED on a custom render "
                      "var sourceName. Bare `objectid`/`primid`/`Ci` emit a named "
                      "part filled with ZEROS, silently -- an AOV that looks like "
                      "it works and carries nothing."),
    "footprints": {}, "candidates": [], "controls": {},
}

try:
    # footprints, from solo renders using the known-good ray:primid
    el, _, _, _ = render("fp_left", [LEFT], "ray:primid")
    er, _, _, _ = render("fp_right", [RIGHT], "ray:primid")
    L, Rp = part(el, "pv"), part(er, "pv")
    lc, rc = (L != 0), (Rp != 0)
    R["footprints"] = {
        "left_px": int(lc.sum()), "right_px": int(rc.sum()),
        "overlap_px": int((lc & rc).sum()),
        "nonempty_and_disjoint": bool(lc.sum() and rc.sum() and not (lc & rc).any()),
    }

    for tag, src, role in (
        ("ray_primid_NEGATIVE", "ray:primid",
         "NEGATIVE CONTROL - D4 proved primid collides; MUST fail the per-object oracle"),
        ("ray_objectid", "ray:objectid", "the candidate per-object id"),
        ("bare_objectid_ZEROGUARD", "objectid",
         "ZERO GUARD - F0 showed a bare source emits a silently-zero plane; this "
         "case must be caught as a non-answer, not scored as a verdict"),
    ):
        e = {"tag": tag, "source": src, "role": role}
        try:
            exr, wall, rc_, err = render(tag, [LEFT, RIGHT], src)
            e.update({"wall_seconds": wall, "returncode": rc_,
                      "stderr_tail": err.strip()[-300:],
                      "file_written": os.path.exists(exr)})
            pl = part(exr, "pv")
            if pl is None:
                e["verdict"] = "NO_PART"
            elif not (pl != 0).any():
                e["verdict"] = "ALL_ZERO_NON_ANSWER"
                e["note"] = "plane emitted but entirely zero; no verdict licensed"
            else:
                lv = set(np.unique(pl[lc]).tolist())
                rv = set(np.unique(pl[rc]).tolist())
                u = np.unique(pl)
                nz = u[u != 0]
                e.update({
                    "left_distinct": len(lv), "right_distinct": len(rv),
                    "left_values": sorted(lv)[:8], "right_values": sorted(rv)[:8],
                    "shared_values": len(lv & rv),
                    "distinct_total": int(u.size),
                    "max_value": float(u.max()),
                    "all_integral": bool(np.all(u == np.round(u))),
                    "per_object_clean": bool(len(lv) == 1 and len(rv) == 1 and lv != rv),
                })
                # float32 exact-integer capacity: ids above 2^24 are quantised on
                # write, and Karma refuses int32 for a render var (E3 case C).
                e["precision"] = {
                    "float32_exact_integer_max": F32_EXACT_INT_MAX,
                    "max_id_observed": float(nz.max()) if nz.size else None,
                    "exceeds_float32_exact_range": bool(nz.size and nz.max() > F32_EXACT_INT_MAX),
                    "min_gap_between_distinct_ids": (
                        float(np.diff(np.sort(nz)).min()) if nz.size > 1 else None),
                    "why_it_matters": ("Karma rejects format=int32 (E3 case C), so an "
                                       "id can only be carried as float. Above 2^24 "
                                       "float32 cannot hold consecutive integers, so "
                                       "distinct objects can quantise onto one value."),
                }
                e["verdict"] = "PER_OBJECT_ID" if e["per_object_clean"] else "NOT_PER_OBJECT"
        except Exception:
            e["verdict"] = "ERROR"
            e["error"] = traceback.format_exc()[-1000:]
        R["candidates"].append(e)
except Exception:
    R["error"] = traceback.format_exc()[-2000:]

neg = next((c for c in R["candidates"] if c["tag"] == "ray_primid_NEGATIVE"), {})
zg = next((c for c in R["candidates"] if c["tag"] == "bare_objectid_ZEROGUARD"), {})
R["controls"] = {
    "footprints_nonempty_and_disjoint": R["footprints"].get("nonempty_and_disjoint"),
    "negative_ray_primid_failed_oracle": neg.get("per_object_clean") is False,
    "zero_guard_caught_the_silent_zero": zg.get("verdict") == "ALL_ZERO_NON_ANSWER",
    "stated_failure_condition": (
        "controls_ok is false if footprints were empty/overlapping, or ray:primid "
        "PASSED the per-object oracle (an oracle that cannot reject a known-colliding "
        "id proves nothing), or the zero guard did NOT flag the bare-source plane -- "
        "which would mean a silently-zero AOV could be scored as a real verdict."
    ),
}
R["controls"]["controls_ok"] = bool(
    R["controls"]["footprints_nonempty_and_disjoint"]
    and R["controls"]["negative_ray_primid_failed_oracle"]
    and R["controls"]["zero_guard_caught_the_silent_zero"])

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(f"controls_ok={R['controls']['controls_ok']} "
      f"disjoint={R['controls']['footprints_nonempty_and_disjoint']} "
      f"primid_failed={R['controls']['negative_ray_primid_failed_oracle']} "
      f"zeroguard={R['controls']['zero_guard_caught_the_silent_zero']}")
print("footprints:", json.dumps(R["footprints"]))
for c in R["candidates"]:
    print(f"  {c['tag']:26} {c.get('verdict','?')}")
    if c.get("left_distinct") is not None:
        print(f"      Ldistinct={c['left_distinct']} Rdistinct={c['right_distinct']} "
              f"shared={c['shared_values']} integral={c['all_integral']} max={c['max_value']}")
        print(f"      L={c['left_values'][:3]} R={c['right_values'][:3]}")
        print(f"      precision: {json.dumps({k: v for k, v in c['precision'].items() if k != 'why_it_matters'})}")
print(f"wrote {OUT}")
