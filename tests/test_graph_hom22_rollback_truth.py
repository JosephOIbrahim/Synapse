"""HOM-22: a sentinel-hash rollback whose performUndo() raised must not be
recorded as "rolled_back"."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import shared.bridge as b  # noqa: E402
from shared.bridge import LosslessExecutionBridge  # noqa: E402


def _fake_hou(raises: bool):
    def perform_undo():
        if raises:
            raise RuntimeError("undo stack empty")

    return SimpleNamespace(undos=SimpleNamespace(performUndo=perform_undo))


def _run(monkeypatch, raises: bool):
    monkeypatch.setattr(b, "hou", _fake_hou(raises), raising=False)
    bridge = LosslessExecutionBridge()
    integrity = SimpleNamespace(scene_hash_before="", delta_hash="")
    note = bridge._guarded_rollback(integrity, "/obj")
    return integrity, note


def test_undo_raised_is_rollback_incomplete(monkeypatch):
    integrity, note = _run(monkeypatch, raises=True)
    assert integrity.delta_hash == "rollback_incomplete"
    assert note and "manual review" in note


def test_undo_returned_is_rolled_back(monkeypatch):
    integrity, note = _run(monkeypatch, raises=False)
    assert integrity.delta_hash == "rolled_back"
    assert note is None
