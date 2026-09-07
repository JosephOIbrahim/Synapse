"""Session consent reuses explicit panel permission, never an ambient send rule."""
import importlib
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from synapse import model_access as access
from synapse.panel.connections import ConnectionFacts, ConnectionSpec


@pytest.fixture(autouse=True)
def isolated_session(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "rules.json"))
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(tmp_path / "panel.json"))
    state = types.ModuleType(access._SESSION_ANCHOR)
    state.schema = 1
    state.owner_pid = os.getpid()
    state.lock = threading.RLock()
    state.approvals = {}
    state.expired = False
    monkeypatch.setattr(access, "_SESSION_STATE", state)
    monkeypatch.setitem(sys.modules, access._SESSION_ANCHOR, state)

    def no_network(*args, **kwargs):
        raise AssertionError("Session tests must not contact a model or service")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    return state


def remote(model="studio-a"):
    return ConnectionSpec("custom", model, "https://models.example/v1/chat/completions")


def allow(spec=None, **kwargs):
    return access.issue_session_grant(spec or remote(), approved=True, **kwargs)


def test_next_prompt_gets_new_child_and_original_task_cannot_be_borrowed():
    spec = remote()
    first_scope = access.capture_scope()
    first = allow(spec, key="synthetic", scope=first_scope)
    assert access.require_access(spec, key="synthetic", grant=first, scope=first_scope) == "session"
    # Ordinary completion/Stop still retires only the original task.
    first.release()
    first_scope.active = False
    second_scope = access.capture_scope()
    second = access.session_task_grant(spec, key="synthetic", scope=second_scope)
    assert second is not None and second is not first
    assert second.scope is second_scope and second.scope is not first_scope
    assert second.scope.task_id != first_scope.task_id
    assert access.require_access(spec, key="synthetic", grant=second, scope=second_scope) == "session"
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(spec, key="synthetic", grant=first, scope=first_scope)
    with pytest.raises(access.ModelAccessDenied, match="another task"):
        access.require_access(spec, key="synthetic", grant=second, scope=access.capture_scope())


def test_task_only_and_project_permission_do_not_create_session_consent():
    spec = remote()
    task = access.issue_task_grant(spec, approved=True)
    assert access.require_access(spec, grant=task) == "task"
    assert not access.has_session_approval(spec)
    assert access.session_task_grant(spec) is None
    access.save_policy("ask", (spec,))
    assert access.require_access(spec) == "project"
    assert access.session_task_grant(spec) is None
    assert not access.has_session_approval(spec)


@pytest.mark.parametrize("approved", [False, None, 1, "yes", {"approved": True}])
def test_session_requires_literal_explicit_approval(approved):
    with pytest.raises(access.ModelAccessDenied, match="explicit"):
        access.issue_session_grant(remote(), approved=approved)
    assert not access.has_session_approval(remote())


@pytest.mark.parametrize("changed", ["provider", "model", "endpoint", "key"])
def test_changed_recipient_does_not_inherit_session(changed):
    spec = remote()
    child = allow(spec, key="synthetic")
    other = replace(spec, **{changed: {"provider": "ollama", "model": "other-model",
                    "endpoint": "https://other.example/v1/chat/completions"}[changed]}) if changed != "key" else spec
    key = "different" if changed == "key" else "synthetic"
    assert not access.has_session_approval(other, key=key)
    assert access.session_task_grant(other, key=key) is None
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(other, key=key, grant=child)
    assert access.has_session_approval(spec, key="synthetic")


@pytest.mark.parametrize("change", ["policy", "project", "cancelled", "inactive"])
def test_change_during_modal_cannot_publish_consent(change, tmp_path, monkeypatch):
    scope = access.capture_scope()
    if change == "policy":
        access.save_policy("ask")
    elif change == "project":
        monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "different.json"))
    elif change == "cancelled":
        scope.cancelled = lambda: True
    else:
        scope.active = False
    with pytest.raises(access.ModelAccessDenied):
        allow(scope=scope)
    assert not access.has_session_approval(remote())
    assert access.session_task_grant(remote()) is None


