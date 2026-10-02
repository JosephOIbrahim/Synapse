"""D6 / R-10, R-11: the Spatial control and /spatial, driven against fake Qt leaves.

The ``test_identify_button`` convention: the REAL ``SynapsePanel`` handlers run
as unbound methods on a fake self, with no QApplication and no Houdini, so the
production wiring is what is pinned. Thread placement is asserted with real
thread identities through a marshaller that runs ``run_on_main`` closures on
the test's main thread.

What a click must do, and what it must never do:
  * run ``synapse_spatial_trail`` OFF the Qt thread, and show its result ON it;
  * never reach the model send path;
  * answer with the tool's sentence, signed as answered with no model request;
  * leave a receipt when, and only when, the scene changed, measured against
    undo snapshots taken before and after;
  * refuse, with a reason, while a task is running;
  * show the tool's own reason when nothing was drawn (UNKNOWN included);
  * give the model's history the click as one ask-and-answer pair.
"""
from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qt_stub_window import qt_stub_window  # noqa: E402

with qt_stub_window():
    from synapse.panel import synapse_panel as sp  # noqa: E402
    from synapse.panel.synapse_panel import SynapsePanel  # noqa: E402
    from synapse.panel.tool_palette import _load_entries  # noqa: E402
    from synapse.panel.command_palette import (  # noqa: E402
        PANEL_ANSWERED_COMMANDS, PANEL_ROW_ORDER, PANEL_ROW_TITLES)

from synapse.panel import spatial_action, turn_revert  # noqa: E402

OUTCOME = ("demo_cam: an arc of radius 6.00 m through 20.0 deg, 2.09 m of travel at a stage "
           "height of 1.29 m; the nearest splat centre comes to 1.04 m, left of the lens, at "
           "frame 1. Drew the path as /guides/demo_cam_path (proxy purpose, 144 points).")
CREATED = {"status": "SUCCESS", "outcome": OUTCOME, "trail": {"status": "created"},
           "undo": {"artist": "One Ctrl+Z reverses: spatial trail"}}
TRAIL_LABEL = "SYNAPSE: synapse_spatial_trail: {}"


class _Chat:
    def __init__(self):
        self.system, self.synapse = [], []

    def append_system_message(self, text, *a, **k):
        self.system.append(text)

    def append_synapse_message(self, content, signed=None):
        self.synapse.append((content, signed))


class _Undos:
    """hou.undos as turn_revert reads it: labels, next-to-undo first."""
    def __init__(self, labels=()):
        self.labels = list(labels)

    def areEnabled(self):
        return True

    def undoLabels(self):
        return tuple(self.labels)

    def performUndo(self):
        self.labels.pop(0)


def _panel(undos=None, **attrs):
    """A fake self that delegates the Spatial methods back to the real unbound
    ``SynapsePanel`` implementations, with the leaves a test supplies."""
    receipt = {"shown": None, "hidden": 0}
    fake = SimpleNamespace(
        _chat=_Chat(), _worker=None, _messages=[], _receipt=receipt,
        _show_turn_receipt=lambda count: receipt.update(shown=count),
        _hide_turn_receipt=lambda: receipt.update(hidden=receipt["hidden"] + 1, shown=None),
        _prepare_connection=Mock(side_effect=AssertionError("reached the model send path")),
        _turn_undo_before="unset", _turn_undo_after="unset",
    )
    fake.__dict__.update(attrs)
    for name in ("_spatial_say", "_run_spatial", "_spatial_worker", "_spatial_done",
                 "_spatial_remember", "_on_spatial"):
        if name not in attrs:
            setattr(fake, name, (lambda n: lambda *a, **k: getattr(SynapsePanel, n)(fake, *a, **k))(name))
    return fake


def _inline(fake, call):
    """Run the whole click on this thread: launch and marshal are identity."""
    fake._spatial_launch = lambda fn: fn()
    fake._spatial_run_on_main = lambda fn: fn()
    fake._spatial_call = call
    return fake


