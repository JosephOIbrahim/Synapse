"""PUX-01b: the panel's conversation follows the scene.

The panel loads its conversation once and pins the file it came from, so a
File > Open can no longer make a later save write scene A's chat over scene
B's ``$HIP/claude/conversation.json`` (PUX-01). A pin on its own broke
Untitled -> Save As: the chat stayed in the untitled store and never reached
the saved scene. These pins drive the hipFile events the panel now listens to:

* Save As moves ``conversation.json``, its owner sidecar and
  ``conversation.previous.json`` into the new ``$HIP/claude/`` and re-pins.
* File > Open (BeforeLoad ... AfterLoad) and File > New (AfterClear) keep the
  chat in its own scene and load the new scene's conversation.
* A turn still running when the scene changes is saved to its own scene first.

Convention from ``tests/test_first_session_panel.py``: the real method source
is compiled from synapse_panel.py and called on a fake self. The panel module
is never imported (an import under the Qt stub leaves a stub-built
``synapse.panel.gate_widget`` behind for a later ``importorskip``).
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
                         AfterClear="AfterClear", AfterSave="AfterSave",
                         BeforeSave="BeforeSave")

CHAT_A = [{"role": "user", "content": "scene A question"},
          {"role": "assistant", "content": "scene A answer"}]
CHAT_B = [{"role": "user", "content": "scene B's own work"},
          {"role": "assistant", "content": "kept"}]
PARKED = [{"role": "user", "content": "an earlier boot"}]


def _panel_tree():
    return ast.parse(PANEL_SOURCE.read_text(encoding="utf-8"))


def _panel_methods(*names):
    cls = next(n for n in _panel_tree().body
               if isinstance(n, ast.ClassDef) and n.name == "SynapsePanel")
    namespace = {"logger": Mock(), "ClaudeWorker": object, "partial": partial,
                 "_remove_hip_callback": Mock()}
    for name in names:
        method = next(n for n in cls.body
                      if isinstance(n, ast.FunctionDef) and n.name == name)
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(PANEL_SOURCE), "exec"),
             namespace)
    return {name: namespace[name] for name in names}


_FOLLOW = ("_on_hip_event", "_follow_save_as", "_rebind_conversation",
           "_announce_parked", "_spatial_remember", "_on_error")


@pytest.fixture
def scenes(monkeypatch, tmp_path):
    """Real scene folders, a hou whose open scene can switch, and the event enum
    the panel reads from the resident hou."""
    launch = tmp_path / "launch"
    show_a = tmp_path / "showA"
    show_b = tmp_path / "showB"
    for folder in (launch, show_a, show_b):
        folder.mkdir()
    hips = {"untitled": launch / "untitled.hip", "A": show_a / "a.hip",
            "A2": show_a / "a_v002.hip", "B": show_b / "b.hip"}
    current = [str(hips["A"])]
    monkeypatch.setattr(session_store, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(session_store, "hou", SimpleNamespace(
        hipFile=SimpleNamespace(path=lambda: current[0])))
    monkeypatch.setattr(sys.modules["hou"], "hipFileEventType", EVENTS, raising=False)

    def open_scene(name):
        current[0] = str(hips[name])

    def store(name):
        return hips[name].parent / "claude" / "conversation.json"

    return SimpleNamespace(open=open_scene, store=store, hips=hips)


def _seed(path, messages, token=None):
    assert session_store.save_conversation(messages, path=str(path), token=token)


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _panel(messages):
    """A fake panel as __init__ leaves it: pinned to the scene open now."""
    methods = _panel_methods(*_FOLLOW)
    panel = SimpleNamespace(
        _messages=list(messages),
        _conversation_path=session_store.conversation_path(),
        _worker=None, _chat=Mock(), _parked_previous=False,
        _task_connection=None, _streaming_started=False, _stream_buf=[],
        _set_thinking=Mock(), _set_busy=Mock(), _refresh_token_surfaces=Mock(),
        _refresh_engine_selector=Mock())
    for name, fn in methods.items():
        setattr(panel, name, partial(fn, panel))
    return panel


# ------------------------------------------------------------------ Save As
def test_untitled_save_as_carries_the_chat_into_the_saved_scene(scenes):
    """The regression the first attempt had: a pin alone left the chat in the
    untitled store. Save As now moves all three files and re-pins."""
    scenes.open("untitled")
    untitled = scenes.store("untitled")
    _seed(untitled, CHAT_A)
    _seed(untitled.parent / "conversation.previous.json", PARKED)
    panel = _panel(CHAT_A)

    scenes.open("A")
    panel._on_hip_event(EVENTS.AfterSave)

    saved = scenes.store("A")
    assert panel._conversation_path == str(saved)
    assert _read(saved) == CHAT_A
    assert Path(str(saved) + ".owner.json").exists()
    assert _read(saved.parent / "conversation.previous.json") == PARKED
    assert not untitled.exists()
    assert not (untitled.parent / "conversation.previous.json").exists()
    assert not Path(str(untitled) + ".owner.json").exists()

    # The next turn lands in the saved scene, and reattaches there this boot.
    panel._spatial_remember("camera path drawn")
    assert len(_read(saved)) == 4
    messages, scope = session_store.load_conversation_scoped(path=str(saved))
    assert scope == "same_boot" and len(messages) == 4


def test_save_as_writes_the_chat_even_when_the_untitled_store_never_existed(scenes):
    """An untitled scene's store can be unwritable (the launch folder); the
    live chat still reaches the saved scene."""
    scenes.open("untitled")
    panel = _panel(CHAT_A)
    assert not scenes.store("untitled").exists()

    scenes.open("B")
    panel._on_hip_event(EVENTS.AfterSave)

    assert _read(scenes.store("B")) == CHAT_A
    assert panel._conversation_path == str(scenes.store("B"))


def test_a_plain_save_moves_nothing(scenes):
    _seed(scenes.store("A"), CHAT_A)
    before = scenes.store("A").read_bytes()
    panel = _panel(CHAT_A)
    pin = panel._conversation_path

    panel._on_hip_event(EVENTS.AfterSave)                 # Ctrl+S
    scenes.open("A2")
    panel._on_hip_event(EVENTS.AfterSave)                 # Save As, same folder

    assert panel._conversation_path == pin
    assert scenes.store("A").read_bytes() == before
    assert sorted(p.name for p in scenes.store("A").parent.iterdir()) == [
        "conversation.json", "conversation.json.owner.json"]


def test_save_as_into_a_folder_with_a_chat_parks_it_instead_of_overwriting(scenes):
    _seed(scenes.store("B"), CHAT_B)
    _seed(scenes.store("A"), CHAT_A)
    panel = _panel(CHAT_A)

    scenes.open("B")
    panel._on_hip_event(EVENTS.AfterSave)

    assert _read(scenes.store("B")) == CHAT_A
    assert _read(scenes.store("B").parent / "conversation.previous.json") == CHAT_B


# ---------------------------------------------------------------- File > Open
def test_file_open_rebinds_to_the_opened_scene(scenes):
    _seed(scenes.store("A"), CHAT_A)
    _seed(scenes.store("B"), CHAT_B)
    b_before = scenes.store("B").read_bytes()
    panel = _panel(CHAT_A)

    panel._on_hip_event(EVENTS.BeforeLoad)
    scenes.open("untitled")                               # the load clears first
    panel._on_hip_event(EVENTS.AfterClear)
    scenes.open("B")
    panel._on_hip_event(EVENTS.AfterLoad)

    assert panel._messages == CHAT_B
    assert panel._conversation_path == str(scenes.store("B"))
    assert scenes.store("B").read_bytes() == b_before
    assert _read(scenes.store("A")) == CHAT_A
    assert not scenes.store("untitled").parent.exists(), "the clear inside a load rebound"
    panel._chat.append_system_message.assert_called_once()

    # Closing or finishing a turn now saves to B, never back over A.
    panel._spatial_remember("camera path drawn")
    assert len(_read(scenes.store("B"))) == 4
    assert _read(scenes.store("A")) == CHAT_A


def test_an_empty_panel_does_not_erase_the_scene_it_opens(scenes):
    """The demo path from the review: the panel loads empty, File > Open the
    demo hip, then a save. The demo scene's chat survives and is loaded."""
    scenes.open("untitled")
    panel = _panel([])
    _seed(scenes.store("B"), CHAT_B)

    scenes.open("B")
    panel._on_hip_event(EVENTS.AfterLoad)
    panel._spatial_remember("camera path drawn")

    assert panel._messages[:2] == CHAT_B
    assert _read(scenes.store("B"))[:2] == CHAT_B


