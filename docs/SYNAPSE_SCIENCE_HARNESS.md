# SYNAPSE Science Harness — First-Principles Design

**Status:** ARCHITECT artifact. Design only, no implementation. Pre-FORGE.
**Purpose:** Define the harness from first principles, then bind it to the SYNAPSE Scaffold Report so the blocker-fix is the harness's own Phase 0 — not a thing it floats above.
**Lineage:** Generalizes the AutoScientists × Harlo proposal (arXiv:2605.28655) out of its Harlo instantiation and re-grounds it in SYNAPSE.
**Target:** `JosephOIbrahim/Synapse` — **v5.10.0**, Moneta memory backend shipped (flag-gated, default-off), 61 recipes, `houdini_execute_python` blocks **when the main thread is occupied** (root cause now known — see §5).

> **Read order:** §0 is the whole idea in one definition. §3 is the discipline that keeps it from sprawling. §5 is where C lives inside A. If you have five minutes, read those three — and the **Re-grounding** note directly below, which is why §5 changed.

---

## Re-grounding (2026-05-31) — what events overtook, and why

The original artifact bound Phase 0 to a repo snapshot that the same session's work then changed. The **design (§0–§4, §6) is unaffected**; only the **Phase-0 binding** moved. The four corrections, with evidence — and the meta-point: the admission gate (§3) dissolved the flagship problem in real time, which is the gate working, not failing.

