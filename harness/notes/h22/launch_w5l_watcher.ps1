$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\User\SYNAPSE\harness\notes\h22\watch_w5l_verdict.ps1' -WindowStyle Hidden -PassThru
$p.Id | Out-File C:\Users\User\SYNAPSE\harness\notes\h22\w5l-watcher.pid -Encoding ascii
Write-Host ('watcher armed, pid ' + $p.Id)
