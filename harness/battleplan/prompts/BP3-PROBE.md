# BP3-PROBE — Fixture download + hython run of harness/probes/synapse_blueprint_probes.py (P/B/S, 22 probes) + review doc with D1.1, D2.1-D2.4 verdicts, gate and risk evidence

You are a SYNAPSE BATTLEPLAN wave agent on branch `bp3/probe` in worktree
`.claude/worktrees/bp3-probe`. Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This
brief is complete; if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "BP3-PROBE",
  "band": "TRUTH",
  "class": "truth",
  "tier": "reasoning",
  "name": "Fixture download + hython run of harness/probes/synapse_blueprint_probes.py (P/B/S, 22 probes) + review doc with D1.1, D2.1-D2.4 verdicts, gate and risk evidence",
  "note": "Tier: reasoning. Self-cap: 30 turns (progress every 5). Blocked until BP3-RECON's finding (hython, pref_dir, fixtures_dir, reviews_dir). NEVER edit harness/probes/synapse_blueprint_probes.py to make a probe pass - a wrong probe is a finding on the bus, the defect goes in the review doc. A raising probe is BLOCKED with traceback and the run continues (the script does this). gui_required rows (B-2 handedness, B-9 visual, viewport display-purpose default) are UNKNOWN headless. Rule D-1: you report evidence found/not found for gates G-1..G-4; you never write OPEN. Known environment facts (memory, verify before relying): GUI Houdini is 22.0.400, hython may be 22.0.417 - pin whichever hython reports; the live H22 prefs dir is C:\\Users\\User\\OneDrive\\Documents\\houdini22.0 (OneDrive known-folder redirect) - hython launched from an agent lane has looked in the old Documents path before; set HOUDINI_USER_PREF_DIR explicitly. Long hython runs: detach and poll, never foreground-wait past 4 minutes.",
  "targets": [
    "T1) Fixture: download narrow_european_cobblestone_lane_500k.ply, _collider.glb, _pano.png from https://wlt-ai-cdn.art/example_exports/narrow_european_cobblestone_lane/ into the reconciled fixtures dir under a worldlabs/narrow_european_cobblestone_lane/ folder; record SHA256 + byte size per file. Do not fetch 2m.ply or hq.glb until B-1 passes on 500k. Fixture files are NOT committed if the repo .gitignore excludes binaries - if they are ignored, the review doc records their absolute paths + hashes and that is the receipt.",
    "T2) Run, detached and polled (log to file), with HOUDINI_USER_PREF_DIR set from RECON: `hython harness\\probes\\synapse_blueprint_probes.py --ply <ply> --glb <glb> --out harness\\notes\\h22wl\\bp3_probes --save-hip`; stdout verbatim to harness/notes/h22wl/bp3_probes/stdout.txt. Wall budget 30 min recorded. Also run `husk --help | findstr -- --pass` and record the line (P-7 shell check).",
    "T3) Review doc in the reconciled reviews dir: `bp3-h22-worldlabs-probes-<yyyy-mm-dd>.md` - build pin (P-0 line), fixture hashes, per-probe status table (22 rows RAN|BLOCKED + seconds), verbatim key outputs (or stdout path + line ranges), done-condition rows D1.1, D2.1, D2.2, D2.3, D2.4 with verdict pass|fail|UNKNOWN + anchor (file:line in stdout.txt), gate evidence G-1..G-4 (found / not found + anchor), risk status R-1..R-4 (triggered / clear / unknown + anchor), blueprint sec.8 open questions 1-5 answered (anchor) or unanswered (blocked by). The B-6 exported .usdc size and B-7 EXR result (or BLOCKED traceback) are quoted verbatim.",
    "T4) Post a bus finding the moment stdout.txt lands: {\"claim\": \"bp3 probes ran: <n> RAN / <m> BLOCKED\", \"anchor\": \"harness/notes/h22wl/bp3_probes/stdout.txt\"} and a second finding with the review doc path. CORPUS and STUBS consume these live."
  ],
  "touches": [
    "harness/notes/h22wl/",
    "docs/reviews/bp3-h22-worldlabs-probes-*.md",
    "fixtures/worldlabs/"
  ],
  "readonly": false,
  "deps": [
    "BP3-RECON"
  ],
  "crucible_criteria": [
    "the crucible re-runs the probe script itself in a fresh checkout with its own out dir and diffs probe_results.json statuses against the builder's",
    "`git diff master..HEAD -- harness/probes/` is empty (no probe edits)",
    "fixture SHA256s recomputed by the crucible match the review doc",
    "a leg with any UNKNOWN acceptance is at best SOUND-WITH-NITS, never SOUND"
  ],
  "spawn_classes": [],
  "source": {
    "doc": "docs/intake/blueprint-h22-worldlabs-intent.md",
    "anchor": "v0.3 sec.6 steps 3-5, 7; sec.2.6 fixtures; sec.2.8 D2.1-D2.4; sec.9 gates; sec.10 risks"
  },
  "acceptance": [
    {
      "predicate": "stdout.txt exists and its first probe block is P-0 with a hou.applicationVersionString() line",
      "evidence": "probe"
    },
    {
      "predicate": "probe_results.json has 22 entries, each RAN or BLOCKED, with seconds on RAN rows and a total wall time line in stdout",
      "evidence": "check"
    },
    {
      "predicate": "review doc has D1.1 and D2.1-D2.4 rows with verdict + stdout.txt anchor; gui_required rows are UNKNOWN",
      "evidence": "receipt"
    },
    {
      "predicate": "B-6 exported b6_wl_component.usdc exists with size printed, OR B-6 is BLOCKED with a traceback quoted in the review doc",
      "evidence": "probe"
    },
    {
      "predicate": "SHA256 + bytes recorded for all three fixture files",
      "evidence": "check"
    },
    {
      "predicate": "B-2 handedness (lane not mirrored after the Y/Z flip) confirmed in the viewer",
      "evidence": "gui_probe",
      "gui_required": true
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
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp3 BP3-PROBE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py claims bp3`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases. No intra-wave shared seam by design.
   Territory for THIS wave: each mission's `touches` is its writable surface and its `note` names ownership; anything outside your `touches` is read-only to you. Consumption is VIA THE BUS the moment a peer posts an artifact path.
2. **Findings** as you go — and the moment an evidence artifact lands, post its
   path so peers consume it live (this is the wave's dynamic handoff):
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp3 BP3-PROBE finding '{\"claim\": \"...\", \"anchor\": \"file:line-or-artifact-path\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp3 BP3-PROBE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam, and poll for peer artifacts your
   mission consumes:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py read bp3 BP3-PROBE`
5. **Progress** every 5 turns - the on-target signal the orchestrator's drift
   check reads. Cite the target you are on and the evidence path if one exists:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp3 BP3-PROBE progress '{\"target\": \"T1\", \"evidence_path\": \"<path-or-none>\"}'`
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

Write `harness/notes/receipts/BP3-PROBE.json` **inside your worktree**:
`{{"leg": "BP3-PROBE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn — hold there.
