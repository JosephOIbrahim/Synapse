"""Offline v1 contract + transport/permission boundaries. No live model calls."""
import copy
import importlib.util
import json
import sys
import threading
import time
import types

import pytest

from synapse import model_access as access
from synapse.jev import adapter, judge

FAKE_KEY = "tsk-SECRET-0123456789abcdef"
STATE = {"doc": "Build a Solaris network."}
QUESTIONS = {
    "mismatch": {"type": "noul", "instructions": "Is the count off?"},
    "severity": {"type": "score", "instructions": "How bad?", "criteria": ["fine", "broken"]},
    "route": {"type": "choice", "instructions": "Who fixes it?", "criteria": {"a": None, "b": None}},
}
RESPONSE = {"model": "jev-1.13.0", "usage": {"input_tokens": 30, "output_tokens": 10}, "answers": {
    "mismatch": {"type": "noul", "noul": .9},
    "severity": {"type": "score", "score": .7, "probabilities": {"0": .3, "1": .7}, "confidence": .6},
    "route": {"type": "choice", "choice": "a", "probabilities": {"a": .8, "b": .2}, "confidence": .7},
}}
REAL_POST = adapter._post


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(adapter, "_post", lambda *args: pytest.fail("unexpected transport call"))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_JEV_LEDGER_DIR", str(tmp_path / "ledger"))
    monkeypatch.setenv("SYNAPSE_JEV", "on")
    monkeypatch.setenv("TYPESAFE_API_KEY", FAKE_KEY)
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "policy.json"))
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(tmp_path / "panel.json"))
    monkeypatch.setitem(sys.modules, "hou", None)
    access.save_policy("ask", (adapter.connection_spec(),))
    return tmp_path


def install(monkeypatch, behavior=None):
    calls = []
    def fake(payload, key, before_send):
        before_send()
        calls.append(json.loads(payload))
        return behavior() if behavior else copy.deepcopy(RESPONSE)
    monkeypatch.setattr(adapter, "_post", fake)
    return calls


def rows(lane):
    path = adapter.ledger_path(lane)
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_unset_env_returns_none_without_io(monkeypatch, tmp_path):
    monkeypatch.delenv("SYNAPSE_JEV", raising=False)
    monkeypatch.setenv("SYNAPSE_JEV_LEDGER_DIR", str(tmp_path))
    monkeypatch.setattr(adapter, "resolve_key", lambda: pytest.fail("disabled resolved a key"))
    assert judge(STATE, QUESTIONS, lane="unit") is None
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("value", ["off", "0", "false", "OFF", "False", ""])
def test_off_values_disable_even_saved_opt_in(monkeypatch, tmp_path, value):
    monkeypatch.setenv("SYNAPSE_JEV", value)
    monkeypatch.setenv("SYNAPSE_JEV_LEDGER_DIR", str(tmp_path))
    assert judge(STATE, QUESTIONS, lane="unit", opt_in=True) is None
    assert not list(tmp_path.iterdir())


def test_shadow_call_returns_current_answers_and_receipt(env, monkeypatch):
    calls = install(monkeypatch)
    evidence = {}
    out = judge(STATE, QUESTIONS, lane="route", receipt=evidence)
    assert out == RESPONSE
    assert calls[0]["model"] == "jev-latest"
    assert rows("route") == [evidence]
    assert evidence["mode"] == "shadow" and evidence["result"] == "ok"
    assert evidence["requested_model"] == "jev-latest"
    assert evidence["reported_model"] == "jev-1.13.0"
    assert len(evidence["request_hash"]) == 16
    assert evidence["task_id"]
    assert "state" not in evidence
    assert access.recent_attempts()[-1]["provider"] == "typesafe"
    assert access.recent_attempts()[-1]["result"] == "completed"


def test_mode_recorded_and_invalid_mode_refuses(env, monkeypatch):
    install(monkeypatch)
    assert judge(STATE, QUESTIONS, lane="mode", mode="on")
    assert judge(STATE, QUESTIONS, lane="mode", mode="decide") is None
    assert [row["mode"] for row in rows("mode")] == ["on", "decide"]


def test_default_ledger_root_under_home(monkeypatch):
    monkeypatch.delenv("SYNAPSE_JEV_LEDGER_DIR", raising=False)
    path = adapter.ledger_path("x/y lane")
    assert path.parts[-3:-1] == (".synapse", "jev")
    assert path.name == "x_y_lane.jsonl"


