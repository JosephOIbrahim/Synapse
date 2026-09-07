"""Policy authorization must bite before a request can leave the workstation."""
import json
import time
from dataclasses import replace
from unittest.mock import Mock

import pytest

from synapse import model_access as access
from synapse.panel.connections import ConnectionFacts, ConnectionSpec


@pytest.fixture
def policy_file(tmp_path, monkeypatch):
    path = tmp_path / "project" / ".synapse" / "model_access.json"
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(path))
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(tmp_path / "panel.json"))
    return path


def remote(model="studio-a"):
    return ConnectionSpec("custom", model, "https://models.example/v1/chat/completions")


def local_facts(model="studio-local"):
    spec = ConnectionSpec("ollama", model, "http://127.0.0.1:11434/v1/chat/completions")
    return ConnectionFacts(spec, {"size": 2000, "details": {"format": "gguf"}}, time.time())


def test_missing_policy_requires_remote_permission(policy_file):
    policy = access.load_policy()
    assert policy.mode == "ask" and not policy.approved_models and policy.error is None
    with pytest.raises(access.ModelAccessDenied, match="permission"):
        access.require_access(remote())
    assert not policy_file.exists()


@pytest.mark.parametrize("content", ["{", "[]", '{"version": 1}',
    '{"version": 1, "mode": "allow", "approved_models": []}',
    '{"version": 1, "mode": "ask", "approved_models": [{}]}',
    '{"version": 1, "mode": "ask", "approved_models": [], "unexpected": true}'])
def test_bad_policy_cannot_become_permission(policy_file, content):
    policy_file.parent.mkdir(parents=True)
    policy_file.write_text(content, encoding="utf-8")
    assert access.load_policy().error
    facts = local_facts()
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(facts.spec, facts=facts)


def test_local_only_blocks_remote_even_with_explicit_task_approval(policy_file):
    access.save_policy("local_only", path=policy_file)
    with pytest.raises(access.ModelAccessDenied, match="Local only"):
        access.issue_task_grant(remote(), approved=True)
    facts = local_facts()
    assert access.require_access(facts.spec, facts=facts) == "local"


@pytest.mark.parametrize("kind", ["stale", "future", "relay", "remote_model", "cloud_tag", "remote_endpoint", "missing_weights"])
def test_only_positive_current_local_evidence_passes(policy_file, kind):
    access.save_policy("local_only", path=policy_file)
    facts = local_facts()
    if kind == "stale":
        facts = replace(facts, checked_at=time.time() - 181)
    elif kind == "future":
        facts = replace(facts, checked_at=time.time() + 10)
    elif kind == "relay":
        facts = replace(facts, metadata={**facts.metadata, "remote_host": "https://cloud.example"})
    elif kind == "remote_model":
        facts = replace(facts, metadata={**facts.metadata, "remote_model": "hosted-model"})
    elif kind == "cloud_tag":
        facts = replace(facts, spec=replace(facts.spec, model="studio:cloud"))
    elif kind == "remote_endpoint":
        facts = replace(facts, spec=replace(facts.spec, endpoint="http://10.0.0.2:11434/v1/chat/completions"))
    elif kind == "missing_weights":
        facts = replace(facts, metadata={})
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(facts.spec, facts=facts)


def test_task_grant_is_exact_and_released(policy_file):
    spec = remote()
    grant = access.issue_task_grant(spec, key="synthetic", approved=True)
    assert access.require_access(spec, key="synthetic", grant=grant) == "task"
    assert access.require_access(spec, key="synthetic", grant=grant) == "task"
    for other in (replace(spec, model="different"), replace(spec, provider="ollama"),
                  replace(spec, endpoint="https://elsewhere.example/v1/chat/completions")):
        with pytest.raises(access.ModelAccessDenied):
            access.require_access(other, key="synthetic", grant=grant)
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(spec, key="changed", grant=grant)
    grant.release()
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(spec, key="synthetic", grant=grant)
    assert "synthetic" not in repr(grant)


