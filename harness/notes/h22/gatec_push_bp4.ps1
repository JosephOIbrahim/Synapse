# gatec_push_bp4.ps1 - ONE push of master on Joe's word (2026-09-03, "push" after "merge tidy"). Gate C's pre-push hook is
# the boundary; the override lives for this single command and is removed immediately after. Never run unattended.
$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\User\SYNAPSE'
$env:SYNAPSE_GATE_C = '1'
git push origin master 2>&1 | Where-Object { $_ -notmatch 'CRLF' }
Remove-Item Env:SYNAPSE_GATE_C -ErrorAction SilentlyContinue
git fetch origin 2>&1 | Out-Null
Write-Host ("master  " + (git rev-parse --short master))
Write-Host ("origin  " + (git rev-parse --short origin/master))
Write-Host ("ahead   " + (git rev-list --count origin/master..master))
Write-Host ("gate env cleared: " + (-not (Test-Path Env:SYNAPSE_GATE_C)))
