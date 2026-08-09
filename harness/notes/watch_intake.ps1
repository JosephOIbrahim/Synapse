# Completion watcher — pops the intake log in Notepad the moment it lands
$log = 'C:\Users\User\SYNAPSE\harness\notes\intake_syn-next-001.log'
while (-not (Test-Path $log)) { Start-Sleep -Seconds 15 }
Start-Sleep -Seconds 5
Start-Process notepad $log
