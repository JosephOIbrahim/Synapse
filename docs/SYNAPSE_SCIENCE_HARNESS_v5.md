# SYNAPSE Science Harness — First-Principles Design (v5)

**Status:** ARCHITECT artifact. Design only, no implementation. Pre-FORGE.
**Edition:** v5. v2 separated *verification* from *search* (the Floor / the elevator). v3 turned that discipline on the harness's own substrate (S1–S4). v4 turned it on what the harness *claims about itself* (doc/code conformance) and folded in two powers — dynamic workflows and long-running teams. **v5 is forced by a fourth field test that is the first one to look *outward*** — a first-principles design review of the Solaris/Copernicus knowledge-scaffold (`SYNAPSE_SOLARIS_COPERNICUS_SCAFFOLD_REPORT.md`). The prior three field tests audited what the harness emits, stands on, and claims. The fourth found a class none of them could: **a grounding design that was flawless at grounding and still misallocated — verifying the wrong surface.** v5 turns one face of the Floor outward, up to the substrate thesis and down to the panel.
**Supersedes:** `SYNAPSE_SCIENCE_HARNESS_v4.md`. v4's spine is kept and load-bearing (enumerated below); v5 is a diff, not a re-derivation.
**Lineage:** Generalizes the AutoScientists × Harlo proposal (arXiv:2605.28655), re-grounded in SYNAPSE. v4 formalized the CTO review's multi-agent structure as a harness capability; v5 formalizes the scaffold review's two transferable findings as harness invariants.
**Target:** `JosephOIbrahim/Synapse`. Wire Protocol 4.0.0, ~110 MCP tools, memory Charmander. The doc/code conformance debt (§4a.4, DOC-1) is unchanged and still in force.

> **Read order:** §0 + §0.9 (the new outward field test and the amendment it forces). Then §3 (the allocation pre-gate) and §8 (the exposure projection) — these are the two new organs. Then §2 (the Ledger changes that carry both) and §4a (the layered Floor). Five minutes: §0.9, §3 head, §8, the one-line synthesis.

---

## §0.9 — The fourth field test: the scaffold review (the first one that looks outward)

This is to v5 what §0.8 was to v4. Where §0.5 found emitted claims, §0.6 found assumed mechanisms, and §0.8 found doc/code drift — all **inward** audits of the harness's own integrity — the fourth field test reviewed a *design artifact* (the COPs/Solaris knowledge-scaffold) and found the harness's first **outward** blind spot.

### The master finding

**A grounding design can be flawless at grounding and still spend its verification budget on the wrong surface.**

