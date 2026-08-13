# W1-KPRE â€” karma progressive presets + background default

You are a SYNAPSE wave agent on branch `wave1/kpre` in worktree `.claude/worktrees/w1-kpre`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W1-KPRE",
  "name": "karma progressive presets + background default",
  "band": "BUILD",
  "source": {
    "doc": "docs/SYNAPSE_latency_and_karma_rendersettings_2026.md",
    "anchor": "Part 2/3/4 - progressive pipeline (layout/lighting/quality/final), OIDN, background soho_foreground=0 for quality+"
  },
  "targets": [
    "encode the four-stage progressive pipeline as named presets in SYNAPSE render orchestration (layout 320x240/4, lighting 960x540/16-32, quality 1080p/64, final 128-512)",
    "quality+ presets default to background render (soho_foreground=0) so renders never fight the panel for the main thread",
    "cheat-sheet lands in docs/ (bounce limits, denoise policy, AOV starter set, XPU-vs-CPU rule)"
  ],
  "acceptance": [
    {
      "predicate": "presets exist and set pathtracedsamples/resolution/denoise/engine per the addendum table",
      "evidence": "test"
    },
    {
      "predicate": "parm NAMES probe-verified against the live 22.0.400 build (autoresearch pattern: names are probe-verified, values are design choices)",
      "evidence": "probe"
    },
    {
      "predicate": "quality and final presets set background mode; layout and lighting stay foreground",
      "evidence": "test"
    },
    {
      "predicate": "XPU flush-delay note travels with the preset surface (10-15s post-render() is not a hang)",
      "evidence": "check"
    }
  ],
  "deps": [
    "BASE"
  ],
  "readonly": false,
  "touches": [
    "python/synapse/",
    "docs/",
    "tests/"
  ],
  "crucible_criteria": [
    "presets are additive - no existing render path changes behaviour unless a preset is invoked",
    "camera stays a USD prim path on usdrender; a preset must not smuggle a node path in",
    "no parm name ships un-probed; a name asserted from docs alone is a BLOCK (karmarenderproperties precedent)"
  ],
  "spawn_classes": [
    "probe"
  ],
  "note": "Part 2-4 of the addendum made executable. Small forge leg by design; the progressive pipeline is also the operational mitigation for panel latency (Part 3), so it ships in the same wave as MTFIX."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave1 W1-KPRE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave1`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave1 W1-KPRE finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave1 W1-KPRE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave1 W1-KPRE`

## Receipt (completion contract)

Write `harness/notes/receipts/W1-KPRE.json` **inside your worktree**:
`{{"leg": "W1-KPRE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
