"""V1 / Q2 analysis — read the EXRs the render matrix produced and answer the
crux with pixels rather than with parm names.

Questions, each answered from the file:
  * what AOV parts/channels did Karma actually emit, and in what PIXEL FORMAT
    (this is the "is it integer?" question, answered by the file not the menu)
  * do the two spheres get DISTINCT id values -- the mask test
  * are the values INTEGRAL, or blended at boundaries
  * are the bare-named (no ray: prefix) parts all zeros while the ray:-prefixed
    controls are not -- the silent-zero test
  * is a repeated identical render byte-identical -- V2's noise floor, measured
    now because it is nearly free once the renders exist

Screen regions: the scene puts sphereL left of centre and sphereR right of
centre, so a column split at x = W/2 separates them. The probe samples a box
well inside each sphere rather than the whole half-frame, so background pixels
do not contaminate the "which ids belong to this object" count.

Run:   hython3.13.exe harness/notes/v1_q2_analyse.py <outdir>
Emits: harness/notes/v1_q2_analysis.json
"""
from __future__ import annotations

import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v1_q2_analysis.json")
OUTDIR = (sys.argv[1] if len(sys.argv) > 1
          else os.path.join(HERE, "_v1_out")).replace("\\", "/")

REPORT = {"schema": "v1-q2-analysis/1", "outdir": OUTDIR, "files": {}}

try:
    import OpenImageIO as oiio
    REPORT["oiio_version"] = oiio.__version__
except Exception as exc:  # noqa: BLE001
    REPORT["oiio_import_error"] = f"{type(exc).__name__}: {exc}"
    oiio = None

try:
    import numpy as np
    REPORT["numpy_version"] = np.__version__
except Exception as exc:  # noqa: BLE001
    REPORT["numpy_import_error"] = f"{type(exc).__name__}: {exc}"
    np = None


def describe(path):
    """Every subimage, its channels, and each channel's on-disk format."""
    inp = oiio.ImageInput.open(path)
    if inp is None:
        return {"error": oiio.geterror()}
    subs = []
    i = 0
    while True:
        spec = inp.spec()
        chformats = list(spec.channelformats) if spec.channelformats else \
            [str(spec.format)] * spec.nchannels
        subs.append({
            "index": i,
            "name": spec.getattribute("oiio:subimagename") or "",
            "width": spec.width, "height": spec.height,
            "nchannels": spec.nchannels,
            "channelnames": list(spec.channelnames),
            "format": str(spec.format),
            "channelformats": [str(c) for c in chformats],
            "attribs": {a.name: str(a.value)[:200] for a in spec.extra_attribs
                        if a.name in (
                            "oiio:ColorSpace", "compression", "openexr:lineOrder",
                            "HoudiniRenderer", "karma:renderer", "software",
                            "hostname", "DateTime")},
        })
        i += 1
        if not inp.seek_subimage(i, 0):
            break
    inp.close()
    return {"subimages": subs, "subimage_count": len(subs)}


def read_plane(path, subimage, channel_index):
    inp = oiio.ImageInput.open(path)
    inp.seek_subimage(subimage, 0)
    spec = inp.spec()
    px = inp.read_image(subimage, 0, 0, spec.nchannels, "float")
    inp.close()
    arr = np.array(px).reshape(spec.height, spec.width, spec.nchannels)
    return arr[:, :, channel_index], spec.width, spec.height


def box(arr, x0, x1, y0, y1):
    return arr[y0:y1, x0:x1]


