"""Pins invariant 5 conditions (a)-(f) on the fenced product-side Jev adapter
(python/synapse/jev/adapter.py). Every test uses a fake SDK seam; nothing here touches
the network, the real ~/.synapse, or the build-time Jev tooling.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import types

import pytest

from synapse.jev import adapter
from synapse.jev import judge

FAKE_KEY = "tsk-SECRET-0123456789abcdef"
STATE = {"doc": "The count line reads 21 rows; the brief expected 22."}
QUESTIONS = {
    "mismatch": {"type": "noul", "instructions": "Is the count off?"},
    "severity": {"type": "score", "instructions": "How bad?", "criteria": "0 fine, 1 broken"},
    "route": {"type": "choice", "instructions": "Who fixes it?", "criteria": ["a", "b"]},
}


# --------------------------------------------------------------------------- fakes
class _Q:
    def __init__(self, **kw):
        self.kw = kw


class _FakeClient:
    """Stands in for TypeSafeClient. ``behaviour`` is a callable (state, questions) -> resp."""

    calls: list = []

    def __init__(self, api_key=None, timeout=None, behaviour=None):
        self.api_key = api_key
        self.timeout = timeout
        self._behaviour = behaviour

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def system_one(self, *, state, questions, model=None):
        _FakeClient.calls.append({"state": state, "qids": sorted(questions), "model": model})
        return self._behaviour(state, questions)


def _install_fake_sdk(monkeypatch, behaviour):
    _FakeClient.calls = []

    def _client(api_key=None, timeout=None):
        return _FakeClient(api_key=api_key, timeout=timeout, behaviour=behaviour)

    monkeypatch.setattr(adapter, "_load_sdk", lambda: (_client, _Q, _Q, _Q))


def _ok_answers(state, questions):
    return {"nouls": {"mismatch": {"probability": 0.9}}, "scores": {"severity": {"score": 0.7}},
            "choices": {"route": {"probabilities": {"a": 0.8, "b": 0.2}}}}


def _rows(lane):
    p = adapter.ledger_path(lane)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("SYNAPSE_JEV_LEDGER_DIR", str(tmp_path / "ledger"))
    monkeypatch.setenv("SYNAPSE_JEV", "on")
    monkeypatch.setenv("TYPESAFE_API_KEY", FAKE_KEY)
    monkeypatch.setitem(sys.modules, "hou", None)  # absence, restored by object (test_hou_reimport_guard)
    return tmp_path


# --------------------------------------------------------------------------- (b)
def test_unset_env_returns_none_without_importing_sdk(monkeypatch, tmp_path):
    monkeypatch.delenv("SYNAPSE_JEV", raising=False)
    monkeypatch.setenv("SYNAPSE_JEV_LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("TYPESAFE_API_KEY", FAKE_KEY)

    def _boom():
        raise AssertionError("SDK seam must not be touched while disabled")

    monkeypatch.setattr(adapter, "_load_sdk", _boom)
    monkeypatch.delitem(sys.modules, "typesafe_sdk", raising=False)
    assert judge(STATE, QUESTIONS, lane="unit") is None
    assert "typesafe_sdk" not in sys.modules
    assert not list(tmp_path.rglob("*.jsonl")), "disabled must short-circuit before any I/O"


@pytest.mark.parametrize("value", ["off", "0", "false", "OFF", "False"])
def test_off_values_disable(monkeypatch, tmp_path, value):
    monkeypatch.setenv("SYNAPSE_JEV", value)
    monkeypatch.setenv("SYNAPSE_JEV_LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("TYPESAFE_API_KEY", FAKE_KEY)
    monkeypatch.setattr(adapter, "_load_sdk", lambda: pytest.fail("SDK imported while disabled"))
    assert judge(STATE, QUESTIONS, lane="unit") is None
    assert not list(tmp_path.rglob("*.jsonl"))


# --------------------------------------------------------------------------- happy path, (d), (f)
def test_shadow_call_returns_answers_and_ledgers_row(env, monkeypatch):
    _install_fake_sdk(monkeypatch, _ok_answers)
    out = judge(STATE, QUESTIONS, lane="route")
    assert out == _ok_answers(None, None)
    assert _FakeClient.calls[0]["qids"] == ["mismatch", "route", "severity"]
    rows = _rows("route")
    assert len(rows) == 1
    row = rows[0]
    assert row["mode"] == "shadow"  # (f) default
    assert row["result"] == "ok"
    assert row["question_ids"] == ["mismatch", "route", "severity"]
    assert row["answers"] == out
    assert isinstance(row["latency_ms"], int)
    assert len(row["request_hash"]) == 16
    assert adapter.ledger_path("route").parent == env / "ledger"  # (d) dirs created


def test_mode_on_is_recorded_and_invalid_mode_returns_none(env, monkeypatch):
    _install_fake_sdk(monkeypatch, _ok_answers)
    assert judge(STATE, QUESTIONS, lane="m", mode="on") is not None
    assert judge(STATE, QUESTIONS, lane="m", mode="decide") is None  # never raises
    modes = [r["mode"] for r in _rows("m")]
    assert modes == ["on", "decide"]
    assert _rows("m")[1]["result"] == "fallback"


def test_default_ledger_root_is_under_home_synapse_jev(monkeypatch):
    monkeypatch.delenv("SYNAPSE_JEV_LEDGER_DIR", raising=False)
    p = adapter.ledger_path("x/y lane")
    assert p.parts[-3:-1] == (".synapse", "jev")
    assert p.name == "x_y_lane.jsonl"
    assert "harness" not in str(p)


# --------------------------------------------------------------------------- (a)
def test_sleeping_client_returns_none_within_one_second(env, monkeypatch):
    def _sleep(state, questions):
        time.sleep(5.0)
        return {}

    _install_fake_sdk(monkeypatch, _sleep)
    t0 = time.perf_counter()
    out = judge(STATE, QUESTIONS, lane="slow")
    wall = time.perf_counter() - t0
    assert out is None
    assert wall < 1.0, f"timeout was not wall-clock bounded: {wall:.3f}s"
    assert _rows("slow")[0]["result"] == "timeout"
    # the worker is a daemon so a hung SDK never pins interpreter exit
    workers = [t for t in threading.enumerate() if t.name == "synapse-jev-judge"]
    assert workers and all(t.daemon for t in workers)


def test_raising_client_returns_none_never_raises(env, monkeypatch):
    def _boom(state, questions):
        raise RuntimeError("upstream 500 " + FAKE_KEY)

    _install_fake_sdk(monkeypatch, _boom)
    assert judge(STATE, QUESTIONS, lane="err") is None
    row = _rows("err")[0]
    assert row["result"] == "fallback"
    assert "RuntimeError" in row["reason"]
    assert FAKE_KEY not in row["reason"]


def test_sdk_import_failure_returns_none(env, monkeypatch):
    def _no_sdk():
        raise ImportError("No module named typesafe_sdk")

    monkeypatch.setattr(adapter, "_load_sdk", _no_sdk)
    assert judge(STATE, QUESTIONS, lane="nosdk") is None
    assert _rows("nosdk")[0]["result"] == "fallback"


def test_garbage_inputs_never_raise(env, monkeypatch):
    _install_fake_sdk(monkeypatch, _ok_answers)
    assert judge(object(), None, lane="junk") is None  # questions not a dict
    assert judge(STATE, {"q": {"type": "bogus", "instructions": ""}}, lane="junk") is None


# --------------------------------------------------------------------------- (c)
def test_key_never_appears_in_ledger(env, monkeypatch):
    _install_fake_sdk(monkeypatch, _ok_answers)
    judge(STATE, QUESTIONS, lane="key")
    _install_fake_sdk(monkeypatch, lambda s, q: (_ for _ in ()).throw(ValueError(FAKE_KEY)))
    judge(STATE, QUESTIONS, lane="key")
    text = adapter.ledger_path("key").read_text(encoding="utf-8")
    assert FAKE_KEY not in text
    assert len(text.splitlines()) == 2
    assert _FakeClient.calls and all(True for _ in _FakeClient.calls)


def test_resolve_key_env_first_and_missing_key_returns_none(env, monkeypatch):
    assert adapter.resolve_key() == FAKE_KEY
    monkeypatch.setenv("TYPESAFE_API_KEY", "  ")
    monkeypatch.setattr(sys, "platform", "linux")  # skip the registry branch
    assert adapter.resolve_key() is None
    monkeypatch.setattr(adapter, "_load_sdk", lambda: pytest.fail("no key -> no SDK"))
    assert judge(STATE, QUESTIONS, lane="nokey") is None
    assert _rows("nokey")[0]["reason"] == "no_key"


def test_key_is_passed_to_client_not_ledger(env, monkeypatch):
    seen = {}

    def _client(api_key=None, timeout=None):
        seen["key"] = api_key
        seen["timeout"] = timeout
        return _FakeClient(api_key=api_key, timeout=timeout, behaviour=_ok_answers)

    monkeypatch.setattr(adapter, "_load_sdk", lambda: (_client, _Q, _Q, _Q))
    judge(STATE, QUESTIONS, lane="pass")
    assert seen["key"] == FAKE_KEY
    assert seen["timeout"] == adapter.TIMEOUT_S == 0.8


# --------------------------------------------------------------------------- (e)
def test_houdini_main_thread_is_refused_without_calling_out(env, monkeypatch):
    fake_hou = types.ModuleType("hou")
    fake_hou.isUIAvailable = lambda: True
    monkeypatch.setitem(sys.modules, "hou", fake_hou)
    monkeypatch.setattr(adapter, "_load_sdk", lambda: pytest.fail("called out from the GUI thread"))
    assert threading.current_thread() is threading.main_thread()
    assert judge(STATE, QUESTIONS, lane="gui") is None
    row = _rows("gui")[0]
    assert row["result"] == "main_thread_refused"
    assert row["mode"] == "shadow"


def test_houdini_worker_thread_is_allowed(env, monkeypatch):
    fake_hou = types.ModuleType("hou")
    fake_hou.isUIAvailable = lambda: True
    monkeypatch.setitem(sys.modules, "hou", fake_hou)
    _install_fake_sdk(monkeypatch, _ok_answers)
    box = {}
    t = threading.Thread(target=lambda: box.update(out=judge(STATE, QUESTIONS, lane="worker")))
    t.start()
    t.join(5)
    assert box["out"] == _ok_answers(None, None)


def test_headless_hou_does_not_refuse(env, monkeypatch):
    fake_hou = types.ModuleType("hou")
    fake_hou.isUIAvailable = lambda: False
    monkeypatch.setitem(sys.modules, "hou", fake_hou)
    _install_fake_sdk(monkeypatch, _ok_answers)
    assert judge(STATE, QUESTIONS, lane="headless") is not None


# --------------------------------------------------------------------------- fence
def test_adapter_module_never_mentions_the_build_time_tooling():
    import pathlib

    pkg = pathlib.Path(adapter.__file__).parent
    for p in pkg.glob("*.py"):
        assert "harness" not in p.read_text(encoding="utf-8"), p
