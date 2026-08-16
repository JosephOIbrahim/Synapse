# W6-FORGE â€” hardening 0/5: mine every receipt, finding, and ruling into the canonical failure-class ledger

You are a SYNAPSE wave agent on branch `wave6/forge` in worktree `.claude/worktrees/w6-forge`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W6-FORGE",
  "band": "BUILD",
  "class": "build",
  "name": "hardening 0/5: mine every receipt, finding, and ruling into the canonical failure-class ledger",
  "source": {
    "doc": "harness/notes/receipts/",
    "anchor": "Joe word 2026-08-16: hardening pass from first principles - failure history becomes enforced gates"
  },
  "targets": [
    "1) TEAM LEAD - use Agent Teams: fan 3 parallel readers over (a) harness/notes/receipts/**, (b) all *_verdict.md + crux rulings + harness/SPEC.md + rsi/SPEC.md, (c) git log --grep for fix/caught/violation on harness paths. HOLD YOUR TURN while teammates run; do not conclude until all three report.",
    "2) synthesize harness/HARDENING-SPEC.md: one row per failure CLASS (not instance) - name, first occurrence, instances, current defense (wired gate / warn-only / prose-only / none), target gate, owner surface. Known seeds you must place, then extend: unquoted interpolation (2026-07-26 prompt truncation + 2026-08-16 name parse bomb), unwired provenance guardrail, grep-only heartbeat check, receipt-without-commit (CRX0), missing bus RELEASE (LCRUX F2/F3), claim-without-observation family (face_token), UNKNOWN-laundering, PS 5.1 BOM/JSON landmines",
    "3) publish the ledger row list to the bus addressed to W6-QUOTE/W6-PROV/W6-BEAT/W6-GATE - it is their shared spec",
    "4) every row cites its evidence anchor (receipt path or commit) - a class without a lived instance is marked PREEMPTIVE, never invented history",
    "5) BUS MANDATE: post claim at start, findings to peers as you resolve shared facts, explicit RELEASE at close. W6-GATE is making this enforceable - model it."
  ],
  "touches": [
    "harness/HARDENING-SPEC.md"
  ],
  "deps": [],
  "readonly": false,
  "crucible_criteria": [
    "every class row carries an evidence anchor; synthesis without citation is the exact defect this wave kills",
    "receipt is own closing commit; RELEASE posted"
  ],
  "spawn_classes": [
    "probe"
  ],
  "acceptance": [
    {
      "predicate": "HARDENING-SPEC.md exists with anchored class rows covering at least the 8 seeded classes plus any newly mined",
      "evidence": "check"
    },
    {
      "predicate": "bus message to all four builders with the row list",
      "evidence": "probe"
    }
  ],
  "note": "Team-lead leg (3-reader fan-out). The ledger is the first-principles artifact: standards derived from lived failures."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-FORGE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave6`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-FORGE finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-FORGE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave6 W6-FORGE`

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

Write `harness/notes/receipts/W6-FORGE.json` **inside your worktree**:
`{{"leg": "W6-FORGE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
