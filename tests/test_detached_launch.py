"""harness/lib/detached.ps1: arm a wave outside the arming app's process tree (BP12 item 6).

On 2026-09-28 the Claude desktop app restarted and took the BP11 orchestrator
with it, because the orchestrator was a child of a shell the app had opened.
arm_template.ps1 now starts the orchestrator and the steward with Start-Detached,
which uses Win32_Process.Create. The launch test starts a short-lived PowerShell
that way and checks what the arm script relies on: the child is outside the
caller's tree, it runs in the caller's desktop session (the steward's SendKeys
needs that), it sees the environment handed to it, and the returned pid is the
child itself.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "harness" / "lib" / "detached.ps1"
ARM = ROOT / "harness" / "bastion" / "arm_template.ps1"

windows_only = pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("powershell") is None,
    reason="Win32_Process.Create and the arm script are Windows-only",
)


def _sq(text) -> str:
    return "'" + str(text).replace("'", "''") + "'"


def _ps(script: str) -> dict:
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=120)
    assert out.returncode == 0, "powershell failed:\n%s\n%s" % (out.stdout, out.stderr)
    facts = {}
    for line in out.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.isupper():
            facts[key] = value.strip()
    return facts


@windows_only
def test_start_detached_runs_outside_the_callers_tree_with_the_given_env(tmp_path):
    marker = tmp_path / "child.txt"
    child_command = ("Set-Content -LiteralPath %s -Value ([string]$PID + '|' + "
                     "$env:SYNAPSE_DETACHED_PROBE); Start-Sleep -Seconds 60") % _sq(marker)
    info = _ps("\n".join([
        ". %s" % _sq(LIB),
        "$child = Start-Detached -Command %s -WorkingDirectory %s "
        "-Environment @{ SYNAPSE_DETACHED_PROBE = 'probe-ok' }" % (_sq(child_command), _sq(tmp_path)),
        "$me = Get-CimInstance Win32_Process -Filter \"ProcessId=$PID\"",
        "Write-Output ('CHILD=' + $child)",
        "Write-Output ('SELF=' + $PID)",
        "Write-Output ('SESSION=' + $me.SessionId)",
    ]))
    child = int(info["CHILD"])
    try:
        deadline = time.time() + 30
        while not marker.exists() and time.time() < deadline:
            time.sleep(0.2)
        assert marker.exists(), "the detached child never ran"
        pid_text, probe = marker.read_text(encoding="utf-8-sig").strip().split("|", 1)
        assert probe == "probe-ok", "the environment was not handed to the child"
        assert int(pid_text) == child, "the returned pid is not the process running the command"
        facts = _ps("$p = Get-CimInstance Win32_Process -Filter \"ProcessId=%d\"\n"
                    "Write-Output ('PARENT=' + $p.ParentProcessId)\n"
                    "Write-Output ('SESSION=' + $p.SessionId)" % child)
        assert int(facts["PARENT"]) not in (int(info["SELF"]), os.getpid())
        assert facts["SESSION"] == info["SESSION"], "the child left the caller's desktop session"
    finally:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Stop-Process -Id %d -Force -ErrorAction SilentlyContinue" % child],
                       capture_output=True, timeout=60)


@windows_only
def test_arm_template_parses():
    facts = _ps("$errors = $null\n"
                "[void][System.Management.Automation.Language.Parser]::ParseFile(%s, [ref]$null, [ref]$errors)\n"
                "Write-Output ('ERRORS=' + $errors.Count)" % _sq(ARM))
    assert facts["ERRORS"] == "0"


def test_arm_template_arms_detached_by_default_and_hands_over_the_leg_env():
    text = ARM.read_text(encoding="utf-8")
    assert "harness\\lib\\detached.ps1" in text
    assert "[switch]$InAppTree" in text
    assert text.count("Start-Detached -Command") == 2        # the orchestrator and the steward
    assert text.count("-Environment $legEnv") == 2
    env_block = text.split("$legEnv = [ordered]@{", 1)[1].split("}", 1)[0]
    for name in ("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", "CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"):
        assert name in env_block
