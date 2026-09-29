"""orchestrate.ps1: a leftover worktree never makes a leg 'ready' before its deps (BP12 item 6).

On 2026-09-28 a worktree left from an earlier run made CRUX2 read 'ready', and the
orchestrator dispatched it before the leg it depends on had a receipt.
Get-LegState returned 'ready' for an existing worktree before it looked at the
leg's deps. The deps check now comes first; a live leg still reads 'running'.

Get-LegState is called the way test_orchestrate_close_gate.py calls it:
dot-source orchestrate.ps1 in library mode with -Repo isolated to a temp dir and
-DryRun set, assign the manifest the function reads, then call the real
function. Skips where no PowerShell exists.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORCH = os.path.join(ROOT, "harness", "orchestrate.ps1")


def _powershell():
    return shutil.which("powershell") or shutil.which("pwsh")


pytestmark = pytest.mark.skipif(
    _powershell() is None,
    reason="no powershell/pwsh on this host - Get-LegState is ps1-only",
)

DEP = {"id": "W99-DEPGATE-A", "name": "the leg the gated leg needs",
       "receipt": "W99-DEPGATE-A.json", "branch": "wave99/dep-a", "worktree": "wt-a", "deps": []}
LEG = {"id": "W99-DEPGATE-B", "name": "the gated leg",
       "receipt": "W99-DEPGATE-B.json", "branch": "wave99/dep-b", "worktree": "wt-b",
       "deps": ["W99-DEPGATE-A"]}


def _fwd(p):
    return str(p).replace("\\", "/")


def _state(repo):
    manifest = json.dumps({"legs": [DEP, LEG]})  # double quotes only: safe in PS single quotes
    script = "\n".join([
        "$env:SYNAPSE_ORCH_LIB='1'",
        ". '%s' -Repo '%s' -DryRun -Quiet *> $null" % (_fwd(ORCH), _fwd(repo)),
        "$manifest = '%s' | ConvertFrom-Json" % manifest,
        "$leg = $manifest.legs | Where-Object { $_.id -eq '%s' }" % LEG["id"],
        "Write-Output ('STATE=' + (Get-LegState $leg))",
    ])
    out = subprocess.run([_powershell(), "-NoProfile", "-NonInteractive", "-Command", script],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=120)
    assert out.returncode == 0, "powershell failed:\n%s\n%s" % (out.stdout, out.stderr)
    states = [line[len("STATE="):].strip() for line in out.stdout.splitlines()
              if line.startswith("STATE=")]
    assert states, "no state printed:\n%s\n%s" % (out.stdout, out.stderr)
    return states[-1]


def _repo(tmp_path, *, leftover_worktree, dep_receipt):
    repo = tmp_path / "repo"
    receipts = repo / "harness" / "notes" / "receipts"
    receipts.mkdir(parents=True)
    if leftover_worktree:
        (repo / "wt-b").mkdir()
    if dep_receipt:
        (receipts / "W99-DEPGATE-A.json").write_text(
            '{"leg":"W99-DEPGATE-A","status":"green"}', encoding="utf-8")
    return repo


def test_leftover_worktree_with_an_unmet_dep_is_blocked(tmp_path):
    """The 2026-09-28 CRUX2 shape: the worktree exists and the dep has no receipt.
    Before the fix this read 'ready' and the leg dispatched early."""
    assert _state(_repo(tmp_path, leftover_worktree=True, dep_receipt=False)) == "blocked"


def test_leftover_worktree_with_its_dep_met_is_ready(tmp_path):
    """Once the dep has a receipt, the leftover worktree is reused: 'ready'."""
    assert _state(_repo(tmp_path, leftover_worktree=True, dep_receipt=True)) == "ready"


def test_no_worktree_and_an_unmet_dep_is_blocked(tmp_path):
    """Unchanged: without a worktree, an unmet dep still blocks."""
    assert _state(_repo(tmp_path, leftover_worktree=False, dep_receipt=False)) == "blocked"
