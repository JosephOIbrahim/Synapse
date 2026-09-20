# arm_bp6.ps1 - arm wave BP6 (clone of arm_bp4.ps1, wave id swap) WITH budget rails.
# One leg (BP6-JEV, reasoning tier via JEV-ROUTE). Default 3turns = 1 dispatch + 2 slack
# for re-dispatch; 40M token ceiling ~ one Opus leg. ARMED ONLY ON JOE'S WORD (2026-09-19).
# Never headless through DC; DC polls the log.
param([string]$Budget = '3turns,40000000tokens')
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\User\SYNAPSE'
$af   = Join-Path $repo 'harness\battleplan'

$pidFile = Join-Path $repo 'harness\notes\h22\orchestrator-bp6.pid'
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$old" -ErrorAction SilentlyContinue
    if ($proc) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue; Write-Host ("killed stale bp6 orchestrator pid " + $old) }
}

python (Join-Path $af 'build_manifest_bp6.py')
if ($LASTEXITCODE -ne 0) { throw 'manifest build failed' }

$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'
$manPath = Join-Path $af 'waves\bp6.live.json'
$outLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp6.log'
$errLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp6.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $repo 'harness\orchestrate.ps1'),'-ManifestPath',$manPath,'-Budget',$Budget -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
$p.Id | Out-File $pidFile -Encoding ascii
Write-Host ("bp6 orchestrator armed, pid " + $p.Id + ", budget " + $Budget + " (rails turn = leg dispatch)")
