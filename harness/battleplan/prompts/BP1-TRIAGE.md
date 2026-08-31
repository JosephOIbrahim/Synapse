# BP1-TRIAGE — Gate 0 - silent-recall triage: four-gate probe (env -> plugin -> layer -> recall) under hython via the hytest shim; names the bucket; ships the GUI-half probe script for Joe's hands

You are a SYNAPSE BATTLEPLAN wave agent on branch `bp1/triage` in worktree
`.claude/worktrees/bp1-triage`. Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This
brief is complete; if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "BP1-TRIAGE",
  "name": "Gate 0 - silent-recall triage: four-gate probe (env -> plugin -> layer -> recall) under hython via the hytest shim; names the bucket; ships the GUI-half probe script for Joe's hands",
  "band": "TRUTH",
  "class": "probe",
  "note": "Silent recall = the green-light class. The M1 finding (two store authorities, python/synapse/memory/store.py:1517) is a HYPOTHESIS for the bucket, not the answer - the gate rows decide. Headless Moneta is UNAVAILABLE by construction (harness/memory/STATE.json substrate_presence); under hython G3/G4 may legitimately render UNAVAILABLE/UNKNOWN - that is a measurement, record it, never coerce it to pass or fail.",
  "targets": [
    "1) Author harness/battleplan/notes/probe_silent_recall.py - ONE script runnable both under hython (through .synapse/hytest.py) and pasted into the Houdini GUI Python shell. G1 ENV: PXR_PLUGINPATH_NAME set and pointing at the Moneta schema dir; the SYNAPSE/Moneta package file present under C:\\Users\\User\\OneDrive\\Documents\\houdini22.0 and absent from C:\\Users\\User\\houdini22.0. G2 PLUGIN: pxr.Plug.Registry().GetAllPlugins() contains a plugin whose .name contains 'moneta' (case-insensitive). G3 LAYER: after a scripted deposit and a stage reload, the memory layer identifier appears in stage.GetLayerStack(). G4 RECALL: MemoryPort.query_and_filter(relation_keys, task_context_tokens) of the known deposit returns it. Emit ONE JSON line per gate: {gate, verdict: pass|fail|UNKNOWN, environment: hython|gui, build, observed, exception}. Build is read from hou.applicationVersionString() at runtime - never typed.",
    "2) Run it under hython via the shim (python .synapse/hytest.py ...). Write harness/battleplan/runs/<date>/silent_recall_hython.json (the four rows + a DONE sentinel written LAST).",
    "3) Statically inspect the GUI launch path: where PXR_PLUGINPATH_NAME is injected for the GUI session (package json / 456.py / pythonrc / scripts/install_synapse_package.py), and whether the Houdini prefs known-folder redirect (OneDrive) is honored. Every claim carries file:line.",
    "4) The moment the hython run completes, post a bus finding addressed to *: {bucket: env|plugin|layer|recall|UNKNOWN, gates: [...], anchor: <artifact path>}. BP1-HONESTY consumes it live.",
    "5) Receipt: the GUI half is UNKNOWN until Joe runs the script at the rig - name it in for_ruling as the human-hands item, with the exact paste-in command."
  ],
  "touches": [
    "harness/battleplan/notes/",
    "harness/battleplan/runs/"
  ],
  "readonly": false,
  "deps": [],
  "crucible_criteria": [
    "build stamp in silent_recall_hython.json equals hou.applicationVersionString() observed in the crucible's own shim run - a typed or assumed stamp is the exact defect this wave exists to kill",
    "UNAVAILABLE/UNKNOWN under hython is recorded as such - never coerced to fail, never to pass",
    "no product code touched (git diff of the branch is confined to harness/battleplan/ and the receipt)",
    "the bucket named on the bus follows from the gate rows, not from the M1 narrative"
  ],
  "spawn_classes": [
    "probe"
  ],
  "source": {
    "doc": "docs/BATTLEPLAN.md",
    "anchor": "sec.2 Gate 0 - four-gate discriminator, run twice (hython + GUI); first failing gate names the bucket"
  },
  "acceptance": [
    {
      "predicate": "harness/battleplan/runs/<date>/silent_recall_hython.json exists with exactly four gate rows, each verdict in pass|fail|UNKNOWN, environment=hython, build runtime-observed, DONE sentinel present",
      "evidence": "probe"
    },
    {
      "predicate": "a bucket finding is on the BP1 bus addressed to * whose anchor is the artifact path",
      "evidence": "check"
    },
    {
      "predicate": "GUI launch-path inspection: every env-injection claim carries file:line; the OneDrive redirect is confirmed honored or named as the defect",
      "evidence": "check"
    },
    {
      "predicate": "probe_silent_recall.py runs to completion pasted into the Houdini 22.0.400 GUI Python shell and emits four rows (Joe's hands)",
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
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp1 BP1-TRIAGE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py claims bp1`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases. No intra-wave shared seam by design:
   TRIAGE is read-only, RAILS owns harness/, HONESTY owns the recall path.
   HONESTY consumes TRIAGE's bucket finding VIA THE BUS the moment it posts.
2. **Findings** as you go — and the moment an evidence artifact lands, post its
   path so peers consume it live (this is the wave's dynamic handoff):
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp1 BP1-TRIAGE finding '{\"claim\": \"...\", \"anchor\": \"file:line-or-artifact-path\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp1 BP1-TRIAGE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam, and poll for peer artifacts your
   mission consumes:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py read bp1 BP1-TRIAGE`

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

Write `harness/notes/receipts/BP1-TRIAGE.json` **inside your worktree**:
`{{"leg": "BP1-TRIAGE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn — hold there.
