"""Composed owned request paths, using real SDK parsing and offline transports."""
import asyncio
import importlib.util
import json
from pathlib import Path
import threading
import time
from unittest.mock import Mock

import pytest

from synapse import model_access as access
from synapse.cognitive.agent_loop import run_turn, AgentTurnConfig
from synapse.routing.router import TieredRouter, RoutingConfig


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "rules.json"))
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(tmp_path / "settings.json"))


def client_for(calls, content=None, stop_reason="end_turn"):
    http = access.sdk_http_module()
    def reply(request):
        calls.append(json.loads(request.content))
        return http.Response(200, json={"id": "test-message", "type": "message", "role": "assistant",
            "model": "server-resolved", "content": content or [{"type": "text", "text": "done"}],
            "stop_reason": stop_reason, "usage": {"input_tokens": 11, "output_tokens": 2}})
    return access.make_anthropic_client("synthetic", base_url="https://fixture.example", transport=http.MockTransport(reply))


def approve(client, *models):
    access.save_policy("ask", tuple(access.sdk_spec(client, model) for model in models))


def test_agent_loop_denied_then_allowed_then_followup_rules_change():
    calls = []
    dispatcher = Mock()
    dispatcher.tool_schemas.return_value = []
    with client_for(calls) as client:
        cfg = AgentTurnConfig(model="chosen", max_tokens=8)
        denied = run_turn(client, dispatcher, "private sentinel", config=cfg)
        assert denied.status == "api_error" and "permission" in denied.error and calls == []
        approve(client, "chosen")
        allowed = run_turn(client, dispatcher, "synthetic task", config=cfg)
        assert allowed.status == "complete" and len(calls) == 1
        assert access.sdk_receipt(client)["reported_model"] == "server-resolved"
    calls = []
    with client_for(calls, [{"type": "tool_use", "id": "call1", "name": "echo", "input": {}}], "tool_use") as client:
        approve(client, "chosen")
        dispatcher.execute.side_effect = lambda *_: (access.save_policy("local_only"), {"ok": True})[1]
        result = run_turn(client, dispatcher, "synthetic followup", config=cfg)
        assert result.status == "api_error" and len(calls) == 1
        assert result.tool_calls_made == 1


def router_with(client, *, deep=False, asynchronous=False):
    router = TieredRouter(config=RoutingConfig(enable_tier0=False, enable_tier1=False,
        enable_recipes=False, enable_tier2=not deep, enable_tier3=deep, tier3_async=asynchronous,
        llm_api_key="synthetic", llm_model_fast="fast", llm_model_deep="deep"))
    router._llm_client = client
    return router


@pytest.mark.parametrize("deep", [False, True])
def test_router_direct_model_lanes_and_pinned_retry_stay_guarded(deep):
    calls = []
    with client_for(calls) as client:
        router = router_with(client, deep=deep)
        denied = router.route("Invent a distinctive synthetic fixture idea")
        assert not denied.success and denied.metadata["model_access"] == "blocked" and calls == []
        approve(client, "fast", "deep")
        allowed = router.route("Invent another distinctive synthetic fixture idea")
        assert allowed.success and len(calls) == 1
        receipt = allowed.metadata["model_request"]
        assert receipt["requested_model"] == ("deep" if deep else "fast")
        assert receipt["reported_model"] == "server-resolved" and receipt["usage"]["input_tokens"] == 11
        # Bypass local cache explicitly, then exercise the pinned LLM tier.
        access.save_policy("local_only")
        denied = router._try_pinned_tier("deep" if deep else "standard", "synthetic pinned", {}, "ctx", time.monotonic())
        assert denied is not None and not denied.success and len(calls) == 1


def test_async_router_keeps_scope_captured_before_queue(monkeypatch, tmp_path):
    calls, queued = [], []
    class PausedThread:
        def __init__(self, *, target, args, daemon):
            queued.append((target, args))
        def start(self):
            pass
    with client_for(calls) as client:
        approve(client, "deep")
        router = router_with(client, deep=True, asynchronous=True)
        monkeypatch.setattr("synapse.routing.router.threading.Thread", PausedThread)
        launched = router.route("Invent a synthetic pending task")
        assert launched.success and len(queued) == 1 and calls == []
        monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "other-project.json"))
        approve(client, "deep")
        target, args = queued[0]
        target(*args)
        completed = next(iter(router._async_results.values()))
        assert not completed.success and completed.metadata["model_access"] == "blocked" and calls == []


