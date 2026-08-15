$R = 'C:\Users\User\SYNAPSE'
$w3 = git -C $R log --oneline --merges -40 | Select-String -Pattern 'wave3|wave2'
Write-Output ('w3-style: ' + ($w3 | Select-Object -First 3 | ForEach-Object { $_.Line }))
if (-not $w3) { Write-Output 'NO LOCAL WAVE-MERGE PRECEDENT - stopping before merge; PR flow likely'; exit 0 }
foreach ($b in 'wave4/help','wave4/know','wave4/guard','wave4/ruling') {
  git -C $R merge --no-ff --no-edit -m ("merge(w4): " + $b + " - CRUX pass, receipts on branch, Gate B/push held for Joe") $b
  if ($LASTEXITCODE -ne 0) { git -C $R merge --abort; Write-Output ('CONFLICT STOP at ' + $b + ' - train halted, master unchanged past last clean merge'); exit 1 }
  Write-Output ('merged ' + $b)
}
Write-Output ('master now: ' + (git -C $R log --oneline -1))
$tests = git -C $R diff --name-only 96b71d21..HEAD -- tests/
Write-Output ('post-merge suites: ' + $tests)
Set-Location $R; python -m pytest @($tests) -q 2>&1 | Select-Object -Last 4
