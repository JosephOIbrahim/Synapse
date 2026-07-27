"""V1 / Q2c — is retina/ingest.py's ID-AOV path EXERCISED or ASPIRATIONAL?

The brief asks whether ingest.py "already knows how to read" the integer
object-ID AOV. Reading the source suggests it picks the wrong part; reading is
not evidence, so this RUNS it against a real Karma 22.0.368 frame produced by
v1_q2_render.py.

find_id_subimage() scans parts in order and returns the first whose part name
OR any channel name contains one of ID_PART_NAMES = ("primid", "id",
"cryptomatte"). A shipped Karma frame with primid+element enabled has parts:

    0  C        channels R,G,B,A
    1  element  channel  element.id     <- "id" matches HERE first
    2  primid   channel  primid.id      <- what the docstring says it wants

So the question is which index comes back. Also reports the resolution actually
rendered and the per-part colour space (the "Raw / never transformed" claim).

Run:   hython3.13.exe harness/notes/v1_q2_ingest_check.py <outdir>
Emits: harness/notes/v1_q2_ingest_check.json
"""
from __future__ import annotations

import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "v1_q2_ingest_check.json")
OUTDIR = (sys.argv[1] if len(sys.argv) > 1
          else os.path.join(HERE, "_v1_out")).replace("\\", "/")
EXR = f"{OUTDIR}/base.exr"

sys.path.insert(0, REPO)

REPORT = {"schema": "v1-q2-ingest-check/1", "exr": EXR, "repo": REPO}


def main() -> int:
    # --- ground truth about the file, straight from OIIO -------------------
    import OpenImageIO as oiio
    inp = oiio.ImageInput.open(EXR)
    parts, i = [], 0
    while True:
        spec = inp.spec()
        parts.append({
            "index": i,
            "name": spec.getattribute("oiio:subimagename") or "",
            "width": spec.width, "height": spec.height,
            "channels": list(spec.channelnames),
            "format": str(spec.format),
            "colorspace": spec.getattribute("oiio:ColorSpace"),
            "compression": spec.getattribute("compression"),
        })
        i += 1
        if not inp.seek_subimage(i, 0):
            break
    inp.close()
    REPORT["ground_truth_parts"] = parts
    REPORT["rendered_resolution"] = [parts[0]["width"], parts[0]["height"]]

    # --- what retina/ingest.py actually does -------------------------------
    try:
        from retina import ingest
        REPORT["ingest_import"] = "ok"
        REPORT["ID_PART_NAMES"] = list(ingest.ID_PART_NAMES)

        hdr = ingest.read_exr_header(EXR)
        REPORT["ingest_header_parts"] = [
            {"name": p.name, "channels": [c.name for c in p.channels]}
            for p in hdr.parts
        ]

        idx = ingest.find_id_subimage(EXR)
        REPORT["find_id_subimage"] = idx
        REPORT["selected_part_name"] = (
            parts[idx]["name"] if idx is not None and idx < len(parts) else None)
        REPORT["primid_part_index"] = next(
            (p["index"] for p in parts if p["name"] == "primid"), None)
        REPORT["selects_primid"] = (
            REPORT["find_id_subimage"] == REPORT["primid_part_index"])

        try:
            plane = ingest.read_id_plane(EXR)
            REPORT["read_id_plane"] = {
                "ok": True, "shape": list(plane.shape),
                "dtype": str(plane.dtype),
                "min": float(plane.min()), "max": float(plane.max()),
            }
        except Exception as exc:  # noqa: BLE001
            REPORT["read_id_plane"] = {
                "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        REPORT["colour_env"] = ingest.colour_report() if hasattr(
            ingest, "colour_report") else None
    except Exception:  # noqa: BLE001
        REPORT["ingest_error"] = traceback.format_exc()

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(REPORT, fh, indent=2)

    print("rendered resolution :", REPORT["rendered_resolution"])
    print("parts               :")
    for p in parts:
        print(f"   [{p['index']}] {p['name']!r:12s} chans={p['channels']} "
              f"fmt={p['format']} colorspace={p['colorspace']!r}")
    print()
    print("ID_PART_NAMES       :", REPORT.get("ID_PART_NAMES"))
    print("find_id_subimage -> :", REPORT.get("find_id_subimage"),
          "=> part", repr(REPORT.get("selected_part_name")))
    print("primid part index   :", REPORT.get("primid_part_index"))
    print("SELECTS primid?     :", REPORT.get("selects_primid"))
    print("read_id_plane       :", REPORT.get("read_id_plane"))
    if "ingest_error" in REPORT:
        print(REPORT["ingest_error"])
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
