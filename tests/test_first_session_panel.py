"""Run actual panel method bodies without loading Houdini or a live bridge."""
import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from synapse.panel.connections import ConnectionSpec, ConnectionFacts


def panel_methods(*names):
    source = Path(__file__).parents[1] / "python/synapse/panel/synapse_panel.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SynapsePanel")
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    namespace = {"ClaudeWorker": object, "_timed_phase": lambda *a, **k: nullcontext(), "logger": Mock(), "_ACTIVE_PANEL_WORKERS": set()}
    for method in methods:
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
    return {name: namespace[name] for name in names}


def fixture_panel():
    spec = ConnectionSpec("custom", "model-a", "https://example.com/v1/chat/completions")
    connection = SimpleNamespace(spec=spec, facts=ConnectionFacts(spec),
                                 provider=SimpleNamespace(resolve_key=lambda: "test-key"), release=Mock())
    methods = panel_methods("_send", "_on_submit")
    panel = SimpleNamespace(
        _worker=None, _input=Mock(), _pending_context=["/stage/light"],
        _messages=[{"role": "user", "content": "earlier"}], _chat=Mock(),
        _prepare_connection=Mock(return_value=connection),
        _allow_connection=Mock(return_value=False), _hide_turn_receipt=Mock(),
        _start_worker=Mock(), _refresh_engine_selector=Mock(),
    )
    panel._input.toPlainText.return_value = "My unfinished prompt"
    panel._send = lambda text: methods["_send"](panel, text)
    return panel, connection, methods


def test_decline_preserves_draft_attachments_and_history():
    panel, connection, methods = fixture_panel()
    before = list(panel._messages)
    methods["_on_submit"](panel)
    panel._input.clear.assert_not_called()
    panel._start_worker.assert_not_called()
    panel._chat.append_user_message.assert_not_called()
    assert panel._messages == before
    assert panel._pending_context == ["/stage/light"]
    connection.release.assert_called_once()


def test_palette_send_also_checks_permission_without_consuming_draft():
    panel, _, _ = fixture_panel()
    assert panel._send("Explain selected network") is False
    panel._allow_connection.assert_called_once()
    panel._input.clear.assert_not_called()
    assert panel._pending_context == ["/stage/light"]


def test_busy_send_does_not_append_a_second_turn():
    panel, _, methods = fixture_panel()
    panel._worker = SimpleNamespace(isRunning=lambda: True)
    methods["_on_submit"](panel)
    assert len(panel._messages) == 1
    panel._prepare_connection.assert_not_called()
    panel._input.clear.assert_not_called()


def test_accept_binds_exact_connection_and_consumes_once():
    panel, connection, methods = fixture_panel()
    panel._allow_connection.return_value = True
    methods["_on_submit"](panel)
    assert panel._task_connection is connection
    assert panel._last_task_facts is connection.facts
    panel._start_worker.assert_called_once()
    panel._input.clear.assert_called_once()
    assert len(panel._messages) == 2
    assert panel._pending_context == []


def test_completion_credits_task_even_after_selection_changes(monkeypatch):
    from synapse.server import session_store
    monkeypatch.setattr(session_store, "save_conversation", lambda _: None)
    panel, connection, _ = fixture_panel()
    panel._task_connection = connection
    panel._stream_buf = ["Completed"]
    panel._streaming_started = False
    panel._author_token = lambda: "new-provider/new-model"
    panel._set_thinking = Mock()
    panel._set_busy = Mock()
    panel._turn_evidence = lambda: ([], [], [])
    panel._refresh_token_surfaces = Mock()
    panel_methods("_on_done")["_on_done"](panel)
    panel._chat.append_synapse_message.assert_called_once_with("Completed", signed="custom/model-a")
    assert panel._task_connection is None


def test_unknown_provider_cannot_take_registry_fallback():
    import pytest
    panel = SimpleNamespace(_provider_id="no-longer-installed", _active_model=lambda: "old-model")
    with pytest.raises(ValueError):
        panel_methods("_make_provider")["_make_provider"](panel)


def test_other_panel_cannot_overlap_a_retained_task():
    panel, _, _ = fixture_panel()
    send = panel_methods("_send")["_send"]
    send.__globals__["_ACTIVE_PANEL_WORKERS"].add(object())
    assert send(panel, "new task") is False
    panel._prepare_connection.assert_not_called()
    assert len(panel._messages) == 1


def test_stop_keeps_completed_tool_results_and_pairs_unexecuted_calls():
    source = Path(__file__).parents[1] / "python/synapse/panel/claude_worker.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_conversation_loop")
    ns = {"USAGE_SINK": None, "_MAX_TOOL_ITERATIONS": 3, "logger": Mock()}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), ns)
    calls = [{"type": "tool_use", "id": "a", "name": "create", "input": {}},
             {"type": "tool_use", "id": "b", "name": "change", "input": {}}]
    worker = SimpleNamespace(_abort=False, _messages=[], _tools=[], _system="",
                             activity_changed=Mock(), token_received=Mock(),
                             _provider=SimpleNamespace(stream=lambda **_: ("tool_use", calls)))
    executed = []
    def execute(block):
        executed.append(block["id"])
        worker._abort = True
        return {"type": "tool_result", "tool_use_id": block["id"], "content": "Created the node"}
    worker._execute_tool_block = execute
    ns["_conversation_loop"](worker, "test-key")
    results = worker._messages[-1]["content"]
    assert executed == ["a"]
    assert [r["tool_use_id"] for r in results] == ["a", "b"]
    assert results[0]["content"] == "Created the node"
    assert results[1]["is_error"] is True and "Cancelled before execution" in results[1]["content"]


