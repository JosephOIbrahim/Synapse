# W5-PANEL â€” panel UX truth: font floor = Houdini default scaling UP, +0.75pt chat leading, Token tab computes real per-task spend on the selected model

You are a SYNAPSE wave agent on branch `wave5/panel` in worktree `.claude/worktrees/w5-panel`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-PANEL",
  "name": "panel UX truth: font floor = Houdini default scaling UP, +0.75pt chat leading, Token tab computes real per-task spend on the selected model",
  "band": "BUILD",
  "class": "build",
  "note": "compiled from Joe's live seat observations 2026-08-16, items 2-5. Fix work only - no lifecycle/timer surface (that is W5-LIFE's claim).",
  "targets": [
    "1) minimum font size floors at the Houdini UI default, derived from the host (hou.ui / QApplication font) - never a hardcoded pt; the size switcher scales UP from that floor (today it only shrinks below default)",
    "2) chat text vertical spacing gains +0.75pt leading - current line spacing too tight (Joe's words)",
    "3) Token tab calculates per-task token spend on the SELECTED model from real usage data (API usage fields / runtime counters); absent plumbing gets minimal honest wiring; anything unmeasurable renders UNKNOWN in the UI - never a fake or frozen number"
  ],
  "touches": [
    "python/synapse/panel/",
    "tests/"
  ],
  "readonly": false,
  "deps": [],
  "crucible_criteria": [
    "python/synapse/panel/ is shared with W5-LIFE and W5-ROPE -> bus claim before ANY edit; overlapping open claim stops the leg; synapse_panel.py lifecycle/timer lines are LIFE's surface - do not touch them",
    "no hardcoded font sizes anywhere - the floor must derive from the host at runtime",
    "token numbers must trace to a usage-source receipt; a counter that invents values is worse than a dead one"
  ],
  "spawn_classes": [
    "probe"
  ],
  "source": {
    "doc": "harness/notes/h22/panel-observations-2026-08-16.md",
    "anchor": "items 2, 3, 4, 5 - Joe, live seat"
  },
  "acceptance": [
    {
      "predicate": "font floor == host default at runtime and switcher only scales up from it (no state below floor reachable)",
      "evidence": "test"
    },
    {
      "predicate": "chat leading increased by 0.75pt over prior value, asserted against the widget's effective line spacing",
      "evidence": "test"
    },
    {
      "predicate": "Token tab spend traces to a real usage source for the selected model; unmeasurable states render UNKNOWN",
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-PANEL claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-PANEL finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-PANEL status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-PANEL`

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

Write `harness/notes/receipts/W5-PANEL.json` **inside your worktree**:
`{{"leg": "W5-PANEL", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
