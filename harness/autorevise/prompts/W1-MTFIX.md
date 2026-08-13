# W1-MTFIX â€” main-thread stalls: panel append/finalize + doctor hold

You are a SYNAPSE wave agent on branch `wave1/mtfix` in worktree `.claude/worktrees/w1-mtfix`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W1-MTFIX",
  "name": "main-thread stalls: panel append/finalize + doctor hold",
  "band": "BUILD",
  "source": {
    "doc": "docs/SYNAPSE_latency_and_karma_rendersettings_2026.md",
    "anchor": "Part 1 - 648ms main_thread_hold (synapse_doctor), 780ms panel finalize, 648ms append, 306ms dispatch tail"
  },
  "targets": [
    "panel result path: append/finalize off the main thread or incremental",
    "synapse_doctor: defer heavy I/O (log/telemetry/bridge/symbol-table) off the main thread",
    "main-thread budget + visible working indicator so a wait reads as 'tool working', not 'Houdini hung'"
  ],
  "acceptance": [
    {
      "predicate": "FRZ receipt consumed first: attribution findings are the map; do not re-derive them",
      "evidence": "receipt"
    },
    {
      "predicate": "GUI session: main_thread_hold_slowest_ms{synapse_doctor} < 100ms in synapse_metrics after fix",
      "evidence": "gui_probe",
      "gui_required": true
    },
    {
      "predicate": "GUI session: panel_result append and finalize phases under slow threshold on the same result volume that measured 648/780",
      "evidence": "gui_probe",
      "gui_required": true
    },
    {
      "predicate": "headless run reports these three as UNKNOWN (lastCookTime-class vendor contract: headless timing is not evidence)",
      "evidence": "check"
    },
    {
      "predicate": "suite ratchet floor holds; no behavioural regression in panel result content",
      "evidence": "test"
    }
  ],
  "deps": [
    "BASE",
    "FRZ"
  ],
  "readonly": false,
  "touches": [
    "python/synapse/panel/",
    "python/synapse/",
    "tests/"
  ],
  "crucible_criteria": [
    "off-thread work never touches hou.* off the main thread - marshal results back; violating this trades a stall for a crash",
    "before/after numbers carry probe receipts from the SAME session type; a headless 0.0 claimed as improvement is the exact bug class this repo documents",
    "the working indicator is driven by real state, not a timer",
    "if FRZ attributes the ~6s freeze Qt-side, that stays OUT of scope here - spawn proposal only"
  ],
  "spawn_classes": [
    "probe",
    "mtfix-followup"
  ],
  "note": "P1 latency core. FRZ (ready, on the board) attributes; this leg fixes what FRZ pinned to SYNAPSE-side holds. Dispatch wait (306ms tail) is queue physics - document, don't chase, unless FRZ says otherwise."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave1 W1-MTFIX claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave1`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave1 W1-MTFIX finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave1 W1-MTFIX status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave1 W1-MTFIX`

## Receipt (completion contract)

Write `harness/notes/receipts/W1-MTFIX.json` **inside your worktree**:
`{{"leg": "W1-MTFIX", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