def test_failed_selection_does_not_keep_previous_location_tooltip():
    panel = SimpleNamespace(_author_lbl=Mock(), _author_token=lambda: "custom/b",
                            _active_model=lambda: "b", _provider_id="custom",
                            _prepare_connection=Mock(side_effect=ValueError("bad config")),
                            _model_connection_detail="Local\nollama/a", _connection_status=Mock(),
                            _render_token_state=Mock())
    panel_methods("_refresh_engine_selector")["_refresh_engine_selector"](panel)
    assert "ollama/a" not in panel._model_connection_detail
    assert "Local" not in panel._model_connection_detail
    assert "custom/b" in panel._model_connection_detail


def test_failed_stream_still_credits_the_task_model():
    panel, connection, _ = fixture_panel()
    panel._task_connection = connection
    panel._streaming_started = True
    panel._stream_buf = ["Partial answer"]
    panel._set_thinking = Mock()
    panel._set_busy = Mock()
    panel._provider_id = "gemini"
    panel_methods("_on_error")["_on_error"](panel, "Model request failed")
    panel._chat.end_stream.assert_called_once_with("Partial answer", signed="custom/model-a")
    assert panel._task_connection is None


@pytest.mark.parametrize("changed", [True, False])
def test_custom_address_change_does_not_rebind_a_legacy_credential(monkeypatch, changed):
    import sys
    from synapse.panel import settings
    from synapse.panel.providers.custom_provider import CustomProvider
    old_address = "https://service-a.example/v1"
    new_address = "https://service-b.example/v1" if changed else old_address
    monkeypatch.setenv("SYNAPSE_TEST_PREVIOUS_SERVICE_KEY", "credential-for-a")
    saved = {"custom": {"base_url": old_address, "model": "a",
                        "key_env": "SYNAPSE_TEST_PREVIOUS_SERVICE_KEY"}}
    monkeypatch.setattr(settings, "load_settings", lambda: saved)
    monkeypatch.setattr(settings, "save_settings", lambda value: saved.update(value))
    spec = ConnectionSpec("custom", "b", new_address + "/chat/completions")
    dialog = SimpleNamespace(exec=lambda: True, selection=(spec, ConnectionFacts(spec), "credential-for-b", new_address),
                             deleteLater=Mock())
    monkeypatch.setitem(sys.modules, "synapse.panel.connection_dialog",
                        SimpleNamespace(ConnectionDialog=lambda *a, **k: dialog))
    panel = SimpleNamespace(_provider_id="custom", _model_by_provider={}, _session_keys={},
                            _connection_facts={}, _persist_picks=Mock(),
                            _refresh_engine_selector=Mock(), _chat=Mock())
    panel_methods("_open_connections")["_open_connections"](panel)
    panel._session_keys.clear()  # closing the panel drops only its session key
    fresh_provider = CustomProvider(**saved["custom"])
    assert fresh_provider._get_endpoint()[1] == ("service-b.example" if changed else "service-a.example")
    if changed:
        assert fresh_provider.resolve_key() != "credential-for-a"
        assert not saved["custom"].get("key_env")
    else:
        assert fresh_provider.resolve_key() == "credential-for-a"
        assert saved["custom"]["key_env"] == "SYNAPSE_TEST_PREVIOUS_SERVICE_KEY"


def test_hda_decline_keeps_the_form_and_accepted_send_consumes_it():
    panel = SimpleNamespace(_hda_prompt=Mock(), _hda_ctx=Mock(), _hda_help=Mock(),
                            _send=Mock(return_value=False), _set_direct_view=Mock())
    panel._hda_prompt.toPlainText.return_value = "My network idea"
    panel._hda_ctx.currentText.return_value = "LOP"
    panel._hda_help.isChecked.return_value = True
    build = panel_methods("_on_build_hda")["_on_build_hda"]
    build(panel)
    panel._hda_prompt.clear.assert_not_called()
    panel._set_direct_view.assert_not_called()
    panel._send.return_value = True
    build(panel)
    panel._hda_prompt.clear.assert_called_once()
    panel._set_direct_view.assert_called_once_with("chat")


def test_revert_decline_does_not_announce_or_leave_review():
    panel = SimpleNamespace(_worker=None, _send=Mock(return_value=False),
                            _chat=Mock(), _set_face=Mock())
    revert = panel_methods("_on_revert")["_on_revert"]
    revert(panel)
    panel._chat.append_system_message.assert_not_called()
    panel._set_face.assert_not_called()
    panel._send.return_value = True
    revert(panel)
    panel._chat.append_system_message.assert_called_once()
    panel._set_face.assert_called_once_with("direct")
