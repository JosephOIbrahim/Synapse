"""VEX Tutor module for the SYNAPSE Houdini panel.

Provides three /vex subcommands:
  /vex explain  -- select a wrangle, explains the code line by line
  /vex help {function}  -- VEX function quick reference with practical example
  /vex write {description}  -- generates VEX code from natural language

Key principle: never just give code, always explain WHY.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Houdini import guard
# ---------------------------------------------------------------------------

_HOU_AVAILABLE = False
try:
    import hou  # type: ignore[import-untyped]

    _HOU_AVAILABLE = True
except ImportError:
    hou = None


# ===================================================================
# 1. Command parser
# ===================================================================


def parse_vex_command(text: str) -> dict[str, str]:
    """Parse ``/vex`` subcommands into mode + arg.

    Examples::

        "/vex explain"           -> {"mode": "explain", "arg": ""}
        "/vex help pcfind"       -> {"mode": "help",    "arg": "pcfind"}
        "/vex write color by height" -> {"mode": "write", "arg": "color by height"}
        "/vex"                   -> {"mode": "help",    "arg": ""}  (show usage)
    """
    stripped = text.strip()
    # Remove the leading /vex (case-insensitive)
    match = re.match(r"^/vex\s*", stripped, re.IGNORECASE)
    if not match:
        return {"mode": "help", "arg": ""}
    remainder = stripped[match.end():].strip()
    if not remainder:
        return {"mode": "help", "arg": ""}

    parts = remainder.split(None, 1)
    mode = parts[0].lower()
    valid_modes = {"explain", "help", "write"}
    if mode not in valid_modes:
        # Treat unknown subcommand as a help lookup (e.g. "/vex pcfind")
        return {"mode": "help", "arg": remainder}

    arg = parts[1].strip() if len(parts) > 1 else ""
    return {"mode": mode, "arg": arg}


# ===================================================================
# 2. Wrangle context gathering
# ===================================================================

# Parameter names that hold VEX code, ordered by priority.
_VEX_CODE_PARMS = ("snippet", "code", "vexcode", "vex_code", "script")

# Run-over values from attribwrangle runover parm.
_RUN_OVER_MAP = {
    0: "Detail",
    1: "Points",
    2: "Primitives",
    3: "Vertices",
}


def _get_selected_wrangle_path() -> str:
    """Return the path of the first selected wrangle-type node, or ''."""
    if not _HOU_AVAILABLE:
        return ""
    try:
        selected = hou.selectedNodes()
        if not selected:
            return ""
        # Prefer an explicit wrangle type, but fall back to first selected.
        for node in selected:
            type_name = node.type().name().lower()
            if "wrangle" in type_name or "vex" in type_name:
                return node.path()
        # Fall back to first selected if it has a snippet parm.
        first = selected[0]
        for pname in _VEX_CODE_PARMS:
            if first.parm(pname):
                return first.path()
        return ""
    except Exception:
        return ""


def _extract_vex_code(node: Any) -> str:
    """Extract VEX source from a node by checking known parm names."""
    for pname in _VEX_CODE_PARMS:
        parm = node.parm(pname)
        if parm is not None:
            try:
                val = parm.evalAsString()
                if val.strip():
                    return val
            except Exception:
                continue
    return ""


def _get_run_over(node: Any) -> str:
    """Return the human-readable run-over mode of a wrangle node."""
    parm = node.parm("class")
    if parm is None:
        parm = node.parm("runover")
    if parm is None:
        return "Points"
    try:
        return _RUN_OVER_MAP.get(parm.evalAsInt(), "Points")
    except Exception:
        return "Points"


def _geo_summary(geo: Any) -> dict[str, int]:
    """Summarise geometry into point/prim counts."""
    if geo is None:
        return {"points": 0, "prims": 0}
    try:
        return {
            "points": geo.intrinsicValue("pointcount"),
            "prims": geo.intrinsicValue("primitivecount"),
        }
    except Exception:
        return {"points": 0, "prims": 0}


def _list_attribs(geo: Any) -> list[str]:
    """List attribute names on a geometry."""
    if geo is None:
        return []
    try:
        names: list[str] = []
        for attr in geo.pointAttribs():
            names.append(f"@{attr.name()}")
        for attr in geo.primAttribs():
            names.append(f"prim@{attr.name()}")
        for attr in geo.vertexAttribs():
            names.append(f"vtx@{attr.name()}")
        for attr in geo.globalAttribs():
            names.append(f"detail@{attr.name()}")
        return names
    except Exception:
        return []


def _get_channel_refs(node: Any) -> dict[str, str]:
    """Return channel references (ch('name') bindings) from the VEX code."""
    code = _extract_vex_code(node)
    bindings: dict[str, str] = {}
    for match in re.finditer(r'\bch[fisv]?\(\s*["\']([^"\']+)["\']\s*\)', code):
        parm_name = match.group(1)
        parm = node.parm(parm_name)
        if parm is not None:
            try:
                bindings[parm_name] = str(parm.eval())
            except Exception:
                bindings[parm_name] = "?"
        else:
            bindings[parm_name] = "(not found)"
    return bindings


def _get_errors(node: Any) -> list[str]:
    """Return VEX compile / cook errors from a node."""
    try:
        errors = node.errors()
        if errors:
            return list(errors)
        warnings = node.warnings()
        if warnings:
            return [f"warning: {w}" for w in warnings]
    except Exception:
        pass
    return []


def gather_wrangle_context(node_path: str = "") -> dict[str, Any]:
    """Gather VEX code and geometry context from a wrangle node.

    Parameters
    ----------
    node_path:
        Explicit node path.  If empty, tries the current selection.

    Returns a dict with keys: node_path, vex_code, run_over,
    input_attribs, output_attribs, input_geo, output_geo,
    bindings, errors.
    """
    empty: dict[str, Any] = {
        "node_path": "",
        "vex_code": "",
        "run_over": "Points",
        "input_attribs": [],
        "output_attribs": [],
        "input_geo": {"points": 0, "prims": 0},
        "output_geo": {"points": 0, "prims": 0},
        "bindings": {},
        "errors": [],
    }

    if not _HOU_AVAILABLE:
        return empty

    if not node_path:
        node_path = _get_selected_wrangle_path()
    if not node_path:
        return empty

    try:
        node = hou.node(node_path)
    except Exception:
        return empty
    if node is None:
        return empty

    vex_code = _extract_vex_code(node)
    run_over = _get_run_over(node)

    # Input geometry (first input).
    input_geo: dict[str, int] = {"points": 0, "prims": 0}
    input_attribs: list[str] = []
    try:
        inputs = node.inputs()
        if inputs and inputs[0] is not None:
            geo = inputs[0].geometry()
            input_geo = _geo_summary(geo)
            input_attribs = _list_attribs(geo)
    except Exception:
        pass

    # Output geometry.
    output_geo: dict[str, int] = {"points": 0, "prims": 0}
    output_attribs: list[str] = []
    try:
        geo = node.geometry()
        output_geo = _geo_summary(geo)
        output_attribs = _list_attribs(geo)
    except Exception:
        pass

    return {
        "node_path": node_path,
        "vex_code": vex_code,
        "run_over": run_over,
        "input_attribs": input_attribs,
        "output_attribs": output_attribs,
        "input_geo": input_geo,
        "output_geo": output_geo,
        "bindings": _get_channel_refs(node),
        "errors": _get_errors(node),
    }


# ===================================================================
# 3. VEX quick-reference dictionary
# ===================================================================

VEX_REFERENCE: dict[str, dict[str, str]] = {
    # -- Attribute access --------------------------------------------------
    "@P": {
        "signature": "vector @P",
        "description": "Point position. Read/write. The most fundamental attribute.",
        "category": "attribute",
        "example": "@P.y += sin(@P.x * 5) * 0.2;  // sine wave displacement",
        "tip": "Modifying @P directly is fastest. Avoid setpointattrib for position unless you need to write to another point.",
    },
    "@N": {
        "signature": "vector @N",
        "description": "Point/vertex normal. Read/write.",
        "category": "attribute",
        "example": "@N = normalize(@N + set(0, 1, 0));  // bias normals upward",
        "tip": "Normals should always be normalized. VEX does NOT auto-normalize after writes.",
    },
    "@Cd": {
        "signature": "vector @Cd",
        "description": "Diffuse color (RGB 0-1). Read/write.",
        "category": "attribute",
        "example": "@Cd = chramp('color', @P.y);  // ramp by height",
        "tip": "Cd is a vector, not vector4. Alpha lives in @Alpha (float).",
    },
    "@id": {
        "signature": "int @id",
        "description": "Stable point identifier. Survives topology changes.",
        "category": "attribute",
        "example": "i@id = @ptnum;  // assign stable IDs before scatter",
        "tip": "@ptnum changes when points are deleted. @id persists. Always prefer @id for references across frames.",
    },
    "v@": {
        "signature": "v@name = vector value",
        "description": "Type-cast prefix for vector attributes.",
        "category": "attribute",
        "example": "v@up = set(0, 1, 0);  // create/write a vector attribute",
        "tip": "Explicit type-casts (v@, i@, f@, s@, 2@, 3@, 4@, p@) are required when creating new attributes. Without a prefix, VEX defaults to float.",
    },
    # -- Math --------------------------------------------------------------
    "length": {
        "signature": "float length(vector v)",
        "description": "Returns the magnitude of a vector.",
        "category": "math",
        "example": "float dist = length(@P);  // distance from origin",
        "tip": "If you only need to compare distances, use length2() (squared length) to avoid the sqrt cost.",
    },
    "distance": {
        "signature": "float distance(vector a, vector b)",
        "description": "Euclidean distance between two points.",
        "category": "math",
        "example": "float d = distance(@P, point(0, 'P', 0));  // distance to point 0",
        "tip": "Same as length(a - b). For repeated comparisons, distance2() avoids sqrt.",
    },
    "normalize": {
        "signature": "vector normalize(vector v)",
        "description": "Returns a unit-length vector in the same direction.",
        "category": "math",
        "example": "vector dir = normalize(@P - centroid);  // direction from center",
        "tip": "Returns {0,0,0} if input is zero-length. Guard with length() check if unsure.",
    },
    "cross": {
        "signature": "vector cross(vector a, vector b)",
        "description": "Cross product. Returns a vector perpendicular to both inputs.",
        "category": "math",
        "example": "vector tangent = normalize(cross(@N, set(0, 1, 0)));",
        "tip": "Cross product is NOT commutative: cross(a,b) = -cross(b,a). Order matters for winding direction.",
    },
    "dot": {
        "signature": "float dot(vector a, vector b)",
        "description": "Dot product. Measures alignment between vectors (-1 to 1 for unit vectors).",
        "category": "math",
        "example": "float facing = dot(@N, normalize(light_pos - @P));  // lambertian",
        "tip": "dot > 0 = same direction, dot == 0 = perpendicular, dot < 0 = opposing. Faster than acos for comparison.",
    },
    "fit": {
        "signature": "float fit(float value, float omin, float omax, float nmin, float nmax)",
        "description": "Remaps a value from one range to another.",
        "category": "math",
        "example": "float mask = fit(@P.y, 0, 5, 0, 1);  // 0..5 height -> 0..1 mask",
        "tip": "fit clamps to [nmin,nmax]. Use fit01 for [0,1]->range, or efit for unclamped.",
    },
    "lerp": {
        "signature": "float|vector lerp(float|vector a, float|vector b, float t)",
        "description": "Linear interpolation. Returns a + (b-a)*t.",
        "category": "math",
        "example": "vector blended = lerp(color_a, color_b, mask);",
        "tip": "t is NOT clamped -- values outside 0..1 extrapolate. Use clamp() on t first if needed.",
    },
    "smooth": {
        "signature": "float smooth(float edge0, float edge1, float x)",
        "description": "Hermite smoothstep. Returns 0 below edge0, 1 above edge1, smooth in between.",
        "category": "math",
        "example": "float falloff = smooth(0, 2, @P.y);  // smooth blend over 0..2 height",
        "tip": "Equivalent to GLSL smoothstep. Use for soft falloffs instead of fit + clamp.",
    },
    # -- Noise -------------------------------------------------------------
    "noise": {
        "signature": "float|vector noise(vector pos)",
        "description": "Perlin noise. Returns values in 0..1 range.",
        "category": "noise",
        "example": "@P.y += noise(@P * chf('freq')) * chf('amp');  // terrain displacement",
        "tip": "noise() is centered at 0.5, not 0. Subtract 0.5 for centered noise. For -1..1 range, use (noise()-0.5)*2.",
    },
    "onoise": {
        "signature": "float onoise(vector pos, int turb, float rough, float atten)",
        "description": "Octave-based (fBm) noise. Built-in turbulence layers.",
        "category": "noise",
        "example": "@P += @N * onoise(@P * 2, 6, 0.5, 1.0) * 0.1;  // organic displacement",
        "tip": "turb = octave count (6-8 typical). rough < 0.5 = smoother, > 0.5 = rougher. Faster than manual fBm loops.",
    },
    "curlnoise": {
        "signature": "vector curlnoise(vector pos)",
        "description": "Divergence-free noise. Ideal for fluid-like motion.",
        "category": "noise",
        "example": "v@vel = curlnoise(@P * chf('scale') + @Time);  // swirling velocity field",
        "tip": "Curl noise guarantees incompressible flow -- particles never converge or diverge. Perfect for advection.",
    },
    "anoise": {
        "signature": "float anoise(vector pos, int turb, float rough, float atten)",
        "description": "Alligator noise. Produces cell-like patterns.",
        "category": "noise",
        "example": "@Cd = set(anoise(@P * 3, 4, 0.5, 1), 0, 0);  // cell pattern visualization",
        "tip": "Good for organic surfaces like bark, scales, or skin. More expensive than Perlin.",
    },
    # -- Proximity ---------------------------------------------------------
    "pcfind": {
        "signature": "int[] pcfind(int input, string group, vector pos, float radius, int maxpts)",
        "description": "Finds points within a radius. Returns array of point numbers.",
        "category": "proximity",
        "example": "int pts[] = pcfind(0, '', @P, 0.5, 10);  // find 10 nearest points within 0.5 units",
        "tip": "Use pcfind_radius for distance-weighted results. pcfind is faster than nearpoints for small result sets.",
    },
    "pcopen": {
        "signature": "int pcopen(int input, string group, vector pos, float radius, int maxpts)",
        "description": "Opens a point cloud handle for iterating with pcfilter/pcimport.",
        "category": "proximity",
        "example": "int h = pcopen(0, '', @P, 1.0, 50); float avg = pcfilter(h, 'density');",
        "tip": "pcopen + pcfilter is the classic smoothing pattern. For simple lookups, pcfind is simpler.",
    },
    "nearpoint": {
        "signature": "int nearpoint(int input, vector pos)",
        "description": "Returns the closest point number to a position.",
        "category": "proximity",
        "example": "int closest = nearpoint(1, @P);  // find nearest point on input 2",
        "tip": "Returns -1 if no points exist. For multiple nearest points, use nearpoints() or pcfind().",
    },
    "nearpoints": {
        "signature": "int[] nearpoints(int input, vector pos, float maxdist, int maxpts)",
        "description": "Returns array of nearby point numbers, sorted by distance.",
        "category": "proximity",
        "example": "int pts[] = nearpoints(0, @P, 1.0, 5);  // 5 closest within 1.0",
        "tip": "Equivalent to pcfind but returns results sorted by distance. Slightly slower due to sorting.",
    },
    "xyzdist": {
        "signature": "float xyzdist(int input, vector pos, int &prim, vector &uv)",
        "description": "Distance to nearest surface point. Also outputs prim number and parametric UV.",
        "category": "proximity",
        "example": "int pr; vector uv; float d = xyzdist(1, @P, pr, uv);  // snap to surface",
        "tip": "Essential for surface transfer. Use primuv() with the returned prim/uv to sample any attribute at that closest point.",
    },
    # -- Geometry read/write -----------------------------------------------
    "point": {
        "signature": "float|vector point(int input, string attrib, int ptnum)",
        "description": "Read an attribute value from a specific point.",
        "category": "geometry",
        "example": "vector other_pos = point(1, 'P', 0);  // position of point 0 on input 2",
        "tip": "For vector attrs, the return is vector. For int attrs, returns int. Type must match your variable.",
    },
    "prim": {
        "signature": "float|vector prim(int input, string attrib, int primnum)",
        "description": "Read a primitive attribute value.",
        "category": "geometry",
        "example": "string name = prim(0, 'name', @primnum);",
        "tip": "For string attributes, use s@name = prim(0, 'name', @primnum) with explicit type.",
    },
    "setpointattrib": {
        "signature": "int setpointattrib(int geohandle, string name, int ptnum, value, string mode)",
        "description": "Write an attribute to a specific point (geohandle 0 = current geo).",
        "category": "geometry",
        "example": 'setpointattrib(0, "Cd", nearest, {1, 0, 0}, "set");  // color nearest red',
        "tip": 'mode is usually "set". Use "add", "min", "max" for accumulation. geohandle is always 0 in wrangles.',
    },
    "addpoint": {
        "signature": "int addpoint(int geohandle, vector pos)",
        "description": "Creates a new point. Returns the new point number.",
        "category": "geometry",
        "example": "int pt = addpoint(0, @P + @N * 0.1);  // duplicate point offset along normal",
        "tip": "New point has no attributes. Copy them with setpointattrib or use addpoint(0, ptnum) to clone from existing.",
    },
    "removeprim": {
        "signature": "void removeprim(int geohandle, int primnum, int andpoints)",
        "description": "Delete a primitive. andpoints=1 also removes its points.",
        "category": "geometry",
        "example": "if (@P.y < 0) removeprim(0, @primnum, 1);  // delete prims below ground",
        "tip": "andpoints=1 removes points ONLY if they belong to no other prim. Safe to use with shared points.",
    },
    "primuv": {
        "signature": "float|vector primuv(int input, string attrib, int primnum, vector uv)",
        "description": "Interpolate an attribute at a parametric UV position on a primitive.",
        "category": "geometry",
        "example": "vector pos = primuv(1, 'P', pr, uv);  // sample position at closest surface point",
        "tip": "Pair with xyzdist() for surface transfer. The uv is parametric (0..1), not texture UV.",
    },
    # -- String ------------------------------------------------------------
    "sprintf": {
        "signature": "string sprintf(string fmt, ...)",
        "description": "Formatted string creation (C-style).",
        "category": "string",
        "example": 's@name = sprintf("piece_%04d", @ptnum);  // piece_0001, piece_0002, ...',
        "tip": "%d = int, %f = float, %g = float (compact), %s = string, %v = vector.",
    },
    "split": {
        "signature": "string[] split(string s, string sep)",
        "description": "Split a string by separator. Returns array.",
        "category": "string",
        "example": 'string parts[] = split(s@path, "/");  // split path by slash',
        "tip": "Returns empty array if input is empty. Sep is literal, not regex.",
    },
    "match": {
        "signature": "int match(string pattern, string str)",
        "description": "Glob-style pattern matching (* and ? wildcards).",
        "category": "string",
        "example": 'if (match("wall_*", s@name)) @group_walls = 1;',
        "tip": "Not regex -- uses shell-style globs. For regex use re_find().",
    },
    "re_find": {
        "signature": "int re_find(string regex, string str)",
        "description": "Regex match. Returns 1 if pattern found.",
        "category": "string",
        "example": 'if (re_find("v\\d+$", s@name)) @group_versioned = 1;',
        "tip": "Backslashes need double-escaping in VEX strings. Use re_findall for capture groups.",
    },
    # -- Color -------------------------------------------------------------
    "hsvtorgb": {
        "signature": "vector hsvtorgb(vector hsv)",
        "description": "Convert HSV to RGB color space.",
        "category": "color",
        "example": "@Cd = hsvtorgb(set(@P.y * 360, 1, 1));  // rainbow by height",
        "tip": "H is in degrees (0-360), S and V are 0-1.",
    },
    "rgbtohsv": {
        "signature": "vector rgbtohsv(vector rgb)",
        "description": "Convert RGB to HSV color space.",
        "category": "color",
        "example": "vector hsv = rgbtohsv(@Cd); hsv.x += 30; @Cd = hsvtorgb(hsv);  // hue shift",
        "tip": "Useful for hue rotation, saturation adjustment. Modify .x for hue, .y for saturation, .z for value.",
    },
    # -- Random / Sampling -------------------------------------------------
    "rand": {
        "signature": "float rand(float seed)",
        "description": "Deterministic pseudo-random. Same seed = same result.",
        "category": "random",
        "example": "float r = rand(@ptnum);  // per-point random, stable across frames",
        "tip": "rand is NOT time-varying. Use rand(@ptnum + @Frame * 0.01) for animated randomness. Faster than random().",
    },
    "random": {
        "signature": "vector random(int seed)",
        "description": "Random vector. Higher quality distribution than rand.",
        "category": "random",
        "example": "v@scatter = random(@id) - 0.5;  // random offset per id",
        "tip": "Returns vector with each component in 0..1. Subtract 0.5 for centered. Better distribution than rand for multi-dimensional use.",
    },
    "nrandom": {
        "signature": "float nrandom(string dist)",
        "description": "Non-deterministic random from a named distribution.",
        "category": "random",
        "example": 'float gauss = nrandom("normal");  // Gaussian random',
        "tip": '"normal" = Gaussian, "twotail" = symmetric. NOT deterministic -- different every cook. Use for variation, not reproducibility.',
    },
    "sample_sphere_uniform": {
        "signature": "vector sample_sphere_uniform(vector2 uv)",
        "description": "Uniformly distributed random point on a sphere surface.",
        "category": "random",
        "example": "vector dir = sample_sphere_uniform(set(rand(@ptnum), rand(@ptnum+1)));",
        "tip": "Better distribution than normalize(random()-0.5) which clusters at corners. Use for scattering directions.",
    },
    # -- Channel references ------------------------------------------------
    "chf": {
        "signature": "float chf(string parmname)",
        "description": "Read a float channel from the wrangle's spare parameter.",
        "category": "utility",
        "example": "float scale = chf('scale');  // auto-creates float slider on node",
        "tip": "First use auto-creates the spare parm. Click the channel button to set range/default. chf, chi, chv, chs for different types.",
    },
    "chi": {
        "signature": "int chi(string parmname)",
        "description": "Read an integer channel from spare parameters.",
        "category": "utility",
        "example": "int seed = chi('seed');  // integer control on node",
        "tip": "Auto-creates integer spare parm. Use for counts, seeds, toggle switches.",
    },
    "chv": {
        "signature": "vector chv(string parmname)",
        "description": "Read a vector (3 floats) from spare parameters.",
        "category": "utility",
        "example": "vector offset = chv('offset');  // 3-component vector control",
        "tip": "Creates a 3-float spare parm. Good for position offsets, direction overrides.",
    },
    "chramp": {
        "signature": "float chramp(string rampname, float pos)",
        "description": "Sample a ramp parameter at position 0..1.",
        "category": "utility",
        "example": "float falloff = chramp('falloff', @P.y / bbox_height);  // artist-controlled curve",
        "tip": "Creates a ramp spare parm on first use. Best way to give artists non-linear control. pos is clamped to 0..1.",
    },
    "printf": {
        "signature": "void printf(string fmt, ...)",
        "description": "Print to the Houdini console (for debugging).",
        "category": "utility",
        "example": 'printf("pt %d: P = %v, Cd = %v\\n", @ptnum, @P, @Cd);',
        "tip": "Only prints once per point/prim in the cook. Use sparingly -- floods console on high-count geometry. For once-only messages, wrap in if(@ptnum==0).",
    },
    "warning": {
        "signature": 'void warning(string fmt, ...)',
        "description": "Emit a warning (yellow flag on the node).",
        "category": "utility",
        "example": 'if (length(@N) < 0.001) warning("Zero-length normal at pt %d", @ptnum);',
        "tip": "Shows as a yellow warning badge on the node. Good for validation. Use error() for hard stops.",
    },
    "error": {
        "signature": "void error(string fmt, ...)",
        "description": "Emit an error (red flag, stops downstream cooking).",
        "category": "utility",
        "example": 'if (@numpt == 0) error("No input points");',
        "tip": "Stops the cook. Use for hard validation. Downstream nodes will not cook.",
    },
}


# ===================================================================
# 4-6. Prompt builders
# ===================================================================


def build_vex_explain_prompt() -> str:
    """System prompt for explaining VEX code line by line."""
    return (
        "You are explaining VEX code to a Houdini artist. Go line by line.\n"
        "For each line: what it does, why this approach, and any gotchas.\n"
        "Use @attribute notation naturally. When mentioning functions, note "
        "if there's a faster/better alternative for this use case.\n"
        "If the code has bugs or inefficiencies, point them out gently -- "
        'phrase it as "one thing to watch for" rather than "this is wrong."\n'
        "Group related lines together when they form a logical unit.\n"
        "End with a brief summary of what the code does overall and any "
        "suggestions for improvement."
    )


def build_vex_help_prompt(function_name: str) -> str:
    """System prompt for VEX function help.

    If the function exists in VEX_REFERENCE, embeds the reference data
    so the model can build on verified information.
    """
    base = (
        "You are a VEX tutor helping a Houdini artist understand a VEX function.\n"
        "Explain what it does, when to use it, and give a practical example.\n"
        "If relevant, mention related functions and common patterns.\n"
        "Use the artist's geometry context if provided."
    )

    ref = VEX_REFERENCE.get(function_name)
    if ref is not None:
        ref_block = (
            f"\n\n--- Reference Data (verified) ---\n"
            f"Function: {function_name}\n"
            f"Signature: {ref['signature']}\n"
            f"Description: {ref['description']}\n"
            f"Category: {ref['category']}\n"
            f"Example: {ref['example']}\n"
            f"Tip: {ref['tip']}\n"
            f"--- End Reference ---\n\n"
            "Build on this reference with additional context and examples."
        )
        return base + ref_block

    return base + (
        f"\n\nNote: '{function_name}' is not in the built-in quick reference. "
        "Provide the best information you can from your training data, "
        "and flag if you are uncertain about the exact signature."
    )


def build_vex_write_prompt() -> str:
    """System prompt for generating VEX code from natural language."""
    return (
        "Write VEX code for the requested task. After the code, explain each "
        "line briefly. Note any performance considerations. If there are multiple "
        "approaches, mention why you chose this one.\n"
        "Always include: what run-over mode to use, what attributes are read/written.\n"
        "Prefer clarity over cleverness. Use channel references (chf, chramp) for "
        "values the artist might want to tweak.\n"
        "If the task is ambiguous, state your assumptions clearly."
    )


# ===================================================================
# 7. Message builder
# ===================================================================


def build_vex_messages(
    mode: str,
    arg: str,
    context: dict[str, Any],
) -> list[dict[str, str]]:
    """Build the messages list for an Anthropic API call.

    Parameters
    ----------
    mode:
        One of ``"explain"``, ``"help"``, ``"write"``.
    arg:
        The argument from the parsed command (function name, description, etc.).
    context:
        Output of :func:`gather_wrangle_context` or an empty dict.

    Returns
    -------
    list[dict[str, str]]
        A list of ``{"role": ..., "content": ...}`` message dicts
        with the system prompt as the first ``system`` entry.
    """
    messages: list[dict[str, str]] = []

    if mode == "explain":
        system = build_vex_explain_prompt()
        vex_code = context.get("vex_code", "")
        if not vex_code:
            user_content = (
                "No VEX code found. Please select a wrangle node first, "
                "then try /vex explain again."
            )
        else:
            geo_info_parts: list[str] = []
            node_path = context.get("node_path", "")
            if node_path:
                geo_info_parts.append(f"Node: {node_path}")
            geo_info_parts.append(f"Run-over: {context.get('run_over', 'Points')}")
            input_geo = context.get("input_geo", {})
            if input_geo.get("points", 0) > 0:
                geo_info_parts.append(
                    f"Input: {input_geo['points']} points, {input_geo.get('prims', 0)} prims"
                )
            input_attribs = context.get("input_attribs", [])
            if input_attribs:
                geo_info_parts.append(f"Input attribs: {', '.join(input_attribs[:20])}")
            bindings = context.get("bindings", {})
            if bindings:
                bind_str = ", ".join(f"{k}={v}" for k, v in bindings.items())
                geo_info_parts.append(f"Channel bindings: {bind_str}")
            errors = context.get("errors", [])
            if errors:
                geo_info_parts.append(f"Errors: {'; '.join(errors)}")
            geo_info = "\n".join(geo_info_parts)
            user_content = f"Explain this VEX code:\n```vex\n{vex_code}\n```\nContext:\n{geo_info}"

    elif mode == "help":
        func_name = arg.strip() if arg else ""
        if not func_name:
            # Show general usage / category listing.
            categories: dict[str, list[str]] = {}
            for fname, fdata in VEX_REFERENCE.items():
                cat = fdata.get("category", "other")
                categories.setdefault(cat, []).append(fname)
            cat_listing = "\n".join(
                f"  {cat}: {', '.join(sorted(funcs))}"
                for cat, funcs in sorted(categories.items())
            )
            system = build_vex_help_prompt("")
            user_content = (
                "Show the VEX quick-reference overview. Available functions by category:\n"
                + cat_listing
                + "\n\nBriefly describe each category and when to use it."
            )
        else:
            system = build_vex_help_prompt(func_name)
            ref = VEX_REFERENCE.get(func_name)
            if ref:
                user_content = (
                    f"Explain the VEX function: {func_name}\n"
                    f"Reference: {ref['signature']}\n"
                    f"Give a practical example and mention related functions."
                )
            else:
                user_content = (
                    f"Explain the VEX function: {func_name}\n"
                    "Give the signature, a practical example, and any gotchas."
                )
            # Add geo context if available.
            if context.get("node_path"):
                input_attribs = context.get("input_attribs", [])
                if input_attribs:
                    user_content += f"\nCurrent geo attributes: {', '.join(input_attribs[:15])}"

    elif mode == "write":
        system = build_vex_write_prompt()
        description = arg if arg else "general VEX help"
        user_content = f"Write VEX to: {description}"
        # Include geometry context if available.
        if context.get("node_path"):
            geo_parts: list[str] = []
            input_geo = context.get("input_geo", {})
            if input_geo.get("points", 0) > 0:
                geo_parts.append(
                    f"Current geo: {input_geo['points']} points, {input_geo.get('prims', 0)} prims"
                )
            input_attribs = context.get("input_attribs", [])
            if input_attribs:
                geo_parts.append(f"Available attribs: {', '.join(input_attribs[:20])}")
            run_over = context.get("run_over", "Points")
            geo_parts.append(f"Current run-over: {run_over}")
            if geo_parts:
                user_content += "\n" + "\n".join(geo_parts)
    else:
        system = build_vex_help_prompt("")
        user_content = f"Unknown /vex mode: {mode}. Show usage information."

    messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_content})
    return messages


# ===================================================================
# 8. HTML reference formatter
# ===================================================================

# VEX keywords for basic syntax highlighting in HTML.
_VEX_KEYWORDS = {
    "int", "float", "vector", "vector2", "vector4", "matrix", "matrix3",
    "string", "void", "if", "else", "for", "while", "foreach", "return",
    "break", "continue", "function",
}

_VEX_TYPES = {"int", "float", "vector", "vector2", "vector4", "matrix", "matrix3", "string", "void"}


def _highlight_vex_html(code: str) -> str:
    """Apply basic syntax highlighting to a VEX code snippet for HTML display."""

    def _replace_token(m: re.Match[str]) -> str:
        token = m.group(0)
        if token in _VEX_TYPES:
            return f'<span style="color:#6db3f2;">{token}</span>'
        if token in _VEX_KEYWORDS:
            return f'<span style="color:#c586c0;">{token}</span>'
        return token

    # Highlight @attributes.
    code = re.sub(
        r"@\w+",
        lambda m: f'<span style="color:#dcdcaa;">{m.group(0)}</span>',
        code,
    )
    # Highlight keywords and types.
    code = re.sub(
        r"\b(" + "|".join(re.escape(k) for k in _VEX_KEYWORDS | _VEX_TYPES) + r")\b",
        _replace_token,
        code,
    )
    # Highlight comments.
    code = re.sub(
        r"//.*$",
        lambda m: f'<span style="color:#6a9955;">{m.group(0)}</span>',
        code,
        flags=re.MULTILINE,
    )
    # Highlight string literals.
    code = re.sub(
        r'"[^"]*"',
        lambda m: f'<span style="color:#ce9178;">{m.group(0)}</span>',
        code,
    )
    # Highlight numbers.
    code = re.sub(
        r"\b(\d+\.?\d*)\b",
        lambda m: f'<span style="color:#b5cea8;">{m.group(0)}</span>',
        code,
    )
    return code


def format_vex_reference_html(func_name: str, ref: dict[str, str]) -> str:
    """Format a VEX reference entry as styled HTML for panel display.

    Parameters
    ----------
    func_name:
        The VEX function name (e.g. ``"pcfind"``).
    ref:
        A dict from :data:`VEX_REFERENCE`.

    Returns
    -------
    str
        HTML fragment suitable for embedding in a Qt label or text browser.
    """
    sig_html = _highlight_vex_html(ref.get("signature", func_name))
    example_html = _highlight_vex_html(ref.get("example", ""))
    description = ref.get("description", "")
    tip = ref.get("tip", "")
    category = ref.get("category", "")

    html = f"""<div style="font-family: 'Consolas', 'Courier New', monospace; padding: 8px;">
  <div style="font-size: 14px; color: #cccccc; margin-bottom: 4px;">
    <span style="color: #808080;">[{category}]</span>
    <b style="color: #e0e0e0;">{func_name}</b>
  </div>
  <div style="background: #1e1e1e; padding: 6px 10px; border-radius: 4px; margin-bottom: 6px;">
    <code style="color: #d4d4d4; font-size: 13px;">{sig_html}</code>
  </div>
  <div style="color: #b0b0b0; font-size: 12px; margin-bottom: 6px;">
    {description}
  </div>
  <div style="background: #1e1e1e; padding: 6px 10px; border-radius: 4px; margin-bottom: 6px;">
    <code style="color: #d4d4d4; font-size: 12px;">{example_html}</code>
  </div>
  <div style="color: #8a8a5c; font-size: 11px; font-style: italic;">
    Tip: {tip}
  </div>
</div>"""
    return html
