"""Offline selection-ranking boundary tests; no provider or live scene calls."""
from dataclasses import FrozenInstanceError
import importlib
import json
from pathlib import Path
import socket
import sys
import threading
import time

import pytest

from synapse import model_access as access
from synapse.jev import adapter
from synapse.jev import selection_suggestions as suggestions
from synapse.jev.selection_actions import ACTIONS, VERSION, prepare_prompt, questions

IDS = [item.id for item in ACTIONS]


def response(levels=None, *, confidence=0.):
    levels = levels or {}
    return {"model": "jev-1.13.0", "usage": {"input_tokens": 120, "output_tokens": 5},
            "answers": {action.id: {
                "type": "score", "score": levels.get(action.id, 0), "confidence": confidence,
                "probabilities": {str(i): float(i == levels.get(action.id, 0)) for i in range(4)},
            } for action in ACTIONS}}


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "policy.json"))
    monkeypatch.setenv("SYNAPSE_JEV_LEDGER_DIR", str(tmp_path / "ledger"))
    monkeypatch.setenv("TYPESAFE_API_KEY", "tsk-offline-test-key")
    monkeypatch.delenv("SYNAPSE_JEV", raising=False)
    monkeypatch.setitem(sys.modules, "hou", None)
    def forbidden(*args, **kwargs):
        raise AssertionError("Live network is prohibited in these tests")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(adapter, "_post", forbidden)
    access.save_policy("ask", (adapter.connection_spec(),))
    return tmp_path


def settle():
    assert suggestions._JOBS.slot.acquire(timeout=3), "suggestion background job did not finish"
    suggestions._JOBS.slot.release()


def rank(text="Find the broken wire.", *, generation=1, service=None, scope=None, **kwargs):
    service = service or suggestions.SuggestionService()
    scope = scope or access.capture_scope()
    result = service.request(text, generation_key=generation, scope=scope, enabled=True, **kwargs)
    return service, scope, result


def ids(view):
    return [item["id"] for item in view["ordered_actions"]]


def test_public_catalog_is_fixed_local_and_does_not_generate_text():
    assert set(IDS) == {"explain_selection", "check_wiring", "fix_selection",
                        "optimize_selection", "inspect_materials"}
    assert len(IDS) == len(set(IDS)) == 5
    for action in ACTIONS:
        assert prepare_prompt(action.id) == action.prompt
        assert isinstance(action.prompt, str) and action.prompt
        assert "stop and ask for a new inspection" in action.prompt
        assert "do not widen to the scene" in action.prompt
        assert "whole scene if nothing" not in action.prompt
    with pytest.raises(KeyError):
        prepare_prompt("execute_python")
    with pytest.raises(FrozenInstanceError):
        ACTIONS[0].prompt = "Invented model output"
    assert "without changing" in prepare_prompt("check_wiring")
    assert "without changing" in prepare_prompt("inspect_materials")
    assert "without measuring" in prepare_prompt("optimize_selection")
    assert "do not apply repairs" in prepare_prompt("fix_selection")


def test_comparable_questions_are_independent_and_fresh():
    batch = questions()
    assert set(batch) == set(IDS)
    assert adapter._questions_valid(batch)
    for action in ACTIONS:
        question = batch[action.id]
        assert question["type"] == "score"
        assert action.description in question["instructions"]
        assert "`artist_request`" in question["instructions"]
        assert question["criteria"] == batch[IDS[0]]["criteria"]
        assert len(question["criteria"]) == 4
    batch[IDS[0]]["criteria"][0] = "Corrupted caller copy"
    assert "Corrupted" not in questions()[IDS[0]]["criteria"][0]


@pytest.mark.parametrize("text,reason", [
    ("", "empty_request"),
    ("x" * 4097, "request_too_large"),
    ([{"type": "image", "data": "private"}], "non_text_request"),
    ("import hou\nhou.node('private')", "private_or_code_request"),
    ("Use my password private", "private_or_code_request"),
    ('{"node": "private"}', "private_or_code_request"),
    ("Look at /stage/privateNode", "private_or_scene_request"),
    ("Read C:\\private\\scene.hip", "private_or_scene_request"),
    ("Read \\\\private\\share", "private_or_scene_request"),
    ("Read /home/private/scene.hip", "private_or_scene_request"),
    ("Inspect /obj", "private_or_scene_request"),
])
def test_projection_rejects_attachments_code_credentials_paths_and_large_input(text, reason):
    assert suggestions._project(text) == (None, reason)


def test_projection_has_only_latest_plain_text_and_drops_panel_context():
    state, error = suggestions._project("[Context: /private/scene/node]\nExplain how this works.")
    assert error is None
    assert state == {"artist_request": "Explain how this works."}


