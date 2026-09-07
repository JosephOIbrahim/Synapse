"""Metadata-only routing evidence; every HTTP call is a controlled fixture."""
import copy
import json
import time
import urllib.request
from types import SimpleNamespace

import pytest

from synapse.panel import connections as cn
from synapse.panel.providers import catalog, probe


def spec(model="checked", endpoint="http://127.0.0.1:11434/v1/chat/completions"):
    return cn.ConnectionSpec("ollama", model, endpoint)


def weights(**extra):
    return {"name": "checked", "size": 128, "details": {"format": "gguf"}, **extra}


def test_checked_metadata_is_detached_and_deeply_read_only():
    raw = weights(capabilities=["completion", "tools"])
    facts = cn.ConnectionFacts(spec(), raw, time.time())
    raw["details"]["format"] = "unknown"
    raw["capabilities"].append("vision")
    raw["remote_host"] = "https://relay.invalid"
    assert facts.location == "Local"
    assert facts.capabilities == frozenset({"completion", "tools"})
    with pytest.raises(TypeError):
        facts.metadata["details"]["format"] = "unknown"
    with pytest.raises(TypeError):
        facts.metadata["capabilities"] = ("vision",)
    assert copy.copy(facts).capabilities == facts.capabilities
    assert copy.deepcopy(facts).location == "Local"


@pytest.mark.parametrize("details", [[], "gguf", True, 7, None])
def test_malformed_weight_details_never_promote_or_raise(details):
    facts = cn.ConnectionFacts(spec(), weights(details=details), time.time())
    assert facts.location == "Unverified"


@pytest.mark.parametrize("remote", [[], {}, False, 0])
def test_malformed_remote_markers_never_become_local(remote):
    facts = cn.ConnectionFacts(spec(), weights(remote_model=remote), time.time())
    assert facts.location == "Unverified"


def test_oversized_time_and_cyclic_metadata_are_unknown_without_raising():
    raw = weights()
    raw["cycle"] = raw
    shared = {"capabilities": ["completion"]}
    raw["one"] = raw["two"] = shared
    facts = cn.ConnectionFacts(spec(), raw, 10 ** 1000)
    assert not facts.fresh() and facts.location == "Unverified"
    assert facts.metadata["cycle"] is None
    assert facts.metadata["one"] is facts.metadata["two"]


@pytest.mark.parametrize("caps", ["tools", {"tools": True}, ["tools", 7], ["tools", ""], True])
def test_malformed_capability_reports_are_unknown(caps):
    facts = cn.ConnectionFacts(spec(), weights(capabilities=caps), time.time())
    assert facts.capabilities is None


@pytest.mark.parametrize("stamp", [0, -1, float("inf"), float("nan"), True, "yesterday"])
def test_invalid_or_future_check_cannot_be_local(stamp):
    facts = cn.ConnectionFacts(spec(), weights(), stamp)
    assert not facts.fresh(now=1000)
    assert facts.location_at(1000) == "Unverified"


def test_context_and_capabilities_come_from_show_and_do_not_invent_values():
    facts = cn.ConnectionFacts(spec(), weights(show={
        "capabilities": ["completion", "vision"],
        "parameters": "temperature 0.7\nnum_ctx 4096",
        "model_info": {"fixture.context_length": 8192},
    }), time.time())
    assert facts.capabilities == frozenset({"completion", "vision"})
    assert facts.context_window == 4096
    assert cn.ConnectionFacts(spec(), weights(show={"model_info": {"x.context_length": True}})).context_window is None
    assert cn.ConnectionFacts(spec(), weights(show={"model_info": {"x.context_length": "8192"}})).context_window is None
    assert cn.ConnectionFacts(spec(), weights(show={"remote_model": "other"}), time.time()).location == "Cloud relay"


def test_missing_or_failed_show_retains_only_truthful_partial_check(monkeypatch):
    monkeypatch.setattr(cn, "_get_json", lambda *a, **k: {"models": [weights()]})
    def unavailable(*args, **kwargs):
        raise OSError("private service failure")
    monkeypatch.setattr(cn, "_show_json", unavailable)
    checked = cn.check_connection(spec(), None)
    assert checked.ok and checked.facts.location == "Local"
    assert checked.facts.capabilities is None
    assert checked.facts.context_window is None
    assert "capabilities unknown" in checked.message.lower()
    assert "private" not in checked.message


class Response:
    def __init__(self, status, payload):
        self.status = status
        self.body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.offset = 0

    def read1(self, count):
        chunk = self.body[self.offset:self.offset + count]
        self.offset += len(chunk)
        return chunk

    def getheaders(self):
        return []


