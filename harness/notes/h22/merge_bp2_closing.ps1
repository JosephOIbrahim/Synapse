# merge_bp2_closing.ps1 - Joe's word "merge closing" (2026-09-01 18:4x). BP2-CRUXB verdicts read at the
# referee seat: PANELDESIGN / HEALTHWIRE / METERLIVE SOUND-WITH-NITS (chain intact); NITS BROKEN at T1 -
# does not ride. Integration: 4 branches clean into bp2/integration, full suite 6928 passed / 0 failed.
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\User\SYNAPSE'
$legs = @(
  @{ b='bp2/healthwire';  m='merge(bp2): BP2-HEALTHWIRE - backend_health wired into the server health row (embedder, dim, ratified verdict), write_plane words untouched; CRUXB SOUND-WITH-NITS (3/4 + GUI UNKNOWN, 4/4 mutations bit)' },
  @{ b='bp2/meterlive';   m='merge(bp2): BP2-METERLIVE - live end-to-end settle proof on a scratch orchestrator (dispatch -> done -> settle -> ceiling halt); first orchestrator-measured leg 75356/278; CRUXB SOUND-WITH-NITS (3/3, 0 UNKNOWN)' },
  @{ b='bp2/paneldesign'; m='merge(bp2): BP2-PANELDESIGN - sec.7 panel rhythm: spacing tokens + QSS on the density root property, five camera regions, zero new colours, Expert pin green; CRUXB SOUND-WITH-NITS (5/6 + GUI UNKNOWN; 2 disclosed teeth gaps)' },
  @{ b='bp2/cruxb';       m='merge(bp2): BP2-CRUXB - verdicts, mutations, receipt, landed flag (read-only artifacts); NITS BROKEN recorded, not merged' }
)
if ((git -C $repo branch --show-current) -ne 'master') { throw 'not on master' }
foreach ($l in $legs) {
  git -C $repo merge --no-ff --no-edit -m $l.m $l.b 2>&1 | Select-String -NotMatch 'CRLF' | Out-Null
  if ($LASTEXITCODE -ne 0) { throw ("merge stopped at " + $l.b) }
  Write-Output ("merged " + $l.b + " -> " + (git -C $repo rev-parse --short=8 HEAD))
}
Write-Output ("ahead of origin: " + (git -C $repo rev-list --count origin/master..master))
