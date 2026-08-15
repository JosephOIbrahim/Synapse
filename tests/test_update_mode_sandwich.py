"""F1 update-mode sandwich — standalone pins (mock hou, no Houdini).

Pins the shipped guards so the live probe (harness/notes/
probe_update_mode_sandwich.py, run-by-Joe on 22.0.400) verifies behavior,
not plumbing:

- flag OFF (dev default) -> pure passthrough: hou never touched.
- headless (hou.isUIAvailable() False) or hou entirely absent -> passthrough.
- try/finally restore is non-negotiable: payload raising still restores the
  PRE-SANDWICH mode and still fires hou.ui.triggerUpdate().
- nested-payload safety: a payload that calls setUpdateMode itself still
  lands back on the pre-sandwich mode (snapshot restore, never a constant).
- active sandwiches record hold duration + caller estimate hints into the
  histogram; passthroughs count skips, never fake a hold sample.
- restore failure never masks the payload's own exception — it is logged
  and counted, and triggerUpdate is still attempted.
- a failed Manual entry degrades to unsandwiched (payload still runs).
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_base = Path(__file__).resolve().parents[1] / "python" / "synapse"


def _load(hou_mock=None):
    """Load update_mode.py fresh with (or without) a mocked hou."""
    saved = sys.modules.get("hou", None)
    present = "hou" in sys.modules
    # Sanctioned absence pattern (test_hou_reimport_guard): None stand-in,
    # never del/pop — eviction re-registers the SWIG type map half-built.
    sys.modules["hou"] = hou_mock if hou_mock is not None else None
    try:
        spec = importlib.util.spec_from_file_location(
            "synapse.server.update_mode", _base / "server" / "update_mode.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.modules["hou"] = saved if present else None
    return mod


def _fake_hou(ui_available=True, initial_mode="Auto"):
    hou = types.SimpleNamespace()
    hou.updateMode = types.SimpleNamespace(
        Auto="Auto", Manual="Manual", OnMouseUp="OnMouseUp")
    state = {"mode": initial_mode, "triggered": 0, "set_calls": []}

    hou.updateModeSetting = lambda: state["mode"]

    def _set(m):
        if isinstance(m, Exception):
            raise m
        state["mode"] = m
        state["set_calls"].append(m)

    hou.setUpdateMode = _set
    hou.isUIAvailable = lambda: ui_available
    hou.ui = types.SimpleNamespace(
        triggerUpdate=lambda: state.__setitem__("triggered",
                                                state["triggered"] + 1))
    hou._state = state
    return hou


@pytest.fixture(autouse=True)
def _flag_off(monkeypatch):
    monkeypatch.delenv("SYNAPSE_COOK_SANDWICH", raising=False)


def test_flag_off_is_passthrough(monkeypatch):
    hou = _fake_hou()
    mod = _load(hou)
    monkeypatch.delenv("SYNAPSE_COOK_SANDWICH", raising=False)
    ran = []
    with mod.cook_sandwich(label="t") as probe:
        probe.note_estimate(7)   # ignored: probe inactive
        ran.append(True)
    assert ran == [True]
    assert hou._state["mode"] == "Auto"           # never entered Manual
    assert hou._state["set_calls"] == []          # hou never touched
    assert hou._state["triggered"] == 0
    s = mod.sandwich_stats()
    assert s["count"] == 0
    assert s["skipped_flag_off"] == 1
    assert s["enabled"] is False


def test_flag_on_activates(monkeypatch):
    hou = _fake_hou()
    mod = _load(hou)
    monkeypatch.setenv("SYNAPSE_COOK_SANDWICH", "1")
    with mod.cook_sandwich(label="t") as probe:
        probe.note_estimate(5)
        assert hou._state["mode"] == "Manual"
    assert hou._state["mode"] == "Auto"           # restored
    assert hou._state["set_calls"] == ["Manual", "Auto"]
    assert hou._state["triggered"] == 1
    s = mod.sandwich_stats()
    assert s["count"] == 1
    assert s["est_collapsed_cooks"] == 5
    assert s["est_labeled"] == 1
    assert s["max_ms"] >= 0.0


def test_headless_is_passthrough(monkeypatch):
    hou = _fake_hou(ui_available=False)
    mod = _load(hou)
    monkeypatch.setenv("SYNAPSE_COOK_SANDWICH", "1")
    with mod.cook_sandwich(label="t"):
        assert hou._state["mode"] == "Auto"       # no Manual under headless
    assert hou._state["set_calls"] == []
    assert hou._state["triggered"] == 0
    s = mod.sandwich_stats()
    assert s["count"] == 0
    assert s["skipped_headless"] == 1


def test_hou_absent_is_passthrough(monkeypatch):
    mod = _load(hou_mock=None)
    assert mod.HOU_AVAILABLE is False
    monkeypatch.setenv("SYNAPSE_COOK_SANDWICH", "1")
    ran = []
    with mod.cook_sandwich(label="t"):
        ran.append(True)
    assert ran == [True]
    assert mod.sandwich_stats()["skipped_headless"] == 1


def test_restore_on_exception(monkeypatch):
    hou = _fake_hou()
    mod = _load(hou)
    monkeypatch.setenv("SYNAPSE_COOK_SANDWICH", "1")
    with pytest.raises(RuntimeError, match="boom"):
        with mod.cook_sandwich(label="t"):
            raise RuntimeError("boom")
    assert hou._state["mode"] == "Auto"           # restored despite raise
    assert hou._state["triggered"] == 1
    assert mod.sandwich_stats()["count"] == 1     # hold still recorded


def test_nested_payload_setUpdateMode_restores_presandwich(monkeypatch):
    hou = _fake_hou(initial_mode="OnMouseUp")
    mod = _load(hou)
    monkeypatch.setenv("SYNAPSE_COOK_SANDWICH", "1")
    with mod.cook_sandwich(label="t"):
        assert hou._state["mode"] == "Manual"
        # The payload calls setUpdateMode itself — the realistic collision.
        hou.setUpdateMode(hou.updateMode.Auto)
        assert hou._state["mode"] == "Auto"
    # finally restores the SNAPSHOT (OnMouseUp), not Manual's default.
    assert hou._state["mode"] == "OnMouseUp"
    assert hou._state["set_calls"] == ["Manual", "Auto", "OnMouseUp"]


def test_restore_failure_never_masks_payload(monkeypatch):
    hou = _fake_hou()
    calls = iter([None, RuntimeError("restore exploded")])  # Manual ok, restore raises

    def _set(m):
        nxt = next(calls, None)
        if isinstance(nxt, Exception):
            raise nxt
        hou._state["mode"] = m
    hou.setUpdateMode = _set
    mod = _load(hou)
    monkeypatch.setenv("SYNAPSE_COOK_SANDWICH", "1")
    with pytest.raises(ValueError, match="payload's own"):
        with mod.cook_sandwich(label="t"):
            raise ValueError("payload's own")
    # Restore failure counted, triggerUpdate still attempted, payload
    # exception propagated unmasked.
    assert mod.sandwich_stats()["restore_failures"] == 1
    assert hou._state["triggered"] == 1


def test_manual_entry_failure_degrades_unsandwiched(monkeypatch):
    hou = _fake_hou()
    hou.setUpdateMode = lambda m: (_ for _ in ()).throw(
        RuntimeError("no update modes today"))
    mod = _load(hou)
    monkeypatch.setenv("SYNAPSE_COOK_SANDWICH", "1")
    ran = []
    with mod.cook_sandwich(label="t"):
        ran.append(True)
    assert ran == [True]                          # payload still ran
    assert hou._state["mode"] == "Auto"
    assert hou._state["triggered"] == 0           # never entered Manual
    s = mod.sandwich_stats()
    assert s["count"] == 0


def test_stats_snapshot_is_a_copy(monkeypatch):
    hou = _fake_hou()
    mod = _load(hou)
    monkeypatch.setenv("SYNAPSE_COOK_SANDWICH", "1")
    mod.reset_sandwich_stats()
    with mod.cook_sandwich(label="t") as probe:
        probe.note_estimate(2)
    snap = mod.sandwich_stats()
    snap["count"] = 999
    snap["buckets"][1] = 999
    fresh = mod.sandwich_stats()
    assert fresh["count"] == 1
    assert fresh["buckets"][1] == 1 or fresh["buckets"][1] == 0


def test_callers_do_not_wrap_batch_commands():
    """Scope invariant (crucible): sandwich scope <= op scope. The sandwich
    is pinned at execute_python / execute_vex / solaris_build_graph — never
    batch_commands, whose per-op hash bracket a batch-wide sandwich would
    span."""
    src = (_base / "server" / "handlers.py").read_text(encoding="utf-8")
    batch_idx = src.find("_handle_batch_commands")
    assert batch_idx != -1, "sanity: batch handler missing entirely"
    window = src[batch_idx: batch_idx + 4000]
    assert "cook_sandwich" not in window
