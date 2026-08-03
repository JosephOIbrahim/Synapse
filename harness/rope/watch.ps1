# rope watch v2 -- live dashboard. Closing this window never stops the run.
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
while ($true) {
  Clear-Host
  $now = Get-Date -Format "HH:mm:ss"
  Write-Host "  ROPE / GATE A          $now" -ForegroundColor Cyan
  Write-Host "  ---------------------------------------------------------------" -ForegroundColor DarkGray

  $rpid = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
          Where-Object { $_.CommandLine -match 'runner\.py run' } | Select-Object -First 1 -ExpandProperty ProcessId
  if ($rpid) { Write-Host "  runner    ALIVE  pid $rpid" -ForegroundColor Green }
  else       { Write-Host "  runner    stopped" -ForegroundColor Yellow }

  $rc = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'rc\.ps1' }
  if ($rc) { Write-Host "  beacon    ALIVE  (rope/beacon on GitHub)" -ForegroundColor Green }
  else     { Write-Host "  beacon    off" -ForegroundColor DarkGray }

  Write-Host ""
  $gate = python harness\rope\runner.py gate 2>$null
  foreach ($g in $gate) {
    if ($g -match "GREEN") { Write-Host "  $g" -ForegroundColor Green }
    else { Write-Host "  $g" -ForegroundColor White }
  }

  Write-Host ""
  Write-Host "  IN FLIGHT" -ForegroundColor DarkCyan
  $flight = python harness\rope\runner.py status 2>$null | Select-String " in_progress "
  if ($flight) {
    foreach ($f in $flight) { Write-Host "  > $($f.Line.Trim())" -ForegroundColor Yellow }
    $lr = Get-Item harness\rope\last_run.log -ErrorAction SilentlyContinue
    if ($lr) { Write-Host "    working $([int]((Get-Date) - $lr.LastWriteTime).TotalSeconds)s since last agent write" -ForegroundColor DarkGray }
  } else { Write-Host "  (nothing running)" -ForegroundColor DarkGray }

  Write-Host ""
  Write-Host "  WAITING ON YOU" -ForegroundColor DarkCyan
  $mine = python harness\rope\runner.py status 2>$null |
          Select-String " blocked_human | needs_review | blocked_seat "
  if ($mine) { foreach ($m in $mine) { Write-Host "  * $($m.Line.Trim())" -ForegroundColor Magenta } }
  else { Write-Host "  (nothing)" -ForegroundColor DarkGray }

  Write-Host ""
  Write-Host "  LEDGER (last 6)" -ForegroundColor DarkCyan
  foreach ($r in (Get-Content harness\rope\results.tsv -Tail 6 -ErrorAction SilentlyContinue)) {
    $c = "Gray"
    if ($r -match "`tkeep`t")        { $c = "Green" }
    if ($r -match "quota-pause")     { $c = "Yellow" }
    if ($r -match "`tdiscard`t")     { $c = "Red" }
    $cols = $r -split "`t"
    if ($cols.Count -ge 6) { Write-Host ("  {0}  {1,-6} {2,-12} {3,5}s  {4}" -f $cols[0].Substring(11), $cols[1], $cols[3], $cols[5], $cols[7]) -ForegroundColor $c }
  }
  Write-Host ""
  Write-Host "  safe to close -- the run is a separate process" -ForegroundColor DarkGray
  Start-Sleep 5
}
