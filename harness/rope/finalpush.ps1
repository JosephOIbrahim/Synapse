Set-Location C:\Users\User\SYNAPSE
while (Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'runner\.py run' }) { Start-Sleep 30 }
Start-Sleep 10
git push origin rope/gate-a 2>&1 | Out-Null
Write-Host "final push done -- rope/gate-a fully on GitHub"
