"""M2-A (dangling-LOP-display): every USD/material mutator's new node used to
land on a dead parallel branch -- wired FROM the resolved LOP, nothing wired
from it, display flag untouched (zero setDisplayFlag file-wide), so the
viewport, Karma (handlers_render.py resolves loppath by isDisplayFlagSet),
and USD export never saw the edit; reference_usd never even called setInput
(island). Policy now: a fresh LOP becomes the display tip ONLY when it
extends the current display chain (the pre-existing node it was wired from
holds the flag, or the network has no display node). Forks NEVER auto-move
display (that would hide the artist's downstream chain) -- they return
display:'not_set' + display_node + needs_rewire instead. Payload opt-out:
set_display (default True). Truth contract: display:'set' only after an
isDisplayFlagSet() readback.

Headless. Handler-module globals are patched directly (sys.modules residency
is order-fragile -- docs/HARDENING_RUN_2026-06-10.md Mile 3 forensics).
"""

import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

if "hou" not in sys.modules:
    sys.modules["hou"] = ModuleType("hou")
# The resident fake's shape leaks into every later-imported handler module
# (first planter wins) -- enrich it with what sibling handler tests rely on,
# never plant a skeleton (test_autonomy_live_contract.py pattern).
_h = sys.modules["hou"]
for _attr in ("undos", "node", "ui"):
    if not hasattr(_h, _attr):
        setattr(_h, _attr, MagicMock())
if not hasattr(_h, "text"):
    # Sibling convention: expandString returns a real str (later files'
    # handlers run Path() over it when this file is the first planter).
    _h.text = MagicMock()
    _h.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
if not hasattr(_h, "frame"):
    _h.frame = MagicMock(return_value=1)
if "hdefereval" not in sys.modules:
    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hd

from synapse.server.handlers import SynapseHandler  # noqa: E402
from synapse.server import handlers_usd as husd  # noqa: E402
from synapse.server import handlers_material as hmat  # noqa: E402
from synapse.server.handler_helpers import _wire_display  # noqa: E402


class _FakeOperationFailed(Exception):
    pass


class _UndoGroup:
    def __init__(self, events=None):
        self._events = events

    def __enter__(self):
        if self._events is not None:
            self._events.append("undo_enter")
        return self

    def __exit__(self, *a):
        if self._events is not None:
            self._events.append("undo_exit")
        return False


# ---------------------------------------------------------------------------
# (A) _wire_display unit tests -- pure, no hou
# ---------------------------------------------------------------------------


class _FakeLop:
    def __init__(self, path, display=False, parent=None):
        self._path = path
        self._display = display
        self._parent = parent
        self.set_calls = []

    def path(self):
        return self._path

    def parent(self):
        return self._parent

    def isDisplayFlagSet(self):
        return self._display

    def setDisplayFlag(self, val):
        self.set_calls.append(val)
        self._display = bool(val)


class _FakeNet:
    def __init__(self, display_node=None):
        self._display_node = display_node

    def displayNode(self):
        return self._display_node


def test_extends_tip_moves_display():
    net = _FakeNet()
    upstream = _FakeLop("/stage/upstream", display=True, parent=net)
    net._display_node = upstream
    tip = _FakeLop("/stage/new", parent=net)
    keys = _wire_display(tip, upstream, True)
    assert tip.set_calls == [True]
    assert keys == {"display": "set", "display_node": "/stage/new"}


def test_fork_never_moves_display():
    net = _FakeNet()
    holder = _FakeLop("/stage/artist_tip", display=True, parent=net)
    net._display_node = holder
    mid_chain = _FakeLop("/stage/mid", display=False, parent=net)
    tip = _FakeLop("/stage/new", parent=net)
    keys = _wire_display(tip, mid_chain, True)
    assert tip.set_calls == []
    assert keys["display"] == "not_set"
    assert keys["display_node"] == "/stage/artist_tip"
    # needs_rewire mentions both the holder and the dangling tip.
    assert "/stage/artist_tip" in keys["needs_rewire"]
    assert "/stage/new" in keys["needs_rewire"]