def test_timeout_keeps_capacity_until_actual_transport_ends(env, monkeypatch):
    release, ended = threading.Event(), threading.Event()
    monkeypatch.setattr(adapter, "TIMEOUT_S", .04)
    def slow():
        try:
            release.wait(2)
            return copy.deepcopy(RESPONSE)
        finally:
            ended.set()
    calls = install(monkeypatch, slow)
    started = time.perf_counter()
    try:
        assert judge(STATE, QUESTIONS, lane="slow") is None
        assert time.perf_counter() - started < .5
        assert rows("slow")[0]["result"] == "timeout"
        spec = importlib.util.spec_from_file_location("jev_adapter_reload_probe", adapter.__file__)
        reloaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reloaded)
        assert reloaded._CAPACITY is adapter._CAPACITY
        assert not reloaded._CAPACITY.slot.acquire(blocking=False)
        assert judge(STATE, QUESTIONS, lane="busy") is None
        assert rows("busy")[0]["reason"] == "busy"
        assert len(calls) == 1
        assert all(t.daemon for t in threading.enumerate() if t.name == "synapse-jev-judge")
    finally:
        release.set()
        assert ended.wait(2)
        # Acquire proves transport cleanup, rather than a guessed sleep.
        assert adapter._CAPACITY.slot.acquire(timeout=2)
        adapter._CAPACITY.slot.release()
    assert judge(STATE, QUESTIONS, lane="after") is not None


def test_errors_never_echo_keys_or_state(env, monkeypatch):
    install(monkeypatch, lambda: (_ for _ in ()).throw(RuntimeError(FAKE_KEY + str(STATE))))
    assert judge(STATE, QUESTIONS, lane="err") is None
    text = adapter.ledger_path("err").read_text()
    assert FAKE_KEY not in text and STATE["doc"] not in text
    assert rows("err")[0]["reason"] == "RuntimeError"


@pytest.mark.parametrize("state,questions", [(object(), None), (STATE, {"q": {"type": "bogus"}}),
    (STATE, {"q": {"type": "choice", "instructions": "x", "criteria": ["a", "b"]}})])
def test_garbage_inputs_never_raise(env, state, questions):
    assert judge(state, questions, lane="junk") is None


def test_missing_key_returns_none(env, monkeypatch):
    monkeypatch.setattr(adapter, "resolve_key", lambda: None)
    assert judge(STATE, QUESTIONS, lane="nokey") is None
    assert rows("nokey")[0]["reason"] == "no_key"


def test_key_resolution_env_first(env):
    assert adapter.resolve_key() == FAKE_KEY


def test_missing_sdk_does_not_prevent_http_contract(env, monkeypatch):
    monkeypatch.setitem(sys.modules, "typesafe_sdk", None)
    install(monkeypatch)
    assert judge(STATE, QUESTIONS, lane="no-sdk") == RESPONSE


def test_current_sdk_noul_and_choice_fields():
    response = types.SimpleNamespace(model="jev-1.13.0", usage={}, scores={},
        choices={"route": types.SimpleNamespace(choice="a", probabilities={"a": .8, "b": .2}, confidence=.7)},
        nouls={"mismatch": types.SimpleNamespace(noul=.9)})
    out = adapter._answers_to_dict(response)
    assert out["answers"]["mismatch"] == {"type": "noul", "noul": .9}
    assert out["answers"]["route"]["choice"] == "a"


def test_houdini_main_thread_refuses(env, monkeypatch):
    monkeypatch.setitem(sys.modules, "hou", types.SimpleNamespace(isUIAvailable=lambda: True))
    assert judge(STATE, QUESTIONS, lane="gui") is None
    assert rows("gui")[0]["result"] == "main_thread_refused"


def test_houdini_worker_thread_allowed(env, monkeypatch):
    monkeypatch.setitem(sys.modules, "hou", types.SimpleNamespace(isUIAvailable=lambda: True))
    install(monkeypatch)
    box = []
    thread = threading.Thread(target=lambda: box.append(judge(STATE, QUESTIONS, lane="worker")))
    thread.start()
    thread.join(2)
    assert box == [RESPONSE]


def test_headless_hou_allowed(env, monkeypatch):
    monkeypatch.setitem(sys.modules, "hou", types.SimpleNamespace(isUIAvailable=lambda: False))
    install(monkeypatch)
    assert judge(STATE, QUESTIONS, lane="headless")


@pytest.mark.parametrize("policy", ["unapproved", "local_only"])
def test_project_policy_blocks_before_transport(env, policy):
    access.save_policy("local_only" if policy == "local_only" else "ask")
    assert judge(STATE, QUESTIONS, lane="denied") is None
    assert rows("denied")[0]["reason"] == "permission_or_scope"


