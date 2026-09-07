"""Process-local journal tests: no Houdini, UI, model, network or persistence."""
import concurrent.futures
import importlib
import json
import sys
import threading
import types

import pytest

from synapse import job_events as events
from synapse.server import render_session as sessions


@pytest.fixture
def journal(monkeypatch):
    anchor = types.ModuleType(events._ANCHOR_NAME)
    anchor.journal = events.JobJournal()
    monkeypatch.setitem(sys.modules, events._ANCHOR_NAME, anchor)
    sessions.reset()
    yield anchor.journal
    sessions.reset()


def test_data_is_detached_bounded_and_never_stringifies_objects(journal):
    class Sensitive:
        def __str__(self):
            raise AssertionError("An arbitrary object was stringified")
    identity = {"session_id": 41, "generation": "scene-generation"}
    job = journal.start("render", "x" * 1000, source="bounded", identity=identity,
                        node="/stage/ROP", scene="first.hip", context_id="generation-a")
    identity["session_id"] = 99
    journal.finish(job, "failed", Sensitive())
    first = journal.snapshot()
    assert len(first["entries"][0]["title"]) <= 120
    assert first["entries"][0]["detail"] == ""
    assert first["entries"][0]["identity"] == {"session_id": 41, "generation": "scene-generation"}
    first["entries"][0]["identity"]["session_id"] = 12
    assert journal.snapshot()["entries"][0]["identity"]["session_id"] == 41
    bad = journal.start("cache", Sensitive(), source="watch", identity={"session_id": 5, "generation": "g", "key": Sensitive()})
    assert journal.snapshot()["entries"][-1]["identity"] is None
    assert journal.snapshot()["entries"][-1]["id"] == bad
    json.dumps(journal.snapshot())


def test_running_capacity_is_hard_and_loss_is_visible():
    journal = events.JobJournal(max_entries=2)
    one = journal.start("render", "one", source="test")
    two = journal.start("render", "two", source="test")
    before = journal.snapshot()
    assert journal.start("render", "overflow", source="test") is None
    full = journal.snapshot()
    assert len(full["entries"]) == 2 and full["dropped"] == 1
    assert full["sequence"] > before["sequence"]
    assert journal.finish(None, "completed") is False
    journal.finish(one, "completed")
    three = journal.start("render", "three", source="test")
    after = journal.snapshot()
    assert {entry["id"] for entry in after["entries"]} == {two, three}
    assert after["dropped"] == 2


def test_terminal_duplicate_conflict_and_no_resurrection(journal):
    journal.set_policy({"desktop": True})
    job = journal.start("render", "render", source="test")
    assert journal.claim_alerts(0) == []
    assert journal.finish(job, "completed", "Returned")
    first = journal.snapshot()
    assert len(journal.claim_alerts(0)) == 1
    assert journal.mark_read([job])
    read = journal.snapshot()
    assert not journal.finish(job, "completed", "Duplicate details")
    assert journal.snapshot() == read
    assert journal.finish(job, "failed", "Contradiction")
    conflict = journal.snapshot()
    assert conflict["entries"][0]["state"] == "unknown"
    assert conflict["entries"][0]["unread"]
    assert conflict["sequence"] > first["sequence"]
    assert len(journal.claim_alerts(0)) == 1
    assert not journal.finish(job, "completed")
    assert not journal.finish(job, "failed")
    assert not journal.finish(job, "running")
    assert journal.snapshot() == conflict
    assert journal.claim_alerts(0) == []


def test_explicit_id_is_never_retargeted(journal):
    job = journal.start("render", "old", source="automatic", scene="a.hip", job_id="owned-id")
    journal.finish(job, "failed")
    before = journal.snapshot()
    assert journal.start("cache", "replacement", source="watch", scene="b.hip", job_id=job) == job
    assert journal.snapshot() == before


def test_note_dedupe_and_clear_keep_metadata_bounded():
    journal = events.JobJournal(max_entries=3)
    job = journal.start("cache", "active", source="test")
    note = journal.note("connection", "Model checked", "Metadata only", dedupe_key="check-1")
    before = journal.snapshot()
    assert journal.note("connection", "Model checked", "Metadata only", dedupe_key="check-1") == note
    assert journal.snapshot() == before
    for index in range(20):
        journal.note("connection", "Model checked", "Metadata only", dedupe_key=f"check-{index + 2}")
    assert len(journal._meta) == len(journal.snapshot()["entries"]) == 3
    assert journal.clear_finished() == 2
    assert list(journal._meta) == [job]
    assert journal.snapshot()["entries"][0]["state"] == "running"
    assert not journal.mark_read()
    assert journal.clear_finished() == 0


def test_shared_policy_initializes_once_and_suppressed_alerts_do_not_replay(journal):
    assert journal.initialize_policy({"desktop": True})["desktop"]
    assert journal.initialize_policy({"quiet": True})["quiet"] is False
    journal.set_policy({"quiet": True, "desktop": 1, "unknown": True})
    assert journal.get_policy() == {"quiet": True, "desktop": True, "completions": True, "connections": True}
    first = journal.note("render", "Done", "Returned", state="completed")
    assert journal.claim_alerts(0) == []
    journal.set_policy({"quiet": False})
    assert journal.claim_alerts(0) == []
    second = journal.note("render", "Failed", "Failed", state="failed")
    assert [entry["id"] for entry in journal.claim_alerts(0)] == [second]
    assert first != second
    policy = journal.get_policy()
    policy["quiet"] = True
    assert journal.get_policy()["quiet"] is False


