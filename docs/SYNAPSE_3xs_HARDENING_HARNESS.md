# SYNAPSE — FIELD-READINESS / HARDENING HARNESS

### Investigation & hardening instrument · reconstruction, rebuilt on the v5 floor

> **Status:** ARCHITECT artifact. Design only, no implementation. Pre-FORGE.
> **What this is:** the release-bar instrument. It investigates and hardens an existing artifact (SYNAPSE) against one question: *would a senior pipeline TD at a mid-size VFX facility trust it in their Houdini pipeline — June 2026, inside-out SDK, not MCP.*
> **Lineage:** reframes the Science Harness (`v3` → `v4` → `v5`) under the facility-trust lens. The Floor/elevator discipline, the five-rung ladder, the allocation gate, and the provenance→exposure projection are inherited from `v5` and load-bearing. The K+S / AutoScientists × Harlo proposal (arXiv:2605.28655) is the distant root.
> **Target:** `JosephOIbrahim/Synapse`. Wire Protocol 4.0.0, ~110 MCP tools, memory Charmander. The doc/code conformance debt (banner reads `v5.8.0`/`21.0.596`; repo says `v5.10.0`/`21.0.671`; six disagreeing tool counts) is unchanged and still in force.
> **Release target:** Houdini 22 announcement, **June 22** (buffer June 25). **Today: June 14 — mid-Leg-2 (Track H floor closure).**
> **One-line thesis:** *the model is the author and judgment is the product; field-readiness is the proof a facility will actually run it. A TD trusts the floor, not the feature count.*

---

## RECONSTRUCTION NOTE — read first (honesty before utility)

This file rebuilds `SYNAPSE_FIELD_READINESS_HARNESS_v1.md` / `SYNAPSE_3xs_HARDENING_HARNESS.md`, both of which are lost. **It is a reconstruction, not a byte-recall.** It is synthesized from material that *does* exist: the uploaded `SYNAPSE_SCIENCE_HARNESS_v3/v4/v5.md`, the project record of the June-8 field-readiness reframe, and the CTO review backlog (C1–C12). Where the original made a specific call I can't recover, this rebuild makes the call the lineage implies and flags it. **Flip anything that doesn't match what you remember.**

Two honesty flags:
- **It rides the v5 floor, not v4's.** The original reframed v4. Rebuilding it on v5 (five-rung ladder, allocation gate, exposure projection) is a deliberate upgrade so you hold one current instrument, not a superseded fork. If you want the v4-era version verbatim, say so.
- **"3xs" is not in any source I have.** It is preserved as the filename you asked for. If it denoted a specific scope (a codename, a track count, a build tag), name it and I'll fold it in.

---

## WHY THIS EXISTS — the two defenses (read second; every rule serves one)

A long-horizon hardening loop fails in exactly two ways. For a **live Houdini integration**, both already have bloodied names in this codebase. If a rule below doesn't trace to one of these, it's ceremony — cut it.

- **Hallucinated completion → PHANTOM VERIFICATION.** Claiming SYNAPSE handles X when nothing probed the live H21.0.671 runtime to confirm it. *Already paid for, four times:* `hou.pdg.*`, `hou.secure`, `hou.lopNetworks()`, `hou.updateGraphTick()` — written against, all absent.
  → **First law: no finding is TRUE until `dir()` / `hasattr` against the live runtime confirms it.** Documentation and model suggestions are hypotheses, not facts.

- **Premature convergence → PHANTOM HARDENING.** Hardening a path the live transport never runs. *Already paid for:* `LosslessExecutionBridge` was the assumed safety mechanism; the live path is `hou.undos.group()` (37 sites). Hardening the bridge hardens a corpse.
  → **Second law: verify the actual execution path before you harden it. The path nothing runs is not a hardening target — it's a deletion candidate.**

