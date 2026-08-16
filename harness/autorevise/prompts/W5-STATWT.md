# W5-STATWT â€” statusline resolves the worktree gitdir so tests/test_statusline.py passes in a linked worktree

You are a SYNAPSE wave agent on branch `wave5/statwt` in worktree `.claude/worktrees/w5-statwt`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-STATWT",
  "name": "statusline resolves the worktree gitdir so tests/test_statusline.py passes in a linked worktree",
  "band": "BUILD",
  "targets": [
    "resolve ROOT/.git when it is a file (parse 'gitdir: <path>') so branch()/head_sha()/packed-refs/worktrees enumeration work from inside a linked worktree",
    "tests/test_statusline.py: 13/13 in BOTH the main checkout and a linked worktree"
  ],
  "touches": [
    "harness/statusline.py",
    "tests/"
  ],
  "readonly": false,
  "spawn_classes": [
    "build"
  ],
  "note": "compiled from spawn W5-STATUSLINE-WT in W5-BASE.json. harness/statusline.py:100/127 open ROOT/.git/HEAD directly; in a linked worktree .git is a FILE ('gitdir: <path>'), so branch()/head_sha()/registered_paths() fail and 4 tests/test_ ",
  "deps": [],
  "crucible_criteria": [
    "house rule: unobtainable renders UNKNOWN, never zero and never an estimate",
    "COMMIT BEFORE RECEIPT, and the receipt itself is the leg's own closing commit"
  ],
  "source": {
    "doc": ".claude/worktrees/w5-base/harness/notes/receipts/W5-BASE.json",
    "anchor": "spawned by W5-BASE :: "
  },
  "acceptance": [
    {
      "predicate": "resolve ROOT/.git when it is a file (parse 'gitdir: <path>') so branch()/head_sha()/packed-refs/worktrees enumeration work from inside a linked worktree",
      "evidence": "test"
    },
    {
      "predicate": "tests/test_statusline.py: 13/13 in BOTH the main checkout and a linked worktree",
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-STATWT claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-STATWT finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-STATWT status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-STATWT`

## Receipt (completion contract)

**COMMIT BEFORE RECEIPT — hard order (CRX0, wave 4).** The receipt is written
LAST, after your named-file commit exists on your branch. Sequence: (1) commit
your product + notes files (named, never -A); (2) verify `git rev-list --count
<base>..HEAD` >= 1; (3) only then write the receipt, and state the observed
HEAD sha in it. A receipt at ahead:0 asserts commit-state that does not exist —
the exact claim-before-act defect this harness exists to kill.

Write `harness/notes/receipts/W5-STATWT.json` **inside your worktree**:
`{{"leg": "W5-STATWT", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