def test_connection_and_completion_preferences_are_independent(journal):
    journal.set_policy({"desktop": True, "connections": False})
    journal.note("connection", "Bridge stopped", "Locally observed")
    render = journal.note("render", "Returned", "Operation returned", state="completed")
    assert [entry["id"] for entry in journal.claim_alerts(0)] == [render]
    journal.set_policy({"connections": True, "completions": False})
    assert journal.claim_alerts(0) == []
    conn = journal.note("connection", "Model checked", "Generation not tested")
    failed = journal.note("render", "Failed", "Observed failure", state="failed")
    assert [entry["id"] for entry in journal.claim_alerts(0)] == [conn, failed]


def test_claim_is_atomic_across_panels_and_does_not_drop_new_arrival(journal):
    journal.set_policy({"desktop": True})
    cursor = journal.snapshot()["sequence"]
    job = journal.note("render", "Returned", "Returned", state="completed")
    barrier = threading.Barrier(8)
    def claim():
        barrier.wait()
        return journal.claim_alerts(cursor)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: claim(), range(8)))
    assert [entry["id"] for result in results for entry in result] == [job]
    captured = journal.snapshot()["sequence"]
    late = journal.note("connection", "Checked", "Metadata only")
    assert [entry["id"] for entry in journal.claim_alerts(captured)] == [late]
    assert journal.claim_alerts(captured) == []


def test_reloaded_consumer_observes_old_producer_finish(journal, monkeypatch):
    import synapse
    import synapse.server
    old_events, old_sessions = events, sessions
    journal.set_policy({"desktop": True})
    token = old_sessions.start_session({"rop": "/stage/original", "scene": "original.hip"})
    before = journal.snapshot()
    with monkeypatch.context() as refresh:
        # Match the loader's deletion for both relevant synapse.* modules;
        # retain their external process anchor exactly as the real loader does.
        refresh.setattr(synapse, "job_events", old_events)
        refresh.setattr(synapse.server, "render_session", old_sessions)
        refresh.delitem(sys.modules, "synapse.job_events")
        refresh.delitem(sys.modules, "synapse.server.render_session")
        new_events = importlib.import_module("synapse.job_events")
        new_sessions = importlib.import_module("synapse.server.render_session")
        assert new_events is not old_events and new_sessions is not old_sessions
        assert new_events.get_journal() is journal
        assert new_sessions.summary() == []
        assert new_events.get_journal().snapshot() == before
        old_sessions.complete_session(token, {"image_path": "synthetic.exr"})
        assert new_events.get_journal().snapshot()["entries"][0]["state"] == "completed"
        assert len(new_events.get_journal().claim_alerts(0)) == 1
        assert old_events.get_journal().claim_alerts(0) == []


@pytest.mark.parametrize("result,state", [
    ({"image_path": "synthetic.exr"}, "completed"), ({"status": "error", "error": "SECRET"}, "failed"),
    ({"status": "completed", "success": False}, "failed"), ({"status": "cancelled"}, "cancelled"),
    ({"flipbook_fallback": True, "image_path": "preview.jpg"}, "preview"),
    ({"status": "unrecognized", "image_path": "synthetic.exr"}, "unknown"),
    ({"status": "render_in_progress"}, "unknown"), ({}, "unknown"), (None, "unknown"),
])
def test_conservative_render_projection(result, state):
    projected, detail = events.classify_render_result(result)
    assert projected == state
    assert "SECRET" not in detail


def test_unknown_outcome_object_is_not_executed():
    class Opaque:
        def __eq__(self, other):
            raise AssertionError("Arbitrary status equality was invoked")
        def __str__(self):
            raise AssertionError("Arbitrary status stringification was invoked")
    assert events.classify_render_result({"status": Opaque()})[0] == "unknown"
    journal = events.JobJournal()
    job = journal.start("render", "Opaque status", source="test")
    assert journal.finish(job, Opaque())
    assert journal.snapshot()["entries"][0]["state"] == "unknown"


@pytest.mark.parametrize("suppressed", [{"desktop": False}, {"quiet": True}, {"completions": False}])
def test_publication_policy_prevents_enable_before_first_poll_replay(journal, suppressed):
    journal.set_policy({"desktop": True, **suppressed})
    journal.note("render", "Finished while suppressed", "Observed return", state="completed")
    journal.set_policy({"desktop": True, "quiet": False, "completions": True})
    assert journal.claim_alerts(0) == []


@pytest.mark.parametrize("suppressed", [{"desktop": False}, {"quiet": True}, {"completions": False}])
def test_disabling_policy_consumes_pending_alert_before_reenable(journal, suppressed):
    journal.set_policy({"desktop": True})
    journal.note("render", "Pending completion", "Observed return", state="completed")
    journal.set_policy(suppressed)
    journal.set_policy({"desktop": True, "quiet": False, "completions": True})
    assert journal.claim_alerts(0) == []


