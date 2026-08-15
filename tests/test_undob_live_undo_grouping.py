"""W5-UNDOB: live-path set_parm + set_keyframe enter exactly one undo group.

Pins the two code acceptance predicates of the W5-UNDOB mission under a mocked
``hou``:
  1. handlers.py::_handle_set_parm wraps its parm.set / parm_tuple.set mutations
     in exactly one hou.undos.group("synapse_set_parm").
  2. handlers_render.py::_handle_set_keyframe wraps its parm.setKeyframe mutation
     in exactly one hou.undos.group("synapse_set_keyframe").
Plus the third predicate (integrity_envelope docstring + CLAUDE.md §1 sync) as
source-text pins.

Grouping only, NOT rollback: the exception-path tests assert the group is
entered *around* the mutation and the identical exception propagates (the group
is never a try/except-pass). The live one-Ctrl+Z verification is a GUI receipt
and lives outside CI (recorded UNKNOWN until an artist confirms it).

Mirrors tests/test_node_undo_grouping.py's recorder harness. Both handlers here
are methods that never touch ``self`` (module-level hou / run_on_main only), so
each is invoked unbound with a throwaway ``self``.
"""

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


class _MockParm:
    """A hou.Parm stand-in whose set()/setKeyframe() record the undo depth."""

    def __init__(self, rec):
        self._rec = rec

    def set(self, value):
        self._rec.mutations.append(("parm.set", self._rec.depth))

    def setKeyframe(self, key):
        self._rec.mutations.append(("parm.setKeyframe", self._rec.depth))


class _MockParmTuple:
    def __init__(self, rec, length=3):
        self._rec = rec
        self._length = length

    def __len__(self):
        return self._length

    def set(self, value):
        self._rec.mutations.append(("parm_tuple.set", self._rec.depth))


class _MockNode:
    """hou.Node stand-in with parm()/parmTuple()/type() for the handlers.

    ``parm`` / ``parm_tuple`` are returned for ANY name (alias fallbacks in the
    handler resolve to the same object), so the tests don't depend on
    USD_PARM_ALIASES contents.
    """

    def __init__(self, rec, parm=None, parm_tuple=None, ntype="null"):
        self._rec = rec
        self._parm = parm
        self._parm_tuple = parm_tuple
        self._ntype = ntype

    def parm(self, name):
        return self._parm

    def parmTuple(self, name):
        return self._parm_tuple

    def type(self):
        t = MagicMock()
        t.name.return_value = self._ntype
        return t


def _make_hou(rec):
    hou_mock = types.ModuleType("hou")
    hou_mock.undos = rec
    hou_mock.node = MagicMock(return_value=None)
    # set_keyframe builds a local key object and reads the current frame.
    hou_mock.Keyframe = lambda: MagicMock()
    hou_mock.frame = lambda: 1.0
    return hou_mock


@pytest.fixture(autouse=True)
def _sync_main_thread():
    """run_on_main runs _on_main inline on the pytest main thread (fast-path-2);
    a synchronous hdefereval stub is the backstop, matching
    tests/test_node_undo_grouping.py."""
    if "hdefereval" not in sys.modules:
        hde = types.ModuleType("hdefereval")
        hde.executeInMainThreadWithResult = lambda fn: fn()
        hde.executeDeferred = lambda fn: fn()
        sys.modules["hdefereval"] = hde
    yield


@pytest.fixture
def set_parm_call(monkeypatch):
    from synapse.server import handlers

    rec = _UndoRecorder()
    hou_mock = _make_hou(rec)
    monkeypatch.setattr(handlers, "hou", hou_mock, raising=False)
    monkeypatch.setattr(handlers, "HOU_AVAILABLE", True, raising=False)

    def _call(payload):
        # _handle_set_parm never touches self — invoke unbound with a dummy.
        return handlers.SynapseHandler._handle_set_parm(object(), payload)

    return _call, hou_mock, rec