def test_project_a_b_a_never_revives_prior_session(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNAPSE_MODEL_POLICY")
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    access.select_project_policy(a)
    child = allow()
    access.select_project_policy(b)
    access.select_project_policy(a)  # No intervening model request is required.
    assert access.session_task_grant(remote()) is None
    assert not access.has_session_approval(remote())
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(remote(), grant=child)


def test_observed_deployment_project_switch_retires_parent(tmp_path, monkeypatch):
    original = os.environ["SYNAPSE_MODEL_POLICY"]
    child = allow()
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "elsewhere.json"))
    assert access.session_task_grant(remote()) is None
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", original)
    assert access.session_task_grant(remote()) is None
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(remote(), grant=child)


def test_saving_identical_rules_still_retires_existing_session():
    access.save_policy("ask")
    child = allow()
    access.save_policy("ask")
    assert not access.has_session_approval(remote())
    assert access.session_task_grant(remote()) is None
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(remote(), grant=child)


def test_unrelated_rules_file_save_does_not_revoke_current_project(tmp_path):
    child = allow()
    access.save_policy("local_only", path=tmp_path / "unused.json")
    assert access.has_session_approval(remote())
    assert access.require_access(remote(), grant=child) == "session"


def test_revoke_all_retires_live_children_without_borrowing_saved_permissions():
    spec = remote()
    access.save_policy("ask", (spec,))
    first = allow(spec)
    second = access.session_task_grant(spec)
    third = allow(remote("other-model"))
    assert access.revoke_session_approvals() == 2
    assert access.revoke_session_approvals() == 0
    for connection, child in ((spec, first), (spec, second), (remote("other-model"), third)):
        with pytest.raises(access.ModelAccessDenied, match="Session permission ended"):
            access.require_access(connection, grant=child)
    assert access.require_access(spec) == "project"
    assert access.session_task_grant(spec) is None


def test_new_approval_after_revoke_cannot_revive_old_children():
    old = allow()
    access.revoke_session_approvals()
    current = allow()
    assert access.require_access(remote(), grant=current) == "session"
    with pytest.raises(access.ModelAccessDenied, match="Session permission ended"):
        access.require_access(remote(), grant=old)


def test_session_is_never_ambient_background_or_handoff_permission():
    from synapse.request_handoff import accepted_child_scope, export_scope, import_scope
    scope = access.capture_scope()
    child = allow(scope=scope)
    with access.request_scope(scope):
        queued = accepted_child_scope()
        exported = export_scope()
    imported = import_scope(exported)
    for original in (scope, queued, imported):
        with pytest.raises(access.ModelAccessDenied, match="needs permission"):
            access.require_access(remote(), scope=original)
    with pytest.raises(access.ModelAccessDenied, match="another task"):
        access.require_access(remote(), grant=child, scope=queued)
    assert access.require_access(remote(), grant=child, scope=scope) == "session"


def test_session_cannot_enable_guarded_sdk_background_lane():
    calls = []
    http = access.sdk_http_module()
    with access.make_anthropic_client(api_key="synthetic", base_url="https://sdk.example",
            transport=http.MockTransport(lambda request: calls.append(request))) as client:
        spec = access.sdk_spec(client, "studio-a")
        allow(spec, key="synthetic")
        with pytest.raises(access.ModelAccessDenied, match="needs permission"):
            access.guarded_create(client, lane="session-negative", model=spec.model,
                                  max_tokens=2, messages=[{"role": "user", "content": "private sentinel"}])
        assert calls == []


def _stream_provider(child):
    return types.SimpleNamespace(id="custom", model_identity="studio-a",
        _get_endpoint=lambda: ("https", "models.example", "/v1/chat/completions"),
        _model_grant=child, _model_scope=child.scope, _connection_facts=None)