def test_generation_grant_cannot_authorize_jev(env, monkeypatch):
    from synapse.panel.connections import ConnectionSpec
    grant = access.issue_task_grant(ConnectionSpec("custom", "generator", "https://generator.example/v1"),
                                    key=FAKE_KEY, approved=True)
    calls = install(monkeypatch)
    assert judge(STATE, QUESTIONS, lane="wrong", scope=grant.scope, grant=grant) is None
    assert calls == []


def test_revocation_after_preparation_blocks_actual_send(env, monkeypatch):
    sent = []
    def transport(payload, key, before_send):
        access.save_policy("local_only")
        before_send()
        sent.append(payload)
    monkeypatch.setattr(adapter, "_post", transport)
    assert judge(STATE, QUESTIONS, lane="revoke") is None
    assert sent == []


def test_cancelled_scope_never_sends(env):
    scope = access.capture_scope()
    scope.active = False
    assert judge(STATE, QUESTIONS, lane="cancel", scope=scope) is None


def test_response_after_revocation_is_discarded(env, monkeypatch):
    scope = access.capture_scope()
    def after_send():
        scope.active = False
        return copy.deepcopy(RESPONSE)
    calls = install(monkeypatch, after_send)
    assert judge(STATE, QUESTIONS, lane="late", scope=scope) is None
    assert len(calls) == 1  # It had already been sent; revocation cannot unsend it.
    assert rows("late")[0]["reason"] == "permission_or_scope"
    assert access.recent_attempts()[-1]["result"] == "blocked"


def test_kill_switch_rechecked_at_actual_send(env, monkeypatch):
    sent = []
    def transport(payload, key, before_send):
        monkeypatch.setenv("SYNAPSE_JEV", "off")
        before_send()
        sent.append(payload)
    monkeypatch.setattr(adapter, "_post", transport)
    assert judge(STATE, QUESTIONS, lane="off-before-send") is None
    assert sent == []


@pytest.mark.parametrize("credential", [FAKE_KEY, "jev-1.13.0"])
def test_service_cannot_echo_credential_into_receipt(env, monkeypatch, credential):
    monkeypatch.setenv("TYPESAFE_API_KEY", credential)
    response = copy.deepcopy(RESPONSE)
    response["model"] = credential
    install(monkeypatch, lambda: response)
    assert judge(STATE, QUESTIONS, lane="echo") is None
    assert credential not in adapter.ledger_path("echo").read_text()
    attempt = access.recent_attempts()[-1]
    assert attempt["reported_model"] is None
    assert credential not in json.dumps(attempt)


def test_resolved_credential_redacted_from_all_receipt_labels(env, monkeypatch):
    questions = {FAKE_KEY: QUESTIONS["route"]}
    response = {**RESPONSE, "answers": {FAKE_KEY: RESPONSE["answers"]["route"]}}
    install(monkeypatch, lambda: response)
    receipt = {}
    assert judge(STATE, questions, lane="unit-" + FAKE_KEY, receipt=receipt) is None
    assert FAKE_KEY not in json.dumps(receipt)
    assert FAKE_KEY not in json.dumps(access.recent_attempts()[-1])
    for path in (env / "ledger").iterdir():
        assert FAKE_KEY not in str(path)
        assert FAKE_KEY not in path.read_text()


@pytest.mark.parametrize("model", ["unapproved", "jev-1.13.0/unapproved", "jev-1.13.0\n", "jev", "jev-1", "jev-１.１３.０"])
def test_invalid_requested_model_never_sends(env, model):
    assert judge(STATE, QUESTIONS, lane="fixed-model", model=model) is None
    assert rows("fixed-model")[0]["reason"] == "invalid_request"


def test_explicit_requested_version_preserved_in_spec_and_payload(env, monkeypatch):
    calls = install(monkeypatch)
    assert judge(STATE, QUESTIONS, lane="version-denied", model="jev-1.13.0") is None
    assert calls == []  # Approval for jev-latest is not approval for another ID.
    access.save_policy("ask", (adapter.connection_spec("jev-1.13.0"),))
    assert judge(STATE, QUESTIONS, lane="version", model="jev-1.13.0") == RESPONSE
    assert calls[0]["model"] == "jev-1.13.0"
    assert access.recent_attempts()[-1]["requested_model"] == "jev-1.13.0"
    assert rows("version")[0]["requested_model"] == "jev-1.13.0"