1. **Target snapshot.** Was "Protocol 4.0.0 / memory Charmander." Now **v5.10.0** with the **Moneta vector memory backend shipped** (PRs #13–#17). Consequence: the dead-end registry (§2) no longer needs a bespoke USD prim schema — it can persist into the Moneta backend or via the file path in correction #2.

2. **Phase 0a's *write path* is ~built; its *Floor hook* is not.** `synapse_write_report` + `cognitive/tools/write_report.py` are on `master` (PR #15): a handler-/server-thread write that **routes around `execute_python`** (no main-thread hop), path-confined, atomic (`tmp + fsync + replace`). That is **0a** (the write path): text-write done, **binary + multi-root path policy UNBUILT**. But the Phase 0a spec (`SCIENCE_HARNESS_PHASE0A_SPEC.md` §1, §8) split out **0a′ — the emit-time Floor hook** (a `CommandHandlerRegistry.invoke()` primitive wrapping every emit), which is **UNBUILT and the largest piece**. So 0a-the-write-path is ~80% done; 0a-the-regime is not — the hook dominates the remaining work.

3. **Phase 0b's hypothesis space collapsed → it is now a BUILD.** A read-only investigation traced the hang: `_handle_execute_python` wraps the *entire* script in `run_on_main` → `hdefereval` (`server/main_thread.py:105`, 30s timeout); a blocked main thread (modal/cook) hangs it while `ping` (no main-thread hop) stays alive. That **confirms T1** (main-thread dispatch), **weakens T2** (socket/queue is fine — the handler reaches dispatch), and reduces **T3** (GIL/background cook) to a *contributor to "main blocked," not a separate never-releasing lock*. Three competing causes collapsed to one known mechanism. By **§3's own gate, "fix `execute_python`" moved SEARCH → BUILD.** The known fix: don't marshal pure-Python / no-`hou` scripts to the main thread; add dialog suppression + a timeout fallback on the WS handler path (the daemon path already has dialog suppression; the WS path does not).

4. **Spike 2.4 is CLOSED.** §5 flagged the connection "as a hypothesis." The daemon↔main deadlock is **shipping** (`TurnHandle`, deadlock-pinned by 31 tests). So `execute_python`'s block is *related but distinct* — the WS-handler path, not the daemon loop. The "two views of one root cause" framing is retired.

**Net:** the harness debuts not on `execute_python` (now a build) but on the problem §3 still admits as a genuine search — the **APEX verify phase** (§6). §5 is rewritten accordingly; everything else stands.

---

## §0 — First principles

Strip AutoScientists to its load-bearing core and it is one thing:

> **A harness searches a space of hypotheses against a target, gated, recording what failed, promoting only what clears noise.**

It needs exactly two inputs to be well-defined:

- **Target** — the thing being changed. *(Harlo: the XGBoost program. SYNAPSE: a subsystem, or a single bug.)*
- **Eval signal** — how you know you improved. *(Harlo: organic accuracy. SYNAPSE: tests pass + behavior verified, or bug resolved.)*

**The harness is well-defined if and only if both inputs are defined.** This is not a style preference — it's the admission test (§3). A target with no noisy eval signal is a *build*, not a *search*, and putting it through the harness is pure overhead.

Everything else — roles, shared state, dead-end registry, promotion gate — is machinery serving that one sentence.

---

## §1 — Roles: formalize what you already run

The harness does not import a foreign role structure. It formalizes the MOE workflow already in use.

| Harness role | What it does | Your existing identity |
|---|---|---|
| **Analyst** | Proposes hypotheses, ranks by expected effect size | **ARCHITECT** — design, no mutation |
| **Experiment** | Executes one hypothesis, records result | **FORGE** — implementation |
| **Critic** | Filters proposals *before* spend; refuses promotion inside noise | **CRUCIBLE** — adversarial, fix-forward, never weakens the test |

Claude Code can't spawn nested processes, so these stay **sequential role identities in one session** — exactly as they run today. The harness adds nothing to the role model except a named loop around it. (This session ran 14 such role-identity agents across ARCHITECT/FORGE/CRUCIBLE on the Moneta work — the loop is already the working pattern, unnamed.)

**Critique-before-compute** is the rule that the Critic filters proposals *to kill weak ones before an experiment spends a cook*, not to reach consensus. This is CRUCIBLE applied one step earlier than usual — at proposal time, not just at test time.

---

## §2 — Shared state and the dead-end registry

The harness coordinates through SYNAPSE's persistence substrate, not a flat forum. Three persisted structures — collectively **the Ledger** (the name the Phase 0a spec, `SCIENCE_HARNESS_PHASE0A_SPEC.md`, uses for §2 as a whole):

**Champion** — the current best answer to the open question (the working predictor / the confirmed root cause / the verified recipe).

**Forum** — a structured proposal / result / critique record for the active question, cross-readable across hypothesis tracks.

**Dead-end registry** — Scaffold item #18:

```
DeadEnd
├── direction        : str    # what was tested
├── change_applied   : str    # the mutation made
├── measured_delta   : float  # effect on the eval signal
├── rejection_reason : str    # why it didn't earn promotion
├── seed / context   : str    # conditions, so it isn't re-walked blindly
└── timestamp        : int
```

No autonomy, no compute. Pure data. It maps directly onto your existing **banked rulings** (orchestrator hygiene rule #7; the `AfterLoad`-not-`AfterClear` finding; this session's CRUCIBLE dead-ends — e.g. "the protected-quota fallback silently demotes pins" → fixed). Those *are* dead-ends and confirmations recorded as durable state.

**Persistence path (re-grounded):** the registry no longer needs a fresh USD prim schema invented for it. Two substrates already exist on `master`: (a) **`synapse_write_report`** (§5 / correction #2) — a blocker-free file write; (b) the **Moneta memory backend** — typed, auditable, decay/consolidation-aware deposits with provenance. A `DeadEnd` is a deposit with a pinned `protected_floor` (it must not decay). Prefer Moneta; fall back to the file path where Moneta is default-off.

**Transparency payoff:** the registry is a coaching surface. SYNAPSE can say *"we tested whether the GIL hold during background cook causes the timeout — it's a contributor, not the lock"* instead of silently re-trying ruled-out directions.

---

## §3 — The admission gate (the anti-sprawl discipline)

This is the section that keeps A from becoming the thing you do instead of shipping.

**Before anything enters the harness, it passes the §0 test:**

```
target defined?  AND  eval signal is search-shaped (noisy, direction unknown)?
   ├── both yes  → admit to harness
   └── otherwise → it's a straight build. Hand to FORGE. Do NOT wrap it.
```

Run the Scaffold Report through the gate and it sorts itself **(re-graded 2026-05-31):**

| Scaffold item | Admit? | Why |
|---|---|---|
| `synapse_write_file` (write path) | **text DONE; binary + multi-root UNBUILT** | Shipped as `synapse_write_report` (PR #15). Separately, **0a′ the emit-time Floor hook is UNBUILT — the largest piece** (spec §1/§8). |
| Fix `execute_python` | **BUILD (was YES)** | Hypothesis space collapsed to one known mechanism (main-thread marshaling; see §5). No longer search-shaped — apply the known fix. |
| APEX agent + recipes | **partial → the debut** | *Which H21 APIs exist* is a `dir()` search → admit the verify phase. Recipes are builds. **This is now the harness's first genuine search (§6).** |
| Recipe confidence scoring | **weak** | "What function predicts recipe success?" is a small search. Admit if you want it; low stakes. |
| Full APEX→USD pipeline | **partial** | Failure-mode discovery is search-shaped. The pipeline build is not. |
| Memory→Bulbasaur, TOPS feedback, Solaris validator, COP↔Solaris, declarative builder, post-render hook, intent locking | no | Straight builds. FORGE work. The harness is dead weight on these. |

**The gate just dissolved its own flagship problem.** `execute_python` was "the one true science problem" until investigation collapsed three root causes to one — at which point §3 *correctly* re-classifies it as a build. That is the discipline working: the gate refuses to keep a science loop on a problem that stopped being a search. The debut shifts to APEX verify, which is still genuinely a search.

---

## §4 — Gating and invariants (SYNAPSE-native, not Harlo's)

The Harlo proposal gated experiments through its basal-ganglia motor spine and RED-kills-everything. **SYNAPSE has no human burnout state and no motor gate — do not import them.** Re-ground the gating in SYNAPSE's own hard invariants:

- **One mutation per experiment.** An experiment is one atomic script — your existing atomic-script rule, unchanged.
- **Idempotent guards.** Check-before-mutate on every experiment so a re-run is safe.
- **Transaction-wrapped with undo-group rollback.** A failed experiment rolls back clean.
- **Verify the API before you spend on it.** No experiment may touch an API surface unconfirmed by runtime `dir()` introspection. (This is precisely the APEX-verify debut: the gate *is* the harness's first search.)
- **Provenance on every decision.** Each promotion, rejection, and dead-end is written with its reasoning. The audit trail *is* the cognitive-substrate thesis pointed at SYNAPSE's own evolution. *(Originally "USD provenance"; correction #1's re-grounding retired the bespoke USD prim schema — the ratified substrate is JSON files via the write path, §4a.3.)*
- **Halt-and-surface, not RED.** The harness halts and hands back on: merge conflict, unverified API, failed transaction, or noise-band ambiguity. Mirrors the constitutional dispatch's explicit halt triggers.

**Promotion rule (noise-aware):** no new champion unless the measured gain clears the noise band, **confirmed on a second seed/context.** This is CRUCIBLE's never-weaken-the-test discipline as a promotion gate. The "second seed" form changes by target (§7): a fresh-session reproduction for a bug; a held-out query set for a learned scorer; a second independent `dir()` env for an API surface.

### §4a — Tier 0 (the Floor) and Tier 1 (the gated search)

*(Added 2026-06-02 to give the Phase 0a spec's vocabulary a home on disk. This formalizes a split that §3 and the invariants above already imply; it adds no new machinery — it names the two tiers and binds the spec.)*

The §0 admission test (§3) does not only sort work in or out of the harness — it cuts the regime into two tiers, and the invariants above belong to different ones:

- **Tier 0 — the Floor (unconditional).** The subset of §4 invariants that hold for **every emitted operation**, harness or not — *including straight builds that never pass the §3 gate*. The Floor is not opt-in and not the harness's alone; it is the substrate's standing guarantee. Its load-bearing member is **provenance on every decision** (§4a.3). Transaction-wrapped rollback and halt-and-surface are also Tier 0.
- **Tier 1 — the gated search (conditional).** What the §3 gate *admits*: the proposal → critique → experiment loop plus the noise-aware promotion rule above. Tier 1 layers **API-verify-before-spend** and **one-mutation-per-experiment** on top of the Floor. A straight build runs on Tier 0 only; a search runs on Tier 0 **and** Tier 1.

This is *why* the Floor must be enforced **below** the harness loop: a build that never enters Tier 1 still emits operations, and those still need provenance and rollback. Enforcement that lived inside the search loop would leave every straight build unprovenanced.

#### §4a.1 — What is unconditional (the Floor's content)

Of the invariants above, these hold for every emit regardless of tier: **transaction-wrapped undo rollback**, **provenance on every decision**, and **halt-and-surface on its rollback-class triggers** (merge conflict / failed transaction). By contrast, *API-verify-before-spend* and *one-mutation-per-experiment* are Tier 1 (they bind experiments, not every emit) — and so are halt-and-surface's *search-class* triggers, **unverified API** and **noise-band ambiguity**, which only exist inside the Tier 1 loop. So §4's halt-and-surface is itself split: rollback-class triggers are Tier 0, search-class triggers are Tier 1.

#### §4a.2 — The emit-time hook (where the Floor is enforced)

The Floor is enforced **structurally by the substrate, not by a role remembering to** — the principle CLAUDE.md gives Houdini mutations via the LosslessExecutionBridge ("agents are downstream"), applied to *every* emit, hou or not.

**Resolved placement (Phase 0a spec §8, ratified 2026-06-02):** a server-side gate at a shared `CommandHandlerRegistry.invoke()` primitive, through which all three handler-invocation sites route — **not** `handle()` alone. Batch fan-out (`_handle_batch_commands`) and the autonomy adapter (`_HandlerAdapter`) dispatch via `registry.get()` directly and bypass `handle()`; a `handle()`-only hook would leave batch sub-ops and every autonomy op unprovenanced. Full call-site map and argument: `SCIENCE_HARNESS_PHASE0A_SPEC.md` §8.

#### §4a.3 — Floor provenance

Every non-read-only emit writes **one immutable provenance record** — `{op, payload-digest, result-digest, sha256, ts, session, outcome, parent, origin}` — via the **blocker-free write path**: Phase 0a's `synapse_write_file` (§5), **never** `execute_python` (whose main-thread marshaling can be blocked exactly when the system is under load). Tier 1 Ledger records (§2) use the *same* write path under a different root key. This is the §4 "provenance on every decision" invariant made structural and given a substrate. **Interlock:** the Floor's enforcement depends on the Floor's write path, so Phase 0a (the write path) strictly precedes 0a′ (the hook) — spec §8.4.

---

## §5 — Phase 0: C lives here (the bootstrap interlock) — RE-GROUNDED

The original interlock — "the harness can't record findings because file I/O is blocked, unless its persistence routes around `execute_python`" — **has already resolved.** That persistence path was built this session.

```
Phase 0a  — synapse_write_file (write path)  [text DONE · synapse_write_report, PR #15 · merged]
              → handler/server-thread write, path-confined, atomic (tmp+fsync+replace)
              → routes around execute_python by construction (no main-thread hop)
              → UNBUILT: binary payloads + multi-root (non-reports-dir) path policy
Phase 0a′ — emit-time Floor hook             [UNBUILT · the largest piece]
              → CommandHandlerRegistry.invoke() wrapping every emit (3 sites + Dispatcher)
              → Floor provenance via the 0a write path; enforces Tier 0 (spec §8, §4a)
              → depends on 0a (the write path) — §8.4 interlock

Phase 0b  — fix execute_python              [BUILD, not a search — hypothesis space collapsed]
              → root cause is known: _handle_execute_python marshals the whole script to
                the main thread (run_on_main → hdefereval, 30s timeout); a blocked main
                thread (modal/cook) hangs it. T1 confirmed; T2 weakened; T3 a contributor.
              → the fix (FORGE, no harness): for no-hou / pure-Python scripts, dispatch off
                the main thread (as synapse_write_report already does); add dialog
                suppression + a timeout fallback on the WS handler path (the daemon path
                already suppresses dialogs; the WS path does not). Spike 2.4 is CLOSED, so
                this is the distinct WS-handler residual, not the daemon deadlock.
```

**The interlock the original doc wanted is satisfied, not pending:** C (the blocker-free write path) shipped first; the blocker (B/0b) is now a known build, not the harness's flagship run. The harness therefore debuts on the next item the gate admits as a real search — §6.

---

## §6 — Forward map (the harness's actual debut)

`synapse_write_report` is live, Spike 2.4 is closed, and the `execute_python` fix is a scheduled build. The harness's **first genuine run** is:

- **APEX verify phase → harness (the debut).** Run `dir()`-based API discovery for `apex::graph`, port conventions, node types as a search; record confirmed/absent surfaces to the dead-end registry; *then* FORGE builds recipes against verified APIs. This is exactly the hard "verify before you spend" gate, now mechanized — and it is genuinely search-shaped (direction unknown, the H21 surface diverges from training data, as the Spike 3.0 PDG audit already proved for `pdg.*`). Second-seed form: a second independent `dir()` environment / hython session.
- **Recipe confidence scoring → harness (optional, low-stakes).** Search for the scoring function that best predicts recipe success from invocation history. Admit only if you want it. Second-seed form: held-out query set / statistical noise band.
- **Everything else → FORGE, straight builds.** Memory→Bulbasaur, TOPS feedback, Solaris validator, COP↔Solaris bridge, declarative SOP/DOP builder, post-render hook, intent locking — plus the `execute_python` fix and the `synapse_write_file` binary/general-path residual.
- **Multi-team self-organization → deferred.** Only after a single-track loop is proven safe and useful on-device. This is the identity decision (co-pilot → co-pilot that also runs science). Don't pre-commit.

---

## §7 — Open questions for FORGE / the blueprint phase

Deliberately unresolved here.

- **Cadence.** Per-session, or a background cadence so foreground co-pilot work stays real-time? (SYNAPSE's anchor is less obvious than Harlo's Sunday — maybe post-render idle windows.)
- **Compute yield.** Per-cycle ceiling, and how an experiment cook yields to a foreground artist cook.
- **Registry surfacing.** How often the dead-end registry feeds back into a recipe response before it becomes noise.
- **Second-seed form per target.** Fresh-session reproduction (bug) vs held-out query set (scorer) vs second `dir()` env (API surface). Enumerate the forms; the promotion rule's *form* changes by target type.

---

## One-line synthesis

The harness is your MOE workflow with a named loop, a dead-end registry persisted via the already-shipped `synapse_write_report` (or the Moneta backend), and an admission gate that refuses to wrap straight builds in a science loop — a gate that just **dissolved its own intended flagship** (`execute_python` collapsed from a three-track search to a one-mechanism build) and so debuts instead on the APEX `dir()`-verify phase, the item that is still genuinely a search.

---

*End of ARCHITECT artifact (re-grounded 2026-05-31 against v5.10.0). Next, if greenlit: the FORGE spec for the `execute_python` fix (build) and the APEX-verify probe harness (the harness's first real search).*

*Addendum 2026-06-02: §2 named "the Ledger"; §4a (Tier 0/Tier 1 + the emit-time Floor hook + Floor provenance) added to bind the now-ratified Phase 0a spec (`SCIENCE_HARNESS_PHASE0A_SPEC.md`). Hook placement resolved there to a registry-invocation primitive, not `handle()`.*
