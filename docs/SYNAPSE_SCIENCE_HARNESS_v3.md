# SYNAPSE Science Harness — First-Principles Design (v3)

**Status:** ARCHITECT artifact. Design only, no implementation. Pre-FORGE.
**Edition:** v3. The v2 separated *verification* from *search* (the Floor / the elevator) after a field test on the docs commit. v3 turns that same discipline back on **the harness itself** — because two things changed since v2 was written, and both are cases of the harness asserting what it hadn't verified.
**What forced v3:** (a) a **second field test** — a code review of the live `bridge.py` substrate — proved the harness *assumes* mechanisms (undo-group rollback, integrity hashing, blast-radius inference) that the substrate doesn't yet satisfy; (b) the v2's founding premise (`execute_python` BLOCKED) is **stale relative to the current repo** and must be re-confirmed live before it drives a phase.
**Lineage:** Generalizes the AutoScientists × Harlo proposal (arXiv:2605.28655) out of its Harlo instantiation, re-grounded in SYNAPSE.
**Target:** `JosephOIbrahim/Synapse`. Wire Protocol 4.0.0, 61 recipes, memory Charmander. **Premise under re-confirmation:** the v2 said `houdini_execute_python` is BLOCKED; the v5.8 repo's README says it works and the GUI-thread deadlock is fixed. §0.7 resolves this by probe, not by trusting either doc.

> **Read order:** §0 is the whole idea, once. §0.5 + §0.6 are the two field tests — the first about *emitted claims*, the second about *assumed mechanisms*. §0.7 is the stale premise. §5 is the bootstrap, now with the substrate fixes bound in. Six minutes: read those five.

---

## Δ from v2

Diff against the version you have, without re-reading it.

