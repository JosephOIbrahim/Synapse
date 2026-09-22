"""Shadow behavior tests, with synthetic replies and no external calls."""
import copy
import json
from pathlib import Path
import sys
import threading
import time
from unittest.mock import MagicMock

import pytest

from synapse import model_access as access
from synapse.jev import adapter, panel_routing as routing
from synapse.jev.panel_questions import QUESTIONS, VERSION
from synapse.panel import settings
from synapse.panel.providers.registry import PROVIDER_IDS
from test_worker_tool_policy import claude_worker_module  # noqa: F401


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "policy.json"))
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(tmp_path / "panel.json"))
    monkeypatch.setenv("SYNAPSE_JEV_LEDGER_DIR", str(tmp_path / "jev"))
    monkeypatch.setenv("SYNAPSE_USAGE_LEDGER", str(tmp_path / "usage/turns.jsonl"))
    monkeypatch.setenv("TYPESAFE_API_KEY", "tsk-synthetic-unit-key")
    monkeypatch.delenv("SYNAPSE_JEV", raising=False)
    monkeypatch.setitem(sys.modules, "hou", None)
    monkeypatch.setattr(adapter, "_post", lambda *args: pytest.fail("live transport forbidden"))
    settings.save_settings({**settings.default_settings(), "jev_routing_mode": "shadow"})
    return tmp_path


def response(work="new_graph", context="solaris"):
    values = {"work_shape": work, "context_family": context}
    return {"model": "jev-1.13.0", "usage": {}, "answers": {
        key: {"type": "choice", "choice": selected, "confidence": 1.,
              "probabilities": {option: float(option == selected) for option in QUESTIONS[key]["criteria"]}}
        for key, selected in values.items()}}


def start(scope=None, text="Build a Solaris scene.", **kwargs):
    return routing.start_shadow([{"role": "user", "content": text}],
        scope=scope or access.capture_scope(), provider="ollama", model="kimi-k3:cloud",
        should_abort=lambda: False, **kwargs)


def settle():
    assert routing._JOBS.slot.acquire(timeout=3)
    routing._JOBS.slot.release()


def test_off_does_not_resolve_credentials_or_start_job(environment, monkeypatch):
    monkeypatch.setattr(adapter, "resolve_key", lambda: pytest.fail("off did I/O"))
    assert start(mode="off").snapshot()["status"] == "disabled"
    assert not (environment / "jev").exists()


def test_environment_off_overrides_saved_measure(environment, monkeypatch):
    monkeypatch.setenv("SYNAPSE_JEV", "off")
    assert start().snapshot()["status"] == "disabled"


def test_projection_never_reads_history_images_or_dropped_paths():
    history = [{"role": "user", "content": "secret old conversation"},
               {"role": "assistant", "content": [{"type": "image", "data": "private"}]},
               {"role": "user", "content": "[Context: /private/scene/node]\nExplain Solaris."}]
    state, error = routing.project_request(history, network_kind="not-whitelisted")
    assert error is None
    assert state == {"artist_request": "Explain Solaris.", "context": {"network_kind": "unknown"}}
    assert history[0]["content"] == "secret old conversation"


@pytest.mark.parametrize("content,reason", [
    ([{"type": "image", "data": "private"}], "non_text_request"),
    ("x" * 4097, "request_too_large"),
    ("import hou\nhou.node('/stage')", "private_or_code_request"),
    ("Use my password hunter2", "private_or_code_request"),
    ("```python\nprint(1)\n```", "private_or_code_request"),
    ('{"nodes": []}', "private_or_code_request"),
    ("Use tsk_abcdefghijk for this", "private_or_code_request"),
])
def test_private_or_unbounded_requests_are_skipped(content, reason):
    assert routing.project_request([{"role": "user", "content": content}]) == (None, reason)


