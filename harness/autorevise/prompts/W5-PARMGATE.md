# W5-PARMGATE â€” substrate P1b: the Parm Gate - gated_set() rejects unknown parm names before touching the node, nearest-match suggestions from the catalog

You are a SYNAPSE wave agent on branch `wave5/parmgate` in worktree `.claude/worktrees/w5-parmgate`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-PARMGATE",
  "name": "substrate P1b: the Parm Gate - gated_set() rejects unknown parm names before touching the node, nearest-match suggestions from the catalog",
  "band": "BUILD",
  "class": "build",
  "note": "Blueprint M2 (docs/BLUEPRINT_WEAK_DOMAINS.md section 2, 'The Parm Gate'). Depends on W5-CATALOG - the gate needs catalog rows to gate against. The parm('kernelcode') or parm('code') hedge in the RD handler is the symptom this cures.",
  "targets": [
    "1) gated_set(node, parm_values) in handler_helpers.py or python/synapse/validation/: reject unknown parm names BEFORE any mutation; on miss raise with nearest-match suggestions from rag/catalog/h22.0.400/; on pass set inside the EXISTING undo-group discipline - never a new undo path",
    "2) runtime lookup API: catalog.parms(category, node_type), catalog.signature(category, node_type) - cheap exact lookups, no embedding round-trips",
    "3) route the weak-domain handlers (handlers_cops.py, DOP/CHOP/VOP handler surfaces) through gated_set for every parm write; the kernelcode/code hedge in reaction_diffusion is deleted and replaced by the gate (observed 2026-08-16: kernelcode is real, code does not exist on the H22 opencl COP)",
    "4) a hallucinated parm name becomes a caught error with a useful suggestion - RED/GREEN test pair proving both the rejection and the suggestion quality"
  ],
  "touches": [
    "python/synapse/server/",
    "python/synapse/validation/",
    "tests/"
  ],
  "readonly": false,
  "deps": [
    "W5-CATALOG"
  ],
  "crucible_criteria": [
    "the gate must not bypass or weaken the undo-group discipline the Ctrl+Z waves just shipped - crucible verifies a gated set still lands in one undo group",
    "handlers_cops.py may be touched by future wave-A work but is claimed by nobody this wave - bus claim anyway, shared-surface habit",
    "gate failures must be catchable and self-correcting for the agent loop, never silent no-ops"
  ],
  "spawn_classes": [
    "probe"
  ],
  "source": {
    "doc": "docs/BLUEPRINT_WEAK_DOMAINS.md",
    "anchor": "section 2 - The Parm Gate; section 8 runtime lookup API"
  },
  "acceptance": [
    {
      "predicate": "gated_set rejects a deliberately wrong parm name with a nearest-match suggestion (RED/GREEN pair)",
      "evidence": "test"
    },
    {
      "predicate": "weak-domain handlers route parm writes through the gate; the kernelcode/code hedge is gone",
      "evidence": "test"
    },
    {
      "predicate": "a gated set still wraps in exactly one undo group",
      "evidence": "test"
    }
  ]
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-PARMGATE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-PARMGATE finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-PARMGATE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-PARMGATE`

## Receipt (completion contract)

**COMMIT BEFORE RECEIPT — hard order (CRX0, wave 4).** The receipt is written
LAST, after your named-file commit exists on your branch. Sequence: (1) commit
your product + notes files (named, never -A); (2) verify `git rev-list --count
<base>..HEAD` >= 1; (3) only then write the receipt, and state the observed
HEAD sha in it. A receipt at ahead:0 asserts commit-state that does not exist —
the exact claim-before-act defect this harness exists to kill.

**THE RECEIPT IS ITS OWN CLOSING COMMIT - the leg commits it, not the operator
(W5H).** Commit-before-receipt is only the first half. The second half is that
the receipt file must itself land as your branch's LAST commit (named, never
`-A`): writing it into the worktree is not finishing, committing it is.
Operator rescue is a failure mode, not the plan. In wave 5, W5-CRUX and three of
the four builder legs (W5-BASE, W5-DENSE, W5-UNDO) left their receipts
worktree-only, and a human had to bring them in-tree afterward (the close pass
`c7a6a08d`; `76ca94a0` for CRUX). Only W5-DELTA committed its own receipt as its
closing commit (`b4bbb562` on `wave5/delta`) - that is the rule now, for every
leg. Full sequence: product commit -> verify ahead >= 1 -> write the receipt
stating the product HEAD sha -> commit the receipt as your closing commit.

Write `harness/notes/receipts/W5-PARMGATE.json` **inside your worktree**:
`{{"leg": "W5-PARMGATE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
