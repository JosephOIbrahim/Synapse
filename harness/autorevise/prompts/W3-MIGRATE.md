# W3-MIGRATE â€” JSONL to Moneta: copy-and-verify, ids preserved, flip with fallback armed

You are a SYNAPSE wave agent on branch `wave3/migrate` in worktree `.claude/worktrees/w3-migrate`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W3-MIGRATE",
  "name": "JSONL to Moneta: copy-and-verify, ids preserved, flip with fallback armed",
  "band": "BUILD",
  "source": {
    "doc": "docs/SYNAPSE-memory-engineering-spec.md",
    "anchor": "S7 Phase 5 - Migration and cut-over: one-shot exporter JSONL to typed USD prims preserving ids so references survive; verify every JSONL memory has a corresponding USD prim (count + spot-check field fidelity, no prim dropped); flip active backend to Moneta keeping JSONL as automatic write-through"
  },
  "targets": [
    "1) HARD BACKUP GATE first: every JSONL store file is backed up before any migration step runs - the W1 policy verbatim",
    "2) one-shot exporter: JSONL memories become typed USD prims, ids preserved so references survive",
    "3) verify: JSONL count equals prim count; spot-check at least 5 memories field-by-field; no prim dropped",
    "4) flip the active backend to Moneta with JSONL write-through armed as the automatic safety net",
    "5) collision policy: keep-both-never-delete - a key collision produces two receipted entries, never an overwrite"
  ],
  "acceptance": [
    {
      "predicate": "backup of every JSONL source exists and originals are byte-untouched after the full run",
      "evidence": "check"
    },
    {
      "predicate": "count of JSONL memories equals count of USD prims after migration",
      "evidence": "check"
    },
    {
      "predicate": "5 spot-checked memories match field-for-field across stores",
      "evidence": "test"
    },
    {
      "predicate": "post-flip, a new write lands in Moneta AND in JSONL (fallback armed)",
      "evidence": "probe"
    }
  ],
  "deps": [
    "W3-KIND",
    "W3-VEC"
  ],
  "readonly": false,
  "touches": [
    "python/synapse/memory/",
    "tests/"
  ],
  "crucible_criteria": [
    "SEAM GUARD: fix/memory-store-recovery is UNMERGED and owns the store AND the nine-store unification - this leg's receipt must reconcile with that branch's store map or BLOCK",
    "THIS IS USER MEMORY DATA: data safety outranks speed, elegance, and completion; migration is copy-and-verify, never cut-over-and-pray; any deletion of a source file is a BLOCK",
    "crucible independently recomputes the count parity from disk, not from the receipt's claim",
    "cut-over reversibility is stated in the receipt: the exact steps to fall back to JSONL-primary"
  ],
  "spawn_classes": [
    "probe"
  ],
  "note": "The actual go-live. Blueprint P6: never destroy a memory."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave3 W3-MIGRATE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave3`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave3 W3-MIGRATE finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave3 W3-MIGRATE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave3 W3-MIGRATE`

## Receipt (completion contract)

Write `harness/notes/receipts/W3-MIGRATE.json` **inside your worktree**:
`{{"leg": "W3-MIGRATE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
