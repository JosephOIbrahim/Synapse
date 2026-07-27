"""V1 / Q1e-2 — the CONTENT half of the Copernicus verification, done properly.

The first attempt reported INCONCLUSIVE and it was right to: it filtered for
parms named *color*/*value*, the `constant` COP names them f4r/f4g/f4b/f4a, so
nothing was set, nothing changed, and an all-1.0 buffer is indistinguishable
from a fixed default. Structural verification had passed; content had not.

Two content tests, either of which a fixed default would fail:

  1. DRIVEN VALUE   -- set f4r/f4g/f4b/f4a to a value no default would produce,
                       re-cook, re-read: the bytes must change AND decode to it.
  2. SPATIAL VARIATION -- read a node whose output varies across the image
                       (noise). A constant buffer cannot fake a gradient, so a
                       high distinct-value count is positive evidence that the
                       readback reflects the real image rather than a placeholder.

Run:   hython3.13.exe harness/notes/v1_q1_cop_content_control.py
Emits: harness/notes/v1_q1_cop_content_control.json
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
import traceback

import hou

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v1_q1_cop_content_control.json")
REPORT = {"schema": "v1-q1-cop-content-control/1",
          "build": hou.applicationVersionString()}


def flush():
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(REPORT, fh, indent=2)


def read_f32(node, ch=4, limit=64):
    node.cook(force=True)
    b = node.layer().allBufferElements(hou.imageLayerStorageType.Float32, ch)
    n = min(len(b) // 4, limit)
    return b, struct.unpack(f"<{n}f", b[:n * 4])


def main() -> int:
    hou.hipFile.clear(suppress_save_prompt=True)
    parent = hou.node("/obj").createNode("copnet", "_v1_cn")

    # ---- test 1: driven value ---------------------------------------------
    e1 = {}
    try:
        node = parent.createNode("constant", "_v1_const")
        e1["parms"] = [q.name() for q in node.parms()]
        b0, v0 = read_f32(node)
        e1["before"] = {"sha256": hashlib.sha256(b0).hexdigest()[:32],
                        "first8": list(v0[:8])}

        # `signature` defaults to 'auto', under which the constant COP drives
        # from the FLOAT1 branch (`f1`) -- not f4r/f4g/f4b/f4a. Determined by
        # setting each branch in turn and watching which one moved the buffer;
        # an earlier run of this probe set f4* and correctly reported
        # INCONCLUSIVE rather than claiming a defect in the readback.
        e1["signature"] = node.parm("signature").eval()
        VALUE = 0.15
        applied = []
        q = node.parm("f1")
        if q is None:
            applied.append({"parm": "f1", "status": "ABSENT"})
        else:
            q.set(VALUE)
            applied.append({"parm": "f1", "status": "set", "readback": q.eval()})
        e1["applied"] = applied

        b1, v1 = read_f32(node)
        e1["after"] = {"sha256": hashlib.sha256(b1).hexdigest()[:32],
                       "first8": list(v1[:8])}
        e1["bytes_changed"] = (b0 != b1)
        first_px = list(v1[:4])
        e1["first_pixel"] = first_px
        want = [VALUE, VALUE, VALUE, 1.0]
        e1["expected_first_pixel"] = want
        e1["matches_target"] = all(
            abs(a - b) < 1e-4 for a, b in zip(first_px, want))
        e1["verdict"] = ("CONFIRMED" if e1["bytes_changed"] and
                         e1["matches_target"] else "INCONCLUSIVE")
        print(f"[1] driven value: before={e1['before']['first8'][:4]} "
              f"after={first_px} want={want}")
        print(f"    bytes_changed={e1['bytes_changed']} "
              f"matches={e1['matches_target']} -> {e1['verdict']}")
    except Exception:  # noqa: BLE001
        e1["error"] = traceback.format_exc()
        print(e1["error"])
    REPORT["test1_driven_value"] = e1
    flush()

    # ---- test 2: spatial variation ----------------------------------------
    e2 = {}
    try:
        chosen, node2 = None, None
        for t in ("fractalnoise", "worleynoise", "cellularnoise", "ramp"):
            try:
                node2 = parent.createNode(t, f"_v1_{t}")
                chosen = t
                break
            except Exception:  # noqa: BLE001
                continue
        e2["node_type"] = chosen
        if node2 is None:
            e2["verdict"] = "UNVERIFIABLE: no varying source COP available"
        else:
            b, _ = read_f32(node2, limit=1)
            n = len(b) // 4
            vals = struct.unpack(f"<{n}f", b)
            distinct = len(set(vals))
            e2["element_count"] = n
            e2["distinct_values"] = distinct
            e2["min"] = min(vals)
            e2["max"] = max(vals)
            e2["sha256"] = hashlib.sha256(b).hexdigest()[:32]
            # a constant/placeholder buffer has distinct == 1
            e2["verdict"] = ("CONFIRMED: buffer varies spatially"
                             if distinct > 100 else
                             f"INCONCLUSIVE: only {distinct} distinct values")
            print(f"[2] spatial variation via {chosen}: n={n} "
                  f"distinct={distinct} min={e2['min']:.5f} max={e2['max']:.5f}")
            print(f"    -> {e2['verdict']}")
    except Exception:  # noqa: BLE001
        e2["error"] = traceback.format_exc()
        print(e2["error"])
    REPORT["test2_spatial_variation"] = e2

    REPORT["overall"] = (
        "CONFIRMED"
        if REPORT.get("test1_driven_value", {}).get("verdict") == "CONFIRMED"
        and str(REPORT.get("test2_spatial_variation", {}).get("verdict", "")
                ).startswith("CONFIRMED")
        else "PARTIAL")
    print("\noverall content verdict:", REPORT["overall"])
    flush()
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        REPORT["fatal"] = traceback.format_exc()
        flush()
        traceback.print_exc()
        sys.exit(1)
