# Re-arm morning 2026-08-17: hardened orchestrator + fresh steward + WCRUX re-dispatch.
Set-Location C:\Users\User\SYNAPSE
# 1) orchestrator on merged-master code
$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'
$log  = 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5l.log'
$errf = 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5l.err'
$o = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\User\SYNAPSE\harness\orchestrate.ps1','-ManifestPath','C:\Users\User\SYNAPSE\harness\autorevise\waves\wave5l.live.json' -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $errf
$o.Id | Out-File 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5l.pid' -Encoding ascii
Write-Host ('orchestrator re-armed pid ' + $o.Id)
# 2) fresh steward (10h deadline baked into script)
$s = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\User\SYNAPSE\harness\notes\h22\steward.ps1' -WindowStyle Hidden -PassThru
$s.Id | Out-File 'C:\Users\User\SYNAPSE\harness\notes\h22\steward.pid' -Encoding ascii
Write-Host ('steward re-armed pid ' + $s.Id)
# 3) WCRUX re-dispatch into its existing worktree
$w = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File',(Join-Path $env:TEMP 'orch_W5-WCRUX.ps1') -WindowStyle Normal -PassThru
Write-Host ('WCRUX re-dispatched window pid ' + $w.Id)