def _patch_undos(monkeypatch, undos):
    monkeypatch.setattr(turn_revert, "hou_undos", lambda: undos)


@pytest.fixture(autouse=True)
def saved(monkeypatch):
    """Every conversation save in this file lands here, never on disk."""
    from synapse.server import session_store
    writes = []
    monkeypatch.setattr(session_store, "save_conversation",
                        lambda messages, *a, **k: writes.append(list(messages)))
    return writes


# --------------------------------------------------------------------------- #
# The registry: /spatial is declared once and answered by the panel.
# --------------------------------------------------------------------------- #

def test_spatial_is_panel_answered_and_appears_exactly_once():
    assert "/spatial" in PANEL_ANSWERED_COMMANDS
    assert PANEL_ROW_ORDER[-1] == "/spatial"
    assert PANEL_ROW_TITLES["/spatial"] == "Read the shot and draw the camera path"
    rows = [r for r in _load_entries() if r.get("send") == "/spatial"]
    assert len(rows) == 1, rows
    assert rows[0].get("panel_answered") is True and rows[0].get("group") == "PANEL"


def test_send_spatial_runs_locally_and_never_reaches_the_model():
    for text in ("/spatial", " /SPATIAL "):
        fake = SimpleNamespace(
            _run_spatial=Mock(return_value=True), _run_identify=Mock(),
            _prepare_connection=Mock(side_effect=AssertionError("reached model send")),
            _chat=_Chat(), _worker=None)
        assert SynapsePanel._send(fake, text) is True
        fake._run_spatial.assert_called_once_with()
        fake._prepare_connection.assert_not_called()
    # A refused read keeps the draft: _send reports what _run_spatial returned.
    refused = SimpleNamespace(_run_spatial=Mock(return_value=False), _chat=_Chat(), _worker=None,
                              _prepare_connection=Mock(side_effect=AssertionError("model")))
    assert SynapsePanel._send(refused, "/spatial") is False


# --------------------------------------------------------------------------- #
# A click: the tool's sentence, a receipt, the history pair, no model.
# --------------------------------------------------------------------------- #

def test_a_click_answers_with_the_tools_sentence_and_leaves_a_receipt(monkeypatch, saved):
    undos = _Undos(["Change Selection"])
    _patch_undos(monkeypatch, undos)

    def call():
        undos.labels.insert(0, TRAIL_LABEL)          # the bridge's one undo step
        return CREATED, None

    fake = _inline(_panel(), call)
    assert SynapsePanel._run_spatial(fake) is True

    text = spatial_action.answer_text(CREATED)
    assert fake._chat.synapse == [(text, spatial_action.SIGNED)]
    assert text.startswith(OUTCOME) and "One Ctrl+Z reverses" in text
    assert fake._chat.system == []                   # no notice beside a good answer
    assert fake._receipt["shown"] == 1               # one change, one receipt
    # The snapshots are what REVERT measures the click against.
    assert fake._turn_undo_before == ("Change Selection",)
    assert fake._turn_undo_after == (TRAIL_LABEL, "Change Selection")
    assert fake._spatial_running is False
    fake._prepare_connection.assert_not_called()
    # History: one ask-and-answer pair, saved as _on_done saves a turn.
    assert [m["role"] for m in fake._messages] == ["user", "assistant"]
    assert fake._messages[0]["content"] == spatial_action.HISTORY_ASK
    assert fake._messages[1]["content"] == text + spatial_action.HISTORY_NOTE
    assert saved and saved[-1] == fake._messages


