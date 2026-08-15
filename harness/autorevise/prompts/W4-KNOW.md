# W4-KNOW â€” retrieval repair: scout sees the corpus, keys carry context, answers carry internals, dense path can say not-found

You are a SYNAPSE wave agent on branch `wave4/know` in worktree `.claude/worktrees/w4-know`.
Model: Opus 4.8, dispatched by harness/orchestrate.ps1. This brief is complete;
if any part reads truncated, STOP and say so.

## Mission (validated work order)

```json
{
  "id": "W4-KNOW",
  "name": "retrieval repair: scout sees the corpus, keys carry context, answers carry internals, dense path can say not-found",
  "band": "BUILD",
  "source": {
    "doc": "docs/reviews/h22-context-knowledge-recon-2026-08-15.md",
    "anchor": "Finding 2 (retrieval broken at 1x) + Recommended sequence step 1; blueprint harness/notes/h22/BLUEPRINT.md Wave K1 LEG-KNOW. Verified anchors: knowledge.py:141 2-token bail to H21 prose (found=True 0.4-0.9 conf, 40/40 wrong); scout serving store shares zero rows with the 659 node entries (no id/searchable_text at promote); type-keyed index, 253/4345 stems destroyed, 239 internal-name collisions; 12-label cap hides 336/659 entries, internal names+channels never returned; :160 hardcodes Houdini 22.0.368 hint; corpus loads with zero build-stamp check"
  },
  "targets": [
    "1) promote emits id + searchable_text so scout_ingest stops silently dropping node entries - scout sees the corpus",
    "2) index keyed (context, type); ambiguous bare-type queries return a disambiguation list, never a silent _CONTEXT_RANK pick",
    "3) tool schema gains context and k parameters",
    "4) type-name intent test replaces the 2-token bail at knowledge.py:141 - sentence-shaped node questions route to the node path, never fall through to H21 prose as found=True",
    "5) responses carry internal parm names + channels, uncapped - kill the 12-label ceiling; the fields needed to actually set a parm are returned",
    "6) similarity floor on the dense path - below floor answers not-found instead of confident-wrong",
    "7) corpus load verifies a build stamp against the live symbol-table build, loud on mismatch; the :160 hardcoded .368 agent_hint dies with it",
    "8) conformance test pins the NEW contract at a runtime checkpoint - corpus-derived types guarded downstream of promote, closing the lint blindspot (finding 5)"
  ],
  "acceptance": [
    {
      "predicate": "scout query for a known node type returns the corpus entry with id and searchable_text populated (today: zero rows visible)",
      "evidence": "probe"
    },
    {
      "predicate": "the 5 pre-flight natural-language questions (incl. the Copernicus blur question) route to the node path or honest not-found - zero H21-prose found=True answers",
      "evidence": "test"
    },
    {
      "predicate": "bare noise query returns a disambiguation list spanning cop/sop/vop/chop; the pair (context=cop, noise) returns exactly the COP entry",
      "evidence": "test"
    },
    {
      "predicate": "an entry with more than 12 parameters returns all of them with internal names and channels; measured serve size reported per response",
      "evidence": "test"
    },
    {
      "predicate": "out-of-corpus query under the floor returns found=false; corpus with mismatched build stamp fails loud at load",
      "evidence": "test"
    },
    {
      "predicate": "scout_eval extended: P@1 >= 0.98 on type-name queries, disambiguation 1.00 on the 239-name collision set, served phantom 0.00, COP/LOP floor-clearing stays 1.00 - shipped corpus does not regress",
      "evidence": "check"
    }
  ],
  "deps": [],
  "readonly": false,
  "touches": [
    "python/synapse/routing/knowledge.py",
    "python/synapse/cognitive/tools/scout_ingest.py",
    "python/synapse/cognitive/tools/scout_eval.py",
    "harness/notes/rag_promote_h22.py",
    "tests/"
  ],
  "crucible_criteria": [
    "GATE B: consumer-fix review on knowledge.py is a human word before any merge - the receipt states the review surface explicitly",
    "no regression on shipped COP/LOP: scout_eval regression is release-blocking, re-run adversarially by W4-CRUX, not trusted from this leg's own numbers",
    "serve-size honesty: uncapping labels must not silently blow the measured ~495B mean / 966B max envelope - measured sizes in the receipt, UNKNOWN never estimated",
    "house rule: unobtainable renders UNKNOWN, never zero and never an estimate - no fabricated found=True anywhere on this leg's surfaces"
  ],
  "spawn_classes": [
    "probe"
  ],
  "note": "The value gate of the campaign: marginal value of new knowledge is negative until this lands. Every ING-<CTX> leg rides behind this via wave order."
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
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave4 W4-KNOW claim '{\"files\": [\"<paths>\"]}'`
   Then read open claims:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py claims wave4`
   If a peer holds an overlapping open claim: STOP, post a `block`, work
   another target until it releases.
2. **Findings** as you go:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave4 W4-KNOW finding '{\"claim\": \"...\", \"anchor\": \"file:line\"}'`
3. **Release** when done editing:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave4 W4-KNOW status '{\"release\": [\"<same paths>\"]}'`
4. **Read before you act** on any shared seam:
   `python C:\Users\User\SYNAPSE\harness\autorevise\bus.py read wave4 W4-KNOW`

## Receipt (completion contract)

Write `harness/notes/receipts/W4-KNOW.json` **inside your worktree**:
`{{"leg": "W4-KNOW", "status": "green|green_with_findings|blocked",
  "acceptance": [{{"predicate", "verdict": "pass|fail|UNKNOWN", "evidence"}}...],
  "findings": [...], "for_ruling": [...], "spawn": [...]}}`
`spawn[]` entries are mission-schema-shaped proposals; classes outside your
`spawn_classes` land `held` for Joe. The receipt closes your turn â€” hold there.
