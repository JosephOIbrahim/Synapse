# W3-STORE â€” materialize cortex_root.usda: typed root, write/query, dual-write armed

You are a SYNAPSE wave agent on branch `wave3/store` in worktree `.claude/worktrees/w3-store`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W3-STORE",
  "name": "materialize cortex_root.usda: typed root, write/query, dual-write armed",
  "band": "BUILD",
  "source": {
    "doc": "docs/SYNAPSE-memory-engineering-spec.md",
    "anchor": "S3 Phase 1 - Materialize the Moneta store: real cortex_root.usda at the resolved usd_root (doctor showed AppData/Local/Temp/houdini_temp/untitled/.synapse/.moneta/cortex_root.usda), MonetaMemory root prim with version attribute, write/query as typed prims keyed (kind,id), dual-write to JSONL for the whole phase"
  },
  "targets": [
    "1) on init, after the dim check passes, create the stage at the resolved usd_root with a MonetaMemory root prim carrying a version attribute",
    "2) write(kind,id,payload) becomes a typed USD prim under the root keyed by (kind,id); query walks the typed prims",
    "3) DUAL-WRITE: every write also lands in the JSONL store - the safety net never goes away this wave",
    "4) memory_key_fingerprint writes its sidecar on first use so the doctor check moves no_sidecar -> ok",
    "5) usd_root durability: the resolved root currently lives under a Temp dir - record the lifecycle risk (P1 durable) in the receipt with the observed path"
  ],
  "acceptance": [
    {
      "predicate": "doctor shows moneta_substrate in_use=True and memory_key_fingerprint no longer reports no_sidecar",
      "evidence": "probe"
    },
    {
      "predicate": "write a memory, the .usda exists non-empty, query returns it (round-trip)",
      "evidence": "test"
    },
    {
      "predicate": "the same memory is present in the JSONL store byte-for-byte (dual-write verified)",
      "evidence": "test"
    },
    {
      "predicate": "the JSONL write path is behaviourally unchanged from pre-wave (safety net untouched)",
      "evidence": "check"
    }
  ],
  "deps": [
    "W3-DIM"
  ],
  "readonly": false,
  "touches": [
    "python/synapse/memory/moneta_store.py",
    "python/synapse/memory/moneta_runtime.py",
    "tests/"
  ],
  "crucible_criteria": [
    "SEAM GUARD: fix/memory-store-recovery is UNMERGED and owns the store - receipt states rebase-compatibility; semantics drift is a BLOCK",
    "any write path where a memory lands ONLY in moneta is a BLOCK - dual-write is the wave's non-negotiable",
    "the Temp-dir usd_root durability risk is carried as an explicit receipt finding, not silently accepted",
    "receipt claims observed scope only: a write/query round-trip does not claim store-level production health"
  ],
  "spawn_classes": [
    "probe"
  ],
  "note": "Blueprint Phase 0 honesty items (deterministic in_use, never claim moneta while serving jsonl) are covered by W3-DIM targets 3-4; this leg makes in_use a real True."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave3 W3-STORE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave3`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave3 W3-STORE finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave3 W3-STORE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave3 W3-STORE`

## Receipt (completion contract)

Write `harness/notes/receipts/W3-STORE.json` **inside your worktree**:
`{{"leg": "W3-STORE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
