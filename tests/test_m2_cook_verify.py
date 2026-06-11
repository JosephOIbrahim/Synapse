"""M2-B (pipeline citizen, report §3 #8 residue + §5 item 4): cook-and-verify.

manage_collection and configure_light_linking were the last two USD mutators
that authored via a pythonscript LOP and returned without cooking -- genuine
USD errors (typo'd collection, missing prim) surfaced nowhere, and the
embedded ``if prim:`` guard silently skips. Now every mutating branch cooks
(sibling set_usd_attribute idiom) and reads the cooked stage back via
``_verify_collection_cooked``; results carry ``verified: True`` /
``cook_error`` / ``verify_error`` honestly. Both commands were retired from
SHAPE_FICTION_DEBT in tests/test_m1_truth_contract.py in this same change --
that test enforces the coupling.

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
for _attr in ("undos", "node", "text", "ui"):
    if not hasattr(_h, _attr):
        setattr(_h, _attr, MagicMock())
if not hasattr(_h, "frame"):
    _h.frame = MagicMock(return_value=1)
if "hdefereval" not in sys.modules:
    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hd

from synapse.server.handlers import SynapseHandler  # noqa: E402
from synapse.server import handlers_usd as husd  # noqa: E402


class _FakeOperationFailed(Exception):
    pass


class _UndoGroup:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture()
def wired(monkeypatch):
    """Fake hou on the USD handler module + inline run_on_main.

    Returns (handler, py_lop, events).
    """
    events = []
    fake_hou = SimpleNamespace(
        undos=SimpleNamespace(group=lambda label: _UndoGroup()),
        OperationFailed=_FakeOperationFailed,
    )
    monkeypatch.setattr(husd, "hou", fake_hou)
    monkeypatch.setattr(husd, "HOU_AVAILABLE", True)

    # Patch the LIVE main_thread entry (test_main_thread.py swaps in a private
    # instance at collection; the handlers resolve it at call time).
    mt_live = importlib.import_module("synapse.server.main_thread")
    monkeypatch.setattr(mt_live, "run_on_main", lambda fn, timeout=None: fn())

    py_lop = MagicMock(name="py_lop")
    py_lop.path.return_value = "/stage/coll_test"
    py_lop.cook.side_effect = lambda **kw: events.append(("cook", kw))
    parent = MagicMock()
    parent.createNode.return_value = py_lop
    lop = MagicMock()
    lop.parent.return_value = parent

    monkeypatch.setattr(
        SynapseHandler, "_resolve_lop_node", lambda self, p: lop, raising=False
    )
    return SynapseHandler(), py_lop, events


@pytest.fixture()
def verify_spy(monkeypatch):
    """Record _verify_collection_cooked calls; spy.result controls the verdict."""
    calls = []

    def spy(py_lop, prim_path, collection_name, rel="includes",
            expect_present=None, expect_absent=None):
        calls.append({
            "prim_path": prim_path,
            "collection_name": collection_name,
            "rel": rel,
            "expect_present": expect_present,
            "expect_absent": expect_absent,
        })
        return spy.result

    spy.result = None
    monkeypatch.setattr(
        SynapseHandler, "_verify_collection_cooked", staticmethod(spy)
    )
    return calls, spy


# ---------------------------------------------------------------------------
# manage_collection
# ---------------------------------------------------------------------------


def test_create_cooks_and_verifies(wired, verify_spy):
    handler, py_lop, events = wired
    calls, _ = verify_spy
    result = handler._handle_manage_collection({
        "prim_path": "/World",
        "action": "create",
        "collection_name": "key_lights",
        "paths": ["/World/lights/key"],
    })
    assert ("cook", {"force": True}) in events
    assert result["verified"] is True
    assert calls == [{
        "prim_path": "/World",
        "collection_name": "key_lights",
        "rel": "includes",
        "expect_present": ["/World/lights/key"],
        "expect_absent": None,
    }]


def test_create_cook_error_is_honest(wired, verify_spy):
    handler, py_lop, _ = wired
    calls, _ = verify_spy
    py_lop.cook.side_effect = _FakeOperationFailed("bad prim")
    result = handler._handle_manage_collection({
        "prim_path": "/World",
        "action": "create",
        "collection_name": "key_lights",
        "paths": ["/World/lights/key"],
    })
    assert "hit a snag when cooking" in result["cook_error"]
    assert "verified" not in result
    assert calls == []  # readback never runs after a failed cook


def test_create_readback_failure_surfaces(wired, verify_spy):
    handler, _, _ = wired
    _, spy = verify_spy
    spy.result = "collection 'key_lights' wasn't found on /World"
    result = handler._handle_manage_collection({
        "prim_path": "/World",
        "action": "create",
        "collection_name": "key_lights",
        "paths": ["/World/lights/key"],
    })
    assert "readback failed" in result["verify_error"]
    assert "verified" not in result


def test_add_and_remove_expectations(wired, verify_spy):
    handler, _, _ = wired
    calls, _ = verify_spy
    handler._handle_manage_collection({
        "prim_path": "/World", "action": "add",
        "collection_name": "key_lights", "paths": ["/World/lights/rim"],
    })
    handler._handle_manage_collection({
        "prim_path": "/World", "action": "remove",
        "collection_name": "key_lights", "paths": ["/World/lights/fill"],
    })
    assert calls[0]["expect_present"] == ["/World/lights/rim"]
    assert calls[0]["expect_absent"] is None
    assert calls[1]["expect_present"] is None
    assert calls[1]["expect_absent"] == ["/World/lights/fill"]


# ---------------------------------------------------------------------------
# configure_light_linking
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action,coll,rel,expect", [
    ("include", "lightLink", "includes", ["/World/geo/hero"]),
    ("exclude", "lightLink", "excludes", ["/World/geo/hero"]),
    ("shadow_include", "shadowLink", "includes", ["/World/geo/hero"]),
    ("shadow_exclude", "shadowLink", "excludes", ["/World/geo/hero"]),
])
def test_lightlink_cooks_and_verifies(wired, verify_spy, action, coll, rel, expect):
    handler, _, events = wired
    calls, _ = verify_spy
    result = handler._handle_configure_light_linking({
        "light_path": "/World/lights/key",
        "action": action,
        "geo_paths": ["/World/geo/hero"],
    })
    assert ("cook", {"force": True}) in events
    assert result["verified"] is True
    assert calls == [{
        "prim_path": "/World/lights/key",
        "collection_name": coll,
        "rel": rel,
        "expect_present": expect,
        "expect_absent": None,
    }]


def test_lightlink_reset_verifies_root_target(wired, verify_spy):
    handler, _, _ = wired
    calls, _ = verify_spy
    result = handler._handle_configure_light_linking({
        "light_path": "/World/lights/key",
        "action": "reset",
    })
    assert result["verified"] is True
    assert calls[0]["collection_name"] == "lightLink"
    assert calls[0]["expect_present"] == ["/"]


def test_lightlink_cook_error_is_honest(wired, verify_spy):
    handler, py_lop, _ = wired
    py_lop.cook.side_effect = _FakeOperationFailed("no light")
    result = handler._handle_configure_light_linking({
        "light_path": "/World/lights/key",
        "action": "include",
        "geo_paths": ["/World/geo/hero"],
    })
    assert "hit a snag when cooking" in result["cook_error"]
    assert "verified" not in result


# ---------------------------------------------------------------------------
# _verify_collection_cooked readback unit tests (fake pxr)
# ---------------------------------------------------------------------------


def _readback(monkeypatch, *, stage, get=None, **kwargs):
    """Run the helper against a fake pxr where CollectionAPI.Get == `get`."""
    fake_pxr = ModuleType("pxr")
    fake_pxr.Usd = SimpleNamespace(
        CollectionAPI=SimpleNamespace(Get=get or (lambda prim, name: None))
    )
    monkeypatch.setitem(sys.modules, "pxr", fake_pxr)
    py_lop = SimpleNamespace(stage=lambda: stage)
    return SynapseHandler._verify_collection_cooked(
        py_lop, "/World", "key_lights", **kwargs
    )


def _valid_prim():
    return SimpleNamespace(IsValid=lambda: True)


def _stage_with(prim):
    return SimpleNamespace(GetPrimAtPath=lambda p: prim)


def test_readback_no_stage(monkeypatch):
    err = _readback(monkeypatch, stage=None)
    assert "exposes no stage" in err


def test_readback_missing_prim(monkeypatch):
    prim = SimpleNamespace(IsValid=lambda: False)
    err = _readback(monkeypatch, stage=_stage_with(prim))
    assert "no prim exists" in err and "silently skipped" in err


def test_readback_missing_collection(monkeypatch):
    err = _readback(monkeypatch, stage=_stage_with(_valid_prim()))
    assert "wasn't found" in err


def test_readback_missing_target(monkeypatch):
    rel = SimpleNamespace(GetTargets=lambda: ["/World/a"])
    coll = SimpleNamespace(GetIncludesRel=lambda: rel)
    err = _readback(
        monkeypatch, stage=_stage_with(_valid_prim()),
        get=lambda prim, name: coll, expect_present=["/World/a", "/World/b"],
    )
    assert "targets missing" in err and "/World/b" in err


def test_readback_lingering_target(monkeypatch):
    rel = SimpleNamespace(GetTargets=lambda: ["/World/a"])
    coll = SimpleNamespace(GetIncludesRel=lambda: rel)
    err = _readback(
        monkeypatch, stage=_stage_with(_valid_prim()),
        get=lambda prim, name: coll, expect_absent=["/World/a"],
    )
    assert "still present" in err


def test_readback_verified(monkeypatch):
    rel = SimpleNamespace(GetTargets=lambda: ["/World/a", "/World/b"])
    coll = SimpleNamespace(GetIncludesRel=lambda: rel)
    err = _readback(
        monkeypatch, stage=_stage_with(_valid_prim()),
        get=lambda prim, name: coll, expect_present=["/World/a"],
    )
    assert err is None


def test_readback_excludes_rel(monkeypatch):
    rel = SimpleNamespace(GetTargets=lambda: ["/World/bg"])
    coll = SimpleNamespace(
        GetIncludesRel=lambda: (_ for _ in ()).throw(AssertionError("wrong rel")),
        GetExcludesRel=lambda: rel,
    )
    err = _readback(
        monkeypatch, stage=_stage_with(_valid_prim()),
        get=lambda prim, name: coll, rel="excludes", expect_present=["/World/bg"],
    )
    assert err is None
