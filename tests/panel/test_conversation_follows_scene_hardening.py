"""PUX-01b hardening: the review findings on "the conversation follows the scene".

* F1 - two panels pinned to one scene both follow a Save As. The first carries
  the chat and the parked previous; the second used to find the first one's
  chat at the destination and park it over that previous, destroying it.
* F2 - a File > Open during a turn leaves the rebind pending; a Ctrl+S before
  the turn ends must not move the old scene's chat over the opened one.
* F3 - the hipFile callback really reaches the panel, and widget death really
  removes it.
* F4 - a load that never sends AfterLoad no longer keeps File > New from
  rebinding once a save proves the load is over.
* F5 - the rebind caps a stored history, and /restore-session restores into
  the pinned scene, not the one open now.

Same convention as ``test_conversation_follows_scene.py``: the real method
source is compiled from synapse_panel.py and run on a fake self. The panel
module is never imported and no SynapsePanel is built.
"""
from __future__ import annotations

import ast
import json
import sys
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import synapse.core.tool_results  # noqa: F401 -- imported before any hou patch
from synapse.server import session_store

PANEL_SOURCE = Path(__file__).resolve().parents[2] / "python/synapse/panel/synapse_panel.py"

EVENTS = SimpleNamespace(BeforeLoad="BeforeLoad", AfterLoad="AfterLoad",
                         BeforeClear="BeforeClear", AfterClear="AfterClear",
                         BeforeSave="BeforeSave", AfterSave="AfterSave")

CHAT_A = [{"role": "user", "content": "scene A question"},
          {"role": "assistant", "content": "scene A answer"}]
CHAT_B = [{"role": "user", "content": "scene B's own work"},
          {"role": "assistant", "content": "kept"}]
PARKED = [{"role": "user", "content": "an earlier boot"}]

_FOLLOW = ("_on_hip_event", "_follow_save_as", "_rebind_conversation",
           "_announce_parked", "_spatial_remember", "_on_error",
           "_restore_previous_session")


def _tree():
    return ast.parse(PANEL_SOURCE.read_text(encoding="utf-8"))


def _compile(nodes, namespace):
    exec(compile(ast.Module(body=list(nodes), type_ignores=[]), str(PANEL_SOURCE), "exec"),
         namespace)
    return namespace


def _panel_methods(*names, namespace=None):
    cls = next(n for n in _tree().body
               if isinstance(n, ast.ClassDef) and n.name == "SynapsePanel")
    ns = {"logger": Mock(), "ClaudeWorker": object, "partial": partial,
          "_remove_hip_callback": Mock()}
    ns.update(namespace or {})
    _compile([next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
              for name in names], ns)
    return {name: ns[name] for name in names}


@pytest.fixture(autouse=True)
def _fresh_carry_record(monkeypatch):
    monkeypatch.setattr(session_store, "_carried", {}, raising=False)