def test_revert_undoes_exactly_the_clicks_step(monkeypatch):
    """The receipt's REVERT is turn_revert on the click's two snapshots: it
    removes the trail's step and leaves the artist's own step alone."""
    undos = _Undos(["Change Selection"])
    _patch_undos(monkeypatch, undos)

    def call():
        undos.labels.insert(0, TRAIL_LABEL)
        return CREATED, None

    fake = _inline(_panel(), call)
    SynapsePanel._run_spatial(fake)
    ok, message = turn_revert.revert_turn(undos, fake._turn_undo_before, fake._turn_undo_after)
    assert ok is True, message
    assert undos.labels == ["Change Selection"]
    # ...and it refuses once the artist has done something of their own on top.
    undos.labels.insert(0, TRAIL_LABEL)
    undos.labels.insert(0, "Move Node")
    ok, message = turn_revert.revert_turn(undos, fake._turn_undo_before, fake._turn_undo_after)
    assert ok is False and "Move Node" in message
    assert undos.labels[0] == "Move Node"


def test_an_unchanged_trail_answers_but_leaves_no_receipt(monkeypatch):
    undos = _Undos([TRAIL_LABEL])
    _patch_undos(monkeypatch, undos)
    unchanged = {"outcome": "demo_cam: an arc. The path is already drawn as /guides/demo_cam_path.",
                 "trail": {"status": "unchanged"}}
    fake = _inline(_panel(), lambda: (unchanged, None))
    assert SynapsePanel._run_spatial(fake) is True
    assert fake._chat.synapse == [(unchanged["outcome"], spatial_action.SIGNED)]
    assert fake._receipt["shown"] is None            # nothing new on the undo stack
    assert fake._turn_undo_before == fake._turn_undo_after == (TRAIL_LABEL,)


def test_an_unknown_move_shows_the_tools_reason_and_no_receipt(monkeypatch, saved):
    _patch_undos(monkeypatch, _Undos([]))
    reason = ("No trail drawn: no Camera LOP at or upstream of /stage/out authors /cameras/cam, "
              "so its move can't be read without moving the playhead")
    fake = _inline(_panel(), lambda: (None, reason))
    assert SynapsePanel._run_spatial(fake) is True   # the read started; it found UNKNOWN
    assert fake._chat.system == ["Spatial: " + reason]
    assert fake._chat.synapse == []                  # never an answer that was not measured
    assert fake._receipt["shown"] is None
    assert fake._messages == [] and saved == []      # nothing for the model to repeat
    assert fake._spatial_running is False


def test_a_call_that_raises_is_reported_and_frees_the_control(monkeypatch):
    _patch_undos(monkeypatch, _Undos([]))

    def call():
        raise RuntimeError("bridge fell over")

    fake = _inline(_panel(), call)
    assert SynapsePanel._run_spatial(fake) is True
    assert fake._chat.system == ["Spatial: RuntimeError: bridge fell over"]
    assert fake._receipt["shown"] is None and fake._spatial_running is False


def test_a_result_that_never_reaches_the_qt_thread_still_frees_the_control(monkeypatch):
    _patch_undos(monkeypatch, _Undos([]))
    fake = _panel()
    fake._spatial_launch = lambda fn: fn()
    fake._spatial_call = lambda: (CREATED, None)

    def broken_marshal(fn):
        raise TimeoutError("main thread did not answer")

    fake._spatial_run_on_main = broken_marshal
    assert SynapsePanel._run_spatial(fake) is True
    assert fake._spatial_running is False            # the next click is not refused forever
    assert fake._chat.synapse == [] and fake._receipt["shown"] is None


# --------------------------------------------------------------------------- #
# Refusals: a running task, and a read already in flight.
# --------------------------------------------------------------------------- #

def test_a_click_during_a_running_task_is_refused_with_the_reason(monkeypatch):
    _patch_undos(monkeypatch, _Undos([]))
    launched = []
    busy = SimpleNamespace(isRunning=lambda: True)
    fake = _panel(_worker=busy, _spatial_launch=lambda fn: launched.append(fn))
    assert SynapsePanel._run_spatial(fake) is False
    assert launched == []
    assert fake._chat.system == [spatial_action.BUSY]
    # The running turn's own snapshots are untouched.
    assert fake._turn_undo_before == "unset" and fake._turn_undo_after == "unset"
    assert fake._receipt["hidden"] == 0


