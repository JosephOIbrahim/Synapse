# SPEC — SYNAPSE RSI Loop-Closure

> **Status:** **RATIFIED** 2026-06-01 (the INGEST gate cleared; DELIBERATE open).
> **Source:** drafted FROM `SYNAPSE_RSI_AUDIT.md`'s verdicts, per the harness
> INGEST spec. The audit was read-only — it never stated the acceptance bar for
> the *whole effort*, so this gate is real, not ceremonial.
> **Date:** 2026-05-31 · **MODE:** SIMULATED TEAM · **Champion:** 0/6 loops at L2+.

---

## Outcome

The four one-liner loops (R / O / S / F) **compound across a real process
restart** — each both **persists (L2)** and **changes a later decision (L3)**.
FORGE's (E) `fixes_validated` **reflects reality** (set from an actual re-run,
not hardcoded) and its **corpus grows per-cycle** (entries with
`created_cycle > 0`, not all `0`). Convergence (C) is **at least specced, with a
working protected-immutable tier** that rejects overwrite and never decays.

The central finding the work must overturn: *every loop today dies at the
process boundary.* So the process boundary IS the bar.

## Acceptance Predicates

**General rule:** each one-liner loop passes **L2** (the closure gate). **R / O /
F** additionally pass **L3**. **S** is different: the audit marks science's
apply/close-loop "n/a — records, by design", and the harness SEED PLAN closes
Line S on **L2 only** — so **S's closure is L2**, with L3 a labeled *stretch*
notch, not a requirement (see the table note).

| Loop | L2 — survives a real restart | L3 — alters a LATER decision |
|---|---|---|
| **R** render-farm | a `record_fix_outcome()` FEEDBACK record survives restart and is reloaded by `_warmup_from_memory()` | a learned fix changes a later render's settings vs. the static `ISSUE_REMEDIES` baseline |
| **O** §16 observ. | `RecommendationHistory` reloads via `from_jsonl()` on a fresh process | the `(kind,target) ≥5×` escalation fires and surfaces in the panel vs. a cold (no-history) baseline |
| **S** science | a deposited dead-end / champion survives into the durable substrate and reloads **← S closes here (L2)** | *stretch, INGEST-proposed, not required for closure — see note* |
| **F** router | a promoted `_session_fast_path` is loaded from the substrate on a fresh process | after restart, `route()` short-circuits via the persisted fast-path — routing changes vs. a cold start |

> **Note on S's L3 (stretch).** The harness SEED PLAN and the audit both close
> Line S on persistence (L2) alone — the audit calls science's apply-half
> "records, by design". An L3 for S *would* read: a persisted dead-end, reloaded
> in a fresh process, makes a later `run_search` skip the known-absent surface
> (no re-walk) vs. a cold registry. That is an **INGEST-proposed** hardening
> notch, offered for ratification — **not** inherited from the audit the way
> R/O/F's L3s are. S's acceptance is **L2**.

**Refined predicates (the Outcome governs these, not the blanket L2+L3):**

- **E (FORGE build):** `fixes_validated` is set from an actual re-run (not the
  hardcoded `0` at `orchestrator.py:214`); the corpus demonstrably grows
  cycle-over-cycle; a runnable entry point exists. (Maps to L0/L1 for the
  executable stage + a persistence check that new corpus entries are present in
  the next cycle.)
- **C (convergence):** the effort-level floor is *"specced + a working
  protected-immutable tier"* (rejects overwrite, never decays). The stretch is
  the full subtractive migration with **system-level L2** (every loop survives
  restart on the unified substrate) and **L4** tier-integrity at STRESS.

**Restart-aware (binds every L2 above):** L2 is inherently a two-run check.
Write → kill the process → start fresh → confirm present + loaded — then
**replicate on a SECOND fresh process** before the notch counts. One restart is
a sample; two is a result.

## Out of Scope

- **Rewriting the pure-logic layers.** The audit found them well-factored: the
  science `Registry`, the advisor's `analyze()`, the render `ISSUE_REMEDIES`
  table, and FORGE's `classifier` / `corpus_manager` / `metrics`. Only their
  **persistence** is made pluggable.
- **New storage engines.** Moneta is the substrate. No new DB. Convergence is
  SUBTRACTIVE — delete bespoke append-logs, repoint at Moneta.
- **Anything the audit did not surface.** No scope creep beyond the six lines.

## Falsification Conditions

A predicate is **falsified** (the work is NOT done) if any of these hold:

1. **Gaming failure (L3 fail).** A loop that "persists" but never alters a later
   decision is **not closed.** Persisting records that nothing reads is not RSI.
2. **Protected-tier violation (item 6 fail / HALT).** A protected-tier record (a
   confirmed-absent API or a FORGE rule) that **decays or is overwritten.** The
   two-tier split is the spec, not an optimization.
3. **Inferred closure.** Claiming L2 from a single restart, or from an
   in-process L1 readback. If a real restart cannot be run in the environment,
   the loop is **carried-forward-with-gap**, never marked closed.
4. **Hallucinated progress.** Narrating parallel agents that are not running, or
   resuming from a champion notch that was never actually verified.

## Verification Strategy

Per predicate, the L-layer that checks it:

| Layer | What it proves | Applies to |
|---|---|---|
| **L0** well-formed + claim-check | the change parses/imports; the cited symbol exists; **the audit's file:line claim is confirmed** | every line, first |
| **L1** in-process loop | write a record, read it back in the SAME process — the path is connected (NOT closure) | R / O / S / F / E |
| **L2** across-restart **★THE GATE★** | write → kill → fresh process → present + loaded; **replicated on a second restart** | R / O / S / F; system-level for C |
| **L3** behavior-change | a persisted record demonstrably alters a later decision (guards the gaming failure) | R / O / F (S: stretch only) |
| **L4** two-tier integrity | protected tier rejects overwrite + never decays; decaying tier decays; concurrent writes don't corrupt | C, at STRESS |

**L2 is the definition of "closed."** L3/L4 are the hardening notches. The first
action on every line is **L0 claim-check** — confirm-or-falsify the audit
against live code before paying any execution cost. A falsified claim goes to
DEADENDS and reopens DELIBERATE for that line; it is never wired on the audit's
word alone.

---

### Flagged at the gate (for ratification — see `RSI_DEADENDS.md` §Provenance)

The protected-tier seed inherits **10 `nodetype` dead-ends** from
`apex_registry.jsonl`. Their `kind: nodetype` field **strongly indicates** they
are **post-fix corrected-probe** outputs (the `getattr` false-negative belonged
to the *earlier* `attr` probe, fixed by commit `1ac0b9e`) — but a same-session
note read the first run as getattr false-negatives, and the registry is
gitignored local run-data, so the tie-break is a **Line S L0** check, not an
INGEST call. On the corrected reading they confirm absence **as spelled** in the
H21 catalog — **not** capability-absence; the real APEX type names may differ
(the registry's own `context` hedges the namespacing/casing). Seeded
**CONFIRMED-ABSENT (as spelled)** with a `scope` caveat so they are never
over-read. **FYI at ratification (not a blocker):** you may instead hold them
PROVISIONAL until the L0 reconcile lands.