The v4 field test proved the second law systemic: **the documented central safety layer is absent from every live transport**, so any invariant that references it references a mechanism that does not run. Tier 1 is re-founded on the handlers (the mechanism that *does* run), not the bridge — a correctness fix to the spec, not a caveat.

---

## THE FACILITY BAR — the trust contract (falsifiability, specialized)

K+S says: *state how you'd know it failed before you build.* Here, **"failed" is defined by the facility, not by Joe.** A senior TD deploying an inside-out agent into a 50–200-artist Houdini pipeline trusts it only if it survives ten questions. These are the **Tier 0 floor** — they hold regardless of capability, and **the Floor applies to the harness itself** (doc/code conformance is Tier 0: the map must match the building).

Each predicate is phrased as a **disproof**. A predicate with no disproof is decoration.

1. **Determinism** — *disprove:* the same request on the same scene yields a different mutation across two fresh sessions.
2. **Recoverability** — *disprove:* a mid-operation crash leaves the scene or `memory.jsonl` in a state no single action restores.
3. **Bounded blast radius** — *disprove:* one tool call mutates prims outside the stated scope, or a cook touches nodes it never declared.
4. **Provenance** — *disprove:* a committed change exists with no recorded author, decision, and verification rung.
5. **USD citizenship** — *disprove:* SYNAPSE writes to the stage in a way a non-SYNAPSE DCC, or Gold's schema conventions, would reject.
6. **Concurrency safety** — *disprove:* two clients (or a background cook + a foreground edit) race a counter, an undo block, or the Ledger.
7. **Cost bounds** — *disprove:* a turn can run unbounded tokens/$ with no ceiling the operator set.
8. **Version portability** — *disprove:* a fix verified on `21.0.671` graphical silently fails on `21.0.631` hython (separate site-packages) with no build-mismatch flag.
9. **Headless / farm readiness** — *disprove:* a path that works in the GUI session cannot run on a scheduler with no display.
10. **Loud failure** — *disprove:* a failure is swallowed — `fail-open`, an optimistic counter, a caught-and-dropped exception — instead of surfaced.

> **Tier 0 is the gate.** Capability (Track C) does not stack on a red floor. The TD trusts these ten before they trust a feature.

---

## THE REGIME — floor + search + the allocation gate

Three things, in order of authority. Conflating the first two was the v1 bug; missing the third was the v5 finding.

**1 · The floor (unconditional).**
> *An artifact may not assert what it has not verified.* A node type exists because `dir()` says so. A thing is "verified" because its eval signal fired **at the rung it claims**. An artifact has lineage because provenance was written. Applies to every output SYNAPSE emits, every mechanism the harness stands on, and every claim the harness makes about itself.

**2 · The search (the elevator — gated).**
> *A harness searches a space of hypotheses against a target, gated, recording what failed, promoting only what clears noise.* Two inputs make it well-defined: a **target** and an **eval signal noisy with unknown direction**. A target with no noisy eval signal is a **build**, not a search — putting it through the loop is overhead. This is the admission test.

**3 · The allocation gate (the bouncer — from v5).**
> *Before how-to-pursue (search vs build), ask whether the target deserves the substrate at all.* One question per target: **does it serve authoring / composition / proof?** Clear `admit` (a LOP authoring tool); clear `downstream` (`pixel_sort`, post-render pixel ops — two stops below the USD/LIVRPS substrate); a genuine middle (procedural-texture gen feeds materials feeds the render — substrate-*adjacent*) gets an `operator-override`. The cheapest gate; it prevents the most expensive mistake — grounding a surface the substrate doesn't want. This is the *fitting-a-technique-the-project-doesn't-need* pattern, caught at intake.

**Provenance is a five-rung ladder, not a binary.** `doc_only` → `V0_membership` → `V1_cook` → `V1_output` → `V1-degraded`. You cannot surface "exists" the way you surface "produces the intended output" with two rungs.

---

## THE LOOP — specialized for investigating an existing artifact

