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
from pathlib import Path
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
            "The direction mask (enabledirection 1, maxangle 20) keeps instances on near-level ground and "
            "off walls, sills and roofs. To also drop instances too far away to read, set "
            "enablecameramaskfar 1 and cameramaskfar to a distance in metres.",
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
                           # Near-level faces only (within 20 degrees of +Y). Measured in hython on the
                           # demo lane, 2026-10-03, as height above the lane (the lane climbs 1.3 m over
                           # 45 m): at 45 degrees 73 of 763 instances sat more than 0.35 m above it, at 20
                           # degrees 12 of 758, all of them more than 26 m from the camera.
                           "enabledirection": 1, "maxangle": 20,
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
    if key == "scatter_instances":
        lines += ["", "Use the host resolver instead of discovering the five bindings individually:",
                  'synapse_solaris_build_graph({"recipe":"scatter_instances","dry_run":true})',
                  "If UNKNOWN, stop and report the missing evidence; do not guess or build.",
                  'If RESOLVED, synapse_solaris_build_graph({"recipe":"scatter_instances"}) rechecks and builds.',
                  "Pass no nodes, bindings or parameter overrides. Recipe literals win over memory, "
                  "including enabledirection=1 and maxangle=20. The sphere prototype is editable "
                  "at /prototypes/rock_a for artist material binding."]
        return "\n".join(lines)
    lines += ["", "Every node type and parm name below is verified on this build: do NOT create probe "
              "nodes, scout, or look them up again. Fill the placeholders, then make this ONE "
              "synapse_solaris_build_graph call and read its receipt (badges, wires, display):"]
    lines += ["- %s = %s" % (k, v) for k, v in r["fill"].items()]
    lines += ["", json.dumps(r["payload"], separators=(",", ":"))]
    return "\n".join(lines)


def payload(key: str, **subs: str) -> Dict[str, Any]:
    """The recipe payload with placeholders filled (keys given without the angle
    brackets, e.g. UPSTREAM='demo_cam'). Unfilled placeholders raise."""
    def fill(value):
        if isinstance(value, dict):
            return {k: fill(v) for k, v in value.items()}
        if isinstance(value, list):
            return [fill(v) for v in value]
        if isinstance(value, str):
            for name, replacement in subs.items():
                value = value.replace("<%s>" % name, str(replacement).replace("\\", "/"))
        return value
    result = fill(RECIPES[key]["payload"])
    text = json.dumps(result, sort_keys=True)
    missing = [k for k in RECIPES[key]["fill"] if k in text]
    if missing:
        raise ValueError("unfilled placeholders: %s" % ", ".join(missing))
    return result


def describe_all() -> List[Dict[str, Any]]:
    return [{"key": k, "title": r["title"], "types": list(r["types"])} for k, r in RECIPES.items()]


