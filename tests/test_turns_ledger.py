"""Scene-model Mile 0 — turns-per-send ledger (the U2 instrument).

Pins:
  1. Ledger units: append shape, FIFO rotation + cap reconcile, never-fail
     with a ONE-TIME warning (mirrors test_read_ledger — same idioms).
  2. Worker tap: ClaudeWorker._conversation_loop persists exactly one
     record on normal completion (hit_25_cap=False) and one on the
     25-iteration cap (hit_25_cap=True); a ledger failure never changes
     worker behavior.
  3. Report units: turns-per-send distribution -> exact expected numbers.

Qt handling reuses the test_worker_tool_policy fixture pattern verbatim:
stub PySide6 ONLY for the duration of the test and restore every touched
sys.modules key (no stub leaks into sibling panel tests). NO sys.modules
hou fakes are planted (the fake-residency trap) — turns_ledger and
claude_worker are both zero-hou modules.
"""

import importlib
import importlib.util
import json
import logging
import os
import sys
import types
from unittest.mock import MagicMock

import pytest

from synapse.panel import turns_ledger


@pytest.fixture(autouse=True)
def _ledger_env(tmp_path, monkeypatch):
    """Isolate every test: tmp logs dir, default env, fresh module state."""
    monkeypatch.setenv("SYNAPSE_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.delenv("SYNAPSE_TURNS_LEDGER_MAX_RECORDS", raising=False)
    turns_ledger.reset_ledger_state()
    yield
    turns_ledger.reset_ledger_state()


def _rows():
    path = turns_ledger.ledger_path()
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# ── 1. ledger units ──────────────────────────────────────────────

class TestAppendTurnRecord:
    def test_append_writes_exact_shape(self):
        assert turns_ledger.append_turn_record(
            "anthropic", turns=3, tool_calls=7, hit_cap=False) is True
        rows = _rows()
        assert len(rows) == 1
        row = rows[0]
        assert set(row) == {"ts", "provider_id", "turns", "tool_calls",
                            "hit_25_cap"}
        assert row["provider_id"] == "anthropic"
        assert row["turns"] == 3
        assert row["tool_calls"] == 7
        assert row["hit_25_cap"] is False

    def test_cap_hit_recorded_true(self):
        turns_ledger.append_turn_record("gemini", 25, 40, hit_cap=True)
        assert _rows()[0]["hit_25_cap"] is True

    def test_fifo_rotation_keeps_newest(self, monkeypatch):
        monkeypatch.setenv("SYNAPSE_TURNS_LEDGER_MAX_RECORDS", "2")
        for i in range(4):
            turns_ledger.append_turn_record(f"p{i}", i, 0, False)
        rows = _rows()
        assert [r["provider_id"] for r in rows] == ["p2", "p3"]

    def test_cap_reconciles_across_restart(self, monkeypatch):
        monkeypatch.setenv("SYNAPSE_TURNS_LEDGER_MAX_RECORDS", "2")
        turns_ledger.append_turn_record("p0", 1, 0, False)
        turns_ledger.append_turn_record("p1", 1, 0, False)
        turns_ledger.reset_ledger_state()  # simulated restart
        turns_ledger.append_turn_record("p2", 1, 0, False)
        rows = _rows()
        assert [r["provider_id"] for r in rows] == ["p1", "p2"]

    def test_cap_zero_disables_rotation(self, monkeypatch):
        monkeypatch.setenv("SYNAPSE_TURNS_LEDGER_MAX_RECORDS", "0")
        for i in range(5):
            turns_ledger.append_turn_record("p", 1, 0, False)
        assert len(_rows()) == 5

    def test_default_cap(self):
        assert turns_ledger.resolve_max_records() == 5000

    def test_never_fails_on_unwritable_dir(self, tmp_path, monkeypatch, caplog):
        blocker = tmp_path / "blocker"
        blocker.write_text("x")
        monkeypatch.setenv("SYNAPSE_LOG_DIR", str(blocker / "sub"))
        with caplog.at_level(logging.WARNING,
                             logger="synapse.panel.turns_ledger"):
            assert turns_ledger.append_turn_record("p", 1, 0, False) is False
            assert turns_ledger.append_turn_record("p", 1, 0, False) is False
        warnings = [r for r in caplog.records
                    if r.name == "synapse.panel.turns_ledger"
                    and r.levelno >= logging.WARNING]
        assert len(warnings) == 1, "warning must fire exactly ONCE"


# ── 2. worker tap ────────────────────────────────────────────────
# Fixture pattern copied from test_worker_tool_policy (the proven headless
# ClaudeWorker import): stub PySide6 only if no GENUINE QThread class is
# importable, restore every touched sys.modules key afterward.

@pytest.fixture
def claude_worker_module():
    touched = [
        "PySide6", "PySide6.QtCore",
        "PySide2", "PySide2.QtCore",
        "synapse.panel.claude_worker",
        "synapse.panel.tool_executor",
    ]
    saved = {k: sys.modules.get(k) for k in touched}

    def _is_genuine_qt(modname):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            return False
        return isinstance(getattr(mod, "QThread", None), type)

    real_qt = (_is_genuine_qt("PySide6.QtCore")
               or _is_genuine_qt("PySide2.QtCore"))

    if not real_qt:
        class _StubBase:
            def __init__(self, *a, **kw):
                pass

        class _QtCoreStub(types.ModuleType):
            QThread = _StubBase
            QObject = _StubBase

            @staticmethod
            def Signal(*a, **kw):
                return MagicMock()

            @staticmethod
            def Slot(*a, **kw):
                return lambda fn: fn

            def __getattr__(self, name):  # pragma: no cover - defensive
                return MagicMock()

        qtcore = _QtCoreStub("PySide6.QtCore")
        pyside = types.ModuleType("PySide6")
        pyside.QtCore = qtcore
        sys.modules["PySide6"] = pyside
        sys.modules["PySide6.QtCore"] = qtcore
        sys.modules.pop("synapse.panel.tool_executor", None)
    sys.modules.pop("synapse.panel.claude_worker", None)
    import synapse.panel.claude_worker as cw

    try:
        yield cw
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


class _EndTurnProvider:
    """Completes immediately: one streamed turn, zero tool calls."""
    id = "fakeprov"

    def stream(self, **kwargs):
        return "end_turn", []


class _AlwaysToolUseProvider:
    """Never ends: drives the loop into the 25-iteration cap (with zero
    tool_use blocks, so no tool is ever executed)."""
    id = "capprov"

    def stream(self, **kwargs):
        return "tool_use", []


def _make_worker(cw, provider):
    worker = cw.ClaudeWorker(messages=[], provider=provider, tools=[])
    # Neutralize signals so .emit() is a no-op under stub or real Qt.
    worker.token_received = MagicMock()
    worker.tool_status = MagicMock()
    return worker


class TestWorkerTap:
    def test_normal_completion_records_one_row(self, claude_worker_module):
        cw = claude_worker_module
        worker = _make_worker(cw, _EndTurnProvider())
        worker._conversation_loop("fake-key")
        rows = _rows()
        assert len(rows) == 1
        row = rows[0]
        assert row["provider_id"] == "fakeprov"
        assert row["turns"] == 1
        assert row["tool_calls"] == 0
        assert row["hit_25_cap"] is False

    def test_cap_hit_records_true(self, claude_worker_module):
        cw = claude_worker_module
        worker = _make_worker(cw, _AlwaysToolUseProvider())
        worker._conversation_loop("fake-key")
        rows = _rows()
        assert len(rows) == 1
        row = rows[0]
        assert row["provider_id"] == "capprov"
        assert row["turns"] == cw._MAX_TOOL_ITERATIONS
        assert row["hit_25_cap"] is True

    def test_ledger_failure_never_changes_worker_behavior(
            self, claude_worker_module, monkeypatch):
        cw = claude_worker_module

        def _boom(**kwargs):
            raise RuntimeError("ledger down")

        monkeypatch.setattr(turns_ledger, "append_turn_record", _boom)
        worker = _make_worker(cw, _EndTurnProvider())
        worker._conversation_loop("fake-key")  # must not raise
        assert _rows() == []


# ── 3. report units (turns distribution) ─────────────────────────

def _load_report_module():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "scripts", "scene_model_report.py")
    spec = importlib.util.spec_from_file_location("scene_model_report", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _turn_rec(turns, hit_cap=False, provider="anthropic"):
    return {"ts": "2026-07-18T00:00:00+00:00", "provider_id": provider,
            "turns": turns, "tool_calls": 0, "hit_25_cap": hit_cap}


class TestTurnsReport:
    def test_distribution_exact(self):
        mod = _load_report_module()
        stats = mod.compute_turn_stats([
            _turn_rec(1), _turn_rec(2), _turn_rec(3),
            _turn_rec(10, hit_cap=True),
        ])
        assert stats["sends"] == 4
        assert stats["turns_mean"] == pytest.approx(4.0)
        assert stats["turns_median"] == pytest.approx(2.5)
        assert stats["turns_p25"] == pytest.approx(1.75)
        assert stats["turns_p75"] == pytest.approx(4.75)
        assert stats["cap_hits"] == 1
        assert stats["cap_hit_rate"] == pytest.approx(0.25)

    def test_single_record(self):
        mod = _load_report_module()
        stats = mod.compute_turn_stats([_turn_rec(7)])
        assert stats["turns_median"] == 7.0
        assert stats["turns_p25"] == 7.0
        assert stats["turns_p75"] == 7.0
        assert stats["cap_hit_rate"] == 0.0

    def test_empty_ledger(self):
        mod = _load_report_module()
        stats = mod.compute_turn_stats([])
        assert stats["sends"] == 0
        assert stats["turns_mean"] is None
        assert stats["cap_hit_rate"] is None

    def test_bad_records_skipped(self):
        mod = _load_report_module()
        stats = mod.compute_turn_stats([
            _turn_rec(2),
            {"ts": "x", "provider_id": "p", "turns": "not-a-number"},
            {"ts": "x", "provider_id": "p", "turns": True},  # bool is not a count
        ])
        assert stats["sends"] == 1
        assert stats["skipped_records"] == 2
