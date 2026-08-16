# W5-HYGIENE â€” harness hygiene: subagent-aware liveness tracker, receipt-closing-commit template mandate, series work-order fix

You are a SYNAPSE wave agent on branch `wave5/hygiene` in worktree `.claude/worktrees/w5-hygiene`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-HYGIENE",
  "band": "BUILD",
  "name": "harness hygiene: subagent-aware liveness tracker, receipt-closing-commit template mandate, series work-order fix",
  "source": {
    "doc": "harness/notes/receipts/W5-CRUX.json",
    "anchor": "HOUSE NOTES: tracker blind to subagents/workflows; CRUX receipt closing-commit gap; CRUX-R2 set_parm mis-location"
  },
  "targets": [
    "1) READ harness/SPEC.md and harness/rsi/SPEC.md FIRST - no harness edit before both are read",
    "2) orchestrate.ps1 last-write liveness tracker also globs the leg's ~/.claude session subagents/workflows/ paths so a crucible deep in subagent probes never reads as dead",
    "3) prompts/_template.md gains the mandate: the receipt file is committed by the leg itself as its closing commit - operator rescue is a failure mode, cite W5 (CRUX + all four legs left receipts worktree-only)",
    "4) BLUEPRINT.md Series plan wording corrected per CRUX-R2: set_parm lives in handlers.py, not handlers_node.py; remaining Ctrl+Z holes ride W5-UNDO-B"
  ],
  "acceptance": [
    {
      "predicate": "tracker liveness test: a fixture path under subagents/workflows/ updates the last-write age",
      "evidence": "test"
    },
    {
      "predicate": "_template.md contains the receipt-closing-commit mandate with the W5 citation",
      "evidence": "check"
    },
    {
      "predicate": "BLUEPRINT.md Series plan no longer locates set_parm in handlers_node.py",
      "evidence": "check"
    }
  ],
  "deps": [],
  "readonly": false,
  "touches": [
    "harness/orchestrate.ps1",
    "harness/autorevise/prompts/_template.md",
    "harness/notes/h22/BLUEPRINT.md",
    "tests/"
  ],
  "crucible_criteria": [
    "SPEC.md + rsi/SPEC.md read before any harness edit - state it in the receipt with anchors",
    "the RUNNING orchestrator must not be disturbed: edits happen in the worktree only",
    "house rule: unobtainable renders UNKNOWN, never zero and never an estimate",
    "COMMIT BEFORE RECEIPT, and the receipt is the leg's own closing commit"
  ],
  "spawn_classes": [
    "probe"
  ],
  "note": "House-cleaning wave W5H. Fix the mirror before the next wave looks into it."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-HYGIENE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-HYGIENE finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-HYGIENE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-HYGIENE`

## Receipt (completion contract)

**COMMIT BEFORE RECEIPT — hard order (CRX0, wave 4).** The receipt is written
LAST, after your named-file commit exists on your branch. Sequence: (1) commit
your product + notes files (named, never -A); (2) verify `git rev-list --count
<base>..HEAD` >= 1; (3) only then write the receipt, and state the observed
HEAD sha in it. A receipt at ahead:0 asserts commit-state that does not exist —
the exact claim-before-act defect this harness exists to kill.

Write `harness/notes/receipts/W5-HYGIENE.json` **inside your worktree**:
`{{"leg": "W5-HYGIENE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
