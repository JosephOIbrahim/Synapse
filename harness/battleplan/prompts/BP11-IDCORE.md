# BP11-IDCORE — Identify core: python/synapse/identify (facts, library, compose, apply) - zero-token bubbles from exact sources, one undo group, artist text never lost, never on disk

You are a SYNAPSE BATTLEPLAN wave agent on branch `bp11/idcore` in worktree
`.claude/worktrees/bp11-idcore`. Model: resolved per mission tier by harness/rails_exec.json (mechanical Haiku 4.5 / reasoning Opus 4.8 / referee Fable 5.1), dispatched by harness/orchestrate.ps1. This
brief is complete; if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "BP11-IDCORE",
  "band": "BUILD",
  "class": "build",
  "tier": "auto",
  "team": {
    "max_subagents": 0,
    "subagent_tier": "mechanical"
  },
  "readonly": false,
  "deps": [],
  "name": "Identify core: python/synapse/identify (facts, library, compose, apply) - zero-token bubbles from exact sources, one undo group, artist text never lost, never on disk",
  "note": "START FROM YOUR CONTEXT PACKET C:\\Users\\User\\SYNAPSE\\.token-saver\\bp11\\BP11-IDCORE.packet.md - the exact code windows the seat already located for your targets (token-saver). Search beyond it only for what it lacks, and list what it lacked in the receipt under packet_gaps; that feedback tunes the next wave's packets. Self-cap: 30 turns (progress every 5). Permission fence: scoped `git add` + `git commit` only; push/merge/checkout/reset denied; use `cd <path> && git status --short`, never `git -C`. Commit code BEFORE the receipt; the receipt is your final write. Budget discipline: run /token-saver first and keep to it - Select-String / grep for symbols, read 40-line windows around cited lines, never whole files. The source docs are untracked on master, so read them by absolute path under C:\\Users\\User\\SYNAPSE\\harness\\battleplan\\notes (IDENTIFY_BLUEPRINT.md, BP11_CTO_PLAN.md): ONCE in full at the start, then only grep them. Houdini GUI is NOT available to you: anything that needs a live panel is UNKNOWN, never a pass. hython IS available at `C:\\Program Files\\Side Effects Software\\Houdini 22.0.400\\bin\\hython.exe` (22.0.400) for headless gates. Minimal diff: touch only the files in `touches`. House rule: no number enters a document without a producer path beside it. Every UNKNOWN stays UNKNOWN - never a pass, never a 0. Write text files as UTF-8 through Python (pathlib.write_text(..., encoding='utf-8')), never through PowerShell default encodings (the BP10 SCAFFOLD mojibake came from a cp1252 round trip). IDENTIFY_BLUEPRINT.md sections 1-4 are the contract; section 3's nine rules are what CRUX re-verifies. M0 probe scripts (read-only reference, port what you need into scripts/probe_identify.py): C:\\Users\\User\\Downloads\\synapse_identify_probe.py, _probe2.py, _probe3.py, _probe4.py. Reuse, don't fork: selection facts come from synapse.server.introspection.inspect_selection with the call pattern in panel/selection_inspection.py:68-80 (run_on_main, timeout=3.0, record_stall=False, record_wait=False, a label). The library reader is python/synapse/cognitive/tools/sidefx_library.py: query-only, never build or download. If it lacks an exact help-path lookup, add ONE read-only function there and test it; a query_library search result is never a node's summary. The Selection Inspector stays read-only: add nothing to it in this leg. Tool-output discipline (token-saver): run pytest -q --tb=line -p no:cacheprovider on the files you touch plus the named pins, never the whole suite unless a row demands it; pipe long output through Select-Object -Last 40 or Select-String; never print a whole log, diff or JSON you can grep. Receipt evidence cells stay one or two lines each.",
  "targets": [
    "T1) python/synapse/identify/compose.py: a pure function (no hou, no Qt) from facts to bubble lines per blueprint sec. 2 - What / Here / State, at most 3 lines, a width constant, the parm filter (folders, folder sets, separators, labels, hidden parms, ramp\\d+(pos|value|interp) internals), labels not names, 3 significant digits, the (expr) marker, '...' truncation, and '- not in library' for unknown types.",
    "T2) python/synapse/identify/library.py: exact lookup from node type to summary by the help path derived from defaultHelpUrl() including versioned types (operator:Sop/polybevel?version=3.0); HDA embedded help first sentence; returns (text, source) or (None, 'unknown'); never searches.",
    "T3) python/synapse/identify/facts.py: per-node facts from inspect_selection(include_parameters=True, node_paths=...) plus the extras it lacks, read in one short main-thread read: help url, parm labels, default and expression flags, errors, warnings, bypass, and LOP last-modified prims if the 22.0.400 API has them (probe it; UNKNOWN otherwise).",
    "T4) python/synapse/identify/apply.py: the only writer - ASCII sentinel block '~ identify ~' appended below any artist comment and stripped from the sentinel down; a per-session registry of the prior DisplayComment flag keyed by node sessionId; one hou.undos.group('SYNAPSE Identify') per show and per clear; BeforeSave strip and AfterSave re-apply with undo disabled; a 60-bubble cap with the flash line 'Identify: N of M nodes'; idempotent toggle; orphan blocks (no registry entry) removed on clear.",
    "T5) tests/test_identify_compose.py, tests/test_identify_library.py, tests/test_identify_apply.py (fake hou objects), and scripts/probe_identify.py (hython: build the M0 seven-node chain in a temp .hip, show, save, reopen, assert zero sentinels, print hou.applicationVersionString())."
  ],
  "touches": [
    "python/synapse/identify/",
    "python/synapse/cognitive/tools/sidefx_library.py",
    "tests/test_identify_compose.py",
    "tests/test_identify_library.py",
    "tests/test_identify_apply.py",
    "scripts/probe_identify.py"
  ],
  "acceptance": [
    {
      "predicate": "pytest tests/test_identify_compose.py tests/test_identify_library.py tests/test_identify_apply.py passes on system Python without hou",
      "evidence": "test"
    },
    {
      "predicate": "compose() on the M0 PolyBevel facts (offset 0.07 plus five changed ramp internals) yields exactly one Here entry, shown by its label, and no ramp internal",
      "evidence": "test"
    },
    {
      "predicate": "an artist comment is byte-identical after show then clear, after show + BeforeSave strip + AfterSave re-apply + clear, and when the artist comment quotes the sentinel inside prose",
      "evidence": "test"
    },
    {
      "predicate": "library returns 'unknown' for a type with no exact help-path row, and swapping the exact lookup for query_library search makes a test fail (mutation shown in the receipt)",
      "evidence": "test"
    },
    {
      "predicate": "hython scripts/probe_identify.py on 22.0.400 prints the version, shows 7 bubbles on the M0 chain, and the saved .hip reopened has zero sentinel lines and one undo group per show",
      "evidence": "check"
    },
    {
      "predicate": "the main-thread apply for 60 nodes is timed in hython and the ms figure is in the receipt against the 100 ms starting target (a miss is a finding, never hidden)",
      "evidence": "check"
    },
    {
      "predicate": "nothing under python/synapse/identify imports harness/ or opens a network connection, and only apply.py calls setComment, setGenericFlag or hou.undos (grep count lines in the receipt)",
      "evidence": "check"
    }
  ],
  "crucible_criteria": [
    "the crucible trusts no builder's proved_it_bites - it authors its own mutations",
    "every verdict row carries the crucible's own anchor",
    "a leg with any UNKNOWN acceptance is at best SOUND-WITH-NITS, never SOUND",
    "the crucible flips no contract feature and edits no product file",
    "the crucible writes its own artist comment that quotes the sentinel in prose and proves show + clear leaves it byte-identical",
    "the crucible disables the BeforeSave strip and proves the save row bites",
    "the crucible re-runs scripts/probe_identify.py in hython itself"
  ],
  "source": {
    "doc": "harness/battleplan/notes/IDENTIFY_BLUEPRINT.md",
    "anchor": "sec. 2 The bubble; sec. 3 Rules; sec. 4 Where it lives"
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
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp11 BP11-IDCORE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py claims bp11`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases. No intra-wave shared seam by design.
   Territory for THIS wave: each mission's `touches` is its writable surface and its `note` names ownership; anything outside your `touches` is read-only to you. Consumption is VIA THE BUS the moment a peer posts an artifact path.
2. **Findings** as you go — and the moment an evidence artifact lands, post its
   path so peers consume it live (this is the wave's dynamic handoff):
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp11 BP11-IDCORE finding '{\"claim\": \"...\", \"anchor\": \"file:line-or-artifact-path\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp11 BP11-IDCORE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam, and poll for peer artifacts your
   mission consumes:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py read bp11 BP11-IDCORE`
5. **Progress** every 5 turns - the on-target signal the orchestrator's drift
   check reads. Cite the target you are on and the evidence path if one exists:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp11 BP11-IDCORE progress '{\"target\": \"T1\", \"evidence_path\": \"<path-or-none>\"}'`
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

Write `harness/notes/receipts/BP11-IDCORE.json` **inside your worktree**:
`{{"leg": "BP11-IDCORE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn — hold there.
