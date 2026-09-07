"""Modern Copernicus texture construction, qualified on Houdini 22.0.400.

All host access belongs inside the caller's run_on_main/undo group. Construction
verifies configuration; cooking or writing texture files is a separate action.
"""

import math
import re


_NOISE = {
    "perlin": ("fractalnoise", "perlin"),
    "worley": ("fractalnoise", "worleyA"),
    "alligator": ("fractalnoise", "alligator"),
    # Simplex exists on the modern 3D generator. With an identity Layer size
    # reference and no position input, this evaluates on the default XY plane.
    "simplex": ("fractalnoise3d", "simplex"),
}


def validate_texture_settings(noise_type, frequency, octaves, resolution, name):
    """Reject invalid requests before any Houdini mutation; never truncate inputs."""
    if not isinstance(noise_type, str) or noise_type not in _NOISE:
        raise ValueError("noise_type must be perlin, worley, simplex, or alligator")
    if isinstance(frequency, bool) or not isinstance(frequency, (int, float)):
        raise ValueError("frequency must be a finite positive number")
    try:
        frequency = float(frequency)
        valid_frequency = math.isfinite(frequency) and frequency > 0
        element_size = 1.0 / frequency if valid_frequency else 0.0
    except (OverflowError, ZeroDivisionError):
        element_size = 0.0
    if not math.isfinite(element_size) or element_size <= 0:
        raise ValueError("frequency and its reciprocal must be finite and positive")
    if type(octaves) is not int or not 1 <= octaves <= 16:
        raise ValueError("octaves must be an integer from 1 to 16")
    if (not isinstance(resolution, (list, tuple)) or len(resolution) != 2
            or any(type(v) is not int or not 1 <= v <= 8192 for v in resolution)):
        raise ValueError("resolution must contain two integers from 1 to 8192")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,128}", name):
        raise ValueError("name must contain 1-128 letters, digits, or underscores")
    return frequency, list(resolution)


def _set_checked(node, name, value, *, menu=False):
    parm = node.parm(name)
    if parm is None:
        raise RuntimeError(f"Copernicus {node.type().name()} is missing parameter '{name}'")
    if menu and value not in parm.menuItems():
        raise RuntimeError(f"Copernicus parameter '{name}' does not support '{value}'")
    parm.set(value)
    actual = parm.evalAsString() if menu else parm.eval()
    matches = (actual == value if menu or type(value) is int
               else math.isclose(actual, value, rel_tol=1e-6, abs_tol=0.0))
    if not matches:
        raise RuntimeError(f"Copernicus parameter '{name}' read back {actual!r}, expected {value!r}")
    return actual


