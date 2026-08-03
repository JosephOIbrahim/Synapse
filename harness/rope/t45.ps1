# T+45 milestone snapshot -- writes a marked update to the beacon branch.
# One-shot: sleeps 45 min, publishes, exits. Close anytime to cancel.
$repo = "C:\Users\User\SYNAPSE"
$bw   = "C:\Users\User\rope-beacon-wt"
Set-Location $repo
$due = (Get-Date).AddMinutes(45)
Write-Host "T+45 update scheduled for $($due.ToString('HH:mm'))" -ForegroundColor Cyan
Start-Sleep -Seconds 2700
Set-Location $repo
$gate    = (python harness\rope\runner.py gate 2>$null) -join "`n"
$board   = (python harness\rope\runner.py status 2>$null) -join "`n"
$ledger  = (Get-Content harness\rope\results.tsv -Tail 12 -ErrorAction SilentlyContinue) -join "`n"
$commits = (git log --oneline rope/gate-a --not master | Select-Object -First 25) -join "`n"
$mine    = (python harness\rope\runner.py status 2>$null |
            Select-String " blocked_human | needs_review | blocked_seat ") -join "`n"
$alive   = [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match 'runner\.py run' })
if (-not (Test-Path $bw)) { git worktree add -B rope/beacon $bw 2>&1 | Out-Null }
$md = @"
# T+45 UPDATE -- $(Get-Date -Format 'yyyy-MM-dd HH:mm')
runner: $(if($alive){"ALIVE"}else{"stopped -- pass complete"})

## Gate
``````
$gate
``````

## WAITING ON YOU
``````
$mine
``````
- L3-2: record first-prompt video, embed in README
    python harness\rope\runner.py human L3-2 --done "video embedded"
- L3-5: Apprentice session + support matrix
    python harness\rope\runner.py human L3-5 --done "Apprentice row filled"
- needs_review items: python harness\rope\runner.py verify <ID> --passed

## Ledger (last 12)
``````
$ledger
``````

## Board
``````
$board
``````

## Commits on rope/gate-a
``````
$commits
``````
"@
Set-Content -Path (Join-Path $bw "STATUS.md") -Value $md -Encoding UTF8
git -C $bw add STATUS.md 2>&1 | Out-Null
git -C $bw commit -m "T+45 UPDATE -- rope gate A status for Joe" 2>&1 | Out-Null
git -C $bw push -f origin rope/beacon 2>&1 | Out-Null
Write-Host "T+45 update published to rope/beacon" -ForegroundColor Green
