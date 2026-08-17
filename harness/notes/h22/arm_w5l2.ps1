# arm_w5l2.ps1 - bounce the w5l orchestrator onto merged-master code (GATE close-gates live).
# Retires the pre-merge supervisor (pid 74056), relaunches on the same 22-leg manifest.
$oldPid = Get-Content 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5l.pid' -ErrorAction SilentlyContinue
if ($oldPid) { Stop-Process -Id $oldPid -ErrorAction SilentlyContinue; Write-Output ('stopped old orchestrator ' + $oldPid) }

$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'

$log  = 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5l.log'
$errf = 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5l.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\User\SYNAPSE\harness\orchestrate.ps1','-ManifestPath','C:\Users\User\SYNAPSE\harness\autorevise\waves\wave5l.live.json' -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $errf
$p.Id | Out-File 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5l.pid' -Encoding ascii
Write-Output ('w5l re-armed on hardened code pid=' + $p.Id + '  teams=1 bg_ceiling=0')
