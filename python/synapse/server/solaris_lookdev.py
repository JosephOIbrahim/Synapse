"""Fixed Solaris + modern Copernicus lookdev trial, qualified on 22.0.400.

This is a private implementation of the existing graph command, not a general
cross-context graph executor. All host access is owned by the caller's main
thread. Construction does not render, export, or claim measured image quality.
"""

from contextlib import nullcontext
import math
from pathlib import Path
import re

from .copernicus_texture import build_procedural_texture, validate_texture_settings


TEMPLATE = "copernicus_lookdev"
QUALIFIED_BUILD = "22.0.400"
RESOLUTION = [256, 256]


def validate_request(payload):
    """Validate the entire fixed-template surface before any host mutations."""
    allowed = {"parent", "template", "template_params", "nodes", "connections",
               "display_node", "layout", "relayout", "dry_run"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise ValueError("Unsupported copernicus_lookdev request fields")
    if payload.get("template") != TEMPLATE:
        raise ValueError("Expected the copernicus_lookdev template")
    if any(payload.get(key, []) != [] for key in ("nodes", "connections")):
        raise ValueError("copernicus_lookdev has fixed topology; node/connection overlays are not supported")
    if payload.get("display_node") is not None or payload.get("relayout", False) is not False:
        raise ValueError("copernicus_lookdev preserves outer display and never rearranges existing nodes")
    if type(payload.get("dry_run", False)) is not bool:
        raise ValueError("dry_run must be a boolean")
    orientation = payload.get("layout", "vertical")
    if orientation not in ("vertical", "horizontal"):
        raise ValueError("layout must be vertical or horizontal")
    parent = payload.get("parent", "/stage")
    if not isinstance(parent, str) or not re.fullmatch(r"(?:/[A-Za-z0-9_]+)+", parent):
        raise ValueError("parent must be an absolute Houdini network path")
    params = payload.get("template_params", {})
    if not isinstance(params, dict) or set(params) - {"name", "base_color", "noise_type", "frequency", "octaves"}:
        raise ValueError("Supported lookdev parameters: name, base_color, noise_type, frequency, octaves")
    name = params.get("name", "synapse_lookdev")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name):
        raise ValueError("name must start with a letter or underscore and contain at most 64 letters, digits or underscores")
    color = params.get("base_color", [0.18, 0.04, 0.01])
    if (not isinstance(color, (list, tuple)) or len(color) != 3
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not 0 <= v <= 1 for v in color)):
        raise ValueError("base_color must contain three finite scene-linear RGB values between 0 and 1")
    noise_type = params.get("noise_type", "perlin")
    octaves = params.get("octaves", 3)
    frequency, resolution = validate_texture_settings(noise_type, params.get("frequency", 4.0), octaves, RESOLUTION, "roughness")
    return {"parent": parent, "name": name, "base_color": list(color),
            "noise_type": noise_type, "frequency": frequency, "octaves": octaves,
            "resolution": resolution, "layout": orientation, "dry_run": payload.get("dry_run", False)}


def _set(node, name, value):
    parm = node.parm(name)
    if parm is None:
        raise RuntimeError(f"{node.path()} is missing parameter {name}")
    try:
        parm.set(value)
    except Exception as error:
        raise RuntimeError(f"Could not set {node.path()}/{name}: {error}") from error
    actual = parm.evalAsString() if isinstance(value, str) else parm.eval()
    matches = (actual == value if isinstance(value, (str, int))
               else math.isclose(actual, value, rel_tol=1e-6, abs_tol=1e-8))
    if not matches:
        raise RuntimeError(f"{node.path()}/{name}: expected {value!r}, observed {actual!r}")


def _wire(target, source, index=0, output=0):
    target.setInput(index, source, output)
    wires = [c for c in target.inputConnections() if c.inputIndex() == index]
    if len(wires) != 1 or wires[0].inputNode() != source or wires[0].outputIndex() != output:
        raise RuntimeError(f"Connection readback failed at {target.path()} input {index}")


