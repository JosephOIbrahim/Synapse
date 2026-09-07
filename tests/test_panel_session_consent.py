"""Actual panel consent methods with synthetic controls, recipients and rules.

Real QMessageBox click/Escape/close coverage lives in checks/session-consent.
These tests remain host-free so the consent lifecycle runs in ordinary CI.
"""
import ast
from contextlib import nullcontext
import importlib.util
from pathlib import Path
import sys
from types import MethodType, SimpleNamespace
from unittest.mock import Mock
import weakref

import pytest

from synapse import model_access as access
from synapse.panel import connections as cn


PANEL_SOURCE = Path(__file__).parents[1] / "python/synapse/panel/synapse_panel.py"


def panel_methods(qt_widgets):
    tree = ast.parse(PANEL_SOURCE.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "SynapsePanel")
    names = {"_allow_connection", "_send", "_on_submit", "_refresh_session_permission", "_revoke_session_approvals"}
    namespace = {"QtWidgets": qt_widgets, "Qt": SimpleNamespace(PlainText=0),
                 "logger": Mock(), "ClaudeWorker": object, "_ACTIVE_PANEL_WORKERS": set(),
                 "_timed_phase": lambda *args, **kwargs: nullcontext(),
                 "_SESSION_PERMISSION_VIEWS": weakref.WeakSet()}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("_session_permission_views", "_refresh_session_permission_views"):
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(PANEL_SOURCE), "exec"), namespace)
    if "_session_permission_views" in namespace:
        namespace["_SESSION_PERMISSION_VIEWS"] = namespace["_session_permission_views"]()
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(PANEL_SOURCE), "exec"), namespace)
    return {name: namespace[name] for name in names if name in namespace}


class PermissionBox:
    AcceptRole, RejectRole, ActionRole = range(3)

    def __init__(self, parent):
        self.parent = parent
        self._buttons = []
        self._clicked = None
        self.default = self.escape = None
        self.informative = self.description = ""

    def setWindowTitle(self, value):
        self.title = value

    def setTextFormat(self, value):
        self.text_format = value

    def setText(self, value):
        self.description = value

    def setInformativeText(self, value):
        self.informative = value

    def addButton(self, text, role):
        button = SimpleNamespace(text=lambda: text, role=role)
        self._buttons.append(button)
        return button

    def setDefaultButton(self, button):
        self.default = button

    def setEscapeButton(self, button):
        self.escape = button

    def clickedButton(self):
        return self._clicked

    def deleteLater(self):
        self.deleted_later = True

    def exec(self):
        self.parent.prompts.append(self)
        assert self.parent.choices, "Unexpected consent prompt after session approval"
        text, before = self.parent.choices.pop(0)
        if before:
            before()
        self._clicked = next((button for button in self._buttons if button.text() == text), None)


class SyntheticProvider:
    def __init__(self, spec):
        self.id, self.model_identity, self.endpoint = spec.provider, spec.model, spec.endpoint

    def _get_endpoint(self):
        endpoint = cn.validate_endpoint(self.endpoint)
        return endpoint.scheme, endpoint.netloc, endpoint.path

    def resolve_key(self):
        raise AssertionError("Use only the explicitly supplied synthetic credential")

    def stream(self, **kwargs):
        raise AssertionError("No model or network calls in consent tests")


class PanelState:
    def __init__(self, **fields):
        self.__dict__.update(fields)


def remote(model="synthetic-a", endpoint="https://service-a.invalid/v1/chat/completions"):
    return cn.ConnectionSpec("custom", model, endpoint)


def bound(spec=None, key="synthetic-key"):
    spec = spec or remote()
    return cn.bind_provider(SyntheticProvider(spec), key=key, facts=cn.ConnectionFacts(spec))


@pytest.fixture
def policy(tmp_path, monkeypatch):
    target = tmp_path / "project/model_access.json"
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(target))
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.delitem(sys.modules, "_synapse_panel_session_permission_views_v1", raising=False)
    if hasattr(access, "revoke_session_approvals"):
        access.revoke_session_approvals()
    yield target
    if hasattr(access, "revoke_session_approvals"):
        access.revoke_session_approvals()


@pytest.fixture
def make_panel(policy):
    methods = panel_methods(SimpleNamespace(QMessageBox=PermissionBox))
    held = []

    def make(spec=None, key="synthetic-key"):
        panel = PanelState(
            choices=[], prompts=[], _worker=None, _input=Mock(),
            _pending_context=["/stage/artist_selection"], _messages=[], _chat=Mock(),
            _permission_connections=[], _task_connection=None,
            _hide_turn_receipt=Mock(), _start_worker=Mock(), _refresh_engine_selector=Mock(),
            _refresh_token_surfaces=Mock(), _session_permission_btn=Mock(),
        )
        panel._input.toPlainText.return_value = "Unsent artist draft"
        panel._prepare_connection = Mock(side_effect=lambda: bound(spec, key))
        panel._route_connection = Mock(side_effect=lambda connection, text: connection)
        for name, function in methods.items():
            setattr(panel, name, MethodType(function, panel))
        methods["_send"].__globals__["_SESSION_PERMISSION_VIEWS"].add(panel)
        held.append(panel)
        return panel

    yield make
    for panel in held:
        for connection in panel._permission_connections:
            connection.release()


