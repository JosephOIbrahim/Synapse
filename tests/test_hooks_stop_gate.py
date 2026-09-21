"""BP9-STOPGATE: Stop and TaskCompleted exit 2 on an unresolved cook error.

Every test drives .claude/hooks/synapse_hooks_bridge.py as a real subprocess
with a crafted events file. SYNAPSE_HOOKS_EVENTS_DIR points the hook at a
temp dir (no test touches %TEMP%/synapse_hooks); SYNAPSE_HOOKS_LEDGER points
the ledger at a temp path.

Referee contract:
    exit 2 ONLY on Stop / TaskCompleted with a non-empty unresolved set
    missing events file -> exit 0, never a false block
    UserPromptSubmit never exits 2
    hook stays under 100 ms on the no-error path
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / ".claude" / "hooks" / "synapse_hooks_bridge.py"
UNRESOLVED_NAME = ".unresolved_cook_errors.json"


def _run(event: str, events_dir: Path, ledger: Path, prompt: str | None = None):
    env = dict(os.environ)
    env["SYNAPSE_HOOKS_EVENTS_DIR"] = str(events_dir)
    env["SYNAPSE_HOOKS_LEDGER"] = str(ledger)
    env.pop("CLAUDE_HOOK_EVENT", None)
    payload = {"hook_event_name": event, "session_id": "stopgate-s"}
    if prompt is not None:
        payload["prompt"] = prompt
    return subprocess.run(
        [sys.executable, str(BRIDGE)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
        timeout=30,
    )


def _write_events(events_dir: Path, events):
    events_dir.mkdir(parents=True, exist_ok=True)
    with (events_dir / "houdini_events.jsonl").open("a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, sort_keys=True) + "\n")


def _cook_error(node="/obj/topnet1", message="VEX compile failed: undefined symbol", ts=None):
    return {
        "type": "pdg_CookError",
        "detail": node,
        "timestamp": ts if ts is not None else time.time(),
        "data": {"message": message, "pdg_node": "ropfetch1"},
    }


def _cook_ok(node="/obj/topnet1", ts=None):
    return {
        "type": "pdg_CookComplete",
        "detail": node,
        "timestamp": ts if ts is not None else time.time(),
    }


def _rows(ledger: Path):
    if not ledger.exists():
        return []
    return [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.fixture
def env(tmp_path):
    return tmp_path / "events", tmp_path / "hooks.jsonl"


# --------------------------------------------------------------------------
# missing events file: exit 0, never a false block
# --------------------------------------------------------------------------

@pytest.mark.parametrize("event", ["Stop", "TaskCompleted", "UserPromptSubmit", "PreCompact"])
def test_missing_events_file_exits_zero(env, event):
    events_dir, ledger = env
    assert not (events_dir / "houdini_events.jsonl").exists()
    proc = _run(event, events_dir, ledger)
    assert proc.returncode == 0, proc.stderr
    assert "BLOCKED" not in proc.stderr


def test_stale_unresolved_file_without_events_file_is_cleared(env):
    """The events file is the source of truth; a leftover unresolved file
    with no events file must not block (Houdini session is gone)."""
    events_dir, ledger = env
    events_dir.mkdir(parents=True)
    (events_dir / UNRESOLVED_NAME).write_text(
        json.dumps({"/obj/ghost": {"message": "old", "timestamp": 0}}), encoding="utf-8"
    )
    proc = _run("Stop", events_dir, ledger)
    assert proc.returncode == 0
    assert not (events_dir / UNRESOLVED_NAME).exists()


# --------------------------------------------------------------------------
# unresolved cook error: Stop / TaskCompleted exit 2, stderr names the node
# --------------------------------------------------------------------------

def test_unresolved_cook_error_blocks_stop_with_exit_2(env):
    events_dir, ledger = env
    _write_events(events_dir, [_cook_error()])
    proc = _run("Stop", events_dir, ledger)
    assert proc.returncode == 2
    assert "/obj/topnet1" in proc.stderr
    assert "VEX compile failed" in proc.stderr
    assert "BLOCKED: 1 unresolved" in proc.stderr
    assert len(proc.stderr.strip().splitlines()) == 1  # one line


def test_task_completed_behaves_like_stop(env):
    events_dir, ledger = env
    _write_events(events_dir, [_cook_error(node="/stage/lopnet1", message="cook failed")])
    stop = _run("Stop", events_dir, ledger)
    task = _run("TaskCompleted", events_dir, ledger)
    assert stop.returncode == 2 and task.returncode == 2
    assert "/stage/lopnet1" in stop.stderr and "/stage/lopnet1" in task.stderr
    assert stop.stderr == task.stderr


def test_block_survives_the_prompt_watermark(env):
    """The old gate lived in the consume-on-prompt watermark: one
    UserPromptSubmit consumed the error and the next Stop saw nothing."""
    events_dir, ledger = env
    _write_events(events_dir, [_cook_error()])
    prompt = _run("UserPromptSubmit", events_dir, ledger, prompt="keep going")
    assert prompt.returncode == 0  # UserPromptSubmit never exits 2
    assert (events_dir / UNRESOLVED_NAME).exists()
    stop = _run("Stop", events_dir, ledger)
    assert stop.returncode == 2
    assert "/obj/topnet1" in stop.stderr


def test_user_prompt_submit_never_exits_2_even_with_errors(env):
    events_dir, ledger = env
    _write_events(events_dir, [_cook_error(), _cook_error(node="/obj/topnet2")])
    proc = _run("UserPromptSubmit", events_dir, ledger, prompt="why did the cook fail?")
    assert proc.returncode == 0
    assert "BLOCKED" not in proc.stderr
    # the set is persisted, not consumed
    data = json.loads((events_dir / UNRESOLVED_NAME).read_text(encoding="utf-8"))
    assert set(data) == {"/obj/topnet1", "/obj/topnet2"}
    assert data["/obj/topnet1"]["message"].startswith("VEX compile failed")


@pytest.mark.parametrize("event", ["PreCompact", "SessionEnd", "PostToolUse"])
def test_other_events_keep_exit_zero_with_unresolved_errors(env, event):
    events_dir, ledger = env
    _write_events(events_dir, [_cook_error()])
    proc = _run(event, events_dir, ledger)
    assert proc.returncode == 0
    assert "BLOCKED" not in proc.stderr


# --------------------------------------------------------------------------
# resolution: a later successful cook for the same node, or an explicit marker
# --------------------------------------------------------------------------

def test_successful_cook_on_same_node_resolves(env):
    events_dir, ledger = env
    t = time.time()
    _write_events(events_dir, [_cook_error(ts=t - 2)])
    assert _run("Stop", events_dir, ledger).returncode == 2
    _write_events(events_dir, [_cook_ok(ts=t)])
    proc = _run("Stop", events_dir, ledger)
    assert proc.returncode == 0, proc.stderr
    assert not (events_dir / UNRESOLVED_NAME).exists()


def test_successful_cook_on_a_different_node_does_not_resolve(env):
    events_dir, ledger = env
    t = time.time()
    _write_events(events_dir, [_cook_error(node="/obj/topnet1", ts=t - 2), _cook_ok(node="/obj/other", ts=t)])
    proc = _run("Stop", events_dir, ledger)
    assert proc.returncode == 2
    assert "/obj/topnet1" in proc.stderr


def test_explicit_resolved_marker_in_prompt_clears(env):
    events_dir, ledger = env
    _write_events(events_dir, [_cook_error()])
    assert _run("Stop", events_dir, ledger).returncode == 2
    proc = _run("UserPromptSubmit", events_dir, ledger, prompt="cook error resolved, move on")
    assert proc.returncode == 0
    assert _run("Stop", events_dir, ledger).returncode == 0
    assert _run("TaskCompleted", events_dir, ledger).returncode == 0


def test_marker_must_be_a_whole_word(env):
    events_dir, ledger = env
    _write_events(events_dir, [_cook_error()])
    _run("UserPromptSubmit", events_dir, ledger, prompt="the unresolvedness is bugging me")
    assert _run("Stop", events_dir, ledger).returncode == 2


# --------------------------------------------------------------------------
# ledger + speed
# --------------------------------------------------------------------------

def test_every_fire_is_recorded_in_the_ledger(env):
    events_dir, ledger = env
    _write_events(events_dir, [_cook_error()])
    _run("UserPromptSubmit", events_dir, ledger, prompt="x")
    _run("Stop", events_dir, ledger)
    rows = _rows(ledger)
    assert [(r["event"], r["decision"]) for r in rows] == [
        ("UserPromptSubmit", "ok"),
        ("Stop", "exit:2"),
    ]
    assert all(r["script"] == "synapse_hooks_bridge" for r in rows)
    assert rows[1]["extra"]["unresolved"] == 1
    assert rows[1]["session"] == "stopgate-s"


def test_no_error_path_is_fast(env):
    """Hook-measured duration (ledger ms, excludes interpreter start) <= 100 ms."""
    events_dir, ledger = env
    for event in ("Stop", "TaskCompleted"):
        proc = _run(event, events_dir, ledger)
        assert proc.returncode == 0
    rows = _rows(ledger)
    assert len(rows) == 2
    for r in rows:
        assert r["ms"] <= 100.0, f"{r['event']} took {r['ms']} ms"


def test_source_pins_exit_2_inside_stop_and_task_branches():
    src = BRIDGE.read_text(encoding="utf-8")
    stop = src.split('elif hook_event == "Stop":', 1)[1].split("elif", 1)[0]
    task = src.split('elif hook_event == "TaskCompleted":', 1)[1].split("elif", 1)[0]
    assert "sys.exit(2)" in stop
    assert "sys.exit(2)" in task
    assert "sys.exit(1)" not in src
    assert src.count("sys.exit(2)") == 2  # only these two branches block