def test_completion_preference_preserves_failure_unknown_and_cancel_attention(journal):
    journal.set_policy({"desktop": True, "completions": False})
    expected = []
    for state in ("completed", "preview", "failed", "unknown", "cancelled"):
        key = journal.note("render", state, "Source observation", state=state)
        if state in {"failed", "unknown", "cancelled"}:
            expected.append(key)
    assert [entry["id"] for entry in journal.claim_alerts(0)] == expected


def test_constant_note_key_preserves_changed_transitions_only(journal):
    ids = []
    for running in (False, True, False, True):
        title = "Bridge ready" if running else "Bridge stopped"
        state = "info" if running else "failed"
        key = journal.note("connection", title, "Local state", state=state, source="bridge", dedupe_key="local-bridge")
        after = journal.snapshot()
        assert journal.note("connection", title, "Local state", state=state, source="bridge", dedupe_key="local-bridge") == key
        assert journal.snapshot() == after
        ids.append(key)
    assert len(set(ids)) == 4
    assert [entry["state"] for entry in journal.snapshot()["entries"]] == ["failed", "info", "failed", "info"]


@pytest.mark.parametrize("suppressed", [{"desktop": False}, {"quiet": True}, {"completions": False}])
def test_finish_publication_policy_prevents_enable_before_first_poll_replay(journal, suppressed):
    journal.set_policy({"desktop": True})
    job = journal.start("render", "Running", source="test")
    journal.set_policy(suppressed)
    journal.finish(job, "completed", "Returned under suppression")
    journal.set_policy({"desktop": True, "quiet": False, "completions": True})
    assert journal.snapshot()["entries"][0]["unread"]
    assert journal.claim_alerts(0) == []


@pytest.mark.parametrize("disable_before_publication", [False, True])
def test_connection_suppression_is_not_delayed_until_poll(journal, disable_before_publication):
    journal.set_policy({"desktop": True, "connections": not disable_before_publication})
    journal.note("connection", "Changed", "Locally observed", state="failed")
    journal.set_policy({"connections": False})
    journal.set_policy({"connections": True})
    assert journal.claim_alerts(0) == []


def test_suppressed_completion_can_still_raise_new_conflict_attention(journal):
    journal.set_policy({"desktop": True, "completions": False})
    job = journal.start("render", "Render", source="test")
    journal.finish(job, "completed")
    assert journal.claim_alerts(0) == []
    journal.finish(job, "failed")
    assert [(row["id"], row["state"]) for row in journal.claim_alerts(0)] == [(job, "unknown")]
    assert journal.claim_alerts(0) == []


@pytest.mark.parametrize("changed", [
    {"title": "A different model checked"}, {"detail": "Different capability observed"},
    {"source": "another source"}, {"node": "/stage/another"}, {"scene": "another.hip"},
    {"identity": {"session_id": 2, "generation": "a"}}, {"context_id": "another-context"},
])
def test_same_connection_key_keeps_changed_visible_facts(journal, changed):
    facts = dict(title="Model checked", detail="Metadata only", source="model_check",
                 node="/stage/one", scene="first.hip", identity={"session_id": 1, "generation": "a"},
                 context_id="first-context")
    first = journal.note("connection", **facts, dedupe_key="model-check")
    second = journal.note("connection", **(facts | changed), dedupe_key="model-check")
    assert second != first
    after = journal.snapshot()
    assert journal.note("connection", **(facts | changed), dedupe_key="model-check") == second
    assert journal.snapshot() == after


def test_connection_transition_history_has_bounded_dedupe_metadata():
    journal = events.JobJournal(max_entries=3)
    for index in range(40):
        journal.note("connection", "Checked", str(index), dedupe_key="same-key")
    snapshot = journal.snapshot()
    assert len(snapshot["entries"]) == len(journal._meta) == 3
    assert snapshot["dropped"] == 37
    assert [entry["detail"] for entry in snapshot["entries"]] == ["37", "38", "39"]


def test_nonconnection_info_key_retains_first_observation(journal):
    first = journal.note("cache", "Notice", "First observation", dedupe_key="one-notice")
    after = journal.snapshot()
    assert journal.note("cache", "Changed notice", "Another observation", dedupe_key="one-notice") == first
    assert journal.snapshot() == after


@pytest.mark.parametrize("flag,state", [
    ({"error": True}, "failed"), ({"errors": True}, "failed"),
    ({"error": 42}, "unknown"), ({"errors": 42}, "unknown"),
    ({"success": "false"}, "unknown"), ({"cancelled": "true"}, "unknown"),
    ({"success": None}, "unknown"), ({"cancelled": []}, "unknown"),
])
@pytest.mark.parametrize("reported_success", [{"image_path": "synthetic.exr"}, {"status": "done"}])
def test_malformed_result_flags_cannot_turn_into_success(flag, state, reported_success):
    assert events.classify_render_result(reported_success | flag)[0] == state
