"""Goalpost: node types and parm names the product writes exist on the recording build.

Born from the 2026-10-04 SideFX cross-reference: several tools wrote parm names
that do not exist (``soppath``, ``resx``, ``pdg_framerange`` ...), each guarded
by ``if parm:``, so the write was skipped and the tool still reported success.

The oracle is the parm catalog dumped from the recording build,
``rag/catalog/h22.0.400/*.json``. This is a RATCHET, like test_except_ratchet:

  * a literal ``createNode("x")`` type that is in no catalog category, or a
    literal ``parm("x")`` / ``parmTuple("x")`` / ``evalParm("x")`` name that is
    on no node type in any category, is a MISS;
  * today's misses are recorded in ``fixtures/catalog_conformance_baseline.json``;
  * a NEW miss fails. A baseline entry that no longer misses also fails, so the
    list can only shrink.

What it cannot see: names built at run time, names inside code sent as strings,
and a real parm name used on the wrong node type (a name passes if ANY node type
has it). A baseline entry is not proof of a bug: HDA and spare parms the product
creates itself are not in the catalog either. It is the list to work through.

Pure Python: no hou, no import of synapse.*.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "rag" / "catalog" / "h22.0.400"
PRODUCT = ROOT / "python" / "synapse"
BASELINE = Path(__file__).resolve().parent / "fixtures" / "catalog_conformance_baseline.json"
_CREATE = {"createNode", "createOutputNode", "createInputNode"}
_PARM = {"parm", "parmTuple", "evalParm", "evalParmTuple"}


_CACHE = {}


def load_catalog():
    """(all type names, all parm names, {type name: its parm names across categories and versions})."""
    if _CACHE:
        return _CACHE["types"], _CACHE["parms"], _CACHE["by_type"]
    types, parms, by_type = set(), set(), {}
    for path in sorted(CATALOG.glob("*.json")):
        if path.name.startswith("_") or path.name == "apex_callbacks.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for name, record in (data.get("types") or {}).items():
            parts = name.split("::")
            # "light::2.0" -> "light"; "Labs::thing::1.0" -> "thing", "Labs::thing"
            core = [p for p in parts if not re.fullmatch(r"[\d.]+", p)]
            names = {name, core[-1], "::".join(core)}
            types |= names
            own = {p["name"] for p in record.get("parms") or []
                   if isinstance(p, dict) and isinstance(p.get("name"), str)}
            parms |= own
            for alias in names:
                by_type.setdefault(alias, set()).update(own)
    _CACHE.update(types=types, parms=parms, by_type=by_type)
    return types, parms, by_type


def scan_product():
    """Yield (kind, relative_path, literal) for every literal node type and parm name."""
    found = set()
    for path in sorted(PRODUCT.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if "/_vendor/" in rel or "/tests/" in rel:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.args):
                continue
            first = node.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value):
                continue
            if node.func.attr in _CREATE:
                found.add(("type", rel, first.value))
            elif node.func.attr in _PARM:
                found.add(("parm", rel, first.value))
        # Typed pass: inside one function, ``x = parent.createNode("t")`` followed
        # by ``x.parm("p")`` ties the parm name to that node type.
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            created = {}
            for node in ast.walk(func):
                if (isinstance(node, ast.Assign) and len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)
                        and isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Attribute)
                        and node.value.func.attr in _CREATE and node.value.args
                        and isinstance(node.value.args[0], ast.Constant)
                        and isinstance(node.value.args[0].value, str)):
                    created.setdefault(node.targets[0].id, set()).add(node.value.args[0].value)
            for node in ast.walk(func):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in _PARM and node.args
                        and isinstance(node.func.value, ast.Name)
                        and len(created.get(node.func.value.id, ())) == 1
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    node_type = next(iter(created[node.func.value.id]))
                    found.add(("typed", rel, f"{node_type}.{node.args[0].value}"))
    return found


def _parm_known(name, parms):
    if name in parms:
        return True
    # multiparm instances: "protogroupprims0" is catalogued as "protogroupprims#"
    templated = re.sub(r"\d+", "#", name)
    return templated in parms or re.sub(r"\d+$", "#", name) in parms


def current_misses():
    types, parms, by_type = load_catalog()
    misses = set()
    for kind, rel, literal in scan_product():
        if kind == "type":
            known = literal in types
        elif kind == "parm":
            known = _parm_known(literal, parms)
        else:  # typed: "<node type>.<parm>"; an unknown type is the "type" miss, not this one
            node_type, parm = literal.split(".", 1)
            known = node_type not in by_type or _parm_known(parm, by_type[node_type])
        if not known:
            misses.add(f"{kind}|{rel}|{literal}")
    return misses


@pytest.fixture(scope="module")
def misses():
    return current_misses()


@pytest.fixture(scope="module")
def baseline():
    return set(json.loads(BASELINE.read_text(encoding="utf-8"))["misses"])


def test_catalog_is_present_and_large():
    types, parms, by_type = load_catalog()
    assert len(types) > 3000 and len(parms) > 10000, (len(types), len(parms))
    assert "maxangle" in by_type["scatterinstances"]
    assert "xn__lightfilters_lva" in by_type["light"]


def test_no_new_name_is_missing_from_the_recording_build(misses, baseline):
    new = sorted(misses - baseline)
    assert not new, (
        "Node types or parm names not found in rag/catalog/h22.0.400 (the recording build). "
        "Fix the name, or check the write and report it when it is missed. Add to the "
        "baseline only for a parm the product creates itself:\n  " + "\n  ".join(new))


def test_baseline_only_shrinks(misses, baseline):
    fixed = sorted(baseline - misses)
    assert not fixed, (
        "These baseline entries no longer miss. Remove them from "
        "tests/fixtures/catalog_conformance_baseline.json:\n  " + "\n  ".join(fixed))


def test_the_scanner_bites(misses):
    """The misses the 2026-10-04 review confirmed by hand must be in the scan."""
    found = {entry.split("|", 1)[0] + "|" + entry.rsplit("|", 1)[1] for entry in misses}
    for known in ("typed|componentgeometry.soppath", "typed|karmarendersettings.resx",
                  "parm|pdg_framerange", "type|componentbuilder"):
        assert known in found, f"scanner no longer sees the known miss {known}"
