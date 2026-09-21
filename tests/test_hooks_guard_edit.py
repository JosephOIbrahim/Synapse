"""BP9-HOOKS: guard-edit-targets.py fail-closed + houdini22.0 + worktree fence,
plus the hook-fire ledger.

Every test runs the hook script as a real subprocess with crafted JSON on
stdin, exactly as Claude Code does. The ledger is redirected to a temp path
via SYNAPSE_HOOKS_LEDGER so no test touches ~/.synapse/hooks.jsonl.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"
GUARD = HOOKS / "guard-edit-targets.py"
BRIDGE = HOOKS / "synapse_hooks_bridge.py"
LEDGER = HOOKS / "_ledger.py"

DENY_EXIT = 2

# tmp_path lives under AppData on Windows, which the pattern list already
# denies; the pure-path fence tests therefore use a fictional tree that exists
# nowhere on disk (the fence needs no filesystem, only the JSON cwd).
FAKE_MAIN = "C:/fake/SYNAPSE" if os.name == "nt" else "/fake/SYNAPSE"


def _run(script: Path, stdin: str, ledger: Path, cwd: Path | None = None, extra_env=None):
    env = dict(os.environ)
    env["SYNAPSE_HOOKS_LEDGER"] = str(ledger)
    env.pop("CLAUDE_HOOK_EVENT", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(script)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd or ROOT),
        timeout=30,
    )


def _hook_json(file_path: str, cwd: str | None = None, tool="Edit") -> str:
    payload = {
        "hook_event_name": "PreToolUse",
        "session_id": "test-session",
        "tool_name": tool,
        "tool_input": {"file_path": file_path},
    }
    if cwd is not None:
        payload["cwd"] = cwd
    return json.dumps(payload)


def _deny_reason(proc) -> str:
    out = proc.stdout.strip()
    assert out, f"expected JSON deny on stdout, got nothing (stderr={proc.stderr!r})"
    data = json.loads(out)
    hso = data["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    return hso["permissionDecisionReason"]


def _rows(ledger: Path):
    if not ledger.exists():
        return []
    return [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]


# --------------------------------------------------------------------------
# allow: ordinary main-tree edit is byte-identical to the original hook
# --------------------------------------------------------------------------

def test_main_tree_edit_allowed(tmp_path):
    ledger = tmp_path / "hooks.jsonl"
    target = str(ROOT / "python" / "synapse" / "some_module.py")
    proc = _run(GUARD, _hook_json(target, cwd=str(ROOT)), ledger)
    assert proc.returncode == 0
    assert proc.stdout == ""  # byte-identical allow: no output at all
    assert proc.stderr == ""


def test_relative_path_inside_worktree_allowed(tmp_path):
    ledger = tmp_path / "hooks.jsonl"
    wt = tmp_path / ".claude" / "worktrees" / "wt-1"
    wt.mkdir(parents=True)
    proc = _run(GUARD, _hook_json("python/synapse/x.py", cwd=str(wt)), ledger, cwd=wt)
    assert proc.returncode == 0
    assert proc.stdout == ""


def test_sibling_worktree_is_outside_the_fence(tmp_path):
    ledger = tmp_path / "hooks.jsonl"
    wt = FAKE_MAIN + "/.claude/worktrees/wf_abc-4"
    sibling = FAKE_MAIN + "/.claude/worktrees/wf_abc-4b/python/x.py"
    assert "Worktree fence" in _deny_reason(_run(GUARD, _hook_json(sibling, cwd=wt), ledger))


# --------------------------------------------------------------------------
# worktree fence
# --------------------------------------------------------------------------

def test_worktree_cwd_outside_path_denied(tmp_path):
    ledger = tmp_path / "hooks.jsonl"
    wt = FAKE_MAIN + "/.claude/worktrees/wf_abc-1"
    outside = FAKE_MAIN + "/python/synapse/server/handlers.py"
    proc = _run(GUARD, _hook_json(outside, cwd=wt), ledger)
    assert proc.returncode == 0  # policy deny: JSON deny, exit 0
    reason = _deny_reason(proc)
    assert "Worktree fence" in reason


def test_worktree_fence_uses_process_cwd_when_json_has_none(tmp_path):
    ledger = tmp_path / "hooks.jsonl"
    main_tree = tmp_path / "SYNAPSE"
    wt = main_tree / ".claude" / "worktrees" / "wf_abc-2"
    wt.mkdir(parents=True)
    outside = str(main_tree / "shared" / "bridge.py")
    proc = _run(GUARD, _hook_json(outside), ledger, cwd=wt)
    assert "Worktree fence" in _deny_reason(proc)


def test_worktree_absolute_path_inside_worktree_allowed(tmp_path):
    ledger = tmp_path / "hooks.jsonl"
    wt = FAKE_MAIN + "/.claude/worktrees/wf_abc-3"
    inside = wt + "/python/synapse/x.py"
    proc = _run(GUARD, _hook_json(inside, cwd=wt), ledger)
    assert proc.returncode == 0
    assert proc.stdout == ""


# --------------------------------------------------------------------------
# narrowed fence (BP9-STOPGATE): deny the main checkout, allow ~/.claude
# --------------------------------------------------------------------------

FAKE_HOME = "C:/Users/User" if os.name == "nt" else "/home/user"


def test_narrowed_fence_denies_main_checkout_from_worktree_cwd(tmp_path):
    ledger = tmp_path / "hooks.jsonl"
    wt = FAKE_MAIN + "/.claude/worktrees/wf_narrow-1"
    main_path = FAKE_MAIN + "/python/synapse/server/handlers.py"
    proc = _run(GUARD, _hook_json(main_path, cwd=wt), ledger)
    assert proc.returncode == 0
    reason = _deny_reason(proc)
    assert "Worktree fence" in reason and "main checkout" in reason


def test_narrowed_fence_allows_auto_memory_file_from_worktree_cwd(tmp_path):
    """The wave-one fence denied ~/.claude/projects/*/memory/MEMORY.md from
    every worktree agent (crucible finding). Outside both trees -> allowed."""
    ledger = tmp_path / "hooks.jsonl"
    wt = FAKE_MAIN + "/.claude/worktrees/wf_narrow-2"
    memory = FAKE_HOME + "/.claude/projects/C--Users-User-SYNAPSE/memory/MEMORY.md"
    proc = _run(GUARD, _hook_json(memory, cwd=wt), ledger)
    assert proc.returncode == 0
    assert proc.stdout == "", proc.stdout  # byte-identical allow
    assert proc.stderr == ""


def test_narrowed_fence_allows_global_skills_dir_from_worktree_cwd(tmp_path):
    ledger = tmp_path / "hooks.jsonl"
    wt = FAKE_MAIN + "/.claude/worktrees/wf_narrow-3"
    skill = FAKE_HOME + "/.claude/skills/codebase-transition/SKILL.md"
    proc = _run(GUARD, _hook_json(skill, cwd=wt), ledger)
    assert proc.returncode == 0 and proc.stdout == ""


def test_narrowed_fence_still_denies_main_checkout_dot_claude(tmp_path):
    """<main>/.claude/settings.json is inside the main checkout: still fenced."""
    ledger = tmp_path / "hooks.jsonl"
    wt = FAKE_MAIN + "/.claude/worktrees/wf_narrow-4"
    settings = FAKE_MAIN + "/.claude/settings.json"
    assert "Worktree fence" in _deny_reason(_run(GUARD, _hook_json(settings, cwd=wt), ledger))


def test_narrowed_fence_pattern_list_still_applies_outside_both_trees(tmp_path):
    """Outside both trees is not a free pass: the pattern list runs next."""
    ledger = tmp_path / "hooks.jsonl"
    wt = FAKE_MAIN + "/.claude/worktrees/wf_narrow-5"
    prefs = FAKE_HOME + "/Documents/houdini22.0/packages/synapse.json"
    assert "Houdini prefs" in _deny_reason(_run(GUARD, _hook_json(prefs, cwd=wt), ledger))


# --------------------------------------------------------------------------
# houdini22.0 prefs tree
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "C:\\Users\\User\\Documents\\houdini22.0\\packages\\synapse.json",
    "/home/user/houdini22.0/packages/synapse.json",
    "C:\\Users\\User\\Documents\\houdini21.0\\packages\\synapse.json",
])
def test_houdini_prefs_path_denied(tmp_path, path):
    ledger = tmp_path / "hooks.jsonl"
    # cwd is a main tree (this test file may itself run inside a worktree,
    # where the fence would fire first with its own, more specific reason).
    proc = _run(GUARD, _hook_json(path, cwd=FAKE_MAIN), ledger)
    assert proc.returncode == 0
    assert "Houdini prefs" in _deny_reason(proc)


# --------------------------------------------------------------------------
# fail-closed
# --------------------------------------------------------------------------

@pytest.mark.parametrize("stdin", ["", "not json {", "{}", "[]", '{"tool_input": null}',
                                   '{"tool_input": {"file_path": ""}}'])
def test_malformed_or_missing_input_denied(tmp_path, stdin):
    ledger = tmp_path / "hooks.jsonl"
    proc = _run(GUARD, stdin, ledger)
    assert proc.returncode == DENY_EXIT
    assert "fail-closed" in proc.stderr
    assert "fail-closed" in _deny_reason(proc)


def test_fail_closed_is_real_when_ledger_import_is_broken(tmp_path, monkeypatch):
    """A broken ledger must not flip the decision either way."""
    ledger = tmp_path / "unwritable" / "dir"
    ledger.mkdir(parents=True)  # a directory: open(..., 'a') will fail
    good = str(ROOT / "python" / "synapse" / "x.py")
    proc = _run(GUARD, _hook_json(good, cwd=str(ROOT)), ledger)
    assert proc.returncode == 0 and proc.stdout == ""
    proc = _run(GUARD, "{}", ledger)
    assert proc.returncode == DENY_EXIT


# --------------------------------------------------------------------------
# ledger
# --------------------------------------------------------------------------

def test_ledger_row_written_via_env_override(tmp_path):
    ledger = tmp_path / "nested" / "hooks.jsonl"
    good = str(ROOT / "python" / "synapse" / "x.py")
    _run(GUARD, _hook_json(good, cwd=str(ROOT)), ledger)
    _run(GUARD, _hook_json("/x/houdini22.0/y", cwd=str(ROOT)), ledger)
    _run(GUARD, "{}", ledger)
    rows = _rows(ledger)
    assert [r["decision"] for r in rows] == ["allow", "deny", "deny"]
    for r in rows:
        assert set(r) == {"ts", "event", "script", "decision", "ms", "session", "extra"}
        assert r["event"] == "PreToolUse"
        assert r["script"] == "guard-edit-targets"
        assert isinstance(r["ms"], float) and r["ms"] >= 0
    assert rows[0]["session"] == "test-session"
    assert rows[2]["extra"]["exit"] == DENY_EXIT
    assert not (tmp_path / "synapse.log").exists()


def test_ledger_helper_never_raises(tmp_path, monkeypatch):
    sys.path.insert(0, str(HOOKS))
    try:
        import importlib
        _ledger = importlib.import_module("_ledger")
        bad = tmp_path / "isdir"
        bad.mkdir()
        monkeypatch.setenv("SYNAPSE_HOOKS_LEDGER", str(bad))
        _ledger.record("E", "s", "d", 1.0)  # open() on a dir fails -> swallowed
        _ledger.record("E", "s", "d", "not-a-number")  # float() fails -> swallowed
        _ledger.record("E", "s", "d", 1.0, extra={"obj": object()})  # default=str
        good = tmp_path / "ok.jsonl"
        monkeypatch.setenv("SYNAPSE_HOOKS_LEDGER", str(good))
        _ledger.record("E", "s", "d", 2, extra={"k": 1}, session="S")
        rows = _rows(good)
        assert len(rows) == 1 and rows[0]["session"] == "S" and rows[0]["ms"] == 2.0
    finally:
        sys.path.remove(str(HOOKS))
        sys.modules.pop("_ledger", None)


def test_ledger_source_never_writes_synapse_log_or_jev_ledger():
    src = LEDGER.read_text(encoding="utf-8")
    code = src.split('"""', 2)[-1]  # drop the module docstring
    code = "\n".join(l for l in code.splitlines() if not l.strip().startswith("#"))
    assert "hooks.jsonl" in code
    assert "synapse.log" not in code
    assert "harness" not in code
    assert "sys.exit" not in code and "permissionDecision" not in code  # zero decisions


# --------------------------------------------------------------------------
# bridge: ledger wrapped, exit codes unchanged
# --------------------------------------------------------------------------

def test_bridge_records_fire_and_keeps_exit_code(tmp_path):
    ledger = tmp_path / "hooks.jsonl"
    events_dir = tmp_path / "hooks_events"
    proc = _run(
        BRIDGE,
        json.dumps({"hook_event_name": "PreCompact", "session_id": "bridge-s"}),
        ledger,
        extra_env={"TEMP": str(tmp_path)},
    )
    assert proc.returncode == 0
    rows = _rows(ledger)
    assert len(rows) == 1
    assert rows[0]["script"] == "synapse_hooks_bridge"
    assert rows[0]["event"] == "PreCompact"
    assert rows[0]["decision"] == "ok"
    assert rows[0]["session"] == "bridge-s"


def test_bridge_stop_and_taskcompleted_both_block_with_exit_2():
    """BP9-STOPGATE (ruling 4): Stop moved from exit 1 to the blocking exit 2,
    TaskCompleted stays exit 2, and nothing else in the bridge exits non-zero.
    Behaviour is driven end-to-end in tests/test_hooks_stop_gate.py."""
    src = BRIDGE.read_text(encoding="utf-8")
    stop = src.split('elif hook_event == "Stop":', 1)[1].split("elif", 1)[0]
    task = src.split('elif hook_event == "TaskCompleted":', 1)[1].split("elif", 1)[0]
    assert "sys.exit(2)" in stop
    assert "sys.exit(2)" in task
    assert src.count("sys.exit(2)") == 2
    assert "sys.exit(1)" not in src
