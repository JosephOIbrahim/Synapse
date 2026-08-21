"""Tests for synapse_checkpoint.py -- checkpoint and resume."""

import json
import sys
import os
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from synapse_planner import SubGoal, Plan, goal_hash
from synapse_checkpoint import (
    Checkpoint,
    save_checkpoint,
    load_latest_checkpoint,
    resume_from_checkpoint,
    list_checkpoints,
    prune_old_checkpoints,
    CHECKPOINT_DIR,
    MAX_MESSAGES,
)


# -- Fixtures ----------------------------------------------------------------


@pytest.fixture
def tmp_checkpoint_dir(tmp_path, monkeypatch):
    """Redirect CHECKPOINT_DIR to a temp directory."""
    import synapse_checkpoint
    monkeypatch.setattr(synapse_checkpoint, "CHECKPOINT_DIR", tmp_path)
    return tmp_path


def _make_plan(goal="Test goal"):
    """Create a minimal Plan for testing."""
    return Plan(
        goal=goal,
        sub_goals=[
            SubGoal(id="a", description="Step A", status="completed"),
            SubGoal(id="b", description="Step B", depends_on=["a"], status="pending"),
        ],
        created_at=100.0,
    )


def _make_checkpoint(goal="Test goal", messages=None):
    """Create a Checkpoint for testing."""
    plan = _make_plan(goal)
    return Checkpoint(
        plan=plan,
        messages=messages or [{"role": "user", "content": "hello"}],
        completed_goals=["a"],
        scene_snapshot={"hip_file": "test.hip", "fps": 24},
        timestamp=200.0,
    )


# -- Checkpoint data model tests ---------------------------------------------


def test_checkpoint_roundtrip(tmp_checkpoint_dir):
    """to_dict -> from_dict preserves all fields."""
    cp = _make_checkpoint()
    d = cp.to_dict()
    restored = Checkpoint.from_dict(d)
    assert restored.goal_hash == cp.goal_hash
    assert restored.plan.goal == cp.plan.goal
    assert len(restored.plan.sub_goals) == 2
    assert restored.completed_goals == sorted(cp.completed_goals)
    assert restored.scene_snapshot == cp.scene_snapshot
    assert restored.timestamp == cp.timestamp
    assert restored.messages == cp.messages


def test_checkpoint_sorted_keys(tmp_checkpoint_dir):
    """to_dict output has sorted keys (He2025)."""
    cp = _make_checkpoint()
    d = cp.to_dict()
    keys = list(d.keys())
    assert keys == sorted(keys)


def test_checkpoint_auto_goal_hash():
    """Checkpoint auto-computes goal_hash from plan."""
    cp = _make_checkpoint()
    assert cp.goal_hash == goal_hash("Test goal")


# -- save / load tests -------------------------------------------------------


def test_save_creates_file(tmp_checkpoint_dir):
    """save_checkpoint creates a JSONL file."""
    cp = _make_checkpoint()
    path = save_checkpoint(cp)
    assert path.exists()
    assert path.suffix == ".jsonl"
    assert path.parent == tmp_checkpoint_dir


def test_save_appends(tmp_checkpoint_dir):
    """Multiple saves append lines to the same file."""
    cp1 = _make_checkpoint()
    cp2 = _make_checkpoint()
    cp2.timestamp = 300.0

    save_checkpoint(cp1)
    save_checkpoint(cp2)

    path = tmp_checkpoint_dir / f"{cp1.goal_hash}.jsonl"
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    assert len(lines) == 2


def test_load_latest(tmp_checkpoint_dir):
    """load_latest_checkpoint returns the last checkpoint."""
    cp1 = _make_checkpoint()
    cp1.timestamp = 100.0
    cp2 = _make_checkpoint()
    cp2.timestamp = 200.0

    save_checkpoint(cp1)
    save_checkpoint(cp2)

    loaded = load_latest_checkpoint(cp1.goal_hash)
    assert loaded is not None
    assert loaded.timestamp == 200.0


