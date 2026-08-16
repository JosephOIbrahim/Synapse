$ErrorActionPreference = 'Stop'
Set-Location C:\Users\User\SYNAPSE
git status -sb | Select-Object -First 1
git log --oneline -1
git merge --no-ff wave5/life -m "merge(w5l): wave5/life - R.2 beat owner + session survival, LCRUX pass 29/29 - merged on Joe's enumerated word 2026-08-16"
if ($LASTEXITCODE -ne 0) { Write-Host 'TRAIN STOPPED at LIFE'; git status; exit 1 }
git merge --no-ff wave5/panel -m "merge(w5l): wave5/panel - chat leading + token tab (hython-proven), font-floor math, LCRUX pass - merged on Joe's enumerated word 2026-08-16"
if ($LASTEXITCODE -ne 0) { Write-Host 'TRAIN STOPPED at PANEL'; git status; exit 1 }
git merge --no-ff wave5/rope -m "merge(w5l): wave5/rope - CURIOUS/EXPERT/ML switcher rides real compositor, 101/101, LCRUX pass - merged on Joe's enumerated word 2026-08-16"
if ($LASTEXITCODE -ne 0) { Write-Host 'TRAIN STOPPED at ROPE'; git status; exit 1 }
Write-Host '=== three clean merges done; SHELF next (expected union conflict) ==='
git merge --no-ff wave5/shelf -m "merge(w5l): wave5/shelf - icons+tooltips, PySide6-first, shelf_current GREEN, LCRUX pass - union on test_r_track per LCRUX F1 - Joe's enumerated word 2026-08-16"
Write-Host ('shelf merge exit: ' + $LASTEXITCODE)
git status -s
