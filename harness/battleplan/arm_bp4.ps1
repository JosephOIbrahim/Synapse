# arm_bp4.ps1 - arm wave BP4 (clone of arm_bp1.ps1, wave id swap) WITH budget rails.
# -Budget is a rails cap: "<N>turns" or "<N>turns,<M>tokens". A rails TURN is one
# leg DISPATCH through Rails-Charge (docs/BATTLEPLAN.md 2026-09-01 sec.12 R-3), not a
# conversational turn. Default 10turns = 4 pair-leg dispatches + 6 slack for
# re-dispatch/spawn. Tokens stay UNKNOWN until BP4-METER's settle lands.
# ARMED ONLY ON JOE'S WORD. Never headless through DC; DC polls the log.
param([string]$Budget = '12turns,105000000tokens')  # 8 dispatches + 4 slack; token ceiling <= BP3's 102.8M in + 1.5M out
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\User\SYNAPSE'
$af   = Join-Path $repo 'harness\battleplan'

# kill a previously-armed bp4 orchestrator if its pid file is live
$pidFile = Join-Path $repo 'harness\notes\h22\orchestrator-bp4.pid'
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$old" -ErrorAction SilentlyContinue
    if ($proc) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue; Write-Host ("killed stale bp4 orchestrator pid " + $old) }
}

python (Join-Path $af 'build_manifest_bp4.py')
if ($LASTEXITCODE -ne 0) { throw 'manifest build failed' }

$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'
$manPath = Join-Path $af 'waves\bp4.live.json'
$outLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp4.log'
$errLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp4.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $repo 'harness\orchestrate.ps1'),'-ManifestPath',$manPath,'-Budget',$Budget -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
$p.Id | Out-File $pidFile -Encoding ascii
Write-Host ("bp4 orchestrator armed, pid " + $p.Id + ", budget " + $Budget + " (rails turn = leg dispatch)")
