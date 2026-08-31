# BP1-RAILS — Harness budget rails - per-run cap with hard stop, spend ledger printed every run, swappable execution seam; a capped Synapse-revision run completes and its ledger is a receipt

You are a SYNAPSE BATTLEPLAN wave agent on branch `bp1/rails` in worktree
`.claude/worktrees/bp1-rails`. Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This
brief is complete; if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "BP1-RAILS",
  "name": "Harness budget rails - per-run cap with hard stop, spend ledger printed every run, swappable execution seam; a capped Synapse-revision run completes and its ledger is a receipt",
  "band": "BUILD",
  "class": "build",
  "note": "The demo roadmap's P1 - the multiplier. Reuse before build: the memory board already keeps a spawn ledger with real subagent_tokens (harness/memory/STATE.json spawn_ledger), harness/verify/token_ceiling.json exists, .synapse/harness.py has --budget, harness/notes/econ_*.py measured real burn. Extend, don't duplicate. Parallel-safe with BP1-TRIAGE by design (harness/ only).",
  "targets": [
    "1) Survey first, in a bus finding: what each existing meter measures (token_ceiling.json, memory STATE spawn_cap/spawn_ledger, econ_*.py, orchestrate.ps1 budget handling, .synapse/harness.py --budget). Build only the gap.",
    "2) harness/rails.py: per-run cap in the unit the runtime actually reports (tokens where measurable, agent-turns/legs otherwise - a field the runtime cannot measure renders UNKNOWN and the cap falls back to the measurable unit, NEVER to unlimited); hard stop (a run past cap halts and writes a receipt with status blocked, reason budget - never a silent continue); spend ledger harness/battleplan/runs/<date>/ledger_<run>.json printed at the end of EVERY run: leg, model, tokens_in, tokens_out (or UNKNOWN per field), wall_ms, cap, remaining.",
    "3) Wire the cap into the orchestrator ADDITIVELY: a -Budget parameter on harness/orchestrate.ps1, or a rails-aware wrapper harness/orchestrate_capped.ps1 if orchestrate.ps1's shape must not change for the other live boards. Existing invocations without -Budget behave byte-for-byte as before.",
    "4) Execution seam: harness/rails_exec.json - a lookup table {tier: mechanical|reasoning -> model string}; mechanical defaults to the cheapest available Claude model string, reasoning to claude-opus-4-8. The seam is a lookup so a local engine (harness/rope/exec_ollama.py already exists) slots in later with no code change. Design note harness/battleplan/notes/RAILS_SEAM.md. Do NOT build the local engine.",
    "5) Prove it: one capped run of a trivial leg (a -DryRun control manifest is acceptable where a real leg would spend real tokens) completes under cap and emits the ledger; one run with a deliberately tiny cap halts with blocked:budget. Both artifacts land under harness/battleplan/runs/<date>/.",
    "6) tests/test_rails.py: cap arithmetic, UNKNOWN propagation, hard stop. Pure Python, stock pytest, no hou."
  ],
  "touches": [
    "harness/rails.py",
    "harness/rails_exec.json",
    "harness/orchestrate.ps1",
    "harness/battleplan/notes/",
    "harness/battleplan/runs/",
    "tests/test_rails.py"
  ],
  "readonly": false,
  "deps": [],
  "crucible_criteria": [
    "no ledger field is an estimate - each is measured or the literal UNKNOWN",
    "the hard stop is exercised in an artifact, not described in prose",
    "orchestrate.ps1 changes are additive: the BP1 -DryRun control log is identical before and after",
    "the execution seam is a lookup table, not a second orchestrator"
  ],
  "spawn_classes": [
    "probe",
    "test"
  ],
  "source": {
    "doc": "docs/BATTLEPLAN.md",
    "anchor": "sec.5 harness-budget-rails.yaml - demo first principle #1: Synapse runs without eating tokens"
  },
  "acceptance": [
    {
      "predicate": "a capped run completes and harness/battleplan/runs/<date>/ledger_*.json exists with leg, model, cap, spent-or-UNKNOWN per field, remaining",
      "evidence": "probe"
    },
    {
      "predicate": "a run whose cap is below its spend halts; its receipt status is blocked with reason budget",
      "evidence": "test"
    },
    {
      "predicate": "orchestrate.ps1 invoked without -Budget produces identical -DryRun control output to the pre-change baseline (diff attached)",
      "evidence": "check"
    },
    {
      "predicate": "tests/test_rails.py passes under stock pytest",
      "evidence": "test"
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
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp1 BP1-RAILS claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py claims bp1`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases. No intra-wave shared seam by design:
   TRIAGE is read-only, RAILS owns harness/, HONESTY owns the recall path.
   HONESTY consumes TRIAGE's bucket finding VIA THE BUS the moment it posts.
2. **Findings** as you go — and the moment an evidence artifact lands, post its
   path so peers consume it live (this is the wave's dynamic handoff):
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp1 BP1-RAILS finding '{\"claim\": \"...\", \"anchor\": \"file:line-or-artifact-path\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp1 BP1-RAILS status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam, and poll for peer artifacts your
   mission consumes:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py read bp1 BP1-RAILS`

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

Write `harness/notes/receipts/BP1-RAILS.json` **inside your worktree**:
`{{"leg": "BP1-RAILS", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn — hold there.
