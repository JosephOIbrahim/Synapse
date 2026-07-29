"""V1 / PROBE B — Copernicus buffer readback, executed rather than inspected.

The brief flags this one specially: "documented Copernicus buffer-to-numpy
readback" is an OPEN SIDEFX ASK, so a clean path here is SURPRISING and must be
verified twice. Probe A established by full-surface diff that hou.CopNode carries
none of the legacy hou.Cop2Node readback verbs, but DOES carry a family Cop2 never
had -- layer / layerAtFrame / attrib / vdb / verb -- alongside module-level
hou.ImageLayer, hou.CopVerb and hou.saveImageDataToFile.

This probe does not ask "does the spelling resolve". It BUILDS a Copernicus
network, cooks it, and tries to get actual pixels out, then reports what the
object really is. Existence is not the question here; behaviour is.

Controls (Law 1):
  positive  the network must actually build and cook -- if node creation fails,
            every readback verdict below is UNVERIFIABLE, not ABSENT.
  negative  a deliberately wrong layer name must NOT return pixels. A readback
            that returns something for a layer that does not exist is a resolver
            that answers yes to everything, and its successes mean nothing.
  FAILS IF  the network does not build, or the wrong-layer control returns data.

Mutates nothing outside a throwaway in-memory scene in this process.
"""

from __future__ import annotations

import json
import sys
import traceback

OUT = sys.argv[1] if len(sys.argv) > 1 else "probe_b_copernicus.json"

import hou  # noqa: E402


def surface(obj, label):
    try:
        return sorted(n for n in dir(obj) if not n.startswith("_"))
    except Exception as exc:
        return f"ERROR {exc!r}"


def describe(name):
    """Module-level symbol: exists? what type? what does help() say about args?"""
    if not hasattr(hou, name):
        return {"exists": False}
    obj = getattr(hou, name)
    d = {"exists": True, "type": type(obj).__name__, "members": surface(obj, name)}
    doc = getattr(obj, "__doc__", None)
    if doc:
        d["doc"] = doc[:800]
    return d


R = {
    "probe": "V1/B Copernicus buffer readback (OPEN SIDEFX ASK -- verified twice)",
    "producer": "harness/notes/v1/probe_b_copernicus.py",
    "build": str(hou.applicationVersionString()),
    "license_category": str(hou.licenseCategory()),
    "ui_available": bool(hou.isUIAvailable()),
    "static_surfaces": {},
    "execution": {},
    "controls": {},
}

# ---------------------------------------------------------------- static half
for name in ("ImageLayer", "CopVerb", "CopNode", "CopCable", "CopCableStructure",
             "saveImageDataToFile", "loadImageDataFromFile", "imageResolution",
             "imageDepth", "imageLayerStorageType", "imageLayerTypeInfo",
             "imageLayerProjection", "imageLayerBorder"):
    R["static_surfaces"][f"hou.{name}"] = describe(name)

# ------------------------------------------------------------- execution half
ex = R["execution"]

# 1. Where do Copernicus nodes live, and what generators exist?
try:
    cat = hou.copNodeTypeCategory()
    ex["cop_category"] = cat.name()
    types = sorted(cat.nodeTypes().keys())
    ex["cop_nodetype_count"] = len(types)
    ex["cop_nodetypes_sample"] = types[:60]
    for probe_name in ("null", "color", "noise", "constant", "ramp", "checkerboard"):
        ex.setdefault("generator_candidates", {})[probe_name] = probe_name in types
except Exception:
    ex["cop_category_error"] = traceback.format_exc()

# 2. Build a Copernicus network and cook it.
built = None
try:
    parent = None
    for path, kind in (("/obj", "copnet"), ("/img", "copnet"), ("/stage", "copnet")):
        n = hou.node(path)
        if n is None:
            continue
        try:
            parent = n.createNode(kind)
            ex["copnet_parent"] = path
            ex["copnet_type"] = parent.type().name()
            break
        except Exception:
            continue
    if parent is None:
        ex["build_error"] = "could not create a copnet under /obj, /img or /stage"
    else:
        # Pick a generator that exists in this build rather than assuming one.
        gen = None
        for cand in ("color", "constant", "noise", "ramp", "checkerboard", "null"):
            try:
                gen = parent.createNode(cand)
                ex["generator_used"] = cand
                break
            except Exception:
                continue
        if gen is None:
            ex["build_error"] = "no usable Copernicus generator node type found"
        else:
            gen.setDisplayFlag(True)
            try:
                gen.cook(force=True)
                ex["cooked"] = True
            except Exception:
                ex["cooked"] = False
                ex["cook_error"] = traceback.format_exc()[-1200:]
            built = gen
            ex["generator_path"] = gen.path()
            ex["generator_class"] = type(gen).__name__
            ex["generator_is_CopNode"] = isinstance(gen, hou.CopNode)
