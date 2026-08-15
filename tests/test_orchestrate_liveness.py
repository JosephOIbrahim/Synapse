"""Acceptance: orchestrate.ps1's staleness tracker counts subagent + workflow
transcripts as liveness, not only the leg's top-level session .jsonl.

The defect (W5H house notes): `Get-LastProgress` filtered transcripts with
`$_.Directory.Name -match 'SYNAPSE'`, which only matches a file whose IMMEDIATE
parent is the SYNAPSE project dir - i.e. the leg's own top-level session
transcript. A crucible deep in subagent probes (or any ultracode workflow)
writes ONLY to

    ~/.claude/projects/<...SYNAPSE...>/<session>/subagents/**/*.jsonl
    ~/.claude/projects/<...SYNAPSE...>/<session>/subagents/workflows/wf_*/agent-*.jsonl

whose parent names are 'subagents' / 'wf_*'. Those never matched, so a busy
subagent fan-out read as dead after StaleMinutes. The fix matches the FULL PATH
against 'SYNAPSE', which carries at every depth (and still excludes other
projects). harness/progress.py:321 and harness/statusline.py:249 already read
this exact path shape; this pins the ps1 tracker in line with them.

Get-LastProgress has no Python twin (unlike lock.py / status.py), so the REAL
ps1 function is exercised directly: dot-source orchestrate.ps1 in library mode
(SYNAPSE_ORCH_LIB=1 -> functions defined, board loop skipped) with USERPROFILE
and repo isolated to temp dirs, then call it. Skips (never a false pass) where
no PowerShell exists.
"""
import os
import shutil
import subprocess
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORCH = os.path.join(ROOT, "harness", "orchestrate.ps1")


def _powershell():
    return shutil.which("powershell") or shutil.which("pwsh")


pytestmark = pytest.mark.skipif(
    _powershell() is None,
    reason="no powershell/pwsh on this host - Get-LastProgress is ps1-only",
)


def _fwd(p):
    return str(p).replace("\\", "/")


def _get_last_progress(userprofile, repo):
    """Call the REAL Get-LastProgress with USERPROFILE + repo isolated to temp
    dirs. Returns the UTC epoch seconds it produced (int), or None for null."""
    ps = _powershell()
    script = "\n".join([
        "$env:SYNAPSE_ORCH_LIB='1'",
        "$env:USERPROFILE='%s'" % _fwd(userprofile),
        ". '%s' -Repo '%s' *> $null" % (_fwd(ORCH), _fwd(repo)),
        "$t = Get-LastProgress",
        "if ($t) { [int64]([datetimeoffset]$t).ToUnixTimeSeconds() } else { '' }",
    ])
    out = subprocess.run(
        [ps, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=90,
    )
    assert out.returncode == 0, "powershell failed:\n%s\n%s" % (out.stdout, out.stderr)
    val = out.stdout.strip()
    return int(val) if val else None


def _touch(path, mtime_epoch):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('{"type":"assistant"}\n')
    os.utime(path, (mtime_epoch, mtime_epoch))


def _synapse_session(profile):
    """<profile>/.claude/projects/C--Users-User-SYNAPSE/<session>"""
    return os.path.join(str(profile), ".claude", "projects",
                        "C--Users-User-SYNAPSE", "sess-0001")


def test_subagent_workflow_write_moves_last_write(tmp_path):
    """FAILS IF: a workflow-agent transcript under subagents/workflows/ is
    invisible to the staleness tracker (Get-LastProgress returns null).

    This is the exact blind spot: with the old immediate-parent filter the only
    .jsonl present here would be skipped and the tracker would report no
    progress at all.
    """
    profile = tmp_path / "profile"
    repo = tmp_path / "repo"
    repo.mkdir()
    want = int(time.time()) - 300
    fixture = os.path.join(_synapse_session(profile), "subagents", "workflows",
                           "wf_probe", "agent-abc123.jsonl")
    _touch(fixture, want)

    got = _get_last_progress(profile, repo)
    assert got is not None, (
        "Get-LastProgress returned null for a subagents/workflows transcript - "
        "the tracker is still blind to subagent depth")
    assert abs(got - want) <= 2, (
        "returned %d, fixture mtime %d (delta %d)" % (got, want, got - want))


def test_fresh_subagent_beats_stale_main_transcript(tmp_path):
    """FAILS IF: a fresh subagent write does not advance the age past a stale
    top-level session transcript.

    The real crucible scenario: the leg's own transcript has gone quiet (stale)
    while the subagent fan-out is actively writing. The tracker must return the
    subagent's fresh time, not the stale main one - otherwise the leg is
    declared STALE while genuinely working.
    """
    profile = tmp_path / "profile"
    repo = tmp_path / "repo"
    repo.mkdir()
    session = _synapse_session(profile)
    now = int(time.time())
    stale = now - 7200   # leg's own session transcript, 2h quiet
    fresh = now - 120    # subagent wrote 2 min ago
    _touch(os.path.join(os.path.dirname(session), "sess-0001.jsonl"), stale)
    _touch(os.path.join(session, "subagents", "workflows", "wf_x",
                        "agent-def456.jsonl"), fresh)

    got = _get_last_progress(profile, repo)
    assert got is not None, "tracker saw neither transcript"
    assert abs(got - fresh) <= 2, (
        "tracker returned %d; expected the fresh subagent time %d, not the "
        "stale main transcript %d" % (got, fresh, stale))


def test_non_synapse_project_is_not_counted(tmp_path):
    """FAILS IF: broadening the filter to FullName also swept in other projects.

    The SYNAPSE scoping must survive the depth fix: a transcript under a
    non-SYNAPSE project slug must not register as SYNAPSE liveness. Guarded
    against a temp root that itself contains 'SYNAPSE' (which would defeat the
    scoping legitimately) with a skip, not a false pass.
    """
    if "SYNAPSE" in str(tmp_path).upper():
        pytest.skip("temp root contains 'SYNAPSE' - cannot isolate the scoping")
    profile = tmp_path / "profile"
    repo = tmp_path / "repo"
    repo.mkdir()
    other = os.path.join(str(profile), ".claude", "projects",
                         "C--Users-User-Octavius", "sess", "subagents",
                         "agent-z.jsonl")
    _touch(other, int(time.time()) - 60)

    got = _get_last_progress(profile, repo)
    assert got is None, (
        "a non-SYNAPSE transcript was counted as SYNAPSE liveness: %r" % got)
