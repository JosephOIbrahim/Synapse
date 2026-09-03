# BP3-PANEL — Design-system pass on the SYNAPSE Python panel: audit (tokens, spacing scale, naming, typography) then a whitespace-and-token-only change set traceable row-by-row to the audit; no new widgets, no behaviour

You are a SYNAPSE BATTLEPLAN wave agent on branch `bp3/panel` in worktree
`.claude/worktrees/bp3-panel`. Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This
brief is complete; if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "BP3-PANEL",
  "band": "BUILD",
  "class": "build",
  "tier": "reasoning",
  "name": "Design-system pass on the SYNAPSE Python panel: audit (tokens, spacing scale, naming, typography) then a whitespace-and-token-only change set traceable row-by-row to the audit; no new widgets, no behaviour",
  "note": "Tier: reasoning. Self-cap: 20 turns (progress every 5) - this is the roadmap's 2h timebox; at 80% post wrap_up and ship what is clean. You own python/synapse/panel/ this wave (designsystem/, manifests/, qss, layout modules). synapse_panel.py lifecycle and timer ranges are untouchable (BP2-CRUX rule). Continue from the accepted result: read the BP2-PANELDESIGN receipt and `git log master -- python/synapse/panel/` first; do not re-derive what landed. Design-system audit shape: Summary (components reviewed, issues, score) / Naming Consistency / Token Coverage (colors, spacing, typography: defined vs hardcoded instances) / Component Completeness (states, variants, docs) / Priority Actions. Reference rhythm: docs/PANEL_RHYTHM_SPEC.md; design review: docs/SYNAPSE_PANEL_DESIGN_REVIEW_H22_LENS.md.",
  "targets": [
    "T1) Read first: harness/notes/receipts/BP2-PANELDESIGN.json, docs/PANEL_RHYTHM_SPEC.md, docs/SYNAPSE_PANEL_DESIGN_REVIEW_H22_LENS.md, `git log --oneline -15 master -- python/synapse/panel/`. Post a bus claim on python/synapse/panel/ before any edit.",
    "T2) Audit (read-only): harness/battleplan/notes/BP3_PANEL_AUDIT.md in the design-system audit shape. Token Coverage table must count hardcoded px/pt/hex/rgb/font-size instances per file (grep, cite file:line). Naming table: token names that disagree with the rhythm spec. Component table: each panel widget class with states/variants/docs ticks. Priority Actions ranked by instances fixed per edit.",
    "T3) Change set: ONLY substitutions from the audit - hardcoded value -> existing token; off-scale spacing -> nearest rhythm-spec step; inconsistent token name -> canonical name (with every reference updated). No new widget, signal, slot, timer, import of new modules, or behaviour change. Every diff hunk cites its audit row in the commit message body.",
    "T4) Evidence: headless - the panel test target (RECON's finding or `python -m pytest tests -k panel -q`) green before and after; `git diff --stat master..HEAD -- python/synapse/panel/` lists only designsystem/manifests/qss/layout files; `git diff master..HEAD -- python/synapse/panel/synapse_panel.py` shows no line inside the lifecycle/timer functions. Visual before/after is gui_required -> UNKNOWN headless; write the exact steps for Joe to capture it."
  ],
  "touches": [
    "python/synapse/panel/",
    "harness/battleplan/notes/BP3_PANEL_AUDIT.md"
  ],
  "readonly": false,
  "deps": [],
  "crucible_criteria": [
    "every diff hunk maps to an audit row (the crucible builds the map itself)",
    "mutations: re-introduce one hardcoded hex/px -> the crucible's grep-based token checker reddens; add a QWidget subclass or a new signal -> whitespace-only checker reddens; touch a timer range -> red",
    "panel tests green in a fresh checkout",
    "a leg with any UNKNOWN acceptance is at best SOUND-WITH-NITS, never SOUND"
  ],
  "spawn_classes": [],
  "source": {
    "doc": "docs/intake/blueprint-h22-worldlabs-intent.md",
    "anchor": "roadmap P5 panel spacing pass (docs/PANEL_RHYTHM_SPEC.md); blueprint v0.3 sec.0.3 rule D-2 (verified over pretty)"
  },
  "acceptance": [
    {
      "predicate": "BP3_PANEL_AUDIT.md exists in the audit shape with file:line instances per token category",
      "evidence": "check"
    },
    {
      "predicate": "diff touches only designsystem/manifests/qss/layout files; synapse_panel.py lifecycle/timer ranges unchanged",
      "evidence": "check"
    },
    {
      "predicate": "panel test target green before and after",
      "evidence": "test"
    },
    {
      "predicate": "before/after screenshots show only spacing/typography/colour-token changes",
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
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp3 BP3-PANEL claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py claims bp3`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases. No intra-wave shared seam by design.
   Territory for THIS wave: each mission's `touches` is its writable surface and its `note` names ownership; anything outside your `touches` is read-only to you. Consumption is VIA THE BUS the moment a peer posts an artifact path.
2. **Findings** as you go — and the moment an evidence artifact lands, post its
   path so peers consume it live (this is the wave's dynamic handoff):
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp3 BP3-PANEL finding '{\"claim\": \"...\", \"anchor\": \"file:line-or-artifact-path\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp3 BP3-PANEL status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam, and poll for peer artifacts your
   mission consumes:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py read bp3 BP3-PANEL`
5. **Progress** every 5 turns - the on-target signal the orchestrator's drift
   check reads. Cite the target you are on and the evidence path if one exists:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp3 BP3-PANEL progress '{\"target\": \"T1\", \"evidence_path\": \"<path-or-none>\"}'`
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

Write `harness/notes/receipts/BP3-PANEL.json` **inside your worktree**:
`{{"leg": "BP3-PANEL", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn — hold there.