@pytest.fixture
def set_keyframe_call(monkeypatch):
    from synapse.server import handlers_render

    rec = _UndoRecorder()
    hou_mock = _make_hou(rec)
    monkeypatch.setattr(handlers_render, "hou", hou_mock, raising=False)
    monkeypatch.setattr(handlers_render, "HOU_AVAILABLE", True, raising=False)

    def _call(payload):
        return handlers_render.RenderHandlerMixin._handle_set_keyframe(object(), payload)

    return _call, hou_mock, rec


# ── predicate 1: set_parm wraps its mutations ───────────────────────

def test_set_parm_scalar_enters_exactly_one_group(set_parm_call):
    call, hou_mock, rec = set_parm_call
    node = _MockNode(rec, parm=_MockParm(rec))
    hou_mock.node = MagicMock(return_value=node)

    result = call({"node": "/obj/geo", "parm": "tx", "value": 0.5})

    assert rec.groups == ["synapse_set_parm"]  # exactly one, correctly named
    assert rec.depth == 0                       # fully unwound
    assert rec.mutations == [("parm.set", 1)]   # mutation fired inside the group
    assert result["node"] == "/obj/geo"
    assert result["parm"] == "tx"
    assert result["value"] == 0.5


def test_set_parm_tuple_via_scalar_name_enters_one_group(set_parm_call):
    """List value with a scalar parm found → the parm_tuple.set fast path
    (handlers.py, the ``parm is not None`` branch) still lands in one group."""
    call, hou_mock, rec = set_parm_call
    node = _MockNode(rec, parm=_MockParm(rec), parm_tuple=_MockParmTuple(rec, 3))
    hou_mock.node = MagicMock(return_value=node)

    result = call({"node": "/obj/light", "parm": "color", "value": [1, 0, 0]})

    assert rec.groups == ["synapse_set_parm"]
    assert rec.depth == 0
    assert rec.mutations == [("parm_tuple.set", 1)]
    assert result["value"] == [1, 0, 0]


def test_set_parm_tuple_path_enters_one_group(set_parm_call):
    """No scalar parm, a parmTuple present → the dedicated tuple branch wraps
    both its list and scalar-broadcast sets in one group."""
    call, hou_mock, rec = set_parm_call
    node = _MockNode(rec, parm=None, parm_tuple=_MockParmTuple(rec, 3))
    hou_mock.node = MagicMock(return_value=node)

    result = call({"node": "/obj/light", "parm": "col", "value": [0.2, 0.4, 0.6]})

    assert rec.groups == ["synapse_set_parm"]
    assert rec.depth == 0
    assert rec.mutations == [("parm_tuple.set", 1)]
    assert result["value"] == [0.2, 0.4, 0.6]


def test_set_parm_propagates_and_closes_group_on_error(set_parm_call):
    """Grouping is NOT rollback: the mutation raises inside the group, the group
    closes, and the identical exception propagates (no try/except-pass)."""
    call, hou_mock, rec = set_parm_call

    class _BoomParm(_MockParm):
        def set(self, value):
            self._rec.mutations.append(("parm.set", self._rec.depth))
            raise RuntimeError("parm.set failed")

    node = _MockNode(rec, parm=_BoomParm(rec))
    hou_mock.node = MagicMock(return_value=node)

    with pytest.raises(RuntimeError, match="parm.set failed"):
        call({"node": "/obj/geo", "parm": "tx", "value": 0.5})

    assert rec.groups == ["synapse_set_parm"]   # opened around the mutation
    assert rec.mutations == [("parm.set", 1)]    # raised while inside the group
    assert rec.depth == 0                         # closed on the exception path


