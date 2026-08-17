$ErrorActionPreference = 'Stop'
Set-Location C:\Users\User\SYNAPSE
git checkout master -q
foreach ($b in 'wave6/forge','wave6/quote','wave6/prov','wave6/beat','wave6/gate','wave6/hcrx') {
    git merge --no-ff $b -m ("merge($b): W6 hardening leg - HCRX green_with_findings, close-pass per R135, Joe word") -q
    if ($LASTEXITCODE -ne 0) { Write-Host ("HALT: conflict on " + $b); git status -s | Select-Object -First 8; exit 1 }
    Write-Host ("merged " + $b + " -> " + (git rev-parse --short HEAD))
}
powershell -NoProfile -ExecutionPolicy Bypass -File harness\notes\h22\gatec_push.ps1
