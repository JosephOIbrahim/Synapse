"""Artist-requested suggestion controls; native/Qt qualification is separate.

The shared Stage 0 report fixture is synthetic data, never a native receipt.
"""
from copy import deepcopy
from pathlib import Path
import sys
import threading
from types import MethodType, ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from test_rsi_stage0 import report, record  # shared synthetic fixture definitions
from test_panel_finesse import functions
from synapse.host import lookdev_suggestion as host
from synapse.panel.lookdev_suggestion import SuggestionState, suggestion_view
from synapse.memory import experience as ex, moneta_runtime as mr, store as memory_store
from synapse.memory.embedding import HashEmbedder
from synapse.memory.moneta_store import MonetaBackedStore


def hit(record, token="test-token"):
    return {"status": "HIT", "complete": True, "record_id": record["record_id"],
            "experience": record, "environment": record["environment"], "request_token": token}


def test_view_exposes_checked_settings_but_draft_excludes_historical_paths(record):
    view = suggestion_view(hit(record))
    assert view["status"] == "HIT"
    assert "Frequency: 4.0" in view["body"]
    assert "rendered appearance were not checked" in view["body"]
    assert "SYNTHETIC unit fixture" not in view["draft"]
    assert "/stage/old" not in view["draft"]
    assert "fresh name" in view["draft"]


@pytest.mark.parametrize("bad", [None, [], {}, {"status": "HIT"},
                                 {"status": "NO_MATCH"}, {"status": "INELIGIBLE"}])
def test_unknown_or_incomplete_result_never_offers_a_draft(bad):
    assert suggestion_view(bad)["draft"] == ""


@pytest.mark.parametrize("change", [
    lambda r: r.update(complete=False),
    lambda r: r.update(record_id="different"),
    lambda r: r["environment"].update(dependency_sha256="0" * 64),
    lambda r: r["experience"]["procedure"].update(summary="Changed after checking"),
])
def test_hit_requires_intact_matching_evidence(record, change):
    response = deepcopy(hit(record))
    # Break shared-reference aliasing so changing observed facts is independent.
    response["environment"] = dict(response["environment"])
    change(response)
    assert suggestion_view(response)["draft"] == ""


def test_new_request_dismiss_and_failure_cannot_restore_old_hit(record):
    state = SuggestionState()
    first = state.begin()
    assert state.accept(first, hit(record))
    assert state.view()["draft"]
    second = state.begin()
    assert not state.accept(first, hit(record))
    assert state.view()["draft"] == ""
    assert state.accept(second, {"status": "UNAVAILABLE", "reason": "Unreadable store"})
    assert state.view()["draft"] == ""
    state.begin()  # dismiss/scene change/close invalidate the same boundary
    assert not state.accept(second, hit(record))


@pytest.mark.parametrize("busy", [False, True])
def test_local_suggestion_command_never_reaches_a_model(busy):
    namespace = functions("synapse_panel.py", ["_send"], {
        "_ACTIVE_PANEL_WORKERS": {object()} if busy else set(), "ClaudeWorker": None})
    panel = SimpleNamespace(_open_lookdev_suggestion=Mock(),
                            _prepare_connection=Mock(side_effect=AssertionError("No model for lookup")))
    assert namespace["_send"](panel, "/lookdev-suggestion") is True
    panel._open_lookdev_suggestion.assert_called_once_with()
    panel._prepare_connection.assert_not_called()


@pytest.mark.parametrize("existing", ["", "My existing creative thought"])
def test_prepare_preserves_composer_and_does_not_send(existing):
    namespace = functions("synapse_panel.py", ["_prepare_lookdev_prompt"], {})
    panel = SimpleNamespace(_input=Mock(), _send=Mock(side_effect=AssertionError("Draft was submitted")))
    panel._input.toPlainText.return_value = existing
    namespace["_prepare_lookdev_prompt"](panel, "Editable starting settings")
    expected = existing + "\n\nEditable starting settings" if existing else "Editable starting settings"
    panel._input.setPlainText.assert_called_once_with(expected)
    panel._send.assert_not_called()


def test_private_assistance_does_not_extend_public_recall_schema():
    from synapse.mcp._tool_registry import TOOL_JSON
    assert set(TOOL_JSON["synapse_recall"]["inputSchema"]["properties"]) == {"query"}


@pytest.fixture
def scene(monkeypatch, tmp_path, record):
    if not mr.moneta_available():
        pytest.skip("Moneta unavailable")
    project = tmp_path / "project"
    project.mkdir()
    storage_dir = project / ".synapse"
    store = MonetaBackedStore.from_storage_dir(storage_dir, HashEmbedder(), dual_write_jsonl=False)
    owner = SimpleNamespace(store=store, storage_dir=storage_dir, _resolve_project_path=lambda _: project)
    callbacks = []
    hip = SimpleNamespace(path=lambda: str(project / "scene.hip"),
                          addEventCallback=callbacks.append, eventCallbacks=lambda: tuple(callbacks),
                          removeEventCallback=callbacks.remove)
    import hou
    monkeypatch.setattr(hou, "hipFile", hip, raising=False)
    monkeypatch.setattr(hou, "applicationVersionString", lambda: "22.0.400", raising=False)
    dependency = tmp_path / "observed-dependency.usd"
    dependency.write_text("synthetic installed dependency", encoding="utf-8")
    monkeypatch.setattr(hou, "expandString", lambda _: str(dependency), raising=False)
    husd = ModuleType("husd")
    husd.quickmaterials = SimpleNamespace(theQuickMaterialBaseFilePath="$HH/observed")
    monkeypatch.setitem(sys.modules, "husd", husd)
    observed = []
    def capture(build, path):
        observed.append((build, path, threading.get_ident()))
        return dict(record["environment"], houdini_build=build)
    monkeypatch.setattr(ex, "capture_environment", capture)
    monkeypatch.setattr(memory_store, "_global_synapse", owner)
    monkeypatch.setattr(memory_store, "get_synapse_memory", Mock(side_effect=AssertionError("Created an owner")))
    monkeypatch.setattr(host, "_on_main", lambda fn: fn())
    yield SimpleNamespace(owner=owner, store=store, callbacks=callbacks, observed=observed,
                          dependency=dependency, hip=hip, project=project)
    store.close()


