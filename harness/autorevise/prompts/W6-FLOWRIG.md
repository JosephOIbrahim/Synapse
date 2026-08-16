# W6-FLOWRIG â€” flow 2/4: build the journey rig - hython drives real panel-to-network flows and measures every step

You are a SYNAPSE wave agent on branch `wave6/flowrig` in worktree `.claude/worktrees/w6-flowrig`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W6-FLOWRIG",
  "band": "BUILD",
  "name": "flow 2/4: build the journey rig - hython drives real panel-to-network flows and measures every step",
  "source": {
    "doc": "harness/notes/h22/panel-observations-2026-08-16.md",
    "anchor": "Joe word 2026-08-16: agent team for user flow, panel to networks - usability measured, not opined"
  },
  "targets": [
    "1) harness/probes/flow/: a journey runner under the real hython 22.0.400 (W5-PARITY env recipe is on the bus and in its receipt - HOUDINI_USER_PREF_DIR so the package loads) using the proven offscreen-Qt pattern from W5-PANEL: instantiate the live panel widget, drive prompts programmatically, let handlers build real nodes in a scratch hip",
    "2) per journey step measure into flow_results.json: wall latency, panel feedback text presence and readability (non-empty, non-traceback), node count + names + network layout bbox sanity (no stacked-at-origin spaghetti), undo group name present and descriptive, error-path humanity for the bad-prompt journey (readable in-panel error, session survives)",
    "3) consume the JRNY predicate list from the bus; anything unmeasurable goes BACK to JRNY as a bus finding with the exact blocked step - never silently skipped; true pixel rendering stays UNKNOWN (Joe seat)",
    "4) LLM-dependent steps: if a journey needs a live model call, use the cheapest configured engine once per journey, cache the transcript into the probe dir, and mark variability honestly - never loop generations",
    "5) TOKEN DISCIPLINE (Joe word: token-saver + budget-advisor apply to this team): read anchored files only, never repo-wide trawls; externalize state to your artifact files early so context pressure never loses work; receipts cite line anchors, not file dumps.",
    "6) BUS MANDATE - this team exists to talk: post claim at start, thread findings to your peers as you resolve them, explicit RELEASE at close."
  ],
  "touches": [
    "harness/probes/flow/"
  ],
  "deps": [
    "W6-JRNY"
  ],
  "readonly": false,
  "crucible_criteria": [
    "every number in flow_results.json traces to first-hand hython stdout committed alongside; unmeasured renders UNKNOWN",
    "receipt is own closing commit; RELEASE posted"
  ],
  "spawn_classes": [
    "probe"
  ],
  "acceptance": [
    {
      "predicate": "rig runs all 6 journeys end to end under hython; flow_results.json with per-step measurements",
      "evidence": "probe"
    },
    {
      "predicate": "bad-prompt journey: readable in-panel error, no traceback, session alive",
      "evidence": "test"
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-FLOWRIG claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave6`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-FLOWRIG finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-FLOWRIG status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave6 W6-FLOWRIG`

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

Write `harness/notes/receipts/W6-FLOWRIG.json` **inside your worktree**:
`{{"leg": "W6-FLOWRIG", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
