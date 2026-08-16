# W6-BEAT â€” hardening 3/5: behavioral heartbeat pin - the runtime beat proven by killing the panel, not by grep (spawn W5-LCRUX-S1)

You are a SYNAPSE wave agent on branch `wave6/beat` in worktree `.claude/worktrees/w6-beat`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W6-BEAT",
  "band": "BUILD",
  "class": "build",
  "name": "hardening 3/5: behavioral heartbeat pin - the runtime beat proven by killing the panel, not by grep (spawn W5-LCRUX-S1)",
  "source": {
    "doc": "harness/notes/receipts/",
    "anchor": "Joe word 2026-08-16: hardening pass from first principles - failure history becomes enforced gates"
  },
  "targets": [
    "1) read the LCRUX F5 finding and the W5-LIFE receipt: runtime_owns_heartbeat currently greens on source grep; replace the proof with behavior",
    "2) test: start the runtime headless (server/runtime_beat.py + session_store.py surfaces from W5-LIFE), attach then destroy a panel-proxy object, assert the beat continues and the session store survives - the P0.3 contract exercised, not read",
    "3) point the machine gate at the behavioral test so a future regression that keeps the strings but breaks the behavior reads RED",
    "4) full relevant suite in worktree green; ratchet holds",
    "5) BUS MANDATE: post claim at start, findings to peers as you resolve shared facts, explicit RELEASE at close. W6-GATE is making this enforceable - model it."
  ],
  "touches": [
    "server/",
    "tests/"
  ],
  "deps": [
    "W6-FORGE"
  ],
  "readonly": false,
  "crucible_criteria": [
    "the pin must fail when the old panel-parented wiring is simulated - prove the test can catch the original defect",
    "receipt is own closing commit; RELEASE posted"
  ],
  "spawn_classes": [
    "probe"
  ],
  "acceptance": [
    {
      "predicate": "behavioral beat test: panel death, beat continues, session survives - first-hand",
      "evidence": "test"
    },
    {
      "predicate": "gate reads the behavior, not the grep; regression simulation fails RED",
      "evidence": "probe"
    }
  ],
  "note": "Folded HELD spawn W5-LCRUX-S1 on Joe hardening directive - flagged for pull before unblock."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-BEAT claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave6`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-BEAT finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-BEAT status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave6 W6-BEAT`

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

Write `harness/notes/receipts/W6-BEAT.json` **inside your worktree**:
`{{"leg": "W6-BEAT", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