```
FRAME → PROBE-MAP → ( TRIAGE ⇄ HARDEN ⇄ VERIFY ) → COMPOSE → STRESS-AS-FACILITY → SHIP-TO-RELEASE
```

- **PROBE-MAP replaces SKETCH.** Because this investigates an artifact that already exists, **ground truth comes before construction.** The probe whose result changes the plan runs first. (D1/D2 resolve here as probe outputs, not armchair calls.)
- **TRIAGE ⇄ HARDEN ⇄ VERIFY** is the floor loop: score against the ten predicates, fix the lowest red, re-probe to confirm the rung rose. No fix is done until a *second fresh session* reproduces it clean.
- **COMPOSE** is Track C — dynamic workflows + long-running teams — and runs only on a green floor.
- **STRESS-AS-FACILITY** runs the ten predicates as a facility would: crash mid-op, race two clients, pull the bridge mid-session, run headless.
- **SHIP-TO-RELEASE** ships with H22 or surfaces a date-moving showstopper. Smaller-and-trustworthy beats feature-rich-and-unverified.

---

## THE PROBE LADDER — five rungs (membership ≠ cook ≠ output)

| Rung | What it proves | How |
|---|---|---|
| `doc_only` | a doc claims it | RAG / README — **a hypothesis, never a fact** |
| `V0_membership` | the symbol exists on the live runtime | `dir()` / `hasattr` against `21.0.671` via `ws://localhost:9999` |
| `V1_cook` | it executes clean | drive it through the live handler path; no exception |
| `V1_output` | it produced the *intended* output | the eval signal was the result, not merely "no error" |
| `V1-degraded` | verified on the fallback only | hython `21.0.631`, **build-mismatch flag set** — the caveat travels with the claim |

**No claim rises a rung without the probe for that rung.** Doc says it cooks ≠ it cooks. It cooked ≠ it produced the right pixels.

---

## TWO TEAMS — the honesty distinction (do not collapse)

- **The investigation runs SOLO.** ARCHITECT / FORGE / CRUCIBLE are **sequential identities in one Claude Code session** — Windows can't spawn nested `claude`, and `/resume` is the continuity mechanism. CRUCIBLE is a standing lens at every gate, not a final phase.
- **SYNAPSE's own agent team is the SUBJECT under the floor, not the investigator.** "Long-running teams" is a *capability being hardened* (Track C), modeled on the CTO review's own structure (8 dimension specialists → adversarial crucible → synthesis + completeness critic). Its **state** survives in USD even though its processes don't.
- **Collapsing the two is the hallucinated-progress trap this harness exists to kill.** The investigator does not get to claim the subject's capabilities as its own.

---

## THE LEDGER — what gets recorded (durable, five-rung, RFC-gated)

`verified_by` ∈ the five rungs above. Entry **kinds**, each first-class so nothing silently vanishes:

- **`VerifiedClaim`** — an emit-time struct: claim + rung + the probe that earned it. The Floor's emit-time gate (an MCP-server hook) rejects a claim asserting above its rung.
- **`SubstrateAssumption`** — a mechanism the harness stands on, with its current rung (e.g., "rollback = handler undo-wrapping," `V1_cook` pending a live test).
- **`DocConformance`** — a doc claim bound to code reality. The banner drift and the six tool counts are `DocConformance` violations, not footnotes (§ the conformance rule below).
- **`Deferred`** — a completeness-critic "unprobed" entry. Supply-chain (22MB vendored SDK, no CVE scan), the perf/scale envelope (JSONL grows forever), TOPS live-path rollback — recorded, none assumed safe.
- **`Allocation`** — the substrate-relevance verdict (`admit` / `downstream` / `override`). A target cannot be worked without one.
- **`Exposure`** (derived, never authored) — a *function of the rung* → the co-pilot exposure tier (below). Hand-authoring it reintroduces the drift the conformance rule abolishes.

**The conformance rule:** the map must match the building. A doc claim that disagrees with code is a **rejectable condition**, not a note.

