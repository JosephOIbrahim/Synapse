# BP2-STORE — Store truth: FU-1 Memory.id generated after created_at (repeat deposits no longer collide); M-5 'requested Moneta, served JSONL' probed and made to report BLOCKED/UNAVAILABLE; health line carries requested/active backend, embedder, dim, rows

You are a SYNAPSE BATTLEPLAN wave agent on branch `bp2/store` in worktree
`.claude/worktrees/bp2-store`. Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This
brief is complete; if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "BP2-STORE",
  "name": "Store truth: FU-1 Memory.id generated after created_at (repeat deposits no longer collide); M-5 'requested Moneta, served JSONL' probed and made to report BLOCKED/UNAVAILABLE; health line carries requested/active backend, embedder, dim, rows",
  "band": "BUILD",
  "class": "build",
  "note": "Tier: reasoning. Self-cap: 30 turns (progress every 5; sec.12 R-3). You are the only writer under python/synapse/memory/ this wave - claim it first; BP2-LATENCY reads it and must not claim it. Today's demo shape is repeat-2 identical deposits on a Moneta backend: FU-1 is the small fix (sec.2 call 9) - id after created_at defaults, time-dependent hash, FORMAT UNCHANGED, no migration, backfill unaffected. UUID + content_fingerprint (Sol-review W2) is beta-W2 - do not start it. Constitution territory holds: harness/memory/** and python/synapse/loop/pgdrm.py are not yours.",
  "targets": [
    "T1) FU-1. python/synapse/memory/models.py: generate Memory.id AFTER created_at defaults so the id is f(content, type, created_at) - format unchanged (mem_* prefix and length), existing ids untouched. Invert the tripwire tests/test_moneta_crucible.py::test_duplicate_content_id_collision_is_documented so it now asserts two identical-content deposits at different created_at get DISTINCT ids; keep a test that identical content+type+created_at still dedups (that overwrite is intended). Add a MonetaBackedStore test: after two identical deposits, count() == len(get-all) - the divergence in docs/MONETA_FOLLOWUPS.md FU-1 is gone.",
    "T2) M-5 PROBE. With SYNAPSE_MEMORY_BACKEND=moneta and Moneta made un-importable in-test, the store MUST report BLOCKED or UNAVAILABLE in the health row and in memory tool responses - never a healthy JSONL masquerading as Moneta. If it already does, the receipt cites the file:line; if it does not, fix it inside the existing status vocabulary (SUCCESS | UNAVAILABLE | BLOCKED) with the sec.4 tool surface byte-identical.",
    "T3) HEALTH LINE. The health row carries requested backend, active backend, embedder id, dim, row count (the W1 operator acceptance) if it does not already; cite the line either way.",
    "T4) tests/test_loop_contracts.py must be unchanged and green; the diff adds no third store authority (store.py:1514 and ledger.py:320 remain the two - the honesty contract's rule)."
  ],
  "touches": [
    "python/synapse/memory/models.py",
    "python/synapse/memory/",
    "tests/test_moneta_crucible.py",
    "tests/",
    "harness/battleplan/notes/"
  ],
  "readonly": false,
  "deps": [],
  "crucible_criteria": [
    "no fsync/durability posture change (R-CI0-1 pending)",
    "no UUID migration, no WAL change, no id format change - a legacy mem_* id still round-trips",
    "no run_sleep_pass gating (FU-2 parked)",
    "the sec.4 memory tool surface is byte-identical against master",
    "grep of the branch diff for pgdrm.py, VERSION, README.md, loop-v00.yaml, harness/loop/, harness/memory/ is empty"
  ],
  "spawn_classes": [
    "probe"
  ],
  "source": {
    "doc": "docs/BATTLEPLAN.md",
    "anchor": "2026-09-01 sec.0.1 M-4/M-5, sec.2 call 9, sec.6 BP2-STORE"
  },
  "acceptance": [
    {
      "predicate": "two identical-content deposits at different created_at produce distinct ids; identical content+type+created_at still dedups (both tests green, old tripwire inverted)",
      "evidence": "test"
    },
    {
      "predicate": "MonetaBackedStore: count() == len(get-all) after two identical deposits",
      "evidence": "test"
    },
    {
      "predicate": "SYNAPSE_MEMORY_BACKEND=moneta with Moneta un-importable -> health row and memory tool status BLOCKED/UNAVAILABLE, never healthy JSONL (test), with the file:line cited in the receipt",
      "evidence": "test"
    },
    {
      "predicate": "health line carries requested backend, active backend, embedder id, dim, row count (line cited)",
      "evidence": "check"
    },
    {
      "predicate": "tests/test_loop_contracts.py unchanged and green; `pytest -q` green on the branch",
      "evidence": "test"
    },
    {
      "predicate": "store authorities remain exactly two (store.py:1514, ledger.py:320) - grep attached",
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
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp2 BP2-STORE claim '{\"files\": [\"<paths>\"]}'`
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
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp2 BP2-STORE finding '{\"claim\": \"...\", \"anchor\": \"file:line-or-artifact-path\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp2 BP2-STORE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam, and poll for peer artifacts your
   mission consumes:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py read bp2 BP2-STORE`
5. **Progress** every 5 turns - the on-target signal the orchestrator's drift
   check reads. Cite the target you are on and the evidence path if one exists:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp2 BP2-STORE progress '{\"target\": \"T1\", \"evidence_path\": \"<path-or-none>\"}'`
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

Write `harness/notes/receipts/BP2-STORE.json` **inside your worktree**:
`{{"leg": "BP2-STORE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn — hold there.
