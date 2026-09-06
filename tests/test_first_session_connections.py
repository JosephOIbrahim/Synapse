"""Artist-facing connection evidence and per-turn binding regressions."""
import time
from types import SimpleNamespace

import pytest

from synapse.panel import connections as cn


def test_local_requires_fresh_positive_weights_and_loopback():
    spec = cn.ConnectionSpec("ollama", "my-model:latest", "http://localhost:11434/v1/chat/completions")
    weights = {"name": spec.model, "size": 123, "details": {"format": "gguf"}}
    facts = cn.ConnectionFacts(spec, weights, time.time())
    assert facts.location == "Local"
    assert cn.ConnectionFacts(spec, {}, time.time()).location == "Unverified"
    assert cn.ConnectionFacts(spec, weights, time.time() - 181).location == "Unverified"
    assert cn.ConnectionFacts(spec, dict(weights, remote_host="https://ollama.com"), time.time()).location == "Cloud relay"
    remote = cn.ConnectionSpec("ollama", spec.model, "http://renderbox:11434/v1/chat/completions")
    assert cn.ConnectionFacts(remote, weights, time.time()).location == "Remote"
    custom = cn.ConnectionSpec("custom", spec.model, spec.endpoint)
    assert cn.ConnectionFacts(custom, weights, time.time()).location == "Unverified"
    cloud_tag = cn.ConnectionSpec("ollama", "gpt-oss:120b-cloud", spec.endpoint)
    assert cn.ConnectionFacts(cloud_tag, weights, time.time()).location == "Cloud relay"
    assert cn.ConnectionFacts(spec, dict(weights, remote_model="upstream"), time.time()).location == "Cloud relay"


@pytest.mark.parametrize("endpoint", ["https://user:secret@example.com/v1", "https://x/v1?key=secret", "file:///tmp/model", "https://x/v1#secret", "https://x/\nheader"])
def test_unsafe_endpoint_rejected_without_echoing_secret(endpoint):
    with pytest.raises(ValueError) as error:
        cn.validate_endpoint(endpoint)
    assert endpoint not in str(error.value)


def test_binding_freezes_endpoint_key_and_model(monkeypatch):
    from synapse.panel.providers.ollama_provider import OllamaProvider
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
    p = OllamaProvider(model="one:cloud", max_tokens=100)
    bound = cn.bind_provider(p, key="session-secret")
    monkeypatch.setenv("OLLAMA_HOST", "https://other.example")
    monkeypatch.setenv("OLLAMA_API_KEY", "replacement")
    assert p._get_endpoint() == ("http", "localhost:11434", "/v1/chat/completions")
    assert p.resolve_key() == "session-secret"
    assert bound.spec.model == "one:cloud"
    assert "session-secret" not in repr(bound)
    bound.release()
    assert p.resolve_key() is None


def test_metadata_success_does_not_claim_generation(monkeypatch):
    spec = cn.ConnectionSpec("custom", "model-a", "https://example.com/v1/chat/completions")
    monkeypatch.setattr(cn, "_get_json", lambda *a, **k: {"data": [{"id": "model-a"}]})
    result = cn.check_connection(spec, "secret")
    assert result.ok
    assert "generation untested" in result.message.lower()
    assert result.facts.location == "Remote"
    missing = cn.check_connection(cn.ConnectionSpec("custom", "missing", spec.endpoint), "secret")
    assert not missing.ok
    assert missing.facts is None


def test_metadata_error_is_sanitized(monkeypatch):
    def fail(*a, **k):
        raise RuntimeError("secret credential and private response")
    monkeypatch.setattr(cn, "_get_json", fail)
    spec = cn.ConnectionSpec("claude", "one", "https://api.anthropic.com/v1/messages")
    result = cn.check_connection(spec, "secret")
    assert not result.ok
    assert "secret" not in result.message


def test_tag_alone_never_means_local_or_free():
    from synapse.panel.providers import model_facts
    assert not model_facts.is_local("ollama", "ordinary-tag")
    assert model_facts.cost({"provider": "ollama", "model": "ordinary-tag", "output_tokens": 5}) is None


def test_streaming_error_cannot_echo_session_secret_to_exception_log():
    import traceback
    from synapse.panel.providers.custom_provider import CustomProvider
    provider = CustomProvider(base_url="https://example.com/v1", model="a")
    def rejected(**kwargs):
        raise RuntimeError("401 Authorization: Bearer private-session-key")
    provider.stream = rejected
    bound = cn.bind_provider(provider, key="private-session-key")
    try:
        provider.stream(api_key=provider.resolve_key())
    except RuntimeError as error:
        rendered = traceback.format_exc()
        assert "private-session-key" not in rendered
        assert "Authorization" not in rendered
        assert "request failed" in str(error)
    else:
        raise AssertionError("The failed request must remain a failure")
    finally:
        bound.release()
