"""Extract every node-type string SYNAPSE emits (task 0.2, deliverable A).

Statically scans ``python/synapse/**/*.py`` for ``createNode("...")`` /
``createNode('...')`` literals — a RAW-TEXT scan, deliberately, because the
recipes emit *generated code strings* (``"stage.createNode('sopimport')"``)
that an AST walk of the emitter would never see as calls. Placeholdered
templates (``createNode('{geo_type}')``) are excluded by restricting the
literal to node-type characters. On top of the scan it merges the two
verified-spelling lists already pinned by the suite:

* ``synapse.science.apex_probes.APEX_SEED`` ``kind=="nodetype"`` surfaces
  (the science authority behind ``tests/test_apex_recipe_names.py``);
* ``VERIFIED_NODE_TYPES`` in ``tests/test_setdressing_recipe.py`` (read via
  ``ast.literal_eval`` — no test import).

Output: ``python/synapse/cognitive/tools/data/emitted_node_types.json``
(schema ``emitted_node_types/v1``), committed after one human review pass.
Deterministic: re-running on the same commit produces an identical file
(pinned by ``tests/test_emitted_node_types.py``).

WHY THIS LIVES IN scripts/ (not python/synapse/)
-------------------------------------------------
Operator entrypoint, not library code — same precedent as
``run_apex_verify.py`` (``print`` allowed outside ``python/synapse/**``).

USAGE
-----
    python scripts/extract_emitted_node_types.py            # regenerate
    python scripts/extract_emitted_node_types.py --check    # verify only
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

# --- Bootstrap: put the package root (<repo>/python) on sys.path ------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PKG = _PROJECT_ROOT / "python"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

SCHEMA = "emitted_node_types/v1"
OUTPUT = _PROJECT_ROOT / "python" / "synapse" / "cognitive" / "tools" / "data" / "emitted_node_types.json"
SETDRESSING_TEST = _PROJECT_ROOT / "tests" / "test_setdressing_recipe.py"

# Literal first-arg of createNode. The character class is the point: real node
# type names are [A-Za-z0-9_:.]+ so f-string/.format placeholders ('{geo_type}')
# never match. Both quote styles; whitespace after '(' tolerated.
_CREATE_NODE = re.compile(r"createNode\(\s*([\"'])([A-Za-z0-9_:.]+)\1")


def scan_createnode_literals(pkg_root: Path) -> dict:
    """``{type_name: sorted relative source files}`` from the raw-text scan."""
    found: dict[str, set] = {}
    for py in sorted(pkg_root.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = py.relative_to(_PROJECT_ROOT).as_posix()
        for m in _CREATE_NODE.finditer(text):
            found.setdefault(m.group(2), set()).add(rel)
    return {t: sorted(files) for t, files in found.items()}


def apex_seed_nodetypes() -> set:
    """Catalog-verified APEX nodetype spellings from the science authority
    (the same derivation as ``tests/test_apex_recipe_names.py::SEED_NODETYPES``)."""
    from synapse.science.apex_probes import APEX_SEED

    return {
        s.surface.removeprefix("nodetypes.")
        for s in APEX_SEED
        if s.kind == "nodetype"
    }


def setdressing_nodetypes(test_path: Path = SETDRESSING_TEST) -> set:
    """``VERIFIED_NODE_TYPES`` from the set-dressing pin test, via AST —
    reading a test's data without importing the test module."""
    tree = ast.parse(test_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "VERIFIED_NODE_TYPES":
                    return set(ast.literal_eval(node.value))
    raise LookupError(f"VERIFIED_NODE_TYPES not found in {test_path}")


def _head_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=_PROJECT_ROOT,
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:  # noqa: BLE001 — git is a soft dependency
        pass
    return "unknown"


def build_payload(commit: str | None = None) -> dict:
    """The full ``emitted_node_types/v1`` payload. Pure over the tree state
    (``commit`` injectable so tests never shell out to git)."""
    merged: dict[str, dict] = {}

    def add(type_name: str, category: str, source_files: list) -> None:
        entry = merged.setdefault(
            type_name, {"categories": set(), "source_files": set()}
        )
        entry["categories"].add(category)
        entry["source_files"].update(source_files)

    for type_name, files in scan_createnode_literals(_PKG / "synapse").items():
        add(type_name, "createNode_literal", files)
    for type_name in apex_seed_nodetypes():
        add(type_name, "apex_seed", ["python/synapse/science/apex_probes.py"])
    for type_name in setdressing_nodetypes():
        add(type_name, "setdressing_verified", ["tests/test_setdressing_recipe.py"])

    entries = [
        {
            "category": "+".join(sorted(e["categories"])),
            "type_name": t,
            "source_files": sorted(e["source_files"]),
        }
        for t, e in sorted(merged.items())
    ]
    return {
        "schema": SCHEMA,
        "generated_from_commit": commit if commit is not None else _head_commit(),
        "entries": entries,
    }


def render(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    payload = build_payload()
    text = render(payload)
    if "--check" in argv:
        if not OUTPUT.exists():
            print(f"MISSING: {OUTPUT}")
            return 1
        committed = json.loads(OUTPUT.read_text(encoding="utf-8"))
        same = committed.get("entries") == payload["entries"]
        print(f"CHECK: entries {'match' if same else 'DRIFTED'} "
              f"({len(payload['entries'])} scanned vs {len(committed.get('entries', []))} committed)")
        return 0 if same else 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"WROTE: {len(payload['entries'])} node types -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
