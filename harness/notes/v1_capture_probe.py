"""V1 / Q1 — capture-verb inventory on the live build.

PRODUCER PATH for every Q1 verdict in harness/notes/receipts/V1.json.

Method (R58's control, applied to probes): dump the COMPLETE dir() of each class
rather than keyword-searching for a spelling we hope exists. A full member list
is simultaneously the evidence for a CONFIRMED verdict and the same-class
positive control R50 requires for an ABSENT one -- if the list is non-empty, the
class resolved and we asked the right object.

R50: ABSENT requires a positive control ON THE SAME CLASS. Where the class
itself cannot be reached in this interpreter (headless GUI submodules), the
verdict is UNVERIFIABLE, never ABSENT (H3a-F5).

Run:  hython3.13.exe harness/notes/v1_capture_probe.py
Emits: harness/notes/v1_q1_symbols.json
"""
from __future__ import annotations

import json
import os
import sys
import traceback

import hou

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "v1_q1_symbols.json")

# (dotted_name, [spellings to adjudicate on that class])
# Spellings are drawn from: the brief, retina/ingest.py, CLAUDE.md, and the
# quarantined-absent list. Guessed spellings are INTENTIONAL here -- the point
# is to adjudicate them, and a full dir() dump is what licenses the verdict.
TARGETS = {
    # --- A. flipbook / viewport capture -------------------------------------
    "hou.SceneViewer": [
        "flipbook", "flipbookSettings", "saveViewToFile", "screenshot",
        "curViewport", "setCurrentState",
    ],
    "hou.FlipbookSettings": [
        "output", "outputToMPlay", "frameRange", "resolution", "useResolution",
        "cropOutMaskOverlay", "beautyPassOnly", "antialias", "sessionLabel",
    ],
    "hou.GeometryViewport": [
        "saveViewToFile", "flipbook", "screenshot", "resolution", "name",
    ],
    "hou.PaneTab": ["type", "pane"],

    # --- B. rop / render ----------------------------------------------------
    "hou.RopNode": [
        "render", "cancel", "abort", "interrupt", "stop", "kill", "killRender",
        "addRenderEventCallback", "removeRenderEventCallback", "bypass",
    ],
    "hou.IPRViewer": ["killRender", "startRender", "isActive", "pauseRender"],

    # --- C. Copernicus readback (OPEN SIDEFX ASK -- verify twice) -----------
    "hou.CopNode": [
        "layer", "layers", "allBufferElements", "allPixels", "planes",
        "getPixel", "xRes", "yRes", "cookLayer", "dataLayer", "saveImage",
    ],
    "hou.ImageLayer": [
        "allBufferElements", "bufferElement", "xres", "yres", "name",
        "dataType", "numComponents",
    ],
    # SAME-CLASS POSITIVE CONTROL CLASS for the legacy readback spellings:
    # if allPixels/planes/getPixel/xRes resolve HERE and not on hou.CopNode,
    # the CopNode ABSENT verdicts are about CopNode, not about our spelling.
    "hou.Cop2Node": [
        "allPixels", "planes", "getPixel", "xRes", "yRes", "saveImage",
    ],

    # --- D. misc capture-adjacent ------------------------------------------
    "hou.LopNode": ["stage", "editableStage", "displayNode"],
    "hou.Node": ["render", "cook", "type", "path"],
}

# Module-level names (not classes) -- probed separately, presence only.
MODULE_TARGETS = [
    "hou.ui",
    "hou.qt",
    "hou.hscript",
    "hou.ActiveRender",      # R73: documented #status:ni, expect ABSENT
    "hou.activeRenders",     # R73: same
    "hou.InterruptableOperation",
    "hou.SceneViewer",
    "hou.FlipbookSettings",
    "hou.CopNode",
    "hou.Cop2Node",
    "hou.ImageLayer",
    "hou.IPRViewer",
    "hou.GeometryViewport",
]


def resolve(dotted: str):
    """Return (obj, None) or (None, 'reason')."""
    parts = dotted.split(".")
    assert parts[0] == "hou"
    obj = hou
    for p in parts[1:]:
        try:
            obj = getattr(obj, p)
        except Exception as exc:  # noqa: BLE001
            return None, f"{type(exc).__name__}: {exc}"
    return obj, None


def main() -> int:
    report = {
        "schema": "v1-q1-symbols/1",
        "build": hou.applicationVersionString(),
        "python": sys.version.split()[0],
        "license": str(hou.licenseCategory()),
        "interpreter": sys.executable,
        "headless": True,
        "classes": {},
        "modules": {},
    }

    for dotted, spellings in TARGETS.items():
        cls, err = resolve(dotted)
        entry = {"resolved": cls is not None, "error": err}
        if cls is None:
            # Class unreachable -> every spelling on it is UNVERIFIABLE (R50).
            entry["verdict_class"] = "UNVERIFIABLE"
            entry["members"] = None
            entry["member_count"] = 0
            entry["spellings"] = {s: "UNVERIFIABLE" for s in spellings}
        else:
            members = sorted(dir(cls))
            entry["verdict_class"] = "RESOLVED"
            entry["members"] = members
            entry["member_count"] = len(members)
            # The positive control IS the non-empty member list.
            entry["positive_control"] = {
                "kind": "same-class full dir() non-empty",
                "member_count": len(members),
                "sample": members[:8],
            }
            entry["spellings"] = {
                s: ("CONFIRMED" if hasattr(cls, s) else "ABSENT") for s in spellings
            }
        report["classes"][dotted] = entry

    for dotted in MODULE_TARGETS:
        obj, err = resolve(dotted)
        report["modules"][dotted] = {
            "present": obj is not None,
            "error": err,
            "repr": (repr(obj)[:160] if obj is not None else None),
        }

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    # Human-readable tail so the run is legible in the transcript.
    print(f"BUILD {report['build']}  LIC {report['license']}")
    for dotted, e in report["classes"].items():
        if not e["resolved"]:
            print(f"  {dotted:24s} CLASS-UNREACHABLE ({e['error']})")
            continue
        conf = [s for s, v in e["spellings"].items() if v == "CONFIRMED"]
        absent = [s for s, v in e["spellings"].items() if v == "ABSENT"]
        print(f"  {dotted:24s} members={e['member_count']:4d}"
              f"  CONFIRMED={conf}  ABSENT={absent}")
    print("--- modules ---")
    for dotted, e in report["modules"].items():
        print(f"  {dotted:28s} present={e['present']}  {e['error'] or ''}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
