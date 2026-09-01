# prove_bp2_dryrun.ps1 - zero-token proof of the BP2 live manifest BEFORE the arm word.
# Runs harness/orchestrate.ps1 -DryRun -Budget 10turns against a copy of
# waves/bp2.live.json in a THROWAWAY repo (Backup-Branches is not -DryRun-guarded and
# pushes non-master worktree branches - isolation is the BP1 discipline, see
# runs/2026-08-31/prove_orchestrate_*.ps1). What it must show:
#   - METER, PANELTRUTH, LATENCY, STORE read 'ready' and dry-dispatch (4 launches)
#   - PANELDESIGN reads 'held' and never dispatches
#   - CRUX reads 'blocked' (deps' receipts absent) and never dispatches
#   - rails: 4 turns charged of 10, 6 remaining, tokens UNKNOWN (ledger artifact)
param([int]$RunSeconds = 15)
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $PSCommandPath
$src  = 'C:\Users\User\SYNAPSE'
$Orch = Join-Path $src 'harness\orchestrate.ps1'

$root  = Join-Path $env:TEMP 'bp2_orch_dryrun'
$repo  = Join-Path $root 'repo'
$notes = Join-Path $repo 'harness\notes'
$manif = Join-Path $root 'bp2_dryrun_manifest.json'
if (Test-Path $root) { Remove-Item $root -Recurse -Force -EA SilentlyContinue }
New-Item -ItemType Directory -Force -Path $notes | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $repo 'harness\battleplan\runs') | Out-Null
git -C $repo init -q 2>&1 | Out-Null
git -C $repo symbolic-ref HEAD refs/heads/master 2>&1 | Out-Null
Set-Content (Join-Path $repo 'seed.txt') 'seed'
git -C $repo add -A 2>&1 | Out-Null
git -C $repo -c user.email=c@c -c user.name=control commit -q -m seed 2>&1 | Out-Null
Copy-Item (Join-Path $src 'harness\rails.py') (Join-Path $repo 'harness\rails.py') -Force
Copy-Item (Join-Path $src 'harness\rails_exec.json') (Join-Path $repo 'harness\rails_exec.json') -Force

# the real BP2 manifest, repo/settings re-pointed at the scratch tree - legs untouched
$m = Get-Content (Join-Path $src 'harness\battleplan\waves\bp2.live.json') -Raw | ConvertFrom-Json
$m.repo = $repo
$m.settings = (Join-Path $root 'settings.json')
$m._comment = 'DRY-RUN CONTROL copy of bp2.live.json (2026-09-01). Never dispatch for real from this file.'
($m | ConvertTo-Json -Depth 8) | Set-Content -Path $manif -Encoding utf8

$p = Start-Process powershell -PassThru -WindowStyle Hidden -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Orch,
    '-DryRun', '-Quiet', '-Budget', '10turns',
    '-Repo', $repo, '-ManifestPath', $manif,
    '-PollSeconds', '300', '-IdlePollSeconds', '300', '-DigestMinutes', '999', '-MaxHours', '1')
Start-Sleep -Seconds $RunSeconds
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -EA SilentlyContinue }
Start-Sleep -Seconds 1

$lg = Get-ChildItem $notes -Filter 'orchestrator_*.log' -EA SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $lg) { Write-Host 'NO LOG PRODUCED'; exit 1 }
Copy-Item $lg.FullName (Join-Path $here 'orch_dryrun_bp2.log') -Force
Write-Host '=== orchestrator -DryRun -Budget 10turns (bp2.live.json copy) ==='
Get-Content $lg.FullName
$led = Get-ChildItem (Join-Path $repo 'harness\battleplan\runs') -Recurse -Filter 'ledger_orch_*.json' -EA SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($led) {
    Copy-Item $led.FullName (Join-Path $here 'ledger_orch_dryrun_bp2.json') -Force
    Write-Host '=== rails ledger (copied to ledger_orch_dryrun_bp2.json) ==='
    python -c "import json,sys;d=json.load(open(sys.argv[1]));print('status',d['status'],'unit',d['enforced_unit'],'turns',d['totals']['turns'],'/',d['cap']['turns'],'remaining',d['remaining']['turns'],'tokens_in',d['totals']['tokens_in']);[print(' ',l['leg'],'admitted' if l['admitted'] else 'REFUSED') for l in d['legs']]" $led.FullName
} else { Write-Host 'NO rails ledger produced - the -Budget path did not run' }
