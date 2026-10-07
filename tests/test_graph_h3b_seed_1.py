"""F04: a per-variant material parm that does not exist must be reported.

create_variants used to drop a misspelled ``v['material']`` parm behind
``if p:`` and still return status 'created'. Hou-free.
"""
import contextlib
from types import SimpleNamespace

from synapse.mcp.tool_impls.solaris import create_variants as cv


class _Type:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _Node:
    def __init__(self, type_name, name, children=()):
        self._type = _Type(type_name)
        self._name = name
        self._children = list(children)

    def type(self):
        return self._type

    def name(self):
        return self._name

    def setName(self, name, unique_name=False):
        self._name = name

    def parm(self, name):
        return None

    def children(self):
        return self._children

    def childTypeCategory(self):
        return _Type("Lop")

    def parent(self):
        return None

    def layoutChildren(self):
        pass

    def setUserData(self, *a):
        pass


def test_missing_material_parm_is_reported(monkeypatch):
    mat = _Node("componentmaterial", "componentmaterial1")
    comp = _Node("componentbuilder", "comp", children=[mat])
    fake_hou = SimpleNamespace(
        node=lambda path: comp,
        copyNodesTo=lambda nodes, parent: [mat],
        undos=SimpleNamespace(group=lambda label: contextlib.nullcontext()),
    )
    monkeypatch.setattr(cv, "hou", fake_hou)
    monkeypatch.setattr(cv, "HOU_AVAILABLE", True)

    result = cv.execute({
        "component_path": "/stage/comp",
        "variant_type": "material",
        "variants": [{"name": "a", "material": {"nope": 1}}, {"name": "b"}],
        "add_explore_node": False,
    })

    assert result["status"] == "created"
    assert result["parms_missed"] == ["componentmaterial.nope"]
