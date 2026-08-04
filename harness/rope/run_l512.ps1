Set-Location C:\Users\User\SYNAPSE
$H = "="*70
Write-Host $H -ForegroundColor Cyan
Write-Host "  ROPE / L5-12  rail-meter radius -- option (a), ruled by Joe" -ForegroundColor Cyan
Write-Host $H -ForegroundColor Cyan
Write-Host ""
Write-Host "[1/2] merging staged task into the board..." -ForegroundColor Yellow
python harness\rope\merge_pending.py
Write-Host ""
Write-Host "[2/2] dispatching L5-12 to claude-fable-5..." -ForegroundColor Yellow
Write-Host "      (agent output streams below; verdict is mechanical)" -ForegroundColor DarkGray
Write-Host ""
$job = Start-Job -ScriptBlock {
  Set-Location C:\Users\User\SYNAPSE
  python harness\rope\runner.py run --model claude-fable-5 --confirm-model --task L5-12 2>&1
}
$seen = 0
while ($job.State -eq "Running") {
  if (Test-Path harness\rope\last_run.log) {
    $lines = @(Get-Content harness\rope\last_run.log -ErrorAction SilentlyContinue)
    if ($lines.Count -gt $seen) {
      $lines[$seen..($lines.Count-1)] | ForEach-Object { Write-Host "  | $_" -ForegroundColor DarkGray }
      $seen = $lines.Count
    }
  }
  Start-Sleep 2
}
Receive-Job $job | ForEach-Object { Write-Host $_ -ForegroundColor White }
Remove-Job $job
Write-Host ""
Write-Host $H -ForegroundColor Cyan
python harness\rope\runner.py gate
Write-Host ""
Get-Content harness\rope\results.tsv -Tail 2
Write-Host ""
Write-Host "  done -- press Enter to close" -ForegroundColor Green
Read-Host