def test_a_task_on_another_panel_refuses_it_too(monkeypatch):
    _patch_undos(monkeypatch, _Undos([]))
    monkeypatch.setattr(sp, "_ACTIVE_PANEL_WORKERS", [object()])   # truthy: a task is bound
    launched = []
    fake = _panel(_spatial_launch=lambda fn: launched.append(fn))
    assert SynapsePanel._run_spatial(fake) is False
    assert launched == [] and fake._chat.system == [spatial_action.BUSY]


def test_a_second_click_while_one_is_reading_is_refused(monkeypatch):
    _patch_undos(monkeypatch, _Undos([]))
    launched = []
    fake = _panel(_spatial_launch=lambda fn: launched.append(fn))
    assert SynapsePanel._run_spatial(fake) is True   # launched, not yet finished
    assert SynapsePanel._run_spatial(fake) is False
    assert len(launched) == 1
    assert fake._chat.system == [spatial_action.RUNNING]


def test_a_worker_object_without_isrunning_is_not_a_running_task(monkeypatch):
    """Seat tests park a bare namespace on _worker; that must not read as busy."""
    _patch_undos(monkeypatch, _Undos([]))
    fake = _inline(_panel(_worker=SimpleNamespace(abort=lambda: None)), lambda: (CREATED, None))
    assert SynapsePanel._run_spatial(fake) is True
    assert fake._chat.synapse


# --------------------------------------------------------------------------- #
# History: only onto a conversation that ends on an answer.
# --------------------------------------------------------------------------- #

def test_history_is_not_written_onto_an_unanswered_user_message(monkeypatch):
    _patch_undos(monkeypatch, _Undos([]))
    pending = [{"role": "user", "content": "half a turn"}]
    fake = _inline(_panel(_messages=list(pending)), lambda: (CREATED, None))
    SynapsePanel._run_spatial(fake)
    assert fake._messages == pending                 # two user messages in a row are refused
    assert fake._chat.synapse                        # the artist still gets the answer


def test_history_follows_an_earlier_answer(monkeypatch):
    _patch_undos(monkeypatch, _Undos([]))
    earlier = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hey."}]
    fake = _inline(_panel(_messages=list(earlier)), lambda: (CREATED, None))
    SynapsePanel._run_spatial(fake)
    assert [m["role"] for m in fake._messages] == ["user", "assistant", "user", "assistant"]
    assert fake._messages[:2] == earlier


# --------------------------------------------------------------------------- #
# Threads: the tool call runs OFF the Qt thread, the result lands ON it.
# --------------------------------------------------------------------------- #

def test_the_call_runs_off_main_and_the_result_is_shown_on_main(monkeypatch):
    _patch_undos(monkeypatch, _Undos([]))
    main_ident = threading.get_ident()
    record: dict = {}
    marshalled: "queue.Queue" = queue.Queue()

    def fake_run_on_main(fn):
        done = threading.Event()
        box: dict = {}

        def job():
            box["result"] = fn()
            done.set()

        marshalled.put(job)
        assert done.wait(5), "run_on_main closure was never drained"
        return box["result"]

    def fake_launch(fn):
        worker = threading.Thread(target=fn, daemon=True)
        worker.start()
        while worker.is_alive() or not marshalled.empty():
            try:
                marshalled.get(timeout=0.05)()
            except queue.Empty:
                continue
        worker.join(5)

    def call():
        record["call_ident"] = threading.get_ident()
        return CREATED, None

    fake = _panel(_spatial_launch=fake_launch, _spatial_run_on_main=fake_run_on_main, _spatial_call=call)
    real_done = fake._spatial_done

    def spy_done(result, error):
        record["done_ident"] = threading.get_ident()
        return real_done(result, error)

    fake._spatial_done = spy_done
    assert SynapsePanel._run_spatial(fake) is True
    assert record["call_ident"] != main_ident        # waiting on Houdini never blocks Qt
    assert record["done_ident"] == main_ident        # chat and receipt are Qt work
    assert fake._chat.synapse and fake._receipt["shown"] == 1