def serve(monkeypatch, responses):
    calls, closed = [], []
    pending = list(responses)
    class Connection:
        sock = None
        def __init__(self, host, timeout=None, **kwargs):
            self.host, self.timeout = host, timeout
        def request(self, method, path, body=None, headers=None):
            calls.append((self.host, method, path, body, dict(headers or {})))
        def getresponse(self):
            assert pending, "Unexpected additional metadata request"
            return pending.pop(0)
        def close(self):
            closed.append(self.host)
    monkeypatch.setattr(cn.http.client, "HTTPConnection", Connection)
    monkeypatch.setattr(cn.http.client, "HTTPSConnection", Connection)
    def unexpected(*args, **kwargs):
        raise AssertionError("Uncontrolled legacy HTTP path: network is closed")
    monkeypatch.setattr(urllib.request, "urlopen", unexpected)
    return calls, closed


def test_list_then_show_sends_only_model_to_same_endpoint(monkeypatch):
    calls, closed = serve(monkeypatch, [Response(200, {"models": [weights()]}), Response(200, {
        "capabilities": ["completion", "tools", "vision"],
        "model_info": {"fixture.context_length": 16384},
    })])
    checked = cn.check_connection(spec(endpoint="http://127.0.0.1:11434/prefix/v1/chat/completions"), None)
    assert checked.ok
    assert checked.facts.capabilities == frozenset({"completion", "tools", "vision"})
    assert checked.facts.context_window == 16384
    assert [(call[1], call[2]) for call in calls] == [("GET", "/prefix/api/tags"), ("POST", "/prefix/api/show")]
    assert json.loads(calls[1][3]) == {"model": "checked"}
    assert [call[0] for call in calls] == ["127.0.0.1:11434"] * 2
    assert len(closed) == 2


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_metadata_redirect_is_not_followed(monkeypatch, status):
    calls, closed = serve(monkeypatch, [Response(status, {"Location": "https://other.invalid"})])
    checked = cn.check_connection(spec(), None)
    assert not checked.ok and len(calls) == len(closed) == 1


def test_show_redirect_preserves_list_check_but_no_capabilities(monkeypatch):
    calls, closed = serve(monkeypatch, [Response(200, {"models": [weights()]}), Response(307, {})])
    checked = cn.check_connection(spec(), None)
    assert checked.ok and checked.facts.capabilities is None
    assert len(calls) == len(closed) == 2


def test_metadata_size_bound_is_enforced_and_closed(monkeypatch):
    calls, closed = serve(monkeypatch, [Response(200, b" " * 2_000_001)])
    checked = cn.check_connection(spec(), None)
    assert not checked.ok and "too large" in checked.message
    assert len(calls) == len(closed) == 1


def test_slow_body_hits_elapsed_deadline_and_closes(monkeypatch):
    from synapse.panel.providers import metadata_probes
    clock = [0.0]
    class DrippingResponse(Response):
        def read1(self, count):
            clock[0] += 4.0
            return b" "
    calls, closed = serve(monkeypatch, [DrippingResponse(200, b"")])
    monkeypatch.setattr(metadata_probes.time, "monotonic", lambda: clock[0])
    checked = cn.check_connection(spec(), None)
    assert not checked.ok and "timed out" in checked.message
    assert len(calls) == len(closed) == 1


def test_legacy_probe_uses_bounded_body_and_closes(monkeypatch):
    calls, closed = serve(monkeypatch, [Response(200, b" " * 2_000_001)])
    with pytest.raises(cn.MetadataError, match="too large"):
        probe._request("http", "127.0.0.1:1", "/api/tags", timeout=1)
    assert len(calls) == len(closed) == 1


@pytest.mark.parametrize("value", ["²", "nonsense", "-1", "0"])
def test_invalid_context_parameter_remains_unknown(value):
    facts = cn.ConnectionFacts(spec(), weights(show={"parameters": "num_ctx " + value}))
    assert facts.context_window is None


def test_no_key_is_sent_to_remote_http_metadata(monkeypatch):
    calls, closed = serve(monkeypatch, [])
    checked = cn.check_connection(spec(endpoint="http://render.invalid/v1/chat/completions"), "fixture-key")
    assert not checked.ok and "HTTPS" in checked.message
    assert calls == closed == []


