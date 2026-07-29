"""V1 / PROBE B2 — the Copernicus readback, VERIFIED TWICE.

Probe A found the path nobody guessed: hou.CopNode.layer() -> hou.ImageLayer,
whose readback verb is allBufferElements() (NOT allPixels -- that spelling lives
only on the legacy hou.Cop2Node). The brief requires a clean path here to be
treated as SURPRISING, because "documented Copernicus buffer-to-numpy readback"
is an OPEN SIDEFX ASK.

So this probe does not ask "did it return something". It authors a constant whose
value nothing else in the process knows, reads the buffer back, and checks the
numbers are that value.

Calibration note, earned in-run (R60 -- the READER must be calibrated too): a
first pass used a 1e-4 tolerance and went red. The cause was not the API: the
copnet's `precision` parm defaults such that the round trip carries float16-class
error. That is a real property of the instrument, so the tolerance is now DERIVED
from the layer's reported storageType rather than assumed, and the decoy control
below proves the derived tolerance is still tight enough to reject a wrong answer.

Controls (Law 1 — state the condition under which this fails):
  positive  the round trip reproduces the authored constant within a tolerance
            derived from the reported storage precision.
  negative  the SAME comparison against a DECOY value must FAIL. Without this the
            tolerance could have been widened until everything passes, which is
            the "check that cannot fail" defect (Law 1).
  determinism  reading the same cooked buffer twice must return IDENTICAL BYTES.
            V2's noise floor is meaningless if readback itself is nondeterministic.
  FAILS IF  the positive match fails, or the decoy ALSO matches, or the two reads
            of one buffer differ.
"""

from __future__ import annotations

import json
import sys
import time
import traceback

OUT = sys.argv[1] if len(sys.argv) > 1 else "probe_b2_readback.json"

import hou  # noqa: E402
import numpy as np  # noqa: E402

AUTHORED = (0.2468, 0.5791, 0.8135)   # nothing else in this process knows these
DECOY = (0.9000, 0.1000, 0.3000)      # the negative control's expectation

DTYPE = {
    "imageLayerStorageType.Float16": np.float16,
    "imageLayerStorageType.Float32": np.float32,
    "imageLayerStorageType.Float64": np.float64,
    "imageLayerStorageType.Int8": np.int8,
    "imageLayerStorageType.Int16": np.int16,
    "imageLayerStorageType.Int32": np.int32,
    "imageLayerStorageType.UInt8": np.uint8,
}
# Tolerance derived from precision, not assumed. float16 has ~3 decimal digits.
TOL = {np.float16: 2e-3, np.float32: 1e-4, np.float64: 1e-9}

R = {
    "probe": "V1/B2 Copernicus readback verified twice (value round-trip + determinism + timing)",
    "producer": "harness/notes/v1/probe_b2_readback.py",
    "build": str(hou.applicationVersionString()),
    "license_category": str(hou.licenseCategory()),
    "numpy": np.__version__,
    "controls": {},
    "roundtrip": {},
    "precision_sweep": [],
    "timing": [],
    "module_level_io": {},
}


def build(w, h, precision=None, sig="f3", rgb=AUTHORED):
    net = hou.node("/obj").createNode("copnet")
    net.parm("setres").set(1)
    net.parm("res1").set(w)
    net.parm("res2").set(h)
    if precision is not None:
        net.parm("setprecision").set(1)
        net.parm("precision").set(precision)
    c = net.createNode("constant")
    c.parm("signature").set(sig)
    c.parm("f3r").set(rgb[0])
    c.parm("f3g").set(rgb[1])
    c.parm("f3b").set(rgb[2])
    c.setDisplayFlag(True)
    c.cook(force=True)
    return net, c


def decode(layer, raw):
    st = str(layer.storageType())
    dt = DTYPE.get(st, np.float32)
    arr = np.frombuffer(raw, dtype=dt)
    ch = layer.channelCount()
    if ch:
        arr = arr.reshape(-1, ch)
    return arr, dt, st


