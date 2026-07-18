"""Tests for the BLACKBOX crash-recovery harness (scripts/blackbox_mine.py + blackbox_recover.py).

Pure-Python, no hou, no PowerShell (git + forensics sections are skipped) — portable to macOS CI.
"""
import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import blackbox_recover as br  # noqa: E402


def _jl(obj):
    return json.dumps(obj)


def _make_transcript(path, *, orphan=True, truncated=True, continue_after_orphan=False):
    lines = [
        _jl({"type": "user", "timestamp": "2026-07-18T17:00:00Z",
             "message": {"role": "user", "content": "finish the render-fix gates"}}),
        _jl({"type": "assistant", "timestamp": "2026-07-18T17:00:05Z",
             "message": {"role": "assistant", "content": [
                 {"type": "text", "text": "Running gate 1 now."},
                 {"type": "tool_use", "id": "t1", "name": "PowerShell",
                  "input": {"command": "pytest tests/a.py -q"}}]}}),
        _jl({"type": "user", "timestamp": "2026-07-18T17:01:00Z",
             "message": {"role": "user", "content": [
                 {"type": "tool_result", "tool_use_id": "t1", "content": "1 passed"}]}}),
    ]
    if orphan:
        lines.append(_jl({"type": "assistant", "timestamp": "2026-07-18T17:02:00Z",
                          "message": {"role": "assistant", "content": [
                              {"type": "tool_use", "id": "t2", "name": "PowerShell",
                               "input": {"command": "pytest tests/ -q"}}]}}))
    if continue_after_orphan:  # Esc-interrupt shape: session talked past the orphan
        lines.append(_jl({"type": "user", "timestamp": "2026-07-18T17:03:00Z",
                          "message": {"role": "user", "content": "never mind, do it later"}}))
    if truncated:
        lines.append('{"type": "assis')  # hard kill mid-append
    path.write_text("\n".join(lines), encoding="utf-8")


def _make_session(proj, sid, *, age_s=3600, with_agent=True, **transcript_kw):
    transcript = proj / f"{sid}.jsonl"
    _make_transcript(transcript, **transcript_kw)
    old = time.time() - age_s
    os.utime(transcript, (old, old))
    if with_agent:
        subdir = proj / sid / "subagents"
        subdir.mkdir(parents=True)
        (subdir / "agent-abc.meta.json").write_text(_jl(
            {"agentType": "general-purpose", "description": "Verify render-fix test gates"}),
            encoding="utf-8")
        (subdir / "agent-abc.jsonl").write_text("\n".join([
            _jl({"type": "assistant", "timestamp": "2026-07-18T17:01:30Z",
                 "message": {"role": "assistant", "content": [
                     {"type": "tool_use", "id": "a1", "name": "PowerShell",
                      "input": {"command": "pytest tests/b.py -q"}}]}}),
            _jl({"type": "user", "timestamp": "2026-07-18T17:01:45Z",
                 "message": {"role": "user",
                             "content": "[Request interrupted by user for tool use]"}}),
        ]), encoding="utf-8")
    return transcript


def test_project_dir_sanitization():
    assert br.project_dir_for(r"C:\Users\User\SYNAPSE").name == "C--Users-User-SYNAPSE"


def test_pick_session_skips_live_transcripts(tmp_path):
    _make_session(tmp_path, "dead00", age_s=3600, with_agent=False)
    live = tmp_path / "live00.jsonl"
    _make_transcript(live)  # mtime = now -> inside grace window
    picked = br.pick_session(tmp_path, 90, None)
    assert picked.stem == "dead00"


def test_pick_session_explicit_prefix(tmp_path):
    _make_session(tmp_path, "dead00", with_agent=False)
    picked = br.pick_session(tmp_path, 90, "dead")
    assert picked.stem == "dead00"


