"""
VEX Error Diagnostics

Pattern-based VEX error diagnosis with coaching-tone suggestions.
Matches Houdini VEX compiler/runtime error messages against known
patterns and returns structured fixes using the RAG knowledge corpus.

This is Synapse's VEXpert-parity feature: when a wrangle node errors,
we don't just relay "syntax error" -- we explain what went wrong and
how to fix it, referencing the artist's actual code.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class VexDiagnosis:
    """Structured diagnosis of a VEX error."""
    category: str           # e.g. "syntax", "type", "attribute", "function", "runtime"
    symptom: str            # What the artist sees (coaching tone)
    cause: str              # Why it happened
    fix: str                # What to do about it
    example: str = ""       # Corrected code snippet
    reference_topic: str = ""   # RAG topic key for deeper lookup
    line_number: int = -1   # Error line if extractable
    confidence: float = 1.0  # How confident the match is (0-1)


# --- Error Pattern Database ---
# Each pattern: (compiled_regex, category, builder_function)
# Builder receives the regex match and original snippet, returns VexDiagnosis

def _build_missing_semicolon(m: re.Match, snippet: str) -> VexDiagnosis:
    line_no = int(m.group("line")) if m.group("line") else -1
    return VexDiagnosis(
        category="syntax",
        symptom="Looks like there's a missing semicolon",
        cause="VEX requires a semicolon at the end of every statement",
        fix="Add a semicolon (;) at the end of the statement",
        example='@P.y += sin(@P.x);  // semicolons required',
        reference_topic="vex_fundamentals",
        line_number=line_no,
    )


def _build_unexpected_token(m: re.Match, snippet: str) -> VexDiagnosis:
    token = m.group("token") if "token" in m.groupdict() else "unknown"
    line_no = int(m.group("line")) if m.group("line") else -1
    return VexDiagnosis(
        category="syntax",
        symptom=f"The compiler hit an unexpected '{token}'",
        cause="Usually a typo, missing operator, or bracket mismatch",
        fix="Check for mismatched parentheses, missing operators, or extra characters",
        reference_topic="vex_fundamentals",
        line_number=line_no,
    )


def _build_undeclared_variable(m: re.Match, snippet: str) -> VexDiagnosis:
    var = m.group("var") if "var" in m.groupdict() else "unknown"
    # Check if it looks like a missing @ prefix
    fix = f"Declare '{var}' before using it, or add an @ prefix if it's an attribute"
    example = ""
    if not var.startswith("@") and len(var) > 1:
        example = f'// If "{var}" is an attribute:\nfloat val = @{var};\n// Or declare it:\nfloat {var} = 0;'

    return VexDiagnosis(
        category="syntax",
        symptom=f"Variable '{var}' hasn't been declared",
        cause="VEX requires variables to be declared with a type before use, "
              "or prefixed with @ for attributes",
        fix=fix,
        example=example,
        reference_topic="vex_attributes",
    )


def _build_unknown_function(m: re.Match, snippet: str) -> VexDiagnosis:
    func = m.group("func") if "func" in m.groupdict() else "unknown"
    suggestion = _suggest_vex_function(func)
    fix = f"Check the function name spelling"
    if suggestion:
        fix = f"Did you mean '{suggestion}'?"
    return VexDiagnosis(
        category="function",
        symptom=f"Couldn't find a function called '{func}'",
        cause="The function name might be misspelled, or it may not exist in this VEX context",
        fix=fix,
        example=f"// Perhaps: {suggestion}(...)" if suggestion else "",
        reference_topic="vex_functions",
    )


def _build_type_mismatch(m: re.Match, snippet: str) -> VexDiagnosis:
    return VexDiagnosis(
        category="type",
        symptom="There's a type mismatch in the expression",
        cause="Trying to assign or combine incompatible types "
              "(e.g., vector to float, or int to string)",
        fix="Check your type prefixes: f@ for float, v@ for vector, "
            "i@ for int, s@ for string. Use explicit casts like float(), "
            "vector(), or set(x,y,z)",
        example='vector v = set(1.0, 2.0, 3.0);  // explicit construction\n'
                'float f = v.x;  // extract component',
        reference_topic="vex_types",
    )


def _build_readonly_attribute(m: re.Match, snippet: str) -> VexDiagnosis:
    attr = m.group("attr") if "attr" in m.groupdict() else "the attribute"
    return VexDiagnosis(
        category="attribute",
        symptom=f"Can't write to '{attr}' -- it's read-only",
        cause="Some attributes like @ptnum, @numpt, @primnum, @numprim, "
              "@Frame, @Time are read-only context variables",
        fix=f"Create a new attribute instead of trying to overwrite the built-in",
        example=f'// Instead of: {attr} = value;\n'
                f'// Use:\ni@my_{attr.lstrip("@")} = value;',
        reference_topic="vex_attributes",
    )


def _build_wrong_input(m: re.Match, snippet: str) -> VexDiagnosis:
    return VexDiagnosis(
        category="runtime",
        symptom="Trying to read from an input that isn't connected",
        cause="Functions like point(1, ...) or pcfind(1, ...) reference "
              "the second input (index 1), but nothing is wired there",
        fix="Wire geometry into the correct input slot on the wrangle node, "
            "or change the input index to 0 for the first input",
        example='// Input 0 = first input (most common)\n'
                'int pts[] = pcfind(0, "P", @P, radius, maxpts);\n'
                '// Input 1 = second input (must be connected)\n'
                'vector other_pos = point(1, "P", 0);',
        reference_topic="vex_functions",
    )


def _build_pcfind_empty(m: re.Match, snippet: str) -> VexDiagnosis:
    return VexDiagnosis(
        category="runtime",
        symptom="Point cloud search returned no results",
        cause="Search radius might be too small, the input might have no "
              "points, or the attribute name might be wrong",
        fix="Try increasing the search radius, or check that the input "
            "geometry has points within range",
        example='// Generous radius + reasonable max points\n'
                'int pts[] = pcfind(0, "P", @P, chf("radius"), 100);\n'
                '// Debug: check if input has points\n'
                'printf("Input points: %d\\n", npoints(0));',
        reference_topic="vex_performance",
    )


def _build_division_by_zero(m: re.Match, snippet: str) -> VexDiagnosis:
    return VexDiagnosis(
        category="runtime",
        symptom="Division by zero",
        cause="A denominator evaluates to zero at some points",
        fix="Guard with max() or a conditional check before dividing",
        example='// Safe division pattern\n'
                'float result = value / max(denominator, 1e-6);',
        reference_topic="vex_fundamentals",
    )


def _build_array_out_of_bounds(m: re.Match, snippet: str) -> VexDiagnosis:
    return VexDiagnosis(
        category="runtime",
        symptom="Array index is out of bounds",
        cause="Trying to access an array element that doesn't exist",
        fix="Check array length with len() before indexing",
        example='int arr[] = neighbours(0, @ptnum);\n'
                'if (len(arr) > 0) {\n'
                '    int first = arr[0];\n'
                '}',
        reference_topic="vex_fundamentals",
    )


# --- Pattern Registry ---
# Order matters: more specific patterns first

_ERROR_PATTERNS: List[Tuple[re.Pattern, callable]] = []


def _init_patterns():
    """Initialize compiled error patterns. Called once at module load."""
    global _ERROR_PATTERNS
    patterns = [
        # Syntax errors
        (r"(?i)(?:line\s+(?P<line>\d+):\s*)?expected\s+['\"]?;['\"]?",
         _build_missing_semicolon),
        (r"(?i)(?:line\s+(?P<line>\d+):\s*)?missing\s+semicolon",
         _build_missing_semicolon),
        (r"(?i)(?:line\s+(?P<line>\d+):\s*)?unexpected\s+(?:token\s+)?['\"]?(?P<token>[^'\"]+)['\"]?",
         _build_unexpected_token),
        (r"(?i)undeclared\s+(?:variable\s+)?['\"]?(?P<var>\w+)['\"]?",
         _build_undeclared_variable),
        (r"(?i)unknown\s+(?:variable|identifier)\s+['\"]?(?P<var>\w+)['\"]?",
         _build_undeclared_variable),
        # Function errors
        (r"(?i)(?:unknown|undefined|no\s+matching)\s+function\s+['\"]?(?P<func>\w+)['\"]?",
         _build_unknown_function),
        (r"(?i)call\s+to\s+undefined\s+function\s+['\"]?(?P<func>\w+)['\"]?",
         _build_unknown_function),
        # Type errors
        (r"(?i)type\s+mismatch|cannot\s+convert|incompatible\s+type",
         _build_type_mismatch),
        (r"(?i)cannot\s+assign\s+.*?\s+to\s+",
         _build_type_mismatch),
        # Attribute errors
        (r"(?i)(?:read[- ]only|cannot\s+write\s+to)\s+(?:attribute\s+)?['\"]?(?P<attr>[@\w]+)['\"]?",
         _build_readonly_attribute),
        # Runtime errors
        (r"(?i)no\s+(?:geometry|points?)\s+(?:on|in|for)\s+input\s+(?P<input>\d+)",
         _build_wrong_input),
        (r"(?i)input\s+(?P<input>\d+)\s+(?:is\s+)?(?:not\s+connected|empty|missing)",
         _build_wrong_input),
        (r"(?i)division\s+by\s+zero|divide\s+by\s+zero",
         _build_division_by_zero),
        (r"(?i)(?:array|index)\s+out\s+of\s+(?:bounds|range)",
         _build_array_out_of_bounds),
    ]
    _ERROR_PATTERNS = [(re.compile(p), fn) for p, fn in patterns]


_init_patterns()


# --- Function Suggestion Database ---
# Common VEX functions for fuzzy matching

_VEX_FUNCTIONS = sorted([
    "addpoint", "addprim", "addvertex", "append",
    "attrib", "attribsize", "attribtype",
    "ceil", "ch", "chf", "chi", "chv", "chramp", "clamp", "cos",
    "cross", "cracktransform",
    "degrees", "detail", "distance", "distance2", "dot",
    "exp", "fit", "float", "floor",
    "getbbox", "getbbox_center", "getbbox_size",
    "hasattrib", "hsvtorgb",
    "ident", "int", "invert",
    "len", "length", "length2", "lerp", "log", "lookat",
    "maketransform", "max", "min",
    "npoints", "nprimitives", "nvertices", "normalize",
    "neighbours", "nearpoint", "nearpoints",
    "pcclose", "pcfilter", "pcfind", "pcfind_radius", "pcopen",
    "point", "prim", "primuv", "printf",
    "quaternion", "qrotate", "qmultiply", "qinvert",
    "radians", "rand", "removepoint", "removeprim",
    "resize", "rint",
    "set", "setattrib", "setpointattrib", "setprimattrib",
    "setvertexattrib", "sin", "slerp", "smooth", "snoise",
    "sprintf", "sqrt",
    "vector", "vertex",
])


def _suggest_vex_function(name: str, limit: int = 3) -> str:
    """Find the most likely intended VEX function name."""
    name_lower = name.lower()

    # Exact match
    if name_lower in _VEX_FUNCTIONS:
        return ""  # Already correct

    # Common misspellings (check first — highest confidence)
    common_typos = {
        "pcfin": "pcfind",
        "nearpoint": "nearpoints",
        "neighbour": "neighbours",
        "neighbor": "neighbours",
        "normalize_v": "normalize",
        "addpt": "addpoint",
        "npts": "npoints",
        "removevert": "removevertex",
        "chfloat": "chf",
        "chint": "chi",
        "chvec": "chv",
        "lenght": "length",
        "distanc": "distance",
        "noise": "snoise",
    }
    if name_lower in common_typos:
        return common_typos[name_lower]

    # Substring match — prefer longer matches (more specific)
    matches = [f for f in _VEX_FUNCTIONS if name_lower in f or f in name_lower]
    if matches:
        # Sort by length similarity to input (closest length first)
        matches.sort(key=lambda f: abs(len(f) - len(name_lower)))
        return matches[0]

    # Edit distance (simple: matching prefix, 3+ chars)
    if len(name_lower) >= 3:
        prefix_matches = [f for f in _VEX_FUNCTIONS if f[:3] == name_lower[:3]]
        if prefix_matches:
            prefix_matches.sort(key=lambda f: abs(len(f) - len(name_lower)))
            return prefix_matches[0]

    return ""


# --- Static Analysis (Pre-Execution) ---

def lint_vex_snippet(snippet: str) -> List[VexDiagnosis]:
    """
    Quick static checks on VEX code before execution.

    Catches obvious issues without needing Houdini. Returns empty list
    if no issues found.
    """
    issues: List[VexDiagnosis] = []
    lines = snippet.strip().split("\n")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("#"):
            continue

        # Check: statement doesn't end with semicolon (but isn't a block opener)
        if (stripped and
            not stripped.endswith(";") and
            not stripped.endswith("{") and
            not stripped.endswith("}") and
            not stripped.endswith(",") and
            not stripped.endswith("(") and
            not stripped.startswith("if") and
            not stripped.startswith("else") and
            not stripped.startswith("for") and
            not stripped.startswith("foreach") and
            not stripped.startswith("while") and
            not stripped.startswith("return") and
            not stripped.startswith("break") and
            not stripped.startswith("continue") and
            "{" not in stripped and
            "}" not in stripped):
            # Might be a multi-line statement, be lenient
            if i < len(lines):
                next_stripped = lines[i].strip() if i < len(lines) else ""
                if next_stripped and not next_stripped.startswith("."):
                    issues.append(VexDiagnosis(
                        category="syntax",
                        symptom=f"Line {i} might be missing a semicolon",
                        cause="VEX requires semicolons on every statement",
                        fix=f"Add ';' at the end of line {i}",
                        line_number=i,
                        confidence=0.6,
                    ))

        # Check: writing to read-only attributes
        readonly_attrs = ["@ptnum", "@primnum", "@vtxnum", "@numpt",
                         "@numprim", "@numvtx", "@Frame", "@Time",
                         "@TimeInc", "@elemnum"]
        for attr in readonly_attrs:
            if re.search(rf"{re.escape(attr)}\s*=(?!=)", stripped):
                issues.append(VexDiagnosis(
                    category="attribute",
                    symptom=f"Line {i}: trying to write to read-only '{attr}'",
                    cause=f"'{attr}' is a built-in read-only variable",
                    fix=f"Create a new attribute: i@my_{attr.lstrip('@')} = ...;",
                    line_number=i,
                    reference_topic="vex_attributes",
                    confidence=0.95,
                ))

    return issues


# --- Main Diagnosis Entry Point ---

def diagnose_vex_error(
    error_message: str,
    snippet: str = "",
    node_path: str = "",
) -> List[VexDiagnosis]:
    """
    Diagnose a VEX error and return structured fix suggestions.

    Args:
        error_message: The error string from Houdini's VEX compiler/runtime.
        snippet: The VEX source code (for context in suggestions).
        node_path: The wrangle node path (for reference).

    Returns:
        List of VexDiagnosis objects, ordered by confidence.
        Empty list if no patterns match (fall through to LLM tier).
    """
    diagnoses: List[VexDiagnosis] = []

    for pattern, builder in _ERROR_PATTERNS:
        m = pattern.search(error_message)
        if m:
            diagnosis = builder(m, snippet)
            diagnoses.append(diagnosis)

    # Also run lint if snippet is provided and no pattern matched
    if snippet and not diagnoses:
        lint_results = lint_vex_snippet(snippet)
        diagnoses.extend(lint_results)

    # Sort by confidence (highest first)
    diagnoses.sort(key=lambda d: d.confidence, reverse=True)
    return diagnoses


# --- Natural-Language Symptom Matching ---
# Maps artist descriptions to likely VEX issues

_SYMPTOM_PATTERNS: List[Tuple[re.Pattern, callable]] = []


def _init_symptoms():
    """Initialize natural-language symptom patterns for diagnosis."""
    global _SYMPTOM_PATTERNS

    symptoms = [
        # Position / movement issues
        (r"(?i)(?:points?|geo(?:metry)?)\s+(?:aren'?t?|not|won'?t?|don'?t?)\s+(?:moving|updating|changing)",
         lambda m, s: VexDiagnosis(
             category="attribute",
             symptom="Points aren't moving",
             cause="The wrangle may be reading @P but not writing it back, or the run-over mode is wrong (e.g., Detail instead of Points).",
             fix="Make sure you assign to @P directly. Check the run-over dropdown is set to 'Points'. If using a Solver SOP, multiply velocity by @TimeInc.",
             example="@P += @N * chf('amount');  // displace along normal",
             reference_topic="vex_attributes",
             confidence=0.75,
         )),
        (r"(?i)(?:nothing|no)\s+(?:is\s+)?(?:happening|changing|moving|working)",
         lambda m, s: VexDiagnosis(
             category="runtime",
             symptom="Nothing seems to be happening",
             cause="Common causes: wrangle isn't wired in (check connections), run-over set to Detail when you need Points, or writing to an output that isn't being read downstream.",
             fix="Check: (1) Is the wrangle connected and cooking? (2) Is run-over correct? (3) Are you writing to the right attribute? Try adding a simple test: @Cd = {1,0,0}; to see if the node has any effect.",
             example="// Quick test: turn everything red\n@Cd = {1,0,0};",
             reference_topic="vex_fundamentals",
             confidence=0.65,
         )),
        # Color issues
        (r"(?i)(?:colors?|cd)\s+(?:are|is|look(?:s|ing)?)\s+(?:wrong|off|weird|bad|black|white|flat)",
         lambda m, s: VexDiagnosis(
             category="attribute",
             symptom="Colors look wrong",
             cause="Common issues: @Cd not initialized (black), values outside 0-1 range (clamped), writing to @Cd.x instead of @Cd (only red channel), or color space mismatch.",
             fix="Verify @Cd exists on input (add Color SOP upstream if needed). Check your values are in 0-1 range. Use vector assignment: @Cd = set(r, g, b); not component-wise unless intentional.",
             example="@Cd = set(chramp('ramp', @P.y), 0.5, 0.2);  // color by height",
             reference_topic="vex_attributes",
             confidence=0.7,
         )),
        # Orientation / rotation issues
        (r"(?i)(?:orient(?:ation)?s?|rotat(?:ion|e|ing))\s+(?:are|is|look(?:s|ing)?)\s+(?:wrong|off|weird|random|flipped|broken)",
         lambda m, s: VexDiagnosis(
             category="attribute",
             symptom="Orientations look wrong",
             cause="Copy-to-points reads @orient (quaternion) with highest priority. If @orient exists but is wrong, @N+@up are ignored. Also: quaternion multiplication order matters.",
             fix="Either (1) remove @orient and use @N+@up instead, or (2) build quaternion correctly from your desired direction. Use dihedral() or lookat() to construct quaternions.",
             example="// Option A: use N + up (simpler)\nv@up = {0,1,0};\n@N = normalize(@P);\n\n// Option B: quaternion from direction\np@orient = dihedral({0,0,1}, @N);",
             reference_topic="vex_attributes",
             confidence=0.75,
         )),
        # Scale issues
        (r"(?i)(?:scale|pscale|size)\s+(?:is|are|look(?:s|ing)?)\s+(?:wrong|off|weird|too\s+(?:big|small)|zero|not\s+working)",
         lambda m, s: VexDiagnosis(
             category="attribute",
             symptom="Scale isn't working as expected",
             cause="Copy-to-points reads @pscale (uniform float) and @scale (per-axis vector3). If both exist, @scale wins. pscale=0 makes things invisible.",
             fix="For uniform scale use f@pscale = value; For per-axis use v@scale = set(sx, sy, sz); Don't set both unless you want them multiplied together.",
             example="f@pscale = fit01(rand(@ptnum), 0.5, 1.5);  // random uniform scale",
             reference_topic="vex_attributes",
             confidence=0.7,
         )),
        # Noise issues
        (r"(?i)(?:noise|displacement|deform(?:ation)?)\s+(?:look(?:s|ing)?|is|are)\s+(?:blocky|pixelated|uniform|flat|same|too\s+(?:smooth|sharp))",
         lambda m, s: VexDiagnosis(
             category="runtime",
             symptom="Noise doesn't look right",
             cause="Common issues: frequency too low (blocky), using integer positions (snoise needs float), not enough octaves (too smooth), or all points at same position (uniform result).",
             fix="Try: (1) Multiply position by frequency: noise(@P * chf('freq')); (2) Add offset for animation: noise(@P * freq + @Time); (3) Layer octaves for fBm detail.",
             example="float freq = chf('freq');  // try 2-10\nfloat amp = chf('amp');   // try 0.1-1.0\n@P += @N * amp * noise(@P * freq + chf('offset'));",
             reference_topic="vex_patterns",
             confidence=0.7,
         )),
        # Performance / speed issues
        (r"(?i)(?:wrangle|vex|node)\s+(?:is|are)\s+(?:slow|taking\s+(?:too\s+)?long|lagging|freezing)",
         lambda m, s: VexDiagnosis(
             category="runtime",
             symptom="VEX wrangle is running slow",
             cause="Common bottlenecks: O(n^2) spatial queries (use pcfind not nearpoints), string operations in loops, heavy branching, or cooking every frame unnecessarily.",
             fix="Profile with Performance Monitor. Quick wins: (1) pcfind() instead of nearpoints(), (2) distance2() instead of distance() if comparing, (3) cache ch() calls outside loops, (4) reduce point count upstream.",
             example="// Fast: KD-tree spatial query\nint pts[] = pcfind(0, 'P', @P, chf('radius'), chi('maxpts'));\n\n// Slow: brute force\n// int pts[] = nearpoints(0, @P, chf('radius'));",
             reference_topic="vex_performance",
             confidence=0.8,
         )),
        # pcfind / scatter / proximity issues
        (r"(?i)(?:pcfind|nearpoint|scatter|proximity|closest)\s+(?:return(?:s|ing)?|giv(?:es|ing))\s+(?:nothing|empty|zero|no\s+(?:result|point))",
         lambda m, s: VexDiagnosis(
             category="runtime",
             symptom="Spatial query returns empty results",
             cause="pcfind/nearpoint found no points within search radius. Either: radius too small, wrong input index (0-3), points not where expected, or searching for attribute that doesn't exist.",
             fix="Debug: (1) Print search radius and point count, (2) Verify input connections, (3) Try much larger radius first, (4) Visualize with a sphere at @P with search radius.",
             example="int pts[] = pcfind(1, 'P', @P, chf('radius'), chi('maxpts'));\ni@found = len(pts);  // check this attribute to see results\n// If found==0, increase radius or check input 1",
             reference_topic="vex_functions",
             confidence=0.75,
         )),
        # Attribute not showing / missing
        (r"(?i)(?:attribute|attrib|@\w+)\s+(?:is|are|seems?)\s+(?:missing|not\s+(?:there|showing|visible|working)|gone|disappeared|zero)",
         lambda m, s: VexDiagnosis(
             category="attribute",
             symptom="Attribute seems to be missing or zero",
             cause="Possible causes: attribute name typo, wrong type prefix (f@ vs v@), reading from wrong input, wrangle run-over doesn't match attribute class, or attribute created but not surviving through the network.",
             fix="Check: (1) Use Geometry Spreadsheet to verify attribute exists, (2) Correct type prefix: f@float, v@vector, i@int, s@string, (3) Right input index for point()/prim() calls, (4) Attribute not being deleted by a downstream node.",
             example="// Read from input 1 (second input)\nfloat val = point(1, 'my_attr', @ptnum);\n// Check with: printf('val=%f\\n', val);",
             reference_topic="vex_attributes",
             confidence=0.7,
         )),
        # Solver / simulation issues
        (r"(?i)(?:solver|simulation|sim)\s+(?:is|are)\s+(?:exploding|unstable|going\s+crazy|flying\s+away|blowing\s+up)",
         lambda m, s: VexDiagnosis(
             category="runtime",
             symptom="Solver is exploding or unstable",
             cause="Classic causes: not multiplying velocity by @TimeInc (frame-rate dependent), missing collision bounds, NaN propagation from division by zero, or values growing without damping.",
             fix="Add @TimeInc multiplication for frame-rate independence, add damping (multiply velocity by 0.98 each frame), clamp values, and check for NaN with isnan().",
             example="// Frame-rate independent velocity\n@P += v@vel * @TimeInc;\n\n// Damping\nv@vel *= 0.98;\n\n// Ground collision\nif (@P.y < 0) { @P.y = 0; v@vel.y *= -0.5; }",
             reference_topic="vex_patterns",
             confidence=0.8,
         )),
    ]

    _SYMPTOM_PATTERNS = [(re.compile(p), fn) for p, fn in symptoms]


_init_symptoms()


def diagnose_vex_symptom(description: str) -> List[VexDiagnosis]:
    """
    Diagnose a VEX issue from a natural-language description.

    Unlike diagnose_vex_error() which matches compiler output,
    this matches artist descriptions like "my points aren't moving"
    or "colors look wrong".

    Args:
        description: Natural-language description of the problem.

    Returns:
        List of VexDiagnosis objects, ordered by confidence.
    """
    diagnoses: List[VexDiagnosis] = []

    for pattern, builder in _SYMPTOM_PATTERNS:
        m = pattern.search(description)
        if m:
            diagnosis = builder(m, "")
            diagnoses.append(diagnosis)

    diagnoses.sort(key=lambda d: d.confidence, reverse=True)
    return diagnoses


def format_diagnosis(diagnoses: List[VexDiagnosis], snippet: str = "") -> str:
    """
    Format diagnoses into a coaching-tone response string.

    This is what gets returned to the artist via the MCP tool.
    """
    if not diagnoses:
        return ""

    parts = []
    for i, d in enumerate(diagnoses):
        if i > 0:
            parts.append("")  # blank line between diagnoses

        line_ref = f" (line {d.line_number})" if d.line_number > 0 else ""
        parts.append(f"**{d.symptom}**{line_ref}")
        parts.append(f"  Why: {d.cause}")
        parts.append(f"  Fix: {d.fix}")

        if d.example:
            parts.append(f"  ```vex")
            parts.append(f"  {d.example}")
            parts.append(f"  ```")

        if d.reference_topic:
            parts.append(
                f"  (More details in the VEX reference: {d.reference_topic})"
            )

    return "\n".join(parts)