# ------------------------------------------------------------- round trip
try:
    net, con = build(256, 128, precision="b32")
    lay = con.layer()
    t0 = time.perf_counter()
    raw = lay.allBufferElements()
    t_read = time.perf_counter() - t0
    arr, dt, st = decode(lay, raw)
    means = [float(x) for x in arr.astype(np.float64).mean(axis=0)]
    tol = TOL.get(dt, 1e-4)

    # determinism: a second read of the SAME cooked buffer must be byte-identical
    raw2 = con.layer().allBufferElements()

    R["roundtrip"] = {
        "authored": list(AUTHORED),
        "measured_means": means,
        "tolerance_used": tol,
        "tolerance_derived_from": st,
        "buffer_type": type(raw).__name__,
        "buffer_is_numpy": isinstance(raw, np.ndarray),
        "buffer_bytes": len(raw),
        "numpy_conversion": "np.frombuffer(raw, dtype) -- zero-copy view, no element loop",
        "channel_count": lay.channelCount(),
        "buffer_resolution": list(lay.bufferResolution()),
        "storage_type": st,
        "stores_integers": bool(lay.storesIntegers()),
        "data_window": str(lay.dataWindow()),
        "display_window": str(lay.displayWindow()),
        "on_gpu": bool(lay.onGPU()),
        "on_cpu": bool(lay.onCPU()),
        "readback_seconds": round(t_read, 6),
    }
    R["controls"]["positive_match"] = all(
        abs(means[i] - AUTHORED[i]) < tol for i in range(3)
    )
    R["controls"]["negative_match"] = all(
        abs(means[i] - DECOY[i]) < tol for i in range(3)
    )
    R["controls"]["determinism_identical_bytes"] = (raw == raw2)
    R["controls"]["detail"] = {
        "expected": list(AUTHORED),
        "decoy": list(DECOY),
        "measured": means,
        "tolerance": tol,
        "why_negative": "if the decoy also matched, the tolerance is so wide the "
                        "check cannot disagree and every match here is worthless",
    }
except Exception:
    R["roundtrip"]["error"] = traceback.format_exc()[-2500:]
    R["controls"]["positive_match"] = False
    R["controls"]["negative_match"] = None
    R["controls"]["determinism_identical_bytes"] = None

# --------------------------------------------------------- precision sweep
for prec in ("b16", "b32"):
    try:
        net, con = build(64, 64, precision=prec)
        lay = con.layer()
        arr, dt, st = decode(lay, lay.allBufferElements())
        R["precision_sweep"].append({
            "precision_parm": prec,
            "reported_storage": st,
            "numpy_dtype": np.dtype(dt).name,
            "means": [float(x) for x in arr.astype(np.float64).mean(axis=0)],
            "authored": list(AUTHORED),
            "honest": (prec == "b16") == (st == "imageLayerStorageType.Float16"),
        })
    except Exception as exc:
        R["precision_sweep"].append({"precision_parm": prec, "error": repr(exc)[:300]})

# ------------------------------------------------------------------ timing
for (w, h) in ((256, 256), (512, 512), (1024, 1024), (1920, 1080), (3840, 2160)):
    try:
        net, con = build(w, h, precision="b32")
        t0 = time.perf_counter()
        con.cook(force=True)
        t_cook = time.perf_counter() - t0
        lay = con.layer()
        t0 = time.perf_counter()
        raw = lay.allBufferElements()
        t_read = time.perf_counter() - t0
        t0 = time.perf_counter()
        arr = np.frombuffer(raw, dtype=np.float32)
        t_np = time.perf_counter() - t0
        R["timing"].append({
            "resolution": [w, h],
            "buffer_resolution": list(lay.bufferResolution()),
            "megapixels": round(w * h / 1e6, 3),
            "bytes": len(raw),
            "cook_seconds": round(t_cook, 5),
            "readback_seconds": round(t_read, 5),
            "frombuffer_seconds": round(t_np, 6),
            "total_seconds": round(t_cook + t_read + t_np, 5),
        })
    except Exception as exc:
        R["timing"].append({"resolution": [w, h], "error": repr(exc)[:300]})

# -------------------------------------------------- module-level image file I/O
for name in ("saveImageDataToFile", "loadImageDataFromFile", "imageResolution"):
    obj = getattr(hou, name, None)
    R["module_level_io"][f"hou.{name}"] = {
        "exists": obj is not None,
        "type": type(obj).__name__ if obj is not None else None,
        "doc": (getattr(obj, "__doc__", "") or "")[:900],
    }

R["controls"]["controls_ok"] = bool(
    R["controls"].get("positive_match") is True
    and R["controls"].get("negative_match") is False
    and R["controls"].get("determinism_identical_bytes") is True
)
R["controls"]["stated_failure_condition"] = (
    "controls_ok is false if the authored constant did not survive the round trip, "
    "OR the decoy ALSO matched (tolerance too wide to disagree), OR two reads of "
    "one cooked buffer returned different bytes (readback nondeterministic, which "
    "would void V2's noise floor before it is measured)."
)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

c = R["controls"]
rt = R["roundtrip"]
print(f"controls_ok={c['controls_ok']}  positive={c.get('positive_match')}  "
      f"decoy(must be False)={c.get('negative_match')}  "
      f"deterministic={c.get('determinism_identical_bytes')}")
print(f"buffer={rt.get('buffer_type')} bytes={rt.get('buffer_bytes')} ch={rt.get('channel_count')} "
      f"res={rt.get('buffer_resolution')} storage={rt.get('storage_type')} "
      f"stores_int={rt.get('stores_integers')} gpu={rt.get('on_gpu')}")
print(f"authored={rt.get('authored')}\nmeasured={rt.get('measured_means')} tol={rt.get('tolerance_used')}")
for t in R["timing"]:
    print("  ", t)
print(f"wrote {OUT}")
