# prove_orchestrate_additive.ps1 - BP1-RAILS Target 3 / acceptance predicate 3.
#
# Captures a bounded -DryRun control log of harness/orchestrate.ps1 invoked
# WITHOUT -Budget. Run once with -Label before (against the unedited file), once
# with -Label after (against the edited file); a normalized diff of the two must
# be EMPTY, proving the -Budget addition is byte-for-byte additive on the default
# path.
#
# ISOLATION (base_control discipline): Backup-Branches runs every poll and is NOT
# -DryRun-guarded - it pushes non-master worktree branches. So this runs against
# a THROWAWAY repo OUTSIDE the SYNAPSE tree ($env:TEMP\rails_orch_control), where
# that function has nothing to find and no remote to push to.
param(
    [string]$Label = 'before',
    [int]$RunSeconds = 8
)

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $PSCommandPath
$Orch = (Resolve-Path (Join-Path $here '..\..\..\orchestrate.ps1')).Path

$root   = Join-Path $env:TEMP 'rails_orch_control'
$repo   = Join-Path $root 'repo'
$notes  = Join-Path $repo 'harness\notes'
$manif  = Join-Path $root 'control_manifest.json'

# --- scratch repo (idempotent: identical for before + after) -----------------
if (-not (Test-Path $notes)) {
    New-Item -ItemType Directory -Force -Path $notes | Out-Null
    git -C $repo init -q 2>&1 | Out-Null
    git -C $repo symbolic-ref HEAD refs/heads/master 2>&1 | Out-Null
    Set-Content (Join-Path $repo 'seed.txt') 'seed'
    git -C $repo add -A 2>&1 | Out-Null
    git -C $repo -c user.email=c@c -c user.name=control commit -q -m seed 2>&1 | Out-Null
}

# A fixed two-leg manifest, no deps -> both read 'ready' -> both dry-dispatch.
$manifest = @{
    _comment = 'CONTROL for BP1-RAILS orchestrate additive proof. Never dispatch for real.'
    _schema  = 'legs/v1'
    repo     = $repo
    settings = 'C:/scratch/settings.json'
    effort   = 'ultracode'
    base     = 'master'
    model    = 'claude-opus-4-8'
    legs     = @(
        @{ id = 'CTRLA'; name = 'control leg A'; branch = 'control/ctrla'; worktree = 'wt/ctrla'; prompt = 'briefs/ctrla.md'; receipt = 'CTRLA.json'; deps = @() },
        @{ id = 'CTRLB'; name = 'control leg B'; branch = 'control/ctrlb'; worktree = 'wt/ctrlb'; prompt = 'briefs/ctrlb.md'; receipt = 'CTRLB.json'; deps = @() }
    )
}
($manifest | ConvertTo-Json -Depth 6) | Set-Content -Path $manif -Encoding utf8

# --- one bounded dry run -----------------------------------------------------
Get-ChildItem $notes -Filter 'orchestrator_*.log' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
$p = Start-Process powershell -PassThru -WindowStyle Hidden -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Orch,
    '-DryRun', '-Quiet',
    '-Repo', $repo,
    '-ManifestPath', $manif,
    '-PollSeconds', '300', '-IdlePollSeconds', '300',
    '-DigestMinutes', '999', '-MaxHours', '1')
Start-Sleep -Seconds $RunSeconds
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -EA SilentlyContinue }
Start-Sleep -Seconds 1

$lg = Get-ChildItem $notes -Filter 'orchestrator_*.log' -EA SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $lg) { Write-Host "NO LOG PRODUCED for $Label"; exit 1 }

$raw = Get-Content $lg.FullName
Set-Content -Path (Join-Path $here "orch_dryrun_$Label.raw.log") -Value $raw -Encoding utf8

# --- normalize the inherently time-varying fields ----------------------------
# Only wall-clock artifacts are stripped; every code-driven line is preserved so
# a real behavioural change would still surface in the diff.
$norm = $raw | ForEach-Object {
    $l = $_ -replace '^\d{2}:\d{2}:\d{2}\s+', ''                  # per-line time prefix
    $l = $l -replace 'orchestrator_\d{8}-\d{6}\.log', 'orchestrator_<TS>.log'
    $l = $l -replace 'first at \d{2}:\d{2}', 'first at <HH:MM>'
    $l = $l -replace 'last write \d+m ago', 'last write <N>m ago'
    $l
}
Set-Content -Path (Join-Path $here "orch_dryrun_$Label.norm.log") -Value $norm -Encoding utf8
Write-Host "captured $Label : $($raw.Count) lines -> orch_dryrun_$Label.norm.log"
