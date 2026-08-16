# W5-LIFE â€” R.2: process-lifetime heartbeat owner + session survival - panel close must not kill the runtime; reopen reconnects to the SAME session

You are a SYNAPSE wave agent on branch `wave5/life` in worktree `.claude/worktrees/w5-life`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-LIFE",
  "name": "R.2: process-lifetime heartbeat owner + session survival - panel close must not kill the runtime; reopen reconnects to the SAME session",
  "band": "BUILD",
  "class": "build",
  "note": "compiled from Joe's live g5 fail, 2026-08-16. Ritual halted at g5 until this lands; g5 re-runs on the fixed build (Joe's hands, never simulated).",
  "targets": [
    "1) synapse_panel.py: remove the panel-parented beat source (self._freeze_timer = QTimer(self)); beat emission moves to a process-lifetime owner under python/synapse/server/ exposing def ensure_beat_started plus a # RUNTIME_BEAT_SOURCE sentinel - deleting the timer WITHOUT the replacement is the R.2 check's own RED leg",
    "2) closeEvent performs DELIBERATE beat-source detach: watchdog informed, no dead-beat false-freeze, FreezeChain never escalates a healthy runtime (resilience.py monitor + freeze_chain.py semantics)",
    "3) panel close leaves runtime + session store alive; reopen reconnects to the SAME runtime with chat history restored (Joe's live repro: closed tab -> operation finished headless -> reopen = not connected, no history)",
    "4) real freeze protection intact: a stalled main thread still escalates - RED/GREEN test pair, headless-simulated",
    "5) machine gate runtime_owns_heartbeat reads GREEN (both legs) via python harness/verify/checks.py"
  ],
  "touches": [
    "python/synapse/panel/synapse_panel.py",
    "python/synapse/server/",
    "tests/"
  ],
  "readonly": false,
  "deps": [],
  "crucible_criteria": [
    "python/synapse/panel/ is shared with W5-PANEL and W5-ROPE this wave -> bus claim before ANY edit; an overlapping open claim stops the leg",
    "timer deletion without a live process-lifetime replacement = no freeze protection at all; crucible verifies protection BEHAVIOR, not literal absence",
    "gui-only legs (live Houdini close/reopen) render UNKNOWN - g5 re-run is Joe's, never simulated into a pass"
  ],
  "spawn_classes": [
    "probe"
  ],
  "source": {
    "doc": "harness/state/release_receipts.json",
    "anchor": "g5_lifecycle :: fail 2026-08-16 - reopen met a fresh runtime, no chat history"
  },
  "acceptance": [
    {
      "predicate": "runtime_owns_heartbeat GREEN, both legs: panel-parented literal gone AND a server-side process-lifetime owner present",
      "evidence": "check"
    },
    {
      "predicate": "deliberate detach: panel close produces no false freeze escalation; stalled main thread still escalates (RED/GREEN pair)",
      "evidence": "test"
    },
    {
      "predicate": "session survival: reconnect-to-same-runtime with history restored - headless-simulatable parts tested, gui-required parts recorded UNKNOWN",
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-LIFE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-LIFE finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-LIFE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-LIFE`

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

Write `harness/notes/receipts/W5-LIFE.json` **inside your worktree**:
`{{"leg": "W5-LIFE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
