# W8-LIBR â€” librarian SYNTHESIZER: one findings index from seven scout streams

You are a SYNAPSE wave agent on branch `wave8/libr` in worktree `.claude/worktrees/w8-libr`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W8-LIBR",
  "band": "TRUTH",
  "name": "librarian SYNTHESIZER: one findings index from seven scout streams",
  "source": {
    "doc": "harness/bastion/PROGRAM.md",
    "anchor": "W8-LIBRARIAN"
  },
  "targets": [
    "1) Consume the bus: scouts post findings addressed to you as they land - read ALL; a scout claim you cannot trace to its receipt anchor is treated as unproven.",
    "2) Dedup against prior art: existing receipts, standing rulings, and the W6 failure-class ledger - a finding already ruled or already gated is cited, not re-opened.",
    "3) Spot-check: re-observe at least one load-bearing P0 finding per scout first-hand - trust is verified, never inherited.",
    "4) Emit harness/bastion/FINDINGS_INDEX.md on your own branch: per finding - id, blueprint, rank, anchor, status (new/known/gated), one-line evidence. This index is the sole input the Chunk-C blueprints cite.",
    "5) Receipt harness/notes/receipts/W8-LIBR.json as your closing commit; RELEASE on the bus; drop flag harness/notes/h22/w8-landed.flag.",
    "TOKEN DISCIPLINE: read anchors not trees; externalize evidence to your receipt early; cite file:line anchors, never file dumps."
  ],
  "touches": [],
  "deps": [
    "W8-SLIFE",
    "W8-STRUTH",
    "W8-SENGINE",
    "W8-SMEM",
    "W8-SSURF",
    "W8-SSHIELD",
    "W8-SSHIP"
  ],
  "readonly": true,
  "crucible_criteria": [
    "evidence first-hand from your own read-only recon, never inherited",
    "unobtainable renders UNKNOWN, never zero, never estimate",
    "one first-hand spot-check per scout stream"
  ],
  "spawn_classes": [
    "probe"
  ],
  "acceptance": [
    {
      "predicate": "all scout findings consumed with per-claim trace-or-unproven status",
      "evidence": "check"
    },
    {
      "predicate": "one first-hand spot-check per scout, stdout in receipt",
      "evidence": "probe"
    },
    {
      "predicate": "FINDINGS_INDEX.md + receipt + flag landed as closing commit",
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave8 W8-LIBR claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave8`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave8 W8-LIBR finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave8 W8-LIBR status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave8 W8-LIBR`

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

Write `harness/notes/receipts/W8-LIBR.json` **inside your worktree**:
`{{"leg": "W8-LIBR", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
