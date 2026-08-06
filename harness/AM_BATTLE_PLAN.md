# AM BATTLE PLAN - 2026-08-06

One file. Read top to bottom, execute. No re-derivation needed.

---

## Where you are

Last night closed clean: autoresearch harness built and proven (55 probe
answers, 0 failures), `solaris.basic` fixture verified across two hython
sessions, committed `1e13629f`, pushed, remote-confirmed via ls-remote.

**The evidence loop is closed. The product loop is not** - the fixture
exists but nothing builds it in a live scene yet (M5) and no phrase routes
to it yet (M6). M5 architect decisions are at the bottom of this file.

**The board:** 32 legs - 12 done, 3 held/superseded, **17 ready**.
Every ready leg already has its brief at `harness/prompts/<id>.md`.
This file is the SEQUENCE, not new briefs.

---

## Wave 1 - fire first: seven read-only scouts, fully parallel

All `readonly:true`, all `deps:[]`. Worst case is a bad finding in a
file - zero mutation risk. Dispatch via the native orchestrator
(`harness/orchestrate.ps1` reads legs.json); these are claude-code
worktree legs, not hython probes - use the native engine.

| leg  | one line | why now |
|------|----------|---------|
| H5   | hou.* deprecation sweep vs H22 reference | last night PROVED the method live: karmarenderproperties deprecated while probes said healthy. Feed H5 our evidence: `harness/autoresearch/runs/*/lop_truth_22.0.368.json` |
| H8   | ruling audit - 78 rulings, no second reader | positive control built in: must catch R48/R64/R58/R15 or the method is broken |
| V1   | Karma integer ID-AOV capture probe | gates the entire vision-mask harness; no per-pixel identity = no "only X changed" |
| RSI0 | is the self-improvement loop wired but never CLOSED | router "not initialized" in health report; demands evidence of EXECUTION |
| S0   | market / adoption forensic scout | goes ALONE by design; gathering after forming a view = confirmation, not evidence |
| I0   | nodes.zip structure + join key | I1 is gated on it; the join key is a FINDING (385 doc ids wrong as names) |
| E0   | cost truth - is T.1 a reduction program or a cache header | settles the PREMISE: 17,310 uncached vs ~1,731 effective if cached |

**Cross-feed:** H5 and I0 overlap last night's work. Point them at the
committed lop_truth evidence files - do not let them re-derive from zero.

---

## Wave 2 - writers: fire ONLY after Wave 1 receipts are read

The scout receipts may CLOSE some of these by evidence. Read first,
then dispatch in this order:

1. **RES** (residency - kill fake-hou) - it is the gate: H1 and H2's
   release condition. Nothing else unblocks until it lands.
2. **U1** (provenance union) - R91: authoring, not merge resolution.
   Supersedes LEDGER; four decided rulings are stranded until it ships.
3. **H6** (substrate truth) - moneta_available() is five claims, one
   measured. Writes moneta_runtime.py. H7 is gated behind it.
4. **H4** (panel finish) - two accent blues resolved at the SOURCE.
   Never dispatched because its brief lived in the wrong file. It is
   in the manifest now; it just runs.
5. **C1** (token benchmark) - THE SPINE. Flat-cost claim, arm B by
   serialization. Run it after E0 settles the cache question, not before.

Then gated follow-ons as deps clear: H1 (after RES), H7 (after H6),
S2 (after S0+S1... S1 is done), S3 (after S2), I1 (after I0).

---

## Held - RESOLVED 2026-08-06

**H3b (cook-cancel).** Joe re-confirmed live tonight. `state: ready` is the
operative field; the stale HELD text in its note is historical. It dispatches
with the board.

---

## Guardrails for the AM (read once)

- Do NOT rewrite existing briefs. 18 exist at harness/prompts/ (M5 now
  among them). This file sequences them; it does not replace them.
- ONE-GO MODE (ruled 2026-08-06): the orchestrator dispatches the whole
  ready board at once. Same-touches writers are serialized IN THE MANIFEST
  (H6 now deps U1 - the R91 fix), so parallel safety is data, not vigilance.
  The wave tables above remain as the READING order for receipts.
- H3b release re-confirmed by Joe 2026-08-06; it dispatches with the board.
- The autoresearch harness (last night) and the leg orchestrator are
  TWO engines: hython probes vs claude-code worktrees. Each has a lane.
  Use autoresearch for new Houdini-truth questions; use orchestrate.ps1
  for the legs on this board.

---

## M5 - RULED AND ON THE BOARD (2026-08-06)

Joe ruled all four decisions as recommended: **D1** box ownership
(BLOCKS_<fixture>) / **D2** fail-loud collisions / **D3** delete scope =
box members only / **D4** Dispatcher seam, discovered live. The full ruled
brief is `harness/prompts/m5.md`; the leg row is in legs.json, state ready,
deps none. It dispatches WITH the board - no morning decisions remain.

Oracle: fixtures/solaris.basic.json, baseline 8bb05761, canonicalizer c2.
Invariants F-1..F-5 headless. M6 (phrase routing) is the follow-on leg,
authored after M5's receipt lands.

The option-by-option architect discussion that produced these rulings is
preserved in the session of 2026-08-05; the rulings above are the operative
record.

---

## AM execute sequence - ONE COMMAND

All rulings landed 2026-08-06. Nothing left to decide. The morning is:

```
cd C:\Users\User\SYNAPSE
.\harness\orchestrate.ps1 -DryRun    # optional 60s preview of the dispatch set
.\harness\orchestrate.ps1            # THE command. Whole board, one window.
git push origin rope/gate-a          # puts this plan + rulings on the remote
```

The orchestrator owns everything after that: dependency gating, worktrees,
launch, receipt monitoring, notification. What fires immediately: the seven
read-only scouts (H5 H8 V1 RSI0 S0 I0 E0), the writers (RES U1 H4 C1 V2
H3a H3b), and M5. Gated legs (H1 H6 H7 S2 S3 I1) release themselves as
receipts land. Merges stay human - Gate C, always.

Coffee is step 2 and it is protected. Read receipts in the Wave order
above when they arrive. That is the whole morning.

State capsule ends here. Everything is on disk and committed;
nothing is in anyone's head.
