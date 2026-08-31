$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\User\SYNAPSE'
$af   = Join-Path $repo 'harness\battleplan'

# kill a previously-armed bp1 orchestrator if its pid file is live
$pidFile = Join-Path $repo 'harness\notes\h22\orchestrator-bp1.pid'
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$old" -ErrorAction SilentlyContinue
    if ($proc) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue; Write-Host ("killed stale bp1 orchestrator pid " + $old) }
}

python (Join-Path $af 'build_manifest_bp1.py')
if ($LASTEXITCODE -ne 0) { throw 'manifest build failed' }

$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'
$manPath = Join-Path $af 'waves\bp1.live.json'
$outLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp1.log'
$errLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp1.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $repo 'harness\orchestrate.ps1'),'-ManifestPath',$manPath -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
$p.Id | Out-File $pidFile -Encoding ascii
Write-Host ("bp1 orchestrator armed, pid " + $p.Id)
