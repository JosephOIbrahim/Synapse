"""Hardening cards H-1 and H-4 (2026-10-04, SideFX cross-reference review).

H-1  execute_python returns a falsy measured result instead of "executed".
H-4  SYNAPSE_AUTO_MEMORY=0 stops the three automatic housekeeping rows.

Runs without Houdini. The tracker is built with object.__new__ and a MagicMock
store: SynapseBridge.__init__ would open the real memory backend, and a test
must never do that.
"""

import threading
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# H-1: a measured zero is an answer
# ---------------------------------------------------------------------------

class TestExecutePythonFalsyResult:

    @pytest.fixture(autouse=True)
    def handler(self):
        import synapse.server.handlers as handlers_mod
        had_hou = hasattr(handlers_mod, "hou")
        saved_hou = getattr(handlers_mod, "hou", None)
        saved_avail = handlers_mod.HOU_AVAILABLE
        hou_ref = saved_hou if saved_hou is not None else MagicMock()
        if not hasattr(hou_ref, "undos") or not hasattr(hou_ref.undos, "group"):
            hou_ref.undos = MagicMock()
        handlers_mod.hou = hou_ref
        handlers_mod.HOU_AVAILABLE = True
        self.h = handlers_mod.SynapseHandler()
        yield
        handlers_mod.HOU_AVAILABLE = saved_avail
        if had_hou:
            handlers_mod.hou = saved_hou
        elif hasattr(handlers_mod, "hou"):
            del handlers_mod.hou

    def _run(self, code):
        return self.h._handle_execute_python({"content": code, "atomic": False})

    @pytest.mark.parametrize("code,expected", [
        ("result = 0", "0"),
        ("result = 0.0", "0.0"),
        ("result = False", "False"),
        ("result = []", "[]"),
        ("result = ''", ""),
        ("result = None", "None"),
        ("result = len([])", "0"),
    ])
    def test_falsy_result_is_returned(self, code, expected):
        out = self._run(code)
        assert out["executed"] is True
        assert out["result"] == expected

    def test_truthy_result_unchanged(self):
        assert self._run("result = 42")["result"] == "42"

    def test_no_result_variable_still_says_executed(self):
        out = self._run("x = 1 + 2")
        assert out == {"executed": True, "result": "executed"}

    def test_api_adapter_uses_the_same_rule(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "python" / "synapse"
               / "server" / "api_adapter.py").read_text(encoding="utf-8")
        assert 'str(result) if "result" in exec_locals else "executed"' in src
        assert 'str(result) if result else "executed"' not in src


# ---------------------------------------------------------------------------
# H-4: the housekeeping rows have a switch, and it is off by default
# ---------------------------------------------------------------------------

def _bridge():
    from synapse.session.tracker import SynapseBridge
    b = object.__new__(SynapseBridge)
    b._sessions = {}
    b._synapse = MagicMock()
    b._markdown_sync = None
    b._lock = threading.Lock()
    b.log_node_creation = True
    b.log_errors = True
    b._context_cache = {"stale": True}
    b._context_cache_time = 0.0
    b._context_cache_ttl = 30.0
    return b


def _one_session(b):
    sid = b.start_session("pytest")
    b.log_action("Executed: create_node", session_id=sid, node_paths=["/stage/a"])
    stats = b.get_session(sid)
    counted = (stats.commands_executed, list(stats.nodes_modified))
    cache_after_action = b._context_cache
    summary = b.end_session(sid)
    return counted, cache_after_action, summary


def test_unset_writes_all_three_rows(monkeypatch):
    monkeypatch.delenv("SYNAPSE_AUTO_MEMORY", raising=False)
    b = _bridge()
    counted, cache, summary = _one_session(b)
    contents = [c.kwargs["content"] for c in b._synapse.add.call_args_list]
    assert contents[0] == "AI session started (client: pytest)"
    assert contents[1] == "Executed: create_node"
    assert len(contents) == 3 and contents[2] == summary
    assert counted == (1, ["/stage/a"]) and cache is None


@pytest.mark.parametrize("value", ["0", "off", "false", "no", " OFF "])
def test_switch_off_writes_nothing_but_keeps_bookkeeping(monkeypatch, value):
    monkeypatch.setenv("SYNAPSE_AUTO_MEMORY", value)
    b = _bridge()
    counted, cache, summary = _one_session(b)
    b._synapse.add.assert_not_called()
    # Session stats, cache invalidation and the returned summary still work.
    assert counted == (1, ["/stage/a"])
    assert cache is None
    assert summary


@pytest.mark.parametrize("value", ["1", "on", "", "anything"])
def test_any_other_value_is_todays_behaviour(monkeypatch, value):
    monkeypatch.setenv("SYNAPSE_AUTO_MEMORY", value)
    b = _bridge()
    _one_session(b)
    assert b._synapse.add.call_count == 3


def test_explicit_error_rows_are_not_switched_off(monkeypatch):
    monkeypatch.setenv("SYNAPSE_AUTO_MEMORY", "0")
    b = _bridge()
    b.log_error("boom")
    assert b._synapse.add.call_count == 1
