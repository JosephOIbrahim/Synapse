# W5-WCRUX â€” substrate crucible: adversarial gate over the weak-domain substrate legs before any merge word

You are a SYNAPSE wave agent on branch `wave5/wcrux` in worktree `.claude/worktrees/w5-wcrux`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-WCRUX",
  "band": "TRUTH",
  "name": "substrate crucible: adversarial gate over the weak-domain substrate legs before any merge word",
  "source": {
    "doc": "docs/BLUEPRINT_WEAK_DOMAINS.md",
    "anchor": "house rule: CRUX before merge - applies to every merged product; blueprint FP1/FP2 are the audit lens"
  },
  "targets": [
    "1) re-verify every substrate leg acceptance independently or mark UNKNOWN with the exact unobtainable step - none inherited; catalog spot-audits re-sampled with DIFFERENT nodes than the builder chose",
    "2) FP1 audit: sample catalog rows against a fresh hython session yourself; any row not traceable to a dump receipt is a laundered claim",
    "3) FP2 audit: run the broken/healthy golden pair yourself; verify the tier ladder cannot promote without measurement",
    "4) mandate table, binary per leg: receipt states a HEAD that exists and precedes the receipt write; the receipt is the leg's OWN closing commit",
    "5) combined-state probe on a scratch tree staging CATALOG + PARMGATE + MEASURES; suite ratchet vs base + guardrail_violations; ingest_ledger byte-identical before/after (single-writer R1)",
    "6) verdict board + receipt committed on wave5/wcrux; the receipt is this leg's own closing commit"
  ],
  "acceptance": [
    {
      "predicate": "per-leg verdicts with independent re-execution evidence, UNKNOWNs never laundered",
      "evidence": "probe"
    },
    {
      "predicate": "mandate table binary per leg including the receipt-closing-commit check",
      "evidence": "check"
    },
    {
      "predicate": "combined scratch-tree probe recorded (ratchet + guardrails + ledger byte-check), cleaned up",
      "evidence": "probe"
    }
  ],
  "deps": [
    "W5-CATALOG",
    "W5-PARMGATE",
    "W5-MEASURES"
  ],
  "readonly": true,
  "touches": [],
  "crucible_criteria": [
    "carries CRX0, the W5H receipt-commit-gap lessons, and the wave5l precedents as standing checks",
    "house rule: unobtainable renders UNKNOWN, never zero and never an estimate"
  ],
  "spawn_classes": [
    "probe"
  ],
  "note": "Gates the substrate trio only - W5-LCRUX's scope stays frozen on the lifecycle four. Merge remains Joe's word, per leg. Domain waves A-E author only after this substrate merges."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-WCRUX claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-WCRUX finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-WCRUX status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-WCRUX`

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

Write `harness/notes/receipts/W5-WCRUX.json` **inside your worktree**:
`{{"leg": "W5-WCRUX", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
