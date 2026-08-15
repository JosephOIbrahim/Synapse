Stop-Process -Id 55124 -ErrorAction SilentlyContinue
$log = 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5.log'
$errf = 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\User\SYNAPSE\harness\orchestrate.ps1','-ManifestPath','C:\Users\User\SYNAPSE\harness\autorevise\waves\wave5.live.json' -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $errf
$p.Id | Out-File 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5.pid' -Encoding ascii
Write-Output ('armed pid=' + $p.Id)
