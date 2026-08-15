"""W5-UNDO: handlers_node mutations enter exactly one undo group.

Pins acceptance predicate 1 of the W5-UNDO mission: under a mocked ``hou``,
each of the ``handlers_node.py`` mutation handlers (create/connect/delete)
wraps its ``hou`` mutations in exactly one ``hou.undos.group(...)`` so a single
artist Ctrl+Z reverses the whole operation — and does so with nesting that
matches the established wrapped-handler pattern (a handler called inside an
outer group opens exactly one *nested* group and unwinds cleanly).

Grouping only, NOT rollback: these tests assert the group is *entered around*
the mutation, never that an exception is auto-reversed. The live one-Ctrl+Z
verification is a GUI receipt and lives outside CI (recorded UNKNOWN until an
artist confirms it).

Scope note pinned by ``test_set_parm_lives_in_handlers_py_and_is_unwrapped``:
the mission's fourth named handler, ``set_parm``, is NOT in handlers_node.py —
it is ``handlers.py::_handle_set_parm`` and remains unwrapped. This leg wraps
the three handlers that genuinely live in handlers_node.py; set_parm is a
follow-up leg on a file outside this mission's ``touches``.
"""

import re
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ── hou stub bootstrap (must precede handler import) ────────────────
if "hou" not in sys.modules:
    sys.modules["hou"] = types.ModuleType("hou")


# ── An undo-group recorder that tracks open depth + mutation timing ─
class _UndoRecorder:
    """Records every group opened and the open-depth at each mutation.

    ``groups`` is the ordered list of group names opened; ``depth`` is the
    current nesting depth; ``mutations`` is a list of ``(op, depth_at_call)``.
    A mutation recorded at depth >= 1 happened *inside* a group.
    """

    def __init__(self):
        self.groups = []
        self.depth = 0
        self.max_depth = 0
        self.mutations = []

    def group(self, name=""):
        return _UndoGroupCtx(self, name)


class _UndoGroupCtx:
    def __init__(self, rec, name):
        self._rec = rec
        self._name = name

    def __enter__(self):
        self._rec.groups.append(self._name)
        self._rec.depth += 1
        self._rec.max_depth = max(self._rec.max_depth, self._rec.depth)
        return self

    def __exit__(self, *exc):
        self._rec.depth -= 1
        return False  # never swallow — grouping is not rollback


class _MockNode:
    """A hou.Node stand-in whose mutating calls record the undo depth."""

    def __init__(self, rec, path, name, ntype="null"):
        self._rec = rec
        self._path = path
        self._name = name
        self._ntype = ntype

    def path(self):
        return self._path

    def name(self):
        return self._name

    def type(self):
        t = MagicMock()
        t.name.return_value = self._ntype
        return t

    # ── mutations (each records the depth it fired at) ──
    def createNode(self, node_type, name=None):
        self._rec.mutations.append(("createNode", self._rec.depth))
        child_name = name or node_type
        return _MockNode(self._rec, f"{self._path}/{child_name}", child_name, node_type)

    def moveToGoodPosition(self):
        self._rec.mutations.append(("moveToGoodPosition", self._rec.depth))

    def layoutChildren(self):
        self._rec.mutations.append(("layoutChildren", self._rec.depth))

    def cook(self, force=False):
        self._rec.mutations.append(("cook", self._rec.depth))

    def destroy(self):
        self._rec.mutations.append(("destroy", self._rec.depth))

    def setInput(self, idx, src, out=0):
        self._rec.mutations.append(("setInput", self._rec.depth))

    def parm(self, name):
        return MagicMock()


@pytest.fixture
def env(monkeypatch):
    """Wire handlers_node to a recorder-backed hou and a synchronous
    run_on_main, then hand back (handler, hou_mock, recorder)."""
    # Synchronous main-thread execution (no real Houdini worker).
    if "hdefereval" not in sys.modules:
        hde = types.ModuleType("hdefereval")
        hde.executeInMainThreadWithResult = lambda fn: fn()
        hde.executeDeferred = lambda fn: fn()
        sys.modules["hdefereval"] = hde
    # Synchronicity comes from run_on_main's fast-path-2 — pytest runs on the
    # main thread (main_thread.py:399), so _on_main executes inline — with the
    # synchronous hdefereval stub above as a backstop. run_on_main reads no
    # _USE_DEFERRED / _HOU_AVAILABLE knob, so none is set here.

    rec = _UndoRecorder()
    hou_mock = types.ModuleType("hou")
    hou_mock.undos = rec
    hou_mock.node = MagicMock(return_value=None)

    from synapse.server import handlers_node
    monkeypatch.setattr(handlers_node, "hou", hou_mock, raising=False)
    monkeypatch.setattr(handlers_node, "HOU_AVAILABLE", True, raising=False)

    handler = type(
        "H",
        (handlers_node.NodeHandlerMixin,),
        {"_get_bridge": lambda self: None, "_session_id": None},
    )()
    return handler, hou_mock, rec