def test_load_nonexistent(tmp_checkpoint_dir):
    """Returns None for nonexistent checkpoint."""
    loaded = load_latest_checkpoint("nonexistent_hash")
    assert loaded is None


def test_resume_returns_plan_and_messages(tmp_checkpoint_dir):
    """resume_from_checkpoint returns (plan, messages) tuple."""
    cp = _make_checkpoint()
    save_checkpoint(cp)

    result = resume_from_checkpoint(cp.goal_hash)
    assert result is not None
    plan, messages = result
    assert isinstance(plan, Plan)
    assert isinstance(messages, list)
    assert plan.goal == "Test goal"


# -- list_checkpoints tests --------------------------------------------------


def test_list_checkpoints(tmp_checkpoint_dir):
    """list_checkpoints returns sorted list with metadata."""
    cp1 = _make_checkpoint("Goal A")
    cp2 = _make_checkpoint("Goal B")
    save_checkpoint(cp1)
    save_checkpoint(cp2)

    cps = list_checkpoints()
    assert len(cps) == 2
    for cp_info in cps:
        assert "goal_hash" in cp_info
        assert "path" in cp_info
        assert "size_bytes" in cp_info
        assert "modified" in cp_info


def test_list_checkpoints_empty(tmp_checkpoint_dir):
    """Empty directory returns empty list."""
    assert list_checkpoints() == []


# -- prune tests -------------------------------------------------------------


def test_prune_old(tmp_checkpoint_dir):
    """prune_old_checkpoints deletes old files."""
    # Create a checkpoint file with an old mtime
    cp = _make_checkpoint()
    path = save_checkpoint(cp)

    # Set the file mtime to 10 days ago
    old_time = time.time() - (10 * 86400)
    os.utime(path, (old_time, old_time))

    deleted = prune_old_checkpoints(max_age_days=7)
    assert deleted == 1
    assert not path.exists()


def test_prune_keeps_recent(tmp_checkpoint_dir):
    """prune_old_checkpoints keeps recent files."""
    cp = _make_checkpoint()
    path = save_checkpoint(cp)

    deleted = prune_old_checkpoints(max_age_days=7)
    assert deleted == 0
    assert path.exists()


def test_prune_empty_dir(tmp_checkpoint_dir):
    """No crash on empty checkpoint directory."""
    assert prune_old_checkpoints() == 0


# -- message truncation test -------------------------------------------------


def test_messages_truncated(tmp_checkpoint_dir):
    """Only last MAX_MESSAGES are saved."""
    messages = [{"role": "user", "content": f"msg {i}"} for i in range(50)]
    cp = _make_checkpoint()
    cp.messages = messages
    save_checkpoint(cp)

    loaded = load_latest_checkpoint(cp.goal_hash)
    assert loaded is not None
    assert len(loaded.messages) == MAX_MESSAGES
    # Should be the LAST 20 messages
    assert loaded.messages[0]["content"] == "msg 30"
    assert loaded.messages[-1]["content"] == "msg 49"


# -- encoding test -----------------------------------------------------------


def test_utf8_encoding(tmp_checkpoint_dir):
    """Non-ASCII content is preserved through save/load."""
    cp = _make_checkpoint()
    cp.scene_snapshot = {"description": "Scene with em-dash \u2014 and umlaut \u00fc"}
    save_checkpoint(cp)

    loaded = load_latest_checkpoint(cp.goal_hash)
    assert loaded is not None
    assert "\u2014" in loaded.scene_snapshot["description"]
    assert "\u00fc" in loaded.scene_snapshot["description"]


# -- sorted keys in JSONL test -----------------------------------------------


def test_sorted_keys_in_jsonl(tmp_checkpoint_dir):
    """JSONL output has sorted keys at top level."""
    cp = _make_checkpoint()
    save_checkpoint(cp)

    path = tmp_checkpoint_dir / f"{cp.goal_hash}.jsonl"
    with open(path, "r", encoding="utf-8") as f:
        line = f.readline().strip()
    data = json.loads(line)
    keys = list(data.keys())
    assert keys == sorted(keys)
