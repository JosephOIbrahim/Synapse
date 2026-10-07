"""Every V1 symbol in SCENE_GROUNDING_CONTRACT.md section 5 exists on Houdini 22.0.400.

V1 means "verified in shipped code". The table listed ``attr.floatListData()`` as V1
long after hou.Attrib was shown to have no such member (be0f2e54 replaced it with the
Geometry *AttribValues readers). This reads the V1 rows of the provenance table, turns
each ``receiver.method(`` call into a dotted hou symbol and checks it against the
introspected symbol table, the existence authority named in CLAUDE.md.
"""
from __future__ import annotations

import itertools
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "SCENE_GROUNDING_CONTRACT.md"
TABLE = ROOT / "python" / "synapse" / "cognitive" / "tools" / "data" / "h22_symbol_table.json"
INTROSPECTION = ROOT / "python" / "synapse" / "server" / "introspection.py"

# Receiver spelling in the contract -> hou class it stands for. ``node`` may be any
# node subclass (geometry() lives on hou.SopNode, not hou.Node).
RECEIVERS = {"hou": "hou", "node": "hou.Node", "geo": "hou.Geometry",
             "attr": "hou.Attrib", "parm": "hou.Parm"}
CALL = re.compile(r"\b(hou|node|geo|attr|parm)\.([A-Za-z_{}\[\],]+)\(")


def _symbols() -> set[str]:
    return set(json.loads(TABLE.read_text(encoding="utf-8"))["symbols"])


def _v1_rows() -> list[str]:
    text = CONTRACT.read_text(encoding="utf-8")
    start = text.index("### 5. Symbol provenance")
    end = text.index("### 6.", start)
    return [line for line in text[start:end].splitlines()
            if line.startswith("|") and "**V1" in line]


def _expand(name: str) -> list[str]:
    """``{point,prim}{Float,Int}[List]AttribValues`` -> every concrete spelling."""
    parts = re.split(r"(\{[^}]*\}|\[[^\]]*\])", name)
    choices = []
    for part in parts:
        if part.startswith("{"):
            choices.append(part[1:-1].split(","))
        elif part.startswith("["):
            choices.append(["", part[1:-1]])
        else:
            choices.append([part])
    return ["".join(combo) for combo in itertools.product(*choices)]


def _calls(row: str) -> list[tuple[str, str]]:
    found = []
    for span in re.findall(r"`([^`]+)`", row):
        for receiver, method in CALL.findall(span):
            found.extend((receiver, m) for m in _expand(method))
    return found


def _exists(receiver: str, method: str, symbols: set[str]) -> bool:
    if receiver == "hou":
        return f"hou.{method}" in symbols
    if receiver == "node":
        return any(s.endswith(f"Node.{method}") and s.count(".") == 2 for s in symbols)
    return f"{RECEIVERS[receiver]}.{method}" in symbols


def test_the_table_has_v1_calls_to_check():
    calls = [c for row in _v1_rows() for c in _calls(row)]
    assert len(calls) >= 15, calls


def test_every_v1_symbol_exists_in_the_h22_symbol_table():
    symbols = _symbols()
    missing = sorted({f"{r}.{m}" for row in _v1_rows() for r, m in _calls(row)
                      if not _exists(r, m, symbols)})
    assert missing == [], f"V1 rows name symbols absent on 22.0.400: {missing}"


def test_floatlistdata_is_not_asserted_as_v1():
    assert not any("floatListData" in c[1] for row in _v1_rows() for c in _calls(row))


def test_the_attribute_value_row_names_the_readers_the_code_uses():
    rows = [r for r in _v1_rows() if "AttribValues" in r]
    assert len(rows) == 1, rows
    named = {m for _, m in _calls(rows[0])}
    source = INTROSPECTION.read_text(encoding="utf-8")
    used = set(re.findall(r'"((?:point|prim)(?:Float|Int)(?:List)?AttribValues)"', source))
    assert used and used <= named, sorted(used - named)
    assert "geo.attribValue(" in source and "attribValue" in named


def test_the_expander_spells_out_every_reader():
    assert sorted(_expand("{point,prim}{Float,Int}[List]AttribValues")) == sorted(
        f"{c}{t}{a}AttribValues" for c in ("point", "prim") for t in ("Float", "Int")
        for a in ("", "List"))
