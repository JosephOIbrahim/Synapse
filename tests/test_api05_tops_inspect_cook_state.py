"""API-05: the ``inspect_cook_state`` recipe in tops_advanced.md teaches real
Houdini 22.0.400 PDG names.

The recipe is retrieved by knowledge_lookup / scout, so a phantom in it
re-teaches the bug to every agent that asks how to find failed work items.
The previous version used names that do not exist on 22.0.400:
``pdg.workItemState.Cooked/Failed/Cancelled``, ``GraphContext.workItems``,
``WorkItem.stringAttrib/intAttrib`` and the ``pdg_error`` / ``pdg_errorcount``
attributes.

Ground truth is the isolated hython assay of 2026-10-07 (assay_lx.log section E,
assay_lx_e2.log, probe_kind.log under synapse_night_loop/cto-20261007):

* workItemState: Uncooked=1 Waiting=2 Scheduled=3 Cooking=4 CookedSuccess=5
  CookedCache=6 CookedFail=7 CookedCancel=8 Dirty=9
* GraphContext.graph is a property, Graph.nodes() a method, Node.workItems
  and WorkItem.logMessages / state / name properties
* stringAttribValue / intAttribValue(name, index=0) return None when missing
* a failed item carries no pdg_error attribute; its error text is logMessages

Pure Python: the recipe runs against fakes whose attribute kinds mirror the
assay, and every pdg name it touches is checked against the committed
introspected symbol table. No ``hou`` or ``pdg`` import.
"""

from __future__ import annotations

import ast
import builtins
import enum
import json
import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_DOC = _REPO / "rag" / "skills" / "houdini21-reference" / "tops_advanced.md"
_SYMBOLS = _REPO / "python" / "synapse" / "cognitive" / "tools" / "data" / "h22_symbol_table.json"

# Live values read on hython 22.0.400 (assay_lx.log, section E).
ASSAYED_STATES = {
    "Uncooked": 1,
    "Waiting": 2,
    "Scheduled": 3,
    "Cooking": 4,
    "CookedSuccess": 5,
    "CookedCache": 6,
    "CookedFail": 7,
    "CookedCancel": 8,
    "Dirty": 9,
}


def _recipe_source() -> str:
    text = _DOC.read_text(encoding="utf-8")
    blocks = re.findall(r"```python\n(.*?)```", text, flags=re.S)
    hits = [b for b in blocks if "def inspect_cook_state" in b]
    assert len(hits) == 1, f"expected one inspect_cook_state block, found {len(hits)}"
    return hits[0]


def _code_only(src: str) -> str:
    """The recipe with comments removed, so prose that names a phantom in
    order to warn against it does not count as teaching it."""
    return "\n".join(line.split("#", 1)[0] for line in src.splitlines())


# --------------------------------------------------------------------------
# Fakes. Attribute KINDS mirror probe_kind.log: properties are properties,
# methods are methods, and names absent on 22.0.400 are absent here, so a
# phantom raises AttributeError exactly as it does in hython.
# --------------------------------------------------------------------------

_FakeState = enum.IntEnum("workItemState", ASSAYED_STATES)


class _FakeWorkItem:
    __slots__ = ("_name", "_state", "_attrs", "_log")

    def __init__(self, name, state, attrs=None, log=""):
        self._name, self._state, self._attrs, self._log = name, state, attrs or {}, log

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def logMessages(self):
        return self._log

    def stringAttribValue(self, name, index=0):
        v = self._attrs.get(name)
        return v if isinstance(v, str) else None

    def intAttribValue(self, name, index=0):
        v = self._attrs.get(name)
        return v if isinstance(v, int) else None


class _FakePdgNode:
    __slots__ = ("_name", "_items")

    def __init__(self, name, items):
        self._name, self._items = name, items

    @property
    def name(self):
        return self._name

    @property
    def workItems(self):
        return list(self._items)


class _FakeGraph:
    __slots__ = ("_nodes",)

    def __init__(self, nodes):
        self._nodes = nodes

    def nodes(self):
        return list(self._nodes)


class _FakeGraphContext:
    __slots__ = ("_graph",)

    def __init__(self, graph):
        self._graph = graph

    @property
    def graph(self):
        return self._graph


class _FakeTopNode:
    def __init__(self, ctx):
        self._ctx = ctx

    def getPDGGraphContext(self):
        return self._ctx


