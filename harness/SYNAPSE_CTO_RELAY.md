# SYNAPSE â€” CTO RELAY

**Harness ID** `CTO-RELAY-01` Â· **Authored** 2026-07-25 Â· **Surface** ARCHITECT (chat) â†’ FORGE (Claude Code)
**F3** This document commits before any execution it governs.
**Mode** B â€” `drop.json` present: H22.0.368 / py3.13.10 / usd0.26.5 / pyside6.8.3
**Baseline** `master @ e4b5916` Â· working tree clean but for `CLAUDE.md` + 15 untracked `docs/*.txt` Â· `0/0` vs origin Â· **0 open PRs**

---

## 0 Â· The variable being reduced

    H  =  (number of times the run stops and waits for a human)  Ã—  (cost per stop)

Reducing `H` is **not** removing human authority. Three gates never automate:

    GATE A   architecture ruling
    GATE B   drop.json MODE Aâ†’B flip
    GATE C   merge to main

`H` falls by removing *verification labour between* gates. Three mechanisms:

1. **Every check is an oracle.** If a human would look at it, write something that looks at it
   instead. `harness/verify/checks.py` already holds 80 check functions â€” extend that vocabulary,
   never bypass it.
2. **Decisions batch.** No leg stops to ask. Everything needing Joe accretes into ONE ruling
   block (Â§5), delivered once at the end of the run.
3. **The run survives its own context.** A leg that dies mid-flight resumes from its receipt,
   not from zero.

### The real constraint â€” why agent teams, precisely

`python/synapse` is **214,093 LOC across 1,259 files**; `_vendor` is 131,921 of that.
No single agent context holds this codebase.

> **Subagents here are a context-isolation device, not a parallelism device.**

A specialist opens a clean window, reads deep, returns a receipt â‰¤2KB, and its context is
discarded. The ORCHESTRATOR holds receipts only. It never reads source. This is what makes the
harness *long-running*: the orchestrator's context grows by ~2KB per leg instead of ~40KB.

---

## 1 Â· Standing orders

- **Probes beat memory.** Every `hou.*` symbol confirmed by live `dir()` against 22.0.368 before
  code is written against it. Quarantined absences are never re-litigated.
- **Commandment 7.** Test count strictly increases or holds. Fix forward. Never weaken, skip,
  `xfail`, or delete a test to make a leg green. A red leg is a finding, not a failure.
- **Truth labels.** Every load-bearing claim carries `VERIFIED-RUNTIME` / `VERIFIED-STATIC` /
  `VERIFIED-WEB` / `VERIFIED-DERIVED` / `UNVERIFIED` plus a `file:line` anchor.
- **Drift log.** When reality contradicts this document: STOP the leg, append to
  `harness/notes/cto_relay_drift.md`, resume only if the contradiction is cosmetic. Structural
  contradiction escalates to Â§5.
- **The deny-list is a fence, not a suggestion.** `harness/agent-settings.json` governs.
  `shared/bridge.py` stays human-authored â€” it is the S.2 security boundary.
- **No leg begins before the prior leg's receipt is written.**
- **No leg opens a PR.** Legs land on `feat/cto-relay-01`. Merge is GATE C.

---

## 2 Â· The team â€” use the roster that already exists

**Do not invent agents.** `.claude/agents/` holds thirteen purpose-built specialists. This relay
dispatches them. The evidence chain they already encode is: **map â†’ candidate â†’ probe â†’ build â†’
attack â†’ adjudicate.**

    ORCHESTRATOR (main thread) â”€â”€ holds receipts only. Never reads source. Never asks Joe.
         â”‚
         â”œâ”€ cartographer â”€â”€â”€â”€â”€â”€ read-only mapper. Inventories tools, routing tiers, seams.
         â”œâ”€ h22-gatewarden â”€â”€â”€â”€ gate-state oracle. ALLOW/REFUSE from drop.json + posture.
         â”œâ”€ prospector â”€â”€â”€â”€â”€â”€â”€â”€ candidates as contracts, each with a runnable dir() probe.
         â”œâ”€ assayer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ V1 hard gate. Live dir()/hasattr on the running build.
         â”œâ”€ h22-forge â”€â”€â”€â”€â”€â”€â”€â”€â”€ implementation. Refuses dispatch lacking a GATEWARDEN verdict.
         â”œâ”€ seam-hunter â”€â”€â”€â”€â”€â”€â”€ adversarial Solaris composition gate. Hunts composed regressions.
         â”œâ”€ panel-design-warden design-system enforcement on panel/. G3 strict audit.
         â”œâ”€ crucible â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ hostile by design. Attacks the finished artefact.
         â””â”€ sidefx-cto â”€â”€â”€â”€â”€â”€â”€â”€ vendor's-architect lens for second-order consequences.

