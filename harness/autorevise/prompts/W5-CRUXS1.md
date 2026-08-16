# W5-CRUXS1 â€” ingest solaris_compound_node_anatomy.md into rag/corpus/ so the CTO-bound reference is retrievable

You are a SYNAPSE wave agent on branch `wave5/cruxs1` in worktree `.claude/worktrees/w5-cruxs1`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-CRUXS1",
  "name": "ingest solaris_compound_node_anatomy.md into rag/corpus/ so the CTO-bound reference is retrievable",
  "band": "BUILD",
  "class": "probe",
  "source": {
    "doc": "harness/notes/receipts/W5-CRUX.json",
    "anchor": "finding F-CRUX-1"
  },
  "targets": [
    "1) author a rag/corpus/ entry for solaris_compound_node_anatomy (id/type/context/label/summary/searchable_text) so the semantic-index id has a corpus backing and is no longer skipped",
    "2) regression probe: synapse_scout('componentgeometry') surfaces the anatomy doc (or knowledge_lookup returns it) so the H22 'alternative' output + island paths are discoverable",
    "3) OR reconcile _dense_ids against the materialized corpus so a doc with an embedding but no corpus entry degrades to honest-empty rather than being silently unreachable"
  ],
  "acceptance": [
    {
      "predicate": "the anatomy doc is retrievable via synapse_scout or knowledge_lookup, and its H22 'alternative' + island-path facts surface for a componentgeometry / component-builder-internals query",
      "evidence": "probe"
    }
  ],
  "readonly": false,
  "touches": [
    "rag/corpus/",
    "python/synapse/cognitive/tools/scout.py",
    "tests/"
  ],
  "spawn_classes": [
    "probe"
  ],
  "note": "compiled from spawn W5-CRUX-S1 in W5-CRUX.json. The anatomy doc the CTO bound to this wave ('consult before any Solaris/VOP-adjacent claim') has a rag/semantic_index embedding row but NO rag/corpus backing entry, so scout's defe class=probe within W5-CRUX spawn_classes; edits shared surfaces (rag/corpus, scout.py) outside this readonly crux's touches -> lands held for Joe.",
  "deps": [],
  "crucible_criteria": [
    "house rule: unobtainable renders UNKNOWN, never zero and never an estimate",
    "COMMIT BEFORE RECEIPT, and the receipt itself is the leg's own closing commit"
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-CRUXS1 claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-CRUXS1 finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-CRUXS1 status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-CRUXS1`

## Receipt (completion contract)

**COMMIT BEFORE RECEIPT — hard order (CRX0, wave 4).** The receipt is written
LAST, after your named-file commit exists on your branch. Sequence: (1) commit
your product + notes files (named, never -A); (2) verify `git rev-list --count
<base>..HEAD` >= 1; (3) only then write the receipt, and state the observed
HEAD sha in it. A receipt at ahead:0 asserts commit-state that does not exist —
the exact claim-before-act defect this harness exists to kill.

Write `harness/notes/receipts/W5-CRUXS1.json` **inside your worktree**:
`{{"leg": "W5-CRUXS1", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