def test_opt_out_set_display_false():
    net = _FakeNet()
    upstream = _FakeLop("/stage/upstream", display=True, parent=net)
    net._display_node = upstream
    tip = _FakeLop("/stage/new", parent=net)
    keys = _wire_display(tip, upstream, False)
    assert tip.set_calls == []
    assert keys["display"] == "not_set"
    assert keys["display_node"] == "/stage/upstream"
    assert "needs_rewire" in keys


def test_empty_network_displays_new_tip():
    net = _FakeNet(display_node=None)
    tip = _FakeLop("/stage/new", parent=net)
    keys = _wire_display(tip, None, True)
    assert keys == {"display": "set", "display_node": "/stage/new"}


def test_set_display_flag_raising_is_honest():
    net = _FakeNet(display_node=None)

    class _Raising(_FakeLop):
        def setDisplayFlag(self, val):
            raise RuntimeError("viewport busy")

    tip = _Raising("/stage/new", parent=net)
    keys = _wire_display(tip, None, True)
    assert keys["display"] == "not_set"
    # No display node exists -> no holder to point the artist at.
    assert "display_node" not in keys


def test_readback_false_is_honest():
    # Truth contract: the result may not claim 'set' without observing it.
    net = _FakeNet(display_node=None)

    class _Sticky(_FakeLop):
        def setDisplayFlag(self, val):
            self.set_calls.append(val)  # call recorded, flag never lands

    tip = _Sticky("/stage/new", parent=net)
    keys = _wire_display(tip, None, True)
    assert tip.set_calls == [True]
    assert keys["display"] == "not_set"


# ---------------------------------------------------------------------------
# Fixtures -- handler integration (test_m2_cook_verify.py 'wired' pattern,
# extended with display-chain shape: stateful flags + parent.displayNode)
# ---------------------------------------------------------------------------


def _stateful_display(node):
    """Give a MagicMock node a real display flag (readback-gated truth)."""
    state = {"display": False}
    node.setDisplayFlag.side_effect = lambda v: state.__setitem__(
        "display", bool(v)
    )
    node.isDisplayFlagSet.side_effect = lambda: state["display"]
    return node


def _patch_main_thread(monkeypatch):
    # Patch the LIVE main_thread entry (test_main_thread.py swaps in a private
    # instance at collection; the handlers resolve it at call time).
    mt_live = importlib.import_module("synapse.server.main_thread")
    monkeypatch.setattr(mt_live, "run_on_main", lambda fn, timeout=None: fn())


@pytest.fixture()
def wired(monkeypatch):
    """Fake hou on the USD handler module + inline run_on_main.

    Returns (handler, py_lop, lop, parent). The resolved lop holds the
    display flag and parent.displayNode() reports it -> the new node
    extends the chain.
    """
    fake_hou = SimpleNamespace(
        undos=SimpleNamespace(group=lambda label: _UndoGroup()),
        OperationFailed=_FakeOperationFailed,
    )
    monkeypatch.setattr(husd, "hou", fake_hou)
    monkeypatch.setattr(husd, "HOU_AVAILABLE", True)
    _patch_main_thread(monkeypatch)

    parent = MagicMock(name="parent")
    py_lop = _stateful_display(MagicMock(name="py_lop"))
    py_lop.path.return_value = "/stage/new_lop"
    py_lop.parent.return_value = parent
    parent.createNode.return_value = py_lop

    lop = MagicMock(name="lop")
    lop.path.return_value = "/stage/upstream"
    lop.parent.return_value = parent
    lop.isDisplayFlagSet.return_value = True
    parent.displayNode.return_value = lop

    monkeypatch.setattr(
        SynapseHandler, "_resolve_lop_node", lambda self, p: lop, raising=False
    )
    return SynapseHandler(), py_lop, lop, parent


