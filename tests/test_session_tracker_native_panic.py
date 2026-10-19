"""L-PANIC-WS.2: a native panic in an automatic memory row stops at the tracker.

With ``SYNAPSE_AUTO_MEMORY=1`` (off by default) the session tracker writes
three housekeeping rows: "AI session started", "Executed: <cmd>" and the
session summary. PyO3 turns a Rust panic into ``pyo3_runtime.PanicException``,
which derives from ``BaseException``, not ``Exception``. Before this change:

- a panic in the start or summary row escaped ``start_session`` or
  ``end_session``, and then the connection handler;
- a panic in the "Executed" row escaped ``log_action``, passed the
  ``except Exception`` in ``SynapseHandler._submit_logs._do_log``, and stopped
  that command's audit entry and integrity block, with nothing logged.

Now each of the three writes logs the panic at ERROR and skips that row. The
session starts or ends normally, and ordinary exceptions are re-raised
unchanged (pinned).

Fakes only. The tracker is built with ``object.__new__`` and a MagicMock store,
as ``tests/test_harden_h1_h4.py`` builds it, so nothing opens a real memory
backend. Not run under hython.

Bite. On the unguarded tracker the four panic cases fail with the
``PanicException`` escaping; the ordinary-error pin passes on both sides.

Follow-up pins (the build -> cut edge gate). The summary and action rows
re-raise ordinary errors too, not only the start row. On all three rows the
ERROR record carries the panic's traceback. And with ``enveloped=True``, a
panic in the action row still lets ``_submit_logs`` write the audit row and
land the live integrity block.
"""

import logging
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class PanicException(BaseException):
    """Stand-in for PyO3's ``pyo3_runtime.PanicException``."""

    __module__ = "pyo3_runtime"


def _rust_panic():
    return PanicException("rust panicked")


def _bridge():
    """The tracker as tests/test_harden_h1_h4.py:79-91 builds it."""
    from synapse.session.tracker import SynapseBridge
    b = object.__new__(SynapseBridge)
    b._sessions = {}
    b._synapse = MagicMock()
    b._markdown_sync = None
    b._lock = threading.Lock()
    b.log_node_creation = True
    b.log_errors = True
    b._context_cache = {"stale": True}
    b._context_cache_time = 0.0
    b._context_cache_ttl = 30.0
    return b


@pytest.fixture
def bridge(monkeypatch):
    """An opted-in tracker: all three automatic rows are written."""
    monkeypatch.setenv("SYNAPSE_AUTO_MEMORY", "1")
    return _bridge()


def _session_errors(caplog):
    return [r for r in caplog.records
            if r.name == "synapse.session" and r.levelno == logging.ERROR]


# ---------------------------------------------------------------------------
# the three rows
# ---------------------------------------------------------------------------

def test_start_session_survives_a_native_panic_in_the_start_row(bridge, caplog):
    bridge._synapse.add.side_effect = _rust_panic()

    with caplog.at_level(logging.ERROR, logger="synapse.session"):
        sid = bridge.start_session("c1")

    assert sid.startswith("sess_")
    assert bridge.get_session(sid) is not None
    bridge._synapse.add.assert_called_once()  # the start row was attempted
    errors = _session_errors(caplog)
    assert len(errors) == 1, [r.getMessage() for r in caplog.records]
    assert "PanicException" in errors[0].getMessage()


def test_end_session_survives_a_native_panic_in_the_summary_row(bridge, caplog):
    sid = bridge.start_session("c1")  # the start row is written normally
    bridge.get_session(sid).commands_executed = 1
    bridge._synapse.add.side_effect = _rust_panic()

    with caplog.at_level(logging.ERROR, logger="synapse.session"):
        summary = bridge.end_session(sid)

    assert isinstance(summary, str) and summary
    # The summary row was attempted with exactly the summary that came back.
    assert bridge._synapse.add.call_args.kwargs["content"] == summary
    assert bridge.get_session(sid) is None
    assert len(_session_errors(caplog)) == 1, [r.getMessage() for r in caplog.records]


def test_log_action_survives_a_native_panic_in_the_action_row(bridge, caplog):
    sid = bridge.start_session("c1")
    assert bridge._context_cache == {"stale": True}  # control: start leaves the cache
    bridge._synapse.add.side_effect = _rust_panic()

    with caplog.at_level(logging.ERROR, logger="synapse.session"):
        bridge.log_action("Executed: create_node", session_id=sid)

    assert bridge._synapse.add.call_args.kwargs["content"] == "Executed: create_node"
    # The count goes up before the add, and the cache is still invalidated after it.
    assert bridge.get_session(sid).commands_executed == 1
    assert bridge._context_cache is None
    assert len(_session_errors(caplog)) == 1, [r.getMessage() for r in caplog.records]


# ---------------------------------------------------------------------------
# the caller of the "Executed" row
# ---------------------------------------------------------------------------