The scaffold review confirmed the design was sound on its own terms — the *missing-arbiter* diagnosis was the correct, non-obvious reframe (writing more docs doesn't fix a system where good docs already exist and the code ignores them); the provenance lattice was the right architecture; the *never-assert-above-the-rung-you've-reached* rule is the `dir()`-hard-gate discipline generalized into a data structure. **None of that is in question.** The blind spot was orthogonal to grounding quality:

- The design proposed grounding **21 `cops_*` tools** — but **~18 of them are two stops downstream of the substrate.** The pipeline is geometry → USD/LOP → Karma → composite. The organizing thesis is that *USD/LIVRPS composition is the cognitive substrate* — that is the LOP layer. Copernicus operates on the render's pixels. Texture-generation tools (feed materials → feed the render) are substrate-adjacent; proof-polishing tools (`pixel_sort`, `analyze_render`, `temporal_analysis`) operate on output after the fact and are genuinely downstream — and the design had *already caught* that the downstream tools are hollow (advertise pixel/NaN/flicker metrics, only read `errors()`). The hollowness clustered exactly where substrate-relevance was lowest.
- The design treated COPs (its Phase 2) and Solaris (its Phase 3, "parallel, later") as **equal-standing tracks** — which contradicts the substrate thesis, under which the documented Solaris *substrate* gaps (Inherits/Specializes arcs, value clips, full point-instancer, RenderVar→Product wiring, Component Builder) are gaps *in the product itself*, and 18 unverified COP stubs are breadth.
- **The design made the allocation call by treating the surface as a given.** It answered *how to ground COPs* exhaustively and never asked *whether to ground all of COPs.* Grounding all 21 reflexively is the *fitting-a-technique-the-project-doesn't-need* pattern the constitution already names.

### The second finding (the fix's other half)

The same review surfaced the synthesis that supplies the correction: **the provenance rung is the panel's exposure signal.** A panel that exposes 21 tools where 18 are unverified or all-black is *chrome pretending to be work* — the opposite of the panel's own Pentagram-derived thesis (the work is the product; the chrome recedes; *trustworthy enough to walk away from*). The rung the harness already computes is exactly the signal the panel needs to decide what to surface. The scaffold and the panel are the same project, two sides; **they meet at the rung.**

### The structural consequence for the harness (the amendment, not a footnote)

The failure class generalizes past *emits / stands-on / claims-about-itself* into a fourth: **what the harness chooses to work on.** A harness can verify flawlessly and still misallocate. Two organs were missing, and they get *built*, not caveated:

1. **The admission gate (§3) decided *how* to pursue a target — search or build. It never decided *whether* a target is worth the substrate.** v5 adds an **allocation pre-gate** above the search-vs-build test.
2. **Provenance (§2) was inward-only — a Ledger fact, a CI latch, a constraint on what the team may assert. It is also the *outward* trust signal the product surfaces on.** v5 adds a **provenance→exposure projection** (§8).

Both organs need a finer provenance ladder than v4's flat `{V0, V1}` to function — you cannot surface "exists" differently from "cooks" differently from "produces the intended output" with two rungs. So v5 lifts the scaffold's granular ladder and its L0–L3 lattice and generalizes them off COPs (§2, §4a).

### Findings → home (nothing dropped, including what does *not* import)

| Review observation | Where it lands in v5 |
|---|---|
| COPs is two stops downstream; not all 21 tools deserve grounding; the design "treated the surface as a given" | **§3 allocation pre-gate** + **§2 `Allocation` Ledger kind** |
| The provenance rung is the panel's exposure signal; rung should determine what's surfaced | **§8 exposure projection** + **§2 `Exposure` projection** |
| Finer ladder needed — membership ≠ cook ≠ output; the flipbook/pixel rung is its own thing | **§2 `verified_by` rung scale** + **§4a.2** |
| The L0–L3 lattice (primitives / composition / operations / intent) is transferable off COPs | **§4a.1 layering** |
| The scaffold's exec-summary was more optimistic than its body ("just point it at COPs" vs three must-fixes of guard plumbing) | **Scaffold-specific — does *not* import.** A writing-discipline note on that artifact, not a harness change. Recorded here so it isn't mistaken for an omission. |
| Sequencing: ship the OpenCL fix first, make the allocation call, consider moving Solaris up | **Scaffold-specific execution order.** The general lesson — an allocation step at the head of target intake — lands in **§5**. |

---

## Δ from v4

Diff against the version you have, without re-reading it.

- **§0 gains a third *question*, not a third discipline.** v4's regime is two disciplines (the Floor; the search). v5 keeps the two intact and adds a gate that runs *before* admission: *is this target substrate-aligned at all?* It is a bouncer before the elevator-vs-stairs choice — not a new floor, not a new loop.
- **§2 Ledger — the rung scale refines, one new kind, one new projection.** `verified_by` ∈ `{V0, V1, V1-degraded}` refines to `{doc_only, V0_membership, V1_cook, V1_output, V1-degraded}`. New kind **`Allocation`** (the substrate-relevance verdict — first-class so a target can't be worked without one). New *derived* projection **`Exposure`** (rung → co-pilot exposure tier).
- **§3 — the workflow composer gains an allocation pre-gate.** Before the per-node search-vs-build test, a per-target test: admit / downstream-with-override / defer. Lightweight by construction.
- **§4a Floor — rule 1 layers onto L0–L3; rule 2 adopts the finer rung.** "Verified" must now name the rung *and the layer* it cleared (exists ≠ composes ≠ achieves-intent).
- **§8 added — the provenance→exposure projection (the panel bridge).** The harness's provenance becomes load-bearing for the UI. This is the seam between the harness and the panel v9 work.
- **§5 — an allocation step at each track's intake.** Not a new phase; a one-line gate where any target enters Track H or Track C.

**Kept intact and load-bearing (the v4 spine):** the two-discipline split and the search definition (§0); all three prior field tests (§0.5/0.6/0.8); the re-founding of Tier 1 on the **handlers, not the bridge** (§4b), with the S1 single-clean-`performUndo` commit as precondition (GIT-0); the team-execution invariants (§4c) and the per-role allowlist / bounded-loops / working-emergency-halt discipline; the workflow composer's **anti-sprawl guardrail** (recomposition triggered by Ledger events only); the two-track **Harden-before-Capability** dependency (§5); the **doc/code conformance** Floor rule and `_conformance.py` extension to values/magnitudes/mechanisms (§4a.4, DOC-1); the **fail-closed** principle; the SYNAPSE-native refusal to import Harlo's motor-gate / RED-burnout; the operator-RED-vs-team-stops distinction (§4c operator note); the **RFC-only Gold zone** for USD schema (§7). The bones are still yours.

---

## §0 — First principles (amended)

The harness is **two disciplines**, unchanged. v5 adds one **question** that runs before either discipline engages.

### The search (the elevator — gated) — unchanged

> A harness searches a space of hypotheses against a target, gated, recording what failed, promoting only what clears noise. Two inputs make it well-defined: a **target** and an **eval signal noisy with unknown direction.** A target with no noisy eval signal is a **build.**

### The floor (unconditional) — unchanged

> An artifact may not assert what it has not verified. Applies to every output SYNAPSE emits, every mechanism it stands on, and (v4) every claim it makes about itself.

### The allocation question (new — runs before admission)

> **Before the harness verifies or searches a target, it asks whether the target deserves the substrate's attention at all.** Substrate-aligned work (authoring, composition, and the render that is composition's proof) is admitted. Downstream work (post-proof polishing) is admitted only on an explicit, recorded operator override. Out-of-scope work is deferred, not worked.

This is **not a third discipline** — that would dilute the clean two-discipline regime, and a heavy allocation process becomes the very *framework-edit-as-avoidance* pattern §3 already guards against. It is a **precondition on entry**: one cheap question, asked once per target, recorded as an `Allocation` Ledger entry, then you are through to the Floor and (if search-shaped) the elevator.

### The v5 amendment, in one line

v2 floored what the harness **emits**; v3, what it **stands on**; v4, what it **claims about itself**. **v5 turns one face outward — it asks whether a target is worth the *substrate* before working it (up, to the thesis), and it makes the rung that gates assertion also gate what the co-pilot *surfaces* (down, to the panel). A harness that verifies the wrong surface flawlessly, or that hides its proof's provenance from the surface that trades on it, is failing outward what the Floor fixed inward.**

---

## §2 — Shared state: the rung scale, `Allocation`, and the `Exposure` projection

The harness coordinates through SYNAPSE's USD substrate (`agent.usd`). Champion, Forum, Workflow graph, and Ledger are unchanged in role (v4 §2). Three changes carry v5.

### The provenance rung scale (refined)

v4's `verified_by ∈ {V0, V1, V1-degraded}` collapsed three real rungs into `V1`. The scaffold review showed *membership ≠ cook ≠ output*, and that the strongest rung (a literal rendered pixel) is categorically different from "it cooked." The refined scale:

```
doc_only  →  V0_membership  →  V1_cook  →  V1_output         (+ V1-degraded, orthogonal)
(prose;       (exists per       (executes/    (the eval signal IS the
 backs         dir()/catalog)    cooks, eval   intended output: rendered
 nothing)                        fired, no     pixel, or bug reproduced
                                 errors)       then resolved on a fresh seed)
```

- `doc_only` makes explicit what v4 left implicit — a claim from prose backs **no** assertion. (The scaffold's whole point: docs that the code ignores.)
- `V0_membership` = v4's `V0`.
- `V1_cook` and `V1_output` split v4's `V1`. The distinction is load-bearing for both new organs: a "verified" claim about *executability* needs `V1_cook`; a claim about *output correctness* needs `V1_output`. `flipbook_pixel_verified` is the **render-domain instance** of `V1_output`; a reproduced-then-resolved bug under a fresh Houdini session is another instance. (Adapt the *form* to the target — §4b promotion rule, unchanged.)
- `V1-degraded` survives unchanged as the live-unavailable fallback, caveat stated.

### New Ledger kind — `Allocation`

The substrate-relevance verdict, made first-class so a target **cannot be worked without one** (the scaffold's "treated the surface as a given," made rejectable).

```
Allocation (LedgerEntry)
├── target        : str            # the surface/capability/question under consideration
├── verdict        : token  ∈ {admit, downstream, defer}
├── thesis_locus   : str            # which layer of the substrate this serves —
│                                    #   authoring / composition / proof(render),
│                                    #   or "downstream" / "out-of-scope"
├── rationale      : str            # one line: why this verdict, against the thesis
├── decided_by     : token  ∈ {gate, operator-override}   # downstream REQUIRES operator-override
└── verified_by    : token         # the allocation verdict is itself an artifact (usually V0)
```

### New projection — `Exposure` (derived, not authored)

A read-only view that maps each capability's **current rung** to a co-pilot exposure tier (§8). It is *derived* from the Ledger so it cannot drift from provenance — there is no authored exposure list to fall out of sync, only a function of the rung.

**Ledger violations the schema now surfaces (v4's five, plus v5's):**

6. **A target enters the Workflow graph with no `Allocation` entry, or one whose `verdict=downstream` lacks `decided_by=operator-override`** → violation. The allocation question cannot be skipped, and "downstream" can never be auto-admitted.
7. **An `Exposure` tier is *authored* rather than *derived*** — i.e., a capability is surfaced at a tier its rung does not justify → violation. Exposure is a function of the rung; hand-authoring it reintroduces the drift §8 exists to abolish.

> **`verified_by` is mandatory on every kind** (the floor as a schema constraint — unchanged). The `Allocation` and `Exposure` USD schema location is **RFC-only (Gold's zone)** — see §7.

---

## §3 — The workflow composer gains an allocation pre-gate

v4's composer decomposed a target into nodes and ran the per-node admission test (search vs build). v5 keeps that **per node** and adds a per-target **allocation pre-gate** at the head.

```
given a target:
  ── ALLOCATION PRE-GATE (new — once per target) ─────────────────
  substrate-aligned?  (serves authoring / composition / its proof?)
     ├── yes            → ADMIT      → record Allocation{verdict=admit}, proceed
     ├── downstream     → require explicit operator override
     │                     ├── granted → record Allocation{verdict=downstream,
     │                     │              decided_by=operator-override}, proceed
     │                     └── absent  → HALT-AND-SURFACE (do not work it)
     └── out of scope   → record Allocation{verdict=defer} + a Deferred entry; do NOT decompose
  ────────────────────────────────────────────────────────────────

  (admitted targets only) decompose into nodes; for each node:
      target defined?  AND  eval signal search-shaped (noisy, direction unknown)?
         ├── both yes  → SEARCH node (Tier 1, on the Floor §4a)
         └── otherwise → BUILD node  (FORGE, on the Floor §4a)
  wire edges; persist the DAG to the Workflow prim hierarchy; recompose on Ledger events only.

  nothing below the Floor. every admitted node is API-verified, provenance-recorded,
  barred from a false "verified," doc-conformant — and now, only worked if allocated-in.
```

### The pre-gate is lightweight by construction — and self-policing

The composer's anti-sprawl guardrail (v4 §3) applies to the allocation gate **itself**. Two checks keep it from becoming the next avoidance surface:

> 1. **The allocation question is asked once per target, at admission — never recurring.** It is a single recorded verdict, not a standing review the operator can tinker with. A second allocation pass on an already-admitted target with no new evidence is the avoidance tell, and the harness surfaces it the way the constitution surfaces a third framework edit in a day.
> 2. **`downstream` is the only verdict that stops flow, and it stops by *asking the operator*, not by deliberating.** The gate does not compute substrate-relevance with ceremony; it routes a one-line scope decision and records it. Ceremony here would re-create the exact failure (effort spent on the meta-surface instead of the work) that the scaffold review caught at the panel layer.

The substrate thesis is the gate's only criterion. It is not a place to encode taste — it asks one structural question (*does this serve authoring, composition, or the render that proves them?*) and admits, overrides, or defers.

---

## §4a — The Floor (Tier 0): layered onto L0–L3, finer rung adopted

The Floor is unchanged in force and reach (every artifact, every node, not gated by §3). Two rules absorb the scaffold's structure.

**1. API-verified-or-quarantined — now layered.** The verification the Floor demands applies across a named lattice, lifted from the scaffold and generalized off COPs:

| Layer | What | Verified by |
|---|---|---|
| **L0 — Primitives** | which node types + module APIs exist | catalog-membership vs a live `dir()`/`hou.nodeTypeCategories()` dump → `V0_membership` |
| **L1 — Composition** | the semantics that compose primitives (USD LIVRPS arcs; a kernel contract; a node-graph's cook) | `createNode(...)`, cook `force=True`, assert `not errors()` → `V1_cook` |
| **L2 — Operations** | parameterized recipes — a verified graph achieving an intent | green only if every node type is an L0 champion *and* its L1 cooks → `V1_cook`/`V1_output` |
| **L3 — Intent** | NL → operation/recipe + canonical doc | `KnowledgeIndex` + Moneta pointers |

The Floor's rule is unchanged — *never assert above the rung you've reached* — but it now also means **never assert above the *layer* you've verified.** "`copnet` exists" (L0/`V0_membership`) is not "`copnet` cooks with these parms" (L1/`V1_cook`) is not "this recipe renders the intended image" (L2/`V1_output`). Conflating layers is the failure the scaffold's *membership ≠ role-fit* rule named.

**2. "Verified" is a reserved word — now rung-and-layer aware.** The `VerifiedClaim` struct (v4 §4a.2) is unchanged except:

```
VerifiedClaim {
  eval_signal_fired : bool
  eval_signal       : str
  verified_by       : token  ∈ {V1_cook, V1_output, V1-degraded}   # doc_only / V0_membership may NOT back "verified"
  verified_layer    : token  ∈ {L0, L1, L2}                        # NEW — name what was verified
  artifact_path     : str    # in-repo; outside-VC path is itself a rejection
  against_build     : str
}
```

A claim of output correctness requires `verified_by=V1_output`; a claim of executability requires `V1_cook`. `V0_membership` backs only an existence claim, never a "verified" one.

**Rules 3 (provenance-or-it-didn't-happen), 4 (doc/code conformance), the self-consistency tail, the fail-closed principle, and V1-unavailable degradation are unchanged from v4 §4a.** DOC-1 (extend `_conformance.py` to values/magnitudes/mechanisms) remains the mechanization of rule 4.

---

## §8 — The provenance→exposure projection (the panel bridge) — NEW

The harness's provenance ladder is also the panel's trust signal. v4 used the rung inward only (CI, Ledger, assertion-gating). v5 projects it outward: **a capability's current rung determines whether, and how, the co-pilot surfaces it.**

| Rung | Co-pilot exposure | Rationale |
|---|---|---|
| `doc_only` | **not surfaced** | the co-pilot does not offer a capability it cannot back; a doc-only tool is a promise, not work |
| `V0_membership` | **surfaced, marked unverified** | offered with the rung shown ("exists; not cook-verified") — present, but honestly stamped |
| `V1_cook` | **available** | offered normally; it executes clean |
| `V1_output` | **trusted, foreground** | offered as a known-good move; the eval signal was the intended output |
| `V1-degraded` | **surfaced, caveat shown** | live verification was unavailable; the caveat travels with the offer |

This makes the Ledger **load-bearing for the UI, not just CI**, and it resolves the trust tension the scaffold review named: a panel exposing capabilities it cannot back is *chrome pretending to be work*; the rung is the gate that separates the two. **The render is the proof; the rung is the proof's provenance; the panel shows proof, not promises.**

**The seam with the panel (v9).** The scaffold and the panel are the same project from two sides — the harness is *how the work becomes trustworthy*; the panel is *show only trustworthy work*; **they meet at the rung.** Concretely: the panel's tool/affordance visibility is a render of the `Exposure` projection (§2), not a hand-authored tool list. A tool drops out of the panel when its rung falls (a conformance violation demotes it); it foregrounds when a `V1_output` Confirmation lands. The panel never has to *know* about provenance — it reads the projection.

> **Derived, never authored.** Per Ledger violation #7, the `Exposure` tier is a *function of the rung*, computed, not stored as an editable list. Hand-authoring exposure reintroduces exactly the doc/code drift the Floor's rule 4 abolishes — an exposure list would be one more artifact that can disagree with reality. The projection's USD schema location is **RFC-only (Gold's zone)** — §7.

---

## §5 — Phase 0: an allocation step at each track's intake

Tracks H (Harden) and C (Capability), and the **Track-C-gated-on-Track-H** dependency, are unchanged from v4. v5 adds one line at the head of each track's *target intake* — not a new phase:

```
At the point any target enters Track H or Track C:
   run the §3 allocation pre-gate → record an Allocation entry → only then decompose.

   Track H — its targets are the CTO review's 63 findings, already allocated-in
             (the review IS the substrate-relevance argument for them). The gate
             formalizes that rather than re-deciding it: each finding gets an
             Allocation{verdict=admit, decided_by=gate} with the thesis_locus noted.

   Track C — teams and the workflow engine get the SAME scope question. "Long-running
             teams" and "dynamic workflows" are admitted because they serve the
             authoring/composition loop (the team that produced the CTO review is the
             existence proof); any capability that does NOT must clear the gate or defer.
```

**The reframed reading.** v4: *lay the floor under the harness's feet (Track H) before laying it under the team's and the engine's feet (Track C).* v5 adds: *and before any of it, confirm the floor is being laid under the right building.* The allocation gate is the cheapest of all the gates — one question — and it is the one that prevents the most expensive mistake (grounding a surface the substrate does not want).

---

## §7 — Open questions for the blueprint phase (v5 additions)

v4's open questions stand (D2 bridge fate; egress classification; concurrency specifics; the dynamism ceiling; the self-consistency check; cadence/compute-yield; second-seed form; supply-chain/perf/TOPS-rollback `Deferred` entries). v5 adds:

- **Allocation-gate criterion sharpness.** The gate's single criterion (*serves authoring / composition / proof?*) is clean for clear cases (a LOP authoring tool: admit; `pixel_sort`: downstream). Define the boundary for the genuine middle — procedural-texture generation feeds materials feeds the render, so it is substrate-*adjacent*; is "feeds the substrate one hop downstream" an `admit` or an `operator-override`? Pick a rule, don't decide by feel.
- **Exposure projection latency and demotion semantics.** When a conformance violation demotes a tool's rung mid-session, does it vanish from the panel immediately, or grey out until the session ends? Immediate is honest but jarring; define it. Also: does `V1-degraded` foreground or background by default when the bridge drops mid-session?
- **`Allocation` / `Exposure` schema location — RFC-ONLY (Gold's zone).** Where the `Allocation` kind and the derived `Exposure` projection live in the USD schema — `customData` on the artifact prim, or typed schemas. This touches substrate conventions; **not a unilateral change.** Same constraint as v4's `VerifiedClaim`/`DocConformance`/`Workflow` placement.
- **Scaffold-specific items explicitly *not* imported (recorded so they aren't re-raised as gaps):** the scaffold's exec-summary-vs-body optimism gap (a writing-discipline note on that artifact); its concrete sequencing (ship the OpenCL emitter fix first, then allocate, then weigh moving Solaris ahead of COPs). Both are correct *for the scaffold*; neither is a harness invariant. The general lesson — allocate at intake — is the §5 line above.

---

## One-line synthesis

The regime is now **two disciplines, one entry question, and two powers — all on one floor that faces both ways.** The **floor** (verify before you assert; "verified" is earned; provenance or it didn't happen; the map matches the building) and the **search loop** (ridden only when search-shaped) are unchanged. v2 floored what the harness *emits*, v3 what it *stands on*, v4 what it *claims about itself* — three inward faces. **v5 turns one face outward**, because a first-principles review of the COPs/Solaris scaffold proved a grounding design can be flawless and still verify the wrong surface: so an **allocation gate** asks whether a target deserves the substrate before it is worked (up, to the thesis), and a **provenance→exposure projection** makes the rung that gates assertion also gate what the co-pilot surfaces (down, to the panel — where the harness and the panel v9 meet at the rung). A harness that grounds the wrong surface flawlessly, or that hides its proof's provenance from the surface that trades on its trust, is failing outward exactly what the Floor was built to fix inward.

---

*End of ARCHITECT artifact (v5). Next, if greenlit: the FORGE spec for the §2 rung-scale migration (`{V0,V1}` → the five-rung scale, with the `Allocation` kind and the derived `Exposure` projection — RFC the schema location with Michael Gold first); the §3 allocation-pre-gate spec (one recorded verdict per target, the operator-override path for `downstream`, the self-policing second-pass detector); and the §8 exposure-projection spec (rung → tier as a pure function of the Ledger, the panel render seam, demotion semantics). v4's Track-H Phase 0a/0b/0c specs are unaffected and remain the priority — the allocation gate and exposure projection are Track-C-shaped (they serve the panel and the team loop), so they sit behind Track H, consistent with the spine. Allocate at intake, verify on the floor, surface by the rung.*