def build_procedural_texture(parent, noise_type, frequency, octaves, resolution, name, *, undo_context, run_init_scripts=True):
    """Build a prevalidated Layer -> noise pair; include undo close in cleanup."""
    category = parent.childTypeCategory()
    if category is None or category.name() != "Cop":
        raise ValueError("Use a modern Copernicus CopNet (new) parent (Cop), not a legacy COP2 network")
    if not parent.isEditable():
        raise ValueError("The Copernicus parent is not editable")
    node_type, basis = _NOISE[noise_type]
    for required in ("layer", node_type):
        if required not in category.nodeTypes():
            raise RuntimeError(f"Modern Copernicus node '{required}' is unavailable in this Houdini build")

    positions = [node.position() for node in parent.children()]
    x = min((p[0] for p in positions), default=0.0)
    y = min((p[1] for p in positions), default=2.5) - 2.5
    owned = []

    def create(type_name, node_name):
        creation_options = {"exact_type_name": True}
        if not run_init_scripts:
            creation_options["run_init_scripts"] = False
        node = parent.createNode(type_name, node_name, **creation_options)
        if node is None:
            raise RuntimeError(f"Could not create modern Copernicus '{type_name}'")
        owned.append(node)
        if node.type().category().name() != "Cop" or node.type().name() != type_name:
            raise RuntimeError(f"Houdini substituted the requested Copernicus '{type_name}'")
        return node

    def cleanup(exc):
        # Undo grouping is not rollback. Remove only nodes created by this call;
        # never use global undo, which could reverse the artist's previous action.
        residue = []
        for node in reversed(tuple(owned)):
            path = "<unknown created node>"
            try:
                path = node.path()
                node.destroy()
                if parent.node(path) is not None:
                    residue.append(path)
                else:
                    # HOM equality can raise ObjectWasDeleted after destroy().
                    # Retire the Python wrapper by identity, never equality.
                    owned[:] = [candidate for candidate in owned if candidate is not node]
            except Exception as cleanup_error:
                residue.append(f"{path}: {cleanup_error}")
        if residue:
            raise RuntimeError(f"{exc}; cleanup incomplete, inspect: {'; '.join(residue)}") from exc

    cleanup_attempted = False
    cleanup_error = None
    try:
        with undo_context:
            try:
                size = create("layer", name + "_resolution")
                # Pin metadata locally, including preview pixel scale, so the parent
                # network's resolution and existing generators remain untouched.
                for parm, value in {
                    "setres": 1, "resx": resolution[0], "resy": resolution[1],
                    "setpixelscale": 1, "pixelscale": 1,
                    "setpixelaspectratio": 1, "pixelaspectratio": 1,
                    "setpixelpad": 1, "pixelpad_h1": 0, "pixelpad_h2": 0,
                    "pixelpad_v1": 0, "pixelpad_v2": 0, "identityxform": 1,
                }.items():
                    _set_checked(size, parm, value)
                _set_checked(size, "signature", "f1", menu=True)

                noise = create(node_type, name)
                _set_checked(noise, "signature", "default", menu=True)
                actual_basis = _set_checked(noise, "noisetype", basis, menu=True)
                _set_checked(noise, "fractaltype", "sharp", menu=True)
                if node_type == "fractalnoise":
                    # Tiling can quantize element size; this helper exposes frequency,
                    # not a tile period, so use the unquantized coordinate scale.
                    _set_checked(noise, "dotiled", 0)
                element_size = _set_checked(noise, "elementsize", 1.0 / frequency)
                actual_octaves = _set_checked(noise, "oct", octaves)
                inputs = noise.inputNames()
                if "size_ref" not in inputs or not size.outputNames() or noise.outputNames()[0:1] != ("noise",):
                    raise RuntimeError("Copernicus texture ports differ from the qualified size_ref -> noise surface")
                noise.setNamedInput("size_ref", size, 0)
                wires = [c for c in noise.inputConnections() if c.inputIndex() == inputs.index("size_ref")]
                if (len(wires) != 1 or wires[0].inputNode() != size or wires[0].outputIndex() != 0):
                    raise RuntimeError("Copernicus size_ref connection did not match the requested wiring")
                # moveToGoodPosition() can move existing input/neighbor nodes on H22.
                # Place only the newly owned pair in a vertical column below the graph.
                size.setPosition((x, y))
                noise.setPosition((x, y - 2.5))
                return {
                    "path": noise.path(), "node_type": noise.type().name(),
                    "resolution_node": size.path(), "output_name": "noise",
                    "noise_type": noise_type, "noise_basis": actual_basis,
                    "frequency": 1.0 / element_size, "octaves": int(actual_octaves),
                    "resolution": [int(size.parm("resx").eval()), int(size.parm("resy").eval())],
                    "configured": True, "cooked": False,
                }
            except Exception as exc:
                # Keep ordinary failure cleanup in the creation undo group.
                # Otherwise artist Undo could resurrect a failed partial graph.
                cleanup_attempted = True
                try:
                    cleanup(exc)
                except Exception as cleanup_exc:
                    cleanup_error = cleanup_exc
                    raise
                raise
    except Exception as exc:
        # Context exit can fail after successful construction. Only this rare
        # fallback runs after the group; never retry removed node wrappers.
        if not cleanup_attempted:
            cleanup(exc)
        elif cleanup_error is not None and exc is not cleanup_error:
            raise RuntimeError(f"{exc}; {cleanup_error}") from exc
        raise
