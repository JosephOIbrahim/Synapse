# W5-BASE â€” suite_baseline promoted to the R31 two-leg tuple - the standing master red dies

You are a SYNAPSE wave agent on branch `wave5/base` in worktree `.claude/worktrees/w5-base`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W5-BASE",
  "name": "suite_baseline promoted to the R31 two-leg tuple - the standing master red dies",
  "band": "BUILD",
  "source": {
    "doc": "harness/verify/checks.py",
    "anchor": "R.R + K.7 guardrail_violations: suite_baseline - 'FLAT baseline shape rejected: top-level passed/failed scalar; R31 requires the two-leg tuple {gate:{...}, shipping:{...}}, each leg naming its interpreter and producer'. Proposal already banked at harness/notes/receipts/Q2_PROPOSED_suite_baseline.json. Pre-existing master state, predates wave 4 (W4-GUARD finding b)."
  },
  "targets": [
    "1) promote harness/verify/suite_baseline.json to the R31 two-leg tuple shape from the banked Q2 proposal, with real measured numbers for both legs (gate interpreter + shipping build), producers named",
    "2) the suite_baseline guardrail reports ok:true under R.R and K.7",
    "3) no checks.py logic edits - this is a data-shape promotion only"
  ],
  "acceptance": [
    {
      "predicate": "checks.py --task R.R shows suite_baseline ok:true; guardrail_violations no longer lists it; no other guardrail regresses",
      "evidence": "check"
    },
    {
      "predicate": "the tuple carries two legs, each with interpreter + producer + measured counts traceable to a real run (anchors in the receipt)",
      "evidence": "test"
    },
    {
      "predicate": "git diff touches suite_baseline.json and tests only - zero checks.py edits",
      "evidence": "check"
    }
  ],
  "deps": [],
  "readonly": false,
  "touches": [
    "harness/verify/suite_baseline.json",
    "tests/"
  ],
  "crucible_criteria": [
    "QUIT-RULE: if the promotion cannot pass without editing checks.py logic, STOP and post for_ruling - that is a bigger leg, not this one",
    "numbers in the tuple are OBSERVED from runs the leg executes or cites with anchors - a baseline with invented counts is the defect class R31 exists to kill",
    "house rule: unobtainable renders UNKNOWN, never zero and never an estimate"
  ],
  "spawn_classes": [
    "probe"
  ],
  "note": "Smallest leg of the wave; clears the last pre-existing red so wave-5 CRUX can demand an all-green R.R. COMMIT BEFORE RECEIPT."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-BASE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave5`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-BASE finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave5 W5-BASE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave5 W5-BASE`

## Receipt (completion contract)

**COMMIT BEFORE RECEIPT — hard order (CRX0, wave 4).** The receipt is written
LAST, after your named-file commit exists on your branch. Sequence: (1) commit
your product + notes files (named, never -A); (2) verify `git rev-list --count
<base>..HEAD` >= 1; (3) only then write the receipt, and state the observed
HEAD sha in it. A receipt at ahead:0 asserts commit-state that does not exist —
the exact claim-before-act defect this harness exists to kill.

Write `harness/notes/receipts/W5-BASE.json` **inside your worktree**:
`{{"leg": "W5-BASE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