def test_off_is_inert_and_never_resolves_keys_or_starts_threads(environment, monkeypatch):
    monkeypatch.setattr(adapter, "resolve_key", lambda: pytest.fail("Off read credentials"))
    monkeypatch.setattr(adapter, "judge", lambda *a, **k: pytest.fail("Off started inference"))
    service = suggestions.SuggestionService()
    view = service.request("Explain this", generation_key=1, scope=access.capture_scope(), enabled=False)
    assert view["status"] == "disabled" and view["reason"] == "off"
    assert ids(view) == IDS
    assert not (environment / "ledger").exists()


def test_environment_off_overrides_explicit_active_preference(environment, monkeypatch):
    monkeypatch.setenv("SYNAPSE_JEV", "off")
    _, _, view = rank()
    assert view["status"] == "disabled"


def test_missing_key_keeps_useful_default_without_transport(environment, monkeypatch):
    monkeypatch.setattr(adapter, "resolve_key", lambda: None)
    service, _, _ = rank()
    settle()
    view = service.snapshot(1)
    assert view["reason"] == "no_key" and ids(view) == IDS


def test_one_active_batch_has_fixed_state_endpoint_model_and_real_permission(environment, monkeypatch):
    calls = []
    def post(payload, key, before_send):
        before_send()
        calls.append(json.loads(payload))
        return response({"check_wiring": 3, "fix_selection": 2})
    monkeypatch.setattr(adapter, "_post", post)
    service, scope, _ = rank("Trace which socket should connect.")
    settle()
    view = service.snapshot(1)
    assert view["source"] == "jev" and ids(view)[0] == "check_wiring"
    assert len(calls) == 1
    assert calls[0]["model"] == adapter.DEFAULT_MODEL
    assert calls[0]["state"] == {"artist_request": "Trace which socket should connect."}
    assert calls[0]["questions"] == questions()
    events = [item for item in access.recent_attempts() if item["task_id"] == scope.task_id]
    assert len(events) == 1 and events[0]["endpoint"] == adapter.ENDPOINT
    transport = json.loads((environment / "ledger/selection-action-transport.jsonl").read_text().splitlines()[-1])
    assert transport["mode"] == "on" and transport["requested_model"] == adapter.DEFAULT_MODEL


def test_highest_score_first_and_zero_confidence_does_not_remove_actions(environment, monkeypatch):
    monkeypatch.setattr(adapter, "judge", lambda *a, **k: response(
        {"fix_selection": 3, "check_wiring": 2, "explain_selection": 1}, confidence=0.))
    service, _, _ = rank()
    settle()
    view = service.snapshot(1)
    assert ids(view) == ["fix_selection", "check_wiring", "explain_selection",
                         "optimize_selection", "inspect_materials"]
    assert [item["score"] for item in view["ordered_actions"]] == [3, 2, 1, 0, 0]
    assert set(view["ordered_actions"][0]) == {"id", "score"}


def test_all_zero_scores_keep_all_actions_in_public_order(environment, monkeypatch):
    monkeypatch.setattr(adapter, "judge", lambda *a, **k: response())
    service, _, _ = rank("Something unrelated.")
    settle()
    assert ids(service.snapshot(1)) == IDS
    assert service.snapshot(1)["source"] == "jev"


@pytest.mark.parametrize("mutation", ["missing", "extra", "unknown_id", "nonfinite", "weighted", "wrong_type"])
def test_invalid_batch_cannot_publish_ranked_actions(environment, monkeypatch, mutation):
    result = response()
    if mutation == "missing":
        del result["answers"][IDS[0]]
    elif mutation in ("extra", "unknown_id"):
        result["answers"]["execute_python"] = result["answers"][IDS[0]]
        if mutation == "unknown_id":
            del result["answers"][IDS[0]]
    elif mutation == "nonfinite":
        result["answers"][IDS[0]]["score"] = float("nan")
    elif mutation == "weighted":
        result["answers"][IDS[0]]["score"] = 3
    else:
        result["answers"][IDS[0]]["type"] = "choice"
    monkeypatch.setattr(adapter, "judge", lambda *a, **k: result)
    service, _, _ = rank()
    settle()
    view = service.snapshot(1)
    assert view["source"] == "default" and view["reason"] == "invalid_response"
    assert ids(view) == IDS and all(item["score"] is None for item in view["ordered_actions"])