**Durability:** the Ledger is **atomic + backed-up**. A long-running harness that loses its Ledger on a crash is the DR finding realized — and it is the same class as **Invariant Q** below.

**Schema location is RFC-ONLY (Michael Gold's zone):** where `VerifiedClaim`, `DocConformance`, `Deferred`, `Allocation`, and the `Exposure` projection live in USD (`customData` vs typed schemas) is **not a unilateral change.**

---

## TRACK H / TRACK C — the floor before the powers

**Track H (Harden) = close the floor.** Its targets are the **CTO review's 63 findings**, already allocated-in (the review *is* their substrate-relevance argument). Each gets an `Allocation{verdict=admit}` and a `thesis_locus`. The P0 / safety / lifecycle subset that gates everything:

- **C1–C3 · P0 — the memory-loss chain.** `memory.jsonl` can be silently and permanently destroyed (non-atomic write). The fix is governed by **Invariant Q — quarantine-before-touch**: the remediation itself must not be able to cause the loss it repairs. Atomic write + backup is the floor's *recoverability* predicate made concrete.
- **C10 / C12 · safety wiring inert.** Freeze-detection and the emergency-halt chain are dead after the v9 panel rebuild — a callable, *tested* `trigger_emergency_halt`, and the bounded-loop guard, are floor (*loud failure*).
- **C4 / C5 / C8 / C11 · lifecycle honesty.** Non-functional Stop, main-thread-blocking render handlers — *recoverability* + *concurrency*.
- **C6 · the one search item.** The ~2-second dispatch floor — the only finding whose direction is unknown, so it gets formal hypothesis tracks with predicted signatures **and a measurement before any fix** (it is search-shaped; the rest are builds).

**Track C (Capability) = the two powers, GATED on Track H.** Dynamic workflows (the admission gate generalized into a runtime-recomposed DAG, with a dynamism ceiling so it doesn't become framework-edit avoidance) and long-running teams (per-role allowlist, bounded loop, the tested halt). **The penthouse does not go up on a bad subfloor.** If Leg 2 overruns, Track C slips — the floor never does.

---

## PHASE 0 — probe first, then the tracks

```
Phase 0.0 · POSTURE PROBE (runs before everything; its outcome changes the plan)
            Confirm execute_python's live posture (ungated, full builtins, no
            consent, no cap — handlers.py) → decide D1. Confirm the bridge does
            not run the live path → re-found Tier 1 on the handlers (D2).

Track H ─ 0a  write + atomic + backup  (Invariant Q; C1–C3)
        ─ 0b  consent posture           (D1)
        ─ 0c  correctness               (S1 commit-first → S2 LOP-hash → S3 dependents)
        — at intake: run the allocation gate → record Allocation → only then decompose.

Track C ─ 0d  team-safety floor         (allowlist · bounded loop · tested halt — C10/C12)
        ─ 0e  workflow-engine floor     (dynamism ceiling · recompose-on-Ledger-events only)
        — GATED on Track H green.
```

**The reframed reading:** lay the floor under the harness's feet (Track H) before laying it under the team's and the engine's feet (Track C) — *and before any of it, confirm the floor is being laid under the right building* (the allocation gate).

---

## THE RELAY — to June 22

| Leg | Window | Anchor | Mile marker |
|---|---|---|---|
| **1 · Probe-map sweep** | Jun 8–11 | | Ledger seeded, floor scored, D1/D2 decided — **human gate** |
| **2 · Track H floor** | Jun 11–17 | ← anchor | Floor green under live probe, **P0 (C1–C3) closed**, halt-chain live |
| **3 · Track C compose + facility stress** | Jun 17–21 | | Teams floor-clean at the seams; the ten predicates survived or limits documented |
| **4 · Ship-to-release** | Jun 21–22 → 25 | | Ship with H22, or surface a date-moving showstopper |

> **You are here — June 14, mid-Leg-2.** Track H floor closure in progress. The panel v9 re-layout (its own harness) runs alongside on the panel layer; it does not touch the substrate Track H is hardening.
>
> **Gate discipline:** if Leg 2 overruns, **Track C slips — the floor never does.** Ship a smaller, trustworthy SYNAPSE before a feature-rich, unverified one.

---

## THE PANEL-v9 SEAM — they meet at the rung

The scaffold/hardening work and the panel v9 are the same project from two sides. **The harness is *how the work becomes trustworthy*; the panel is *show only trustworthy work*; they meet at the rung.**

The provenance ladder is also the panel's trust signal. The `Exposure` projection maps rung → what the co-pilot surfaces:

| Rung | Co-pilot exposure |
|---|---|
| `doc_only` | **not surfaced** — a promise, not work |
| `V0_membership` | **surfaced, marked unverified** — exists; not cook-verified |
| `V1_cook` | **available** — executes clean |
| `V1_output` | **trusted, foreground** — the eval signal was the intended output |
| `V1-degraded` | **surfaced, caveat shown** — live verification was unavailable |

The panel's tool/affordance visibility is a **render of the `Exposure` projection, not a hand-authored list.** A tool drops out when its rung falls; it foregrounds when a `V1_output` confirmation lands. The panel never has to *know* about provenance — it reads the projection. *The render is the proof; the rung is the proof's provenance; the panel shows proof, not promises.* (Exposure schema location: RFC-only, Gold's zone.)

---

## OWNER DECISIONS — the D-gates (explicit, never defaulted by the harness)

- **D1 · consent posture** for `execute_python` (blocks Phase 0b).
- **D2 · bridge fate** — promote-and-measure `LosslessExecutionBridge`, or retire-to-audit-only and rewrite CLAUDE.md §1's "only code path / cannot bypass." Until shipped, Tier 1 stands on the handlers.
- **D3 · two-tier Moneta** — immutable falsifiability tier + decaying tier, so the six siloed "what we learned" stores stop multiplying.
- **D4 · FORGE's verify stage / RSI metric** — the harness *is* the verify stage (`fixes_validated` gated by second-session reproduction); until wired, **stop emitting the optimistic counter.**
- **EmergencyProtocol fate + SEC-1 timing** — owner gates the harness refuses to default (per-command RBAC lands on *both* transports — they've drifted).
- **v5 additions** — allocation-criterion sharpness (define the substrate-adjacent middle by rule, not feel); exposure latency + demotion semantics (vanish immediately vs grey-out till session end); the schema-location RFC above.

---

## ONE-LINE SYNTHESIS

The regime is **two disciplines, one entry question, and two powers — all on one floor that faces both ways.** Verify before you assert; "verified" is earned at the rung it claims; provenance or it didn't happen; the map matches the building. **Allocate at intake** (does the substrate want this surface?), **harden on the floor** (the CTO findings, P0 first, Invariant Q on the memory chain), **compose only on green** (teams and workflows gated on Track H), **stress as a facility would**, and **surface by the rung** — where this harness and the panel v9 meet. A SYNAPSE that grounds the wrong surface flawlessly, hardens a path nothing runs, or shows a facility proof it cannot back, is standing on the bare subfloor this instrument was built to abolish. *The model is the author; field-readiness is the proof a facility will run it; a TD trusts the floor, not the feature count.*

---

*End of ARCHITECT artifact (reconstruction). The v5 FORGE specs are unaffected and remain the priority: Phase 0a (`synapse_write_file` + atomic/backup + the emit-time `VerifiedClaim`/`DocConformance` hook), the Phase 0c fixes (S1 commit-first), the Phase 0d team-safety spec (allowlist + bounded loop + tested `trigger_emergency_halt`), and the Phase 0.0 posture probe. Track H before Track C — the floor before the powers. Allocate at intake, verify on the floor, surface by the rung.*
