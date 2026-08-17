# arm_w8.ps1 - BASTION wave 0 arm. RUN ONLY ON JOE'S EXPLICIT ARM WORD.
# Mirrors arm_w5l.ps1 (traced 2026-08-17) + verdict watcher armed as part of
# arming, per harness/bastion/PROGRAM.md. Steward NOT armed: orchestrated legs
# carry their permission profile via --settings, /rc is a manual-session concern.
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\User\SYNAPSE'
$av   = Join-Path $repo 'harness\autorevise'

# kill a previously-armed w8 orchestrator if its pid file is live
$pidFile = Join-Path $repo 'harness\notes\h22\orchestrator-w8.pid'
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$old" -ErrorAction SilentlyContinue
    if ($proc) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue; Write-Host ("killed stale w8 orchestrator pid " + $old) }
}

python (Join-Path $av 'build_manifest_w8.py')
if ($LASTEXITCODE -ne 0) { throw 'manifest build failed' }

$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'
$manPath = Join-Path $av 'waves\wave8.live.json'
$outLog  = Join-Path $repo 'harness\notes\h22\orchestrator-w8.log'
$errLog  = Join-Path $repo 'harness\notes\h22\orchestrator-w8.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $repo 'harness\orchestrate.ps1'),'-ManifestPath',$manPath -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
$p.Id | Out-File $pidFile -Encoding ascii
Write-Host ("W8 orchestrator armed, pid " + $p.Id)

$w = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $repo 'harness\notes\h22\watch_w8_verdict.ps1') -WindowStyle Hidden -PassThru
Write-Host ("W8-LIBR verdict watcher armed, pid " + $w.Id)