def test_opening_a_scene_from_an_earlier_boot_parks_it(scenes):
    _seed(scenes.store("B"), CHAT_B, token="an-earlier-boot")
    panel = _panel(CHAT_A)

    scenes.open("B")
    panel._on_hip_event(EVENTS.AfterLoad)

    assert panel._messages == []
    assert panel._parked_previous is True
    assert _read(scenes.store("B").parent / "conversation.previous.json") == CHAT_B
    assert "restore-session" in panel._chat.append_system_message.call_args[0][0]


def test_reopening_the_same_scene_keeps_the_chat(scenes):
    _seed(scenes.store("A"), CHAT_A)
    panel = _panel(CHAT_A + [{"role": "user", "content": "unsaved tail"}])

    panel._on_hip_event(EVENTS.BeforeLoad)
    panel._on_hip_event(EVENTS.AfterLoad)

    assert len(panel._messages) == 3
    panel._chat.append_system_message.assert_not_called()


def test_file_new_rebinds_to_the_untitled_store(scenes):
    _seed(scenes.store("A"), CHAT_A)
    panel = _panel(CHAT_A)

    scenes.open("untitled")
    panel._on_hip_event(EVENTS.AfterClear)

    assert panel._messages == []
    assert panel._conversation_path == str(scenes.store("untitled"))
    assert _read(scenes.store("A")) == CHAT_A