### Leg â†’ agent binding

| Leg | Agents, in order |
|---|---|
| L0 GROUND | `h22-gatewarden` â†’ `cartographer` |
| L1 CONTEXT | `cartographer` â†’ `prospector` â†’ `assayer` â†’ `h22-forge` |
| L2 SOLARIS | `h22-forge` â†’ `seam-hunter` |
| L3 PANEL TRUTH | `cartographer` â†’ `panel-design-warden` (audit mode, read-only) |
| L4 PANEL SKIN | `panel-design-warden` |
| L5 RULING | `sidefx-cto` â†’ `crucible` (attacks the ruling block before Joe sees it) |

**Role bleed is the failure mode.** `cartographer` maps and does not prospect. `prospector`
specifies probes and does not run them. `assayer` answers only *does this API exist*.
`h22-forge` never self-certifies â€” `seam-hunter` or `crucible` certifies.

One agent per Task subagent. **Never nest.** Give each: its Â§4 leg block, the prior receipt,
nothing else. Load `rlm-navigator` for any read over 50k tokens â€” navigate the tree, do not
load it.

---

## 3 Â· Receipt schema â€” `receipt/v1`

Every leg terminates by writing `harness/notes/receipts/<LEG>.json`. This is the baton.

```json
{
  "leg": "L0",
  "schema": "receipt/v1",
  "started": "ISO8601",
  "ended": "ISO8601",
  "status": "green | amber | red",
  "suite": { "before": 4716, "after": 4716, "delta": 0, "failed": 0 },
  "commits": ["sha"],
  "findings": [
    { "id": "L0.F1", "claim": "â€¦", "truth": "VERIFIED-RUNTIME", "anchor": "path:line",
      "severity": "blocker | debt | cosmetic" }
  ],
  "for_ruling": [
    { "id": "L0.R1", "question": "â€¦", "options": ["â€¦"], "recommendation": "â€¦", "cost_of_delay": "â€¦" }
  ],
  "resume_token": "what the next attempt should skip if this leg is re-entered"
}
```

**`status` semantics.** `green` = oracle passed. `amber` = oracle passed, debt logged.
`red` = oracle failed; the leg STOPS and the orchestrator proceeds to the next leg carrying the
red forward. A red leg never blocks the relay â€” it blocks its own merge.

**`for_ruling` is the only channel to Joe.** Nothing else interrupts.

---

## 4 Â· The relay â€” six legs

    L0 GROUND â”€â”€> L1 CONTEXT â”€â”€> L2 SOLARIS â”€â”€> L3 PANEL TRUTH â”€â”€> L4 PANEL SKIN â”€â”€> L5 RULING
     ledger        LOP/COP        wiring          capability          chrome         one gate
     ARCHITECT     ARCH+FORGE     FORGE+CRUC      ARCHITECT           DRAFTSMAN      ORCHESTRATOR

---

### LEG 0 â€” GROUND Â· owner ARCHITECT Â· then FORGE

**Why.** There are zero open PRs. The premise that unfinished work lives in PRs is false; it
lives in the 80-task ledger and in root-directory entropy. Establish what is actually open.

**Work**
1. Reconcile `harness/tasks.json` (80 tasks, 58 MODE A / 22 MODE B, 13 human gates) against
   repo reality. For each task emit `done | open | stale | superseded` with a `file:line` anchor
   proving it. A task claiming a file that no longer exists is `stale`, not `open`.
2. Adjudicate **GitHub issue #3 "Installation issues"** â€” open since 2026-05-03, ~12 weeks.
   Reproduce against current master + H22 install path. Either fix, or close with a written
   reason. It is the only public-facing open thread on the repo.
