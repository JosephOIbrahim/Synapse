# W5-CATALOG â€” substrate P1: build-keyed schema catalog - one hython dump makes every parm name verified-by-construction

You are a SYNAPSE wave agent on branch `wave5/catalog` in worktree `.claude/worktrees/w5-catalog`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-CATALOG",
  "name": "substrate P1: build-keyed schema catalog - one hython dump makes every parm name verified-by-construction",
  "band": "BUILD",
  "class": "build",
  "note": "Blueprint M1-M2 (docs/BLUEPRINT_WEAK_DOMAINS.md section 2). FP1: never recall what the binary can tell you. Domain waves A-E stay gated on this substrate.",
  "targets": [
    "1) scripts/build_node_catalog.py modeled on scripts/harvest_lop_catalog.py: full hou.nodeTypeCategories() walk (18 categories proven live, Cop=386 types) -> rag/catalog/h22.0.400/<category>.json with type/label/inputs/parms (name, label, type, defaults, ranges, menu tokens+labels). hython: C:\\Program Files\\Side Effects Software\\Houdini 22.0.400\\bin\\hython.exe",
    "2) VOP extension: instantiate each VOP type in a throwaway matnet, read inputNames/outputNames/inputDataTypes/outputDataTypes, destroy - wire signatures the parm templates do not carry (industrializes the conn_mtlx probes)",
    "3) APEX extension: enumerate apex.callbackRegistry + component/constraint/control/brush registries via getRegistries; typed ports from apex.Signature/OverloadSet -> rag/catalog/h22.0.400/apex_callbacks.json (dump path proven 2026-08-16, 78 symbols)",
    "4) docs join: each catalog row gains a doc field joined from the help-cache ASTs at C:\\Users\\User\\OneDrive\\Documents\\houdini22.0\\config\\Help\\cache, parm-include fragments resolved; cache is visited-pages-only - absent docs stay absent, never synthesized",
    "5) spot-audit 20 nodes per weak domain (dop, vop, chop, cop, apex) against a live hython session - zero mismatches, receipts with node/parm anchors",
    "6) if hython is unreachable from the worktree, the leg records blocked with the exact failing invocation - a catalog not dumped from the binary is not a catalog"
  ],
  "touches": [
    "scripts/",
    "rag/catalog/",
    "tests/"
  ],
  "readonly": false,
  "deps": [],
  "crucible_criteria": [
    "rag/ingest_ledger is SINGLE-WRITER (R1) - this leg writes rag/catalog/ only and never touches the ledger or the served corpus; any K.5 refresh need lands as for_ruling, not an edit",
    "catalog rows must trace to a live dump receipt (hython stdout/log committed) - rows authored from model memory are the exact defect this substrate kills",
    "build-keyed path h22.0.400 exact - staleness-by-construction depends on it"
  ],
  "spawn_classes": [
    "probe"
  ],
  "source": {
    "doc": "docs/BLUEPRINT_WEAK_DOMAINS.md",
    "anchor": "section 2 - Substrate Phase 1, the Schema Catalog; exit criteria Mile 1-2"
  },
  "acceptance": [
    {
      "predicate": "catalog files exist for every category hou.nodeTypeCategories() returns, build-keyed under rag/catalog/h22.0.400/",
      "evidence": "probe"
    },
    {
      "predicate": "spot-audit 20 nodes per weak domain vs live session: zero mismatches, anchored receipts",
      "evidence": "probe"
    },
    {
      "predicate": "VOP wire signatures and APEX callback ports present with typed entries",
      "evidence": "test"
    }
  ]
}
```

## Constitution (non-negotiable)

- **NEVER**: `git push`, `git merge`, tag, edit `harness/state/drop.json`, flip
  any `ratified` or any leg `state` in a manifest. Those are human words, per act.
- **Unobtainable renders UNKNOWN** â€” never zero, never an estimate, never a pass.
  A `gui_required` acceptance you cannot measure headless is recorded UNKNOWN.
- **Receipts over claims** â€” every finding carries a file:line, probe path, or
  receipt anchor. No anchor, no claim.
- Named-file commits only on your branch. Never `git add -A`.
- Scope is the mission. Prerequisite work is real work â€” do it. Unrelated value â€”
  post a `spawn` proposal, don't chase it.

## The bus (how the team talks)

ONE bus command. Always this exact absolute path â€” NEVER a relative call. A
relative `python harness/autorevise/bus.py` from your worktree writes a
FRAGMENTED bus in the worktree that nobody reads: your claims become invisible
and two agents will edit one file.

1. **Before touching any file in `touches`** â€” post a claim:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-CATALOG claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-CATALOG finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-CATALOG status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-CATALOG`

## Receipt (completion contract)

**COMMIT BEFORE RECEIPT — hard order (CRX0, wave 4).** The receipt is written
LAST, after your named-file commit exists on your branch. Sequence: (1) commit
your product + notes files (named, never -A); (2) verify `git rev-list --count
<base>..HEAD` >= 1; (3) only then write the receipt, and state the observed
HEAD sha in it. A receipt at ahead:0 asserts commit-state that does not exist —
the exact claim-before-act defect this harness exists to kill.

**THE RECEIPT IS ITS OWN CLOSING COMMIT - the leg commits it, not the operator
(W5H).** Commit-before-receipt is only the first half. The second half is that
the receipt file must itself land as your branch's LAST commit (named, never
`-A`): writing it into the worktree is not finishing, committing it is.
Operator rescue is a failure mode, not the plan. In wave 5, W5-CRUX and three of
the four builder legs (W5-BASE, W5-DENSE, W5-UNDO) left their receipts
worktree-only, and a human had to bring them in-tree afterward (the close pass
`c7a6a08d`; `76ca94a0` for CRUX). Only W5-DELTA committed its own receipt as its
closing commit (`b4bbb562` on `wave5/delta`) - that is the rule now, for every
leg. Full sequence: product commit -> verify ahead >= 1 -> write the receipt
stating the product HEAD sha -> commit the receipt as your closing commit.

Write `harness/notes/receipts/W5-CATALOG.json` **inside your worktree**:
`{{"leg": "W5-CATALOG", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
