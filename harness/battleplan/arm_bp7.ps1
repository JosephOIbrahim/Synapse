# arm_bp7.ps1 - arm wave BP6 (clone of arm_bp4.ps1, wave id swap) WITH budget rails.
# Four scouts + SYNTH, tiers via JEV-ROUTE. Default 8turns = 5 dispatches + 3 slack
# for re-dispatch; 60M ceiling: scouts expected mechanical, SYNTH reasoning. ARMED ONLY ON JOE'S WORD (2026-09-20).
# Never headless through DC; DC polls the log.
param([string]$Budget = '8turns,60000000tokens')
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\User\SYNAPSE'
$af   = Join-Path $repo 'harness\battleplan'

$pidFile = Join-Path $repo 'harness\notes\h22\orchestrator-bp7.pid'
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$old" -ErrorAction SilentlyContinue
    if ($proc) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue; Write-Host ("killed stale bp7 orchestrator pid " + $old) }
}

python (Join-Path $af 'build_manifest_bp7.py')
if ($LASTEXITCODE -ne 0) { throw 'manifest build failed' }

$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'
$manPath = Join-Path $af 'waves\bp7.live.json'
$outLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp7.log'
$errLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp7.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $repo 'harness\orchestrate.ps1'),'-ManifestPath',$manPath,'-Budget',$Budget -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
$p.Id | Out-File $pidFile -Encoding ascii
Write-Host ("bp7 orchestrator armed, pid " + $p.Id + ", budget " + $Budget + " (rails turn = leg dispatch)")
