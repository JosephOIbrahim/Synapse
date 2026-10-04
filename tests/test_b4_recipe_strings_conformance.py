"""B4: the catalog ratchet, extended to code the product sends as strings.

test_harden_catalog_conformance reads node types and parm names from call
sites. It cannot see a recipe step that carries its Houdini code as a string
(``execute_python`` payload templates). This test reads
the string constants under ``python/synapse/routing/`` for ``createNode('x'``
and ``.parm('x')`` / ``.parmTuple('x')`` and checks the names against the same
22.0.400 catalog, with its own baseline.

Same ratchet rules: a new miss fails, and a baseline entry that stops missing
fails, so the list only shrinks. A baseline entry is a lead, not proof of a
bug: a name passes if ANY node type has it, and HDA or spare parms are not in
the catalog.

Pure Python: no hou, no import of synapse.*.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from test_harden_catalog_conformance import _parm_known, load_catalog  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCANNED = ROOT / "python" / "synapse" / "routing"
BASELINE = Path(__file__).resolve().parent / "fixtures" / "recipe_strings_conformance_baseline.json"

_CREATE = re.compile(r"""\.create(?:Output|Input)?Node\(\s*['"]([A-Za-z0-9_:.]+)['"]""")
_PARM = re.compile(r"""\.(?:parm|parmTuple|evalParm|evalParmTuple)\(\s*['"]([A-Za-z0-9_#]+)['"]""")


def _strings(path):
    """Every string the module holds, with adjacent literals already joined by the parser."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "(" in node.value:
            yield node.value


def scan_strings():
    found = set()
    for path in sorted(SCANNED.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        for text in _strings(path):
            if "{" in text:
                # payload templates double their braces; names never contain one
                text = text.replace("{{", "{").replace("}}", "}")
            for name in _CREATE.findall(text):
                found.add(("str_type", rel, name))
            for name in _PARM.findall(text):
                found.add(("str_parm", rel, name))
    return found


def current_misses():
    types, parms, _ = load_catalog()
    misses = set()
    for kind, rel, literal in scan_strings():
        known = literal in types if kind == "str_type" else _parm_known(literal, parms)
        if not known:
            misses.add(f"{kind}|{rel}|{literal}")
    return misses


@pytest.fixture(scope="module")
def misses():
    return current_misses()


@pytest.fixture(scope="module")
def baseline():
    return set(json.loads(BASELINE.read_text(encoding="utf-8"))["misses"])


def test_the_scan_finds_the_recipes():
    found = scan_strings()
    assert len(found) > 50, len(found)
    assert any(kind == "str_type" and name == "cop2net" for kind, _, name in found)


def test_no_new_name_in_a_code_string_is_missing_from_the_recording_build(misses, baseline):
    new = sorted(misses - baseline)
    assert not new, (
        "Names in code strings that rag/catalog/h22.0.400 does not have. Fix the name, or "
        "add it to tests/fixtures/recipe_strings_conformance_baseline.json only for a parm "
        "the product creates itself:\n  " + "\n  ".join(new))


def test_the_string_baseline_only_shrinks(misses, baseline):
    fixed = sorted(baseline - misses)
    assert not fixed, (
        "These baseline entries no longer miss. Remove them from "
        "tests/fixtures/recipe_strings_conformance_baseline.json:\n  " + "\n  ".join(fixed))