def test_policy_revision_and_scope_revoke_existing_task(policy_file, monkeypatch):
    spec = remote()
    grant = access.issue_task_grant(spec, approved=True)
    access.save_policy("ask", path=policy_file)
    with pytest.raises(access.ModelAccessDenied, match="changed"):
        access.require_access(spec, grant=grant)
    fresh = access.issue_task_grant(spec, approved=True)
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(policy_file.parent / "other.json"))
    with pytest.raises(access.ModelAccessDenied, match="changed"):
        access.require_access(spec, grant=fresh)


def test_saved_background_permission_names_model_and_service(policy_file):
    spec = remote()
    access.save_policy("ask", approved_models=(spec,), path=policy_file)
    assert access.require_access(spec) == "project"
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(replace(spec, model="another"))
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(replace(spec, endpoint="https://other.example/v1/chat/completions"))
    access.save_policy("local_only", approved_models=(spec,), path=policy_file)
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(spec)


def test_facts_for_another_connection_cannot_authorize(policy_file):
    facts = local_facts()
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(remote(), facts=facts)


def test_boolean_or_dict_is_not_a_task_grant(policy_file):
    for grant in (True, {"approved": True}):
        with pytest.raises(access.ModelAccessDenied):
            access.require_access(remote(), grant=grant)


def test_write_conflict_preserves_newer_policy(policy_file):
    original = access.load_policy()
    access.save_policy("local_only", path=policy_file)
    before = policy_file.read_bytes()
    with pytest.raises(access.ModelAccessDenied, match="changed"):
        access.save_policy("ask", path=policy_file, expected_revision=original.revision)
    assert policy_file.read_bytes() == before


def test_policy_never_persists_key_or_prompt(policy_file):
    spec = remote()
    access.save_policy("ask", approved_models=(spec,), path=policy_file)
    data = json.loads(policy_file.read_text(encoding="utf-8"))
    assert set(data) == {"version", "mode", "approved_models"}
    assert data["approved_models"] == [{"provider": spec.provider, "model": spec.model, "endpoint": spec.endpoint}]


def test_unapproved_sdk_call_has_no_transport_effect(policy_file):
    client = Mock(base_url="https://sdk.example/v1/")
    with pytest.raises(access.ModelAccessDenied):
        access.guarded_create(client, lane="test", model="studio", messages=[{"role": "user", "content": "private sentinel"}])
    client.messages.create.assert_not_called()


def test_sdk_each_call_rechecks_policy_and_retains_reported_model(policy_file):
    spec = ConnectionSpec("claude", "studio", "https://sdk.example/v1/messages")
    access.save_policy("ask", approved_models=(spec,), path=policy_file)
    # The original opaque Mock client is now intentionally refused. Exercise
    # the same two-call contract through a real, controlled SDK transport.
    http = access.sdk_http_module()
    calls = []
    def respond(request):
        calls.append(request)
        return http.Response(200, json={"id": "test", "type": "message", "role": "assistant",
            "model": "studio-actual", "content": [], "stop_reason": "end_turn",
            "usage": {"input_tokens": 7, "output_tokens": 3}})
    with access.make_anthropic_client("synthetic", base_url="https://sdk.example", transport=http.MockTransport(respond)) as client:
        response = access.guarded_create(client, lane="test", model="studio", max_tokens=8, messages=[])
        assert response.model == "studio-actual"
        assert access.recent_attempts()[-1]["reported_model"] == "studio-actual"
        access.save_policy("local_only", path=policy_file)
        with pytest.raises(access.ModelAccessDenied):
            access.guarded_create(client, lane="test", model="studio", max_tokens=8, messages=[])
        assert len(calls) == 1


def test_another_task_cannot_borrow_grant(policy_file):
    spec = remote()
    grant = access.issue_task_grant(spec, approved=True)
    with access.request_scope(access.capture_scope()):
        with pytest.raises(access.ModelAccessDenied, match="another task"):
            access.require_access(spec, grant=grant)


