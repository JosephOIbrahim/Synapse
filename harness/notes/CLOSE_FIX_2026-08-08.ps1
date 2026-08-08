# CLOSE_FIX_2026-08-08.ps1 - repairs and completes the wave-1 close.
# Fixes two defects in CLOSE_2026-08-08.ps1: (1) git exit codes are now
# checked on EVERY step; (2) the .orch_launched junk-marker add/add
# conflict is auto-resolved; ANY other conflict hard-aborts untouched.
# The final banner is DERIVED from checks, never asserted.
$ErrorActionPreference = 'Stop'
Set-Location C:\Users\User\Synapse

function G { param([Parameter(ValueFromRemainingArguments)]$a)
  & git @a
  if ($LASTEXITCODE -ne 0) { throw "git $($a -join ' ') failed (exit $LASTEXITCODE)" } }

function Resolve-MarkerConflict($id) {
  $conf = @(git diff --name-only --diff-filter=U)
  if ($conf.Count -eq 1 -and $conf[0] -eq '.claude/.orch_launched') {
    G rm -q .claude/.orch_launched
    G commit --no-edit
    Write-Host "  $id merged (junk marker dropped)" -ForegroundColor Green
  } else {
    git merge --abort 2>$null
    throw "ABORT on ${id}: unexpected conflict in [$($conf -join ', ')] - human eyes needed; nothing was merged for this leg."
  }
}

function MergeLeg($br, $id) {
  & git merge --no-ff $br -m "merge ${id}: receipted green - wave 1 finish"
  if ($LASTEXITCODE -ne 0) { Resolve-MarkerConflict $id }
  else { Write-Host "  $id merged clean" -ForegroundColor Green }
}

# 1 - finish the GUARD merge that is currently parked mid-conflict
if (Test-Path .git\MERGE_HEAD) { Resolve-MarkerConflict 'GUARD' }

# 2 - the three remaining merges, marker-aware
MergeLeg 'finish/freeze-attribution'  'FRZ'
MergeLeg 'finish/fidelity-unknown'    'FID'
MergeLeg 'finish/network-persistence' 'PRST'

# 3 - ban the junk marker from the repo permanently
if (-not (Select-String -Path .gitignore -Pattern 'orch_launched' -Quiet)) {
  Add-Content .gitignore "`n# orchestrator launch marker - runtime junk, never history`n.claude/.orch_launched"
}
if (Test-Path .claude\.orch_launched) { G rm -q --cached --ignore-unmatch .claude/.orch_launched }

# 4 - the day's paperwork, one commit
G add .gitignore harness/prompts harness/legs.json harness/board.py harness/AM_BATTLE_PLAN.md harness/notes/CLOSE_2026-08-08.ps1 harness/notes/CLOSE_FIX_2026-08-08.ps1 harness/notes/RULING_SHEET_2026-08-08.md harness/notes/ping_watch.ps1 harness/notes/status_pulse.ps1 harness/notes/board.html harness/notes/receipts/BASE.json harness/notes/receipts/VER1.json harness/notes/guard_live_probe.py
G commit -m "feat(harness): wave-1 close - 10-leg finish board, live meter, receipts, close protocol + exit-checked fix script"

# 5 - Gate C, one deliberate push, closed behind you
$env:SYNAPSE_GATE_C = 1
G push origin master
$env:SYNAPSE_GATE_C = $null

# 6 - banner is EARNED: verify, then speak
$stillMerging = Test-Path .git\MERGE_HEAD
$unmerged = @(git diff --name-only --diff-filter=U)
$merges = @(git log --oneline -8 --merges) -match 'GUARD|FRZ|FID|PRST'
if (-not $stillMerging -and $unmerged.Count -eq 0 -and $merges.Count -eq 4) {
  Write-Host ''
  Write-Host 'VERIFIED: 4 merges landed, no conflicts remain, pushed. WAVE 1 CLOSED.' -ForegroundColor Green
  Write-Host 'Held legs (STAT DOCS CLOCK M6) wait on your letters.' -ForegroundColor Gray
} else {
  Write-Host "INCOMPLETE: merging=$stillMerging unmerged=$($unmerged.Count) merges_found=$($merges.Count)/4 - screenshot this." -ForegroundColor Red
}
