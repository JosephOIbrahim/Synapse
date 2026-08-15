# W4-HELP â€” helpdoc build pin parameterized: two attributes, no leg hardcodes a build

You are a SYNAPSE wave agent on branch `wave4/help` in worktree `.claude/worktrees/w4-help`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W4-HELP",
  "name": "helpdoc build pin parameterized: two attributes, no leg hardcodes a build",
  "band": "BUILD",
  "source": {
    "doc": "docs/reviews/h22-context-knowledge-recon-2026-08-15.md",
    "anchor": "Four parser patches, item repoint-the-pinned-build: harness/notes/h9/helpdoc.py hardcodes BUILD; verified i1_extract.py:59 BUILD = helpdoc.BUILD (pinned, fails loudly); pre-flight proved the .368-to-.400 repoint is two module attributes (helpdoc.BUILD, helpdoc.HELP_DIR) - parameterize, do not mutate"
  },
  "targets": [
    "1) helpdoc resolves BUILD and HELP_DIR from an explicit parameter or environment override, defaulting to the current pin - callers choose the build, nothing mutates the module",
    "2) importers (i1_extract.py:59 et al) consume the parameterized surface; grep-clean of hardcoded 22.0.368 on ingest code paths",
    "3) fails loudly when the requested build archive is absent - never silently serves another build's pages"
  ],
  "acceptance": [
    {
      "predicate": "helpdoc resolves 22.0.368 and 22.0.400 by parameter in one process without module mutation; absent-archive request raises and names the missing path",
      "evidence": "test"
    },
    {
      "predicate": "i1_extract parses a sample page from each build via the parameterized surface, zero exceptions",
      "evidence": "test"
    },
    {
      "predicate": "rg shows no hardcoded 22.0.368 governing harness/notes ingest code paths (docs, archive, receipts exempt)",
      "evidence": "check"
    }
  ],
  "deps": [],
  "readonly": false,
  "touches": [
    "harness/notes/h9/helpdoc.py",
    "harness/notes/ingest/i1_extract.py",
    "tests/"
  ],
  "crucible_criteria": [
    "the .368 pin was fails-loudly by design - parameterization must preserve loud failure, not soften it into a fallback",
    "house rule: unobtainable renders UNKNOWN, never zero and never an estimate"
  ],
  "spawn_classes": [
    "probe"
  ],
  "note": "Unblocks every ING-<CTX> leg from the stale pin; survives Gate P on either fork branch (both need a build-addressable doc source)."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave4 W4-HELP claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave4`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave4 W4-HELP finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave4 W4-HELP status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave4 W4-HELP`

## Receipt (completion contract)

Write `harness/notes/receipts/W4-HELP.json` **inside your worktree**:
`{{"leg": "W4-HELP", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
