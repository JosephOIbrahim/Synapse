# W5-WXB â€” crucible shard B: explosion-detector goldens + tier projection audited

You are a SYNAPSE wave agent on branch `wave5/wxb` in worktree `.claude/worktrees/w5-wxb`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-WXB",
  "band": "TRUTH",
  "name": "crucible shard B: explosion-detector goldens + tier projection audited",
  "source": {
    "doc": "harness/notes/h22/CTO-RULING-measures-divergence-2026-08-16.md",
    "anchor": "supersession note: charter delivered at 520a10d4 - the team audits that delivery"
  },
  "targets": [
    "1) Evidence tree: the audited content lives on branch wave5/measures (tip 520a10d4, product a6db2286), which is NOT on master. Create a side worktree inside your sandbox: `git worktree add _m wave5/measures` and run all re-execution there. Your receipts and any notes commit to YOUR OWN branch only - never touch wave5/measures or the side tree state.",
    "2) re-run the explosion-detector golden pair (fires-on-broken, silent-on-healthy) first-hand; verify the anchor names the offending frame + signal; try ONE fresh broken golden variant of your own",
    "3) acceptance-3 audit: the measurement-to-exposure-rung projection - re-run its tests, confirm extends-not-forks synapse.science.exposure, and verify the deferred MCP DISCLOSURE wiring (S1) is honestly absent, not silently claimed",
    "4) TOKEN DISCIPLINE: read anchors not trees; externalize evidence to your receipt early; cite line anchors, never file dumps.",
    "5) BUS MANDATE - this team exists to talk: post claim at start, post each finding to the bus AS IT LANDS addressed to W5-WCRUX (do not batch), explicit RELEASE at close."
  ],
  "touches": [],
  "deps": [],
  "readonly": true,
  "crucible_criteria": [
    "evidence first-hand from your own side-tree run, never inherited",
    "unobtainable renders UNKNOWN, never zero, never estimate"
  ],
  "spawn_classes": [
    "probe"
  ],
  "acceptance": [
    {
      "predicate": "both goldens + one fresh variant re-executed first-hand",
      "evidence": "probe"
    },
    {
      "predicate": "tier projection: extends-not-forks verified; S1 absence confirmed honest",
      "evidence": "check"
    }
  ],
  "note": ""
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-WXB claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-WXB finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-WXB status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-WXB`

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

Write `harness/notes/receipts/W5-WXB.json` **inside your worktree**:
`{{"leg": "W5-WXB", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