def test_parse_detects_orphan_and_truncation(tmp_path):
    t = _make_session(tmp_path, "s1", with_agent=False)
    parsed = br.parse_transcript(t)
    assert [tl["id"] for tl in parsed["unanswered"]] == ["t2"]
    assert [tl["id"] for tl in parsed["tail_orphans"]] == ["t2"]
    assert parsed["bad"] == 1
    sig = br.death_signature(parsed)
    assert "mid-tool-call" in sig and "truncated" in sig


def test_interrupted_orphan_is_not_a_tail_orphan(tmp_path):
    t = _make_session(tmp_path, "s1b", with_agent=False,
                      continue_after_orphan=True, truncated=False)
    parsed = br.parse_transcript(t)
    assert [tl["id"] for tl in parsed["unanswered"]] == ["t2"]
    assert parsed["tail_orphans"] == []  # session continued -> interrupt, not death
    assert "clean" in br.death_signature(parsed)


def test_clean_tail_signature(tmp_path):
    t = _make_session(tmp_path, "s2", with_agent=False, orphan=False, truncated=False)
    parsed = br.parse_transcript(t)
    assert parsed["unanswered"] == [] and parsed["bad"] == 0
    assert "clean" in br.death_signature(parsed)


def test_mine_subagents_flags_interrupt(tmp_path):
    _make_session(tmp_path, "s3")
    agents = br.mine_subagents(tmp_path / "s3")
    assert len(agents) == 1
    a = agents[0]
    assert a["desc"] == "Verify render-fix test gates"
    assert a["interrupted"] is True
    assert "pytest tests/b.py" in a["last_tool"]


def test_capsule_end_to_end(tmp_path, capsys):
    _make_session(tmp_path, "s4")
    out = tmp_path / "capsule.md"
    rc = br.main(["--project", str(tmp_path), "--out", str(out),
                  "--no-git", "--no-forensics", "--grace", "60"])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "s4" in text
    assert "ORPHANED PowerShell" in text
    assert "Verify render-fix test gates" in text
    assert "INTERRUPTED/KILLED" in text
    assert "truncated write (hard kill)" in text
    assert "DETACHED" in text  # next-action doctrine present
    assert "BLACKBOX RECOVERY CAPSULE" in capsys.readouterr().out  # capsule also printed


def test_detect_reports_crashed_session(tmp_path, capsys):
    _make_session(tmp_path, "dead1", with_agent=False)  # tail orphan + truncation, aged 1h
    rc = br.main(["--project", str(tmp_path), "--detect", "--grace", "60"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dead1" in out and "may have died" in out and "--session dead1" in out


def test_detect_silent_on_clean_session(tmp_path, capsys):
    _make_session(tmp_path, "clean1", with_agent=False, orphan=False, truncated=False)
    rc = br.main(["--project", str(tmp_path), "--detect", "--grace", "60"])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_detect_silent_on_interrupted_session(tmp_path, capsys):
    # Esc-interrupt shape (orphan mid-file, session continued) must NOT cry crash.
    _make_session(tmp_path, "esc1", with_agent=False,
                  continue_after_orphan=True, truncated=False)
    rc = br.main(["--project", str(tmp_path), "--detect", "--grace", "60"])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_detect_sees_crash_behind_trivial_newer_session(tmp_path, capsys):
    _make_session(tmp_path, "dead2", with_agent=False, age_s=3600)
    _make_session(tmp_path, "triv1", with_agent=False, age_s=600,
                  orphan=False, truncated=False)  # newer, clean, must not mask
    rc = br.main(["--project", str(tmp_path), "--detect", "--grace", "60"])
    assert rc == 0
    assert "dead2" in capsys.readouterr().out


def test_detect_missing_project_dir_is_silent_success(tmp_path, capsys):
    rc = br.main(["--project", str(tmp_path / "nope"), "--detect"])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_list_mode_runs(tmp_path, capsys):
    _make_session(tmp_path, "s5", with_agent=False)
    rc = br.main(["--project", str(tmp_path), "--list"])
    assert rc == 0
    assert "s5" in capsys.readouterr().out
