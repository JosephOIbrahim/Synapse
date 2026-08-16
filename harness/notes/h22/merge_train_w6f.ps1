$ErrorActionPreference = 'Stop'
Set-Location C:\Users\User\SYNAPSE
git checkout master -q
if (Test-Path harness\notes\h22\w6f-landed.flag) { git ls-files --error-unmatch harness/notes/h22/w6f-landed.flag 2>$null; if ($LASTEXITCODE -ne 0) { Remove-Item harness\notes\h22\w6f-landed.flag } }
foreach ($b in 'wave6/jrny','wave6/flowrig','wave6/flowfix','wave6/fcrx') {
    git merge --no-ff $b -m ("merge($b): W6 user-flow leg - FCRX green_with_findings, Joe merge word") -q
    if ($LASTEXITCODE -ne 0) { Write-Host ("HALT: conflict on " + $b); exit 1 }
    Write-Host ("merged " + $b + " -> " + (git rev-parse --short HEAD))
}
powershell -NoProfile -ExecutionPolicy Bypass -File harness\notes\h22\gatec_push.ps1