def _material_wire(material, label, data_type, source):
    """H22's semantic ports are labels; internal names are input1, input2, ..."""
    labels, types = material.inputLabels(), material.inputDataTypes()
    indices = [i for i, value in enumerate(labels) if value == label]
    if len(indices) != 1 or types[indices[0]] != data_type:
        raise RuntimeError(f"USD Material requires one {label} port of type {data_type}")
    if source.outputDataTypes() != (data_type,):
        raise RuntimeError(f"{label} source must have exactly one {data_type} output")
    _wire(material, source, indices[0])
    return {"label": label, "name": material.inputNames()[indices[0]], "index": indices[0],
            "type": data_type, "source": source.path(), "output": 0}


def _create(parent, type_name, name, category):
    if parent.node(name) is not None:
        raise ValueError(f"Refusing to replace existing node {parent.path()}/{name}")
    node = parent.createNode(type_name, name, exact_type_name=True, run_init_scripts=False)
    if node.type().name() != type_name or node.type().category().name() != category or node.name() != name:
        raise RuntimeError(f"Houdini substituted the requested {category}/{type_name} at {node.path()}")
    return node


def _outer_flags(parent):
    return {node.path(): {"id": node.sessionId(), "flag": bool(node.isDisplayFlagSet())}
            for node in parent.children() if callable(getattr(node, "isDisplayFlagSet", None))}


def _restore_flags(parent, before, owned_node=None, first_display=False):
    owned_path = None
    owned_id = None
    if owned_node is not None:
        try:
            owned_path, owned_id = owned_node.path(), owned_node.sessionId()
        except Exception as error:
            raise RuntimeError("The owned lookdev scope was removed or replaced") from error
    current = {node.path(): node for node in parent.children()
               if callable(getattr(node, "isDisplayFlagSet", None))}
    # Check identity and ownership before invoking a single setter. A path may
    # have been replaced; restoring that new object's flags would edit someone else's work.
    for path, state in before.items():
        if path not in current or current[path].sessionId() != state["id"]:
            raise RuntimeError(f"Original display node was removed or replaced: {path}")
    unexpected = set(current) - set(before) - ({owned_path} if owned_path else set())
    if unexpected:
        raise RuntimeError("Unowned nodes appeared during construction; display was not changed: " + ", ".join(sorted(unexpected)))
    if owned_path is not None and (owned_path not in current or current[owned_path].sessionId() != owned_id):
        raise RuntimeError("The owned lookdev scope was removed or replaced")
    expected = {path: state["flag"] for path, state in before.items()}
    if owned_path in current:
        expected[owned_path] = first_display
    for path, flag in expected.items():
        node = current[path]
        if bool(node.isDisplayFlagSet()) != flag:
            node.setDisplayFlag(flag)
    if any(bool(current[path].isDisplayFlagSet()) != flag for path, flag in expected.items()):
        raise RuntimeError("Could not restore the original outer display state")
    return next((path for path, flag in expected.items() if flag), None)


