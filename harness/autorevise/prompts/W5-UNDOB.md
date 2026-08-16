# W5-UNDOB â€” close the remaining live-path Ctrl+Z holes: set_parm + set_keyframe wrap, integrity_envelope docstring sync

You are a SYNAPSE wave agent on branch `wave5/undob` in worktree `.claude/worktrees/w5-undob`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-UNDOB",
  "name": "close the remaining live-path Ctrl+Z holes: set_parm + set_keyframe wrap, integrity_envelope docstring sync",
  "band": "BUILD",
  "class": "build",
  "note": "compiled from spawn W5-UNDO-B in W5-UNDO.json. class outside W5-UNDO spawn_classes ([probe]) -> lands HELD for Joe.",
  "targets": [
    "handlers.py:_handle_set_parm wraps its parm.set/parm_tuple.set mutations in one hou.undos.group",
    "handlers_render.py:_handle_set_keyframe wraps its parm.setKeyframe mutations in one hou.undos.group",
    "integrity_envelope.py:19-28 docstring updated: create/connect/delete now wrap; only set_parm/set_keyframe remain; CLAUDE.md 1 is no longer drift for the three node handlers"
  ],
  "touches": [
    "python/synapse/server/handlers.py",
    "python/synapse/server/handlers_render.py",
    "python/synapse/server/integrity_envelope.py",
    "CLAUDE.md",
    "tests/"
  ],
  "readonly": false,
  "deps": [],
  "crucible_criteria": [
    "handlers.py + handlers_render.py are high-traffic shared surfaces -> bus claim + main-tree seam-guard BEFORE any edit; two writers on one surface stops the train"
  ],
  "spawn_classes": [
    "probe"
  ],
  "source": {
    "doc": ".claude/worktrees/w5-undo/harness/notes/receipts/W5-UNDO.json",
    "anchor": "spawned by W5-UNDO :: "
  },
  "acceptance": [
    {
      "predicate": "handlers.py:_handle_set_parm wraps its parm.set/parm_tuple.set mutations in one hou.undos.group",
      "evidence": "test"
    },
    {
      "predicate": "handlers_render.py:_handle_set_keyframe wraps its parm.setKeyframe mutations in one hou.undos.group",
      "evidence": "test"
    },
    {
      "predicate": "integrity_envelope.py:19-28 docstring updated: create/connect/delete now wrap; only set_parm/set_keyframe remain; CLAUDE.md 1 is no longer drift for the three node handlers",
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-UNDOB claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-UNDOB finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-UNDOB status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-UNDOB`

## Receipt (completion contract)

**COMMIT BEFORE RECEIPT — hard order (CRX0, wave 4).** The receipt is written
LAST, after your named-file commit exists on your branch. Sequence: (1) commit
your product + notes files (named, never -A); (2) verify `git rev-list --count
<base>..HEAD` >= 1; (3) only then write the receipt, and state the observed
HEAD sha in it. A receipt at ahead:0 asserts commit-state that does not exist —
the exact claim-before-act defect this harness exists to kill.

Write `harness/notes/receipts/W5-UNDOB.json` **inside your worktree**:
`{{"leg": "W5-UNDOB", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