# ── create_node ────────────────────────────────────────────────────

def test_create_node_enters_exactly_one_group(env):
    handler, hou_mock, rec = env
    parent = _MockNode(rec, "/stage", "stage", "stage")
    hou_mock.node = MagicMock(return_value=parent)

    result = handler._handle_create_node(
        {"parent": "/stage", "type": "null", "name": "n1"}
    )

    # Exactly one group, correctly named, fully unwound.
    assert rec.groups == ["synapse_node_create"]
    assert rec.depth == 0
    # Every mutation happened inside the group.
    assert rec.mutations, "expected at least the createNode mutation"
    assert all(depth == 1 for _op, depth in rec.mutations)
    assert {op for op, _ in rec.mutations} == {"createNode", "moveToGoodPosition"}
    # Return shape unchanged (grouping only).
    assert set(result) == {"path", "type", "name"}


def test_create_materiallibrary_scaffold_shares_one_group(env):
    """The MaterialX auto-populate (extra createNodes + parm sets) must live in
    the SAME single group as the parent create — one Ctrl+Z undoes it all."""
    handler, hou_mock, rec = env
    parent = _MockNode(rec, "/stage", "stage", "stage")
    hou_mock.node = MagicMock(return_value=parent)

    result = handler._handle_create_node(
        {"parent": "/stage", "type": "materiallibrary", "name": "matlib1"}
    )

    assert rec.groups == ["synapse_node_create"]  # exactly one, not one-per-child
    assert rec.depth == 0
    ops = [op for op, _ in rec.mutations]
    assert ops.count("createNode") >= 3  # matlib + shader + uv_reader
    assert "layoutChildren" in ops
    assert all(depth == 1 for _op, depth in rec.mutations)
    assert result["materialx_ready"] is True


# ── delete_node ────────────────────────────────────────────────────

def test_delete_node_enters_exactly_one_group(env):
    handler, hou_mock, rec = env
    node = _MockNode(rec, "/stage/n1", "n1")
    hou_mock.node = MagicMock(return_value=node)

    result = handler._handle_delete_node({"node": "/stage/n1"})

    assert rec.groups == ["synapse_node_delete"]
    assert rec.depth == 0
    assert rec.mutations == [("destroy", 1)]
    assert set(result) == {"deleted", "name"}


# ── connect_nodes ──────────────────────────────────────────────────

def test_connect_nodes_enters_exactly_one_group(env):
    handler, hou_mock, rec = env
    src = _MockNode(rec, "/stage/a", "a")
    tgt = _MockNode(rec, "/stage/b", "b")
    hou_mock.node = MagicMock(side_effect=lambda p: {"/stage/a": src, "/stage/b": tgt}.get(p))

    result = handler._handle_connect_nodes({"source": "/stage/a", "target": "/stage/b"})

    assert rec.groups == ["synapse_node_connect"]
    assert rec.depth == 0
    assert rec.mutations == [("setInput", 1)]
    assert set(result) == {"source", "target", "source_output", "target_input"}


# ── exception path: grouping is NOT rollback, error routing unchanged ─
# The mutation raises INSIDE the group. Grouping must not swallow it (the group
# closes and the identical exception propagates) — this is the "grouping only,
# not rollback / zero error-routing change" guarantee. A regression that wrapped
# the mutation in a try/except-pass would pass every happy-path test above but
# fail these.

def test_create_propagates_and_closes_group_on_error(env):
    handler, hou_mock, rec = env
    parent = _MockNode(rec, "/stage", "stage", "stage")

    def _boom(*a, **k):
        rec.mutations.append(("createNode", rec.depth))
        raise RuntimeError("createNode failed")

    parent.createNode = _boom
    hou_mock.node = MagicMock(return_value=parent)

    with pytest.raises(RuntimeError, match="createNode failed"):
        handler._handle_create_node({"parent": "/stage", "type": "null"})

    assert rec.groups == ["synapse_node_create"]  # opened around the mutation
    assert rec.mutations == [("createNode", 1)]  # raised while inside the group
    assert rec.depth == 0  # group closed on the exception path (not swallowed)


