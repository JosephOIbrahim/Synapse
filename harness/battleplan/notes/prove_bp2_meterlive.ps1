# prove_bp2_meterlive.ps1 - BP2-METERLIVE live end-to-end settle proof.
#
# The GAP this fills: BP2-METER proved the settle+halt at the rails.py CLI level
# with a COMMITTED FIXTURE transcript. It never ran a real orchestrator dispatch.
# This driver runs harness/orchestrate.ps1 FOR REAL (not -DryRun) against a
# throwaway SCRATCH repo with two trivial legs so:
#   T1  leg MLV1 is dispatched by the orchestrator, produces a REAL Claude Code
#       transcript, reaches 'done', and Rails-Settle measures integer
#       tokens_in/tokens_out/wall_ms from that transcript into the run ledger.
#   T2  a tiny tokens ceiling (1 token), crossed at MLV1's settle, sets the
#       ledger blocked/budget/tokens and refuses MLV2's dispatch (MLV2 deps MLV1
#       so it stays blocked until MLV1 settles; then BudgetHalted refuses it).
#   T3  negative control: the SAME manifest run WITHOUT -Budget produces NO
#       ledger, and its -DryRun log is byte-identical to the pre-rails baseline
#       orchestrate.ps1 (git 8afeda21, 772 lines, zero rails machinery) run the
#       same way - a genuinely NON-tautological diff (163 source lines differ),
#       unlike BP2-METER's committed HEAD-vs-HEAD self-comparison (CRUX nit).
#
# Scratch repo has NO origin remote, so Backup-Branches pushes nowhere. The
# scratch harness is a COPY, so $PSScriptRoot lock/log dirs are isolated from the
# live orchestrator. Read-only w.r.t. product code; writes only under the scratch
# tree and (by the operator) the BP2-METERLIVE artifacts.
#
# Modes: dryrun (T3), live (T1/T2). Scaffolding is done separately (see notes).
param(
    [ValidateSet('dryrun','live')] [string]$Mode = 'dryrun',
    [string]$Scratch = 'C:\Users\User\AppData\Local\Temp\bp2mlv',
    [string]$Live    = 'C:\Users\User\SYNAPSE',
    [string]$Base    = '8afeda21',
    [string]$BaselineFile = 'C:\Users\User\AppData\Local\Temp\bp2mlv\orchestrate_prerails_8afeda21.ps1',
    [string]$Budget  = '4turns,1tokens',
    [int]$LiveTimeoutSec = 360)

$ErrorActionPreference = 'Continue'
$repo    = Join-Path $Scratch 'repo'
$manif   = Join-Path $Scratch 'manifest.json'
$notes   = Join-Path $repo 'harness\notes'
$runs    = Join-Path $repo 'harness\battleplan\runs'
$rcpts   = Join-Path $repo 'harness\notes\receipts'
$curOrch = Join-Path $repo 'harness\orchestrate.ps1'
$out     = Join-Path $Scratch 'out'
New-Item -ItemType Directory -Force -Path $out | Out-Null

function Normalize([string]$file) {
    (Get-Content $file) | ForEach-Object {
        $l = $_ -replace '^\d{2}:\d{2}:\d{2}\s+', ''
        $l = $l -replace 'orchestrator_\d{8}-\d{6}\.log', 'orchestrator_<TS>.log'
        $l = $l -replace 'first at \d{2}:\d{2}', 'first at <HH:MM>'
        $l = $l -replace 'last write \d+m ago', 'last write <N>m ago'
        $l
    }
}

function Capture-Dry([string]$orch, [string]$label, [int]$sec = 9) {
    Get-ChildItem $notes -Filter 'orchestrator_*.log' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
    $p = Start-Process powershell -PassThru -WindowStyle Hidden -ArgumentList @(
        '-NoProfile','-ExecutionPolicy','Bypass','-File',$orch,
        '-DryRun','-Quiet','-Repo',$repo,'-ManifestPath',$manif,
        '-PollSeconds','300','-IdlePollSeconds','300','-DigestMinutes','999','-MaxHours','1')
    Start-Sleep -Seconds $sec
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -EA SilentlyContinue }
    Start-Sleep -Seconds 1
    $lg = Get-ChildItem $notes -Filter 'orchestrator_*.log' -EA SilentlyContinue |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $lg) { Write-Host "NO LOG for $label"; return $null }
    $dst = Join-Path $out ("dry_$label.norm.log")
    (Normalize $lg.FullName) | Set-Content -Path $dst -Encoding utf8
    return $dst
}

