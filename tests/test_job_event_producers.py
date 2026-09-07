"""Actual producer/journal composition, with rendering replaced locally."""
import json
import sys
import threading
import types
from unittest.mock import MagicMock

import pytest

from synapse import job_events as events
from synapse.server import render_session as sessions
from synapse.server import render_notify as notify
from synapse.server import handlers_render as render
from synapse.server import main_thread


@pytest.fixture
def journal(monkeypatch):
    anchor = types.ModuleType(events._ANCHOR_NAME)
    anchor.journal = events.JobJournal()
    monkeypatch.setitem(sys.modules, events._ANCHOR_NAME, anchor)
    sessions.reset()
    yield anchor.journal
    sessions.reset()


def test_registry_semantics_survive_error_projection_without_payload_retention(journal):
    result = {"status": "error", "error": "PRIVATE_KEY_AND_PROMPT"}
    token = sessions.start_session({"rop": "/stage/ROP", "scene": "a.hip", "prompt": "PRIVATE_KEY_AND_PROMPT"})
    assert sessions.complete_session(token, result) is None
    assert sessions.get_session(token)["state"] == "done"
    assert sessions.get_session(token)["result"] is result
    row = journal.snapshot()["entries"][0]
    assert row["state"] == "failed" and row["source"] == "render_session"
    assert row["node"] == "/stage/ROP" and row["scene"] == "a.hip"
    assert "PRIVATE_KEY_AND_PROMPT" not in json.dumps(journal.snapshot())


def test_observer_failure_cannot_alter_registry_or_inline_execution(journal, monkeypatch):
    def broken():
        raise RuntimeError("broken observer")
    monkeypatch.setattr(events, "get_journal", broken)
    token = sessions.start_session({})
    result = {"image_path": "a.exr"}
    sessions.complete_session(token, result)
    assert sessions.get_session(token)["result"] is result
    assert events.observe_inline_render(lambda _: result, {}) is result
    original = ValueError("original execution exception")
    def raises(_):
        raise original
    with pytest.raises(ValueError) as exc:
        events.observe_inline_render(raises, {})
    assert exc.value is original
    assert journal.snapshot()["entries"] == []


def test_inline_real_branch_preserves_no_registry_invariant(journal, monkeypatch):
    rop = MagicMock()
    rop.type.return_value.name.return_value = "karma"
    rop.parm.return_value = None
    monkeypatch.setattr(render, "HOU_AVAILABLE", True)
    monkeypatch.setattr(render, "hou", types.SimpleNamespace(node=lambda _: rop), raising=False)
    monkeypatch.setattr(main_thread, "run_on_main", lambda fn, **kw: fn())
    monkeypatch.setattr(main_thread, "_MAIN_THREAD_ID", threading.get_ident())
    handler = render.RenderHandlerMixin()
    result = {"image_path": "preview.jpg", "flipbook_fallback": True}
    handler._handle_render = lambda _: result
    assert handler._handle_render_bounded({"node": "/stage/ROP"}) is result
    assert sessions.summary() == []
    row = journal.snapshot()["entries"][0]
    assert row["source"] == "render_inline" and row["state"] == "preview"
    assert row["node"] == "/stage/ROP"


def test_inline_exception_is_preserved_and_not_copied(journal):
    original = RuntimeError("PRIVATE_PROMPT")
    def raises(_):
        raise original
    with pytest.raises(RuntimeError) as exc:
        events.observe_inline_render(raises, {})
    assert exc.value is original
    assert journal.snapshot()["entries"][0]["state"] == "failed"
    assert "PRIVATE_PROMPT" not in json.dumps(journal.snapshot())


@pytest.mark.parametrize("total,passed,failed,state", [(3,3,0,"completed"), (3,2,1,"failed"),
    (3,1,0,"unknown"), (3,2,0,"unknown"), (0,0,0,"unknown"), (3,4,0,"unknown")])
def test_batch_is_terminal_report_only_and_never_toasts(journal, monkeypatch, tmp_path, total, passed, failed, state):
    monkeypatch.setattr(notify, "send_toast", lambda *a, **kw: pytest.fail("Producer bypassed desktop policy"))
    report = notify.BatchReport(start_frame=1, end_frame=3, total_frames=total,
                                 successful_frames=passed, failed_frames=failed, rop_path="/stage/ROP")
    before = journal.snapshot()["sequence"]
    result = notify.notify_batch_complete(report, str(tmp_path))
    assert result["toast_sent"] is False and "report_path" in result
    after = journal.snapshot()
    assert after["sequence"] == before + 1
    assert len(after["entries"]) == 1
    assert after["entries"][0]["state"] == state
    assert after["entries"][0]["node"] == "/stage/ROP"
    assert after["entries"][0]["source"] == "render_batch_report"
    assert "_notification_id" not in report.to_dict()
    notify.notify_batch_complete(report, str(tmp_path))
    assert journal.snapshot() == after


def test_failure_notice_preserves_boolean_but_keeps_issue_text_private(journal, monkeypatch):
    monkeypatch.setattr(notify, "send_toast", lambda *a, **kw: pytest.fail("Producer bypassed desktop policy"))
    assert notify.notify_persistent_failure(42, "SECRET_TOOL_RESULT", 3) is False
    row = journal.snapshot()["entries"][0]
    assert row["state"] == "failed" and "42" in row["detail"] and "3" in row["detail"]
    assert "SECRET_TOOL_RESULT" not in json.dumps(journal.snapshot())


def test_notification_failure_does_not_drop_report(journal, monkeypatch, tmp_path):
    monkeypatch.setattr(events, "get_journal", lambda: (_ for _ in ()).throw(RuntimeError("observer failed")))
    report = notify.BatchReport(start_frame=1, end_frame=1, total_frames=1, successful_frames=1)
    result = notify.notify_batch_complete(report, str(tmp_path))
    assert result["toast_sent"] is False and "report_path" in result


@pytest.mark.parametrize("passed,failed", [(2, 1), (1, 0)])
def test_changed_terminal_report_keeps_identity_and_never_creates_green(journal, tmp_path, passed, failed):
    report = notify.BatchReport(start_frame=1, end_frame=3, total_frames=3,
                                successful_frames=passed, failed_frames=failed)
    notify.notify_batch_complete(report, str(tmp_path))
    original = journal.snapshot()["entries"][0]
    report.successful_frames, report.failed_frames = 3, 0
    notify.notify_batch_complete(report, str(tmp_path))
    changed = journal.snapshot()
    assert len(changed["entries"]) == 1
    row = changed["entries"][0]
    assert row["id"] == original["id"] and row["state"] == "unknown"
    assert "Conflicting outcome reports" in row["detail"]
    notify.notify_batch_complete(report, str(tmp_path))
    assert journal.snapshot() == changed