def test_duplicate_pending_and_completed_input_runs_only_once(environment, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls = []
    def judge(*args, **kwargs):
        calls.append(args)
        entered.set()
        assert release.wait(3)
        return response({"fix_selection": 3})
    monkeypatch.setattr(adapter, "judge", judge)
    before = time.perf_counter()
    service, scope, view = rank()
    try:
        assert time.perf_counter() - before < .5
        assert entered.wait(2) and view["status"] == "pending"
        for generation in range(2, 12):
            service.request("Find the broken wire.", generation_key=generation, scope=scope, enabled=True)
        assert service.snapshot(1)["reason"] == "stale_generation"
        assert len(calls) == 1
    finally:
        release.set()
        settle()
    assert service.snapshot(11)["source"] == "jev"
    service.request(" Find the broken wire. ", generation_key=12, scope=scope, enabled=True)
    assert len(calls) == 1 and service.snapshot(12)["source"] == "jev"
    assert not any(hasattr(service, name) for name in ("wait", "join", "result"))


def test_changed_input_rejects_late_response_and_global_busy_is_useful(environment, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls = []
    def judge(*args, **kwargs):
        calls.append(args)
        entered.set()
        assert release.wait(3)
        return response({"fix_selection": 3})
    monkeypatch.setattr(adapter, "judge", judge)
    service, scope, _ = rank()
    try:
        assert entered.wait(2)
        other, _, view = rank(service=service, scope=scope, text="Explain this setup.", generation=2)
        assert other is service and view["reason"] == "busy" and ids(view) == IDS
        rank(service=service, scope=scope, text="Explain this setup.", generation=2)
        assert len(calls) == 1
    finally:
        release.set()
        settle()
    assert service.snapshot(2)["source"] == "default"
    assert service.snapshot(1)["reason"] == "stale_generation"
    # A later explicit lifecycle may try the new intent, never automatically.
    rank(service=service, text="Explain this setup.", generation=3)
    settle()
    assert len(calls) == 2


def test_cancel_never_releases_shared_scope_or_publishes_late_rank(environment, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def judge(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return response({"fix_selection": 3})
    monkeypatch.setattr(adapter, "judge", judge)
    service, scope, _ = rank()
    try:
        assert entered.wait(2)
        service.cancel()
        assert service.snapshot(1)["status"] == "discarded"
        assert scope.active
    finally:
        release.set()
        settle()
    assert service.snapshot(1)["source"] == "default" and scope.active


@pytest.mark.parametrize("previous", ["cancel", "busy", "unavailable"])
def test_explicit_new_generation_recovers_same_input_after_terminal_fallback(environment, monkeypatch, previous):
    calls = []
    def judge(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1 and previous != "cancel":
            kwargs["receipt"]["reason"] = previous
            return None
        return response({"fix_selection": 3})
    monkeypatch.setattr(adapter, "judge", judge)
    service, scope, _ = rank()
    settle()
    if previous == "cancel":
        service.cancel()
    assert service.snapshot(1)["source"] == "default"
    rank(service=service, scope=scope, generation=1)
    assert len(calls) == 1
    rank(service=service, scope=scope, generation=2)
    settle()
    assert len(calls) == 2 and service.snapshot(2)["source"] == "jev"


def test_cached_ranking_is_discarded_after_project_permission_revocation(environment, monkeypatch):
    monkeypatch.setattr(adapter, "judge", lambda *a, **k: response({"fix_selection": 3}))
    service, _, _ = rank()
    settle()
    assert service.snapshot(1)["source"] == "jev"
    access.save_policy("local_only")
    view = service.snapshot(1)
    assert view["source"] == "default" and view["status"] == "discarded"
    assert ids(view) == IDS


def test_cached_ranking_is_discarded_after_session_grant_revocation(environment, monkeypatch):
    monkeypatch.setattr(adapter, "judge", lambda *a, **k: response())
    scope = access.capture_scope()
    grant = access.issue_session_grant(adapter.connection_spec(), key="tsk-offline-test-key",
                                       scope=scope, approved=True)
    service, _, _ = rank(scope=scope, grant=grant)
    settle()
    assert service.snapshot(1)["source"] == "jev"
    access.revoke_session_approvals()
    assert service.snapshot(1)["source"] == "default"


def test_cached_result_rechecks_changed_abort_callback_and_off(environment, monkeypatch):
    monkeypatch.setattr(adapter, "judge", lambda *a, **k: response())
    service, scope, _ = rank()
    settle()
    assert service.snapshot(1)["source"] == "jev"
    _, _, view = rank(service=service, scope=scope, generation=2, should_abort=lambda: True)
    assert view["source"] == "default" and view["status"] == "discarded"
    service.request("Find the broken wire.", generation_key=3, scope=scope, enabled=False)
    assert service.snapshot(3)["status"] == "disabled"


def test_cached_result_rechecks_rotated_key_for_exact_grant(environment, monkeypatch):
    monkeypatch.setattr(adapter, "judge", lambda *a, **k: response())
    scope = access.capture_scope()
    grant = access.issue_task_grant(adapter.connection_spec(), key="tsk-offline-test-key",
                                    scope=scope, approved=True)
    service, _, _ = rank(scope=scope, grant=grant)
    settle()
    assert service.snapshot(1)["source"] == "jev"
    monkeypatch.setenv("TYPESAFE_API_KEY", "tsk-different-offline-key")
    assert service.snapshot(1)["source"] == "default"


def test_real_transport_discards_response_after_scope_is_cancelled(environment, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def post(payload, key, before_send):
        before_send()
        entered.set()
        assert release.wait(3)
        return response()
    monkeypatch.setattr(adapter, "_post", post)
    service, scope, _ = rank()
    try:
        assert entered.wait(2)
        scope.active = False
    finally:
        release.set()
        settle()
    assert service.snapshot(1)["source"] == "default"


@pytest.mark.parametrize("policy", ["ask", "local_only"])
def test_missing_exact_permission_never_posts(environment, policy):
    access.save_policy(policy)
    service, _, _ = rank()
    settle()
    view = service.snapshot(1)
    assert view["source"] == "default" and view["reason"] == "permission_or_scope"


def test_timeout_retains_actual_transport_capacity_for_next_job(environment, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls = []
    def post(payload, key, before_send):
        before_send()
        calls.append(payload)
        entered.set()
        assert release.wait(3)
        return response()
    monkeypatch.setattr(adapter, "_post", post)
    monkeypatch.setattr(adapter, "TIMEOUT_S", .02)
    first, _, _ = rank()
    try:
        assert entered.wait(2)
        settle()
        assert first.snapshot(1)["reason"] == "deadline"
        second, _, _ = rank("Explain this setup.")
        settle()
        assert second.snapshot(1)["reason"] == "busy"
        assert len(calls) == 1
    finally:
        release.set()
        assert adapter._CAPACITY.slot.acquire(timeout=3)
        adapter._CAPACITY.slot.release()


def test_global_service_bound_survives_module_reload(environment, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def judge(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return response()
    monkeypatch.setattr(adapter, "judge", judge)
    first, _, _ = rank()
    try:
        assert entered.wait(2)
        old_jobs = suggestions._JOBS
        importlib.reload(suggestions)
        assert suggestions._JOBS is old_jobs
        _, _, view = rank()
        assert view["reason"] == "busy"
    finally:
        release.set()
        settle()
    assert first.snapshot(1)["source"] == "jev"


def test_snapshots_are_copies_and_old_generations_cannot_replace_current(environment, monkeypatch):
    monkeypatch.setattr(adapter, "judge", lambda *a, **k: response())
    service, scope, _ = rank(generation=2)
    settle()
    view = service.snapshot(2)
    view["ordered_actions"][0]["id"] = "execute_python"
    assert ids(service.snapshot(2)) == IDS
    _, _, stale = rank(service=service, scope=scope, generation=1, text="stale text")
    assert stale["reason"] == "stale_generation" and service.snapshot(2)["source"] == "jev"
    assert service.snapshot(True)["reason"] == "invalid_generation"


def test_receipts_contain_no_intent_key_or_raw_model_text(environment, monkeypatch):
    private_text = "Diagnose the mysterious azure triangle."
    def post(payload, key, before_send):
        before_send()
        result = response({"fix_selection": 3})
        result["raw_message"] = private_text + key
        return result
    monkeypatch.setattr(adapter, "_post", post)
    service, _, _ = rank(private_text, generation=7654321)
    settle()
    assert service.snapshot(7654321)["source"] == "jev"
    receipt_text = "\n".join(p.read_text() for p in (environment / "ledger").glob("*.jsonl"))
    assert private_text not in receipt_text and "tsk-offline-test-key" not in receipt_text
    assert "7654321" not in receipt_text and "raw_message" not in receipt_text


def test_thread_start_failure_releases_service_capacity(environment, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(threading.Thread, "start", lambda _self: (_ for _ in ()).throw(RuntimeError()))
        _, _, view = rank()
        assert view["reason"] == "thread_start"
    settle()


def test_offline_evaluation_cases_cover_catalog_without_claiming_accuracy():
    fixture = Path(__file__).parent / "fixtures/jev_selection_actions_v1.json"
    data = json.loads(fixture.read_text())
    assert data["version"] == VERSION
    assert data["model_accuracy"] == "UNKNOWN: no live model evaluation authorized"
    expected = set()
    for case in data["cases"]:
        assert set(case["acceptable_first"]).issubset(IDS)
        expected.update(case["acceptable_first"])
        if case.get("projection_reason"):
            assert suggestions._project(case["request"])[1] == case["projection_reason"]
    assert expected == set(IDS)
