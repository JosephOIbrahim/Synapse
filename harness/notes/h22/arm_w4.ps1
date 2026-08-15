$log = 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w4.log'
$errf = 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w4.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\User\SYNAPSE\harness\orchestrate.ps1','-ManifestPath','C:\Users\User\SYNAPSE\harness\autorevise\waves\wave4.live.json' -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $errf
$p.Id | Out-File 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w4.pid' -Encoding ascii
Write-Output ('armed pid=' + $p.Id)
