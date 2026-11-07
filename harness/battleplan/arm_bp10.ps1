# arm_bp10.ps1 - arm wave BP10 (clone of arm_bp8.ps1, wave id swap) WITH budget rails.
# HARVEST: SCAFFOLD(mech) -> CORPUS(auto) -> GUIDES(auto) -> BENCH(auto) -> CRUX(referee) -> TIDY(mech),
# fully serial, so at most one Opus leg is live at any time. Default 8turns = 6 dispatches + 2 slack for
# re-dispatch; 80M cost-weighted token ceiling is the CTO seat's ESTIMATE, not a measurement (three Opus
# builders at BP5's ~32M each would exceed it - the rails HALT is the correct failure, then Joe re-arms
# with the remaining legs). JEV-EDGE and JEV-DRIFT run in SHADOW: they ledger what they would do and
# change nothing. ARMED ONLY ON JOE'S WORD. Never headless through DC; DC polls the log.
param([string]$Budget = '8turns,80000000tokens')
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\User\SYNAPSE'
$af   = Join-Path $repo 'harness\battleplan'

$pidFile = Join-Path $repo 'harness\notes\h22\orchestrator-bp10.pid'
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$old" -ErrorAction SilentlyContinue
    if ($proc) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue; Write-Host ("killed stale bp10 orchestrator pid " + $old) }
}

python (Join-Path $af 'build_manifest_bp10.py')
if ($LASTEXITCODE -ne 0) { throw 'manifest build failed' }

$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'
$env:SYNAPSE_JEV_EDGE  = 'shadow'
$env:SYNAPSE_JEV_DRIFT = 'shadow'
$manPath = Join-Path $af 'waves\bp10.live.json'
$outLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp10.log'
$errLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp10.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $repo 'harness\orchestrate.ps1'),'-ManifestPath',$manPath,'-Budget',$Budget -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
$p.Id | Out-File $pidFile -Encoding ascii
Write-Host ("bp10 orchestrator armed, pid " + $p.Id + ", budget " + $Budget + " (rails turn = leg dispatch); JEV-EDGE + JEV-DRIFT in shadow")