# ---------------------------------------------------------------------------
# (B) Handler integration -- pythonscript mutators
# ---------------------------------------------------------------------------


def test_set_usd_attribute_extends_chain(wired):
    handler, py_lop, _, _ = wired
    result = handler._handle_set_usd_attribute({
        "prim_path": "/World/sphere",
        "usd_attribute": "radius",
        "value": 2.0,
    })
    py_lop.setDisplayFlag.assert_called_once_with(True)
    assert result["display"] == "set"
    assert result["display_node"] == "/stage/new_lop"


def test_set_usd_attribute_fork_returns_needs_rewire(wired):
    handler, py_lop, lop, parent = wired
    # The resolved node is mid-chain: another node holds the display flag.
    holder = MagicMock(name="holder")
    holder.path.return_value = "/stage/artist_tip"
    parent.displayNode.return_value = holder
    lop.isDisplayFlagSet.return_value = False
    result = handler._handle_set_usd_attribute({
        "prim_path": "/World/sphere",
        "usd_attribute": "radius",
        "value": 2.0,
    })
    py_lop.setDisplayFlag.assert_not_called()
    assert result["display"] == "not_set"
    assert result["display_node"] == "/stage/artist_tip"
    assert "/stage/artist_tip" in result["needs_rewire"]
    assert "/stage/new_lop" in result["needs_rewire"]


def test_set_usd_attribute_opt_out(wired):
    handler, py_lop, _, _ = wired
    result = handler._handle_set_usd_attribute({
        "prim_path": "/World/sphere",
        "usd_attribute": "radius",
        "value": 2.0,
        "set_display": "false",  # stringified opt-out coerces via _coerce_bool
    })
    py_lop.setDisplayFlag.assert_not_called()
    assert result["display"] == "not_set"


def test_set_usd_attribute_cook_error_carries_no_display(wired):
    handler, py_lop, _, _ = wired
    py_lop.cook.side_effect = _FakeOperationFailed("bad prim")
    result = handler._handle_set_usd_attribute({
        "prim_path": "/World/sphere",
        "usd_attribute": "radius",
        "value": 2.0,
    })
    assert "cook_error" in result
    assert "display" not in result  # never display a failed op
    py_lop.setDisplayFlag.assert_not_called()


def test_manage_collection_create_verified_with_display(wired, monkeypatch):
    handler, py_lop, _, _ = wired
    monkeypatch.setattr(
        SynapseHandler, "_verify_collection_cooked",
        staticmethod(lambda *a, **k: None),
    )
    result = handler._handle_manage_collection({
        "prim_path": "/World",
        "action": "create",
        "collection_name": "key_lights",
        "paths": ["/World/lights/key"],
    })
    assert result["verified"] is True
    assert result["display"] == "set"
    assert result["display_node"] == "/stage/new_lop"


# ---------------------------------------------------------------------------
# (C) reference_usd island closure
# ---------------------------------------------------------------------------


@pytest.fixture()
def ref_wired(monkeypatch):
    """reference_usd wiring: hou.node(parent) -> /stage net with an anchor.

    Returns (handler, parent_node, anchor). Tests configure createNode.
    """
    parent_node = MagicMock(name="parent_node")
    anchor = MagicMock(name="anchor")
    anchor.path.return_value = "/stage/existing_tip"
    anchor.isDisplayFlagSet.return_value = True
    parent_node.displayNode.return_value = anchor
    parent_node.children.return_value = [anchor]

    fake_hou = SimpleNamespace(
        undos=SimpleNamespace(group=lambda label: _UndoGroup()),
        OperationFailed=_FakeOperationFailed,
        node=lambda p: parent_node,
    )
    monkeypatch.setattr(husd, "hou", fake_hou)
    monkeypatch.setattr(husd, "HOU_AVAILABLE", True)
    _patch_main_thread(monkeypatch)
    return SynapseHandler(), parent_node, anchor


