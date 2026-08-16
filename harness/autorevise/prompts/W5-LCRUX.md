# W5-LCRUX â€” lifecycle-wave crucible: adversarial gate over the W5L legs before any merge word

You are a SYNAPSE wave agent on branch `wave5/lcrux` in worktree `.claude/worktrees/w5-lcrux`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-LCRUX",
  "band": "TRUTH",
  "name": "lifecycle-wave crucible: adversarial gate over the W5L legs before any merge word",
  "source": {
    "doc": "harness/notes/h22/BLUEPRINT.md",
    "anchor": "house rule: CRUX before merge - applies to every merged product"
  },
  "targets": [
    "1) re-verify every W5L leg acceptance independently or mark UNKNOWN with the exact unobtainable step - none inherited; that includes re-running runtime_owns_heartbeat and shelf_current via python harness/verify/checks.py yourself",
    "2) mandate table, binary per leg: receipt states a HEAD that exists and precedes the receipt write; the receipt is the leg's OWN closing commit (W5H F2: a receipt narrating a commit that never existed is a laundered claim - interrogate git, not prose)",
    "3) combined-state probe on a scratch tree staging all four legs; suite ratchet vs base + guardrail_violations on the combined tree; exact failing surface named if any",
    "4) panel/ overlap audit: LIFE, PANEL, ROPE all touched python/synapse/panel/ - verify bus claims were posted/released and no two legs edited one line",
    "5) verdict board + receipt committed on wave5l/crux; the receipt is this leg's own closing commit"
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
      "predicate": "combined scratch-tree probe recorded (ratchet + guardrails), cleaned up",
      "evidence": "probe"
    }
  ],
  "deps": [
    "W5-LIFE",
    "W5-PANEL",
    "W5-SHELF",
    "W5-ROPE"
  ],
  "readonly": true,
  "touches": [],
  "crucible_criteria": [
    "carries wave-4 CRX0, wave-5 first-enforcement, and the W5H receipt-commit-gap lessons as standing checks",
    "house rule: unobtainable renders UNKNOWN, never zero and never an estimate"
  ],
  "spawn_classes": [
    "probe"
  ],
  "note": "Gates all. Merge remains Joe's word, per leg."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-LCRUX claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-LCRUX finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-LCRUX status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-LCRUX`

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

Write `harness/notes/receipts/W5-LCRUX.json` **inside your worktree**:
`{{"leg": "W5-LCRUX", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