@pytest.mark.parametrize("endpoint,row,expected", [
    ("http://127.0.0.1:11434", weights(), True),
    ("http://render.invalid:11434", weights(), False),
    ("http://127.0.0.1:11434", {"name": "checked"}, False),
    ("http://127.0.0.1:11434", weights(remote_model="relay"), False),
    ("http://127.0.0.1:11434", weights(name="checked:cloud"), False),
    ("http://127.0.0.1:11434", weights(size=True), False),
])
def test_catalog_uses_positive_local_evidence(monkeypatch, endpoint, row, expected):
    calls, closed = serve(monkeypatch, [Response(200, {"models": [row]})])
    models, latency, reason = catalog._discover_ollama(endpoint, 1)
    assert reason is None and models == {row["name"]: expected}
    assert latency >= 0 and len(calls) == len(closed) == 1


def test_catalog_failure_does_not_return_another_endpoints_cache(monkeypatch, tmp_path):
    path = tmp_path / "catalog.json"
    old = catalog.CatalogEntry("same-model", "ollama", "http://127.0.0.1:1", True, 10, 20, 1, True)
    catalog.save_catalog([old], path)
    original = path.read_bytes()
    monkeypatch.setattr(catalog, "_discover_ollama", lambda *a: (None, None, "unreachable"))
    result = catalog.refresh(path=path, endpoint="http://127.0.0.1:2", now=30)
    assert result.stale and result.entries == ()
    assert path.read_bytes() == original


def test_catalog_endpoint_change_does_not_inherit_first_seen(monkeypatch, tmp_path):
    path = tmp_path / "catalog.json"
    old = catalog.CatalogEntry("same-model", "ollama", "http://127.0.0.1:1", True, 10, 20, 1, True)
    catalog.save_catalog([old], path)
    monkeypatch.setattr(catalog, "_discover_ollama", lambda *a: ({"same-model": False}, 2, None))
    result = catalog.refresh(path=path, endpoint="http://127.0.0.1:2", now=30)
    assert result.entries[0].first_seen == result.entries[0].last_seen == 30
    assert result.new == ("same-model",) and result.removed == ()


def test_legacy_catalog_local_flags_are_not_positive_evidence(tmp_path):
    path = tmp_path / "catalog.json"
    row = catalog.CatalogEntry("old", "ollama", "http://127.0.0.1:1", True, 10, 20, 1, True)
    path.write_text(json.dumps({"version": 1, "entries": [row.to_dict()]}), encoding="utf-8")
    assert catalog.load_catalog(path)[0].local is False


def test_probe_unverified_tags_have_unknown_cost(monkeypatch):
    monkeypatch.setattr(probe, "_declared_models", lambda _: ())
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")
    monkeypatch.setattr(probe, "_request", lambda *a, **kw: (200, {}, json.dumps({"models": [{"name": "checked"}]}), 1))
    row = probe.probe_ollama()[0]
    assert row.cost_per_1k_in is None and row.cost_per_1k_out is None
    assert row.detail["location"] == "Unverified"


@pytest.mark.parametrize("endpoint,local", [("http://127.0.0.1:1", True), ("http://render.invalid:1", False)])
def test_probe_positive_weights_require_loopback(monkeypatch, endpoint, local):
    monkeypatch.setattr(probe, "_declared_models", lambda _: ())
    monkeypatch.setenv("OLLAMA_HOST", endpoint)
    monkeypatch.setattr(probe, "_request", lambda *a, **kw: (200, {}, json.dumps({"models": [weights()]}), 1))
    row = probe.probe_ollama()[0]
    assert (row.cost_per_1k_in == 0) is local
    assert row.detail["location"] == ("Local" if local else "Remote")


def test_bound_revocation_is_separate_from_secret_lifetime():
    events = []
    provider = SimpleNamespace(_model_grant=SimpleNamespace(release=lambda: events.append("released")),
                               _model_scope=SimpleNamespace(active=True), _panel_session_key="fixture-key")
    bound = cn.BoundConnection(spec(), provider, cn.ConnectionFacts(spec()))
    bound.revoke()
    assert events == ["released"] and provider._model_scope.active is False
    assert provider._panel_session_key == "fixture-key"
    bound.revoke()
    bound.release()
    assert events == ["released"] and provider._panel_session_key is None


def test_binding_preserves_actionable_model_access_denial():
    from synapse.model_access import ModelAccessDenied
    def refused(**kwargs):
        raise ModelAccessDenied("Project rules changed. Start a new task.")
    provider = SimpleNamespace(id="custom", model_identity="checked", stream=refused,
                               _get_endpoint=lambda: ("https", "fixture.invalid", "/v1/chat/completions"))
    bound = cn.bind_provider(provider, key=None)
    with pytest.raises(ModelAccessDenied, match="Project rules changed"):
        provider.stream()
    bound.release()
