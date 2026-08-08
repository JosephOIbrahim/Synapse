# CLOSE_2026-08-08.ps1 - wave-1 close in ONE reviewed paste.
# You running this IS the human gate (Constitution 2026-08-01: merges and
# push are yours; relayed approval is not consent). Read top to bottom once.
# Self-verifying: aborts if any receipt is missing or not green - safe to
# paste the minute the toast fires.
$ErrorActionPreference = 'Stop'
Set-Location C:\Users\User\Synapse

$legs = @(
  @{id='WARN';  wt='.claude\worktrees\warn-not-refuse';     br='finish/warn-not-refuse'},
  @{id='GUARD'; wt='.claude\worktrees\shotlayers-guard';    br='finish/shotlayers-guard'},
  @{id='FRZ';   wt='.claude\worktrees\freeze-attribution';  br='finish/freeze-attribution'},
  @{id='FID';   wt='.claude\worktrees\fidelity-unknown';    br='finish/fidelity-unknown'},
  @{id='PRST';  wt='.claude\worktrees\network-persistence'; br='finish/network-persistence'}
)

# 0 - discard the orchestrator twin's competing edit; the receipted,
#     DryRun-verified BASE fix lives in the MAIN tree and stays.
git -C .claude\worktrees\orch-dispatch checkout -- harness/orchestrate.ps1

# 1 - verify every receipt green, commit any uncommitted receipted work in
#     its own worktree (FRZ closed dirty), then merge each branch.
foreach ($l in $legs) {
  $r = Join-Path $l.wt "harness\notes\receipts\$($l.id).json"
  if (-not (Test-Path $r)) { throw "ABORT: $($l.id) receipt missing - leg not done." }
  $s = (Get-Content $r -Raw | ConvertFrom-Json).status
  if ("$s" -notlike 'green*') { throw "ABORT: $($l.id) status '$s' - read the receipt before merging." }
  Write-Host ("{0,-6} {1}" -f $l.id, $s) -ForegroundColor Green
  if (git -C $l.wt status --porcelain) {
    git -C $l.wt add -A
    git -C $l.wt commit -m "$($l.id): close-out commit of receipted work (see harness/notes/receipts/$($l.id).json)"
  }
  git merge --no-ff $l.br -m "merge $($l.id): receipted green - wave 1 finish"
}

# 2 - main tree: BASE fix + scaffold + receipts, one commit, then push.
git add harness/prompts harness/legs.json harness/board.py `
        harness/AM_BATTLE_PLAN.md harness/orchestrate.ps1 `
        harness/notes/receipts/BASE.json harness/notes/receipts/VER1.json `
        harness/notes/RULING_SHEET_2026-08-08.md harness/notes/CLOSE_2026-08-08.ps1 `
        harness/notes/ping_watch.ps1 harness/notes/board.html
git commit -m "feat(harness): wave-1 finish board - 10 legs scaffolded, BASE dispatch fix (per-leg base + model passthrough), live board meter, VER1+BASE receipts, close protocol"

# Gate C: opened deliberately for this one push, closed immediately after.
# You running this script IS the deliberate human act the gate exists for.
$env:SYNAPSE_GATE_C = 1
git push origin master
$env:SYNAPSE_GATE_C = $null

Write-Host ''
Write-Host 'WAVE 1 CLOSED AND PUSHED. Held legs (STAT DOCS CLOCK M6) wait on your letters.' -ForegroundColor Green
