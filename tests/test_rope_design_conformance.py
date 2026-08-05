"""L5-11 design conformance — no hardcoded hex / bare px outside designsystem/.

``python/synapse/panel/designsystem/`` is the single vendored source of truth
for colour, size, type, radius and motion (its docstring records that a
redesign audit already reconciled THREE divergent token sources — this test
exists so a fourth never grows back). It scans the panel modules the L5-11
pass touched and fails on any hex colour (``#RRGGBB``) or bare px value
(``NNpx``) found in their *code* string literals. Comments and docstrings are
prose, not styling, so only string constants are scanned — and a
token-computed size like ``"font-size: %dpx" % t.scaled(...)`` has no literal
digits for the pattern to match, which is exactly the point: values must
arrive through the token pipeline.

A site may be waived ONLY by a ``DESIGN-GAP`` marker on the offending line,
and every waived file must be registered in docs/PROFILES.md under
'Design gaps for human decision'. Marked-but-unlisted fails too: the waiver
and the human-decision ledger may not drift apart.
"""

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PANEL = REPO / "python" / "synapse" / "panel"

# The panel modules L5-11 touched — the scan surface. designsystem/ itself is
# exempt by construction: its literals ARE the tokens.
SCANNED = (
    PANEL / "synapse_panel.py",
    PANEL / "manifests" / "curious.py",
    PANEL / "manifests" / "expert.py",
    PANEL / "manifests" / "ml.py",
)

PROFILES_DOC = REPO / "docs" / "PROFILES.md"
GAPS_HEADING = "Design gaps for human decision"

MARKER = "DESIGN-GAP"
HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")
PX_RE = re.compile(r"\b\d+(?:\.\d+)?\s*px\b")


def _docstring_ids(tree):
    """ids of Constant nodes that are docstrings (first statement of a
    module / class / function body)."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                out.add(id(body[0].value))
    return out


def _findings(path):
    """[(lineno, [hits], waived)] for every string constant carrying a
    hardcoded hex colour or bare px value."""
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    tree = ast.parse(src)
    docstrings = _docstring_ids(tree)
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in docstrings:
            continue
        hits = HEX_RE.findall(node.value) + PX_RE.findall(node.value)
        if not hits:
            continue
        span = range(node.lineno, (node.end_lineno or node.lineno) + 1)
        waived = any(
            MARKER in lines[i - 1] for i in span if 0 < i <= len(lines))
        found.append((node.lineno, hits, waived))
    return found


def test_scan_surface_exists():
    for path in SCANNED:
        assert path.is_file(), "scan surface missing: %s" % path


def test_no_hardcoded_hex_or_px_outside_designsystem():
    """Every colour / px in the touched panel modules arrives via tokens."""
    offenders = []
    for path in SCANNED:
        for lineno, hits, waived in _findings(path):
            if not waived:
                offenders.append(
                    "%s:%d: %s" % (path.relative_to(REPO), lineno, hits))
    assert not offenders, (
        "Hardcoded design values outside designsystem/ (use tokens.py / "
        "components.py, or mark the line DESIGN-GAP and register it in "
        "docs/PROFILES.md):\n" + "\n".join(offenders))


def test_design_gap_markers_are_registered():
    """A DESIGN-GAP waiver without a ledger entry is drift, not a waiver."""
    marked_files = [
        path for path in SCANNED
        if MARKER in path.read_text(encoding="utf-8")
    ]
    if not marked_files:
        return  # nothing waived, nothing to register
    doc = PROFILES_DOC.read_text(encoding="utf-8")
    assert GAPS_HEADING in doc, (
        "%s markers exist but docs/PROFILES.md has no '%s' section"
        % (MARKER, GAPS_HEADING))
    gaps_section = doc.split(GAPS_HEADING, 1)[1]
    for path in marked_files:
        assert path.name in gaps_section, (
            "%s carries a %s marker but is not listed under '%s' in "
            "docs/PROFILES.md" % (path.name, MARKER, GAPS_HEADING))


def test_panel_consumes_designsystem():
    """The panel styles itself from the vendored designsystem, not inline."""
    src = (PANEL / "synapse_panel.py").read_text(encoding="utf-8")
    assert "designsystem" in src
