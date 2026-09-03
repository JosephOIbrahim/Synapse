# BP3-STUBS — Scaffold, not implement: three NEW_MCP_TOOL candidates as signatures + preconditions (D1.5); spatial lane entry as an UNAPPLIED diff (D3.1); world_manifest schema homed + example manifest that validates (D3.2)

You are a SYNAPSE BATTLEPLAN wave agent on branch `bp3/stubs` in worktree
`.claude/worktrees/bp3-stubs`. Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This
brief is complete; if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "BP3-STUBS",
  "band": "BUILD",
  "class": "build",
  "tier": "reasoning",
  "name": "Scaffold, not implement: three NEW_MCP_TOOL candidates as signatures + preconditions (D1.5); spatial lane entry as an UNAPPLIED diff (D3.1); world_manifest schema homed + example manifest that validates (D3.2)",
  "note": "Tier: reasoning. Self-cap: 20 turns (progress every 5). Blocked until BP3-RECON's finding (schema_home, notes_dir, authoring_domains.json path). Reads BP3-PROBE's finding if present but does not wait for it. Nothing you write is registered, imported by mcp_server, or applied: the lane is ratified:false and the tools are signatures. Mirror an existing tool's signature shape from mcp_tools_render.py / mcp_tools_usd.py so the stubs read like the house style. Rule D-3: the blueprint gains no scope; the only blueprint edit allowed is the sidecar path line if the schema moves.",
  "targets": [
    "T1) D1.5: docs/intake/h22-tool-candidates-<yyyy-mm-dd>.md - for synapse_author_light_blocker, synapse_author_image_filters, synapse_author_render_pass_chain: signature (name, params with types/defaults), preconditions from blueprint sec.1.4 (Karma delegate; Husk raster product; husk --pass present; one product per file), the exact refusal/warning text SYNAPSE returns when a precondition fails, source claim IDs, and 'implementation: none (D1.5)'. Add the two RECIPE_CHANGE rows (scatter recipe, textured material) as 'change proposal' entries with the parm-name dependency on P-5/P-2.",
    "T2) D3.1: harness/battleplan/notes/BP3_lane_spatial.diff - a unified diff against the reconciled authoring_domains.json adding the sec.3.2 lane entry verbatim (ratified:false, non_goals verbatim). `git apply --check` must pass; the diff is NOT applied. If authoring_domains.json does not exist, write the entry as BP3_lane_spatial.proposed.json and say so.",
    "T3) D3.2: move docs/intake/world_manifest.schema.json to RECON's schema_home (git mv; if schema_home is none, leave it and record that). Validate: `python -c \"import json; json.load(open(p))\"` at minimum; `jsonschema` if importable. Write docs/intake/world_manifest.example.json - a fixture-shaped instance (world.source=fixture, frame.native=marble_raw_opencv, applied flags false, provenance.probes from PROBE's finding if available else []) that validates against the schema; paste the validation command + result in the receipt.",
    "T4) If the schema moved, edit ONLY the 'Sidecars' line of docs/intake/blueprint-h22-worldlabs-intent.md to the new path. No other blueprint edit."
  ],
  "touches": [
    "docs/intake/h22-tool-candidates-*.md",
    "harness/battleplan/notes/BP3_lane_spatial.diff",
    "harness/battleplan/notes/BP3_lane_spatial.proposed.json",
    "docs/intake/world_manifest.schema.json",
    "docs/intake/world_manifest.example.json",
    "docs/intake/blueprint-h22-worldlabs-intent.md"
  ],
  "readonly": false,
  "deps": [
    "BP3-RECON"
  ],
  "crucible_criteria": [
    "grep mcp_server.py and every mcp_tools_*.py on the branch for the three tool names - zero hits",
    "authoring_domains.json byte-identical to master on the branch (diff not applied)",
    "mutations: remove `required` from the schema -> example validation must change outcome; add a body to a stub -> a 'no implementation' checker or the crucible's grep reddens; apply the diff -> authoring_domains differs from master -> red",
    "every verdict row carries the crucible's own anchor"
  ],
  "spawn_classes": [],
  "source": {
    "doc": "docs/intake/blueprint-h22-worldlabs-intent.md",
    "anchor": "v0.3 sec.1.3 D1.5; sec.3.7 D3.1/D3.2; sec.3.2 lane declaration; rule D-3"
  },
  "acceptance": [
    {
      "predicate": "three candidates each with signature, preconditions, refusal text, claim IDs, implementation: none",
      "evidence": "check"
    },
    {
      "predicate": "BP3_lane_spatial.diff passes `git apply --check` and authoring_domains.json is unchanged vs master",
      "evidence": "check"
    },
    {
      "predicate": "world_manifest.example.json validates against the schema (command + result in receipt)",
      "evidence": "test"
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
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp3 BP3-STUBS claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py claims bp3`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases. No intra-wave shared seam by design.
   Territory for THIS wave: each mission's `touches` is its writable surface and its `note` names ownership; anything outside your `touches` is read-only to you. Consumption is VIA THE BUS the moment a peer posts an artifact path.
2. **Findings** as you go — and the moment an evidence artifact lands, post its
   path so peers consume it live (this is the wave's dynamic handoff):
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp3 BP3-STUBS finding '{\"claim\": \"...\", \"anchor\": \"file:line-or-artifact-path\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp3 BP3-STUBS status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam, and poll for peer artifacts your
   mission consumes:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py read bp3 BP3-STUBS`
5. **Progress** every 5 turns - the on-target signal the orchestrator's drift
   check reads. Cite the target you are on and the evidence path if one exists:
   `python C:\Users\User\SYNAPSE\harness\battleplan\bus.py post bp3 BP3-STUBS progress '{\"target\": \"T1\", \"evidence_path\": \"<path-or-none>\"}'`
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

Write `harness/notes/receipts/BP3-STUBS.json` **inside your worktree**:
`{{"leg": "BP3-STUBS", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn — hold there.
