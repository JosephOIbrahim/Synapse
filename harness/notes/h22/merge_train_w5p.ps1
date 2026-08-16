# merge_train_w5p.ps1 - parity trio merge train. RUNS ONLY ON JOE'S EXPLICIT WORD.
# Scope enumerated: wave5/parity, wave5/seat, wave5/pcrux -> master, --no-ff each, then Gate C push.
$ErrorActionPreference = 'Stop'
Set-Location C:\Users\User\SYNAPSE
git checkout master -q
foreach ($b in 'wave5/parity','wave5/seat','wave5/pcrux') {
    git merge --no-ff $b -m ("merge($b): parity wave leg - PCRUX green_with_findings, Joe merge word") -q
    if ($LASTEXITCODE -ne 0) { Write-Host ("HALT: merge conflict on " + $b); exit 1 }
    Write-Host ("merged " + $b + " -> " + (git rev-parse --short HEAD))
}
git log --oneline -4
powershell -NoProfile -ExecutionPolicy Bypass -File harness\notes\h22\gatec_push.ps1
