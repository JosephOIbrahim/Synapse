foreach ($l in 'help','know','guard') {
  $wt = 'C:\Users\User\SYNAPSE\.claude\worktrees\w4-' + $l
  Write-Output ('== w4-' + $l)
  Get-Content ($wt + '\harness\notes\receipts\W4-' + $l.ToUpper() + '.json') -TotalCount 4
  $files = git -C $wt status --porcelain | ForEach-Object { $_.Substring(3) }
  Write-Output ('files:' + $files.Count)
  foreach ($f in $files) { git -C $wt add -- $f }
  git -C $wt commit -q -m ("notes(w4-" + $l + "): secure leg artifacts - receipt written but no commit at close (receipt-sentinel race, systemic across wave 4); staged post-hoc by driver, content unmodified")
  Write-Output ('ahead:' + (git -C C:\Users\User\SYNAPSE rev-list --count ("master..wave4/" + $l)))
}
