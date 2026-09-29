"""BP12 item 18: an untitled scene's notes live beside its session's store.

Since item 1 each untitled launch keeps its memory store in
$HOUDINI_TEMP_DIR/untitled/sessions/<id>, but scene_memory still resolved the notes'
claude/ folder to the shared untitled root, so a new launch read an earlier launch's notes.
"""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from synapse.memory import scene_memory

lifecycle = pytest.importorskip("synapse.host.memory_lifecycle")


@pytest.fixture()
def temp_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HOUDINI_TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(lifecycle, "_unsaved_base", None)
    monkeypatch.setattr(scene_memory, "HOU_AVAILABLE", False)
    monkeypatch.setattr(scene_memory, "hou", None, raising=False)
    scene_memory._RELOCATED.clear()
    return tmp_path


def test_the_notes_base_is_a_session_folder_and_stays_put(temp_root):
    base = Path(scene_memory.unsaved_memory_base())
    assert base.parent == temp_root / "untitled" / "sessions"
    assert Path(scene_memory.unsaved_memory_base()) == base


def test_a_bound_session_owns_the_notes_folder(temp_root, monkeypatch):
    session = temp_root / "untitled" / "sessions" / "abc123"
    monkeypatch.setattr(lifecycle, "_unsaved_base", session)
    assert scene_memory.unsaved_memory_base() == os.path.normpath(str(session))
    hip = str(temp_root / "bin" / "untitled.hip")
    assert scene_memory.resolve_hip_dir(hip) == os.path.normpath(str(session))


def test_a_session_from_another_temp_root_is_replaced(temp_root, monkeypatch, tmp_path_factory):
    stale = tmp_path_factory.mktemp("other") / "untitled" / "sessions" / "old"
    monkeypatch.setattr(lifecycle, "_unsaved_base", stale)
    base = Path(scene_memory.unsaved_memory_base())
    assert base != stale
    assert base.is_relative_to(temp_root / "untitled" / "sessions")


def test_two_launches_get_two_notes_folders_that_match_their_stores(temp_root):
    hou = SimpleNamespace(hipFile=SimpleNamespace(path=lambda: str(temp_root / "untitled.hip")))
    first = lifecycle.current_binding(hou)
    assert Path(scene_memory.unsaved_memory_base()).resolve() == first.scene_dir
    lifecycle._unsaved_base = None      # the next launch
    second = lifecycle.current_binding(hou)
    assert Path(scene_memory.unsaved_memory_base()).resolve() == second.scene_dir
    assert first.scene_dir != second.scene_dir


def test_notes_written_before_any_binding_are_read_back_after_it(temp_root):
    """The hazard v1 of this change had: a session bound between a write and a read."""
    hip = str(temp_root / "bin" / "untitled.hip")
    paths = scene_memory.ensure_scene_structure(hip, str(temp_root / "bin"))
    scene_memory.write_memory_entry(paths["scene_dir"], {"content": "ARROW-IN-THE-KNEE"}, "note")
    lifecycle.current_binding(SimpleNamespace(hipFile=SimpleNamespace(path=lambda: hip)))
    ctx = scene_memory.load_full_context(scene_memory.resolve_hip_dir(hip), str(temp_root / "bin"))
    assert "ARROW-IN-THE-KNEE" in ctx["scene"]["content"]
