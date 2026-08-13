# W1-HSTRIP â€” panel health strip

You are a SYNAPSE wave agent on branch `wave1/hstrip` in worktree `.claude/worktrees/w1-hstrip`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W1-HSTRIP",
  "name": "panel health strip",
  "band": "BUILD",
  "source": {
    "doc": "docs/SYNAPSE_production_readiness_report_2026.md",
    "anchor": "S4.1 persistent health/status strip + S1.2/S2.1 silent degradation surfacing"
  },
  "targets": [
    "python/synapse/panel/ - slim always-visible status strip",
    "wire to existing health facts (synapse_health / doctor), never to asserted state"
  ],
  "acceptance": [
    {
      "predicate": "strip renders connection, memory-backend, project, active-job cells from live health facts",
      "evidence": "test"
    },
    {
      "predicate": "backend fallback (moneta->jsonl) renders AMBER/RED with the doctor's one-line reason - the 384/256 case must display, not hide",
      "evidence": "test"
    },
    {
      "predicate": "unmeasured/unreachable health facts render UNKNOWN, never green and never 0",
      "evidence": "test"
    },
    {
      "predicate": "strip visible in a live GUI session without stealing focus or stalling paint",
      "evidence": "gui_probe",
      "gui_required": true
    }
  ],
  "deps": [
    "BASE",
    "H4"
  ],
  "readonly": false,
  "touches": [
    "python/synapse/panel/",
    "tests/"
  ],
  "crucible_criteria": [
    "strip states are FACT-sourced (producer path per cell) - a green cell without a producer is a BLOCK",
    "degraded is loud: amber/red + reason, no click required to notice",
    "no main-thread I/O added by the strip itself (it must not become the next 648ms hold)",
    "H4 receipt precedes this leg (deps-encoded serialization); build on H4's landed token state, no re-litigating its choices"
  ],
  "spawn_classes": [
    "probe"
  ],
  "note": "P0.3 from the readiness report. The doctor is honest, the panel is not - this closes that gap. MEM leg (held, Joe's flip) owns the store-side fail-loud; this leg owns the SURFACING only. No memory-store mutation here - W1 Moneta recovery holds that seam."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave1 W1-HSTRIP claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave1`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave1 W1-HSTRIP finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave1 W1-HSTRIP status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave1 W1-HSTRIP`

## Receipt (completion contract)

Write `harness/notes/receipts/W1-HSTRIP.json` **inside your worktree**:
`{{"leg": "W1-HSTRIP", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