def resolve_scatter(hou_module, parent_path="/stage") -> Dict[str, Any]:
    """Read one supported imported-world chain; never choose between candidates.

    Must run on Houdini's main thread. Collider identity comes from the
    importer's persisted grounding provenance, not a generated filename.
    The supported splice is a Camera LOP directly feeding Render Settings.
    No memory store, remote request, geometry creation or parameter write.
    """
    bindings = {name.strip("<>"): {"value": "UNKNOWN", "source": None}
                for name in RECIPES["scatter_instances"]["fill"]}

    def unknown(reason):
        return {"status": "UNKNOWN", "recipe": "scatter_instances",
                "bindings": bindings, "reason": reason, "build_allowed": False}

    def bind(name, value, source):
        bindings[name] = {"value": str(value), "source": source}

    if parent_path != "/stage":
        return unknown("Scatter resolver supports only the /stage network")
    host_errors = tuple(cls for name in ("OperationFailed", "ObjectWasDeleted")
                        if isinstance((cls := getattr(hou_module, name, None)), type)
                        and issubclass(cls, BaseException))
    read_errors = (AttributeError, KeyError, TypeError, ValueError, OSError, RuntimeError) + host_errors
    try:
        parent = hou_module.node(parent_path)
        if parent is None:
            return unknown("LOP network is missing")
        shown = parent.displayNode()
        if shown is None:
            return unknown("LOP network has no displayed stage")
        stage = shown.stage()
        if stage is None:
            return unknown("Displayed stage is unavailable")
        cameras = [p for p in stage.Traverse() if p.GetTypeName() == "Camera"]
        if len(cameras) != 1:
            return unknown("Expected exactly one camera on the displayed stage")
        camera_path = str(cameras[0].GetPath())
        bind("CAMERA_PRIM", camera_path, shown.path() + ":stage Camera")
        chain = [shown] + list(shown.inputAncestors())
        camera_nodes = [n for n in chain if not n.isBypassed()
                        and n.type().nameComponents()[2] == "camera"
                        and n.parm("primpath") is not None
                        and n.parm("primpath").evalAsString() == camera_path]
        if len(camera_nodes) != 1:
            return unknown("Expected exactly one active Camera LOP authoring this camera")
        camera = camera_nodes[0]
        downstream = [n for n in parent.children() if not n.isBypassed()
                      and n.type().nameComponents()[2] in ("rendersettings", "karmarendersettings")
                      and n.input(0) == camera and n in chain]
        if len(downstream) != 1 or len(camera.outputs()) != 1:
            return unknown("Camera must feed exactly one Render Settings node directly")
        bind("UPSTREAM", camera.path(), camera.path() + ":primpath")
        bind("DOWNSTREAM", downstream[0].path(), downstream[0].path() + ":input[0]")
        upstream = [camera] + list(camera.inputAncestors())
        imports = [n for n in upstream if not n.isBypassed()
                   and n.type().nameComponents()[2] == "sopimport"
                   and n.userData("synapse.worldlabs")]
        if len(imports) != 1:
            return unknown("Expected exactly one provenance-bearing world import upstream")
        world = imports[0]
        root = world.parm("pathprefix").evalAsString()
        if not root.startswith("/") or root == "/" or not stage.GetPrimAtPath(root).IsValid():
            return unknown("Imported world root is not a valid live prim")
        splats = [p for p in stage.Traverse()
                  if p.GetTypeName() == "ParticleField3DGaussianSplat"
                  and (str(p.GetPath()) == root
                       or str(p.GetPath()).startswith(root.rstrip("/") + "/"))]
        if not splats:
            return unknown("World root has no live native splat prim")
        bind("WORLD_PRIM", root, world.path() + ":pathprefix + live splat descendants")
        sop = hou_module.node(world.parm("soppath").evalAsString())
        if sop is None:
            return unknown("World import SOP source is missing")
        sources = [n for n in [sop] + list(sop.inputAncestors())
                   if n.type().nameComponents()[2] == "file" and n.parm("file") is not None]
        if len(sources) != 1:
            return unknown("World source must resolve to exactly one File SOP")
        source = Path(sources[0].parm("file").evalAsString())
        provenance = json.loads(world.userData("synapse.worldlabs"))
        collider_name = provenance.get("grounding", {}).get("collider")
        if (not isinstance(collider_name, str) or not collider_name
                or Path(collider_name).name != collider_name
                or "/" in collider_name or "\\" in collider_name):
            return unknown("Import provenance does not identify a sibling collider")
        collider = source.with_name(collider_name)
        if not source.is_absolute() or not source.is_file() or not collider.is_file():
            return unknown("Recorded source or collider file is missing")
        if source.suffix.lower() != ".ply" or collider.suffix.lower() != ".glb":
            return unknown("Recorded source/collider formats are unsupported")
        # Multiple sibling candidates are unresolved, even if provenance names one.
        from synapse.worldlabs.importer import world_stem
        candidates = {source.with_name(stem + "_collider.glb")
                      for stem in (world_stem(source), source.stem)}
        present = {p.resolve() for p in candidates if p.is_file()}
        if present != {collider.resolve()}:
            return unknown("Sibling collider candidates are missing, ambiguous or contradict provenance")
        bind("COLLIDER_GLB", collider.as_posix(),
             world.path() + ":synapse.worldlabs.grounding.collider + " + sources[0].path() + ":file")
        values = {k: v["value"] for k, v in bindings.items()}
        return {"status": "RESOLVED", "recipe": "scatter_instances", "bindings": bindings,
                "build_allowed": True, "payload": payload("scatter_instances", **values),
                "limits": ["Current-frame camera mask; not occlusion or whole-move coverage",
                           "Collider association is recorded importer provenance, not a content hash"]}
    except read_errors as error:
        return unknown("Cannot read required binding evidence: %s" % error)


def scatter_request(hou_module, request: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve-only or canonical recipe execution request; no model overrides.

    Execution re-reads the scene rather than trusting a previous resolver
    payload. The caller applies the returned graph only when build_allowed.
    """
    allowed = {"recipe", "recipe_action", "parent"}
    extra = set(request) - allowed
    if extra:
        raise ValueError("Scatter recipe parameters are fixed; unsupported overrides: "
                         + ", ".join(sorted(extra)))
    if request.get("recipe") != "scatter_instances":
        raise ValueError("Only scatter_instances is supported by this resolver")
    action = request.get("recipe_action", "resolve")
    if action not in ("resolve", "build"):
        raise ValueError("recipe_action must be resolve or build")
    result = resolve_scatter(hou_module, request.get("parent", "/stage"))
    result["action"] = action
    return result


def scatter_fixed_parameters() -> Dict[str, Any]:
    """Canonical literal Scatter parms; live camera/target bindings stay separate."""
    spec = next(n for n in RECIPES["scatter_instances"]["payload"]["nodes"]
                if n.get("type") == "scatterinstances")
    return {k: copy.deepcopy(v) for k, v in spec["parms"].items()
            if not (isinstance(v, str) and "<" in v)}


def enforce_scatter_parameters(nodes):
    """Copy the graph and replace every Scatter literal with its recipe value.

    Existing references are wiring-only and never have their parms written.
    Corrections describe request normalization, not proof of a live parm write.
    """
    if not isinstance(nodes, list) or any(not isinstance(node, dict) for node in nodes):
        raise ValueError("Graph nodes must be a list of objects")
    result = copy.deepcopy(nodes)
    corrections = []
    fixed = scatter_fixed_parameters()
    for node in result:
        if node.get("existing") or "scatterinstances" not in str(node.get("type", "")).split("::"):
            continue
        parms = node.setdefault("parms", {})
        if not isinstance(parms, dict):
            raise ValueError("scatterinstances parms must be an object")
        for name, value in fixed.items():
            if name not in parms or parms[name] != value or type(parms[name]) is not type(value):
                corrections.append({"node": node.get("id"), "parm": name,
                                    "requested": parms.get(name), "fixed": value})
            parms[name] = value
    return result, corrections
