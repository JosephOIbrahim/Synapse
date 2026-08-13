# W3-DIM â€” embedding dim contract: index reads the provider, loud on mismatch

You are a SYNAPSE wave agent on branch `wave3/dim` in worktree `.claude/worktrees/w3-dim`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W3-DIM",
  "name": "embedding dim contract: index reads the provider, loud on mismatch",
  "band": "BUILD",
  "source": {
    "doc": "docs/SYNAPSE-memory-engineering-spec.md",
    "anchor": "S0 THE ONE ROOT CAUSE + S2 Phase 0: index expects 384, provider emits 256; ValueError at Moneta/src/moneta/vector_index.py:112, snapshot-restored dim at :189; two construction paths in moneta_store.py (:262 passes embedder.dim, :289 passes cfg.embedding_dim); embedding.py fallback embedder dim=256 (:77) vs model embedder dim=384 (:158); init aborts and the store silently falls back to jsonl while claiming moneta (panel/health_strip.py:23 documents the incident class); write_plane degraded"
  },
  "targets": [
    "1) one dim authority: the vector index resolves embedding_dim from the ACTIVE embedder at init; cfg.embedding_dim is either removed or validated equal to embedder.dim - reconcile the :262 vs :289 construction paths so a provider change can never silently break init again",
    "2) stale-snapshot path: a persisted index whose snapshot dim mismatches the live provider is DERIVED DATA - rebuild it from source memories at init, never abort into fallback",
    "3) fallback honesty: if Moneta init still fails for any reason, the served backend reports jsonl - the store never claims moneta while serving jsonl; backend_fallback carries requested/served/reason",
    "4) no papering: the failure stays loud in the log; no silent catch-and-continue on the ValueError class"
  ],
  "acceptance": [
    {
      "predicate": "synapse_doctor on hython shows moneta_substrate ok AND write_plane ok; no 'embedding dim mismatch' anywhere in the init log",
      "evidence": "probe"
    },
    {
      "predicate": "constructing the store with a 256-dim embedder over a persisted 384-dim index snapshot rebuilds the index and init succeeds (and the mirror case 384-over-256)",
      "evidence": "test"
    },
    {
      "predicate": "negative control: a forced init failure reports served:jsonl requested:moneta in backend_fallback and doctor never shows in_use moneta",
      "evidence": "test"
    },
    {
      "predicate": "dim is resolved in exactly one place; grep shows no remaining hardcoded 384/256 pin governing index construction",
      "evidence": "check"
    }
  ],
  "deps": [],
  "readonly": false,
  "touches": [
    "python/synapse/memory/moneta_store.py",
    "python/synapse/memory/moneta_runtime.py",
    "python/synapse/memory/embedding.py",
    "C:/Users/User/Moneta/src/moneta/vector_index.py (VENDOR BOUNDARY - findings + held spawn only, see crucible)",
    "tests/"
  ],
  "crucible_criteria": [
    "SEAM GUARD: fix/memory-store-recovery is UNMERGED and owns python/synapse/memory/ - the receipt must state rebase-compatibility with that branch; store-semantics drift beyond the anchored dim contract is a BLOCK",
    "MONETA BOUNDARY: C:/Users/User/Moneta is a separate repo with no harness - any edit there lands as a receipt finding plus a held moneta-side spawn, never a silent in-place commit",
    "the silent-fallback class is re-attacked adversarially after the fix: attempt a mismatched init and verify the doctor says jsonl, loudly - not assumed closed",
    "house rule: unobtainable renders UNKNOWN, never zero and never an estimate - no fabricated ok on any doctor surface this leg touches"
  ],
  "spawn_classes": [
    "probe",
    "moneta-side"
  ],
  "note": "Crux leg of the wave - every other W3 leg gates on this one bug. Base ruling pending Joe's word at arming: master + seam guard vs base fix/memory-store-recovery."
}
```

## Constitution (non-negotiable)

- **NEVER**: `git push`, `git merge`, tag, edit `harness/state/drop.json`, flip
  any `ratified` or any leg `state` in a manifest. Those are human words, per act.
- **Unobtainable renders UNKNOWN** â€” never zero, never an estimate, never a pass.
  A `gui_required` acceptance you cannot measure headless is recorded UNKNOWN.
- **Receipts over claims** â€” every finding carries a file:line, probe path, or
  receipt anchor. No anchor, no claim.
- Named-file commits only on your branch. Never `git add -A`.
- Scope is the mission. Prerequisite work is real work â€” do it. Unrelated value â€”
  post a `spawn` proposal, don't chase it.

## The bus (how the team talks)

ONE bus command. Always this exact absolute path â€” NEVER a relative call. A
relative `python harness/autorevise/bus.py` from your worktree writes a
FRAGMENTED bus in the worktree that nobody reads: your claims become invisible
and two agents will edit one file.

1. **Before touching any file in `touches`** â€” post a claim:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave3 W3-DIM claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave3`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave3 W3-DIM finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave3 W3-DIM status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave3 W3-DIM`

## Receipt (completion contract)

Write `harness/notes/receipts/W3-DIM.json` **inside your worktree**:
`{{"leg": "W3-DIM", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
