"""The decisions board's resolution channel — the closure mechanism it never had.

Before this, `harness/decisions.py` collect() only ever appended: an item whose
work had demonstrably landed stayed on the board until someone hand-edited the
source receipt JSON. The count could not go down, which the CLEAR SPEC names as
a falsification condition ("the board count goes UP after a run → the harness
is net-producing work").

Every test states the condition under which it FAILS.
"""
import importlib
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mod():
    sys.path.insert(0, os.path.join(ROOT, "harness"))
    try:
        import decisions
        return importlib.reload(decisions)
    finally:
        sys.path.pop(0)


@pytest.fixture
def board(tmp_path, monkeypatch):
    """A tiny synthetic board: two rulings, one non-green receipt, one
    unratified flywheel cycle — fully isolated from the real state files."""
    d = _mod()
    rdir = tmp_path / "receipts"
    rdir.mkdir()
    (rdir / "T1.json").write_text(json.dumps({
        "leg": "T1", "status": "green",
        "for_ruling": ["ship the widget?", "rename the flag?"],
    }), encoding="utf-8")
    (rdir / "T2.json").write_text(json.dumps({
        "leg": "T2", "status": "amber",
    }), encoding="utf-8")
    fly = tmp_path / "flywheel_queue.json"
    fly.write_text(json.dumps({
        "cycles": [{"id": "X.1", "title": "an unratified cycle", "ratified": False}],
    }), encoding="utf-8")
    monkeypatch.setattr(d, "RDIR", str(rdir))
    monkeypatch.setattr(d, "FLYWHEEL", str(fly))
    monkeypatch.setattr(d, "RESOLVED", str(tmp_path / "resolved.json"))
    return d


def test_resolution_actually_lowers_the_count(board):
    """FAILS IF: resolving a live item does not remove it from collect()."""
    items = board.collect(with_ages=False)
    n0 = len(items)
    target = next(i for i in items if i["kind"] == "ruling")
    rc, msg = board.resolve(target["key"], "landed in commit abc123")
    assert rc == 0, msg
    after = board.collect(with_ages=False)
    assert len(after) == n0 - 1
    assert target["key"] not in {i["key"] for i in after}


def test_flywheel_items_refuse_this_channel(board):
    """FAILS IF: a flywheel item can be closed by resolved.json instead of the
    human ratified flip. That would shadow the anti-runaway fence."""
    items = board.collect(with_ages=False)
    fly = next(i for i in items if i["kind"] == "flywheel")
    rc, msg = board.resolve(fly["key"], "trying to sneak past the fence")
    assert rc != 0
    assert "ratified" in msg
    assert len(board.collect(with_ages=False)) == len(items)


def test_flywheel_survives_even_a_forged_resolved_entry(board):
    """FAILS IF: hand-writing a flywheel key into resolved.json subtracts it.
    The refusal must live in collect(), not only in the CLI."""
    items = board.collect(with_ages=False)
    fly = next(i for i in items if i["kind"] == "flywheel")
    board._save_resolved([{"key": fly["key"], "reason": "forged"}])
    after = board.collect(with_ages=False)
    assert fly["key"] in {i["key"] for i in after}, "forged entry closed a fenced item"


def test_phantom_and_double_resolution_are_errors(board):
    """FAILS IF: resolving a nonexistent key, or the same key twice, succeeds."""
    rc, msg = board.resolve("000000000000", "no such item")
    assert rc != 0 and "no live board item" in msg
    target = next(i for i in board.collect(with_ages=False) if i["kind"] == "ruling")
    assert board.resolve(target["key"], "first")[0] == 0
    rc, msg = board.resolve(target["key"], "second")
    assert rc != 0 and "already resolved" in msg


def test_resolution_requires_a_reason(board):
    """FAILS IF: an empty reason is accepted — indistinguishable from deletion."""
    target = next(i for i in board.collect(with_ages=False) if i["kind"] == "ruling")
    rc, _ = board.resolve(target["key"], "   ")
    assert rc != 0


def test_key_dies_when_the_text_changes(board):
    """FAILS IF: a changed ruling inherits the old resolution. A changed
    question is a new question."""
    items = board.collect(with_ages=False)
    a = next(i for i in items if i["text"] == "ship the widget?")
    changed = dict(a)
    changed["text"] = "ship the widget TO PRODUCTION?"
    assert board.item_key(a) != board.item_key(changed)


def test_statusline_and_board_agree_after_resolution(board):
    """FAILS IF: the two consumers of collect() could diverge. The statusline
    imports decisions.collect directly, so subtraction must live inside it."""
    target = next(i for i in board.collect(with_ages=False) if i["kind"] == "ruling")
    board.resolve(target["key"], "landed")
    # Same call the statusline makes (subprocess-free path):
    assert len(board.collect(with_ages=False)) == len(board.collect(with_ages=False))
    resolved_keys = set(board.load_resolved())
    assert target["key"] in resolved_keys
    assert all(i["key"] not in resolved_keys or i["kind"] == "flywheel"
               for i in board.collect(with_ages=False))