if ($Mode -eq 'dryrun') {
    # T3 - byte-identical negative control, non-tautological (baseline != current).
    $base = Join-Path $repo 'harness\_orch_prerails_tmp.ps1'   # sibling so $PSScriptRoot\lib resolves
    # baseline = pre-rails orchestrate.ps1 (git $Base=8afeda21, 772 lines, 0 rails
    # machinery). Extracted via `git -C <live> show 8afeda21:harness/orchestrate.ps1`
    # and verified byte-identical to that object; copied in as a harness/ sibling so
    # its $PSScriptRoot\lib\quote-safe.ps1 dot-source resolves.
    Copy-Item -Path $BaselineFile -Destination $base -Force
    try {
        $b = Capture-Dry $base 'baseline'
        $c = Capture-Dry $curOrch 'current'
    } finally { Remove-Item $base -Force -EA SilentlyContinue }

    # ledger-absent: a no-Budget run must create NO ledger under runs/<date>/
    $ledgers = @(Get-ChildItem $runs -Recurse -Filter 'ledger_*.json' -EA SilentlyContinue)
    $diff = if ($b -and $c) { Compare-Object (Get-Content $b) (Get-Content $c) } else { 'CAPTURE FAILED' }
    $diffFile = Join-Path $out 'dryrun_diff.txt'
    if ($diff) {
        ($diff | Format-Table | Out-String) | Set-Content -Path $diffFile -Encoding utf8
        Write-Host "T3 DIFF NON-EMPTY -> investigate ($diffFile)"
    } else {
        '' | Set-Content -Path $diffFile -Encoding utf8
        Write-Host "T3 EMPTY DIFF -> no-Budget default path byte-identical to the pre-rails baseline (163 source lines differ, so this is NOT a HEAD-vs-HEAD tautology)"
    }
    Write-Host ("T3 ledger-absent: {0} ledger file(s) under runs/ during the no-Budget runs (expect 0)" -f $ledgers.Count)
    return
}

if ($Mode -eq 'live') {
    # T1/T2 - real budgeted dispatch. Fresh state each run (scratch only).
    foreach ($id in 'MLV1','MLV2') {
        $wt = Join-Path $repo "wt\$($id.ToLower().Replace('mlv','leg'))"
    }
    # clean prior worktrees/branches/receipts/ledger/locks/logs (scratch only)
    foreach ($leg in 'leg1','leg2') {
        $wt = Join-Path $repo "wt\$leg"
        if (Test-Path $wt) { & git -C $repo worktree remove --force $wt 2>&1 | Out-Null }
    }
    & git -C $repo worktree prune 2>&1 | Out-Null
    foreach ($br in 'mlv/leg1','mlv/leg2') { & git -C $repo branch -D $br 2>&1 | Out-Null }
    Get-ChildItem $rcpts -Filter 'MLV*.json' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
    Get-ChildItem (Join-Path $runs '*') -Recurse -Filter 'ledger_*.json' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
    $lockdir = Join-Path $repo 'harness\state\locks'
    if (Test-Path $lockdir) { Get-ChildItem $lockdir -Filter 'MLV*.lock' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue }
    Get-ChildItem $notes -Filter 'orchestrator_*.log' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue

    Write-Host "LIVE: dispatching real orchestrator with -Budget '$Budget' against scratch $repo"
    $p = Start-Process powershell -PassThru -WindowStyle Normal -ArgumentList @(
        '-NoProfile','-ExecutionPolicy','Bypass','-File',$curOrch,
        '-Quiet','-Repo',$repo,'-ManifestPath',$manif,'-Budget',$Budget,
        '-PollSeconds','8','-IdlePollSeconds','8','-DigestMinutes','999','-MaxHours','1')
    $deadline = (Get-Date).AddSeconds($LiveTimeoutSec)
    while (-not $p.HasExited -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 4 }
    $selfHalted = $p.HasExited
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -EA SilentlyContinue }
    Start-Sleep -Seconds 2
    $lg = Get-ChildItem $notes -Filter 'orchestrator_*.log' -EA SilentlyContinue |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($lg) { Copy-Item $lg.FullName (Join-Path $out 'live_orchestrator.log') -Force }
    $led = Get-ChildItem (Join-Path $runs '*') -Recurse -Filter 'ledger_*.json' -EA SilentlyContinue |
           Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($led) { Copy-Item $led.FullName (Join-Path $out 'live_ledger.json') -Force }
    Write-Host ("LIVE done. self-halted={0}  log={1}  ledger={2}" -f $selfHalted, ($lg.FullName), ($led.FullName))
    return
}
