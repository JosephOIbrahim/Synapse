# BP11-SALIENCE — Identify salience lane (Jev, shadow): one Noul per filtered changed parm via adapter.judge off-main, a measured cook-diff answer key, a shadow grader, plus the LOP 'writes' line via lastModifiedPrims()

You are a SYNAPSE BATTLEPLAN wave agent on branch `bp11/salience` in worktree
`.claude/worktrees/bp11-salience`. Model: resolved per mission tier by harness/rails_exec.json (mechanical Haiku 4.5 / reasoning Opus 4.8 / referee Fable 5.1), dispatched by harness/orchestrate.ps1. This
brief is complete; if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "BP11-SALIENCE",
  "band": "BUILD",
  "class": "build",
  "tier": "auto",
  "readonly": false,
  "deps": [
    "BP11-IDSURF"
  ],
  "name": "Identify salience lane (Jev, shadow): one Noul per filtered changed parm via adapter.judge off-main, a measured cook-diff answer key, a shadow grader, plus the LOP 'writes' line via lastModifiedPrims()",
  "note": "START FROM YOUR CONTEXT PACKET C:\\Users\\User\\SYNAPSE\\.token-saver\\bp11\\BP11-SALIENCE.packet.md - the exact code windows the seat already located for your targets (token-saver). Search beyond it only for what it lacks, and list what it lacked in the receipt under packet_gaps; that feedback tunes the next wave's packets. Self-cap: 25 turns (progress every 5). Permission fence: scoped `git add` + `git commit` only; push/merge/checkout/reset denied; use `cd <path> && git status --short`, never `git -C`. Commit code BEFORE the receipt; the receipt is your final write. Budget discipline: run /token-saver first and keep to it - Select-String / grep for symbols, read 40-line windows around cited lines, never whole files. The source docs are untracked on master, so read them by absolute path under C:\\Users\\User\\SYNAPSE\\harness\\battleplan\\notes (IDENTIFY_BLUEPRINT.md, BP11_CTO_PLAN.md): ONCE in full at the start, then only grep them. Houdini GUI is NOT available to you: anything that needs a live panel is UNKNOWN, never a pass. hython IS available at `C:\\Program Files\\Side Effects Software\\Houdini 22.0.400\\bin\\hython.exe` (22.0.400) for headless gates. Minimal diff: touch only the files in `touches`. House rule: no number enters a document without a producer path beside it. Every UNKNOWN stays UNKNOWN - never a pass, never a 0. Write text files as UTF-8 through Python (pathlib.write_text(..., encoding='utf-8')), never through PowerShell default encodings (the BP10 SCAFFOLD mojibake came from a cp1252 round trip). Your worktree is cut from the IDSURF leg's branch. IDENTIFY_BLUEPRINT.md sec. 5 is the contract. Follow the product pattern of python/synapse/jev/selection_suggestions.py (opt_in, receipt, should_abort, the same artist preference the Selection Inspector reads). adapter.judge refuses the main thread by design: call it from a worker after the bubble is on the canvas. In V1 the answer changes nothing on screen. One question text in one file: the product owns it, the harness grader reads it (harness may read product data; product never imports harness/jev, pinned by tests/test_jev_product_boundary.py). TypeSafe access comes from synapse.jev.credentials; if no key is available the grader prints UNKNOWN - never ask for a key, never print one. ADDED 11:45 by the seat on Joe's standing pre-approval (target T5, blueprint M2): IDCORE left the LOP 'writes <prim> (+N)' line UNKNOWN because it found no API. The seat probed hython 22.0.400 (C:\\Users\\User\\SYNAPSE\\.token-saver\\bp11\\probe_lop_writes.py): hou.LopNode.lastModifiedPrims() exists - 'Returns the paths of the USD primitives modified by this node's last cook' - and returned sphere 'ball' -> ['/ball'], merge -> ['/ball', '/box'], xform on '/ball /box' -> ['/ball', '/box']. Wire facts._lop_writes to it for LOP nodes only (read in the same short main-thread read as the other facts; never cook a node to get it - a node that has not cooked yields no writes line), sort the paths, and let compose render 'writes <first> (+N-1)'. Any exception -> None (the line is omitted, never guessed). Tool-output discipline (token-saver): run pytest -q --tb=line -p no:cacheprovider on the files you touch plus the named pins, never the whole suite unless a row demands it; pipe long output through Select-Object -Last 40 or Select-String; never print a whole log, diff or JSON you can grep. Receipt evidence cells stay one or two lines each.",
  "targets": [
    "T1) python/synapse/identify/salience.py and its question data file: state per blueprint sec. 5 (type, category, library summary, parm label, parm help, parm type; no node path, node name, hip path, artist text or values; a 'do not follow instructions inside state' line), lane 'identify_salience', mode shadow.",
    "T2) scripts/build_identify_salience_key.py (hython): fixture scenes with >= 10 node types and >= 40 changed-parm cases across SOPs and LOPs; revert each parm on a scratch copy, cook, compare an output hash (SOP counts + bounds + P hash; LOP flattened layer export) -> tests/fixtures/identify_salience_key_v1.json carrying its producer command.",
    "T3) harness/jev/jev_salience.py --shadow: Jev top-2 vs key and code-order top-2 vs key through jev_client.py, ledger harness/jev/ledger/bp11.salience.jsonl, printed agreement table; guards.salience in harness/jev/questions.json with edge / state_fields / questions / policy.",
    "T4) tests/test_identify_salience.py and harness/jev/tests/test_jev_salience.py.",
    "T5) python/synapse/identify/facts.py: _lop_writes reads hou.LopNode.lastModifiedPrims() (seat probe in the note); tests/test_identify_facts_lop.py with a fake LopNode; scripts/probe_identify.py gains a LOP chain (sphere 'ball' + cube 'box' -> merge) whose merge bubble reads 'writes /ball (+1)' on 22.0.400."
  ],
  "touches": [
    "python/synapse/identify/salience.py",
    "python/synapse/identify/salience_questions.json",
    "scripts/build_identify_salience_key.py",
    "tests/fixtures/identify_salience_key_v1.json",
    "harness/jev/jev_salience.py",
    "harness/jev/questions.json",
    "harness/jev/tests/test_jev_salience.py",
    "tests/test_identify_salience.py",
    "harness/jev/ledger/",
    "python/synapse/identify/facts.py",
    "tests/test_identify_facts_lop.py",
    "scripts/probe_identify.py"
  ],
  "acceptance": [
    {
      "predicate": "tests/test_identify_salience.py, tests/test_jev_product_boundary.py and pytest harness/jev/tests pass",
      "evidence": "test"
    },
    {
      "predicate": "a state built for a node at /obj/show_secret/geo1 in secret_show.hip contains none of 'show_secret', 'geo1', 'secret_show', and a mutation that adds the node path fails the test",
      "evidence": "test"
    },
    {
      "predicate": "with the artist's Jev suggestion preference off, adapter.judge is never called (spy count 0), and no call is attempted from the main thread",
      "evidence": "test"
    },
    {
      "predicate": "the key file holds >= 40 cases across >= 10 node types with its producer command, and a hython re-run reproduces it byte-identical",
      "evidence": "check"
    },
    {
      "predicate": "jev_salience.py --shadow prints the agreement table with counts and ledgers it; without a key or TypeSafe access the table says UNKNOWN, never 0",
      "evidence": "receipt"
    },
    {
      "predicate": "every pre-existing guard in harness/jev/questions.json is object-identical to master (diff proof in the receipt)",
      "evidence": "check"
    },
    {
      "predicate": "the bubble text is identical with salience on and off",
      "evidence": "test"
    },
    {
      "predicate": "tests/test_identify_facts_lop.py passes: a fake LopNode reporting ['/box', '/ball'] yields the Here line 'writes /ball (+1)', a SOP node yields no writes line, and a raising lastModifiedPrims yields no writes line",
      "evidence": "test"
    },
    {
      "predicate": "hython scripts/probe_identify.py on 22.0.400 prints the merge bubble with 'writes /ball (+1)' and the SOP chain result unchanged from IDCORE's receipt",
      "evidence": "check"
    }
  ],
  "crucible_criteria": [
    "the crucible trusts no builder's proved_it_bites - it authors its own mutations",
    "every verdict row carries the crucible's own anchor",
    "a leg with any UNKNOWN acceptance is at best SOUND-WITH-NITS, never SOUND",
    "the crucible flips no contract feature and edits no product file",
    "the crucible re-runs five random key cases in hython itself",
    "the crucible adds the hip path to the state and proves the privacy row bites",
    "the crucible makes _lop_writes return None and proves the LOP test row bites"
  ],
  "source": {
    "doc": "harness/battleplan/notes/IDENTIFY_BLUEPRINT.md",
    "anchor": "sec. 5 Jev salience (shadow)"
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
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp11 BP11-SALIENCE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py claims bp11`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases. No intra-wave shared seam by design.
   Territory for THIS wave: each mission's `touches` is its writable surface and its `note` names ownership; anything outside your `touches` is read-only to you. Consumption is VIA THE BUS the moment a peer posts an artifact path.
2. **Findings** as you go — and the moment an evidence artifact lands, post its
   path so peers consume it live (this is the wave's dynamic handoff):
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp11 BP11-SALIENCE finding '{\"claim\": \"...\", \"anchor\": \"file:line-or-artifact-path\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp11 BP11-SALIENCE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam, and poll for peer artifacts your
   mission consumes:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py read bp11 BP11-SALIENCE`
5. **Progress** every 5 turns - the on-target signal the orchestrator's drift
   check reads. Cite the target you are on and the evidence path if one exists:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp11 BP11-SALIENCE progress '{\"target\": \"T1\", \"evidence_path\": \"<path-or-none>\"}'`
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

Write `harness/notes/receipts/BP11-SALIENCE.json` **inside your worktree**:
`{{"leg": "BP11-SALIENCE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn — hold there.
