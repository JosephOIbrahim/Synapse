"""Physical request controls exercised with instrumented, offline transports."""
import json
from unittest.mock import Mock

import pytest

from synapse import model_access as access
from synapse.panel.connections import provider_spec


@pytest.fixture(autouse=True)
def isolated_rules(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "rules.json"))
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(tmp_path / "panel.json"))


def sdk_client(handler):
    http = access.sdk_http_module()
    return access.make_anthropic_client(api_key="synthetic-key", base_url="https://sdk.example",
                                        transport=http.MockTransport(handler))


def reply(request, status=200, headers=None):
    http = access.sdk_http_module()
    return http.Response(status, headers=headers, json={"id": "msg_test", "type": "message",
        "role": "assistant", "model": "resolved-model", "content": [{"type": "text", "text": "ok"}],
        "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 7, "output_tokens": 3}})


def invoke(client, **extra):
    return access.guarded_create(client, lane="offline-test", model="requested-alias", max_tokens=8,
        messages=[{"role": "user", "content": "private sentinel"}], **extra)


def approve(client):
    spec = access.sdk_spec(client, "requested-alias")
    access.save_policy("ask", (spec,))


def test_opaque_sdk_client_refused_even_with_project_approval():
    spec = access.ConnectionSpec("claude", "requested-alias", "https://sdk.example/v1/messages")
    access.save_policy("ask", (spec,))
    client = Mock(base_url="https://sdk.example/")
    with pytest.raises(access.ModelAccessDenied, match="guarded"):
        invoke(client)
    client.messages.create.assert_not_called()


def test_sdk_denial_then_approval_then_revocation():
    calls = []
    with sdk_client(lambda req: (calls.append(req), reply(req))[1]) as client:
        with pytest.raises(access.ModelAccessDenied):
            invoke(client)
        assert calls == []
        approve(client)
        result = invoke(client)
        assert result.model == "resolved-model"
        assert len(calls) == 1 and json.loads(calls[0].content)["model"] == "requested-alias"
        receipt = access.recent_attempts()[-1]
        assert receipt["reported_model"] == "resolved-model"
        assert receipt["usage"]["input_tokens"] == 7
        assert "private sentinel" not in json.dumps(receipt)
        access.save_policy("local_only")
        with pytest.raises(access.ModelAccessDenied):
            invoke(client)
        assert len(calls) == 1


@pytest.mark.parametrize("status", [307, 429, 500])
def test_sdk_never_redirects_or_retries(status, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:1234")
    calls = []
    with sdk_client(lambda req: (calls.append(req), reply(req, status, {"location": "https://elsewhere.example/v1/messages"}))[1]) as client:
        approve(client)
        try:
            invoke(client)
        except Exception:
            pass
        assert len(calls) == 1
        assert str(calls[0].url) == "https://sdk.example/v1/messages"
        assert not client._client._mounts


@pytest.mark.parametrize("change", ["endpoint", "key", "hooks", "retry", "redirect", "payload_model"])
def test_sdk_actual_transport_cannot_change_after_approval(change):
    calls = []
    with sdk_client(lambda req: (calls.append(req), reply(req))[1]) as client:
        approve(client)
        extra = {}
        if change == "endpoint":
            client.base_url = "https://elsewhere.example"
        elif change == "key":
            client.api_key = "different"
        elif change == "hooks":
            client._client.event_hooks["request"] = []
        elif change == "retry":
            client.max_retries = 2
        elif change == "redirect":
            client._client.follow_redirects = True
        else:
            extra["extra_body"] = {"model": "other-model"}
        with pytest.raises(Exception):
            invoke(client, **extra)
        assert calls == []


@pytest.mark.parametrize("provider_id", ["claude", "gemini", "nemotron", "ollama", "custom"])
def test_every_raw_provider_denies_before_transport(provider_id, monkeypatch):
    from synapse.panel.providers.registry import build_provider
    from synapse.panel.providers.custom_provider import CustomProvider
    provider = (CustomProvider(base_url="https://custom.example/v1", model="requested-alias")
                if provider_id == "custom" else build_provider(provider_id, model="requested-alias"))
    # No implicit loopback discovery or environment credential lookup in this test.
    calls = Mock(side_effect=AssertionError("Transport reached without approval"))
    monkeypatch.setattr("http.client.HTTPSConnection", calls)
    monkeypatch.setattr("http.client.HTTPConnection", calls)
    with pytest.raises(access.ModelAccessDenied):
        provider.stream(messages=[{"role": "user", "content": "private sentinel"}], tools=[],
                        system="", api_key="synthetic-key", emit_token=lambda _: None, should_abort=lambda: False)
    assert calls.call_count == 0


def test_unknown_provider_never_falls_back_to_cloud():
    from synapse.panel.providers.registry import build_provider
    with pytest.raises(ValueError, match="unavailable"):
        build_provider("retired-engine")


@pytest.mark.parametrize("reason", ["scope", "abort"])
def test_early_stream_refusal_keeps_its_own_receipt(reason, monkeypatch):
    from synapse.panel.providers.custom_provider import CustomProvider
    provider = CustomProvider(base_url="https://custom.example/v1", model="queued-model")
    spec = provider_spec(provider)
    access.save_policy("ask", (spec,))
    provider._model_scope = access.capture_scope()
    if reason == "scope":
        access.save_policy("local_only")
    previous = access.recent_attempts()
    calls = Mock(side_effect=AssertionError("A refused task reached transport"))
    monkeypatch.setattr("http.client.HTTPSConnection", calls)
    monkeypatch.setattr("http.client.HTTPConnection", calls)
    with pytest.raises(access.ModelAccessDenied):
        provider.stream(messages=[{"role": "user", "content": "private sentinel"}], tools=[],
            system="", api_key="synthetic-key", emit_token=lambda _: None,
            should_abort=lambda: reason == "abort")
    records = access.recent_attempts()
    assert records[-1]["attempt_id"] not in {r["attempt_id"] for r in previous}
    assert records[-1]["task_id"] == provider._model_scope.task_id
    assert records[-1]["result"] == "blocked" and records[-1]["reason"]
    assert records[-1]["reported_model"] is None and records[-1]["usage"] is None
    assert "private sentinel" not in json.dumps(records[-1])
    assert calls.call_count == 0
