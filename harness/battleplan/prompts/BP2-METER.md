# BP2-METER — Token meter measured: post-close settle from the leg transcript into rails/ledger; per-leg tier resolution incl. referee; drift check on the bus

You are a SYNAPSE BATTLEPLAN wave agent on branch `bp2/meter` in worktree
`.claude/worktrees/bp2-meter`. Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This
brief is complete; if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "BP2-METER",
  "name": "Token meter measured: post-close settle from the leg transcript into rails/ledger; per-leg tier resolution incl. referee; drift check on the bus",
  "band": "BUILD",
  "class": "build",
  "note": "Tier: reasoning. Self-cap: 40 turns (a rails turn is a leg DISPATCH, not a conversational turn - docs/BATTLEPLAN.md sec.12 R-3; your cap is self-reported via progress messages every 5 turns). First leg of BP2 by design - every later cap is set from this leg's first measured ledger. REUSE BEFORE BUILD (sec.12 R-4): harness/rails.py:176 measure_transcript_tokens() and `rails.py charge --transcript` ALREADY EXIST; nothing calls them because orchestrate.ps1 Rails-Charge (:102-115) is a pre-dispatch gate. Do NOT build a `claude -p --output-format json` envelope parser: orchestrate legs are interactive sessions (orchestrate.ps1:406) and never emit an envelope; that parser belongs to harness/rope (parked). Cut T3 first if the cap nears. Parallel-safe with BP2-PANELTRUTH (harness/ vs panel/).",
  "targets": [
    "T1) POST-CLOSE SETTLE. In harness/orchestrate.ps1, when a leg transitions to done (the :682 branch) AND -Budget is set, resolve that leg's Claude Code transcript JSONL (the projects dir for the leg's worktree path; the .claude/.orch_launched marker and the --name 'SYNAPSE <id> ...' string are your anchors) and settle it: `python harness/rails.py charge --run <run> --leg <id> --model <model> --transcript <jsonl> --wall_ms <measured from marker timestamp to done>`. If the transcript cannot be resolved, settle with no --transcript so every token field stays the literal UNKNOWN - never skip the settle silently, never estimate. rails.py: `enforced_unit` becomes `tokens` only when a tokens ceiling is set AND >= 1 leg has measured tokens; a settle that crosses the ceiling sets status blocked/reason budget and the orchestrator dispatches nothing further (halt). Ledger fields integer-or-UNKNOWN. Absent -Budget: byte-identical (BP1 -DryRun control).",
    "T2) TIERS PER LEG. harness/rails_exec.json gains `referee: {engine: claude, model: claude-fable-5}` (lookup only; nothing else decides a model). harness/battleplan/mission_schema.py OPTIONAL gains `tier`; compile_wave.py carries `tier` onto the row; orchestrate.ps1:363 resolves `$leg.tier` via `python harness/rails.py resolve <tier>` when the row has one, else `$manifest.model` (byte-identical default). ADAPT receipt: the preflight at harness/battleplan/runs/2026-09-01/preflight.json shows the fable-5 alias resolving; if `rails.py resolve referee` cannot be honoured at dispatch, referee falls back to reasoning and the ledger row says so.",
    "T3) DRIFT. harness/battleplan/drift.py (<= 60 lines, pure Python, zero model calls): reads bus/<wave>/bus.jsonl; per leg, on-target ratio = progress messages citing a T<n> or acceptance index / progress messages, over the last 5; < 0.6 -> post `refocus` from `orchestrator` addressed to the leg with its mission targets verbatim; two refocus with no improvement -> post `halt`. orchestrate.ps1 invokes it once per poll ONLY when -Budget is set (additive). Document `progress` / `refocus` / `halt` in prompts/_template.md (the BP2 template already asks legs to post progress).",
    "T4) UNIT HONESTY. rails.py docstring and the ledger `note` state what a turn IS (one leg dispatch through Rails-Charge) so no reader mistakes 40 for conversational turns; tests/test_rails.py gains the settle cases."
  ],
  "touches": [
    "harness/orchestrate.ps1",
    "harness/rails.py",
    "harness/rails_exec.json",
    "harness/battleplan/mission_schema.py",
    "harness/battleplan/compile_wave.py",
    "harness/battleplan/drift.py",
    "harness/battleplan/prompts/_template.md",
    "tests/test_rails.py",
    "tests/fixtures/",
    "harness/battleplan/notes/",
    "harness/battleplan/runs/"
  ],
  "readonly": false,
  "deps": [],
  "crucible_criteria": [
    "no token value that did not come from a transcript message.usage record - an estimate is BROKEN, UNKNOWN is honest",
    "orchestrate.ps1 without -Budget is byte-identical: the -DryRun control log diff against runs/2026-08-31/orch_dryrun_before.norm.log is empty",
    "rails_exec.json remains a lookup table; nothing else decides a model",
    "the settle is post-close only - it never blocks or delays a dispatch",
    "drift.py makes zero model calls and never edits a mission or manifest"
  ],
  "spawn_classes": [
    "probe"
  ],
  "source": {
    "doc": "docs/BATTLEPLAN.md",
    "anchor": "2026-09-01 sec.0.4 H-1/H-2/H-4, sec.6 BP2-METER, sec.12 R-3/R-4/R-5/R-9"
  },
  "acceptance": [
    {
      "predicate": "a proof run ledger under harness/battleplan/runs/<date>/ shows integer tokens_in, tokens_out and wall_ms for >= 1 leg, each traceable to a named transcript JSONL",
      "evidence": "receipt"
    },
    {
      "predicate": "negative control: a settled leg with no resolvable transcript renders every token field the literal UNKNOWN and enforced_unit stays turns",
      "evidence": "test"
    },
    {
      "predicate": "tests/test_rails.py: transcript fixture with usage -> integers; fixture without usage -> UNKNOWN; enforced_unit flips to tokens only when a ceiling is set AND tokens were measured",
      "evidence": "test"
    },
    {
      "predicate": "a run with a tiny tokens ceiling halts after settle: status blocked, reason budget, enforced_unit tokens (ledger artifact)",
      "evidence": "receipt"
    },
    {
      "predicate": "-DryRun control log byte-identical to the BP1 baseline (diff file attached, empty)",
      "evidence": "check"
    },
    {
      "predicate": "drift.py unit test on a synthetic bus: one drifting leg -> refocus posted with targets verbatim; two unimproved -> halt posted",
      "evidence": "test"
    },
    {
      "predicate": "rails_exec.json carries the referee tier and `python harness/rails.py resolve referee` prints claude-fable-5 (or the documented reasoning fallback)",
      "evidence": "check"
    }
  ]
}
```

## Constitution (non-negotiable)

- **NEVER**: `git push`, `git merge`, tag, edit `harness/state/drop.json`, flip
  any `ratified` or any leg `state` in a manifest. Those are human words, per act.
- **Unobtainable renders UNKNOWN** — never zero, never an estimate, never a pass.
  A `gui_required` acceptance you cannot measure headless is recorded UNKNOWN.
  A skipped hython probe is UNKNOWN — the hytest shim discipline (skip ≠ pass).
- **Receipts over claims** — every finding carries a file:line, probe path, or
  receipt anchor. No anchor, no claim.
- **Runtime is truth, docs are the referee, model memory is hypothesis.** The
  green-light-that-cannot-report-failure class (silent-empty recall, cook
  success-noop) is what this wave exists to make unshippable — do not add to it.
  Any status you emit is one of SUCCESS | UNAVAILABLE | BLOCKED with a reason;
  an empty payload under SUCCESS is the defect, not a result.
- **Ratified text is untouchable.** `python/synapse/loop/ports.py` §4 parameter
  names, `STATUS` values, `.synapse/contracts/loop-v00.yaml`, `VERSION`,
  `README.md`, `harness/loop/STATE.json`, `harness/memory/**` are owned or
  ratified surfaces. If your goalpost cannot be met without changing one,
  DRAFT the amendment into `harness/battleplan/notes/` and stop that target
  as `blocked` (M3 precedent). Never apply it.
- **Territory:** `python/synapse/loop/pgdrm.py` belongs to the memory board's
  live `mem/m2-pgdrm` branch. Never touch it.
- Named-file commits only on your branch. Never `git add -A`.
- Scope is the mission. Prerequisite work is real work — do it. Unrelated value —
  post a `spawn` proposal, don't chase it.

## The bus (how the team talks — BATTLEPLAN bus, NOT the autorevise bus)

ONE bus command. Always this exact absolute path — NEVER a relative call. A
relative call from your worktree writes a FRAGMENTED bus nobody reads: your
claims become invisible and two agents will edit one file.

1. **Before touching any file in `touches`** — post a claim:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp2 BP2-METER claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py claims bp2`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases. No intra-wave shared seam by design.
   BP2 territory: METER owns harness/; PANELTRUTH owns python/synapse/panel/
   + houdini/scripts/python/synapse_shelf.py; LATENCY is READ-ONLY under
   python/synapse/memory/ (its writes are harness/battleplan/notes|runs and
   its contract); STORE is the only writer under python/synapse/memory/;
   PANELDESIGN (held until Joe's word) owns designsystem/ + manifests/ + qss;
   CRUX is read-only. Consumption VIA THE BUS the moment it posts: PANELDESIGN
   reads PANELTRUTH's profile_diff.json finding; STORE reads LATENCY's bucket
   finding if the bucket is id/lock; the orchestrator reads METER's first
   measured ledger.
2. **Findings** as you go — and the moment an evidence artifact lands, post its
   path so peers consume it live (this is the wave's dynamic handoff):
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp2 BP2-METER finding '{\"claim\": \"...\", \"anchor\": \"file:line-or-artifact-path\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp2 BP2-METER status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam, and poll for peer artifacts your
   mission consumes:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py read bp2 BP2-METER`
5. **Progress** every 5 turns - the on-target signal the orchestrator's drift
   check reads. Cite the target you are on and the evidence path if one exists:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp2 BP2-METER progress '{\"target\": \"T1\", \"evidence_path\": \"<path-or-none>\"}'`
   A `refocus` message addressed to you carries your own mission targets
   verbatim: answer it by naming the target you return to, not with a new idea.
   A `halt` message means rails stopped the wave: commit what is named-file
   clean, write your receipt at observed scope, stop.
   Self-cap: the turn number in your mission note is SELF-REPORTED (a rails
   turn is a leg dispatch, not one of your turns - docs/BATTLEPLAN.md sec.12
   R-3). At 80% of it post a progress message saying `wrap_up`; at 100% commit,
   receipt, stop - partial work stays on your branch for a fresh session.

## Receipt (completion contract)

**COMMIT BEFORE RECEIPT — hard order (CRX0).** The receipt is written LAST,
after your named-file commit exists on your branch. Sequence: (1) commit your
product + notes files (named, never -A); (2) verify `git rev-list --count
<base>..HEAD` >= 1; (3) only then write the receipt, stating the observed HEAD
sha in it. A receipt at ahead:0 asserts commit-state that does not exist.

**THE RECEIPT IS ITS OWN CLOSING COMMIT — the leg commits it, not the operator
(W5H rule).** Writing it into the worktree is not finishing; committing it is.
Full sequence: product commit → verify ahead >= 1 → write the receipt stating
the product HEAD sha → commit the receipt as your closing commit.

Write `harness/notes/receipts/BP2-METER.json` **inside your worktree**:
`{{"leg": "BP2-METER", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn — hold there.