def test_disabled_and_unarmed_request_do_no_host_work(monkeypatch):
    marshal = Mock(side_effect=AssertionError("Unexpected host work"))
    monkeypatch.setattr(host, "_on_main", marshal)
    session = host.LookdevSuggestionSession()
    assert session.lookup()["status"] == "UNAVAILABLE"
    assert session.lookup(session.token())["status"] == "UNAVAILABLE"
    session.close()
    marshal.assert_not_called()


def test_host_uses_observed_environment_existing_owner_and_no_embeddings(scene, record, monkeypatch):
    assert ex.ExperienceMemory(scene.owner, enabled=True).record(record)["status"] == "STORED"
    monkeypatch.setattr(scene.store._embedder, "embed", Mock(side_effect=AssertionError("Lookup embedded")))
    session = host.LookdevSuggestionSession()
    try:
        token = session.begin_request()
        assert scene.observed == []  # arming never reads project memory/environment
        result = session.lookup(token, requested=True)
        assert result["status"] == "HIT" and result["experience"] == record
        assert session.is_current(result["request_token"])
        assert scene.observed == [("22.0.400", str(scene.dependency), threading.main_thread().ident)]
        assert len(scene.callbacks) == 1
    finally:
        session.close()
    assert not scene.callbacks


@pytest.mark.parametrize("event", ["BeforeLoad", "BeforeClear", "BeforeQuit", "AfterSave"])
def test_scene_change_after_click_before_lookup_invalidates_without_reading(scene, event):
    session = host.LookdevSuggestionSession()
    token = session.begin_request()
    scene.callbacks[0]("hipFileEventType." + event)
    assert session.lookup(token, requested=True)["status"] == "UNAVAILABLE"
    assert not scene.observed
    session.close()


def test_owner_or_backend_replacement_invalidates_a_returned_result(scene, record, monkeypatch):
    assert ex.ExperienceMemory(scene.owner, enabled=True).record(record)["status"] == "STORED"
    session = host.LookdevSuggestionSession()
    token = session.begin_request()
    assert session.lookup(token, requested=True)["status"] == "HIT"
    monkeypatch.setattr(memory_store, "_global_synapse", SimpleNamespace(store=scene.store))
    assert not session.is_current(token)
    monkeypatch.setattr(memory_store, "_global_synapse", scene.owner)
    scene.owner.store = object()
    assert not session.is_current(token)
    scene.owner.store = scene.store
    session.close()


def test_wrong_project_or_missing_owner_never_reads_record(scene, monkeypatch):
    read = Mock(side_effect=AssertionError("Wrong project was read"))
    monkeypatch.setattr(scene.store, "get_by_tag_strict", read)
    session = host.LookdevSuggestionSession()
    token = session.begin_request()
    scene.owner.storage_dir = scene.project / "wrong"
    assert session.lookup(token, requested=True)["status"] == "UNAVAILABLE"
    monkeypatch.setattr(memory_store, "_global_synapse", None)
    assert session.lookup(token, requested=True)["status"] == "UNAVAILABLE"
    read.assert_not_called()
    session.close()


def test_wrong_thread_cannot_fall_through_to_host_access(scene):
    session = host.LookdevSuggestionSession()
    token = session.begin_request()
    results = []
    thread = threading.Thread(target=lambda: results.append(session.lookup(token, requested=True)))
    thread.start()
    thread.join(3)
    assert not thread.is_alive()
    assert results[0]["status"] == "UNAVAILABLE"
    assert "main thread" in results[0]["reason"]
    assert scene.observed == []
    session.close()


@pytest.mark.parametrize("target", ["owner", "backend"])
def test_busy_memory_is_unavailable_without_waiting_on_main(scene, target):
    lock = memory_store._GLOBAL_LOCK if target == "owner" else scene.store._lock
    acquired, release = threading.Event(), threading.Event()
    def hold():
        with lock:
            acquired.set()
            release.wait(3)
    holder = threading.Thread(target=hold)
    holder.start()
    assert acquired.wait(1)
    rescue = threading.Timer(0.25, release.set)
    rescue.start()
    session = host.LookdevSuggestionSession()
    try:
        response = session.lookup(session.begin_request(), requested=True)
        assert not release.is_set(), "Main waited for the background memory operation"
        assert response["status"] == "UNAVAILABLE" and "busy" in response["reason"]
        assert scene.observed == []
    finally:
        release.set()
        holder.join(3)
        rescue.cancel()
        session.close()