class _FakeTopnet:
    def __init__(self, children):
        self._children = children

    def node(self, name):
        return self._children.get(name)


_FAIL_LOG = (
    "[11:13:49.857] ERROR: Failed to run script:\n"
    "Traceback (most recent call last):\n"
    '  File "proc_script", line 2, in <module>\n'
    "RuntimeError: assay failure\n\n\n"
)


def _run_recipe(capsys):
    proc_items = [
        _FakeWorkItem("proc_4", _FakeState.CookedSuccess, {"frame": 1001}),
        _FakeWorkItem("proc_5", _FakeState.CookedFail, {"frame": 1002}, log=_FAIL_LOG),
        _FakeWorkItem("proc_6", _FakeState.CookedCache),
    ]
    gen_items = [_FakeWorkItem(f"gen_{i}", _FakeState.CookedSuccess) for i in (1, 2, 3)]
    ctx = _FakeGraphContext(_FakeGraph([
        _FakePdgNode("proc", proc_items),
        _FakePdgNode("gen", gen_items),
    ]))
    topnet = _FakeTopnet({"ropfetch1": _FakeTopNode(ctx)})

    class _Hou:
        @staticmethod
        def node(path):
            return topnet if path == "/obj/topnet1" else None

    class _Pdg:
        workItemState = _FakeState

    fakes = {"hou": _Hou, "pdg": _Pdg}
    real_import = builtins.__import__

    def _import(name, *args, **kwargs):
        return fakes[name] if name in fakes else real_import(name, *args, **kwargs)

    safe_builtins = dict(vars(builtins))
    safe_builtins["__import__"] = _import
    ns = {"__builtins__": safe_builtins, "__name__": "tops_recipe"}
    exec(compile(_recipe_source(), str(_DOC), "exec"), ns)
    result = ns["inspect_cook_state"]()
    return result, capsys.readouterr().out


def test_recipe_runs_against_h22_shaped_pdg(capsys):
    failed, out = _run_recipe(capsys)
    assert [f["name"] for f in failed] == ["proc_5"]
    rec = failed[0]
    assert rec["node"] == "proc"
    assert rec["frame"] == 1002
    assert rec["shot"] == ""  # missing attribute -> None -> "or" default
    assert "RuntimeError: assay failure" in rec["log"]
    assert "RuntimeError: assay failure" in out


def test_state_values_comment_matches_assay():
    src = _recipe_source()
    pairs = dict(re.findall(r"\b([A-Z][A-Za-z]+)=(\d+)\b", src))
    taught = {k: int(v) for k, v in pairs.items()}
    assert taught == ASSAYED_STATES


def test_no_phantom_pdg_names_in_recipe_code():
    code = _code_only(_recipe_source())
    for phantom in (
        r"\.Cooked\b", r"\.Failed\b", r"\.Cancelled\b",
        r"\.stringAttrib\(", r"\.intAttrib\(",
        r"\bctx\.workItems\b", r"\bgraph\.workItems\b",
        r"pdg_error", r"pdg_errorcount",
        r"\.logMessages\(",   # a property on 22.0.400, calling it raises
    ):
        assert not re.search(phantom, code), f"recipe still teaches {phantom!r}"


def test_every_pdg_member_the_recipe_touches_exists_in_h22_symbol_table():
    symbols = set(json.loads(_SYMBOLS.read_text(encoding="utf-8"))["symbols"])
    tree = ast.parse(_recipe_source())
    # Variable -> the pdg class its attributes resolve against.
    owner = {"S": "workItemState", "item": "WorkItem", "pdg_node": "Node", "ctx": "GraphContext"}
    checked = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        base = node.value
        if isinstance(base, ast.Name) and base.id in owner:
            checked.append(f"pdg.{owner[base.id]}.{node.attr}")
        elif (isinstance(base, ast.Attribute) and base.attr == "graph"
              and isinstance(base.value, ast.Name) and base.value.id == "ctx"):
            checked.append(f"pdg.Graph.{node.attr}")
        elif (isinstance(base, ast.Attribute) and base.attr == "workItemState"
              and isinstance(base.value, ast.Name) and base.value.id == "pdg"):
            checked.append(f"pdg.workItemState.{node.attr}")
    assert len(checked) >= 10, checked  # the walk actually found the recipe's surface
    missing = sorted({s for s in checked if s not in symbols})
    assert not missing, f"names absent from h22_symbol_table.json: {missing}"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