def _verify_stage(output, mesh_path, material_path, color, roughness, camera_path, settings_path):
    stage = output.stage(ignore_errors=False)
    if stage is None or output.errors():
        raise RuntimeError(f"Lookdev output did not compose cleanly: {output.errors()}")
    mesh = stage.GetPrimAtPath(mesh_path)
    if not mesh or mesh.GetTypeName() != "Mesh" or len(mesh.GetAttribute("points").Get() or []) != 4:
        raise RuntimeError("The expected four-point lookdev fixture is missing")
    uv = mesh.GetAttribute("primvars:st")
    values = uv.Get() if uv else None
    indices = mesh.GetAttribute("primvars:st:indices").Get()
    counts = mesh.GetAttribute("faceVertexCounts").Get()
    vertices = mesh.GetAttribute("faceVertexIndices").Get()
    if (not uv or uv.GetMetadata("interpolation") != "faceVarying" or values is None or len(values) != 4
            or list(counts or []) != [4] or sorted(vertices or []) != [0, 1, 2, 3]):
        raise RuntimeError("The lookdev fixture has no qualified four-corner UV topology")
    coordinates = [tuple(value) for value in values]
    if (any(len(value) != 2 or any(not math.isfinite(v) for v in value) for value in coordinates)
            or set(coordinates) != {(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)}
            or (indices is not None and sorted(indices) != [0, 1, 2, 3])):
        raise RuntimeError("The lookdev UVs must span the four finite unit-square corners")
    binding = [str(p) for p in mesh.GetRelationship("material:binding").GetTargets()]
    if binding != [material_path]:
        raise RuntimeError(f"Material binding mismatch: {binding!r}")
    material = stage.GetPrimAtPath(material_path)
    if not material or material.GetTypeName() != "Material":
        raise RuntimeError("The expected USD material is missing")
    sources = {}
    for attribute, source in (("base_color_file", color), ("specular_roughness_file", roughness)):
        asset = material.GetAttribute("inputs:" + attribute).Get()
        expected = f"op:{source.path()}{{{source.outputNames()[0]}}}"
        if asset is None or asset.path != expected or asset.resolvedPath != expected:
            raise RuntimeError(f"Material source mismatch for {attribute}: {asset!r}; expected {expected}")
        sources[attribute] = expected
    for attr, expected in (("base_color", (1, 1, 1)), ("base_color_primvar", ""),
                           ("specular_roughness", 1), ("roughness_primvar", ""), ("uv_primvar", "st")):
        actual = material.GetAttribute("inputs:" + attr).Get()
        if (tuple(actual) if attr == "base_color" and actual is not None else actual) != expected:
            raise RuntimeError(f"Material multiplier/UV mismatch for {attr}: {actual!r}")
    surface = material.GetAttribute("outputs:mtlx:surface").GetConnections()
    if len(surface) != 1 or not stage.GetAttributeAtPath(surface[0]):
        raise RuntimeError("The MaterialX surface does not resolve")
    camera = stage.GetPrimAtPath(camera_path)
    settings = stage.GetPrimAtPath(settings_path)
    if not camera or camera.GetTypeName() != "Camera" or not settings or settings.GetTypeName() != "RenderSettings":
        raise RuntimeError("The preview camera or settings are missing")
    if [str(p) for p in settings.GetRelationship("camera").GetTargets()] != [camera_path]:
        raise RuntimeError("The render settings do not use the lookdev camera")
    if list(settings.GetAttribute("resolution").Get() or []) != RESOLUTION:
        raise RuntimeError("The composed preview resolution must be 256 by 256")
    return {"geometry": mesh_path, "material": material_path, "binding": binding,
            "uv": "faceVarying st", "texture_sources": sources, "camera": camera_path,
            "render_settings": settings_path, "usd": "verified",
            "texture_pixels": "not measured", "rendered_appearance": "not checked"}


