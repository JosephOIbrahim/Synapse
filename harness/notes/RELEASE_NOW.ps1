# RELEASE_NOW.ps1 - v5.44.0: CI0 cure + today's changes, one paste.
# Every git call exit-checked; banners are EARNED. Merge, VERSION, tag,
# push, release are YOUR acts - running this script is that act.
$ErrorActionPreference = 'Stop'
Set-Location C:\Users\User\Synapse

function G { param([Parameter(ValueFromRemainingArguments)]$a)
  & git @a
  if ($LASTEXITCODE -ne 0) { throw "git $($a -join ' ') failed (exit $LASTEXITCODE)" } }

# guards
if ((git branch --show-current) -ne 'master') { throw 'ABORT: not on master.' }
if (@(git diff --name-only --diff-filter=U).Count) { throw 'ABORT: unmerged files present.' }
$v = (Get-Content VERSION -Raw).Trim()
if ($v -ne '5.42.0') { throw "ABORT: VERSION reads '$v', expected 5.42.0 - stop and look." }

# 0 - commit tonight's vacation-parking paperwork first (named paths only)
$dirty = @(git diff --name-only)
$known = @('harness/legs.json','harness/NEXT_SESSION.md')
$unknown = $dirty | Where-Object { $known -notcontains $_ }
if ($unknown) { throw "ABORT: unexpected modified files [$($unknown -join ', ')] - stop and look." }
if ($dirty) {
  G add harness/legs.json harness/NEXT_SESSION.md harness/prompts/mem.md
  G commit -m "feat(harness): vacation parking - MEM leg (held), return handoff"
  Write-Host '  parking paperwork committed' -ForegroundColor Green
}

# 1 - Gate C: merge the CI cure. Known single conflict: harness/legs.json
#     (branch carries an old roster; master's is complete incl. the CI0 row).
$env:SYNAPSE_GATE_C = 1
& git merge --no-ff ci/ci0-honest-green -m "merge CI0: honest-green CI - real rot fixed, env-gated tests visible (Gate C)"
if ($LASTEXITCODE -ne 0) {
  if (-not (Test-Path .git\MERGE_HEAD)) {
    $env:SYNAPSE_GATE_C = $null
    throw 'ABORT: merge refused to start (dirty tree or other precondition) - nothing changed; read the git message above.'
  }
  $conf = @(git diff --name-only --diff-filter=U)
  if ($conf.Count -eq 1 -and $conf[0] -eq 'harness/legs.json') {
    G checkout --ours harness/legs.json
    G add harness/legs.json
    G commit --no-edit
    Write-Host '  CI0 merged (kept master roster)' -ForegroundColor Green
  } else {
    git merge --abort 2>$null; $env:SYNAPSE_GATE_C = $null
    throw "ABORT: unexpected conflict in [$($conf -join ', ')] - nothing merged."
  }
} else { Write-Host '  CI0 merged clean' -ForegroundColor Green }

# 2 - VERSION 5.42.0 -> 5.44.0 (file lagged Wednesday's tag), commit
Set-Content VERSION '5.44.0' -NoNewline
G add VERSION harness/notes/RELEASE_v5.44.0.md harness/notes/RELEASE_NOW.ps1
G commit -m "release: v5.44.0 - honest-green CI + wave-1 hardening; known Moneta open issue disclosed"

# 3 - tag + push, gate closed behind you
G tag v5.44.0
G push origin master --tags
$env:SYNAPSE_GATE_C = $null

# 4 - GitHub release from the notes file
gh release create v5.44.0 --title 'v5.44.0' --notes-file harness/notes/RELEASE_v5.44.0.md
if ($LASTEXITCODE -ne 0) { throw 'gh release create failed - tag is pushed; create the release at github.com in the UI with the notes file.' }

# 5 - banner is EARNED: verify remote tag + live release
$remoteTag = git ls-remote --tags origin v5.44.0
& gh release view v5.44.0 --json tagName > $null 2>&1
if ($remoteTag -and $LASTEXITCODE -eq 0) {
  Write-Host ''
  Write-Host 'VERIFIED: v5.44.0 tagged on origin and live on GitHub Releases.' -ForegroundColor Green
  Write-Host 'CI cure merged - the badge goes green when the run completes.' -ForegroundColor Gray
} else {
  Write-Host "INCOMPLETE: remoteTag=$([bool]$remoteTag) releaseView=$LASTEXITCODE - screenshot this." -ForegroundColor Red
}