@pytest.fixture
def scenes(monkeypatch, tmp_path):
    launch, show_a, show_b = tmp_path / "launch", tmp_path / "showA", tmp_path / "showB"
    for folder in (launch, show_a, show_b):
        folder.mkdir()
    hips = {"untitled": launch / "untitled.hip", "A": show_a / "a.hip",
            "B": show_b / "b.hip"}
    current = [str(hips["A"])]
    monkeypatch.setattr(session_store, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(session_store, "hou", SimpleNamespace(
        hipFile=SimpleNamespace(path=lambda: current[0])))
    monkeypatch.setattr(sys.modules["hou"], "hipFileEventType", EVENTS, raising=False)

    def open_scene(name):
        current[0] = str(hips[name])

    def store(name):
        return hips[name].parent / "claude" / "conversation.json"

    return SimpleNamespace(open=open_scene, store=store)


def _seed(path, messages, token=None):
    assert session_store.save_conversation(messages, path=str(path), token=token)


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _prev(store):
    return store.parent / "conversation.previous.json"


def _panel(messages):
    """A fake panel as __init__ leaves it: pinned to the scene open now."""
    panel = SimpleNamespace(
        _messages=list(messages),
        _conversation_path=session_store.conversation_path(),
        _worker=None, _chat=Mock(), _parked_previous=False,
        _task_connection=None, _streaming_started=False, _stream_buf=[],
        _set_thinking=Mock(), _set_busy=Mock(), _refresh_token_surfaces=Mock(),
        _refresh_engine_selector=Mock())
    for name, fn in _panel_methods(*_FOLLOW).items():
        setattr(panel, name, partial(fn, panel))
    return panel


def _all_chats(*folders):
    """Every conversation file under the given store folders, by content."""
    found = []
    for folder in folders:
        if folder.exists():
            found += [_read(p) for p in folder.iterdir()
                      if p.name.startswith("conversation") and p.name.endswith(".json")
                      and not p.name.endswith(".owner.json")]
    return found


# ----------------------------------------------------------------------- F1
def test_two_panels_following_one_save_as_keep_the_parked_previous(scenes):
    """The reviewer's reproduction: panel 1 carries A's chat and previous to
    B; panel 2 must not then park panel 1's chat over that previous."""
    _seed(scenes.store("A"), CHAT_A)
    _seed(_prev(scenes.store("A")), PARKED)
    first, second = _panel(CHAT_A), _panel(CHAT_A)

    scenes.open("B")
    first._on_hip_event(EVENTS.AfterSave)
    second._on_hip_event(EVENTS.AfterSave)

    assert PARKED in _all_chats(scenes.store("A").parent, scenes.store("B").parent), \
        "the parked previous-boot chat was destroyed"
    assert _read(_prev(scenes.store("B"))) == PARKED
    assert _read(scenes.store("B")) == CHAT_A
    for panel in (first, second):
        assert panel._conversation_path == str(scenes.store("B"))


def test_two_untitled_panels_saving_into_a_folder_with_a_chat_keep_it(scenes):
    """Same class from an untitled scene whose store was never written: the
    first panel parks the destination's chat; the second must not bury it."""
    _seed(scenes.store("B"), CHAT_B)
    scenes.open("untitled")
    first, second = _panel(CHAT_A), _panel(CHAT_A)

    scenes.open("B")
    first._on_hip_event(EVENTS.AfterSave)
    second._on_hip_event(EVENTS.AfterSave)

    assert _read(_prev(scenes.store("B"))) == CHAT_B
    assert _read(scenes.store("B")) == CHAT_A


def test_an_empty_untitled_save_as_into_a_folder_with_a_chat_parks_it(scenes):
    """Why F1 is not fixed by 'nothing to carry -> do nothing': an empty
    untitled panel has never written its store, and its Save As must still
    park the folder's chat rather than let the follow-up save write [] over it."""
    _seed(scenes.store("B"), CHAT_B)
    scenes.open("untitled")
    panel = _panel([])

    scenes.open("B")
    panel._on_hip_event(EVENTS.AfterSave)

    assert _read(_prev(scenes.store("B"))) == CHAT_B


def test_a_panel_bound_afresh_to_a_carried_store_is_not_a_follower(scenes, tmp_path):
    """The carry record ends when a panel binds to the source store again: an
    empty panel that reopens A after A's chat left, then Save As into B, parks
    B's chat as any Save As does."""
    _seed(scenes.store("A"), CHAT_A)
    first = _panel(CHAT_A)
    scenes.open("B")
    first._on_hip_event(EVENTS.AfterSave)            # A -> B, recorded
    assert not scenes.store("A").exists()

    scenes.open("A")
    late = _panel([])
    session_store.load_conversation_scoped()          # what __init__ / a rebind does
    scenes.open("B")
    late._on_hip_event(EVENTS.AfterSave)

    assert _read(_prev(scenes.store("B"))) == CHAT_A


def test_move_conversation_second_follower_changes_nothing(tmp_path):
    src = tmp_path / "a" / "claude" / "conversation.json"
    dst = tmp_path / "b" / "claude" / "conversation.json"
    _seed(src, CHAT_A)
    _seed(_prev(src), PARKED)

    assert session_store.move_conversation(str(src), str(dst)) is True
    _seed(dst, CHAT_A + [{"role": "user", "content": "panel 1 kept going"}])
    assert session_store.move_conversation(str(src), str(dst)) is False

    assert _read(_prev(dst)) == PARKED
    assert len(_read(dst)) == 3


# ----------------------------------------------------------------------- F2
def test_ctrl_s_while_a_file_open_waits_for_the_turn_moves_nothing(scenes):
    """File > Open B during a turn, then Ctrl+S before the turn ends: the
    pending rebind keeps A's chat from moving over B's and parking it."""
    _seed(scenes.store("A"), CHAT_A)
    _seed(scenes.store("B"), CHAT_B)
    a_before = scenes.store("A").read_bytes()
    b_before = scenes.store("B").read_bytes()
    panel = _panel(CHAT_A)
    panel._worker = SimpleNamespace(get_terminal_messages=lambda: CHAT_A)

    panel._on_hip_event(EVENTS.BeforeLoad)
    scenes.open("B")
    panel._on_hip_event(EVENTS.AfterLoad)
    panel._on_hip_event(EVENTS.BeforeSave)
    panel._on_hip_event(EVENTS.AfterSave)              # Ctrl+S on B, turn still running

    assert scenes.store("B").read_bytes() == b_before
    assert not _prev(scenes.store("B")).exists()
    assert scenes.store("A").read_bytes() == a_before
    assert panel._conversation_path == str(scenes.store("A"))

    panel._on_error("network blip")                    # the turn ends, then the rebind
    assert panel._messages == CHAT_B
    assert panel._conversation_path == str(scenes.store("B"))


# ----------------------------------------------------------------------- F3
def test_the_registered_hip_callback_reaches_the_panel_and_dies_with_it(monkeypatch):
    tree = _tree()
    helper = next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == "_remove_hip_callback")
    ns = _compile([helper], {"logger": Mock()})
    register = _panel_methods("_register_hip_cb", namespace={
        "_remove_hip_callback": ns["_remove_hip_callback"]})["_register_hip_cb"]

    hip_file = SimpleNamespace(addEventCallback=Mock(), removeEventCallback=Mock())
    monkeypatch.setattr(sys.modules["hou"], "hipFile", hip_file, raising=False)
    on_destroyed = []
    panel = SimpleNamespace(destroyed=SimpleNamespace(connect=on_destroyed.append),
                            _on_hip_event=Mock())

    register(panel)

    hip_file.addEventCallback.assert_called_once()
    callback = hip_file.addEventCallback.call_args[0][0]
    assert callback is panel._hip_cb
    callback(EVENTS.AfterLoad)
    panel._on_hip_event.assert_called_once_with(EVENTS.AfterLoad)

    assert on_destroyed, "nothing removes the callback when the widget dies"
    hip_file.removeEventCallback.assert_not_called()
    for slot in on_destroyed:
        slot(object())                                 # Qt passes the dying QObject
    hip_file.removeEventCallback.assert_called_once_with(callback)


