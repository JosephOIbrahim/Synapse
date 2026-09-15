# gatec_push_tag_v5620.ps1 - cut and push the v5.62.0 tag at the bump commit on Joe's word ("waiver + publish", 2026-09-03).
# Gate C override scoped to the single tag push and removed after. Never run unattended.
$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\User\SYNAPSE'
git tag -a v5.62.0 8bd4fee5 -m 'v5.62.0 - the inspector found the light'
$env:SYNAPSE_GATE_C = '1'
git push origin v5.62.0 2>&1 | Where-Object { $_ -notmatch 'CRLF' }
Remove-Item Env:SYNAPSE_GATE_C -ErrorAction SilentlyContinue
git fetch --tags origin 2>&1 | Out-Null
Write-Host ("local tag  -> " + (git rev-parse --short 'v5.62.0^{commit}'))
Write-Host ("remote tag -> " + ((git ls-remote --tags origin v5.62.0^{}) -replace '\s.*$', '').Substring(0, 8))
Write-Host ("gate env cleared: " + (-not (Test-Path Env:SYNAPSE_GATE_C)))