3. Root hygiene census. 44 top-level directories. Classify each: `live | archive | delete`.
   Named suspects: `MagicMock/` (a leaked mock artifact written to disk by a test),
   `untitled.hip`, `_solaris_fix/`, `SYNAPSE-asm-*` Ã—4, `SYNAPSE-fx-*` Ã—3, `MagicMock`,
   `_cto_recon.py`. Do not delete anything in this leg â€” classify only.
4. Reconcile the 15 untracked `docs/*.txt` scratch files against `.gitignore`.

**Oracle**
```
pytest -q  â†’  failed == 0  AND  passed >= 4716
python harness/verify/checks.py --all  â†’  no new red
git status --porcelain | wc -l  â†’  recorded, not asserted
```

**Receipt** `L0.json`. `findings[]` must include one entry per `stale` task.
**Exit** ledger truth written to `harness/notes/ledger_truth.json`.

---

### LEG 1 â€” CONTEXT Â· owner ARCHITECT, then FORGE Â· **LOP and COP**

**Why.** U.6 measured LOP emission coverage at **39 of 218 live LOP types (18%)**, with four
confirmed-dead `createNode` literals on H22. COP has had no equivalent census. H22's centre of
mass moved into Copernicus; the port debt re-rank was ruled COP-first and never executed.

**Work**
1. **COP census (new).** Live-probe `hou.copNodeTypeCategory()` on 22.0.368. Emit
   `harness/notes/cop_catalog_live_22.0.368.json`: every COP type, its parms, its input arity.
   Then measure grounded coverage exactly as U.5/U.6 did for LOP. This number does not exist yet.
2. **LOP delta.** Re-run the U.6 probe. Confirm the 18% and kill the four dead literals.
3. **Per-context capability truth.** `harness/notes/context_capability_21.json` is pinned to H21.
   Rebuild it for 22.0.368 across SOP / LOP / COP. Any capability claimed for a context and not
   probed becomes `UNVERIFIED` and is stripped from the emission corpus.
4. **The improvement, derived â€” not invented.** Rank COP and LOP gaps by
   `(live type frequency) Ã— (grounded == false)`. Close the top 5. Do not close gaps that no
   real scene exercises; that is surface-area tax, and surface area is the thing being cut in T.1.

**Oracle**
```
every closed gap ships a test that FAILS on master and PASSES after
python harness/verify/checks.py --check lop_emission_grounded  â†’  coverage strictly up
python harness/verify/checks.py --check no_phantom_api  â†’  green
suite delta >= 0
```

**Receipt** `L1.json` with `before/after` coverage for LOP and COP as integers.
**Exit** COP has a coverage number for the first time.

---

### LEG 2 â€” SOLARIS WIRING Â· owner FORGE, certified by CRUCIBLE

**Why.** PR #48 landed the seam-gate and reported **13/13 attacks held, 2 cosmetic residuals**.
Two merges have landed since (`7e5cc7d`, `d92bb4b`, `0d78515`, `69149a7`, `e4b5916`). An
acceptance run is only true for the commit it ran against.

**Work**
1. Re-run the seam-gate acceptance on `e4b5916`. Not a re-read of the old result â€” a re-run.
2. Close the 2 cosmetic residuals from `harness/notes/` or promote them to `debt` with a reason.
3. **Wiring correctness, actually asserted.** For each of the six Solaris tools
   (`component_builder`, `scene_template`, `import_megascans`, `create_variants`, `set_purpose`,
   `tool_audit`) prove the emitted network is *connected*, not merely *created*:
   - every node has its expected input arity satisfied
   - the terminal LOP resolves to a composed stage without error
   - `hou.LopNode.stage()` returns a stage whose prim count > 0
   Only `component_builder` currently has a `validation/` verifier. Write the other five.
4. **CRUCIBLE pass.** Attack each tool: wrong context, existing-node collision, reserved prim
   paths, missing upstream, mid-cook interrupt. Emit the attack ledger.

**Oracle**
```
6/6 tools have a validation/solaris/verify_*.py
seam-gate acceptance == GO on e4b5916
CRUCIBLE ledger: 0 unhandled attacks (handled-and-typed counts as held)
suite delta >= +5  (five new verifiers ship five new tests, minimum)
```

**Receipt** `L2.json` including the full attack ledger.
**Exit** "Solaris networks wire properly" becomes a runnable assertion, not a belief.

---

### LEG 3 â€” PANEL TRUTH Â· owner ARCHITECT Â· **read-only, no chrome**