def _ref_node(parent_node, path):
    n = _stateful_display(MagicMock(name=path))
    n.path.return_value = path
    n.parent.return_value = parent_node
    return n


def test_sublayer_joins_chain_and_displays(ref_wired):
    handler, parent_node, anchor = ref_wired
    sub = _ref_node(parent_node, "/stage/sublayer_import")
    parent_node.createNode.return_value = sub
    result = handler._handle_reference_usd({
        "file": "$HIP/asset.usd",
        "mode": "sublayer",
    })
    sub.setInput.assert_called_once_with(0, anchor)  # island closed
    sub.moveToGoodPosition.assert_called_once()
    assert result["display"] == "set"
    assert result["display_node"] == "/stage/sublayer_import"


def test_reference_karma_visible_tip_is_kv_lop(ref_wired):
    handler, parent_node, anchor = ref_wired
    ref = _ref_node(parent_node, "/stage/ref_import")
    kv = _ref_node(parent_node, "/stage/karma_visibility")
    parent_node.createNode.side_effect = [ref, kv]
    result = handler._handle_reference_usd({
        "file": "$HIP/asset.usd",
        "mode": "reference",
        "prim_path": "/World/asset",
    })
    ref.setInput.assert_called_once_with(0, anchor)
    assert result["display"] == "set"
    assert result["display_node"] == "/stage/karma_visibility"
    assert ref.setDisplayFlag.call_count == 0


def test_reference_kv_cook_failure_tip_falls_back_to_ref(ref_wired):
    handler, parent_node, anchor = ref_wired
    ref = _ref_node(parent_node, "/stage/ref_import")
    kv = _ref_node(parent_node, "/stage/karma_visibility")
    kv.cook.side_effect = _FakeOperationFailed("no prim")
    parent_node.createNode.side_effect = [ref, kv]
    result = handler._handle_reference_usd({
        "file": "$HIP/asset.usd",
        "mode": "reference",
        "prim_path": "/World/asset",
    })
    assert "karma_visibility_error" in result
    # Never display the errored kv node -- the tip stays on the ref.
    assert result["display"] == "set"
    assert result["display_node"] == "/stage/ref_import"
    assert kv.setDisplayFlag.call_count == 0


def test_reference_empty_network_no_setinput_still_displays(ref_wired):
    handler, parent_node, _ = ref_wired
    parent_node.displayNode.return_value = None
    parent_node.children.return_value = []
    sub = _ref_node(parent_node, "/stage/sublayer_import")
    parent_node.createNode.return_value = sub
    result = handler._handle_reference_usd({
        "file": "$HIP/asset.usd",
        "mode": "sublayer",
    })
    sub.setInput.assert_not_called()  # nothing to wire from
    assert result["display"] == "set"
    assert result["display_node"] == "/stage/sublayer_import"


# ---------------------------------------------------------------------------
# (D) handlers_material
# ---------------------------------------------------------------------------


@pytest.fixture()
def mat_wired(monkeypatch):
    """Fake hou on the material handler module; undo enter/exit recorded.

    Returns (handler, lop, parent, events).
    """
    events = []
    fake_hou = SimpleNamespace(
        undos=SimpleNamespace(group=lambda label: _UndoGroup(events)),
        OperationFailed=_FakeOperationFailed,
    )
    monkeypatch.setattr(hmat, "hou", fake_hou)
    monkeypatch.setattr(hmat, "HOU_AVAILABLE", True)
    _patch_main_thread(monkeypatch)

    parent = MagicMock(name="parent")
    lop = MagicMock(name="lop")
    lop.path.return_value = "/stage/upstream"
    lop.parent.return_value = parent
    lop.isDisplayFlagSet.return_value = True
    parent.displayNode.return_value = lop

    monkeypatch.setattr(
        SynapseHandler, "_resolve_lop_node", lambda self, p: lop, raising=False
    )
    return SynapseHandler(), lop, parent, events