def id_stats(path):
    """For every subimage that looks like an ID/data AOV, report what is in it,
    and whether the two spheres separate."""
    out = []
    d = describe(path)
    if "error" in d:
        return d
    for sub in d["subimages"]:
        nm = (sub["name"] or "").lower()
        chans = " ".join(sub["channelnames"]).lower()
        looks_id = any(t in nm or t in chans for t in
                       ("id", "element", "primid", "objectid", "crypto"))
        entry = {"subimage": sub["index"], "name": sub["name"],
                 "channelnames": sub["channelnames"],
                 "channelformats": sub["channelformats"],
                 "looks_like_id": looks_id}
        try:
            plane, W, H = read_plane(path, sub["index"], 0)
            finite = plane[np.isfinite(plane)]
            entry["stats"] = {
                "min": float(finite.min()) if finite.size else None,
                "max": float(finite.max()) if finite.size else None,
                "nonzero_frac": float((plane != 0).mean()),
                "distinct_values_total": int(np.unique(plane).size),
                "all_zero": bool(not plane.any()),
            }
            # integrality
            integral = np.isclose(plane, np.round(plane), atol=1e-6)
            entry["stats"]["integral_frac"] = float(integral.mean())
            entry["stats"]["non_integral_pixels"] = int((~integral).sum())
            # the two-sphere separation test: boxes well inside each sphere
            qw, qh = W // 8, H // 8
            cy = H // 2
            lx = W // 4          # centre of the left sphere
            rx = 3 * W // 4      # centre of the right sphere
            L = box(plane, lx - qw, lx + qw, cy - qh, cy + qh)
            R = box(plane, rx - qw, rx + qw, cy - qh, cy + qh)
            lu = set(np.unique(L).tolist())
            ru = set(np.unique(R).tolist())
            entry["separation"] = {
                "left_box": [lx - qw, lx + qw, cy - qh, cy + qh],
                "right_box": [rx - qw, rx + qw, cy - qh, cy + qh],
                "left_distinct": len(lu),
                "right_distinct": len(ru),
                "shared_values": len(lu & ru),
                "shared_sample": sorted(lu & ru)[:10],
                "left_sample": sorted(lu)[:10],
                "right_sample": sorted(ru)[:10],
                "disjoint": len(lu & ru) == 0,
            }
        except Exception as exc:  # noqa: BLE001
            entry["read_error"] = f"{type(exc).__name__}: {exc}"
        out.append(entry)
    return {"subimage_count": d["subimage_count"], "subimages": out}


def compare(a, b):
    """Pixel-level comparison of two EXRs (base vs noise, base vs denoise)."""
    da, db = describe(a), describe(b)
    if "error" in da or "error" in db:
        return {"error": "describe failed"}
    res = {"subimage_count": [da["subimage_count"], db["subimage_count"]],
           "per_subimage": []}
    n = min(da["subimage_count"], db["subimage_count"])
    for i in range(n):
        try:
            pa, W, H = read_plane(a, i, 0)
            pb, _, _ = read_plane(b, i, 0)
            diff = np.abs(pa - pb)
            res["per_subimage"].append({
                "index": i,
                "name": da["subimages"][i]["name"],
                "identical": bool(not diff.any()),
                "max_abs_diff": float(diff.max()),
                "changed_pixel_frac": float((diff > 0).mean()),
            })
        except Exception as exc:  # noqa: BLE001
            res["per_subimage"].append({"index": i, "error": str(exc)})
    return res


def main() -> int:
    if oiio is None or np is None:
        REPORT["fatal"] = "OpenImageIO or numpy unavailable in this interpreter"
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(REPORT, fh, indent=2)
        print(REPORT["fatal"])
        return 1

    for name in ("base", "noise", "bare_names", "ray_names", "int_format",
                 "denoise_on"):
        path = f"{OUTDIR}/{name}.exr"
        if not os.path.exists(path):
            REPORT["files"][name] = {"exists": False}
            continue
        print(f"\n===== {name} =====", flush=True)
        e = {"exists": True, "bytes": os.path.getsize(path)}
        try:
            e["analysis"] = id_stats(path)
            for sub in e["analysis"]["subimages"]:
                s = sub.get("stats", {})
                sep = sub.get("separation", {})
                print(f"  [{sub['subimage']}] {sub['name']!r:28s} "
                      f"chans={sub['channelnames']} fmt={sub['channelformats']}")
                if s:
                    print(f"        min={s['min']} max={s['max']} "
                          f"distinct={s['distinct_values_total']} "
                          f"all_zero={s['all_zero']} "
                          f"integral_frac={s['integral_frac']:.4f} "
                          f"non_integral_px={s['non_integral_pixels']}")
                if sep:
                    print(f"        L_distinct={sep['left_distinct']} "
                          f"R_distinct={sep['right_distinct']} "
                          f"shared={sep['shared_values']} "
                          f"DISJOINT={sep['disjoint']}")
                    print(f"        L_sample={sep['left_sample'][:6]} "
                          f"R_sample={sep['right_sample'][:6]}")
        except Exception:  # noqa: BLE001
            e["error"] = traceback.format_exc()
            print(e["error"])
        REPORT["files"][name] = e

    # determinism + denoiser comparisons
    b = f"{OUTDIR}/base.exr"
    if os.path.exists(b):
        for other, label in ((f"{OUTDIR}/noise.exr", "base_vs_noise"),
                             (f"{OUTDIR}/denoise_on.exr", "base_vs_denoise")):
            if os.path.exists(other):
                REPORT[label] = compare(b, other)
                print(f"\n--- {label} ---")
                for r in REPORT[label]["per_subimage"]:
                    print(f"   {r}")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(REPORT, fh, indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