# ----------------------------------------------------------------------- F4
def test_file_new_after_an_open_rebinds(scenes):
    """AfterLoad ends the load, so the next File > New rebinds."""
    _seed(scenes.store("A"), CHAT_A)
    panel = _panel(CHAT_A)

    panel._on_hip_event(EVENTS.BeforeLoad)
    panel._on_hip_event(EVENTS.AfterLoad)              # reopen A: nothing to change
    scenes.open("untitled")
    panel._on_hip_event(EVENTS.AfterClear)             # File > New

    assert panel._conversation_path == str(scenes.store("untitled"))
    assert panel._messages == []


def test_a_save_ends_a_load_that_never_sent_after_load(scenes):
    """A load that failed or was cancelled leaves BeforeLoad without its
    AfterLoad. A save proves the load is over, so File > New rebinds again."""
    _seed(scenes.store("A"), CHAT_A)
    panel = _panel(CHAT_A)

    panel._on_hip_event(EVENTS.BeforeLoad)             # the load dies here
    panel._on_hip_event(EVENTS.AfterSave)              # Ctrl+S on A
    scenes.open("untitled")
    panel._on_hip_event(EVENTS.AfterClear)             # File > New

    assert panel._conversation_path == str(scenes.store("untitled"))
    assert _read(scenes.store("A")) == CHAT_A


# ----------------------------------------------------------------------- F5
def test_the_rebind_caps_a_stored_history(scenes):
    huge = "x" * (synapse.core.tool_results._MAX_TOOL_RESULT_CHARS + 5000)
    stored = [{"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": huge}]}]
    _seed(scenes.store("B"), stored)
    panel = _panel(CHAT_A)

    scenes.open("B")
    panel._on_hip_event(EVENTS.AfterLoad)

    kept = panel._messages[0]["content"][0]["content"]
    assert len(kept) < len(huge)
    assert "SYNAPSE kept the first" in kept


def test_restore_session_restores_into_the_pinned_scene(scenes):
    """/restore-session brings back the previous of the scene the chat is
    pinned to, even after hou already points at another scene."""
    _seed(_prev(scenes.store("A")), PARKED)
    _seed(_prev(scenes.store("B")), CHAT_B)
    panel = _panel([])
    scenes.open("B")                                   # pin still A

    panel._restore_previous_session()

    assert panel._messages == PARKED
    assert _read(scenes.store("A")) == PARKED
    assert _read(_prev(scenes.store("B"))) == CHAT_B
    assert not scenes.store("B").exists()