def test_daemon_envelope_captures_project_before_processing(monkeypatch, tmp_path):
    from synapse.host.daemon import _AgentRequest, SynapseDaemon
    from synapse.host.turn_handle import TurnHandle
    calls = []
    with client_for(calls) as client:
        approve(client, "chosen")
        pending = _AgentRequest("synthetic queued task", AgentTurnConfig(model="chosen"), TurnHandle())
        monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "project-b.json"))
        approve(client, "chosen")
        daemon = SynapseDaemon.__new__(SynapseDaemon)
        daemon._dispatcher = Mock(tool_schemas=Mock(return_value=[]))
        daemon._anthropic_client = client
        daemon._cancel_event = threading.Event()
        daemon._process_request(pending)
        result = pending.handle.result(timeout=.1)
        assert result.status == "api_error" and "changed" in result.error and calls == []
        assert pending.model_scope.active is False


def test_cli_planner_uses_same_guard(monkeypatch):
    import sys
    path = Path(__file__).parents[1] / "agent/synapse_planner.py"
    monkeypatch.syspath_prepend(str(path.parent))
    spec = importlib.util.spec_from_file_location("synapse_routing_test_planner", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    calls = []
    with client_for(calls) as client:
        with pytest.raises(access.ModelAccessDenied):
            asyncio.run(module.create_plan(client, "synthetic goal", {"synthetic": True}, model="planner"))
        assert calls == []


def test_process_handoff_cannot_borrow_changed_project(monkeypatch, tmp_path):
    from synapse.request_handoff import export_scope, import_scope
    calls = []
    with client_for(calls) as client:
        approve(client, "worker")
        token = export_scope()
        monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "different.json"))
        approve(client, "worker")
        accepted = import_scope(token)
        with access.request_scope(accepted), pytest.raises(access.ModelAccessDenied, match="changed"):
            access.guarded_create(client, lane="process-test", model="worker", max_tokens=8, messages=[])
        assert calls == []


def test_malformed_process_scope_is_not_fresh_consent():
    from synapse.request_handoff import import_scope
    for token in ("not-base64", "e30=", "W10=", "x" * 16385):
        with pytest.raises(access.ModelAccessDenied):
            import_scope(token)


def test_deferred_coroutine_keeps_call_time_project(monkeypatch, tmp_path):
    calls = []
    @access.scoped_request
    async def later(client):
        return access.guarded_create(client, lane="queued-coroutine", model="worker", max_tokens=8, messages=[])
    with client_for(calls) as client:
        approve(client, "worker")
        queued = later(client)
        monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "project-b.json"))
        approve(client, "worker")
        with pytest.raises(access.ModelAccessDenied, match="changed"):
            asyncio.run(queued)
        assert calls == []


def test_queued_child_inherits_parent_scope_and_stop(monkeypatch, tmp_path):
    from synapse.host.daemon import _AgentRequest
    from synapse.host.turn_handle import TurnHandle
    from synapse.request_handoff import export_scope, import_scope
    parent = access.capture_scope()
    with access.request_scope(parent):
        monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "project-b.json"))
        queued = _AgentRequest("parent task", AgentTurnConfig(), TurnHandle())
        assert queued.model_scope.path == parent.path
        assert queued.model_scope is not parent
        assert not queued.model_scope.cancelled()
        parent.active = False
        assert queued.model_scope.cancelled()
        handoff = import_scope(export_scope())
        assert not handoff.active


def test_handoff_duplicate_fields_cannot_revive_cancelled_scope():
    import base64
    from synapse.request_handoff import import_scope, export_scope
    raw = base64.urlsafe_b64decode(export_scope()).decode("utf-8")
    raw = raw.replace('"active": true', '"active": false, "active": true')
    with pytest.raises(access.ModelAccessDenied):
        import_scope(base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii"))


def test_openai_images_are_pixels_not_serialized_json():
    from synapse.panel.providers.nemotron_provider import _to_openai_messages
    image = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "aGVsbG8="}}
    converted = _to_openai_messages([
        {"role": "user", "content": [{"type": "text", "text": "look"}, image]},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "a", "name": "capture", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a", "content": [{"type": "text", "text": "captured"}, image]}]},
    ], "", directive=None)
    images = [part for msg in converted if isinstance(msg.get("content"), list) for part in msg["content"] if part["type"] == "image_url"]
    assert len(images) == 2 and all(part["image_url"]["url"] == "data:image/png;base64,aGVsbG8=" for part in images)
    assert next(msg for msg in converted if msg["role"] == "tool")["content"] == "captured"
