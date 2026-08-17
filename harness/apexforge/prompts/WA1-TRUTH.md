# WA1-TRUTH — G1+G4+C1: re-seed APEX truth surface under H22.0.400, author apex_basic autoresearch mission + probe kinds, extend version-agreement to the APEX catalog stamp

You are a SYNAPSE APEXFORGE wave agent on branch `wavea1/truth` in worktree
`.claude/worktrees/wa1-truth`. Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This
brief is complete; if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "WA1-TRUTH",
  "name": "G1+G4+C1: re-seed APEX truth surface under H22.0.400, author apex_basic autoresearch mission + probe kinds, extend version-agreement to the APEX catalog stamp",
  "band": "BUILD",
  "class": "build",
  "note": "The H21.0.671 stamp on apex_probes.py is the stale-truth defect class DESIGN.md prosecuted. Probe execution is hython via .synapse/hytest.py shim discipline (skip != pass). Publish the catalog artifact path on the bus the moment it lands - WA1-WIRE and WA1-RECIPE consume it live.",
  "targets": [
    "1) python/synapse/science/apex_probes.py: re-run the seed set under the running H22 build via hython; add seed rows for the H22 additions (blueprint sec.3: rigpose SOP, controlextract::2.0, configuregraph Effects mode, sceneinvoke alias, fuse-graph utilities, UsdSkel renames, ramp types); re-stamp the docstring with the observed build string - stamp is read from the runtime, never typed from memory",
    "2) harness/autoresearch/missions/apex_basic.json: new mission in the existing autoresearch schema with phases P0_catalog (apex_callback_discovery), P0_ports (apex_port_signature), P1_sops (type_existence seeded from apex_probes.py + sec.3 additions), P2_invoke (chain_hash invoke smoke, repeat 2)",
    "3) harness/autoresearch/probes.py: implement probe kinds apex_callback_discovery and apex_port_signature (probes.py is the one file allowed to touch hou); capture the APEX Log error channel where available, not just stdout",
    "4) run the mission: evidence artifact harness/autoresearch/runs/<stamp>/apex_truth_<build>.json with claim/value/probe/build/timestamp per entry; unobtainable entries render UNKNOWN",
    "5) harness/verify/version_agreement.py: extend contract to cover the apex_truth build stamp so catalog drift is a red check; do not weaken existing checks",
    "6) bus: post a finding with the artifact path + entry count the moment apex_truth lands, addressed to *"
  ],
  "touches": [
    "python/synapse/science/apex_probes.py",
    "harness/autoresearch/missions/",
    "harness/autoresearch/probes.py",
    "harness/autoresearch/runs/",
    "harness/verify/version_agreement.py",
    "tests/"
  ],
  "readonly": false,
  "deps": [],
  "crucible_criteria": [
    "build stamp in apex_truth_<build>.json equals the build string observed from the runtime in the same run - a typed or assumed stamp is the exact defect this leg exists to kill",
    "every catalog entry carries probe provenance; no entry copied from model memory or docs without a runtime confirmation",
    "hytest shim discipline: a skipped hython probe is UNKNOWN, never a pass; headless-unmeasurable values render UNKNOWN",
    "version_agreement extension is additive - existing agreement checks still pass"
  ],
  "spawn_classes": [
    "probe"
  ],
  "source": {
    "doc": "docs/APEX_H22_BLUEPRINT.md",
    "anchor": "sec.4 G1/G4 + sec.5 C1 - re-stamp truth surface, apex_basic mission, catalog + port signatures"
  },
  "acceptance": [
    {
      "predicate": "apex_truth_<build>.json exists under autoresearch/runs with build == running H22 build (runtime-observed), all pre-existing rank>=70 seeds re-confirmed or explicitly UNKNOWN/absent with probe evidence",
      "evidence": "probe"
    },
    {
      "predicate": "apex_probes.py docstring re-stamped with the same runtime-observed build string; H21.0.671 stamp gone",
      "evidence": "check"
    },
    {
      "predicate": "version_agreement.py covers the apex catalog stamp and reads green against the fresh artifact; full agreement suite still green",
      "evidence": "check"
    },
    {
      "predicate": "P2 invoke smoke: minimal graph -> invokegraph -> cook -> geometry hash, repeat 2, hashes identical (determinism claim held)",
      "evidence": "probe"
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
   `python C:\Users\User\SYNAPSE\harness\apexforge\bus.py post wavea1 WA1-TRUTH claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\apexforge\bus.py claims wavea1`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases. `harness/autoresearch/probes.py` is the
   known shared seam this wave (TRUTH + WIRE) — serialize on it.
2. **Findings** as you go — and the moment an evidence artifact lands, post its
   path so peers consume it live (this is the wave's dynamic handoff):
   `python C:\Users\User\SYNAPSE\harness\apexforge\bus.py post wavea1 WA1-TRUTH finding '{\"claim\": \"...\", \"anchor\": \"file:line-or-artifact-path\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\apexforge\bus.py post wavea1 WA1-TRUTH status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam, and poll for peer artifacts your
   mission consumes:
   `python C:\Users\User\SYNAPSE\harness\apexforge\bus.py read wavea1 WA1-TRUTH`

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

Write `harness/notes/receipts/WA1-TRUTH.json` **inside your worktree**:
`{{"leg": "WA1-TRUTH", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn — hold there.
