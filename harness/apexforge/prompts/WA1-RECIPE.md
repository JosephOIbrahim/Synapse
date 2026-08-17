# WA1-RECIPE — G2: migrate panel recipes off phantom APEX names + catalog-membership goalpost test - the phantom class becomes unshippable

You are a SYNAPSE APEXFORGE wave agent on branch `wavea1/recipe` in worktree
`.claude/worktrees/wa1-recipe`. Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This
brief is complete; if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "WA1-RECIPE",
  "name": "G2: migrate panel recipes off phantom APEX names + catalog-membership goalpost test - the phantom class becomes unshippable",
  "band": "BUILD",
  "class": "build",
  "note": "The supersession map has existed in apex_probes.py since June; this leg executes it. Consume the fresh apex_truth catalog VIA THE BUS when TRUTH posts it; the supersession map in apex_probes.py is the migration guide either way. Pure-Python goalpost - no hou, no hython, stock pytest.",
  "targets": [
    "1) python/synapse/panel/apex_recipes.py: replace every fictional name (apex::rig::, apex::sop:: namespaces and any other catalog-absent type) with the real superseded name per the supersession map; recipe semantics preserved",
    "2) python/synapse/panel/apex_explainer.py: same migration, same map",
    "3) goalpost test (tests/panel/): grep every emitted graph/recipe type name against the apex_truth catalog artifact - any catalog-absent name fails the test; pure Python, real signal under stock pytest, no skip path",
    "4) the test reads the catalog path from the newest apex_truth_*.json under autoresearch/runs (or an env override) - it must fail LOUDLY if no catalog artifact exists, never skip to green",
    "5) record in notes which names were migrated old->new, with the supersession-map anchor per rename"
  ],
  "touches": [
    "python/synapse/panel/apex_recipes.py",
    "python/synapse/panel/apex_explainer.py",
    "tests/"
  ],
  "readonly": false,
  "deps": [
    "WA1-TRUTH"
  ],
  "crucible_criteria": [
    "no-catalog-artifact => test FAILS loudly, never skips - a skip here is the false-green class hytest exists to kill",
    "migration preserves recipe behavior: renames only, no silent semantic edits; any needed semantic change is a finding for ruling, not a quiet fix",
    "python/synapse/panel/ surface: this leg is the ONLY writer to apex_recipes.py/apex_explainer.py this wave; bus claim still posted before edit (house discipline)",
    "every rename in the notes carries its supersession-map anchor"
  ],
  "spawn_classes": [],
  "source": {
    "doc": "docs/APEX_H22_BLUEPRINT.md",
    "anchor": "sec.4 G2 - phantom-name migration + catalog-membership goalpost"
  },
  "acceptance": [
    {
      "predicate": "zero catalog-absent type names emitted by apex_recipes.py/apex_explainer.py - goalpost test green against the fresh apex_truth catalog",
      "evidence": "test"
    },
    {
      "predicate": "goalpost test fails loudly (not skip) when the catalog artifact is absent - RED leg demonstrated in the test suite",
      "evidence": "test"
    },
    {
      "predicate": "rename ledger in notes: every old->new pair anchored to the supersession map",
      "evidence": "receipt"
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
- **Runtime is truth, docs are the referee, model memory is hypothesis.** Any
  APEX name you emit must be catalog-proven (apex_truth artifact) or explicitly
  flagged unverified. The phantom-namespace failure (apex::rig::, apex::sop::)
  is the class this wave exists to make unshippable — do not add to it.
- Named-file commits only on your branch. Never `git add -A`.
- Scope is the mission. Prerequisite work is real work — do it. Unrelated value —
  post a `spawn` proposal, don't chase it.

## The bus (how the team talks — APEXFORGE bus, NOT the autorevise bus)

ONE bus command. Always this exact absolute path — NEVER a relative call. A
relative call from your worktree writes a FRAGMENTED bus nobody reads: your
claims become invisible and two agents will edit one file.

1. **Before touching any file in `touches`** — post a claim:
   `python C:\Users\User\SYNAPSE\harness\apexforge\bus.py post wavea1 WA1-RECIPE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\apexforge\bus.py claims wavea1`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases. `harness/autoresearch/probes.py` is the
   known shared seam this wave (TRUTH + WIRE) — serialize on it.
2. **Findings** as you go — and the moment an evidence artifact lands, post its
   path so peers consume it live (this is the wave's dynamic handoff):
   `python C:\Users\User\SYNAPSE\harness\apexforge\bus.py post wavea1 WA1-RECIPE finding '{\"claim\": \"...\", \"anchor\": \"file:line-or-artifact-path\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\apexforge\bus.py post wavea1 WA1-RECIPE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam, and poll for peer artifacts your
   mission consumes:
   `python C:\Users\User\SYNAPSE\harness\apexforge\bus.py read wavea1 WA1-RECIPE`

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

Write `harness/notes/receipts/WA1-RECIPE.json` **inside your worktree**:
`{{"leg": "WA1-RECIPE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn — hold there.
