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
