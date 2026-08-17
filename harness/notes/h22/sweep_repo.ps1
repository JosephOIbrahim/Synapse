# sweep_repo.ps1 - first-principles repo surveillance: every place work can hide.
Set-Location C:\Users\User\SYNAPSE
Write-Host ('=== sweep ' + (Get-Date -Format 'yyyy-MM-dd HH:mm') + ' ===')
Write-Host '--- 1 master vs origin ---'
git fetch origin -q
git status -sb | Select-Object -First 1
git log origin/master..master --oneline | Select-Object -First 5
Write-Host '--- 2 tracked modifications + untracked ---'
git status -s | Select-Object -First 15
Write-Host '--- 3 stashes ---'
git stash list | Select-Object -First 5
Write-Host '--- 4 branches ahead of their upstream or unpushed ---'
git for-each-ref refs/heads --format='%(refname:short) %(upstream:track)' | Select-String 'ahead|gone'
Write-Host '--- 5 worktrees + dirty state ---'
git worktree list
foreach ($wt in (git worktree list --porcelain | Select-String '^worktree ' )) {
    $path = $wt.ToString().Substring(9)
    if ($path -ne 'C:/Users/User/SYNAPSE') {
        $dirty = git -C $path status -s | Select-Object -First 3
        if ($dirty) { Write-Host ("DIRTY " + $path); $dirty | ForEach-Object { Write-Host ("   " + $_) } }
    }
}
Write-Host '--- 6 orchestrator board tail ---'
Get-Content harness\notes\h22\orchestrator-w5l.log -Tail 2
Write-Host '--- 7 verdict flags ---'
Get-ChildItem harness\notes\h22\*-landed.flag -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_.Name }
Write-Host '--- 8 detached process liveness ---'
$orchPid = Get-Content harness\notes\h22\orchestrator-w5l.pid -ErrorAction SilentlyContinue
foreach ($pair in @(@('orchestrator', $orchPid), @('steward', '62960'), @('measures-agent-window', '35232'))) {
    $alive = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $pair[1]) -ErrorAction SilentlyContinue
    if ($alive) { Write-Host ($pair[0] + ' ALIVE pid ' + $pair[1]) } else { Write-Host ($pair[0] + ' DEAD pid ' + $pair[1]) }
}
Write-Host '--- 9 steward overnight alerts ---'
Get-Content harness\notes\h22\steward.log -Tail 4 -ErrorAction SilentlyContinue
Write-Host '--- 10 CI on master + tag ---'
gh run list -L 2
Write-Host '=== sweep end ==='