**Why.** `panel/` is 23,365 LOC across 71 files â€” larger than `server/` at 22,879. A surface
that big drifts from its backend silently. Before any restyle, establish what the panel can
actually do versus what the codebase can actually do.

**Standing ruling carried forward:** T.4 (*panel: product or reference implementation*) remains
**FROZEN â€” do not decide**. T.1 and T.2 will change what the panel fundamentally is. This leg
audits capability. It does not rule on product identity. Do not touch T.4.

**Work**
1. Enumerate every user-reachable affordance in `panel/` â€” button, action, menu item, hotkey.
   For each, resolve the call chain to its terminating handler.
2. Classify each affordance:
   - `LIVE` â€” reaches a handler that exists and is tested
   - `ORPHAN` â€” reaches a handler that does not exist, or raises `NotImplementedError`
   - `SILENT` â€” reaches a handler that returns success without doing anything
   `SILENT` is the dangerous class. Search for it deliberately.
3. Reverse the map. Enumerate dispatch-reachable capabilities with **no** panel surface.
   Cross-reference the 104 tools still on the WebSocket path.
4. Adjudicate the superseded `ui/` package (8 files, 1,076 LOC) sitting beside `panel/`.
   Live, or archive? Anchor the answer in imports, not intent.
5. Note for the record: `providers/` is 136 LOC against a documented claim of five swappable
   LLM engines. Measure the real number. Do not fix it here.

**Oracle**
```
harness/notes/panel_capability_matrix.json exists and is complete
every affordance in the matrix carries a file:line anchor
count(ORPHAN) and count(SILENT) are reported as integers, not prose
```

**Receipt** `L3.json`. **Zero commits to source in this leg** â€” ARCHITECT does not mutate.
**Exit** the matrix. L4 is forbidden from restyling anything the matrix marks `ORPHAN`.

---

### LEG 4 â€” PANEL SKIN Â· owner DRAFTSMAN Â· **chrome only**

**Why.** The panel keeps the Pentagram idiom but moves from generic Swiss-minimal toward the
specific logic of Pentagram's Cohere identity (Jody Hudson-Powell / Luke Powell, London).

**Scope fence.** DRAFTSMAN touches `python/synapse/panel/styles.py` and widget-level presentation
only. No dispatch logic, no routing, no handler edits. Anything the L3 matrix marks `ORPHAN` is
**removed from the surface, not restyled**. Restyling a dead affordance is how a panel lies.

**The reference, reduced to five rules**

1. **The title is not bold.** Cohere's wordmark carries identity through *form*, not weight.
   `SYNAPSE` drops to weight 400, tracking widens to ~4px, size holds. The mark does the work.
   Current state: weight 500 at 2.5px tracking â€” that reads as an application shouting its name.
2. **Cells, not boxes.** Cohere's root motif is the Voronoi tessellation. SYNAPSE already *has*
   a cell substrate â€” the node graph and the USD prim hierarchy. Use it natively: the bucket
   grid, the network peek, and the node chips become irregular-boundary cells rather than
   uniform rectangles. This is not decoration; it is the panel drawing what it operates on.
3. **Monolinear icons on a 24px grid.** One weight, one line, no fills, no dual-tone. Replace
   the current dot/square status affordances with 24px monolinear glyphs.
4. **Mono is for code, sans is for everything else.** Cohere uses mono strictly in code
   environments. The current panel spends mono on labels and metadata, which flattens hierarchy.
   Mono retreats to: node paths, tool names, versions, token counts. Everything else is sans.
5. **Gradient atmospheres, never dominant.** Texture enters through low-contrast gradient fields
   behind content, not through borders or fills. Keep the 0.5px hairline.

**Palette.** Hold the Houdini `UIDark.hcs` greys â€” that is the non-negotiable host constraint.
Cohere's structure is *natural tone + synthetic hue*. The existing signal blue `#8FB3D9` and
warm coral `#FF7759` already occupy the synthetic side. The natural side is missing: add one
muted green for `verified/ok` and one warm mushroom grey for inert metadata. Two accents remain
the ceiling for any single view.

**Work**
1. Read `harness/notes/receipts/L3.json`. Remove `ORPHAN` affordances from the surface.
2. Rewrite `styles.py` (705 LOC) against the five rules. Preserve every existing token *name* so
   nothing downstream breaks; change values, not the contract.
