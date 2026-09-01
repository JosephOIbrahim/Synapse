# merge_bp2.ps1 - Joe's merge word for wave BP2 pairs 1+2 (2026-09-01 ~15:30).
# Preconditions met before this runs: BP2-CRUX verdicts read at the referee seat (4x SOUND-WITH-NITS,
# chain_broken_at none); integration proof clean (5 branches, 0 conflicts); full suite green on the
# integrated tree (pytest_bp2_integration2.log). --no-ff, one merge commit per leg, no amends.
# Order per docs/BATTLEPLAN.md sec.2 call 3: memory -> harness -> paint -> crucible artifacts.
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\User\SYNAPSE'
$legs = @(
  @{ b='bp2/store';      m='merge(bp2): BP2-STORE - backend_health M-5 honest report + FU-1 divergence pins; CRUX SOUND-WITH-NITS (6/6, 0 UNKNOWN); product dd66b089, receipt b1b9bc74' },
  @{ b='bp2/latency';    m='merge(bp2): BP2-LATENCY - memory latency receipt, repeat-5 p50/p95, under budget on the provisioned-headless proxy (.400 in-process); CRUX SOUND-WITH-NITS (4/5 + GUI UNKNOWN); product 0ef53146, receipt ce958092, hygiene a0692a98 (.jsonl)' },
  @{ b='bp2/meter';      m='merge(bp2): BP2-METER - token meter: post-close settle from transcript, per-leg tiers incl referee, bus drift check, unit/status honesty; CRUX SOUND-WITH-NITS (7/7); product 1c2b78fd, receipt 7b8c0855, hygiene 84453de9+6259c5a0 (by-path test imports)' },
  @{ b='bp2/paneltruth'; m='merge(bp2): BP2-PANELTRUTH - profile diff receipt, TOKEN refresh on completion, docked-open float fix; CRUX SOUND-WITH-NITS (5/7 + 2 GUI UNKNOWN); product d9b0c06d, receipt 45cf2fa5; territory breach remediated in-session' },
  @{ b='bp2/crux';       m='merge(bp2): BP2-CRUX - verdicts, mutations, latency reprobe, receipt, landed flag (read-only artifacts)' }
)
if ((git -C $repo branch --show-current) -ne 'master') { throw 'not on master' }
foreach ($l in $legs) {
  git -C $repo merge --no-ff --no-edit -m $l.m $l.b
  if ($LASTEXITCODE -ne 0) { throw ("merge stopped at " + $l.b) }
  Write-Output ("merged " + $l.b + " -> " + (git -C $repo rev-parse --short=8 HEAD))
}
git -C $repo log --oneline -6
Write-Output ("master is now " + (git -C $repo rev-list --count origin/master..master) + " commits ahead of origin/master")