def test_credential_bearing_requested_model_never_sends(env, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "jev-1.13.0")
    assert judge(STATE, QUESTIONS, lane="key-model", model="jev-1.13.0") is None
    assert "jev-1.13.0" not in adapter.ledger_path("key-model").read_text()


@pytest.mark.parametrize("model", ["arbitrary echoed input", "jev-1.13.0/malicious", "jev-1.13.0\n", "jev", "jev-1", "jev-1.13", "jev-latest", "jev-１.１３.０"])
def test_reported_model_must_have_documented_jev_shape(env, monkeypatch, model):
    response = copy.deepcopy(RESPONSE)
    response["model"] = model
    install(monkeypatch, lambda: response)
    assert judge(STATE, QUESTIONS, lane="reported-model") is None
    assert access.recent_attempts()[-1]["reported_model"] is None


@pytest.mark.parametrize("change", ["nan", "unknown", "wrong_winner", "missing", "extra", "old_noul", "weighted_score"])
def test_malformed_answers_fall_back(env, monkeypatch, change):
    response = copy.deepcopy(RESPONSE)
    choice = response["answers"]["route"]
    if change == "nan": choice["confidence"] = float("nan")
    if change == "unknown": choice["choice"] = "execute_python"
    if change == "wrong_winner": choice["choice"] = "b"
    if change == "missing": del response["answers"]["route"]
    if change == "extra": response["answers"]["secret"] = FAKE_KEY
    if change == "old_noul": response["answers"]["mismatch"] = {"type": "noul", "probability": .9}
    if change == "weighted_score": response["answers"]["severity"]["score"] = 0.
    install(monkeypatch, lambda: response)
    assert judge(STATE, QUESTIONS, lane="bad") is None
    assert FAKE_KEY not in adapter.ledger_path("bad").read_text()


def test_fixed_http_destination_model_and_no_redirect_retry(env, monkeypatch):
    seen = []
    monkeypatch.setenv("TYPESAFE_BASE_URL", "https://unapproved.example")
    monkeypatch.setenv("TYPESAFE_DEFAULT_MODEL", "unapproved")
    class Connection:
        def __init__(self, host, **kwargs):
            seen.append((host, kwargs))
        def request(self, method, path, body, headers):
            seen.append((method, path, json.loads(body), headers["Authorization"]))
        def getresponse(self):
            return types.SimpleNamespace(status=302)
        def close(self):
            seen.append("closed")
    monkeypatch.setattr(adapter.http.client, "HTTPSConnection", Connection)
    monkeypatch.setattr(adapter, "_post", REAL_POST)
    assert judge(STATE, QUESTIONS, lane="redirect") is None
    assert seen[0][0] == "api.typesafe.ai" and seen[0][1]["timeout"] == .8
    assert seen[0][1]["context"].check_hostname
    assert seen[1][:2] == ("POST", "/v1/systemone")
    assert seen[1][2]["model"] == "jev-latest"
    assert len(seen) == 3


def test_http_response_size_is_bounded(monkeypatch):
    reads = []
    class Connection:
        def __init__(self, *args, **kwargs): pass
        def request(self, *args, **kwargs): pass
        def getresponse(self):
            def read(size):
                reads.append(size)
                return b"x" * size
            return types.SimpleNamespace(status=200, read=read)
        def close(self): pass
    monkeypatch.setattr(adapter.http.client, "HTTPSConnection", Connection)
    with pytest.raises(ValueError, match="response_too_large"):
        REAL_POST(b"{}", "synthetic", lambda: None)
    assert reads == [adapter.MAX_RESPONSE_BYTES + 1]


@pytest.mark.parametrize("raw", [b"not json", b'{"model":"a","model":"b"}', b'{"value":NaN}'])
def test_bad_json_rejected_without_retry(monkeypatch, raw):
    calls = []
    class Connection:
        def __init__(self, *args, **kwargs): pass
        def request(self, *args, **kwargs): calls.append(1)
        def getresponse(self): return types.SimpleNamespace(status=200, read=lambda n: raw)
        def close(self): pass
    monkeypatch.setattr(adapter.http.client, "HTTPSConnection", Connection)
    with pytest.raises(ValueError):
        REAL_POST(b"{}", "synthetic", lambda: None)
    assert len(calls) == 1


def test_package_does_not_import_build_time_tools():
    from pathlib import Path
    for path in Path(adapter.__file__).parent.glob("*.py"):
        assert "harness" not in path.read_text(encoding="utf-8")
