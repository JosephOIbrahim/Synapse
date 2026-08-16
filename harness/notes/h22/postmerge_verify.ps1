Set-Location C:\Users\User\SYNAPSE
$out = 'C:\Users\User\SYNAPSE\harness\notes\h22\postmerge_verify.log'
"START $(Get-Date -Format 'HH:mm:ss')" | Out-File $out -Encoding ascii
python harness/verify/checks.py --task R.2 --worktree . 2>&1 | Select-Object -Last 6 | Out-File $out -Append -Encoding ascii
python harness/verify/checks.py --task R.7 --worktree . 2>&1 | Select-Object -Last 4 | Out-File $out -Append -Encoding ascii
git status -sb | Select-Object -First 1 | Out-File $out -Append -Encoding ascii
"DONE $(Get-Date -Format 'HH:mm:ss')" | Out-File $out -Append -Encoding ascii
