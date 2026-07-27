# Positive control for the idle-watch fix.
#
# THE BUG: the loop `break`ed on board-complete. H9 was added to the manifest at
# 20:00 and sat undispatched until 22:51 - nearly three hours - because the
# orchestrator had exited at 19:58 and was sitting at a prompt, alive but not
# polling.
#
# THE FIX is untested until an orchestrator that has ALREADY reported
# board-complete is seen to dispatch a leg added afterwards. A fix that has never
# been observed working is the decoration this repository keeps finding.
#
# Self-contained: throwaway repo, throwaway manifest, -Quiet so no toasts fire,
# -DryRun so nothing is actually launched. Asserts on the log.
$ErrorActionPreference = 'Continue'
$orch = 'C:\Users\User\SYNAPSE\harness\orchestrate.ps1'
$tmp  = Join-Path $env:TEMP "orchctl_$(Get-Random)"
New-Item -ItemType Directory -Force -Path "$tmp\harness\notes\receipts" | Out-Null

# CTRL1 already has a receipt, so the board completes on the first poll.
'{"status":"green","for_ruling":[]}' | Set-Content "$tmp\harness\notes\receipts\CTRL1.json"

$m = @{
    repo = $tmp; settings = 'none'; effort = 'high'; base = 'none'
    legs = @( @{ id='CTRL1'; name='already done'; state='ready'; receipt='CTRL1.json'; deps=@() } )
}
$mp = "$tmp\harness\legs.json"
$m | ConvertTo-Json -Depth 10 | Set-Content $mp -Encoding utf8

Write-Host "control repo: $tmp" -ForegroundColor DarkGray
Write-Host "starting orchestrator (quiet, dry-run, 3s polls)..." -ForegroundColor Cyan

$job = Start-Job -ScriptBlock {
    param($o, $r, $mp)
    & $o -Repo $r -ManifestPath $mp -PollSeconds 3 -IdlePollSeconds 3 `
         -DigestMinutes 999 -MaxHours 1 -Quiet -DryRun
} -ArgumentList $orch, $tmp, $mp

Start-Sleep -Seconds 12
$log1 = Get-ChildItem "$tmp\harness\notes\orchestrator_*.log" -EA SilentlyContinue | Select-Object -First 1
$t1 = if ($log1) { Get-Content $log1.FullName -Raw } else { "" }

Write-Host ""
Write-Host "STEP 1 - did it enter IDLE WATCH instead of exiting?" -ForegroundColor Yellow
if ($t1 -match 'idle watch') { Write-Host "  PASS - idle watch entered" -ForegroundColor Green }
else { Write-Host "  FAIL - no idle watch in log" -ForegroundColor Red }
if ($job.State -eq 'Running') { Write-Host "  PASS - still running after board complete" -ForegroundColor Green }
else { Write-Host "  FAIL - job state $($job.State) (old behaviour: exited)" -ForegroundColor Red }

Write-Host ""
Write-Host "STEP 2 - add CTRL2 AFTER board-complete. Does it dispatch?" -ForegroundColor Yellow
$m.legs += @{ id='CTRL2'; name='added after complete'; state='ready'; receipt='CTRL2.json'
              branch='ctl/two'; worktree='wt2'; prompt='harness/legs.json'; deps=@() }
$m | ConvertTo-Json -Depth 10 | Set-Content $mp -Encoding utf8
Start-Sleep -Seconds 14

$t2 = if ($log1) { Get-Content $log1.FullName -Raw } else { "" }
if ($t2 -match 'DISPATCH CTRL2') { Write-Host "  PASS - CTRL2 dispatched from idle" -ForegroundColor Green }
else { Write-Host "  FAIL - CTRL2 never dispatched" -ForegroundColor Red }
if ($t2 -match 'RESUMED from idle') { Write-Host "  PASS - resume announced" -ForegroundColor Green }
else { Write-Host "  (no resume line)" -ForegroundColor DarkGray }

Stop-Job $job -EA SilentlyContinue; Remove-Job $job -Force -EA SilentlyContinue
Write-Host ""
Write-Host "--- log tail ---" -ForegroundColor DarkGray
if ($log1) { Get-Content $log1.FullName -Tail 12 }
Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