def test_last_send_rechecks_parent_after_payload_preparation():
    child = allow(key="synthetic")
    provider = _stream_provider(child)
    sent = []

    @access.guarded_stream
    def send(provider, **kwargs):
        payload = json.dumps({"model": "studio-a"}, sort_keys=True)
        access.revoke_session_approvals()  # Between outer permission check and bytes.
        access.before_stream_send(provider, kwargs["api_key"], payload, remote().endpoint)
        sent.append(payload)
        provider._stream_complete = True

    with pytest.raises(access.ModelAccessDenied, match="Session permission ended"):
        send(provider, api_key="synthetic", should_abort=lambda: False, messages=[], tools=[], system="")
    assert sent == []
    assert access.recent_attempts()[-1]["result"] == "blocked"


def test_same_task_tool_followup_is_allowed_until_session_revoked():
    child = allow(key="synthetic")
    provider = _stream_provider(child)
    sent = []

    @access.guarded_stream
    def send(provider, **kwargs):
        access.before_stream_send(provider, kwargs["api_key"], '{"model":"studio-a"}', remote().endpoint)
        sent.append("request")
        provider._stream_complete = True

    args = dict(api_key="synthetic", should_abort=lambda: False, messages=[], tools=[], system="")
    send(provider, **args)
    send(provider, **args)
    access.revoke_session_approvals()
    with pytest.raises(access.ModelAccessDenied):
        send(provider, **args)
    assert sent == ["request", "request"]


@pytest.mark.parametrize("key", [12, b"not-text", "bad\nheader", "bad\x00header", "caf\u00e9"])
def test_bad_key_never_creates_parent(key):
    with pytest.raises(access.ModelAccessDenied):
        allow(key=key)
    assert access.revoke_session_approvals() == 0


def test_remote_plain_http_with_credentials_never_creates_parent():
    spec = replace(remote(), endpoint="http://models.example/v1/chat/completions")
    with pytest.raises(access.ModelAccessDenied, match="HTTPS"):
        allow(spec, key="synthetic")
    assert access.revoke_session_approvals() == 0


def test_local_only_and_malformed_policy_never_become_session_approval():
    access.save_policy("local_only")
    with pytest.raises(access.ModelAccessDenied, match="Local only"):
        allow()
    access.policy_path().write_text('{"version":1,"mode":"ask","mode":"local_only","approved_models":[]}', encoding="utf-8")
    with pytest.raises(access.ModelAccessDenied):
        allow()
    assert access.revoke_session_approvals() == 0


@pytest.mark.parametrize("supply_scope", [False, True])
def test_corrupt_selector_retires_existing_consent_without_repairing_it(monkeypatch, tmp_path, supply_scope):
    from synapse.panel import settings
    monkeypatch.delenv("SYNAPSE_MODEL_POLICY")
    access.select_project_policy(tmp_path / "project.json")
    child = allow()
    original = settings.settings_path().read_bytes()
    settings.settings_path().write_text('{"model_policy_path":null}', encoding="utf-8")
    assert not access.has_session_approval(remote(), scope=child.scope if supply_scope else None)
    settings.settings_path().write_bytes(original)
    assert access.session_task_grant(remote()) is None
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(remote(), grant=child)


def test_mismatched_or_opaque_facts_never_publish_session_consent():
    for facts in ({"local": True}, ConnectionFacts(remote("other-model"))):
        with pytest.raises(access.ModelAccessDenied, match="connection changed"):
            allow(facts=facts)
    assert access.revoke_session_approvals() == 0


def test_session_local_evidence_cannot_turn_into_unverified_permission():
    spec = ConnectionSpec("ollama", "local-a", "http://127.0.0.1:11434/v1/chat/completions")
    facts = ConnectionFacts(spec, {"size": 2000, "details": {"format": "gguf"}}, time.time())
    child = allow(spec, facts=facts)
    stale = replace(facts, checked_at=time.time() - 181)
    assert access.session_task_grant(spec, facts=stale) is None
    assert not access.has_session_approval(spec)
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(spec, facts=facts, grant=child)


