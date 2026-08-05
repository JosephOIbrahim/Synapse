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

## Held - human gate, do NOT auto-dispatch

**H3b (cook-cancel).** The manifest note says both "RELEASED by Joe
2026-07-28" and "HELD by ruling - human release required." That is a
contradiction in the record. Re-confirm your own release intent before
it dispatches - one word from you resolves it; nobody else may.

---

## Guardrails for the AM (read once)

- Do NOT rewrite existing briefs. 17 exist at harness/prompts/. This
  file sequences them; it does not replace them.
- Do NOT fire Wave 2 before reading Wave 1 receipts. Evidence first.
- Do NOT dispatch H3b without re-confirming the release yourself.
- The autoresearch harness (last night) and the leg orchestrator are
  TWO engines: hython probes vs claude-code worktrees. Each has a lane.
  Use autoresearch for new Houdini-truth questions; use orchestrate.ps1
  for the legs on this board.

---

## M5 ARCHITECT BRIEF - the reconciler (BLOCKS)

Not on the legs board - this is the missing brief. M5 is the engine that
makes "basic Solaris setup" real: reads fixtures/solaris.basic.json,
makes /stage match it, no-ops on reask, never touches your nodes.
Oracle already exists: baseline sha 8bb05761, canonicalizer c2.

Four decisions need YOUR ruling before FORGE can run. Each has a
recommendation so ruling is fast - agree or override, then it builds.

**D1 - Ownership mechanism.** How does the reconciler know which nodes
are its own?
  a) network box membership (BLOCKS_solaris_basic)   <- RECOMMENDED
  b) name prefix convention
  c) spare-parm metadata stamp per node
Box: flat nodes stay native and editable, membership is queryable,
one gesture selects-and-deletes, persists in the hip. Note: provenance
stamping via USD customData is Michael Gold RFC territory - the box
avoids that zone entirely.

**D2 - Collision policy.** Artist already has a node named `camera`
in /stage, outside the box. Reconciler should:
  a) fail loudly with a named-collision report, touch nothing  <- RECOMMENDED
  b) adopt the artist node into the fixture
  c) auto-rename the fixture node
Fail-loud is the only option that never surprises. Adopt and rename
both silently change meaning.

**D3 - Delete scope.** On re-apply, what may the reconciler delete?
  a) ONLY nodes inside its own box, nothing else, ever  <- RECOMMENDED
  b) any node matching fixture names
This is the safety invariant. (a) makes "your nodes never touched"
structural rather than behavioral.

**D4 - Integration seam.** Where does apply_fixture mount?
  a) new tool through the Dispatcher, same port pattern as
     synapse_inspect_stage  <- RECOMMENDED
  b) panel-side helper outside the tool surface
Dispatcher keeps it on the one spine and makes M6 routing trivial:
the alias table resolves the phrase, calls the same tool, zero tokens.

**After ruling:** FORGE builds reconcile + apply (seed already exists:
_build_fixture_once in harness/autoresearch/probes.py). CRUCIBLE runs
F-1 (apply on clean -> 8bb05761), F-2 (apply/delete/apply -> same),
F-3 (apply on applied -> ops==0, hash unchanged) headless via the
autoresearch pattern. Then M6: the phrase table.

---

## AM execute sequence

```
0.  (optional) push this plan file if you want it on the remote first
1.  rule on H3b release + the four M5 decisions above  (~10 min)
2.  fire Wave 1 through orchestrate.ps1  (7 legs, parallel)
3.  coffee. protected.
4.  read the seven receipts
5.  dispatch Wave 2 in the listed order as evidence allows
6.  M5 FORGE+CRUCIBLE with the ruled contract
```

State capsule ends here. Everything above is on disk and committed;
nothing is in anyone's head.
