"""V1 / Q1d + Q4a — storage types, saveImageDataToFile, and the Karma parm surface.

Three questions this answers, all cheap (no render):

  1. hou.imageLayerStorageType -- does a COP buffer have an INTEGER storage type?
     If it does, the COP path can carry a mask that Karma cannot (R102's reopen).
  2. hou.saveImageDataToFile -- signature unavailable via inspect; get the real
     docstring, because a module-level image writer is the headless capture verb
     the guessed target list missed.
  3. The Karma render-var + render-settings PARM surface: what an ID AOV would
     actually be spelled as, and where the denoiser lives (Q4).

Nodes are created in a scratch LOP network in memory. Nothing is saved.

Run:  hython3.13.exe harness/notes/v1_karma_surface.py
Emits: harness/notes/v1_q1_karma_surface.json
"""
from __future__ import annotations

import json
import os
import sys

import hou

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "v1_q1_karma_surface.json")

# Node types whose parm surface is load-bearing for Q2/Q4.
LOP_TYPES = ["rendervar", "karmarenderproperties", "karmarendersettings",
             "usdrender_rop", "usdrender", "renderproduct", "rendersettings"]

DENOISE_TOKENS = ("denois", "oidn", "optix", "nvidia")
ID_TOKENS = ("id", "cryptomatte", "primid", "objectid", "element")


def enum_values(dotted):
    obj = hou
    for p in dotted.split(".")[1:]:
        obj = getattr(obj, p, None)
        if obj is None:
            return None
    return sorted(m for m in dir(obj) if not m.startswith("_") and m != "thisown")


def main() -> int:
    report = {
        "schema": "v1-q1-karma-surface/1",
        "build": hou.applicationVersionString(),
        "license": str(hou.licenseCategory()),
    }

    # --- 1. storage types ---------------------------------------------------
    report["imageLayerStorageType"] = enum_values("hou.imageLayerStorageType")
    report["imageDepth"] = enum_values("hou.imageDepth")

    # --- 2. saveImageDataToFile --------------------------------------------
    f = getattr(hou, "saveImageDataToFile", None)
    report["saveImageDataToFile"] = {
        "present": f is not None,
        "doc": (getattr(f, "__doc__", None) or "").strip() if f else None,
    }

    # --- 3. node type availability + parm surface ---------------------------
    lop_cat = hou.lopNodeTypeCategory()
    report["lop_types_present"] = {
        t: (lop_cat.nodeType(t) is not None) for t in LOP_TYPES
    }
    rop_cat = hou.ropNodeTypeCategory()
    report["rop_types_present"] = {
        t: (rop_cat.nodeType(t) is not None) for t in
        ["usdrender", "usdrender_rop", "karma", "opengl", "ifd"]
    }

    stage = hou.node("/stage")
    parm_surface = {}
    for tname in LOP_TYPES:
        if lop_cat.nodeType(tname) is None:
            continue
        try:
            n = stage.createNode(tname, f"_v1_probe_{tname}")
        except Exception as exc:  # noqa: BLE001
            parm_surface[tname] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        parms = [p.name() for p in n.parms()]
        entry = {
            "parm_count": len(parms),
            "denoise_parms": sorted(
                p for p in parms if any(t in p.lower() for t in DENOISE_TOKENS)),
            "id_parms": sorted(
                p for p in parms if any(t in p.lower() for t in ID_TOKENS)),
        }
        # Menu items for the interesting parms -- this is where the legal
        # spellings live, rather than in our guesses.
        menus = {}
        for p in n.parms():
            try:
                items = p.parmTemplate().menuItems()
            except Exception:  # noqa: BLE001
                continue
            if not items:
                continue
            low = p.name().lower()
            if any(t in low for t in DENOISE_TOKENS) or "format" in low \
                    or "datatype" in low or "sourcename" in low \
                    or "sourcetype" in low or "dataType" in low:
                menus[p.name()] = list(items)[:60]
        entry["menus"] = menus
        parm_surface[tname] = entry
        n.destroy()
    report["parm_surface"] = parm_surface

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print("imageLayerStorageType:", report["imageLayerStorageType"])
    print("imageDepth           :", report["imageDepth"])
    print("\nsaveImageDataToFile doc:\n", report["saveImageDataToFile"]["doc"])
    print("\nLOP types present:", report["lop_types_present"])
    print("ROP types present:", report["rop_types_present"])
    for t, e in parm_surface.items():
        if "error" in e:
            print(f"\n[{t}] ERROR {e['error']}")
            continue
        print(f"\n[{t}] parms={e['parm_count']}")
        print(f"   denoise: {e['denoise_parms']}")
        print(f"   id     : {e['id_parms']}")
        for pname, items in e["menus"].items():
            print(f"   menu {pname}: {items}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
