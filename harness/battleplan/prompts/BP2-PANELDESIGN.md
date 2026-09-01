# BP2-PANELDESIGN — Panel rhythm: spec then implement the sec.7 spacing pass on the five camera regions - tokens + QSS on the density root property, zero new colours/widgets/families, Expert pin green

You are a SYNAPSE BATTLEPLAN wave agent on branch `bp2/paneldesign` in worktree
`.claude/worktrees/bp2-paneldesign`. Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This
brief is complete; if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "BP2-PANELDESIGN",
  "name": "Panel rhythm: spec then implement the sec.7 spacing pass on the five camera regions - tokens + QSS on the density root property, zero new colours/widgets/families, Expert pin green",
  "band": "BUILD",
  "class": "build",
  "note": "Tier: reasoning (the importer-retirement chore is mechanical tier - Haiku - if the orchestrator can dispatch it separately; otherwise do it last and say so). Self-cap: 60 turns across two sessions (A: spec, B: implement; progress every 5; sec.12 R-3). HELD in the live manifest until Joe's Wed word (sec.12 R-6): PANELTRUTH must be MERGED, not merely receipted, before you run - its harness/battleplan/runs/<date>/profile_diff.json is your input, read it from master. Amber tier: the GUI sign-off on the five regions is Joe's eyes (gui_required). ADAPT: confirm /design skill syntax with /help in your session; if unavailable, author the spec by hand from sec.7 - same output, same accept.",
  "targets": [
    "T1) SESSION A - SPEC. Input: docs/BATTLEPLAN.md sec.7 + profile_diff.json + the five camera regions. Output docs/PANEL_RHYTHM_SPEC.md: token table (SPACE 4/8/12/16/24/32/48 mapped onto the EXISTING SPACE_* names - never rename), per-region QSS rules, density multipliers (airy x1.5 / standard x1 / tight x0.75, GAPS only, paddings fixed), before/after measurements in px per region. Stop at five regions.",
    "T2) SESSION B - IMPLEMENT. Extend python/synapse/panel/designsystem/tokens.py spacing scale to sec.7 values; QSS descendant rules keyed on the existing `density` root property (repolish per 08-04, proven by PANELTRUTH); the five camera regions only: profile tab strip pills, verb rail labels, recall card (three bands; footer pill mirrors HIT / NO HIT / UNAVAILABLE / BLOCKED in label style, HOT_SOFT only for BLOCKED), TOKEN face parameter rows (UNKNOWN as text in the value column, never a bar at zero), .hip ribbon + header status line. fontload.py untouched; zero new colours; Curious gets the airy multiplier; Expert reads the same tokens at x1.",
    "T3) HEADLESS TEST: gap tokens step by the density multipliers per profile; test_expert_resolved_equals_v5420_snapshot green; `pytest -q` green.",
    "T4) CHORE (mechanical tier): `python .synapse/verify.py no-importers python/synapse/panel/tokens.py python/synapse/panel` - if that subcommand does not exist, a grep of importers is the same evidence. If only styles.py imports tokens.py and nothing imports styles.py, delete both (contract theme-seed-tokens.yaml split, sec.5); else post a finding and leave them. Host-scheme seeding stays parked.",
    "T5) Author .synapse/contracts/panel-rhythm.yaml (git add -f; features passing:false; GUI sign-off feature is red tier)."
  ],
  "touches": [
    "python/synapse/panel/designsystem/",
    "python/synapse/panel/manifests/",
    "python/synapse/panel/tokens.py",
    "python/synapse/panel/styles.py",
    "docs/PANEL_RHYTHM_SPEC.md",
    ".synapse/contracts/panel-rhythm.yaml",
    "tests/",
    "harness/battleplan/notes/"
  ],
  "readonly": false,
  "deps": [
    "BP2-PANELTRUTH"
  ],
  "crucible_criteria": [
    "any new hex colour string in the diff is BROKEN",
    "any new QFont family in the diff is BROKEN (families come from fontload.py only)",
    "any structural change to the Expert manifest is BROKEN - the pin proves it",
    "paddings are fixed; only gap tokens scale with density",
    "no hardcoded pt size (font floor derives from the host, W5L-PANEL T1)"
  ],
  "spawn_classes": [
    "probe"
  ],
  "source": {
    "doc": "docs/BATTLEPLAN.md",
    "anchor": "2026-09-01 sec.0.3 P-4/P-6/P-7, sec.6 BP2-PANEL-DESIGN, sec.7, sec.12 R-6"
  },
  "acceptance": [
    {
      "predicate": "docs/PANEL_RHYTHM_SPEC.md exists with px numbers per region, token table, density multipliers",
      "evidence": "check"
    },
    {
      "predicate": "QSS/token diff introduces no colour token and no hex string (grep attached)",
      "evidence": "check"
    },
    {
      "predicate": "headless test: gap tokens step by the density multipliers per profile",
      "evidence": "test"
    },
    {
      "predicate": "test_expert_resolved_equals_v5420_snapshot green and `pytest -q` green on the branch",
      "evidence": "test"
    },
    {
      "predicate": "importer chore outcome posted as a bus finding (deleted pair, or importers named and left)",
      "evidence": "receipt"
    },
    {
      "predicate": "GUI sign-off on the five camera regions in the .400 GUI (Joe, Thu/Fri)",
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
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp2 BP2-PANELDESIGN claim '{\"files\": [\"<paths>\"]}'`
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
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp2 BP2-PANELDESIGN finding '{\"claim\": \"...\", \"anchor\": \"file:line-or-artifact-path\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp2 BP2-PANELDESIGN status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam, and poll for peer artifacts your
   mission consumes:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py read bp2 BP2-PANELDESIGN`
5. **Progress** every 5 turns - the on-target signal the orchestrator's drift
   check reads. Cite the target you are on and the evidence path if one exists:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp2 BP2-PANELDESIGN progress '{\"target\": \"T1\", \"evidence_path\": \"<path-or-none>\"}'`
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

Write `harness/notes/receipts/BP2-PANELDESIGN.json` **inside your worktree**:
`{{"leg": "BP2-PANELDESIGN", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn — hold there.
