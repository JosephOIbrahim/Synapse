# verify_bp2_close.ps1 - (1) receipt summary for the exited legs, (2) integration proof:
# scratch worktree bp2/integration = master + the four receipted branches, conflicts reported,
# (3) pin references. Zero words: touches no branch Joe rules on.
$ErrorActionPreference = 'Continue'
$repo = 'C:\Users\User\SYNAPSE'
Set-Location $repo
Write-Output "--- receipts ---"
python harness\notes\h22\verify_bp2_receipts.py
Write-Output "--- integration proof ---"
$wt = Join-Path $repo '.claude\worktrees\bp2-integration'
if (Test-Path $wt) { git worktree remove --force $wt 2>&1 | Out-Null }
git branch -D bp2/integration 2>&1 | Out-Null
git worktree add -q -b bp2/integration $wt master 2>&1 | Out-Null
foreach ($b in 'store','latency','meter','paneltruth') {
    $r = git -C $wt merge --no-ff -q -m "integration-proof: merge bp2/$b" "bp2/$b" 2>&1
    if ($LASTEXITCODE -eq 0) { Write-Output "merge bp2/$b -> clean" } else { Write-Output ("merge bp2/$b -> CONFLICT " + ($r -join ' ')); git -C $wt merge --abort 2>&1 | Out-Null }
}
$n = (git -C $wt log --oneline master..HEAD | Measure-Object).Count
Write-Output "integration commits ahead of master: $n"
git -C $wt diff --stat master..HEAD | Select-Object -Last 1
Write-Output "--- pin references (build strings) ---"
foreach ($f in 'SUPPORT_MATRIX.md','BETA_DONE.md','harness\verify\version_agreement.py','verify\version_agreement.py','cognitive\tools\data\h22_symbol_table.json','python\synapse\cognitive\tools\data\h22_symbol_table.json','.synapse\contracts\demo-round-trip.yaml') {
    if (Test-Path $f) { $v = Select-String -Path $f -Pattern '22\.0\.4\d\d' | ForEach-Object { [regex]::Matches($_.Line,'22\.0\.4\d\d') | ForEach-Object { $_.Value } } | Sort-Object -Unique; Write-Output ("{0}: {1}" -f $f, ($v -join ',')) }
}
Write-Output "--- installed builds / package ---"
Get-ChildItem 'C:\Program Files\Side Effects Software' -Directory | Select-Object -ExpandProperty Name
$pkg = 'C:\Users\User\OneDrive\Documents\houdini22.0\packages\synapse.json'
if (Test-Path $pkg) { Get-Content $pkg | Select-String -Pattern 'path|HFS|22\.0|SYNAPSE' | Select-Object -First 8 }
Write-Output "--- running houdini ---"
Get-CimInstance Win32_Process -Filter "Name='houdini.exe'" | ForEach-Object { [regex]::Match($_.CommandLine,'Houdini 22\.0\.\d+').Value }
