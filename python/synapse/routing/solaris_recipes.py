"""Verified H22 Solaris workflow recipes (the Pieke pack, 10/1).

Each recipe is ONE synapse_solaris_build_graph call that splices new LOPs into an
existing chain (Chain Insertion Pattern: the upstream and downstream nodes are
``existing: true`` and the last wire is ``insert: true``). Every node type and
parm name here was probed and built on Houdini 22.0.400 with zero error or
warning badges; see .token-saver/pack/recipes_proof.json for the receipt.

Why this exists: the 10/1 baseline (bench3) put three of Rob Pieke's H22 Solaris
workflows to the panel worker and none was built. The knowledge index answered
exact type names well but had no bridge from the artist's words ("blocker",
"light filter", "render pass") to the types, so the model guessed fifteen type
names, or fell back to the pre-H22 workflow. KnowledgeIndex.lookup serves these
recipes for those words, before any other strategy.

Placeholders in a payload are written <LIKE_THIS>; the recipe text says how to
fill each one. ``payload(key, **subs)`` fills them (tests and the proof use it).
"""
from __future__ import annotations

import copy
import json
from typing import Any, Dict, FrozenSet, List, Optional

RECIPES: Dict[str, Dict[str, Any]] = {
    "scatter_instances": {
        "title": "Scatter Instances on a surface, masked to a camera (H22 Lop/scatterinstances)",
        "types": ["reference", "configureprimitive", "sphere", "scatterinstances"],
        "triggers": [{"scatterinstances"}, {"scatter", "instances"}, {"scatter", "instance"},
                     {"scatter", "lop"}, {"scatter", "solaris"}, {"scatter", "prototypes"},
                     {"scatter", "camera"}],
        "notes": [
            "scatterinstances needs a Mesh target. A Gaussian-splat world has none: reference its collider "
            "instead. The collider sits in the same folder as the splat .ply (read the `file` parm of the "
            "SOURCE_PLY file SOP under the world's /obj node) and its name DROPS the point-count tag: "
            "narrow_lane_500k.ply -> narrow_lane_collider.glb. Reference it UNDER the world prim so it "
            "inherits the world's scale and ground offset; the recipe then hides it from render.",
            "The camera mask reads the camera PRIM, so splice the scatter in AFTER the node that authors "
            "the camera (e.g. after the camera LOP, before render settings), not before it.",
            "Multiparms are zero-based: protogroupprims0 / protogroupweight0 is the first group.",
            "executionmode menu: 0 Deferred (render-time procedural), 1 Immediate (instances on the stage "
            "now; use this so the viewport and a stage check see them). scattermethod: 0 Number, 1 Density, "
            "2 Face Centroids.",
        ],
        "fill": {
            "<UPSTREAM>": "the existing node to splice after (the camera LOP's node)",
            "<DOWNSTREAM>": "the existing node it currently feeds (e.g. render settings)",
            "<COLLIDER_GLB>": "absolute path of the *_collider.glb beside the splat .ply",
            "<WORLD_PRIM>": "the world's prim, e.g. /World/cobblestone_lane",
            "<CAMERA_PRIM>": "the camera prim, e.g. /cameras/demo_cam",
        },
        "payload": {
            "parent": "/stage",
            "nodes": [
                {"id": "up", "existing": True, "name": "<UPSTREAM>"},
                {"id": "collider", "type": "reference", "name": "scatter_collider",
                 "parms": {"filepath1": "<COLLIDER_GLB>", "primpath1": "<WORLD_PRIM>/collider"}},
                {"id": "hide", "type": "configureprimitive", "name": "hide_collider",
                 "parms": {"primpattern": "<WORLD_PRIM>/collider", "setvisibility": 1,
                           "visibility": "invisible"}},
                {"id": "proto", "type": "sphere", "name": "rock_proto",
                 "parms": {"primpath": "/prototypes/rock_a", "scale": 0.06}},
                {"id": "scatter", "type": "scatterinstances", "name": "scatter_rocks",
                 "parms": {"primpath": "/World/scatter_rocks",
                           "scattertargetgeometry": "<WORLD_PRIM>/collider/**",
                           "scattercount": 2000, "executionmode": 1,
                           "enablecameramask": 1, "enablecamera": 1, "camerapath": "<CAMERA_PRIM>",
                           "protopattern": "/prototypes/*", "hideprotosourceprims": 1,
                           "protogroups": 1, "protogroupprims0": "/prototypes/rock_a",
                           "protogroupweight0": 1.0}},
                {"id": "down", "existing": True, "name": "<DOWNSTREAM>"},
            ],
            "connections": [
                {"from": "up", "to": "collider"}, {"from": "collider", "to": "hide"},
                {"from": "hide", "to": "proto"}, {"from": "proto", "to": "scatter"},
                {"from": "scatter", "to": "down", "input": 0, "insert": True},
            ],
        },
    },
    "karma_blocker": {
        "title": "Karma blocker light filter bound to a light (H22 Lop/karmablockerlightfilter)",
        "types": ["karmablockerlightfilter", "light"],
        "triggers": [{"blocker"}, {"light", "filter"}, {"lightfilter"}, {"light", "filters"},
                     {"karmablockerlightfilter"}, {"karma", "blocker"}, {"light", "blocker"}],
        "notes": [
            "The node type is karmablockerlightfilter (not lightfilter, karmablocker, barndoors or gobo).",
            "Shape: xn__inputsshape_zta, menu sphere / capsule / box. Place and size the blocker with its "
            "own t / r / s / scale parms.",
            "Bind it on the LIGHT: the light's xn__lightfilters_lva parm takes the filter prim path, which "
            "authors the light:filters relationship.",
            "Light LOP type is `light` with lighttype UsdLuxDistantLight / UsdLuxRectLight / "
            "UsdLuxSphereLight / UsdLuxDiskLight / UsdLuxCylinderLight / point.",
        ],
        "fill": {
            "<UPSTREAM>": "the existing node to splice after",
            "<DOWNSTREAM>": "the existing node it currently feeds",
        },
        "payload": {
            "parent": "/stage",
            "nodes": [
                {"id": "up", "existing": True, "name": "<UPSTREAM>"},
                {"id": "blocker", "type": "karmablockerlightfilter", "name": "key_blocker",
                 "parms": {"primpath": "/lights/filters/key_blocker", "xn__inputsshape_zta": "box"}},
                {"id": "key", "type": "light", "name": "blocked_key",
                 "parms": {"lighttype": "UsdLuxDistantLight",
                           "xn__lightfilters_lva": "/lights/filters/key_blocker",
                           "xn__inputsexposure_vya": 0.5, "rx": -12, "ry": -60}},
                {"id": "down", "existing": True, "name": "<DOWNSTREAM>"},
            ],
            "connections": [
                {"from": "up", "to": "blocker"}, {"from": "blocker", "to": "key"},
                {"from": "key", "to": "down", "input": 0, "insert": True},
            ],
        },
    },
    "render_passes": {
        "title": "Render passes as USD RenderPass prims (H22 Lop/renderpass)",
        "types": ["renderpass"],
        "triggers": [{"render", "pass"}, {"render", "passes"}, {"renderpass"}, {"renderpasses"},
                     {"beauty", "pass"}],
        "notes": [
            "H22 splits a shot into passes with Render Pass LOPs (UsdRenderPass prims), not extra "
            "usdrender ROPs or prune branches.",
            "Which prims a pass renders: xn__collectionrenderVisibility_jjb, a prim pattern. The recipe "
            "includes the lights ('<ISOLATE_PRIM> /lights') because an isolated pass without them would "
            "likely render unlit. The prims and relationships are verified; a render of the pass is not "
            "yet, so do not describe how the pass will look.",
            "Splice the passes in BEFORE the render settings node so they are on the displayed stage.",
        ],
        "fill": {
            "<UPSTREAM>": "the existing node to splice after (e.g. the camera LOP's node)",
            "<DOWNSTREAM>": "the render settings node it currently feeds",
            "<ISOLATE_PRIM>": "the prim the isolated pass keeps, e.g. /World/cobblestone_lane",
        },
        "payload": {
            "parent": "/stage",
            "nodes": [
                {"id": "up", "existing": True, "name": "<UPSTREAM>"},
                {"id": "beauty", "type": "renderpass", "name": "pass_beauty",
                 "parms": {"primpath": "/Render/Passes/beauty"}},
                {"id": "isolate", "type": "renderpass", "name": "pass_isolate",
                 "parms": {"primpath": "/Render/Passes/isolate",
                           "xn__collectionrenderVisibility_jjb": "<ISOLATE_PRIM> /lights"}},
                {"id": "down", "existing": True, "name": "<DOWNSTREAM>"},
            ],
            "connections": [
                {"from": "up", "to": "beauty"}, {"from": "beauty", "to": "isolate"},
                {"from": "isolate", "to": "down", "input": 0, "insert": True},
            ],
        },
    },
}