3. Title fix first, committed alone, so it is bisectable.
4. Screenshot-diff every panel view before/after into `design/cto_relay_01/`.

**Oracle**
```
grep -n "font.*[Bb]old\|setBold(True)" on the title path  â†’  0 hits
pytest tests/ -k panel  â†’  failed == 0
every token name present in styles.py before is present after  (assert, do not eyeball)
no import of routing/ or server/ added to panel/ in this leg
```

**Receipt** `L4.json`. **Exit** the panel looks like Cohere and tells the truth about itself.

---

### LEG 5 â€” RULING Â· owner ORCHESTRATOR

Concatenate every `for_ruling[]` entry from L0â€“L4 into **one** block:
`harness/notes/CTO_RELAY_01_RULING.md`.

Format per item: **question Â· options (â‰¤3) Â· recommendation Â· cost of delay Â· what unblocks.**
Rank by cost of delay, not by leg order.

Then STOP. This is the only stop. Do not merge â€” merge is GATE C, and GATE C is Joe.

---

## 5 Â· Expected ruling items (pre-seeded)

These are known before the run starts. The relay will add to them.

| # | Question | Recommendation |
|---|---|---|
| R1 | Issue #3 â€” fix or close? | Decide from L0's reproduction, not from age |
| R2 | Root hygiene â€” delete `MagicMock/`, `_solaris_fix/`, `SYNAPSE-asm-*`, `SYNAPSE-fx-*`? | Archive branch, then delete from master |
| R3 | `ui/` (1,076 LOC) beside `panel/` â€” archive? | Archive if L3 finds zero live imports |
| R4 | `providers/` at 136 LOC vs "five swappable engines" â€” fix the code or fix the claim? | Fix the claim now, the code after T.1 |
| R5 | T.4 panel ruling | **Stays frozen.** Do not decide until T.1 and T.2 land |

---

## 6 Â· Dispatch

```
Read harness/SYNAPSE_CTO_RELAY.md and execute it end to end. You are ORCHESTRATOR.
Spawn ARCHITECT, FORGE, CRUCIBLE and DRAFTSMAN as subagents per Â§2.
Do not ask me anything until Â§5. Branch feat/cto-relay-01. Begin at Leg 0.
```

**Resume**, after any interruption:

```
Read harness/SYNAPSE_CTO_RELAY.md and harness/notes/receipts/*.json.
Resume the relay at the first leg with no receipt. You are ORCHESTRATOR.
```


---

## 7 · Write targets — checked against the fence

`harness/agent-settings.json` denies `Edit(harness/state/**)`, `Edit(harness/run.ts)`,
`Edit(harness/agent-settings.json)`, `Edit(VERSION)`, `Edit(suite_baseline.json)`,
`Edit(token_ceiling.json)`, and `Bash(git push|git merge|rm -rf)`.

Every artefact this relay produces therefore lands in an **allowed** path:

| Artefact | Path | Allowed by |
|---|---|---|
| Leg receipts | `harness/notes/receipts/L*.json` | `Edit(harness/notes/**)` |
| Ledger truth | `harness/notes/ledger_truth.json` | `Edit(harness/notes/**)` |
| COP catalogue | `harness/notes/cop_catalog_live_22.0.368.json` | `Edit(harness/notes/**)` |
| Panel matrix | `harness/notes/panel_capability_matrix.json` | `Edit(harness/notes/**)` |
| Drift log | `harness/notes/cto_relay_drift.md` | `Edit(harness/notes/**)` |
| Ruling block | `harness/notes/CTO_RELAY_01_RULING.md` | `Edit(harness/notes/**)` |
| Solaris verifiers | `python/synapse/validation/solaris/verify_*.py` | `Edit(python/synapse/**)` |
| Panel styles | `python/synapse/panel/styles.py` | `Edit(python/synapse/**)` |
| New tests | `tests/**` | `Edit(tests/**)` |
| New checks | `harness/verify/checks.py` | `Edit(harness/verify/**)` |

**If a leg needs to write outside this table, that is a ruling item — not a permission to
widen the fence.** `harness/agent-settings.json` is itself deny-listed; the agent cannot edit
its own leash, and must not try.

`git push` and `git merge` are denied. The relay commits locally to `feat/cto-relay-01` and
stops. Push and merge are GATE C, and GATE C is Joe.
