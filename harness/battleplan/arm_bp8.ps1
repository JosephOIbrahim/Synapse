# arm_bp8.ps1 - arm wave BP8 (clone of arm_bp7.ps1, wave id swap) WITH budget rails.
# Two reasoning builders (WATCHDOG, TIMEOUTS) + CRUX referee + TIDY mechanical. Default 6turns =
# 4 dispatches + 2 slack for re-dispatch; 70M token ceiling is the CTO seat's ESTIMATE, not a
# measurement (narrow briefs, turn caps 20/25; BP5's legs ran ~32M each). A settle that crosses it
# halts further dispatch - a halt is the correct failure. JEV-EDGE and JEV-DRIFT run in SHADOW:
# they ledger what they would do and change nothing. ARMED ONLY ON JOE'S WORD (2026-09-20 13:12).
# Never headless through DC; DC polls the log.
param([string]$Budget = '6turns,70000000tokens')
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\User\SYNAPSE'
$af   = Join-Path $repo 'harness\battleplan'

$pidFile = Join-Path $repo 'harness\notes\h22\orchestrator-bp8.pid'
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$old" -ErrorAction SilentlyContinue
    if ($proc) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue; Write-Host ("killed stale bp8 orchestrator pid " + $old) }
}

python (Join-Path $af 'build_manifest_bp8.py')
if ($LASTEXITCODE -ne 0) { throw 'manifest build failed' }

$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'
$env:SYNAPSE_JEV_EDGE  = 'shadow'
$env:SYNAPSE_JEV_DRIFT = 'shadow'
$manPath = Join-Path $af 'waves\bp8.live.json'
$outLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp8.log'
$errLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp8.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $repo 'harness\orchestrate.ps1'),'-ManifestPath',$manPath,'-Budget',$Budget -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
$p.Id | Out-File $pidFile -Encoding ascii
Write-Host ("bp8 orchestrator armed, pid " + $p.Id + ", budget " + $Budget + " (rails turn = leg dispatch); JEV-EDGE + JEV-DRIFT in shadow")