def build_lookdev(hou, settings):
    """Build a validated request on the main thread; remove only our new root on failure."""
    if hou.applicationVersionString() != QUALIFIED_BUILD:
        raise ValueError(f"copernicus_lookdev is qualified on Houdini {QUALIFIED_BUILD}; current build is {hou.applicationVersionString()}")
    parent = hou.node(settings["parent"])
    if parent is None or parent.childTypeCategory() is None or parent.childTypeCategory().name() != "Lop" or not parent.isEditable():
        raise ValueError("copernicus_lookdev needs an editable Solaris LOP network")
    if parent.node(settings["name"]) is not None:
        raise ValueError("That lookdev name already exists. Choose a new name; existing work is never reused or overwritten.")
    for required in ("subnet", "sopnet", "sopimport", "texturemateriallibrary", "camera", "light", "karmarendersettings"):
        if required not in parent.childTypeCategory().nodeTypes():
            raise RuntimeError(f"Required Houdini node is unavailable: {required}")
    first_display = not parent.children()
    before = _outer_flags(parent)
    root_path = parent.path() + "/" + settings["name"]
    display_before = next((p for p, state in before.items() if state["flag"]), None)
    if settings["dry_run"]:
        return {"status": "preview", "dry_run": True, "template": TEMPLATE,
                "planned_root": root_path, "resolution": list(RESOLUTION),
                "planned_display": root_path if first_display else display_before,
                "display_node": display_before, "nodes_created": [],
                "verification": {"configuration": "not built", "usd": "not checked", "rendered_appearance": "not checked"}}
    positions = [n.position() for n in parent.children()]
    root = None
    cleaned = False
    cleanup_error = None

    def cleanup(error):
        nonlocal root, cleaned
        residue = []
        if root is not None:
            try:
                root.destroy()
                root = None
            except Exception as exc:
                residue.append(f"{root_path}: {exc}")
        if parent.node(settings["name"]) is not None:
            residue.append(root_path)
        try:
            _restore_flags(parent, before, root, first_display)
        except Exception as exc:
            residue.append(str(exc))
        cleaned = True
        if residue:
            raise RuntimeError(f"{error}; cleanup incomplete, inspect: {'; '.join(residue)}") from error

    try:
        with hou.undos.group("SYNAPSE: Copernicus lookdev"):
            try:
                from .update_mode import cook_sandwich
                with cook_sandwich(label="copernicus_lookdev"):
                    # Hold ownership before checking the returned type so a
                    # substituted root can still be removed on failure.
                    root = parent.createNode("subnet", settings["name"], exact_type_name=True, run_init_scripts=False)
                    if root.type().name() != "subnet" or root.type().category().name() != "Lop" or root.path() != root_path:
                        raise RuntimeError("Houdini substituted the lookdev owner subnet")
                    _restore_flags(parent, before, root, first_display)
                    root.setPosition((min((p[0] for p in positions), default=0), min((p[1] for p in positions), default=3) - 3))
                    root.setComment("SYNAPSE lookdev trial: modern Copernicus color + roughness. Render/export are separate actions.")
                    # H22 SOP Create's editable children disappear on native
                    # Redo. An explicit owned SOP network/import survives Undo/Redo.
                    home = _create(root, "sopnet", "geometry", "Lop")
                    if home.childTypeCategory().name() != "Sop":
                        raise RuntimeError("The owned geometry network is not a SOP network")
                    home.setPosition((0, 3) if settings["layout"] == "horizontal" else (-4, 0))
                    asset = _create(root, "sopimport", "asset", "Lop")
                    grid = _create(home, "grid", "plane", "Sop")
                    for p, v in {"orient": "xy", "sizex": 2.0, "sizey": 2.0, "rows": 2, "cols": 2}.items():
                        _set(grid, p, v)
                    uv = _create(home, "texture", "uv", "Sop")
                    for p, v in {"type": "texture", "axis": "z", "coord": "vertex"}.items():
                        _set(uv, p, v)
                    _wire(uv, grid)
                    grid.setPosition((0, 2)); uv.setPosition((0, 0))
                    uv.setDisplayFlag(True); uv.setRenderFlag(True)
                    fixture_path = "/World/" + settings["name"]
                    mesh_path = fixture_path + "/mesh_0"
                    material_path = "/materials/" + settings["name"]
                    camera_path = "/cameras/" + settings["name"]
                    settings_path = "/Render/" + settings["name"]
                    for p, v in {"soppath": uv.path(), "enable_pathprefix": 1, "pathprefix": fixture_path, "enable_savepath": 0}.items():
                        _set(asset, p, v)
                    textures = _create(root, "texturemateriallibrary", "textures", "Lop")
                    if textures.childTypeCategory().name() != "Cop":
                        raise RuntimeError("Texture Material Library did not provide modern Copernicus")
                    material = _create(textures, "usdmaterial", "surface", "Cop")
                    # Explicitly initialize the stock interface without running
                    # user OnCreated scripts outside our ownership boundary.
                    from husd.quickmaterials import setupUsdMaterialCop
                    setupUsdMaterialCop(material)
                    _set(textures, "matnode1", material.name())
                    base_asset = material.parm("shader_baseassetpath").eval()
                    if not Path(base_asset).is_file() or material.parm("shader_baseprimpath").eval() != "/Materials/QuickSurfaceMaterial":
                        raise RuntimeError("The installed QuickSurfaceMaterial dependency is unavailable")
                    color = _create(textures, "layer", "base_color", "Cop")
                    for p, v in {"signature": "f3", "setres": 1, "resx": 256, "resy": 256,
                                 "setpixelscale": 1, "pixelscale": 1, "identityxform": 1,
                                 "setpixelaspectratio": 1, "pixelaspectratio": 1, "setpixelpad": 1,
                                 "pixelpad_h1": 0, "pixelpad_h2": 0, "pixelpad_v1": 0, "pixelpad_v2": 0,
                                 "f3r": settings["base_color"][0], "f3g": settings["base_color"][1], "f3b": settings["base_color"][2]}.items():
                        _set(color, p, v)
                    noise = build_procedural_texture(textures, settings["noise_type"], settings["frequency"],
                                                     settings["octaves"], RESOLUTION, "roughness", undo_context=nullcontext(), run_init_scripts=False)
                    roughness = textures.node(noise["path"])
                    for p, v in {"base_colorr": 1.0, "base_colorg": 1.0, "base_colorb": 1.0,
                                 "base_color_primvar": "", "specular_roughness": 1.0,
                                 "roughness_primvar": "", "uv_primvar": "st"}.items():
                        _set(material, p, v)
                    ports = [_material_wire(material, "base_color", "RGB", color),
                             _material_wire(material, "specular_roughness", "Mono", roughness)]
                    color.setPosition((-3, 2)); textures.node(noise["resolution_node"]).setPosition((3, 4))
                    roughness.setPosition((3, 2)); material.setPosition((0, -1))
                    for p, v in {"matpath1": material_path, "assign1": 1, "geoprims1": mesh_path}.items():
                        _set(textures, p, v)
                    _wire(textures, asset)
                    camera = _create(root, "camera", "camera", "Lop")
                    for p, v in {"primpath": camera_path, "tz": 7.0, "focalLength": 50.0}.items():
                        _set(camera, p, v)
                    _wire(camera, textures)
                    key = _create(root, "light", "key", "Lop")
                    for p, v in {"primpath": "/lights/" + settings["name"] + "_key", "tx": 1.0,
                                 "ty": 1.0, "tz": 3.0, "intensity": 1.0, "exposure": 4.0}.items():
                        _set(key, p, v)
                    _wire(key, camera)
                    render = _create(root, "karmarendersettings", "preview_settings", "Lop")
                    _set(render, "res_mode", "manual")
                    render.parm("res_mode").pressButton()  # Run the installed HDA resolution callback.
                    for p, v in {"primpath": settings_path, "camera": camera_path, "engine": "cpu",
                                 "resolutionx": 256, "resolutiony": 256, "samplesperpixel": 8,
                                 "pathtracedsamples": 8, "picture": ""}.items():
                        _set(render, p, v)
                    _wire(render, key)
                    output = _create(root, "output", "output0", "Lop")
                    _wire(output, render)
                    for i, node in enumerate((asset, textures, camera, key, render, output)):
                        node.setPosition((i*3, 0) if settings["layout"] == "horizontal" else (0, -i*2.5))
                    output.setDisplayFlag(True)
                    verification = _verify_stage(output, mesh_path, material_path, color, roughness, camera_path, settings_path)
                    display = _restore_flags(parent, before, root, first_display)
                    result = {"status": "created", "template": TEMPLATE, "dry_run": False,
                              "root": root.path(), "output": output.path(), "display_node": display,
                              "display_changed": display != display_before,
                              "display_reason": "First LOP in an empty network becomes the display" if first_display else "Existing display preserved",
                              "nodes_created": [{"id": node.name(), "path": node.path()} for node in root.children()],
                              "controls": {"base_color": color.path(), "roughness": roughness.path(), "material": material.path()},
                              "material_ports": ports, "resolution": list(RESOLUTION), "layout": settings["layout"],
                              "verification": {"configuration": "verified", **verification},
                              "dependencies": [base_asset],
                              "warnings": ["Texture/geometry evaluation was needed to inspect USD; image pixels and rendered appearance were not measured.",
                                           "In-session op: textures depend on this Houdini scene and the installed QuickSurfaceMaterial. Export is not qualified.",
                                           "Existing display is preserved; an empty network displays the new fixture. View the returned output to try the setup; choose an output path before file rendering."]}
                # Closing the update-mode context can itself fail. Keep cleanup
                # inside the undo group for ordinary failures, including that case.
                _restore_flags(parent, before, root, first_display)
            except Exception as error:
                try:
                    cleanup(error)
                except Exception as failure:
                    cleanup_error = failure
                    raise
                raise
        return result
    except Exception as error:
        if cleanup_error is not None and cleanup_error is not error:
            raise cleanup_error from error
        if not cleaned:
            cleanup(error)
        raise