def test_parent_memory_is_bounded_and_contains_only_identity_and_digest(isolated_session, tmp_path):
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    for number in range(64):
        allow(remote("model-%d" % number), key="synthetic-secret")
    with pytest.raises(access.ModelAccessDenied, match="Too many"):
        allow(remote("one-too-many"), key="synthetic-secret")
    assert len(isolated_session.approvals) == 64
    assert "synthetic-secret" not in repr(isolated_session.approvals)
    assert all(type(identity) is tuple and all(type(x) is str for x in identity[:6])
               and type(identity[-1]) is bytes and len(identity[-1]) == 32
               and parent == {"active": True, "local": False}
               for identity, parent in isolated_session.approvals.items())
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert after == before  # No policy, settings, secret or session file was written.


def test_two_panels_racing_reuse_share_one_revocable_parent():
    allow(key="synthetic")
    barrier = threading.Barrier(3)

    def panel_submit():
        scope = access.capture_scope()
        barrier.wait(timeout=3)
        return access.session_task_grant(remote(), key="synthetic", scope=scope)

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(panel_submit) for _ in range(2)]
        barrier.wait(timeout=3)
        children = [future.result(timeout=3) for future in pending]
    assert children[0].scope is not children[1].scope
    assert access.revoke_session_approvals() == 1
    for child in children:
        with pytest.raises(access.ModelAccessDenied):
            access.require_access(remote(), key="synthetic", grant=child)


def test_ordinary_module_reload_reuses_primitive_identity_and_new_module_revokes_old_child():
    import synapse
    import synapse.panel
    old_child = allow(key="synthetic")
    saved = {name: sys.modules[name] for name in ("synapse.model_access", "synapse.panel.connections")}
    try:
        for name in saved:
            del sys.modules[name]
        fresh = importlib.import_module("synapse.model_access")
        assert fresh is not access and fresh.ConnectionSpec is not ConnectionSpec
        spec = fresh.ConnectionSpec("custom", "studio-a", remote().endpoint)
        scope = fresh.capture_scope()
        assert fresh.has_session_approval(spec, key="synthetic", scope=scope)
        child = fresh.session_task_grant(spec, key="synthetic", scope=scope)
        assert child is not None and child.scope is scope
        assert fresh.require_access(spec, key="synthetic", grant=child, scope=scope) == "session"
        assert fresh.revoke_session_approvals() == 1
        with pytest.raises(access.ModelAccessDenied, match="Session permission ended"):
            access.require_access(remote(), key="synthetic", grant=old_child)
        with pytest.raises(fresh.ModelAccessDenied):
            fresh.require_access(spec, key="synthetic", grant=child, scope=scope)
    finally:
        sys.modules.update(saved)
        synapse.model_access = saved["synapse.model_access"]
        synapse.panel.connections = saved["synapse.panel.connections"]


@pytest.mark.parametrize("attribute,value", [("schema", 2), ("schema", True), ("owner_pid", -1)])
def test_incompatible_or_inherited_authority_expires_without_resurrection(isolated_session, attribute, value):
    child = allow()
    original = getattr(isolated_session, attribute)
    setattr(isolated_session, attribute, value)
    assert not access.has_session_approval(remote())
    assert access.session_task_grant(remote()) is None
    ordinary = access.issue_task_grant(remote(), approved=True)
    assert access.require_access(remote(), grant=ordinary) == "task"
    with pytest.raises(access.ModelAccessDenied, match="runtime change"):
        access.require_access(remote(), grant=child)
    setattr(isolated_session, attribute, original)
    assert not access.has_session_approval(remote())
    with pytest.raises(access.ModelAccessDenied):
        allow()
    assert isolated_session.approvals == {}


def test_unavailable_session_state_never_turns_invalid_task_into_fresh_consent(isolated_session):
    scope = access.capture_scope()
    scope.active = False
    isolated_session.schema = 2
    with pytest.raises(access.ModelAccessDenied, match="changed"):
        access.session_task_grant(remote(), scope=scope)
