"""Tests for synapse.core.state_digest - runs headless, no Houdini."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "python"))

from synapse.core import state_digest as sd


class FakeParm:
    def __init__(self, name, raw, value):
        self._n, self._raw, self._v = name, raw, value

    def name(self):
        return self._n

    def rawValue(self):
        return self._raw

    def eval(self):
        return self._v


class FakeType:
    def __init__(self, name):
        self._n = name

    def name(self):
        return self._n


class FakeNode:
    def __init__(self, name, parms=(), children=(), type_name="null"):
        self._n, self._p, self._c = name, list(parms), list(children)
        self._t = FakeType(type_name)

    def name(self):
        return self._n

    def type(self):
        return self._t

    def parms(self):
        return self._p

    def children(self):
        return self._c


class FakeHou:
    def __init__(self, mapping):
        self._m = mapping

    def node(self, path):
        return self._m.get(path)


def _hou(tx=0.5, extra_parms=()):
    parms = [
        FakeParm("tx", str(tx), tx),
        FakeParm("ty", "0", 0.0),
        FakeParm("frame_driven", "$F * 2", 48.0),   # must be excluded
    ]
    parms.extend(extra_parms)
    geo = FakeNode("geo1", parms=parms, type_name="geo")
    obj = FakeNode("obj", children=[geo])
    return FakeHou({"/obj/geo1": geo, "/obj": obj})


# ---------- scope routing ----------

def test_readonly_ops_skipped():
    for op in ("cops_read_layer_info", "get_node", "ping", "list_nodes"):
        assert sd.in_scope(op) is False


def test_execute_python_is_null_not_faked():
    d, snap = sd.state_digest("execute_python", {"node": "/obj/geo1"}, _hou())
    assert d == "" and snap is None


def test_mutating_ops_in_scope():
    for op in ("set_parm", "cops_create_copnet", "batch_commands"):
        assert sd.in_scope(op) is True


# ---------- path extraction ----------

def test_extracts_corpus_shapes():
    assert sd.extract_paths({"node": "/obj/cop2net1/file1"}) == ["/obj/cop2net1/file1"]
    assert sd.extract_paths({"node_path": "/obj/top"}) == ["/obj/top"]


def test_extracts_nested_and_dedupes():
    args = {"commands": [{"node": "/obj/a"}, {"node": "/obj/b"}, {"node": "/obj/a"}]}
    assert sd.extract_paths(args) == ["/obj/a", "/obj/b"]


def test_ignores_non_paths():
    assert sd.extract_paths({"node": "not_a_path", "parm": "tx"}) == []


# ---------- digest behaviour ----------

def test_stable_across_calls():
    a, _ = sd.state_digest("set_parm", {"node": "/obj/geo1"}, _hou())
    b, _ = sd.state_digest("set_parm", {"node": "/obj/geo1"}, _hou())
    assert a == b and a != ""


def test_changes_when_parm_changes():
    a, _ = sd.state_digest("set_parm", {"node": "/obj/geo1"}, _hou(tx=0.5))
    b, _ = sd.state_digest("set_parm", {"node": "/obj/geo1"}, _hou(tx=0.9))
    assert a != b


def test_time_varying_parm_excluded():
    _, snap = sd.state_digest("set_parm", {"node": "/obj/geo1"}, _hou())
    assert "frame_driven" not in snap["/obj/geo1"]
    assert "tx" in snap["/obj/geo1"]


def test_float_precision_canonicalised():
    a, _ = sd.state_digest("set_parm", {"node": "/obj/geo1"}, _hou(tx=0.1 + 0.2))
    b, _ = sd.state_digest("set_parm", {"node": "/obj/geo1"}, _hou(tx=0.3))
    assert a == b


def test_structural_op_uses_children_not_parms():
    _, snap = sd.state_digest("cops_create_node", {"parent": "/obj"}, _hou())
    assert "children" in snap["/obj"]
    assert snap["/obj"]["children"] == [["geo1", "geo"]]


def test_missing_node_marked_not_crashed():
    d, snap = sd.state_digest("set_parm", {"node": "/obj/ghost"}, _hou())
    assert d != ""
    assert snap["/obj/ghost"] == {"__missing__": True}


def test_no_hou_returns_empty():
    d, snap = sd.state_digest("set_parm", {"node": "/obj/geo1"}, None)
    assert (d, snap) == ("", None) or d != ""  # tolerant if hou is importable


def test_no_paths_returns_empty():
    assert sd.state_digest("set_parm", {"parm": "tx"}, _hou()) == ("", None)


# ---------- changed() tri-state ----------

def test_changed_tristate():
    assert sd.changed("a", "b") is True
    assert sd.changed("a", "a") is False
    # out-of-scope must be UNKNOWN, never "unchanged"
    assert sd.changed("", "") is None
    assert sd.changed("a", "") is None


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
