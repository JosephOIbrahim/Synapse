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

Recipe payload dicts (``payload_template={"type": "colorcorrect", ...}`` under
``python/synapse/routing/``) are harvested too (category ``recipe_payload``,
AST walk) — they name node types as data, which the createNode scan never
sees (CTO B6: the phantom ``grade`` hid there).

Every harvested type is then audited against ``rag/catalog/h22.0.400/``:
``phantom`` = resolves in no category; ``deprecated`` = deprecated in every
category it resolves in, or emitted via ``stage.createNode`` while Lop.json
marks it deprecated (the ``karma`` LOP). ``--check`` and regeneration both
exit 1 on any violation; ``tests/test_emitted_node_types.py`` pins zero.

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

# Same literal, but only when the receiver is the recipes' LOP-network handle
# (``stage = hou.node('/stage')``). ``stage.createNode('karma')`` is a LOP
# emit, so the catalog verdict for it is Lop.json's -- where ``karma`` is
# deprecated -- not Driver.json's, where the /out ROP of the same name is not.
# Receiver-aware so the audit can be category-aware where the text lets it.
_LOP_CREATE_NODE = re.compile(r"\bstage\.createNode\(\s*([\"'])([A-Za-z0-9_:.]+)\1")

# Recipe payloads name node types as data, not code:
# ``payload_template={"type": "colorcorrect", "name": ..., "parent": ...}``.
# A dict literal is a create_node payload when it carries ``type`` + ``name``
# and either ``parent`` (recipes / planner) or ``parms`` (hda_recipes). That
# shape excludes the TOPs wedge attribute dict (``{"name", "type": "float",
# "start", "end", "steps"}``) whose ``type`` is a data type, not a node type.
_RECIPE_ROOT = _PKG / "synapse" / "routing"
_NODE_TYPE_CHARS = re.compile(r"^[A-Za-z0-9_:.]+$")

CATALOG_DIR = _PROJECT_ROOT / "rag" / "catalog" / "h22.0.400"
# Catalog files that are not ``{types: {...}}`` category dumps.
_NON_CATEGORY_FILES = frozenset({"_audit.json", "_docs_report.json", "_manifest.json",
                                 "apex_callbacks.json"})


def scan_createnode_literals(pkg_root: Path, pattern: re.Pattern = _CREATE_NODE) -> dict:
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
        for m in pattern.finditer(text):
            found.setdefault(m.group(2), set()).add(rel)
    return {t: sorted(files) for t, files in found.items()}


def scan_lop_createnode_literals(pkg_root: Path) -> dict:
    """``stage.createNode('<literal>')`` emits only -- the LOP-receiver subset."""
    return scan_createnode_literals(pkg_root, _LOP_CREATE_NODE)