def test_assign_material_display_inside_undo_group(mat_wired):
    handler, _, parent, events = mat_wired
    assign_node = MagicMock(name="assign")
    assign_node.path.return_value = "/stage/assign_gold"
    assign_node.parent.return_value = parent
    assign_node.setDisplayFlag.side_effect = (
        lambda v: events.append("display_set")
    )
    assign_node.isDisplayFlagSet.return_value = True
    parent.createNode.return_value = assign_node

    result = handler._handle_assign_material({
        "prim_pattern": "/World/hero",
        "material_path": "/materials/gold",
    })
    assert result["display"] == "set"
    assert result["display_node"] == "/stage/assign_gold"
    # Display mutation happened inside the undo group.
    assert events.index("undo_enter") < events.index("display_set")
    assert events.index("display_set") < events.index("undo_exit")


def test_textured_material_tip_is_matlib_without_geo_pattern(mat_wired):
    handler, _, parent, _ = mat_wired
    matlib = _stateful_display(MagicMock(name="matlib"))
    matlib.path.return_value = "/stage/textured_material"
    matlib.parent.return_value = parent
    parent.createNode.return_value = matlib

    result = handler._handle_create_textured_material({
        "diffuse_map": "/tex/albedo.exr",
    })
    assert result["display"] == "set"
    assert result["display_node"] == "/stage/textured_material"


def test_textured_material_tip_is_assign_node_with_geo_pattern(mat_wired):
    handler, _, parent, _ = mat_wired
    matlib = _stateful_display(MagicMock(name="matlib"))
    matlib.path.return_value = "/stage/textured_material"
    matlib.parent.return_value = parent
    assign_node = _stateful_display(MagicMock(name="assign"))
    assign_node.path.return_value = "/stage/assign_textured_material"
    assign_node.parent.return_value = parent
    parent.createNode.side_effect = [matlib, assign_node]

    result = handler._handle_create_textured_material({
        "diffuse_map": "/tex/albedo.exr",
        "geo_pattern": "/World/geo/hero",
    })
    assert result["assign_node"] == "/stage/assign_textured_material"
    assert result["display"] == "set"
    assert result["display_node"] == "/stage/assign_textured_material"
    assert matlib.setDisplayFlag.call_count == 0


def test_create_material_display_keys(mat_wired):
    handler, _, parent, _ = mat_wired
    matlib = _stateful_display(MagicMock(name="matlib"))
    matlib.path.return_value = "/stage/material"
    matlib.parent.return_value = parent
    parent.createNode.return_value = matlib

    result = handler._handle_create_material({})
    assert result["display"] == "set"
    assert result["display_node"] == "/stage/material"


# ---------------------------------------------------------------------------
# (E) Registry pin -- guards the orchestrator-reserved _tool_registry edit
# ---------------------------------------------------------------------------


def test_registry_passes_set_display_through_filter_keys():
    """The three _filter_keys-mapped USD mutators must let set_display
    through on the /mcp path; until the allowed-key tuples are extended in
    python/synapse/mcp/_tool_registry.py the opt-out is silently stripped
    for exactly these tools. This pin FAILS until that (orchestrator-
    reserved) edit lands in the same wave.
    """
    from synapse.mcp import _tool_registry as reg

    by_name = {t[0]: t for t in reg.TOOL_DEFS}
    for tool in (
        "houdini_set_usd_attribute",
        "houdini_create_usd_prim",
        "houdini_modify_usd_prim",
    ):
        builder = by_name[tool][2]
        out = builder({"node": "/stage/x", "set_display": False})
        assert out.get("set_display") is False, (
            f"{tool}: set_display stripped by _filter_keys -- extend the "
            "allowed-key tuple in _tool_registry.py"
        )