def test_delete_propagates_and_closes_group_on_error(env):
    handler, hou_mock, rec = env
    node = _MockNode(rec, "/stage/n1", "n1")

    def _boom():
        rec.mutations.append(("destroy", rec.depth))
        raise RuntimeError("destroy failed")

    node.destroy = _boom
    hou_mock.node = MagicMock(return_value=node)

    with pytest.raises(RuntimeError, match="destroy failed"):
        handler._handle_delete_node({"node": "/stage/n1"})

    assert rec.groups == ["synapse_node_delete"]
    assert rec.mutations == [("destroy", 1)]
    assert rec.depth == 0


def test_connect_propagates_and_closes_group_on_error(env):
    handler, hou_mock, rec = env
    src = _MockNode(rec, "/stage/a", "a")
    tgt = _MockNode(rec, "/stage/b", "b")

    def _boom(*a, **k):
        rec.mutations.append(("setInput", rec.depth))
        raise RuntimeError("setInput failed")

    tgt.setInput = _boom
    hou_mock.node = MagicMock(side_effect=lambda p: {"/stage/a": src, "/stage/b": tgt}.get(p))

    with pytest.raises(RuntimeError, match="setInput failed"):
        handler._handle_connect_nodes({"source": "/stage/a", "target": "/stage/b"})

    assert rec.groups == ["synapse_node_connect"]
    assert rec.mutations == [("setInput", 1)]
    assert rec.depth == 0


# ── nested-group behavior (matches the wrapped-handler pattern) ─────

@pytest.mark.parametrize(
    "call,label,setup",
    [
        (
            "create",
            "synapse_node_create",
            lambda rec: {"/stage": _MockNode(rec, "/stage", "stage", "stage")},
        ),
        (
            "delete",
            "synapse_node_delete",
            lambda rec: {"/stage/n1": _MockNode(rec, "/stage/n1", "n1")},
        ),
        (
            "connect",
            "synapse_node_connect",
            lambda rec: {
                "/stage/a": _MockNode(rec, "/stage/a", "a"),
                "/stage/b": _MockNode(rec, "/stage/b", "b"),
            },
        ),
    ],
)
def test_handler_nests_exactly_one_group_inside_an_outer_group(env, call, label, setup):
    """A handler invoked while an outer group is already open (the batch/atomic
    recipe case, handlers.py:1013) opens exactly ONE nested group and unwinds
    back to the outer depth — the acceptance's 'nested-group behavior'."""
    handler, hou_mock, rec = env
    nodes = setup(rec)
    hou_mock.node = MagicMock(side_effect=lambda p: nodes.get(p))

    with hou_mock.undos.group("outer_batch"):
        assert rec.depth == 1
        if call == "create":
            handler._handle_create_node({"parent": "/stage", "type": "null"})
        elif call == "delete":
            handler._handle_delete_node({"node": "/stage/n1"})
        else:
            handler._handle_connect_nodes({"source": "/stage/a", "target": "/stage/b"})
        # Handler opened exactly one own group, nested inside the outer.
        assert rec.groups == ["outer_batch", label]
        assert rec.depth == 1  # back inside the outer after the handler returns
        # Every handler mutation fired at depth 2 (inside both groups).
        assert all(depth == 2 for _op, depth in rec.mutations)

    assert rec.depth == 0  # outer closed cleanly
    assert rec.max_depth == 2


# ── scope finding pin: set_parm is elsewhere and still unwrapped ────

def test_set_parm_now_wraps_in_handlers_py():
    """W5-UNDOB closed the set_parm Ctrl+Z hole. set_parm still lives in
    handlers.py (NOT on NodeHandlerMixin), but now wraps its parm.set /
    parm_tuple.set mutations in hou.undos.group("synapse_set_parm"). This is the
    flipped successor of W5-UNDO's ...is_unwrapped pin — kept so a regression
    that DROPS the wrap reddens here too, not only in
    tests/test_undob_live_undo_grouping.py."""
    import synapse.server.handlers_node as hn

    assert not hasattr(hn.NodeHandlerMixin, "_handle_set_parm"), (
        "set_parm unexpectedly appeared on NodeHandlerMixin — the scope finding "
        "(set_parm lives in handlers.py) is stale; re-check the receipt."
    )

    handlers_py = Path(hn.__file__).with_name("handlers.py")
    text = handlers_py.read_text(encoding="utf-8")
    m = re.search(r"\n    def _handle_set_parm\(.*?(?=\n    def )", text, re.S)
    assert m, "could not locate _handle_set_parm in handlers.py"
    assert 'hou.undos.group("synapse_set_parm")' in m.group(0), (
        "set_parm no longer wraps in handlers.py — W5-UNDOB closed this Ctrl+Z "
        "hole; a regression dropped the hou.undos.group wrap."
    )
