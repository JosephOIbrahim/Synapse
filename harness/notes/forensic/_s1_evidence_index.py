"""S1 producer path — per-tool evidence index.

For every registered tool, collect the raw material a classifier needs:
  - the handler function and its file:line
  - the handler body's execution signature (does it COOK / EXECUTE, or only
    build topology?)  -> the SCAFFOLD tell
  - which test files name it, and whether those tests drive a mock `hou`
  - explicit self-reported scaffold/stub/not-implemented markers

Emits harness/notes/forensic/s1_evidence_index.json.

This script does NOT classify. It gathers. Classification is adjudicated
against the code by a reader, because the tells below are heuristics and a
heuristic that assigns a verdict is exactly the decoration Law 1 bans.
"""

import ast
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "python"))

from synapse.mcp._tool_registry import TOOL_DEFS  # noqa: E402

SERVER = ROOT / "python" / "synapse" / "server"
TESTS = ROOT / "tests"
IMPLS = ROOT / "python" / "synapse" / "mcp" / "tool_impls"

# ---------------------------------------------------------------- handlers --
handler_for: dict[str, tuple[str, str]] = {}  # cmd -> (handler_attr, site)
for py in sorted(SERVER.rglob("*.py")):
    if "__pycache__" in py.parts:
        continue
    try:
        tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        continue
    rel = str(py.relative_to(ROOT)).replace("\\", "/")
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "register"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            cmd = node.args[0].value
            target = "?"
            if len(node.args) > 1:
                a1 = node.args[1]
                if isinstance(a1, ast.Attribute):
                    target = a1.attr
                elif isinstance(a1, ast.Name):
                    target = a1.id
            handler_for[cmd] = (target, f"{rel}:{node.lineno}")

# ------------------------------------------------- handler bodies + tells --
# index every function def under server/ and tool_impls/ by name
fn_bodies: dict[str, list[tuple[str, str]]] = {}  # name -> [(site, source)]
for base in (SERVER, IMPLS):
    for py in sorted(base.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        src = py.read_text(encoding="utf-8", errors="replace")
        lines = src.splitlines()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        rel = str(py.relative_to(ROOT)).replace("\\", "/")
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = getattr(node, "end_lineno", node.lineno)
                body = "\n".join(lines[node.lineno - 1 : end])
                fn_bodies.setdefault(node.name, []).append(
                    (f"{rel}:{node.lineno}", body)
                )

COOK_TELLS = [
    r"\.cook\s*\(",
    r"cookWorkItems",
    r"executeGraph",
    r"\.render\s*\(",
    r"\.press\s*\(",
    r"executeInMainThread",
    r"run_on_main",
    r"\.save\s*\(",
    r"\.write",
    r"\.parm\(",
    r"\.setParms?\(",
]
BUILD_TELLS = [r"createNode", r"\.createNode", r"NodeSpec", r"build_manifest"]
SCAFFOLD_MARKERS = [
    r"scaffold",
    r"not implemented",
    r"NotImplemented",
    r"TODO",
    r"stub",
    r"placeholder",
    r"does not cook",
    r"never cooks",
    r"topology only",
    r"no cook",
]


def scan(body: str, pats):
    hits = []
    for p in pats:
        if re.search(p, body, re.IGNORECASE):
            hits.append(p)
    return hits


# ------------------------------------------------------------------ tests --
test_blobs: dict[str, str] = {}
for py in sorted(TESTS.rglob("*.py")):
    if "__pycache__" in py.parts:
        continue
    test_blobs[str(py.relative_to(ROOT)).replace("\\", "/")] = py.read_text(
        encoding="utf-8", errors="replace"
    )

MOCK_PAT = re.compile(r"MagicMock|Mock\(|monkeypatch\.setattr\(.{0,40}hou|mock_hou|fake_hou", re.I)
LIVE_PAT = re.compile(r"hython|importorskip\(.hou.|HOU_AVAILABLE|_HAVE_HOU|has_hou|skipif.{0,80}hou", re.I)

rows = []
for name, cmd_type, _payload, desc, _schema, ro, destr, idemp in TOOL_DEFS:
    h_attr, h_site = handler_for.get(cmd_type, ("<NONE>", "<NONE>"))
    bodies = fn_bodies.get(h_attr, [])
    cook_hits, build_hits, scaf_hits, sites = [], [], [], []
    for site, body in bodies:
        sites.append(site)
        cook_hits += scan(body, COOK_TELLS)
        build_hits += scan(body, BUILD_TELLS)
        scaf_hits += scan(body, SCAFFOLD_MARKERS)

    naming = set()
    mock_tests, live_tests = [], []
    for tf, blob in test_blobs.items():
        if name in blob or (cmd_type and f'"{cmd_type}"' in blob):
            naming.add(tf)
            if MOCK_PAT.search(blob):
                mock_tests.append(tf)
            if LIVE_PAT.search(blob):
                live_tests.append(tf)

    rows.append(
        {
            "tool": name,
            "command_type": cmd_type,
            "read_only": bool(ro),
            "destructive": bool(destr),
            "handler_attr": h_attr,
            "registration_site": h_site,
            "handler_def_sites": sites,
            "handler_found": bool(bodies),
            "cook_tells": sorted(set(cook_hits)),
            "build_tells": sorted(set(build_hits)),
            "scaffold_markers": sorted(set(scaf_hits)),
            "tests_naming_it": sorted(naming),
            "tests_with_mock_hou": sorted(set(mock_tests)),
            "tests_live_gated": sorted(set(live_tests)),
            "test_count": len(naming),
            "desc_head": (desc or "").strip().replace("\n", " ")[:200],
        }
    )

out = {
    "producer": "harness/notes/forensic/_s1_evidence_index.py",
    "caveat": "Heuristic tells, not verdicts. cook_tells/build_tells/scaffold_markers "
    "are grep signatures over the handler body only (not its callees). A tool is "
    "classified by a reader who opened the code, never by these fields alone.",
    "tools_indexed": len(rows),
    "handlers_not_found": sorted(r["tool"] for r in rows if not r["handler_found"]),
    "no_test_names_it": sorted(r["tool"] for r in rows if r["test_count"] == 0),
    "self_reported_scaffold": sorted(
        r["tool"] for r in rows if r["scaffold_markers"]
    ),
    "tools": sorted(rows, key=lambda r: r["tool"]),
}

dest = ROOT / "harness" / "notes" / "forensic" / "s1_evidence_index.json"
dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "tools"}, indent=1)[:4000])
print(f"wrote {dest}")
