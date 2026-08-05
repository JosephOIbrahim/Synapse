# rope /remote-control -- outbound beacon + quota sentinel. Close anytime.
# Beacon: pushes STATUS.md to branch rope/beacon every cycle (phone-readable).
# Sentinel: if the runner quota-paused with work left, relaunches it (max 6).
$repo = "C:\Users\User\SYNAPSE"
$bw   = "C:\Users\User\rope-beacon-wt"   # separate worktree: no index races
Set-Location $repo
if (-not (Test-Path $bw)) { git worktree add -B rope/beacon $bw 2>&1 | Out-Null }
$relaunches = 0
function RunnerAlive {
  [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'runner\.py run' })
}
while ($true) {
  Set-Location $repo
  $gate   = (python harness\rope\runner.py gate 2>$null) -join "`n"
  $tail   = (Get-Content harness\rope\results.tsv -Tail 10 -ErrorAction SilentlyContinue) -join "`n"
  $alive  = RunnerAlive
  $last   = (Get-Content harness\rope\results.tsv -Tail 1 -ErrorAction SilentlyContinue)
  $paused = $last -match "quota-pause"
  $pend   = $gate -match '"pending": [1-9]'
  if ((-not $alive) -and $paused -and $pend -and $relaunches -lt 6) {
    $relaunches++
    Start-Process python -ArgumentList "harness\rope\runner.py","run","--model","claude-fable-5","--confirm-model","--live-seat-ok" `
      -WorkingDirectory $repo -WindowStyle Minimized `
      -RedirectStandardOutput "harness\rope\runner_console.log" `
      -RedirectStandardError "harness\rope\runner_console.err.log" | Out-Null
    Start-Sleep 15; $alive = RunnerAlive
  }
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  $md = @"
# ROPE /remote-control beacon
**$stamp** | runner: $(if($alive){"ALIVE"}else{"stopped"}) | sentinel relaunches used: $relaunches/6

## Gate
``````
$gate
``````

## Ledger (last 10)
``````
$tail
``````

Refresh this page for updates (~5 min cycle). Read-only: this beacon carries
status OUT; it executes nothing FROM the repo, by design.
"@
  Set-Content -Path (Join-Path $bw "STATUS.md") -Value $md -Encoding UTF8
  git -C $bw add STATUS.md 2>&1 | Out-Null
  git -C $bw commit -m "beacon $stamp" 2>&1 | Out-Null
  git -C $bw push -f origin rope/beacon 2>&1 | Out-Null
  Write-Host "$stamp  beacon pushed | runner $(if($alive){'ALIVE'}else{'stopped'}) | relaunches $relaunches"
  Start-Sleep 300
}
