# bp4_merge_train.ps1 - runs ONLY on Joe's enumerated merge word ("merge N-M"), after the BP4-CRUX verdicts
# were READ. One --no-ff merge per leg in dependency order; a BROKEN leg is simply left out of -Legs.
# Nothing pushes (Gate C; push is a separate word). Nothing here runs unattended.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File harness\notes\h22\bp4_merge_train.ps1 `
#          -Legs intake,rulings,b7fix,spatial,panelfont,usdknow,crux,tidy
param([string[]]$Legs = @('intake','b7fix','spatial','panelfont','usdknow','crux'))  # rulings BROKEN (CRUX 8a1c91e9) - carried to the fresh rulings session; tidy merges after its re-arm
$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\User\SYNAPSE'
$staged = git status --porcelain | Where-Object { $_ -match '^(M|A|D|R)' }
if ($staged) { throw "staged changes on master - refusing to merge over them:`n$($staged -join "`n")" }

foreach ($leg in $Legs) {
  $branch = "bp4/$leg"
  Write-Host "=== merge $branch"
  git merge --no-ff --no-edit -m "merge: $branch (BP4, Joe's word; CRUX verdict read)" $branch 2>&1 | Where-Object { $_ -notmatch 'CRLF' }
  if ($LASTEXITCODE -ne 0) {
    if ($leg -ne 'intake') { throw "merge of $branch did not apply cleanly - train stopped at $branch; resolve by hand" }
    # Known add/add conflicts against the R135 harvest commits (2574de6b, 9a90e9af): the LEG's versions win.
    git checkout --theirs -- docs/intake/src/MANIFEST.md harness/notes/receipts/BP4-INTAKE.json
    git show 9a90e9af:harness/notes/receipts/BP4-INTAKE.json | Set-Content -Encoding utf8 harness/notes/receipts/BP4-INTAKE.harvest-addendum.json
    Add-Content -Encoding utf8 docs/intake/src/MANIFEST.md "`n**Harvest addendum (2026-09-03, CTO seat; corrected per BP4-CRUX verdict I-1):** an R135 in-place harvest of this manifest was committed on master at 2574de6b before the leg branch merged. The leg's version above is canonical (branch product 03a4e43d, receipt 0d738db9, verdict SOUND-WITH-NITS). Two corrections to the harvest record: (1) its receipt's sentence 'no worktree, no leg branch' was FALSE - bp4/intake existed from 18:05; (2) its byte-count claim 7168/6451 came from an uncommitted main-tree draft observed by the CTO seat at ~18:30 and has no repo anchor. The harvest receipt is kept as harness/notes/receipts/BP4-INTAKE.harvest-addendum.json for the record only. The two .docx sources are still missing; the leg's bus value 'dossier_in_repo: true' overclaims - 'partial' is the truth."
    git add docs/intake/src/MANIFEST.md harness/notes/receipts/BP4-INTAKE.json harness/notes/receipts/BP4-INTAKE.harvest-addendum.json
    git -c core.safecrlf=false commit --no-edit 2>&1 | Where-Object { $_ -notmatch 'CRLF' }
    if ($LASTEXITCODE -ne 0) { throw "intake merge commit failed - resolve by hand" }
  }
  git log -1 --format='%h %s' | ForEach-Object { $_.Substring(0, [Math]::Min(110, $_.Length)) }
}
Write-Host "=== train done: $($Legs.Count) merges on master, NOT pushed. Next: ratchet (pytest tests -q, detached), then Joe's push word."
