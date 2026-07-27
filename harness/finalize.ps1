# FINALIZE — the closing sequence, one pass, gated at every step.
#
# Written in advance so the sequence is not improvised at 00:30. Every step
# verifies before the next begins, and ANY failure stops the run with the tree
# in a known state.
#
# It does NOT push master. Gate C requires SYNAPSE_GATE_C=1 deliberately, typed
# by a human for that one command. This script prints it and stops.
param([switch]$Force)

$ErrorActionPreference = 'Continue'
$repo = 'C:\Users\User\SYNAPSE'
Set-Location $repo

function Step($n, $m) { Write-Host ""; Write-Host "  [$n] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "      OK  $m" -ForegroundColor Green }
function Die($m)  { Write-Host ""; Write-Host "  STOPPED: $m" -ForegroundColor Red; Write-Host "  Tree is in a known state. Nothing was pushed." -ForegroundColor DarkGray; exit 1 }

Write-Host ""
Write-Host "  SYNAPSE FINALIZE" -ForegroundColor Cyan
Write-Host "  U1 -> renormalize -> suite -> master -> v5.35.0" -ForegroundColor DarkGray

# --- 1. U1 must have landed --------------------------------------------------
Step 1 "U1 receipt"
$u1 = "$repo\.claude\worktrees\u1-provenance-union\harness\notes\receipts\U1.json"
if (-not (Test-Path $u1)) {
    if (-not $Force) { Die "U1 has no receipt. It carries R52-R55, decided but unshipped. Wait, or -Force to proceed without it." }
    Write-Host "      -Force: proceeding WITHOUT U1. R52-R55 stay unshipped." -ForegroundColor Yellow
} else {
    $r = Get-Content $u1 -Raw | ConvertFrom-Json
    Ok "status=$($r.status)  ruling items=$(@($r.for_ruling).Count)"
    if ($r.status -notmatch '^green') { Die "U1 status is $($r.status), not green. Read it before merging." }
}

# --- 2. Nothing must be running ----------------------------------------------
Step 2 "quiet tree"
$busy = @(Get-Process claude -EA SilentlyContinue | Where-Object { $_.CPU -gt 60 })
if ($busy.Count -gt 3) { Die "$($busy.Count) claude processes with >60s CPU. Renormalizing under a live agent is R91 again." }
Ok "$($busy.Count) busy processes - safe"

# --- 3. Merge U1 -------------------------------------------------------------
if (Test-Path $u1) {
    Step 3 "merge U1"
    git merge repair/u1-provenance-union --no-ff -m "merge(U1): the five-field moneta_provenance union

LEDGER and H6 both rewrote this function from the same base because the CTO
dispatched a composition as two independent legs (R91). Neither had all five
fields. Authored, not merge-resolved - no strategy produces a five-field
function. Ships R52-R55, decided and previously stranded." 2>&1 | Select-Object -Last 3
    if ($LASTEXITCODE -ne 0) { Die "U1 merge conflicted. Resolve by hand - do not fix forward through product code you have not read." }
    Ok "merged"
} else { Step 3 "merge U1 - SKIPPED" }

# --- 4. Renormalize on a quiet tree ------------------------------------------
Step 4 "renormalize (R24 regenerates - agents write CRLF)"
$real = git diff --ignore-cr-at-eol --numstat 2>$null
if ($real) { Die "working tree has REAL uncommitted changes. Commit or stash first." }
git add --renormalize . 2>&1 | Out-Null
$staged = @(git diff --cached --numstat).Count
if ($staged -gt 0) {
    git commit -q -m "chore(eol): renormalize to .gitattributes

R24's debt regenerates - agents write CRLF and git captures it back against an
LF-normalized index. Cleared on a quiet tree, nothing running."
    Ok "$staged files renormalized"
} else { Ok "already normalized" }

# --- 5. Suite must be green --------------------------------------------------
Step 5 "gate suite"
$bt = "$repo\.pytest_final_$(Get-Random)"
$out = python -m pytest -q --no-header -p no:cacheprovider --basetemp=$bt 2>&1 | Out-String
Remove-Item $bt -Recurse -Force -EA SilentlyContinue
if ($out -match '(\d+) passed') { $passed = [int]$Matches[1] } else { $passed = 0 }
if ($out -match '(\d+) failed') { Die "$($Matches[1]) tests FAILED after merge. Nothing proceeds." }
if ($passed -lt 4940) { Die "suite is $passed, below the 4940 floor. Commandment 7." }
Ok "$passed passed, 0 failed"

# --- 6. Merge to master ------------------------------------------------------
Step 6 "master"
$branch = git rev-parse --abbrev-ref HEAD
git checkout master 2>&1 | Select-Object -Last 1
git merge $branch --no-ff -m "merge($branch): v5.35.0 - the instruments were the defect" 2>&1 | Select-Object -Last 3
if ($LASTEXITCODE -ne 0) { git merge --abort; git checkout $branch; Die "master merge conflicted and was aborted. Back on $branch." }
Ok "merged to master"

# --- 7. Version + tag --------------------------------------------------------
Step 7 "v5.35.0"
Set-Content "$repo\VERSION" "5.35.0" -NoNewline -Encoding utf8

# R107: bumping VERSION alone is NOT bumping the version. __version__ in
# python/synapse/__init__.py is what the RUNNING CODE reports, and what
# synapse_doctor reads. On 2026-07-27 VERSION said 5.35.0, __version__ said
# 5.33.0, the git tag said v5.35.0 and the install stamp said 5.23.0 - four
# numbers, because this step only ever touched one of them.
# --fix also strips the BOM that Set-Content -Encoding utf8 writes above.
python "$repo\harness\verify\version_agreement.py" --fix
if ($LASTEXITCODE -ne 0) { Die "VERSION and __version__ still disagree after --fix." }
Ok "VERSION and __version__ agree"

git add VERSION python/synapse/__init__.py
git commit -q -m "release(v5.35.0): the instruments were the defect"
git tag -a v5.35.0 -m "v5.35.0 - the instruments were the defect"
Ok "tagged v5.35.0 at $(git rev-parse --short HEAD)"

# --- Gate C stops here -------------------------------------------------------
Write-Host ""
Write-Host "  READY. Nothing pushed. Gate C is yours:" -ForegroundColor Yellow
Write-Host ""
Write-Host '      $env:SYNAPSE_GATE_C=1; git push origin master; git push origin v5.35.0' -ForegroundColor White
Write-Host ""
Write-Host "      then:  gh release create v5.35.0 --notes-file docs/RELEASE_NOTES_v5.35.0.md" -ForegroundColor DarkGray
Write-Host ""
