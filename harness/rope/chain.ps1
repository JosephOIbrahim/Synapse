# chain: wait out the current pass, then run whatever is still pending.
Set-Location C:\Users\User\SYNAPSE
while (Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
       Where-Object { $_.CommandLine -match 'runner\.py run' }) { Start-Sleep 15 }
Start-Sleep 5
Remove-Item harness\rope\.runner.lock -Force -ErrorAction SilentlyContinue
python harness\rope\merge_pending.py
python harness\rope\runner.py run --model claude-fable-5 --confirm-model --live-seat-ok
Write-Host "chain complete"