def test_shadow_has_no_join_and_global_job_capacity(environment, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def slow(*args, **kwargs):
        entered.set()
        release.wait(3)
        return response()
    monkeypatch.setattr(adapter, "judge", slow)
    before = time.perf_counter()
    job = start()
    try:
        assert time.perf_counter() - before < .5
        assert entered.wait(2)
        assert not any(hasattr(job, name) for name in ("wait", "join", "result"))
        assert start().snapshot()["reason"] == "busy"
        assert job.snapshot()["status"] == "pending"
    finally:
        release.set()
        settle()
    assert job.snapshot()["status"] == "measured"
    assert job.snapshot()["generator"] == {"provider": "ollama", "model": "kimi-k3:cloud"}
    assert job.snapshot()["behavior_changed"] is False


def test_late_cancelled_answer_is_discarded_and_next_task_independent(environment, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def slow(*args, **kwargs):
        entered.set()
        release.wait(3)
        return response()
    monkeypatch.setattr(adapter, "judge", slow)
    scope = access.capture_scope()
    first = start(scope)
    try:
        assert entered.wait(2)
        scope.active = False
    finally:
        release.set()
        settle()
    assert first.snapshot()["status"] == "discarded"
    assert "judgments" not in first.snapshot()
    second = start()
    settle()
    assert second.snapshot()["status"] == "measured"
    assert second.snapshot()["task_id"] != first.snapshot()["task_id"]


def test_missing_permission_is_measured_as_unavailable(environment):
    job = start()
    settle()
    assert job.snapshot()["status"] == "unavailable"
    assert job.snapshot()["reason"] == "permission_or_scope"


def test_saved_off_discards_inflight_measurement(environment, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    callbacks = []
    def slow(*args, **kwargs):
        callbacks.append(kwargs["should_abort"])
        entered.set()
        release.wait(3)
        return response()
    monkeypatch.setattr(adapter, "judge", slow)
    job = start()
    try:
        assert entered.wait(2)
        settings.save_settings({**settings.default_settings(), "jev_routing_mode": "off"})
        assert callbacks[0]()
    finally:
        release.set()
        settle()
    assert job.snapshot()["status"] == "discarded"
    assert "judgments" not in job.snapshot()


def test_shadow_only_even_when_adapter_env_is_on(environment, monkeypatch):
    seen = []
    def judge(*args, **kwargs):
        seen.append(kwargs["mode"])
        return response()
    monkeypatch.setattr(adapter, "judge", judge)
    monkeypatch.setenv("SYNAPSE_JEV", "on")
    job = start()
    settle()
    assert seen == ["shadow"]
    assert job.snapshot()["behavior_changed"] is False
    assert "typesafe" not in PROVIDER_IDS


def test_malformed_reply_is_not_published(environment, monkeypatch):
    answer = response()
    answer["answers"]["work_shape"]["choice"] = "change_generator"
    monkeypatch.setattr(adapter, "judge", lambda *args, **kwargs: answer)
    job = start()
    settle()
    assert job.snapshot()["status"] == "unavailable"
    assert "judgments" not in job.snapshot()


def test_saved_routing_mode_defaults_off_and_rejects_active(environment):
    settings.save_settings({"jev_routing_mode": "on", "provider_id": "ollama",
                            "model_by_provider": {"ollama": "kimi-k3:cloud"}})
    loaded = settings.load_settings()
    assert loaded["jev_routing_mode"] == "off"
    assert loaded["model_by_provider"] == {"ollama": "kimi-k3:cloud"}


def test_named_evaluation_fixture_has_covered_labels_not_claimed_accuracy():
    data = json.loads((Path(__file__).parent / "fixtures/jev_panel_routes_v1.json").read_text())
    assert data["name"] == VERSION
    assert "no live model accuracy measured" in data["status"]
    for field in QUESTIONS:
        assert {case[field] for case in data["cases"]} == set(QUESTIONS[field]["criteria"])


def test_worker_completes_with_pending_shadow_and_keeps_generator_inputs(
        environment, monkeypatch, claude_worker_module):
    entered, release = threading.Event(), threading.Event()
    def slow(*args, **kwargs):
        entered.set()
        release.wait(3)
        return response()
    monkeypatch.setattr(adapter, "judge", slow)
    observed = []
    class Provider:
        id = "ollama"
        model_identity = "kimi-k3:cloud"
        last_usage = None
        def stream(self, **kwargs):
            observed.append(copy.deepcopy({key: kwargs[key] for key in ("messages", "tools", "system")}))
            kwargs["emit_token"]("Hello")
            return "end_turn", [{"type": "text", "text": "Hello"}]
    provider = Provider()
    messages = [{"role": "user", "content": "Build a Solaris scene."}]
    cw = claude_worker_module
    worker = cw.ClaudeWorker(messages, provider=provider, tools=[], system_prompt="fixed generator instructions")
    worker.token_received = MagicMock()
    worker.activity_changed = MagicMock()
    before = time.perf_counter()
    try:
        worker._conversation_loop("generator-key")
        assert time.perf_counter() - before < .5
        assert entered.wait(2)
        assert worker._shadow_job.snapshot()["status"] == "pending"
        assert worker._provider is provider
        assert observed == [{"messages": messages, "tools": [], "system": "fixed generator instructions"}]
        row = json.loads((environment / "usage/turns.jsonl").read_text())
        assert row["jev"]["status"] == "pending"
        assert row["model"] == "kimi-k3:cloud"
        assert row["worker_first_token_ms"] is not None
        assert row["task_id"] == row["jev"]["task_id"]
        assert row["worker_ms"] >= row["worker_first_token_ms"]
    finally:
        worker.abort()
        release.set()
        settle()
    assert worker._shadow_job.snapshot()["status"] == "discarded"


def test_blocked_shadow_keeps_generator_inputs_and_model(environment, claude_worker_module):
    seen = []
    class Provider:
        id = "custom"
        model_identity = "artist-chosen-model"
        last_usage = None
        def stream(self, **kwargs):
            seen.append((copy.deepcopy(kwargs["messages"]), copy.deepcopy(kwargs["tools"]), kwargs["system"]))
            return "end_turn", []
    messages = [{"role": "user", "content": "Explain Solaris."}]
    tools = [{"name": "synapse_ping", "input_schema": {"type": "object"}}]
    provider = Provider()
    worker = claude_worker_module.ClaudeWorker(messages, tools=tools, provider=provider, system_prompt="unchanged")
    worker.activity_changed = MagicMock()
    worker._conversation_loop("generator-key")
    settle()
    assert worker._shadow_job.snapshot()["reason"] == "permission_or_scope"
    assert seen == [(messages, tools, "unchanged")]
    assert worker._provider is provider