_TYPE_TO_RECIPE: Dict[str, str] = {
    "scatterinstances": "scatter_instances",
    "karmablockerlightfilter": "karma_blocker",
    "renderpass": "render_passes",
}


def match(query_words) -> Optional[str]:
    """The recipe key whose trigger set is fully contained in the query words, else None.

    Most specific (largest) trigger wins; ties go to registry order. A bare type
    name that is the WHOLE query does not match here, so the datasheet for that
    type stays reachable (the datasheet points back to the recipe instead)."""
    words = frozenset(w.lower() for w in query_words)
    if len(words) == 1 and next(iter(words)) in _TYPE_TO_RECIPE:
        return None
    best, best_size = None, 0
    for key, recipe in RECIPES.items():
        for trig in recipe["triggers"]:
            if trig <= words and len(trig) > best_size:
                best, best_size = key, len(trig)
    return best


def recipe_for_type(node_type: str) -> Optional[str]:
    return _TYPE_TO_RECIPE.get((node_type or "").lower())


def render(key: str) -> str:
    """The recipe as the lookup's answer: what to know, then the one call to make."""
    r = RECIPES[key]
    lines = ["VERIFIED RECIPE (Houdini 22.0.400, built with 0 error/warning badges): " + r["title"], ""]
    lines += ["- " + n for n in r["notes"]]
    lines += ["", "Every node type and parm name below is verified on this build: do NOT create probe "
              "nodes, scout, or look them up again. Fill the placeholders, then make this ONE "
              "synapse_solaris_build_graph call and read its receipt (badges, wires, display):"]
    lines += ["- %s = %s" % (k, v) for k, v in r["fill"].items()]
    lines += ["", json.dumps(r["payload"], separators=(",", ":"))]
    return "\n".join(lines)


def payload(key: str, **subs: str) -> Dict[str, Any]:
    """The recipe payload with placeholders filled (keys given without the angle
    brackets, e.g. UPSTREAM='demo_cam'). Unfilled placeholders raise."""
    text = json.dumps(RECIPES[key]["payload"])
    for name, value in subs.items():
        text = text.replace("<%s>" % name, str(value).replace("\\", "/"))
    missing = [k for k in RECIPES[key]["fill"] if k in text]
    if missing:
        raise ValueError("unfilled placeholders: %s" % ", ".join(missing))
    return json.loads(text)


def describe_all() -> List[Dict[str, Any]]:
    return [{"key": k, "title": r["title"], "types": list(r["types"])} for k, r in RECIPES.items()]
