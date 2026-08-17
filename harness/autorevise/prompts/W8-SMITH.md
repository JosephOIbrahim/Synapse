# W8-SMITH â€” smith: fork AUTOREVISE into BASTION harness v2 under harness/bastion/

You are a SYNAPSE wave agent on branch `wave8/smith` in worktree `.claude/worktrees/w8-smith`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W8-SMITH",
  "band": "BUILD",
  "name": "smith: fork AUTOREVISE into BASTION harness v2 under harness/bastion/",
  "source": {
    "doc": "harness/bastion/PROGRAM.md",
    "anchor": "HARNESS-V2-SMITH"
  },
  "targets": [
    "1) TASK 1 - resolve /rc: it is delivered by steward SendKeys and observed working across W6+W5 waves, but no rc.md exists under .claude (recursive) or the repo, and no doc mentions it. Interrogate: launch a scratch claude session in a worktree, capture /help and what typing '/rc' resolves to, document it. If unresolvable headless, escalate UNKNOWN with the transcript - never guess.",
    "2) Fork, do not rewrite: copy AUTOREVISE (mission_schema, compile_wave, make_control, bus, orchestrate pattern, arm template) into harness/bastion/, preserving every runner survival rule traced to its source file: hold-turn clause, CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0, AGENT_TEAMS env, detached Start-Process with pid capture, debom discipline.",
    "3) Schema v2: add optional skills[] (list of repo-relative or /mnt skill paths); compile injects them into the leg prompt brief. Add typed bus message kinds CLAIM/FINDING/HANDOFF/BLOCK/RELEASE with a validator on bus write.",
    "4) Arm template v2: steward arm/refresh with deadline past the wave horizon + /rc bake-in slot (fills from task 1 resolution).",
    "5) Self-test under stock pytest, pure Python, no hou: schema round-trip, compile of a fixture mission carrying skills[], bus kind validation. Skip is not pass.",
    "6) Receipt harness/notes/receipts/W8-SMITH.json; commit-before-receipt; your branch only.",
    "TOKEN DISCIPLINE: read anchors not trees; externalize evidence to your receipt early; cite file:line anchors, never file dumps.",
    "BUS MANDATE: post claim at start, post BLOCK immediately if /rc stays unresolved, explicit RELEASE at close."
  ],
  "touches": [
    "harness/bastion/"
  ],
  "deps": [],
  "readonly": false,
  "crucible_criteria": [
    "no phantom surface: every carried runner rule traced to its source file, never memory",
    "unobtainable renders UNKNOWN, never zero, never estimate"
  ],
  "spawn_classes": [
    "probe"
  ],
  "acceptance": [
    {
      "predicate": "v2 fork complete with skills[] + typed bus + steward-arm clause; pytest self-test green, skip is not pass",
      "evidence": "test"
    },
    {
      "predicate": "/rc resolved and documented, or UNKNOWN escalated with interrogation transcript",
      "evidence": "check"
    }
  ],
  "note": "no W8 leg depends on smith; v2 serves the exec waves"
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave8 W8-SMITH claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave8`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave8 W8-SMITH finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave8 W8-SMITH status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave8 W8-SMITH`

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

Write `harness/notes/receipts/W8-SMITH.json` **inside your worktree**:
`{{"leg": "W8-SMITH", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
