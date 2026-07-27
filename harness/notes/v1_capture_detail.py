"""V1 / Q1c — signatures + docstrings for the capture candidates the sweep found.

The Q1b sweep surfaced four verbs the hand-written target list did not guess:
    hou.saveImageDataToFile                    module-level
    hou.GeometryViewport._captureFramebuffer   private, but present
    hou.IPRViewer.pixel / .pixels              IPR readback
    hou.GeometryViewportSettings.setUseDenoising / .useDenoising   <- Q4

This resolves what each one actually TAKES and WRITES, so the Q1 verdicts say
more than "the name resolves".

Run:  hython3.13.exe harness/notes/v1_capture_detail.py
Emits: harness/notes/v1_q1_detail.json
"""
from __future__ import annotations

import inspect
import json
import os
import sys

import hou

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "v1_q1_detail.json")

CANDIDATES = [
    "hou.saveImageDataToFile",
    "hou.SceneViewer.flipbook",
    "hou.SceneViewer.flipbookSettings",
    "hou.GeometryViewport._captureFramebuffer",
    "hou.GeometryViewport.resolutionInPixels",
    "hou.GeometryViewport.queryPrimAtPixel",
    "hou.GeometryViewport.queryNodeAtPixel",
    "hou.GeometryViewportSettings.useDenoising",
    "hou.GeometryViewportSettings.setUseDenoising",
    "hou.IPRViewer.pixel",
    "hou.IPRViewer.pixels",
    "hou.IPRViewer.startRender",
    "hou.IPRViewer.killRender",
    "hou.CopNode.layer",
    "hou.ImageLayer.allBufferElements",
    "hou.ImageLayer.bufferResolution",
    "hou.ImageLayer.bufferToImage",
    "hou.Cop2Node.allPixels",
    "hou.Cop2Node.getPixelByUV",
    "hou.RopNode.render",
    "hou.RopNode.addRenderEventCallback",
]

# Full member dumps for the classes whose complete surface is load-bearing.
FULL_DUMP = [
    "hou.FlipbookSettings",
    "hou.ImageLayer",
    "hou.IPRViewer",
    "hou.GeometryViewport",
]


def resolve(dotted):
    obj = hou
    for p in dotted.split(".")[1:]:
        try:
            obj = getattr(obj, p)
        except Exception as exc:  # noqa: BLE001
            return None, f"{type(exc).__name__}: {exc}"
    return obj, None


def describe(obj):
    d = {"type": type(obj).__name__}
    try:
        d["signature"] = str(inspect.signature(obj))
    except Exception as exc:  # noqa: BLE001
        d["signature"] = f"<unavailable: {type(exc).__name__}>"
    doc = getattr(obj, "__doc__", None)
    d["doc"] = (doc or "").strip()[:600] or None
    return d


def main() -> int:
    report = {
        "schema": "v1-q1-detail/1",
        "build": hou.applicationVersionString(),
        "license": str(hou.licenseCategory()),
        "candidates": {},
        "full_dumps": {},
    }

    for dotted in CANDIDATES:
        obj, err = resolve(dotted)
        if obj is None:
            report["candidates"][dotted] = {"present": False, "error": err}
        else:
            e = {"present": True}
            e.update(describe(obj))
            report["candidates"][dotted] = e

    for dotted in FULL_DUMP:
        cls, err = resolve(dotted)
        if cls is None:
            report["full_dumps"][dotted] = {"error": err}
        else:
            report["full_dumps"][dotted] = {
                "members": sorted(m for m in dir(cls) if not m.startswith("__"))
            }

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    for dotted, e in report["candidates"].items():
        if not e.get("present"):
            print(f"  ABSENT   {dotted}   ({e['error']})")
            continue
        print(f"  PRESENT  {dotted}{e['signature']}")
        if e.get("doc"):
            first = e["doc"].splitlines()[0][:150]
            print(f"           doc: {first}")
    print("\n--- hou.FlipbookSettings full member list ---")
    print(", ".join(report["full_dumps"]["hou.FlipbookSettings"]["members"]))
    print("\n--- hou.IPRViewer full member list ---")
    print(", ".join(report["full_dumps"]["hou.IPRViewer"]["members"]))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