def _is_create_node_payload(node: ast.Dict) -> bool:
    keys = {k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return "type" in keys and "name" in keys and ("parent" in keys or "parms" in keys)


def scan_recipe_payload_types(recipe_root: Path = _RECIPE_ROOT) -> dict:
    """``{type_name: sorted relative source files}`` from recipe payload dicts.

    AST walk (the payloads are real dict literals, unlike the generated-code
    strings the raw scan exists for). Placeholdered types (``"{geo_type}"``)
    fail the node-type character class and are skipped, like the raw scan.
    """
    found: dict[str, set] = {}
    for py in sorted(recipe_root.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, SyntaxError):
            continue
        rel = py.relative_to(_PROJECT_ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict) or not _is_create_node_payload(node):
                continue
            for key, value in zip(node.keys, node.values):
                if (isinstance(key, ast.Constant) and key.value == "type"
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                        and _NODE_TYPE_CHARS.match(value.value)):
                    found.setdefault(value.value, set()).add(rel)
    return {t: sorted(files) for t, files in found.items()}


def load_catalog_index(catalog_dir: Path = CATALOG_DIR) -> dict:
    """``{type_name: {category: deprecated_bool}}`` over every category dump.

    One node-type name can live in several categories with different
    verdicts (``karma``: Lop deprecated, Driver not), so the index keeps the
    per-category flag rather than collapsing it.
    """
    index: dict[str, dict] = {}
    for path in sorted(catalog_dir.glob("*.json")):
        if path.name in _NON_CATEGORY_FILES:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        types = data.get("types") if isinstance(data, dict) else None
        if not isinstance(types, dict):
            continue
        for name, entry in types.items():
            deprecated = bool(entry.get("deprecated")) if isinstance(entry, dict) else False
            index.setdefault(name, {})[path.stem] = deprecated
    return index


# Emitted names absent from the catalog whose emit is existence-gated at
# runtime, so they are not phantoms in the "will raise on createNode" sense.
# Every entry must STILL be absent from the catalog -- a stale entry (the type
# appears in a later dump) fails ``tests/test_emitted_node_types.py`` loud.
KNOWN_PHANTOMS: dict[str, str] = {
    "componentbuilder": (
        "component_builder.py only emits it behind _has_native_componentbuilder() "
        "(runtime hou type-category probe); absent from the 22.0.400 dump, the "
        "fallback path builds componentgeometry/componentmaterial/componentoutput."
    ),
}


def catalog_audit(type_files: dict, lop_type_files: dict, index: dict,
                  allow: dict | None = None) -> list:
    """Violations of "every emitted node type is real and not deprecated".

    Two rules, each honest about what the text can and cannot tell:

    * ``phantom`` -- the name resolves in NO catalog category. (``grade``)
    * ``deprecated`` -- either the name is deprecated in EVERY category it
      resolves in (no live home anywhere), or it was emitted through the LOP
      receiver (``stage.createNode``) and Lop.json marks it deprecated
      (``karma``: the /out ROP is fine, the LOP is not).

    A type deprecated in one category but live in another that the text does
    not pin (``duplicate``: Sop deprecated, Lop not) is NOT flagged -- the
    scan cannot see which network it lands in, and a false phantom is the
    failure class this whole file exists to prevent.

    ``allow`` (default ``KNOWN_PHANTOMS``) exempts runtime-gated phantoms;
    it never exempts a deprecated verdict.
    """
    allow = KNOWN_PHANTOMS if allow is None else allow
    violations = []
    for type_name in sorted(type_files):
        homes = index.get(type_name)
        if not homes and type_name in allow:
            continue
        if not homes:
            violations.append({"type_name": type_name, "verdict": "phantom",
                               "categories": {}, "source_files": type_files[type_name]})
        elif all(homes.values()):
            violations.append({"type_name": type_name, "verdict": "deprecated",
                               "categories": dict(homes), "source_files": type_files[type_name]})
    for type_name in sorted(lop_type_files):
        homes = index.get(type_name) or {}
        if homes.get("Lop") is True:
            violations.append({"type_name": type_name, "verdict": "deprecated",
                               "categories": {"Lop": True},
                               "source_files": lop_type_files[type_name],
                               "receiver": "stage"})
    return violations


def audit_tree(pkg_root: Path = _PKG / "synapse", catalog_dir: Path = CATALOG_DIR) -> list:
    """``catalog_audit`` over the live tree: raw scan + recipe payloads + LOP subset."""
    type_files: dict[str, set] = {}
    for t, files in scan_createnode_literals(pkg_root).items():
        type_files.setdefault(t, set()).update(files)
    for t, files in scan_recipe_payload_types().items():
        type_files.setdefault(t, set()).update(files)
    merged = {t: sorted(f) for t, f in type_files.items()}
    return catalog_audit(merged, scan_lop_createnode_literals(pkg_root), load_catalog_index(catalog_dir))


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
    for type_name, files in scan_recipe_payload_types().items():
        add(type_name, "recipe_payload", files)
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


def _print_audit(violations: list) -> None:
    for v in violations:
        where = ", ".join(v["source_files"])
        via = f" via {v['receiver']}.createNode" if v.get("receiver") else ""
        print(f"AUDIT {v['verdict'].upper()}: {v['type_name']}{via} "
              f"(catalog: {v['categories'] or 'absent'}) <- {where}")
    print(f"AUDIT: {len(violations)} phantom/deprecated emitted node type(s)")


def main(argv: list[str]) -> int:
    payload = build_payload()
    text = render(payload)
    violations = audit_tree()
    if "--check" in argv:
        if not OUTPUT.exists():
            print(f"MISSING: {OUTPUT}")
            return 1
        committed = json.loads(OUTPUT.read_text(encoding="utf-8"))
        same = committed.get("entries") == payload["entries"]
        print(f"CHECK: entries {'match' if same else 'DRIFTED'} "
              f"({len(payload['entries'])} scanned vs {len(committed.get('entries', []))} committed)")
        _print_audit(violations)
        return 0 if same and not violations else 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"WROTE: {len(payload['entries'])} node types -> {OUTPUT}")
    _print_audit(violations)
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
