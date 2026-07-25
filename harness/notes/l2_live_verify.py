"""L2 LIVE tier: run the five Solaris wiring verifiers inside hython 22.0.368."""
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "python"))

import hou  # noqa: E402

from synapse.validation.solaris import (  # noqa: E402
    verify_wiring_common as common,
    verify_scene_template as v_scene,
    verify_import_megascans as v_mega,
    verify_create_variants as v_var,
    verify_set_purpose as v_purpose,
    verify_tool_audit as v_audit,
)

out = {"build": hou.applicationVersionString(), "results": {}}
assert out["build"] == common.PINNED_BUILD, out["build"]

stage = hou.node("/stage")


def run(label, fn):
    try:
        out["results"][label] = fn()
    except Exception as exc:
        out["results"][label] = {"status": "ERROR", "error": repr(exc)[:400]}


# --- scene_template -------------------------------------------------------
def _scene():
    net = stage.createNode("lopnet", "l2_scene")
    return v_scene.verify_live(net)


run("scene_template.live", _scene)


# --- import_megascans -----------------------------------------------------
def _mega():
    net = stage.createNode("lopnet", "l2_mega")
    return v_mega.verify_live(net)


run("import_megascans.live", _mega)


# --- create_variants ------------------------------------------------------
def _variants():
    net = stage.createNode("lopnet", "l2_var")
    comp = net.createNode("subnet", "component")
    geo = comp.createNode("componentgeometry", "geo_base")
    mat = comp.createNode("componentmaterial", "mat_base")
    o = comp.createNode("componentoutput", "output_base")
    mat.setInput(0, geo)
    o.setInput(0, mat)
    return v_var.verify_live(comp, "geometry")


run("create_variants.live", _variants)


# --- set_purpose ----------------------------------------------------------
def _purpose():
    net = stage.createNode("lopnet", "l2_purpose")
    return v_purpose.verify_live(net)


run("set_purpose.live", _purpose)

# --- tool_audit (static only, no network) ---------------------------------
run("tool_audit.registration", v_audit.verify_registration)

print("LIVE_JSON_START")
print(json.dumps(out, indent=2))
print("LIVE_JSON_END")