def choose(panel, text, before=None):
    panel.choices.append((text, before))


def finish_task(panel):
    connection = panel._task_connection
    connection.revoke()
    panel._permission_connections.clear()
    panel._task_connection = None
    return connection


def test_session_choice_is_explicit_and_uses_safe_default(make_panel):
    panel = make_panel()
    choose(panel, "Allow for this session")
    assert panel._send("Make the lighting softer") is True
    prompt = panel.prompts[0]
    assert [button.text() for button in prompt._buttons] == [
        "Allow this task", "Allow for this session", "Keep editing"]
    assert prompt.default.text() == "Keep editing"
    assert prompt.escape.text() == "Keep editing"
    assert prompt.deleted_later
    assert "session" in prompt.informative.lower()
    assert "background" in prompt.informative.lower()
    assert "external mcp" in prompt.informative.lower()


def test_repeated_send_redeems_session_with_fresh_child_scope(make_panel, policy):
    panel = make_panel()
    choose(panel, "Allow for this session")
    assert panel._send("First task") is True
    first = finish_task(panel)
    assert panel._send("Second task") is True
    second = panel._task_connection
    assert len(panel.prompts) == 1
    assert second.provider._model_grant is not first.provider._model_grant
    assert second.provider._model_scope is not first.provider._model_scope
    assert second.provider._model_scope.task_id != first.provider._model_scope.task_id
    assert not first.provider._model_scope.active
    assert access.require_access(second.spec, key=second.provider.resolve_key(), facts=second.facts,
                                 scope=second.provider._model_scope, grant=second.provider._model_grant)
    assert not policy.exists(), "Session approval must not write project rules"
    assert [message["content"] for message in panel._messages] == [
        "[Context: /stage/artist_selection]\nFirst task", "Second task"]


def test_task_only_choice_prompts_again_on_second_send(make_panel):
    panel = make_panel()
    choose(panel, "Allow this task")
    assert panel._send("First task")
    first = finish_task(panel)
    choose(panel, "Allow this task")
    assert panel._send("Second task")
    assert len(panel.prompts) == 2
    assert not access.has_session_approval(first.spec, key="synthetic-key")


@pytest.mark.parametrize("dismissal", ["Keep editing", None, "Escape"])
def test_decline_keeps_draft_context_and_history(make_panel, dismissal):
    panel = make_panel()
    panel._messages.append({"role": "assistant", "content": "Earlier work"})
    before = list(panel._messages)
    choose(panel, dismissal)
    panel._on_submit()
    assert panel._messages == before
    assert panel._pending_context == ["/stage/artist_selection"]
    panel._input.clear.assert_not_called()
    panel._start_worker.assert_not_called()
    panel._chat.append_user_message.assert_not_called()


@pytest.mark.parametrize("option", ["Allow this task", "Allow for this session"])
def test_policy_change_while_modal_cannot_authorize_new_scope(make_panel, policy, option):
    panel = make_panel()
    choose(panel, option, lambda: access.save_policy("local_only", path=policy))
    panel._on_submit()
    panel._start_worker.assert_not_called()
    panel._input.clear.assert_not_called()
    assert panel._messages == [] and panel._pending_context == ["/stage/artist_selection"]
    assert access.load_policy().mode == "local_only"


def test_session_can_be_reused_by_other_panel_then_revoked_before_dispatch(make_panel):
    first = make_panel()
    choose(first, "Allow for this session")
    assert first._send("First task")
    finish_task(first)
    other = make_panel()
    assert other._send("Queued task")
    child = other._task_connection
    first._revoke_session_approvals()
    assert not access.has_session_approval(child.spec, key="synthetic-key")
    with pytest.raises(access.ModelAccessDenied):
        access.require_access(child.spec, key=child.provider.resolve_key(), facts=child.facts,
                              scope=child.provider._model_scope, grant=child.provider._model_grant)
    assert child.provider.resolve_key() == "synthetic-key", "Revoke must not erase an in-flight worker key"
    assert not other.prompts


@pytest.mark.parametrize("changed", ["model", "endpoint", "key"])
def test_session_never_inherits_across_changed_recipient(make_panel, changed):
    original = make_panel()
    choose(original, "Allow for this session")
    assert original._send("First task")
    finish_task(original)
    spec = remote(model="synthetic-b") if changed == "model" else remote(
        endpoint="https://service-b.invalid/v1/chat/completions") if changed == "endpoint" else remote()
    other = make_panel(spec, key="changed-key" if changed == "key" else "synthetic-key")
    choose(other, "Keep editing")
    assert other._send("Draft for another recipient") is False
    assert len(other.prompts) == 1
    other._start_worker.assert_not_called()