def test_set_parm_nests_one_group_inside_an_outer_group(set_parm_call):
    """Called while an outer group is already open (the atomic-recipe case),
    set_parm opens exactly one nested group and unwinds to the outer depth."""
    call, hou_mock, rec = set_parm_call
    node = _MockNode(rec, parm=_MockParm(rec))
    hou_mock.node = MagicMock(return_value=node)

    with hou_mock.undos.group("outer_batch"):
        assert rec.depth == 1
        call({"node": "/obj/geo", "parm": "tx", "value": 0.5})
        assert rec.groups == ["outer_batch", "synapse_set_parm"]
        assert rec.depth == 1  # back inside the outer after set_parm returns
        assert all(depth == 2 for _op, depth in rec.mutations)

    assert rec.depth == 0
    assert rec.max_depth == 2


# ── predicate 2: set_keyframe wraps its mutation ────────────────────

def test_set_keyframe_with_frame_enters_one_group(set_keyframe_call):
    call, hou_mock, rec = set_keyframe_call
    node = _MockNode(rec, parm=_MockParm(rec))
    hou_mock.node = MagicMock(return_value=node)

    result = call({"node": "/obj/geo", "parm": "tx", "value": 1.0, "frame": 12})

    assert rec.groups == ["synapse_set_keyframe"]
    assert rec.depth == 0
    assert rec.mutations == [("parm.setKeyframe", 1)]
    assert result["frame"] == 12.0
    assert result["parm"] == "tx"


def test_set_keyframe_without_frame_uses_current_frame(set_keyframe_call):
    call, hou_mock, rec = set_keyframe_call
    node = _MockNode(rec, parm=_MockParm(rec))
    hou_mock.node = MagicMock(return_value=node)

    result = call({"node": "/obj/geo", "parm": "ty", "value": 2.0})

    assert rec.groups == ["synapse_set_keyframe"]
    assert rec.depth == 0
    assert rec.mutations == [("parm.setKeyframe", 1)]
    assert result["frame"] == 1.0  # hou.frame() stub


def test_set_keyframe_propagates_and_closes_group_on_error(set_keyframe_call):
    call, hou_mock, rec = set_keyframe_call

    class _BoomParm(_MockParm):
        def setKeyframe(self, key):
            self._rec.mutations.append(("parm.setKeyframe", self._rec.depth))
            raise RuntimeError("setKeyframe failed")

    node = _MockNode(rec, parm=_BoomParm(rec))
    hou_mock.node = MagicMock(return_value=node)

    with pytest.raises(RuntimeError, match="setKeyframe failed"):
        call({"node": "/obj/geo", "parm": "tx", "value": 1.0, "frame": 5})

    assert rec.groups == ["synapse_set_keyframe"]
    assert rec.mutations == [("parm.setKeyframe", 1)]
    assert rec.depth == 0


# ── predicate 3: docstring + CLAUDE.md §1 sync (source-text pins) ────

def _repo_file(*rel):
    # tests/<this file> → repo root is one directory up.
    return Path(__file__).resolve().parents[1].joinpath(*rel)


def test_integrity_envelope_docstring_synced():
    """The honesty docstring no longer inverts reality: it records that the node
    handlers (incl. W5-UNDOB's set_parm + set_keyframe) DO wrap, retracts the
    doc-drift brand, and still honestly records undo as not-verified."""
    import synapse.server.integrity_envelope as ie

    doc = ie.__doc__ or ""
    assert "do NOT" not in doc, "the stale inverted 'do NOT wrap' claim survives"
    assert "DO wrap inline now" in doc
    assert "W5-UNDOB" in doc
    assert "set_parm" in doc and "set_keyframe" in doc
    assert "no longer doc drift" in doc
    # Behavior is unchanged — undo is still recorded not-verified, honestly.
    assert "undo_applicable=False" in doc


def test_claude_md_section1_records_wrapped_state():
    """CLAUDE.md §1 no longer calls set_parm the one remaining hole; it records
    both handlers as wrapped via W5-UNDOB and the docstring as synced."""
    text = _repo_file("CLAUDE.md").read_text(encoding="utf-8")

    assert "is UNWRAPPED still" not in text, "stale one-hole set_parm claim survives"
    assert "synced by W5-UNDOB" in text
    assert "_handle_set_parm" in text
    assert "_handle_set_keyframe" in text
