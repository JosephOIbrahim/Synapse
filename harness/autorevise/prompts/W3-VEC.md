# W3-VEC â€” vector recall: derived index over the store, ranked with scores

You are a SYNAPSE wave agent on branch `wave3/vec` in worktree `.claude/worktrees/w3-vec`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W3-VEC",
  "name": "vector recall: derived index over the store, ranked with scores",
  "band": "BUILD",
  "source": {
    "doc": "docs/SYNAPSE-memory-engineering-spec.md",
    "anchor": "S5 Phase 3 - Vector recall: index built OVER the USD store as derived data (rebuildable from source memories, never the source of truth); synapse_recall returns nearest neighbors by embedding with a confidence score; index embedding_dim read from the provider at init per the Phase 0 fix"
  },
  "targets": [
    "1) build the vector index over the USD store as derived data - deletable and rebuildable from source memories at any time",
    "2) synapse_recall returns ranked nearest neighbors with confidence scores, not a raw dump",
    "3) regression guard on W3-DIM: index construction here reads embedding_dim from the active provider - no reintroduced pin"
  ],
  "acceptance": [
    {
      "predicate": "doctor shows vector_recall ok",
      "evidence": "probe"
    },
    {
      "predicate": "recall for a seeded query returns ranked results with scores",
      "evidence": "test"
    },
    {
      "predicate": "derived-data proof: delete the index, rebuild from source memories, recall results reproduce",
      "evidence": "test"
    },
    {
      "predicate": "no hardcoded dim governs index construction on this leg's diff",
      "evidence": "check"
    }
  ],
  "deps": [
    "W3-STORE"
  ],
  "readonly": false,
  "touches": [
    "python/synapse/memory/moneta_store.py",
    "python/synapse/memory/embedding.py",
    "tests/"
  ],
  "crucible_criteria": [
    "SEAM GUARD: fix/memory-store-recovery is UNMERGED and owns the store - receipt states rebase-compatibility; drift is a BLOCK",
    "the index is never treated as source of truth anywhere in the diff - a lost index must cost nothing but a rebuild",
    "scores are real model outputs - a fabricated or constant score is a BLOCK (UNKNOWN discipline)"
  ],
  "spawn_classes": [
    "probe"
  ],
  "note": "Runs parallel to W3-KIND after W3-STORE lands."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave3 W3-VEC claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave3`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave3 W3-VEC finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave3 W3-VEC status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave3 W3-VEC`

## Receipt (completion contract)

Write `harness/notes/receipts/W3-VEC.json` **inside your worktree**:
`{{"leg": "W3-VEC", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