def test_file_open_during_a_turn_waits_for_the_turn(scenes):
    """The turn's answer belongs to the scene it was asked in."""
    _seed(scenes.store("A"), CHAT_A)
    _seed(scenes.store("B"), CHAT_B)
    b_before = scenes.store("B").read_bytes()
    panel = _panel(CHAT_A)
    finished = CHAT_A + [{"role": "user", "content": "q2"},
                         {"role": "assistant", "content": "a2"}]
    panel._worker = SimpleNamespace(get_terminal_messages=lambda: finished)

    scenes.open("B")
    panel._on_hip_event(EVENTS.AfterLoad)
    assert panel._messages == CHAT_A
    assert panel._conversation_path == str(scenes.store("A"))

    panel._on_error("network blip")                      # the turn ends

    assert _read(scenes.store("A")) == finished
    assert scenes.store("B").read_bytes() == b_before
    assert panel._messages == CHAT_B
    assert panel._conversation_path == str(scenes.store("B"))


def test_a_scene_event_never_raises(scenes, monkeypatch):
    panel = _panel(CHAT_A)
    monkeypatch.setattr(session_store, "load_conversation_scoped",
                        Mock(side_effect=OSError("disk gone")))
    scenes.open("B")

    panel._on_hip_event(EVENTS.AfterLoad)                 # logged, not raised

    assert panel._messages == CHAT_A


# ------------------------------------------------------------- session store
def test_move_conversation_same_folder_is_a_no_op(tmp_path):
    path = tmp_path / "claude" / "conversation.json"
    _seed(path, CHAT_A)
    assert session_store.move_conversation(str(path), str(path)) is False
    assert _read(path) == CHAT_A


def test_move_conversation_keeps_the_source_previous_when_the_slot_is_taken(tmp_path):
    src = tmp_path / "a" / "claude" / "conversation.json"
    dst = tmp_path / "b" / "claude" / "conversation.json"
    _seed(src, CHAT_A)
    _seed(src.parent / "conversation.previous.json", PARKED)
    _seed(dst, CHAT_B)

    assert session_store.move_conversation(str(src), str(dst)) is True

    assert _read(dst) == CHAT_A
    assert _read(dst.parent / "conversation.previous.json") == CHAT_B
    assert _read(src.parent / "conversation.previous.json") == PARKED


# ------------------------------------------------------------ panel wiring
def _calls(tree, attr):
    return [node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == attr]


def _enclosing(tree, target):
    best = None
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and any(n is target for n in ast.walk(fn)):
            if best is None or fn.lineno > best.lineno:
                best = fn
    return best.name if best else None


def test_every_panel_save_goes_through_the_pin():
    tree = _panel_tree()
    assert _calls(tree, "save_conversation") == [], "an unpinned save is back"
    sites = {_enclosing(tree, call) for call in _calls(tree, "save_conversation_pinned")}
    assert sites == {"_spatial_remember", "_on_done", "_on_error", "closeEvent",
                     "_follow_save_as", "_rebind_conversation"}


def test_the_panel_pins_at_load_listens_at_init_and_stops_at_close():
    tree = _panel_tree()
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SynapsePanel")
    body = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    init_calls = {c.func.attr for c in _calls(body["__init__"], "_register_hip_cb")}
    assert init_calls == {"_register_hip_cb"}
    assert any(isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
               and isinstance(n.value.func, ast.Attribute)
               and n.value.func.attr == "conversation_path"
               for n in ast.walk(body["__init__"]))
    closing = [n for n in ast.walk(body["closeEvent"])
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "_remove_hip_callback"]
    assert closing
    for done in ("_on_done", "_on_error"):
        assert _calls(body[done], "_rebind_conversation"), done
