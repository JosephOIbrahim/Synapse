$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\User\SYNAPSE'
$av   = Join-Path $repo 'harness\autorevise'

# kill a previously-armed w5l orchestrator if its pid file is live
$pidFile = Join-Path $repo 'harness\notes\h22\orchestrator-w5l.pid'
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$old" -ErrorAction SilentlyContinue
    if ($proc) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue; Write-Host ("killed stale w5l orchestrator pid " + $old) }
}

python (Join-Path $av 'build_manifest_w5l.py')
if ($LASTEXITCODE -ne 0) { throw 'manifest build failed' }

$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'
$manPath = Join-Path $av 'waves\wave5l.live.json'
$outLog  = Join-Path $repo 'harness\notes\h22\orchestrator-w5l.log'
$errLog  = Join-Path $repo 'harness\notes\h22\orchestrator-w5l.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $repo 'harness\orchestrate.ps1'),'-ManifestPath',$manPath -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
$p.Id | Out-File $pidFile -Encoding ascii
Write-Host ("orchestrator armed, pid " + $p.Id)
