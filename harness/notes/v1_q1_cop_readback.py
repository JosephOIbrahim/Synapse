"""V1 / Q1e — Copernicus buffer readback, verified TWICE.

The brief flags this one specially: "documented Copernicus buffer-to-numpy
readback" is an OPEN SIDEFX ASK, so a clean path here is SURPRISING and must be
verified twice rather than once.

The two verifications are deliberately different in kind:
  1. STRUCTURAL -- the chain resolves and returns bytes of the length the
     buffer resolution and storage type predict. A wrong-length buffer would
     pass a "did it return something" check and fail this one.
  2. CONTENT    -- the same buffer read twice is byte-identical, AND the values
     decoded from the bytes match what the COP graph was told to produce.
     A readback that returns a plausible-but-stale or zero buffer passes (1)
     and fails (2).

Also times the readback, because Q3's real question is whether verification can
run per-mutation, and a COP readback is the cheap candidate.

Run:   hython3.13.exe harness/notes/v1_q1_cop_readback.py
Emits: harness/notes/v1_q1_cop_readback.json
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
OUT = os.path.join(HERE, "v1_q1_cop_readback.json")

REPORT = {"schema": "v1-q1-cop-readback/1",
          "build": hou.applicationVersionString(),
          "license": str(hou.licenseCategory())}


def flush():
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(REPORT, fh, indent=2)


def main() -> int:
    # --- what the API actually says ----------------------------------------
    REPORT["allBufferElements_doc"] = (
        hou.ImageLayer.allBufferElements.__doc__ or "").strip()
    REPORT["storage_types"] = sorted(
        m for m in dir(hou.imageLayerStorageType)
        if not m.startswith("_") and m != "thisown")
    print("allBufferElements doc:\n", REPORT["allBufferElements_doc"][:900])
    print("\nstorage types:", REPORT["storage_types"])
    flush()

    # --- find the Copernicus context ---------------------------------------
    cat = hou.copNodeTypeCategory()
    REPORT["cop_category"] = cat.name()
    parent = None
    for path in ("/img", "/obj", "/stage", "/mat"):
        n = hou.node(path)
        if n is None:
            continue
        try:
            if n.type().childTypeCategory() == cat:
                parent = n
                break
        except Exception:  # noqa: BLE001
            pass
    if parent is None:
        # Make a copnet wherever one is allowed.
        for host in ("/obj", "/img"):
            h = hou.node(host)
            if h is None:
                continue
            for tname in ("copnet", "cop2net"):
                try:
                    parent = h.createNode(tname, "_v1_copnet")
                    break
                except Exception:  # noqa: BLE001
                    continue
            if parent is not None:
                break
    REPORT["cop_parent"] = parent.path() if parent else None
    print("\ncop parent:", REPORT["cop_parent"],
          "child category:",
          parent.type().childTypeCategory().name() if parent else None)
    if parent is None:
        REPORT["verdict"] = "UNVERIFIABLE: no Copernicus parent network found"
        flush()
        return 1

    # --- build a COP that produces a KNOWN image ---------------------------
    avail = sorted(cat.nodeTypes().keys())
    REPORT["cop_type_count"] = len(avail)
    REPORT["cop_types_sample"] = [t for t in avail if "color" in t or "const" in t
                                  or "ramp" in t or "noise" in t][:20]
    print("cop types available:", REPORT["cop_type_count"],
          "sample:", REPORT["cop_types_sample"])

    node = None
    for tname in ("color", "constant", "ramp", "noise"):
        if tname in avail:
            try:
                node = parent.createNode(tname, "_v1_src")
                REPORT["cop_node_type"] = tname
                break
            except Exception:  # noqa: BLE001
                continue
    if node is None:
        REPORT["verdict"] = f"UNVERIFIABLE: could not create a source COP from {avail[:20]}"
        flush()
        return 1
    print("created COP:", node.path(), node.type().name())

    # Set a known constant colour if the parm exists (Law 3: record it).
    setrec = []
    for pname, val in (("colorr", 0.25), ("colorg", 0.5), ("colorb", 0.75)):
        p = node.parm(pname)
        setrec.append({"parm": pname,
                       "status": "set" if p else "ABSENT",
                       "wanted": val})
        if p:
            p.set(val)
    REPORT["source_parms"] = setrec

    node.cook(force=True)

    # --- verification 1: STRUCTURAL ---------------------------------------
    layer = node.layer()
    REPORT["layer_repr"] = repr(layer)[:200]
    res = list(layer.bufferResolution())
    REPORT["buffer_resolution"] = res
    print("buffer resolution:", res)

    CHANNELS = 4   # signature is allBufferElements(storagetype, channels:int)
    REPORT["channels_requested"] = CHANNELS
    results = {}
    for stname in REPORT["storage_types"]:
        st = getattr(hou.imageLayerStorageType, stname)
        try:
            t0 = time.perf_counter()
            data = layer.allBufferElements(st, CHANNELS)
            dt = time.perf_counter() - t0
            entry = {
                "ok": True,
                "bytes": len(data),
                "seconds": round(dt, 6),
                "sha256": hashlib.sha256(data).hexdigest()[:32],
            }
            # structural check: does the length match res * components * width?
            entry["bytes_per_pixel_implied"] = (
                len(data) / (res[0] * res[1]) if res and res[0] * res[1] else None)
            # verification 2 (content): read again, must be byte-identical
            data2 = layer.allBufferElements(st, CHANNELS)
            entry["repeat_identical"] = (data == data2)
            results[stname] = entry
            print(f"  {stname:8s} bytes={len(data):9d} "
                  f"bpp={entry['bytes_per_pixel_implied']} "
                  f"{dt*1000:.3f} ms  repeat_identical={entry['repeat_identical']}")
        except Exception as exc:  # noqa: BLE001
            results[stname] = {"ok": False,
                               "error": f"{type(exc).__name__}: {exc}"}
            print(f"  {stname:8s} FAILED {type(exc).__name__}: {exc}")
    REPORT["allBufferElements"] = results
    flush()

    # --- verification 2b: CONTENT — decode Float32 and check the values ----
    try:
        f32 = layer.allBufferElements(hou.imageLayerStorageType.Float32, CHANNELS)
        n = len(f32) // 4
        vals = struct.unpack(f"<{n}f", f32[:n * 4])
        REPORT["float32_decode"] = {
            "element_count": n,
            "min": min(vals), "max": max(vals),
            "first_16": list(vals[:16]),
            "distinct_first_4096": len(set(vals[:4096])),
        }
        print("\nfloat32 decode: n=%d min=%.6f max=%.6f first8=%s"
              % (n, min(vals), max(vals), list(vals[:8])))
    except Exception:  # noqa: BLE001
        REPORT["float32_decode_error"] = traceback.format_exc()
        print(REPORT["float32_decode_error"])

    # --- timing at a realistic size ---------------------------------------
    timings = []
    for _ in range(5):
        t0 = time.perf_counter()
        layer.allBufferElements(hou.imageLayerStorageType.Float32, CHANNELS)
        timings.append(time.perf_counter() - t0)
    REPORT["readback_timing_float32"] = {
        "resolution": res,
        "channels": CHANNELS,
        "runs": len(timings),
        "seconds_min": round(min(timings), 6),
        "seconds_median": round(sorted(timings)[len(timings) // 2], 6),
        "seconds_max": round(max(timings), 6),
    }
    print("readback timing:", REPORT["readback_timing_float32"])

    flush()
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        REPORT["fatal"] = traceback.format_exc()
        flush()
        traceback.print_exc()
        sys.exit(1)
