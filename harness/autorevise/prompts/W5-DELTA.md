# W5-DELTA â€” ING-DELTA: shipped contexts re-promoted from the 22.0.400 archive - freshness gate goes green

You are a SYNAPSE wave agent on branch `wave5/delta` in worktree `.claude/worktrees/w5-delta`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-DELTA",
  "name": "ING-DELTA: shipped contexts re-promoted from the 22.0.400 archive - freshness gate goes green",
  "band": "BUILD",
  "source": {
    "doc": "harness/notes/receipts/W4-GUARD.json",
    "anchor": "Freshness gate honestly RED: served corpus stamped .368 != ratified .400 (drop.json), release-blocking by design; W4-GUARD proposed probe ING-DELTA. Promote path already emits id/searchable_text (W4-KNOW); helpdoc is build-parameterized (W4-HELP) - re-promotion of the SHIPPED contexts (cop/lop/cop2) from the .400 archive needs no new machinery."
  },
  "targets": [
    "1) re-run rag_promote_h22 for the shipped contexts against the 22.0.400 archive via the parameterized helpdoc surface; corpus stamped 22.0.400",
    "2) zero entry loss vs the .368 corpus: every currently-served (context,type) survives; collisions keep both, deletions forbidden; adds/changes receipted with counts",
    "3) K.7 corpus_stamp_fresh flips ok:true on the leg's worktree",
    "4) the ledger entry for this flip is PROPOSED in the receipt, not written - the ingest ledger is single-writer (gate side); the wiring flip lands at merge on Joe's word",
    "5) CROSS-REFERENCE (rag/skills/houdini21-reference/solaris_compound_node_anatomy.md, live-verified 22.0.400): the .400 corpus must not contradict the live-verified anatomy - especially: NO karmamaterial* VOP type exists (the tab entry is a configured subnet), componentgeometry gains an 'alternative' output in H22, instancer tab resolves to type copytopoints. Post the census AND any corpus-vs-anatomy contradictions to the bus as findings addressed to W5-DENSE and W5-CRUX"
  ],
  "acceptance": [
    {
      "predicate": "corpus header stamped 22.0.400; checks.py --task K.7 shows corpus_stamp_fresh ok:true in the worktree",
      "evidence": "check"
    },
    {
      "predicate": "entry census: .400 count >= .368 count per shipped context, zero dropped (context,type) keys, diff receipted",
      "evidence": "test"
    },
    {
      "predicate": "COP/LOP calibration regression holds on the .400 corpus (the 35/35 class) and served phantom stays 0.00",
      "evidence": "check"
    },
    {
      "predicate": "scout_eval floor-clearing and disambiguation do not regress vs W4-CRUX figures on the new corpus",
      "evidence": "check"
    },
    {
      "predicate": "anatomy cross-check: no .400 corpus entry contradicts the live-verified compound-node anatomy doc; a scout probe for karmamaterialbuilder yields honest not-found or subnet guidance, never a phantom type",
      "evidence": "check"
    }
  ],
  "deps": [],
  "readonly": false,
  "touches": [
    "harness/notes/rag_promote_h22.py",
    "rag/corpus/h22_nodes.json",
    "harness/notes/h22/",
    "tests/"
  ],
  "crucible_criteria": [
    "BUS CONTRACT: post the census and any corpus-vs-anatomy contradictions as findings addressed to W5-DENSE and W5-CRUX as soon as the .400 promote completes - peers eval against your corpus; silence past a re-stamp is a receipt-level violation",
    "QUIT-RULE: any served entry lost vs .368 -> STOP, keep-both, post for_ruling; a re-ingest never deletes",
    "backup-before-mutation: the .368 corpus file is copied aside before the promote writes, path in the receipt",
    "ledger single-writer honored: the leg proposes, never writes harness/ingest_ledger.json",
    "house rule: unobtainable renders UNKNOWN, never zero and never an estimate"
  ],
  "spawn_classes": [
    "probe"
  ],
  "note": "Greens the gate GUARD built. Runs on current parser - Branch-A patches are wave-7 material behind Gate P. COMMIT BEFORE RECEIPT."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-DELTA claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-DELTA finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-DELTA status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-DELTA`

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

Write `harness/notes/receipts/W5-DELTA.json` **inside your worktree**:
`{{"leg": "W5-DELTA", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