def test_submit_logs_keeps_the_audit_row_when_the_action_row_panics(bridge, monkeypatch):
    import synapse.server.handlers as handlers
    import synapse.server.main_thread as main_thread

    sid = bridge.start_session("c1")
    bridge._synapse.add.side_effect = _rust_panic()

    handler = object.__new__(handlers.SynapseHandler)
    handler._bridge = bridge  # never None: _get_bridge() would open a real store
    handler._session_id = sid
    handler._user_id = "pytest"

    class _InlineExecutor:
        def submit(self, fn, *args, **kwargs):
            return fn(*args, **kwargs)

    audited = []

    class _AuditRecorder:
        def log(self, **entry):
            audited.append(entry)

    recorder = _AuditRecorder()
    monkeypatch.setattr(handlers, "_log_executor", _InlineExecutor())
    # _do_log imports run_on_main from the module at call time.
    monkeypatch.setattr(main_thread, "run_on_main", lambda fn, *a, **k: fn())
    monkeypatch.setattr(handlers, "audit_log", lambda: recorder)

    handler._submit_logs("create_node", {}, {})

    assert bridge._synapse.add.call_args.kwargs["content"] == "Executed: create_node"
    assert [entry["operation"] for entry in audited] == ["create_node"]


# ---------------------------------------------------------------------------
# pin: ordinary errors keep today's behavior
# ---------------------------------------------------------------------------

def test_tracker_still_raises_ordinary_errors(bridge):
    bridge._synapse.add.side_effect = RuntimeError("store is down")

    with pytest.raises(RuntimeError, match="store is down"):
        bridge.start_session("c1")


# ---------------------------------------------------------------------------
# follow-up pins: all three rows, and the enveloped caller
# ---------------------------------------------------------------------------

def _write_row(bridge, row, error):
    """Run the call that writes ``row``, with that row's add raising ``error``.

    For the summary and action rows, the start row is written normally first.
    """
    if row == "start":
        bridge._synapse.add.side_effect = error
        return bridge.start_session("c1")
    sid = bridge.start_session("c1")
    if row == "summary":
        bridge.get_session(sid).commands_executed = 1  # no summary row at 0 commands
        bridge._synapse.add.side_effect = error
        return bridge.end_session(sid)
    bridge._synapse.add.side_effect = error
    return bridge.log_action("Executed: create_node", session_id=sid)


@pytest.mark.parametrize("row", ["summary", "action"])
def test_summary_and_action_rows_still_raise_ordinary_errors(bridge, row):
    # The start row's pin is test_tracker_still_raises_ordinary_errors.
    error = RuntimeError("store is down")

    with pytest.raises(RuntimeError) as caught:
        _write_row(bridge, row, error)

    assert caught.value is error


@pytest.mark.parametrize("row", ["start", "summary", "action"])
def test_each_row_logs_the_panic_with_its_traceback(bridge, caplog, row):
    panic = _rust_panic()

    with caplog.at_level(logging.ERROR, logger="synapse.session"):
        _write_row(bridge, row, panic)

    errors = _session_errors(caplog)
    assert len(errors) == 1, [r.getMessage() for r in caplog.records]
    assert f"session {row} row" in errors[0].getMessage()
    assert errors[0].exc_info is not None and errors[0].exc_info[1] is panic


def test_submit_logs_keeps_the_live_integrity_block_when_the_action_row_panics(
        bridge, monkeypatch):
    import synapse.server.handlers as handlers
    import synapse.server.main_thread as main_thread

    # record_live_block does nothing when shared.bridge cannot be imported.
    # Fail here rather than pass on a no-op.
    assert handlers._envelope._ENVELOPE_AVAILABLE
    sid = bridge.start_session("c1")
    bridge._synapse.add.side_effect = _rust_panic()

    handler = object.__new__(handlers.SynapseHandler)
    handler._bridge = bridge  # never None: _get_bridge() would open a real store
    handler._session_id = sid
    handler._user_id = "pytest"

    class _InlineExecutor:
        def submit(self, fn, *args, **kwargs):
            return fn(*args, **kwargs)

    audited, landed = [], []
    monkeypatch.setattr(handlers, "_log_executor", _InlineExecutor())
    # _do_log imports run_on_main from the module at call time.
    monkeypatch.setattr(main_thread, "run_on_main", lambda fn, *a, **k: fn())
    monkeypatch.setattr(handlers, "audit_log",
                        lambda: SimpleNamespace(log=lambda **entry: audited.append(entry)))
    # The block lands here instead of in the process-wide bridge trail.
    monkeypatch.setattr(handlers._envelope, "get_process_bridge",
                        lambda: SimpleNamespace(record_external_block=landed.append))

    handler._submit_logs("create_node", {"node": "/obj/x"}, {},
                         hash_before="aaaa", hash_after="bbbb", enveloped=True)

    assert bridge._synapse.add.call_args.kwargs["content"] == "Executed: create_node"
    assert [entry["operation"] for entry in audited] == ["create_node"]
    assert [(blk.operation_type, blk.execution_path) for blk in landed] == [
        ("create_node", "live")]
    assert (landed[0].scene_hash_before, landed[0].scene_hash_after) == ("aaaa", "bbbb")
