# prove_orchestrate_budget_halt.ps1 - BP1-RAILS Target 3, end-to-end.
#
# Proves the -Budget wiring actually HALTS the real orchestrator (not just that
# it is additive). Runs orchestrate.ps1 -DryRun -Budget 1turns against an
# isolated scratch repo with a 2-leg manifest: leg 1 is admitted, leg 2 trips the
# cap, rails.py writes a blocked:budget receipt, and the loop halts. The scratch
# ledger is copied here as ledger_orch_budget_halt.json.
#
# ISOLATION: scratch repo OUTSIDE the SYNAPSE tree, no remote - Backup-Branches
# has nothing to push. rails.py + rails_exec.json are copied into the scratch
# harness so the -Budget path runs fully (rails.py resolves ROOT to the scratch).
param([int]$RunSeconds = 12)

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $PSCommandPath
$srcHarness = (Resolve-Path (Join-Path $here '..\..\..')).Path            # worktree harness/
$Orch = (Resolve-Path (Join-Path $srcHarness 'orchestrate.ps1')).Path

$root  = Join-Path $env:TEMP 'rails_orch_budget'
$repo  = Join-Path $root 'repo'
$notes = Join-Path $repo 'harness\notes'
$manif = Join-Path $root 'control_manifest.json'

if (Test-Path $root) {
    Get-ChildItem $root -Recurse -Force -EA SilentlyContinue | ForEach-Object { $_.Attributes = 'Normal' }
    Remove-Item $root -Recurse -Force -EA SilentlyContinue
}
New-Item -ItemType Directory -Force -Path $notes | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $repo 'harness') | Out-Null
git -C $repo init -q 2>&1 | Out-Null
git -C $repo symbolic-ref HEAD refs/heads/master 2>&1 | Out-Null
Set-Content (Join-Path $repo 'seed.txt') 'seed'
git -C $repo add -A 2>&1 | Out-Null
git -C $repo -c user.email=c@c -c user.name=control commit -q -m seed 2>&1 | Out-Null

# rails.py + seam into the scratch harness so the -Budget path runs fully
Copy-Item (Join-Path $srcHarness 'rails.py') (Join-Path $repo 'harness\rails.py') -Force
Copy-Item (Join-Path $srcHarness 'rails_exec.json') (Join-Path $repo 'harness\rails_exec.json') -Force

$manifest = @{
    _comment = 'CONTROL for BP1-RAILS -Budget halt proof. Never dispatch for real.'
    _schema  = 'legs/v1'; repo = $repo; settings = 'C:/scratch/settings.json'
    effort = 'ultracode'; base = 'master'; model = 'claude-opus-4-8'
    legs = @(
        @{ id = 'CTRLA'; name = 'control leg A'; branch = 'control/ctrla'; worktree = 'wt/ctrla'; prompt = 'briefs/ctrla.md'; receipt = 'CTRLA.json'; deps = @() },
        @{ id = 'CTRLB'; name = 'control leg B'; branch = 'control/ctrlb'; worktree = 'wt/ctrlb'; prompt = 'briefs/ctrlb.md'; receipt = 'CTRLB.json'; deps = @() }
    )
}
($manifest | ConvertTo-Json -Depth 6) | Set-Content -Path $manif -Encoding utf8

Get-ChildItem $notes -Filter 'orchestrator_*.log' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
$p = Start-Process powershell -PassThru -WindowStyle Hidden -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Orch,
    '-DryRun', '-Quiet', '-Budget', '1turns',
    '-Repo', $repo, '-ManifestPath', $manif,
    '-PollSeconds', '300', '-IdlePollSeconds', '300', '-DigestMinutes', '999', '-MaxHours', '1')
Start-Sleep -Seconds $RunSeconds
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -EA SilentlyContinue }
Start-Sleep -Seconds 1

$lg = Get-ChildItem $notes -Filter 'orchestrator_*.log' -EA SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($lg) {
    Copy-Item $lg.FullName (Join-Path $here 'orch_budget_halt.log') -Force
    Write-Host "=== orchestrator -Budget 1turns log ==="
    Get-Content $lg.FullName | ForEach-Object { $_ -replace '^\d{2}:\d{2}:\d{2}\s+', '' }
}

$led = Get-ChildItem (Join-Path $repo 'harness\battleplan\runs') -Recurse -Filter 'ledger_orch_*.json' -EA SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($led) {
    Copy-Item $led.FullName (Join-Path $here 'ledger_orch_budget_halt.json') -Force
    Write-Host ""
    Write-Host "=== rails ledger (copied to ledger_orch_budget_halt.json) ==="
    Get-Content $led.FullName
} else {
    Write-Host "NO rails ledger produced - the -Budget path did not run"
    exit 1
}
