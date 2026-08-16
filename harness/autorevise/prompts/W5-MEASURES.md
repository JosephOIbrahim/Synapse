# W5-MEASURES â€” substrate P2: cook-verify contracts - extend 'unmeasured renders UNKNOWN' to every output kind, tier ladder, golden runner

You are a SYNAPSE wave agent on branch `wave5/measures` in worktree `.claude/worktrees/w5-measures`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-MEASURES",
  "name": "substrate P2: cook-verify contracts - extend 'unmeasured renders UNKNOWN' to every output kind, tier ladder, golden runner",
  "band": "BUILD",
  "class": "build",
  "note": "Blueprint M3 (docs/BLUEPRINT_WEAK_DOMAINS.md section 3). FP2: never assert what you haven't measured. Independent of the catalog - runs parallel to W5-CATALOG.",
  "targets": [
    "1) python/synapse/validation/measures.py: measurement contracts per output kind - image (res/channels/stats/hash), sim (per-frame NaN, max velocity, KE ratio, max strain), geometry (counts/bbox/NaN/weight-normalization), channels (samples/range/variance), graph (compiles, errors empty, invokes) - each with its UNKNOWN condition per the blueprint table",
    "2) explosion signature: monotonic KE growth ratio over threshold across 5 consecutive frames, or max strain over bound, or any NaN -> verdict EXPLODING with offending frame and signal - no vibes",
    "3) tier ladder as a verification axis on existing tool_exposure metadata: SCAFFOLD -> SCHEMA_VERIFIED -> COOK_VERIFIED -> GOLDEN; SCAFFOLD stays doc_only, COOK_VERIFIED+ earns foreground; tier disclosed in tool results in the existing scaffold-note voice; tests/test_phase3_exposure.py stays green - extend, never fork",
    "4) golden harness: rulebook/goldens/<domain>/ fixtures with deterministic seeds + a hython runner that cooks each golden and asserts its measurement contract; grow from the tests/test_forge_copernicus.py seam and the .claude/cook_probe_*.json habit",
    "5) explosion detector fires on a deliberately broken golden and stays quiet on the healthy one - both fixtures committed"
  ],
  "touches": [
    "python/synapse/validation/",
    "rulebook/",
    "tests/"
  ],
  "readonly": false,
  "deps": [],
  "crucible_criteria": [
    "the tier ladder EXTENDS tool_exposure - test_phase3_exposure.py and the truth-contract suite (test_m1_truth_contract.py) stay green byte-for-byte in intent; any contract change is for_ruling",
    "hython goldens that cannot run headless in the worktree render UNKNOWN with the exact failing invocation, never a simulated pass",
    "no overlap with W5-PANEL's python/synapse/panel/ surface - registry/metadata edits stay server/validation side; bus claim before any shared seam"
  ],
  "spawn_classes": [
    "probe"
  ],
  "source": {
    "doc": "docs/BLUEPRINT_WEAK_DOMAINS.md",
    "anchor": "section 3 - Substrate Phase 2, Cook-Verify contracts; exit criteria Mile 3"
  },
  "acceptance": [
    {
      "predicate": "measures module covers all five output kinds with UNKNOWN conditions per the blueprint table",
      "evidence": "test"
    },
    {
      "predicate": "explosion detector: fires on broken golden, silent on healthy golden",
      "evidence": "test"
    },
    {
      "predicate": "tier field live in the registry, disclosed in tool results, exposure tests green",
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-MEASURES claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-MEASURES finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-MEASURES status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-MEASURES`

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

Write `harness/notes/receipts/W5-MEASURES.json` **inside your worktree**:
`{{"leg": "W5-MEASURES", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