- **§0 compressed.** The floor/elevator split was stated five times across v2 (§0, §0.5, §3, §4, synthesis). It's stated **once** now, in §0, and referenced thereafter. The idea didn't change; the repetition is gone.
- **§0.6 added — the second field test (substrate audit).** The v2 closed the *output* hole (don't assert un-verified claims). It left open the *mechanism* hole: the harness's own Tier-1 invariants are asserted against a substrate that doesn't satisfy them. Four substrate findings (S1–S4), each tagged with the invariant it breaks.
- **§0.7 added — the stale premise.** `execute_python` BLOCKED is a 4.0.0-era claim; the v5.8 repo contradicts it. New **Phase 0.0**: re-confirm the blocker by live probe before Phase 0b assumes a deadlock to debug.
- **§4a hardened.** "Verified" is no longer defined only in prose — it's a **checkable emit-time contract** (the §7-v2 open question, now answered). A "verified" claim that doesn't carry the contract fields is rejected by the substrate, not by a role remembering to.
- **§2 Ledger schema cleaned.** The v2 schema was a nullable union — one prim, twelve fields, most null for any given `kind`. v3 binds fields to kinds explicitly, and adds a **`SubstrateAssumption`** kind so a relied-upon mechanism is itself a Ledger entry that must cite live verification.
- **§5 extended — Phase 0c.** The substrate-correctness fixes (the `bridge.py` defects) are bound into Phase 0 as blockers, because the harness can't *claim* "transaction-wrapped rollback" until rollback works. Bootstrap interlock unchanged.

Kept intact and load-bearing: the §0 search definition, the §3 admission test, the §5 bootstrap interlock, the §1 role mapping. The bones are still yours.

---

## §0 — First principles (stated once)

The harness is **two disciplines**, not one. Conflating them was the v1 bug; restating the split five times was the v2 redundancy. Here it is, once.

### The search (the elevator — gated)

> **A harness searches a space of hypotheses against a target, gated, recording what failed, promoting only what clears noise.**

Two inputs make it well-defined:

- **Target** — the thing being changed. *(Harlo: the XGBoost program. SYNAPSE: a subsystem, or a single bug.)*
- **Eval signal** — how you know you improved, and it must be **noisy with unknown direction.** *(Harlo: organic accuracy. SYNAPSE: tests pass + behavior verified, or bug resolved.)*

A target with no noisy eval signal is a **build**, not a search. Putting it through the loop is pure overhead. This is the admission test (§3).

### The floor (unconditional)

> **An artifact may not assert what it has not verified.**

A node type exists because `dir()` says so, not because a doc does. A thing is "verified" because its eval signal fired, not because a node got created. An artifact has lineage because provenance was written, not because everyone remembers.

This applies to **every output SYNAPSE emits** — search result, recipe, report, HDA, fix instruction. It is the project's "zero hallucinated APIs" premise, stated as a property of *output* rather than a habit of the author.

### The one-line correction

**The admission gate decides whether you *search*. It must never decide whether you *verify*.** Verification is the floor — always underfoot. Search is the elevator — ridden only when the problem is search-shaped. That's the whole regime. Everything below is consequence.

### The v3 amendment, in one line

The v2 applied the floor to **what the harness emits.** It did not apply it to **what the harness stands on.** §0.6 closes that.

---

## §0.5 — The first field test: emitted claims (why the floor exists)

A `/code-review` ran against the docs commit — 10 files, all `.md`/`.txt`, zero executable code. The standard angles (null deref, await, races) had nothing to bite on. The defects were **factual and self-contradictory claims** — the acute failure class for this project.

| # | Finding | Failure class | Should've been caught by | Why it wasn't |
|---|---------|---------------|--------------------------|---------------|
| **F1** | Fix instruction says create a `usdrender` ROP; real type is `usdrender_rop` | phantom API | the `dir()` verify gate | gate scoped to admitted experiments; a fix in a report is neither |
| **F2** | Recipe stamped *"Verified working"*; same-session diagnostic shows the scene was unrenderable (no camera, no ROP) | false promotion | noise-aware promotion gate | gate governed only the search champion, not a build's self-stamp |
| **F3** | Three reports, three conflicting math-shape HDAs, none canonical, all `.hda` outside version control | state loss / no provenance | USD provenance | provenance recorded harness *decisions*, not build *outputs* |
| **F4** | Key light "brightest" at +1.0 while rim is +1.5; impact "~50%" while the table shows ~80% | internal inconsistency | — | out of scope entirely |

**The pattern was total.** Every defect was an *assertion nobody verified*, and every one occurred in a **build** — the work §3 sends to FORGE. The v1 design left that work with no discipline. Hence the floor.

**The conduct note that became a rule.** The reviewer found the bridge unreachable that session (the stale-"connected"-banner pattern), so F1 couldn't be re-probed live — and the reviewer *refused to assert it as confirmed*, leaning on prior recon with the caveat stated. That is the correct behavior when live verification is unavailable. The floor codifies it (§4a, V1-unavailable).

---

## §0.6 — The second field test: assumed mechanisms (why v3 exists)

A `/code-review` then ran against the **live `bridge.py` substrate** — `LosslessExecutionBridge`, the component every mutation routes through, and the thing the harness's Tier-1 invariants quietly depend on. The first field test found the harness didn't discipline what it *emitted*. This one finds it **assumed what it stood on.**

Four findings, same shape as F1–F4 — each is the harness asserting an invariant the substrate doesn't satisfy:

| # | Finding (verified against `shared/bridge.py`) | Harness invariant it breaks | The Floor violation |
|---|----------------------------------------------|----------------------------|---------------------|
| **S1** | On composition failure, `performUndo()` is called *inside* the still-open `hou.undos.group()`, then the outer `except` calls `performUndo()` **again** — a double-undo that can pop the artist's *previous* action | §4b *"transaction-wrapped with undo-group rollback — a failed experiment rolls back clean"* | The harness asserts clean rollback. The substrate rolls back **twice**. "Rolls back clean" is unverified. |
| **S2** | `_compute_scene_hash` digests SOP intrinsics + `cookCount`; for a LOP op `node.geometry()` is None, so it collapses to *"did this node recook"* — it never hashes the composed stage | §4a.2 *"verified" requires the eval signal to fire* | For a **render recipe**, the integrity signal can't even detect that the stage changed. The eval signal the Floor depends on is **blind on the Solaris path** — the headline path. |
| **S3** | `_infer_stage_touch` traces `node.dependents()` (parameter/expression refs) to find downstream LOPs, but SOP→LOP data flow is `outputs()` + a SOP-Import path ref — a wired SOP chain feeding a SOP Import LOP is **missed** | §4b *"idempotent guards / check-before-mutate"* and the `touches_stage` blast-radius the integrity anchor keys on | The blast-radius inference has a **false negative on exactly the case it exists to catch** — a stage touch the harness believes it would flag. |
| **S4** | Consent's `_wait_for_decision` busy-polls with blocking `time.sleep` *inside* `execute_async`, stalling the FastMCP event loop for the full timeout (the PDG path correctly uses `await asyncio.sleep`) | §5 Phase 0b track **T1** (main-thread dispatch deadlock) | Not a violation — a **corroboration.** The deadlock class T1 hypothesizes is *present in the substrate*, with evidence. See §0.7. |

**Plus one, from the test strategy itself.** The harness's deepest rule is **V1 over V0** — live `dir()` beats documentation. The 3,168-test suite mocks `hou` via conftest, so it validates the Python logic against *encoded assumptions about Houdini's API* — which is **V0-equivalent.** S1, S2, and S3 are precisely the class a mock can't catch: the mock implements the assumed semantics, so the test goes green while the real API does something else. **The harness's V0/V1 distinction applies to its own test suite**, and the suite currently sits on V0 for the mechanisms that matter most.

**The lesson, stated as the v3 amendment was:** §0.5 closed the *output* hole. §0.6 closes the *mechanism* hole. Both are the same sentence — *assert only what you've verified* — applied at different levels:

- **F-series:** the harness emitted claims (`usdrender`, "verified") it hadn't checked.
- **S-series:** the harness relied on mechanisms (rollback, integrity, blast-radius) it hadn't checked.

A harness that disciplines SYNAPSE's outputs while trusting SYNAPSE's untested internals is standing on the same bare subfloor it was built to abolish. **Phase 0c (§5) fixes the floor under the harness's own feet before the harness runs.**

---

## §0.7 — The stale premise (re-ground before you run)

The v2 target line reads `houdini_execute_python BLOCKED`. That was true in the 4.0.0 era. The repo reviewed at v5.8 says otherwise: the README claims `execute_python` is the live mutation path (*"make a box → real geo node, confirmed in graphical Houdini 21.0.671, 2026-06-01"*) and that the GUI-thread consent deadlock was *"root-caused live and fixed."*

These cannot both be load-bearing. Under the Floor, the resolution is **not** to trust the newer doc either — it is to **probe the running build:**

```
Phase 0.0 — RE-CONFIRM THE BLOCKER  [live probe · minutes · gates everything after]
   → multi-line execute_python round-trip against H21.0.671:
       does print() return? does a multi-line dict literal survive transport?
       does a class definition exec in the Source Editor path?
   → record result to the Ledger as a Confirmation, verified_by = V1
   → branch:
       BLOCKED confirmed   → Phase 0b runs as the v2 designed (deadlock debug)
       WORKS confirmed     → Phase 0b's deadlock track is CLOSED; its budget
                             moves to Phase 0c (substrate correctness). The
                             "what holds the lock" search is retired with a
                             Ledger DeadEnd: "resolved upstream, v4→v5.8."
```

This is the harness's own discipline applied to its own premise: **a blocker is BLOCKED because a probe says so today, not because a doc said so in April.** Note also S4 — the consent poll *does* still block the event loop, so even if `execute_python` round-trips, a deadlock-class defect remains in the substrate. The honest reading is likely *"the artist path was fixed; a gated-path blocking call survives"* — but that is a hypothesis for 0.0/0c to confirm, **not asserted.**

---

## §1 — Roles: formalize what you already run

The harness formalizes the MOE workflow already in use; it does not import a foreign structure.

| Harness role | What it does | Your identity |
|--------------|--------------|---------------|
| **Analyst** | Proposes hypotheses, ranks by expected effect size | **ARCHITECT** — design, no mutation |
| **Experiment** | Executes one hypothesis, records result | **FORGE** — implementation |
| **Critic** | Filters proposals *before* spend; refuses promotion inside noise; **enforces the Floor at emit-time** | **CRUCIBLE** — adversarial, fix-forward, never weakens the test |

Sequential role identities in one session — Claude Code can't spawn nested processes, exactly as today.

**Critique-before-compute** still means CRUCIBLE kills weak proposals *before an experiment spends a cook* — one step earlier than usual, at proposal time.

**v3 widens CRUCIBLE's emit-time gate to cover assumptions, not just claims.** The v2 made CRUCIBLE gate the Floor when an artifact is *emitted* (catching the phantom `usdrender`, the false "verified"). v3 adds: when an artifact *relies on* a SYNAPSE mechanism — "this rolls back," "this is idempotent," "the integrity hash will catch it" — CRUCIBLE checks that the mechanism is a **`SubstrateAssumption` Ledger entry verified V1**, not folklore. S1–S3 were folklore. Under v3 they don't pass.

---

## §2 — Shared state and the Ledger

The harness coordinates through SYNAPSE's USD substrate, persisted in `agent.usd`.

**Champion** — the current best answer to the open question (working predictor / confirmed root cause / verified recipe).

**Forum** — a prim hierarchy of structured proposal / result / critique posts for the active question, cross-readable across hypothesis tracks.

**Ledger** — durable memory of what's settled. v2 widened the dead-end registry to carry confirmations and canonical pointers; v3 **cleans the schema** (it was a nullable union) and adds **`SubstrateAssumption`** so a relied-upon mechanism is itself a tracked, verified entry.

```
LedgerEntry (prim)
├── kind         : token  ∈ {DeadEnd, Confirmation, Canonical, SubstrateAssumption}
├── question     : str    # the open question this entry answers
├── verified_by  : token  ∈ {V0, V1, V1-degraded}   # ALWAYS required
├── timestamp    : int
│
├── DeadEnd ───────────── direction, change_applied, measured_delta, rejection_reason, seed/context
├── Confirmation ──────── direction, change_applied, measured_delta, artifact_path
├── Canonical ─────────── artifact_path, supersedes : path[]
└── SubstrateAssumption ─ mechanism, probe, holds : bool, scope/caveat
                          # e.g. mechanism="undo-group rollback is single + clean"
                          #      probe="composition-fail test in live H21; assert undo depth delta == 1"
                          #      holds=false  (S1)  → blocks any invariant that depends on it
```

`verified_by` is mandatory on **every** kind — there is no Ledger entry without a verification provenance. That single required field is the floor, expressed as a schema constraint.

**Two violations the Ledger now surfaces, not tolerates:**

1. **Two artifacts answer the same `question` with no `Canonical` pointer** → violation (the three math-shape HDAs; F3). Unchanged from v2.
2. **An invariant is asserted whose `SubstrateAssumption` is `holds=false` or absent** → violation (S1–S3). New in v3. The harness cannot claim "transaction-wrapped rollback" while the rollback assumption reads `holds=false`.

**Coaching surface:** SYNAPSE can now say *"the current shape generator is the Hypotrochoid one; the Fourier and Fermat reports are superseded"* **and** *"undo-group rollback is not yet single-and-clean — S1 is open, so 'reversible' is a Phase-0 target, not a current guarantee"* — instead of leaving you to discover either by surprise.

---

## §3 — The admission gate (the anti-sprawl discipline)

Unchanged from v2. It gates the **elevator**, not the floor.

```
target defined?  AND  eval signal is search-shaped (noisy, direction unknown)?
   ├── both yes  → ride the elevator (Tier 1 harness) — on the floor (§4a)
   └── otherwise → take the stairs (FORGE)            — on the floor (§4a)

   nothing is ever below the floor.
```

Running the Scaffold Report through the gate sorts it exactly as before: **one strong search** (`execute_python`, *if* §0.7 confirms it's still blocked), **two partial** (APEX verify phase, full pipeline failure-discovery), **one weak** (recipe confidence scoring), **eight builds.** The gate still refuses to cargo-cult a science loop onto a checklist.

**Where the substrate fixes (S1–S3) sort:** they are **builds — FORGE on the Floor**, not searches. Each has a defined target and a deterministic eval signal (the bug reproduces, then doesn't). No hypotheses to search. They go to Phase 0c, not the loop. *(Same instinct as your `hdefereval`-in-read-only-handlers ruling: no ceremony where the mechanism doesn't require it. A known fix is not a search.)*

---

## §4 — Invariants, in two tiers

### §4a — The Floor (Tier 0, unconditional)

Applies to **every artifact**, search or build. Not gated by §3.

**1. API-verified-or-quarantined.** No artifact references an API surface, node type, or method unconfirmed by live `dir()`/`hasattr` against the *running* build (H21.0.671). Phantom surfaces are quarantined, never emitted. *(Catches F1.)*

**2. "Verified" is a reserved word — and now a checkable contract.** v2 defined "verified" in prose. v3 makes it a structure the substrate enforces at emit-time. A claim of "verified" is **rejected unless it carries:**

```
VerifiedClaim {
  eval_signal_fired : bool   # the signal for THIS artifact's purpose, not node-creation
  eval_signal       : str    # what fired — "render produced intended image" / "bug reproduced then resolved"
  verified_by       : token  ∈ {V1, V1-degraded}   # V0 may NOT back a "verified" claim
  artifact_path     : str    # in-repo path; outside-VC path is itself a rejection (F3)
  against_build     : str     # the H21 build / session probed
}
```

Below the bar, the honest stamp is the specific lesser claim: *"node graph builds clean — not render-verified (no camera/geo/ROP on stage)."* A "verified" claim **is** a promotion; promotions clear the bar or aren't made. *(Catches F2. Answers v2's §7 "where does the check live": it's an MCP-server emit-time hook validating this struct — confirm the hook point in the blueprint phase.)*

**3. Provenance-or-it-didn't-happen.** Every artifact records, as USD provenance: producer (build/role), target build/session, **in-repo path**, and a canonical pointer if a prior artifact answers the same question (§2). An artifact whose file lives outside version control is itself a violation. *(Catches F3.)*

**Tail — self-consistency.** An artifact may not assert two incompatible facts (key "brightest" at +1.0 while rim is +1.5; impact "~50%" while the table shows ~80%). Same principle, applied to a claim against the artifact's own data. Lightweight tail, cost scales with stakes. *(Catches F4.)*

**V1-unavailable degradation.** When the live probe can't run — bridge unreachable, stale-"connected"-banner — verification **degrades to V0 (doc citation) with the caveat stated, and never silently stamps "verified."** `verified_by` records `V1-degraded`. Note the asymmetry with rule 2: V1-degraded can back a *cautious* claim but **never a "verified" one.**

### §4b — Search-execution invariants (Tier 1, gated)

Applies **only inside the search loop**, on top of the Floor. SYNAPSE-native — the Harlo proposal gated through a basal-ganglia motor spine and RED-kills-everything; **SYNAPSE has no human burnout state and no motor gate. Do not import them.**

- **One mutation per experiment.** One atomic script. Your existing rule.
- **Idempotent guards.** Check-before-mutate so a re-run is safe. *(S3 note: the inference this depends on has a false-negative class — Phase 0c hardens it before this invariant is trusted on the LOP path.)*
- **Transaction-wrapped with undo-group rollback.** A failed experiment rolls back clean. **Precondition, new in v3:** assertable only once `SubstrateAssumption("undo rollback is single + clean")` reads `holds=true`. Today it reads `holds=false` (S1). **This invariant is a Phase-0c target, not a current guarantee.**
- **Promotion rule (noise-aware).** No new champion unless the measured gain clears the noise band, **confirmed on a second seed/context.** For `execute_python` the "second seed" is a second reproduction under a fresh Houdini session, not a statistical band — adapt the *form* to the target (§7).
- **Halt-and-surface, not RED.** The loop halts and hands back on: merge conflict, unverified API, failed transaction, or noise-band ambiguity. Mirrors constitutional dispatch's halt triggers.

---

## §5 — Phase 0: the bootstrap, now with the floor under the harness

Phase 0 is no longer only *"give the harness a write path and fix the blocker."* It is **"make the substrate satisfy the invariants the harness assumes, confirm the premise, and give both tiers somewhere to write"** — in dependency order.

```
Phase 0.0 — RE-CONFIRM THE BLOCKER             [live probe · minutes]   ← NEW (§0.7)
   → is execute_python actually blocked at v5.8? probe, don't trust a doc.
   → result → Ledger Confirmation (V1). Branches Phase 0b.

Phase 0a — BUILD synapse_write_file            [straight build · ~days]
   → server-side write endpoint, path validation, UTF-8 + binary.
   → routes through the MCP server's own I/O layer, NOT Houdini's Python —
     so it does not depend on execute_python, by design.
   → the write-path for BOTH tiers:
       · Tier 1's Ledger (results, dead-ends, canonical pointers, SubstrateAssumptions)
       · Tier 0's provenance (every emitted artifact's lineage + VerifiedClaim structs)
   → prerequisite, not a hypothesis. No harness needed to build it.

Phase 0b — execute_python deadlock             [the one admitted search — IF 0.0 says BLOCKED]
   → Champion question: "what holds the lock that never releases?"
   → three tracks, critiqued before any cook is spent:
       T1  main-thread dispatch deadlock (call arrives mid-cook)  ← S4 corroborates this class
       T2  socket buffer / handler queues but never dispatches
       T3  GIL held by soho_foreground / background cook
   → each: idempotent probe, transaction-wrapped, dir()-verified (§4a.1)
   → promotion = fix reproduced clean on a second fresh session (§4b)
   → IF 0.0 says WORKS: this phase's budget moves to 0c; the search retires
     with a Ledger DeadEnd ("resolved upstream v4→v5.8"). S4 may still spawn a
     narrower track: "gated-path consent poll blocks the event loop."

Phase 0c — SUBSTRATE CORRECTNESS               [straight builds · FORGE on the Floor]   ← NEW (§0.6)
   → the harness can't CLAIM its Tier-1 invariants until the substrate satisfies them.
       S1  delete the inner performUndo; let the group close on raise, undo once outside.
           → flips SubstrateAssumption("undo rollback single + clean") to holds=true.
       S2  for LOP ops, hash lop.stage() content (flattened root+session export or a
           stable prim/attr digest), not SOP intrinsics + cookCount.
           → makes §4a.2's eval signal actually fire on the Solaris path.
       S3  trace outputs() for in-network data flow AND dependents() for cross-context
           refs; justify or drop the depth-3 cap.
           → removes the blast-radius false-negative §4b idempotency rides on.
   → each fix: bug reproduced (live), fixed, reproduced-clean on a second session.
     deterministic eval signal → these are builds, not searches (§3).
```

**The reframed reading of "C inside A":** `synapse_write_file` (0a) is still the nervous system of both tiers — Ledger *and* provenance. But Phase 0 now also **lays the floor the harness itself stands on** (0c) and **confirms the ground is where the map says** (0.0). The harness does not run a single experiment on a substrate whose rollback, integrity, and blast-radius it merely assumes. That is the v3 thesis as a sequencing constraint, not a slogan.

**Connection worth flagging (still a hypothesis):** the `execute_python` timeout, S4's blocking consent poll, and **Spike 2.4** (main-thread/daemon-thread deadlock) are very likely three views of one root cause. If so, Phase 0b's tracks, S4's narrower track, and Spike 2.4's three options (non-blocking `submit_turn` returning a Future / Qt-pumping while waiting / agent loop off the daemon thread) resolve together. *Stated as a hypothesis to verify in 0.0/0b, not asserted.*

---

## §6 — Forward map (after Phase 0)

Once the blocker's status is settled, the substrate satisfies its invariants, and both tiers can write:

- **APEX verify phase → search loop.** `dir()`-based API discovery for `apex::graph`, port conventions, node types as a search; confirmed surfaces → Ledger; *then* FORGE builds recipes against verified APIs. Your existing hard gate, mechanized.
- **Recipe confidence scoring → search loop (optional, low-stakes).** Search for the scoring function that best predicts recipe success from invocation history. Admit only if you want it.
- **Everything else → FORGE on the Floor.** Memory→Bulbasaur, TOPS feedback, Solaris validator, COP↔Solaris bridge, declarative SOP/DOP builder, post-render hook, intent locking. The search loop stays out of their way; the Floor does not. Every one is API-verified, provenance-recorded, barred from a false "verified." The recipe-report failure class (§0.5) is structurally impossible for floor-disciplined builds.
- **Test strategy → add a V1 tier.** From §0.6: a handful of `live`-marked tests pinning the load-bearing API assumptions (does `performUndo`-in-group misbehave; does `cookCount` update before the after-hash; does `dependents()` catch *your* SOP→LOP wiring). The 3,168 mocked tests prove the logic; these prove the contract. Small, high-leverage, and it moves the substrate's `SubstrateAssumption` entries from V0 to V1.
- **Multi-team self-organization → deferred.** Same call as Harlo: only after a single-track loop is proven safe and useful on-device. The identity decision (co-pilot → co-pilot that also runs science). Don't pre-commit.

---

## §7 — Open questions for the blueprint phase

Resolved since v2: *"where does the Floor's emit-time check live"* (an MCP-server hook validating the `VerifiedClaim` struct, §4a.2) and *"is `execute_python` still the blocker"* (Phase 0.0). Still open:

- **Cheapest viable self-consistency check (F4 tail).** Minimum that catches "key brightest but rim higher" and mismatched percentages without a heavyweight semantic checker. Probably a structured-claims pass, not prose analysis. Scope it.
- **Cadence.** Per-session, or a background cadence so foreground artist work stays real-time? (Harlo leaned Sunday for ADHD-anchoring; SYNAPSE's equivalent — maybe post-render idle windows.)
- **Compute yield.** Per-cycle ceiling, and how an experiment cook yields to a foreground artist cook.
- **Ledger surfacing.** How often dead-ends, canonical pointers, and `SubstrateAssumption` states feed back into a recipe response before it becomes noise.
- **Second-seed form per target.** Statistical noise band for a learned scorer vs. fresh-session reproduction for a bug — the promotion rule's *form* changes by target type. Enumerate the forms.
- **Where does the `VerifiedClaim` struct live in the USD schema?** customData on the artifact prim, or a typed schema? This touches substrate conventions — **RFC-ONLY (Michael Gold's zone), not a unilateral change.**

---

## One-line synthesis

The regime is two disciplines: a **floor** every SYNAPSE artifact stands on — *verify before you assert, "verified" is earned, provenance or it didn't happen* — and a **search loop** ridden only when the problem is search-shaped. v2 applied the floor to what the harness *emits*. v3 applies it to what the harness *stands on*: the substrate audit (S1–S3) proved the harness assumed mechanisms it never verified, and the founding `execute_python` premise is stale until a probe re-confirms it. So Phase 0 now lays the floor under the harness's own feet — fix rollback, hash the stage, trace the right edge, re-confirm the blocker — before a single experiment runs. A harness that disciplines a system's outputs while trusting its untested internals is standing on the same bare subfloor it was built to abolish.

---

*End of ARCHITECT artifact (v3). Next, if greenlit: the FORGE spec for Phase 0a (`synapse_write_file` endpoint + the §4a `VerifiedClaim` emit-time hook), the Phase 0c substrate-correctness fix specs (S1 first — five-line change, highest reversibility risk), and the Phase 0.0 blocker re-confirmation probe.*