def test_routed_recipient_is_the_one_approved(make_panel):
    panel = make_panel()
    target = bound(remote(model="routed-b", endpoint="https://routed.invalid/v1/chat/completions"))
    originals = []

    def route(connection, text):
        originals.append(connection)
        connection.release()
        return target

    panel._route_connection.side_effect = route
    choose(panel, "Allow for this session")
    assert panel._send("Task routed before consent")
    assert panel._task_connection is target
    assert target.spec.identity in panel.prompts[0].description
    assert access.has_session_approval(target.spec, key="synthetic-key")
    assert not access.has_session_approval(originals[0].spec, key="synthetic-key")


def test_project_only_rules_do_not_create_a_session_approval(make_panel, policy):
    access.save_policy("ask", (remote(),), path=policy)
    panel = make_panel()
    assert panel._send("Already covered by project rules")
    assert not panel.prompts
    assert not access.has_session_approval(remote(), key="synthetic-key")


def test_visible_footer_follows_shown_recipient_and_revoke_broadcast(make_panel):
    first, other = make_panel(), make_panel()
    choose(first, "Allow for this session")
    assert first._send("Approve the selected service")
    first._session_permission_btn.setVisible.assert_called_with(True)
    other._session_permission_btn.setVisible.assert_called_with(True)
    different = bound(remote(model="not-approved"))
    first._refresh_session_permission(different)
    first._session_permission_btn.setVisible.assert_called_with(False)
    different.release()
    other._revoke_session_approvals()
    first._session_permission_btn.setVisible.assert_called_with(False)
    other._session_permission_btn.setVisible.assert_called_with(False)


def test_footer_permission_read_releases_only_temporary_connection(make_panel):
    panel = make_panel()
    temporary = bound()
    panel._prepare_connection.side_effect = lambda: temporary
    panel._refresh_session_permission()
    assert temporary.provider.resolve_key() is None
    active = bound()
    panel._task_connection = active
    panel._refresh_session_permission()
    assert active.provider.resolve_key() == "synthetic-key"
    active.release()


@pytest.mark.parametrize("choice,accepted", [("Allow this task", True), ("Allow for this session", False)])
def test_unavailable_session_anchor_retains_task_only_recovery(make_panel, monkeypatch, choice, accepted):
    # Replace the process-local handle only in this test; leave real state intact.
    monkeypatch.setattr(access, "_SESSION_STATE", None)
    panel = make_panel()
    choose(panel, choice)
    assert panel._send("Draft after runtime consent expiry") is accepted
    assert len(panel.prompts) == 1
    if accepted:
        child = panel._task_connection
        assert access.require_access(child.spec, key=child.provider.resolve_key(), facts=child.facts,
                                     scope=child.provider._model_scope, grant=child.provider._model_grant)
    else:
        panel._start_worker.assert_not_called()
        assert panel._pending_context == ["/stage/artist_selection"] and not panel._messages


def test_independent_panel_method_generations_share_view_registry(make_panel):
    first = make_panel()
    newer_methods = panel_methods(SimpleNamespace(QMessageBox=PermissionBox))
    old_views = first._send.__func__.__globals__["_SESSION_PERMISSION_VIEWS"]
    assert newer_methods["_send"].__globals__["_SESSION_PERMISSION_VIEWS"] is old_views
    other = make_panel()
    for name, function in newer_methods.items():
        setattr(other, name, MethodType(function, other))
    choose(first, "Allow for this session")
    assert first._send("Consent in the older panel generation")
    other._session_permission_btn.setVisible.assert_called_with(True)
    other._revoke_session_approvals()
    first._session_permission_btn.setVisible.assert_called_with(False)


def test_older_connection_class_can_display_permission_without_reminting(make_panel, monkeypatch):
    name = "synapse.panel._consent_test_previous_connections"
    spec = importlib.util.spec_from_file_location(name, cn.__file__)
    previous = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, previous)
    spec.loader.exec_module(previous)
    panel = make_panel()
    choose(panel, "Allow for this session")
    assert panel._send("Approve current recipient")
    old_spec = previous.ConnectionSpec(remote().provider, remote().model, remote().endpoint)
    assert not isinstance(old_spec, access.ConnectionSpec)
    old = previous.bind_provider(SyntheticProvider(old_spec), key="synthetic-key", facts=previous.ConnectionFacts(old_spec))
    panel._refresh_session_permission(old)
    panel._session_permission_btn.setVisible.assert_called_with(True)
    assert not hasattr(old.provider, "_model_grant"), "A display refresh must never mint a grant"
    old.release()
