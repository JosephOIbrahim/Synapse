# W6-QUOTE â€” hardening 1/5: kill the injection class - audit and sanitize every uncontrolled string entering a quoted context

You are a SYNAPSE wave agent on branch `wave6/quote` in worktree `.claude/worktrees/w6-quote`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W6-QUOTE",
  "band": "BUILD",
  "class": "build",
  "name": "hardening 1/5: kill the injection class - audit and sanitize every uncontrolled string entering a quoted context",
  "source": {
    "doc": "harness/notes/receipts/",
    "anchor": "Joe word 2026-08-16: hardening pass from first principles - failure history becomes enforced gates"
  },
  "targets": [
    "1) consume the FORGE ledger from the bus (or proceed on the seeded classes if not yet posted). Sweep harness/**/*.ps1 and harness/autorevise/**/*.py for interpolation of mission/leg/branch/user strings into PS quotes, git arguments, here-strings, and Say/Notify lines - todays safeName fix (orchestrate.ps1 ~L240) is the pattern to generalize",
    "2) central helpers: a PS Sanitize-SQ function dot-sourced where needed and a python equivalent; replace ad-hoc fixes with them where surgical (never rebuild shipped code - wrap, do not rewrite)",
    "3) tests/test_harness_quoting.py: adversarial leg names (apostrophe, backtick, dollar, double-quote, em-dash, unicode) driven through orchestrate.ps1 -DryRun - the generated temp runner must parse clean via the PS Language Parser for every name",
    "4) lint pinned in tests: committed .ps1 under harness/ must not build inline -Command strings with unescaped interpolation; JSON writes BOM-free",
    "5) BUS MANDATE: post claim at start, findings to peers as you resolve shared facts, explicit RELEASE at close. W6-GATE is making this enforceable - model it."
  ],
  "touches": [
    "harness/",
    "tests/test_harness_quoting.py"
  ],
  "deps": [
    "W6-FORGE"
  ],
  "readonly": false,
  "crucible_criteria": [
    "every fixed site enumerated with before/after anchors; dry-run parser proof is first-hand stdout",
    "no touch of checks.py provenance region (W6-PROV owns it) or orchestrate close-state region (W6-GATE owns it) - coordinate overlaps on the bus",
    "receipt is own closing commit; RELEASE posted"
  ],
  "spawn_classes": [
    "probe"
  ],
  "acceptance": [
    {
      "predicate": "adversarial-name dry-run matrix parses clean for all metachar names",
      "evidence": "test"
    },
    {
      "predicate": "site audit table committed; zero remaining unsanitized mission-string interpolations",
      "evidence": "probe"
    }
  ],
  "note": ""
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-QUOTE claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave6`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-QUOTE finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave6 W6-QUOTE status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave6 W6-QUOTE`

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

Write `harness/notes/receipts/W6-QUOTE.json` **inside your worktree**:
`{{"leg": "W6-QUOTE", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
