# rope watch -- live dashboard for the GATE A marathon.
# Close this window anytime: the runner is a separate process and keeps going.
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
while ($true) {
  Clear-Host
  Write-Host ("ROPE MARATHON  " + (Get-Date -Format "HH:mm:ss") + "   (closing this window does NOT stop the run)") -ForegroundColor Cyan
  $pids = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
          Where-Object { $_.CommandLine -match 'runner\.py run' } | Select-Object -ExpandProperty ProcessId
  if ($pids) { Write-Host ("runner: ALIVE  pid " + ($pids -join ",")) -ForegroundColor Green }
  else       { Write-Host "runner: NOT RUNNING (finished or stopped -- see gate below)" -ForegroundColor Yellow }
  python harness\rope\runner.py gate 2>$null
  Write-Host ""
  Write-Host "-- tasks (non-pending) --" -ForegroundColor DarkCyan
  python harness\rope\runner.py status 2>$null | Select-String -NotMatch " pending "
  Write-Host ""
  Write-Host "-- ledger (last 8) --" -ForegroundColor DarkCyan
  Get-Content harness\rope\results.tsv -Tail 8 -ErrorAction SilentlyContinue
  Write-Host ""
  Write-Host "-- current agent (last_run.log tail) --" -ForegroundColor DarkCyan
  Get-Content harness\rope\last_run.log -Tail 8 -ErrorAction SilentlyContinue
  $err = Get-Item harness\rope\runner_console.err.log -ErrorAction SilentlyContinue
  if ($err -and $err.Length -gt 0) {
    Write-Host "-- stderr (frays visibly) --" -ForegroundColor Red
    Get-Content $err.FullName -Tail 3
  }
  Start-Sleep 5
}
