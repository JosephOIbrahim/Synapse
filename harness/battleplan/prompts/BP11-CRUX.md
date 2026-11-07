# BP11-CRUX — CRUX: adversarial re-verification of the five BP11 builder legs, one JEV-SCREEN line per leg

You are a SYNAPSE BATTLEPLAN wave agent on branch `bp11/crux` in worktree
`.claude/worktrees/bp11-crux`. Model: resolved per mission tier by harness/rails_exec.json (mechanical Haiku 4.5 / reasoning Opus 4.8 / referee Fable 5.1), dispatched by harness/orchestrate.ps1. This
brief is complete; if any part reads truncated, STOP and say so.

## JEV screen pre-read

screen BP11-FIXFWD: REFEREE - full read; weak rows [1, 3]; crux_need 0.52
screen BP11-FIXFWD2: REFEREE - full read; weak rows [0, 1]
screen BP11-IDCORE: REFEREE - full read; weak rows [0, 1, 2, 3, 4, 5, 6]; crux_need 0.99

## Mission (validated work order)

```json
{
  "id": "BP11-CRUX",
  "band": "TRUST",
  "class": "crucible",
  "tier": "referee",
  "readonly": true,
  "deps": [
    "BP11-FIXFWD",
    "BP11-FIXFWD2",
    "BP11-IDCORE",
    "BP11-IDSURF",
    "BP11-SALIENCE",
    "BP11-HARDEN"
  ],
  "name": "CRUX: adversarial re-verification of the five BP11 builder legs, one JEV-SCREEN line per leg",
  "note": "START FROM YOUR CONTEXT PACKET C:\\Users\\User\\SYNAPSE\\.token-saver\\bp11\\BP11-CRUX.packet.md - the exact code windows the seat already located for your targets (token-saver). Search beyond it only for what it lacks, and list what it lacked in the receipt under packet_gaps; that feedback tunes the next wave's packets. Self-cap: 30 turns (progress every 5). Permission fence: scoped `git add` + `git commit` only; push/merge/checkout/reset denied; use `cd <path> && git status --short`, never `git -C`. Commit code BEFORE the receipt; the receipt is your final write. Budget discipline: run /token-saver first and keep to it - Select-String / grep for symbols, read 40-line windows around cited lines, never whole files. The source docs are untracked on master, so read them by absolute path under C:\\Users\\User\\SYNAPSE\\harness\\battleplan\\notes (IDENTIFY_BLUEPRINT.md, BP11_CTO_PLAN.md): ONCE in full at the start, then only grep them. Houdini GUI is NOT available to you: anything that needs a live panel is UNKNOWN, never a pass. hython IS available at `C:\\Program Files\\Side Effects Software\\Houdini 22.0.400\\bin\\hython.exe` (22.0.400) for headless gates. Minimal diff: touch only the files in `touches`. House rule: no number enters a document without a producer path beside it. Every UNKNOWN stays UNKNOWN - never a pass, never a 0. Write text files as UTF-8 through Python (pathlib.write_text(..., encoding='utf-8')), never through PowerShell default encodings (the BP10 SCAFFOLD mojibake came from a cp1252 round trip). Read-only on product files. Re-run every row in a fresh `git clone --shared` of each leg branch; bp11/harden carries the whole Identify chain. Every Identify rule in IDENTIFY_BLUEPRINT.md sec. 3 gets at least one mutation of your own. gui_probe rows stay UNKNOWN: the seat closes them by computer use after the wave. Tool-output discipline (token-saver): run pytest -q --tb=line -p no:cacheprovider on the files you touch plus the named pins, never the whole suite unless a row demands it; pipe long output through Select-Object -Last 40 or Select-String; never print a whole log, diff or JSON you can grep. Receipt evidence cells stay one or two lines each.",
  "targets": [
    "T1) harness/battleplan/notes/BP11-CRUX_verdicts.md: SOUND / SOUND-WITH-NITS / BROKEN per leg, every row with the crucible's own anchor and a SCREEN-vs-CRUX agreement line.",
    "T2) harness/battleplan/notes/BP11-CRUX_mutations.json: every mutation with its target row and outcome."
  ],
  "touches": [
    "harness/battleplan/notes/BP11-CRUX_verdicts.md",
    "harness/battleplan/notes/BP11-CRUX_mutations.json"
  ],
  "acceptance": [
    {
      "predicate": "every builder acceptance row has a CRUX verdict with a crucible anchor",
      "evidence": "check"
    },
    {
      "predicate": "the mutation record holds at least one crucible-authored mutation per Identify rule 1-9, each labelled bite, survived or crash",
      "evidence": "check"
    },
    {
      "predicate": "each leg's verdict carries its SCREEN-vs-CRUX agreement line",
      "evidence": "check"
    },
    {
      "predicate": "gui_probe rows are UNKNOWN in the verdicts, never pass",
      "evidence": "check"
    }
  ],
  "crucible_criteria": [
    "the crucible flips no contract feature and edits no product file",
    "a leg with any UNKNOWN acceptance is at best SOUND-WITH-NITS, never SOUND",
    "any hash of a committed file is taken over git blob bytes (`git cat-file blob`), never a Windows checkout"
  ],
  "source": {
    "doc": "harness/battleplan/notes/IDENTIFY_BLUEPRINT.md",
    "anchor": "sec. 3 Rules (the crucible re-checks each one)"
  }
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
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp11 BP11-CRUX claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py claims bp11`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases. No intra-wave shared seam by design.
   Territory for THIS wave: each mission's `touches` is its writable surface and its `note` names ownership; anything outside your `touches` is read-only to you. Consumption is VIA THE BUS the moment a peer posts an artifact path.
2. **Findings** as you go — and the moment an evidence artifact lands, post its
   path so peers consume it live (this is the wave's dynamic handoff):
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp11 BP11-CRUX finding '{\"claim\": \"...\", \"anchor\": \"file:line-or-artifact-path\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp11 BP11-CRUX status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam, and poll for peer artifacts your
   mission consumes:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py read bp11 BP11-CRUX`
5. **Progress** every 5 turns - the on-target signal the orchestrator's drift
   check reads. Cite the target you are on and the evidence path if one exists:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp11 BP11-CRUX progress '{\"target\": \"T1\", \"evidence_path\": \"<path-or-none>\"}'`
   A `refocus` message addressed to you carries your own mission targets
   verbatim: answer it by naming the target you return to, not with a new idea.
   A `halt` message means rails stopped the wave: commit what is named-file
   clean, write your receipt at observed scope, stop.
   How the drift check reads you (`harness/battleplan/drift.py`, run once per poll
   when the wave is budgeted, zero model calls): it takes your last 5 `progress`
   messages and computes the fraction that cite a `T<n>` target or an acceptance
   index. Below 0.6 you have DRIFTED, and the orchestrator posts you a `refocus`
   with your targets verbatim; two refocus with the ratio still under 0.6 (no
   improvement) escalate to a `halt`. The defence is simple: tag every `progress`
   with the `"target"` you are actually on — an off-target or untagged progress
   message counts against your ratio.
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

Write `harness/notes/receipts/BP11-CRUX.json` **inside your worktree**:
`{{"leg": "BP11-CRUX", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn — hold there.

**Shell rule (seat, 13:05).** Keep `#` comments out of every quoted shell argument, including `python -c` and `bash -c`. Claude Code stops for a manual prompt on them, and no one is at the keyboard to answer it. For any script longer than three lines, Write it to `.scratch/<name>.py` in your worktree (gitignored and allowed) and run that file with python. Never commit anything under `.scratch/`.
