# W5-SHELF â€” shelf truth: PySide6-first clipboard + current installer message (greens shelf_current), icons + tooltips for all six tools

You are a SYNAPSE wave agent on branch `wave5/shelf` in worktree `.claude/worktrees/w5-shelf`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-SHELF",
  "name": "shelf truth: PySide6-first clipboard + current installer message (greens shelf_current), icons + tooltips for all six tools",
  "band": "BUILD",
  "class": "build",
  "note": "compiled from Joe's live seat observations 2026-08-16, items 6-7 ('hard to read and not sure what it does'), folded with the red shelf_current machine gate (P1-shelf).",
  "targets": [
    "1) houdini/scripts/python/synapse_shelf.py: PySide6-first clipboard with the PySide2 fallback KEPT (the gate greens on PySide6 PRESENCE, never PySide2 absence) + user-facing installer message points to scripts/install_synapse_package.py -> machine gate shelf_current GREEN",
    "2) icons for the six shelf tools (Project Setup, Inspect Selection, Inspect Scene, Last Result, Health Check, Generate Docs); .gitignore blankets *.png/*.jpg around lines 94-95 -> icon assets need git add -f <named files>, shas noted in the receipt",
    "3) tooltip/help text per tool stating what it does in one operator sentence"
  ],
  "touches": [
    "houdini/",
    "tests/"
  ],
  "readonly": false,
  "deps": [],
  "crucible_criteria": [
    "crucible re-runs shelf_current itself via python harness/verify/checks.py - never inherits the builder's claim",
    "PySide2 literal legitimately survives the fix - any crucible test gating on its absence is wrong by spec",
    "icon files must exist in the commit (git add -f receipts) - a tooltip-only fix does not satisfy item 6"
  ],
  "spawn_classes": [
    "probe"
  ],
  "source": {
    "doc": "harness/notes/h22/panel-observations-2026-08-16.md",
    "anchor": "items 6, 7 - Joe, live seat; shelf screenshot in session"
  },
  "acceptance": [
    {
      "predicate": "shelf_current reads GREEN (PySide6 presence + install_synapse_package.py message)",
      "evidence": "check"
    },
    {
      "predicate": "each of the six tools carries an icon committed via git add -f with sha recorded",
      "evidence": "probe"
    },
    {
      "predicate": "each of the six tools carries a tooltip/help string",
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-SHELF claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-SHELF finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-SHELF status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-SHELF`

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

Write `harness/notes/receipts/W5-SHELF.json` **inside your worktree**:
`{{"leg": "W5-SHELF", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