def test_project_selector_survives_preferences_and_cannot_resurrect_task(policy_file, monkeypatch, tmp_path):
    from synapse.panel import settings
    monkeypatch.delenv("SYNAPSE_MODEL_POLICY")
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    access.select_project_policy(a)
    access.save_policy("local_only")
    accepted = access.capture_scope()
    prefs = settings.load_settings()
    prefs["composer_height"] = 181
    assert settings.save_settings(prefs)
    assert access.policy_path() == a and access.load_policy().mode == "local_only"
    access.select_project_policy(b)
    access.select_project_policy(a)
    facts = local_facts()
    with pytest.raises(access.ModelAccessDenied, match="changed"):
        access.require_access(facts.spec, facts=facts, scope=accepted)


def test_duplicate_policy_keys_fail_closed(policy_file):
    policy_file.parent.mkdir(parents=True)
    policy_file.write_text('{"version":1,"mode":"local_only","mode":"ask","approved_models":[]}', encoding="utf-8")
    facts = local_facts()
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(facts.spec, facts=facts)


def test_bad_selector_stays_denied_through_ordinary_save_but_explicit_selection_repairs(policy_file, monkeypatch, tmp_path):
    from synapse.panel import settings
    monkeypatch.delenv("SYNAPSE_MODEL_POLICY")
    settings.settings_path().write_text('{"model_policy_path":"a","model_policy_path":"b"}', encoding="utf-8")
    accepted = access.capture_scope()
    prefs = settings.load_settings()
    prefs["composer_height"] = 200
    assert settings.save_settings(prefs)
    with pytest.raises(access.ModelAccessDenied):
        access.policy_path()
    fixed = tmp_path / "explicit-project.json"
    access.select_project_policy(fixed)
    assert access.policy_path() == fixed
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(remote(), scope=accepted)


def test_invalid_parent_is_controlled_refusal(policy_file, tmp_path):
    parent = tmp_path / "not-a-folder"
    parent.write_text("keep me", encoding="utf-8")
    with pytest.raises(access.ModelAccessDenied):
        access.save_policy("ask", path=parent / "rules.json")
    assert parent.read_text(encoding="utf-8") == "keep me"


def test_oversized_selector_is_not_repaired_by_preference_save(policy_file, monkeypatch):
    from synapse.panel import settings
    monkeypatch.delenv("SYNAPSE_MODEL_POLICY")
    settings.settings_path().write_text(json.dumps({"padding": "x" * 66000}), encoding="utf-8")
    with pytest.raises(access.ModelAccessDenied):
        access.policy_path()
    current = settings.load_settings()
    current["composer_height"] = 99
    assert settings.save_settings(current)
    with pytest.raises(access.ModelAccessDenied):
        access.policy_path()


def test_stale_cosmetic_save_cannot_restore_previous_project(policy_file, monkeypatch, tmp_path):
    from synapse.panel import settings
    monkeypatch.delenv("SYNAPSE_MODEL_POLICY")
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    access.select_project_policy(a)
    access.save_policy("ask", (remote(),))
    accepted = access.capture_scope()
    stale = settings.load_settings()
    access.select_project_policy(b)
    access.save_policy("local_only")
    chosen = settings.load_settings()
    stale["composer_height"] = 221
    assert settings.save_settings(stale)
    assert access.policy_path() == b
    assert settings.load_settings()["model_policy_generation"] == chosen["model_policy_generation"]
    assert settings.load_settings()["composer_height"] == 221
    with pytest.raises(access.ModelAccessDenied, match="changed"):
        access.require_access(remote(), scope=accepted)


def test_project_selector_and_cosmetic_saves_share_writer_lock(policy_file, monkeypatch, tmp_path):
    from synapse.panel import settings
    monkeypatch.delenv("SYNAPSE_MODEL_POLICY")
    access.select_project_policy(tmp_path / "a.json")
    target = settings.settings_path()
    before = target.read_bytes()
    lock = target.with_name(target.name + ".lock")
    lock.write_text("another writer", encoding="utf-8")
    assert not settings.save_settings({"composer_height": 100})
    with pytest.raises(access.ModelAccessDenied, match="could not be saved"):
        access.select_project_policy(tmp_path / "b.json")
    assert target.read_bytes() == before and lock.read_text(encoding="utf-8") == "another writer"
