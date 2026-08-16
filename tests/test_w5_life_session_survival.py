"""W5-LIFE (R.2) — session survival, headless-simulatable slice (target 3).

The g5 failure: close the panel, an operation finishes headless, reopen ->
"fresh runtime, no chat history". Root cause (mapped, file:line): the
conversation is ``self._messages`` on the panel widget (synapse_panel.py:335),
discarded on close; and the ``.pypanel`` loader flushes ``sys.modules[synapse.*]``
on every reopen, so even a module singleton would reset. The fix is a
disk-backed, HIP-keyed conversation store (``server/session_store.py``) that
survives BOTH the widget death and the module flush.

These pins exercise the parts that DON'T need a live Houdini GUI: the disk
round-trip, survival across a simulated module flush, per-scene keying,
freshness, corruption tolerance, and atomic-write hygiene. The GUI-only parts —
wiring closeEvent/__init__ and Joe's live close→reopen — are recorded UNKNOWN in
the receipt, never simulated into a pass.
"""

from __future__ import annotations

import importlib
import json
import sys

import pytest

from synapse.server import session_store as ss


_CONVO = [
    {"role": "user", "content": "make the rim light warmer"},
    {"role": "assistant", "content": [
        {"type": "text", "text": "On it — nudging the rim toward 3200K."},
        {"type": "tool_use", "id": "tu_1", "name": "houdini_set_parm",
         "input": {"path": "/stage/rim", "parm": "color_temp", "value": 3200}},
    ]},
    {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "tu_1", "content": "ok"}]},
]


def test_save_then_load_roundtrip(tmp_path):
    path = str(tmp_path / "conversation.json")
    assert ss.save_conversation(_CONVO, path=path) is True
    restored = ss.load_conversation(path=path)
    assert restored == _CONVO


def test_survives_simulated_module_flush_and_new_instance(tmp_path):
    """The reopen path: the pypanel loader deletes synapse.* from sys.modules and
    a brand-new panel is built. A DISK store survives that; a module global would
    not. Save, flush the module, re-import fresh, load -> same conversation."""
    path = str(tmp_path / "conversation.json")
    assert ss.save_conversation(_CONVO, path=path) is True

    # Simulate the loader's flush of the store module.
    for name in [m for m in list(sys.modules) if m.startswith("synapse.server.session_store")]:
        del sys.modules[name]
    fresh = importlib.import_module("synapse.server.session_store")
    assert fresh is not ss or "synapse.server.session_store" in sys.modules  # re-imported

    restored = fresh.load_conversation(path=path)
    assert restored == _CONVO


def test_fresh_scene_has_empty_history(tmp_path):
    path = str(tmp_path / "does_not_exist.json")
    assert ss.load_conversation(path=path) == []
    assert ss.has_conversation(path=path) is False


def test_corrupt_file_degrades_to_fresh_not_crash(tmp_path):
    path = tmp_path / "conversation.json"
    path.write_text("{ this is not valid json ][", encoding="utf-8")
    assert ss.load_conversation(path=str(path)) == []  # tolerated, no exception


def test_non_list_payload_degrades_to_fresh(tmp_path):
    path = tmp_path / "conversation.json"
    path.write_text(json.dumps({"role": "user"}), encoding="utf-8")  # a dict, not a list
    assert ss.load_conversation(path=str(path)) == []


def test_per_scene_keying_is_independent(tmp_path):
    """Two scenes (two paths) hold independent conversations — reopen restores
    the conversation for THIS scene, not a global one."""
    a = str(tmp_path / "scene_a" / "conversation.json")
    b = str(tmp_path / "scene_b" / "conversation.json")
    ss.save_conversation([{"role": "user", "content": "A"}], path=a)
    ss.save_conversation([{"role": "user", "content": "B"}], path=b)
    assert ss.load_conversation(path=a) == [{"role": "user", "content": "A"}]
    assert ss.load_conversation(path=b) == [{"role": "user", "content": "B"}]


def test_clear_conversation(tmp_path):
    path = str(tmp_path / "conversation.json")
    ss.save_conversation(_CONVO, path=path)
    assert ss.has_conversation(path=path) is True
    assert ss.clear_conversation(path=path) is True
    assert ss.load_conversation(path=path) == []
    assert ss.clear_conversation(path=path) is False  # already gone


def test_atomic_write_leaves_no_tmp(tmp_path):
    path = tmp_path / "conversation.json"
    assert ss.save_conversation(_CONVO, path=str(path)) is True
    assert path.exists()
    assert not (tmp_path / "conversation.json.tmp").exists()


def test_refuses_non_list_save(tmp_path):
    path = str(tmp_path / "conversation.json")
    assert ss.save_conversation({"not": "a list"}, path=path) is False  # type: ignore[arg-type]
    assert ss.load_conversation(path=path) == []


def test_overwrite_replaces_prior_conversation(tmp_path):
    path = str(tmp_path / "conversation.json")
    ss.save_conversation([{"role": "user", "content": "first"}], path=path)
    ss.save_conversation([{"role": "user", "content": "second"}], path=path)
    assert ss.load_conversation(path=path) == [{"role": "user", "content": "second"}]
