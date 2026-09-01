# prove_bp2_meter_dryrun.ps1 - BP2-METER acceptance #5.
#
# The -DryRun control (NO -Budget) must be byte-identical after BP2-METER's
# additive edits to orchestrate.ps1 (T1 settle, T2 tier resolve, T3 drift - all
# gated behind -Budget or a leg.tier). This captures a bounded dry run against
# BOTH the pre-edit orchestrate.ps1 (git show HEAD:..., before my BP2-METER edits)
# AND the edited working copy, over the SAME throwaway repo + manifest, normalizes
# only the wall-clock fields, and Compare-Objects the two. An EMPTY diff is PASS.
#
# Same-environment on purpose: both logs are written by the same Set-Content, so
# there is no CRLF-vs-LF checkout artifact - a real behavioural change is the only
# thing that can make the diff non-empty. Isolated in $env:TEMP so Backup-Branches
# has no remote and no dry-run worktree is ever created.
param([int]$RunSeconds = 8)
$ErrorActionPreference = 'Continue'
$here     = Split-Path -Parent $PSCommandPath
$repoRoot = (Resolve-Path (Join-Path $here '..\..\..\..')).Path
$editedOrch = Join-Path $repoRoot 'harness\orchestrate.ps1'

$root  = Join-Path $env:TEMP 'bp2meter_dryctl'
$repo  = Join-Path $root 'repo'
$notes = Join-Path $repo 'harness\notes'
$manif = Join-Path $root 'control_manifest.json'
if (-not (Test-Path $notes)) {
    New-Item -ItemType Directory -Force -Path $notes | Out-Null
    git -C $repo init -q 2>&1 | Out-Null
    git -C $repo symbolic-ref HEAD refs/heads/master 2>&1 | Out-Null
    Set-Content (Join-Path $repo 'seed.txt') 'seed'
    git -C $repo add -A 2>&1 | Out-Null
    git -C $repo -c user.email=c@c -c user.name=control commit -q -m seed 2>&1 | Out-Null
}
$manifest = @{
    _comment = 'CONTROL for BP2-METER dry-run additive proof. Never dispatch for real.'
    _schema  = 'legs/v1'; repo = $repo; settings = 'C:/scratch/settings.json'
    effort = 'ultracode'; base = 'master'; model = 'claude-opus-4-8'
    legs = @(
        @{ id = 'CTRLA'; name = 'control leg A'; branch = 'control/ctrla'; worktree = 'wt/ctrla'; prompt = 'briefs/ctrla.md'; receipt = 'CTRLA.json'; deps = @() },
        @{ id = 'CTRLB'; name = 'control leg B'; branch = 'control/ctrlb'; worktree = 'wt/ctrlb'; prompt = 'briefs/ctrlb.md'; receipt = 'CTRLB.json'; deps = @() }
    )
}
($manifest | ConvertTo-Json -Depth 6) | Set-Content -Path $manif -Encoding utf8

function Capture([string]$orch, [string]$label) {
    Get-ChildItem $notes -Filter 'orchestrator_*.log' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
    $p = Start-Process powershell -PassThru -WindowStyle Hidden -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $orch,
        '-DryRun', '-Quiet', '-Repo', $repo, '-ManifestPath', $manif,
        '-PollSeconds', '300', '-IdlePollSeconds', '300', '-DigestMinutes', '999', '-MaxHours', '1')
    Start-Sleep -Seconds $RunSeconds
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -EA SilentlyContinue }
    Start-Sleep -Seconds 1
    $lg = Get-ChildItem $notes -Filter 'orchestrator_*.log' -EA SilentlyContinue |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $lg) { Write-Host "NO LOG for $label"; return $null }
    $norm = (Get-Content $lg.FullName) | ForEach-Object {
        $l = $_ -replace '^\d{2}:\d{2}:\d{2}\s+', ''
        $l = $l -replace 'orchestrator_\d{8}-\d{6}\.log', 'orchestrator_<TS>.log'
        $l = $l -replace 'first at \d{2}:\d{2}', 'first at <HH:MM>'
        $l = $l -replace 'last write \d+m ago', 'last write <N>m ago'
        $l
    }
    $out = Join-Path $here ("dryrun_$label.norm.log")
    $norm | Set-Content -Path $out -Encoding utf8
    return $out
}

# The pre-edit orchestrate.ps1 must run from INSIDE harness/ so its
# $PSScriptRoot\lib\quote-safe.ps1 sibling resolves - extracting it to a bare temp
# dir would break that dot-source and forge a false diff. Placed alongside the
# real one under a temp name, run, then removed (never committed / git-tracked).
$baseOrch = Join-Path $repoRoot 'harness\_orch_base_bp2meter_tmp.ps1'
try {
    (& git -C $repoRoot show 'HEAD~1:harness/orchestrate.ps1') | Set-Content -Path $baseOrch -Encoding utf8
    $before = Capture $baseOrch 'baseline'
    $after  = Capture $editedOrch 'edited'
} finally {
    Remove-Item $baseOrch -Force -EA SilentlyContinue
}

$diffFile = Join-Path $here 'dryrun_bp2meter_diff.txt'
$diff = Compare-Object (Get-Content $before) (Get-Content $after)
if ($diff) {
    $diff | Format-Table | Out-String | Set-Content -Path $diffFile -Encoding utf8
    Write-Host "DIFF NON-EMPTY -> FAIL (see $diffFile)"
    exit 1
}
'' | Set-Content -Path $diffFile -Encoding utf8
Write-Host "EMPTY DIFF -> the -DryRun control is byte-identical after BP2-METER's edits (acceptance #5 PASS)"
