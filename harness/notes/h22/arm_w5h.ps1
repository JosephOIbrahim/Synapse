# arm_w5h.ps1 - house-cleaning wave. Retires the idle w5 orchestrator, arms w5h
# with agent-teams env (team leads die at the 600s bg ceiling without the second var).
$oldPid = Get-Content 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5.pid' -ErrorAction SilentlyContinue
if ($oldPid) { Stop-Process -Id $oldPid -ErrorAction SilentlyContinue }
Stop-Process -Id 14424 -ErrorAction SilentlyContinue

$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'

$log  = 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5h.log'
$errf = 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5h.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\User\SYNAPSE\harness\orchestrate.ps1','-ManifestPath','C:\Users\User\SYNAPSE\harness\autorevise\waves\wave5h.live.json' -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $errf
$p.Id | Out-File 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5h.pid' -Encoding ascii
Write-Output ('w5h armed pid=' + $p.Id + '  teams=1 bg_ceiling=0')