except Exception:
    ex["build_error"] = traceback.format_exc()[-2000:]

R["controls"]["build_ok"] = built is not None and ex.get("cooked") is True

# 3. THE question: get pixels out.
readback = {}
if built is not None:
    # 3a. what layers does the node report?
    for verb in ("layer", "layerAtFrame", "attrib", "vdb", "geometry"):
        try:
            fn = getattr(built, verb, None)
            if fn is None:
                readback[verb] = {"verdict": "ABSENT"}
                continue
            val = fn() if verb in ("layer", "attrib", "vdb", "geometry") else fn(hou.frame())
            readback[verb] = {
                "verdict": "CALLED",
                "returned_type": type(val).__name__,
                "returned_is_None": val is None,
                "members": surface(val, verb) if val is not None else None,
            }
        except Exception as exc:
            readback[verb] = {"verdict": "RAISED", "error": repr(exc)[:400]}

    # 3b. if we got an ImageLayer, can it become an array?
    try:
        lay = built.layer()
        if lay is not None:
            info = {"type": type(lay).__name__}
            for m in ("allPixels", "allPixelsAsString", "asNumpyArray", "numpyArray",
                      "pixels", "asString", "resolution", "xRes", "yRes", "depth",
                      "storageType", "typeInfo", "name", "bounds", "components"):
                info[m] = hasattr(lay, m)
            R["static_surfaces"]["<returned ImageLayer instance>"] = {
                "exists": True, "type": type(lay).__name__, "members": surface(lay, "layer")
            }
            # actually try to pull data
            for m in ("allPixels", "allPixelsAsString", "asNumpyArray", "numpyArray"):
                if hasattr(lay, m):
                    try:
                        v = getattr(lay, m)()
                        info[f"{m}_result_type"] = type(v).__name__
                        info[f"{m}_len"] = len(v) if hasattr(v, "__len__") else None
                    except Exception as exc:
                        info[f"{m}_error"] = repr(exc)[:300]
            readback["ImageLayer_probe"] = info
    except Exception as exc:
        readback["ImageLayer_probe"] = {"error": repr(exc)[:400]}

    # 3c. NEGATIVE CONTROL: a layer name that cannot exist must not return data.
    try:
        bogus = built.layer("zzz_layer_that_cannot_exist_v1")
        R["controls"]["wrong_layer_returned"] = bogus is not None
        R["controls"]["wrong_layer_detail"] = (
            f"returned {type(bogus).__name__}" if bogus is not None else "returned None"
        )
        R["controls"]["negative_ok"] = bogus is None
    except Exception as exc:
        # raising on a bogus name is the CORRECT behaviour -- it discriminates
        R["controls"]["wrong_layer_returned"] = False
        R["controls"]["wrong_layer_detail"] = f"raised {exc!r}"[:300]
        R["controls"]["negative_ok"] = True
else:
    R["controls"]["negative_ok"] = None

R["readback"] = readback

# 4. numpy availability in hython -- the "buffer-to-numpy" half of the ask
try:
    import numpy  # noqa
    R["numpy_in_hython"] = {"available": True, "version": numpy.__version__}
except Exception as exc:
    R["numpy_in_hython"] = {"available": False, "error": repr(exc)}

R["controls"]["controls_ok"] = bool(
    R["controls"].get("build_ok") and R["controls"].get("negative_ok")
)
R["controls"]["stated_failure_condition"] = (
    "controls_ok is false if the Copernicus network did not build+cook (making every "
    "readback verdict UNVERIFIABLE rather than ABSENT), or if a layer name that cannot "
    "exist still returned data (making every readback SUCCESS meaningless)."
)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(f"build_ok={R['controls'].get('build_ok')} negative_ok={R['controls'].get('negative_ok')} "
      f"controls_ok={R['controls']['controls_ok']}")
print(f"generator={ex.get('generator_used')} cooked={ex.get('cooked')} "
      f"copnet_parent={ex.get('copnet_parent')}")
print(f"wrote {OUT}")
