# prune_merged_remotes.ps1 - delete remote branches fully merged into master
# guard: mechanical --merged check; explicit keep-list for live/unmerged legs
Set-Location C:\Users\User\SYNAPSE
git fetch origin --prune | Out-Null
$keep = @('origin/master','origin/HEAD','origin/wave5/measures','origin/wave5/catalog','origin/wave5/parmgate')
$merged = git branch -r --merged origin/master |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and ($_ -notmatch '->') -and ($keep -notcontains $_) }
if (-not $merged) { Write-Host 'NOTHING TO PRUNE'; exit 0 }
Write-Host "PRUNING $($merged.Count) merged remote branches:"
$merged | ForEach-Object { Write-Host "  $_" }
$names = $merged | ForEach-Object { $_ -replace '^origin/','' }
git push origin --delete @names
Write-Host '--- REMAINING ---'
git branch -r
