# W6-JRNY â€” flow 1/4: map the canonical user journeys, panel to network, from lived evidence

You are a SYNAPSE wave agent on branch `wave6/jrny` in worktree `.claude/worktrees/w6-jrny`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W6-JRNY",
  "band": "BUILD",
  "name": "flow 1/4: map the canonical user journeys, panel to network, from lived evidence",
  "source": {
    "doc": "harness/notes/h22/panel-observations-2026-08-16.md",
    "anchor": "Joe word 2026-08-16: agent team for user flow, panel to networks - usability measured, not opined"
  },
  "targets": [
    "1) evidence base, anchored: harness/notes/h22/panel-observations-2026-08-16.md, the W5-ROPE seat-walk receipt, houdini/python_panels/synapse_panel.pypanel help text, the tool palette surface, W5-PANEL/W5-LIFE receipts. No invented personas - every journey step cites where a real seam or friction was observed or coded",
    "2) docs/USER-FLOW-MAP.md, capped at the TOP 6 journeys (first-node build, multi-node rig, error recovery, mode switch, palette tool use, close-reopen continuity). Each journey: numbered steps, seam classification (input/execution/feedback/recovery), current friction with anchor, and ONE measurable predicate per step a rig can assert",
    "3) publish the journey+predicate list to the bus addressed to W6-FLOWRIG; iterate when FLOWRIG reports a predicate unmeasurable - refine, never drop silently",
    "4) TOKEN DISCIPLINE (Joe word: token-saver + budget-advisor apply to this team): read anchored files only, never repo-wide trawls; externalize state to your artifact files early so context pressure never loses work; receipts cite line anchors, not file dumps.",
    "5) BUS MANDATE - this team exists to talk: post claim at start, thread findings to your peers as you resolve them, explicit RELEASE at close."
  ],
  "touches": [
    "docs/USER-FLOW-MAP.md"
  ],
  "deps": [],
  "readonly": false,
  "crucible_criteria": [
    "a journey step without an evidence anchor is a laundered persona - the crucible will hunt these",
    "receipt is own closing commit; RELEASE posted"
  ],
  "spawn_classes": [
    "probe"
  ],
  "acceptance": [
    {
      "predicate": "USER-FLOW-MAP.md: 6 journeys, every step anchored + one measurable predicate",
      "evidence": "check"
    },
    {
      "predicate": "bus thread with FLOWRIG shows at least one refine round-trip or an explicit none-needed",
      "evidence": "probe"
    }
  ],
  "note": "",
  "class": "build"
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-JRNY claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave6`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-JRNY finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-JRNY status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave6 W6-JRNY`

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

Write `harness/notes/receipts/W6-JRNY.json` **inside your worktree**:
`{{"leg": "W6-JRNY", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
