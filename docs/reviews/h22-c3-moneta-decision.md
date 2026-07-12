# C3 — the "Moneta" decision brief

> **Date:** 2026-07-12 · **Author:** CTO-orchestrator session (main Claude Code, under blueprint authority).
> **Status:** RECOMMENDATION. One item reserved to Joe (brand disambiguation). No public surface was edited.
> **Trigger:** blueprint v2.0 §1 C3 rider, reconciled against shipped code during the v2 harness pass.

## The contradiction

The blueprint's **C3** ([`docs/SYNAPSE_H22_GAP_BLUEPRINT.md` §1](../SYNAPSE_H22_GAP_BLUEPRINT.md)) asserts:

> *"Moneta is the Nuke host, not a memory service … The whitepaper reassigns 'Moneta' to a decoupled
> vector-backed memory substrate. That is a confabulation. Moneta remains the planned Nuke inside-out host;
> the memory layer is the Cognitive Substrate / Cognitive Bridge."*

The harness encoded this as an enforceable rider (`h22-docsurgeon.md:18`, `h22-adjudicator.md` rule 6,
`h22-intake.js:35` confabulation-leakage attack, `h22-leg0.js:104`). **Executed literally, it would cut the
README lines that describe Moneta as a memory substrate — and those lines are true.**

## Evidence (tiered)

| Tier | Fact |
|---|---|
| **VERIFIED-CODE** | `python/synapse/memory/moneta_store.py:1` — *"MonetaBackedStore — SYNAPSE MemoryStore backed by the Moneta engine (Mile 4)."* Moneta **is** SYNAPSE's memory engine. `moneta_runtime.py` ships alongside it. |
| **VERIFIED-CODE** | `SYNAPSE_MEMORY_BACKEND=moneta` selects it (README:324); JSONL is the default, `moneta`/`shadow` opt in. |
| **VERIFIED-CODE** | `moneta_store.py:11,15-16` — content is embedded for vector recall, but **live recall is keyword** (`score_memories`, a parity re-impl of `MemoryStore.search`); *"vector recall is a deliberate later upgrade, measured against keyword recall in shadow first."* |
| **VERIFIED-REPO** | `README.md:322` — *"Moneta is a private, encrypted memory substrate (repo `JosephOIbrahim/Moneta`)."* `:348` — *"memory/ # Moneta-backed memory substrate."* |
| **VERIFIED-REPO** | `README.md:273` — *"Moneta/Nuke"* listed among portfolio hosts (the **only** Nuke-host framing on the surface). |
| **BLUEPRINT** | C3: "Moneta is the Nuke host, not a memory service." |
| **UNVERIFIED (whitepaper, via blueprint §3 row 3)** | "Moneta = memory service **with vector index**." |

## Analysis

The whitepaper's *specific* error was **"vector index"** — implying vector-similarity recall for SYNAPSE's
cognitive state. That framing **is** wrong and rightly rejected — it collides with **Non-Goal 6** ("vector
similarity for cognitive state"). But C3 over-corrected: it threw out the entire **"memory service" identity**
when only the *vector-similarity-recall mechanism* was the confabulation. Against shipped code:

- **"Moneta is a memory backend"** — TRUE. `moneta_store.py` proves it.
- **"Moneta's cognitive-state recall is vector similarity"** — FALSE today (keyword recall live; vector staged in shadow).
- **"Moneta is the Nuke host, not a memory service"** — FALSE as an exclusive claim; the repo `JosephOIbrahim/Moneta` **is** the memory substrate.

## Recommendation (CTO)

1. **Correct C3; do not enforce it.** As written it is factually wrong against `moneta_store.py`. A docsurgeon
   cut per the rider would make the README contradict shipped code — the exact failure the reconcile pass exists to catch.
2. **Keep C3's defensible core** = Non-Goal 6, restated precisely: *cognitive **state** is deterministic
   USD/LIVRPS, never vector similarity.* Moneta the **encrypted memory backend** is a distinct, legitimately-named
   layer whose **live recall is keyword**; the shadow-measured vector upgrade is a memory-layer concern, not a
   cognitive-state one.
3. **Guardrail fix (specified, held for confirm):** soften the C3 rider in `h22-docsurgeon.md:18` and
   `h22-adjudicator.md` rule 6 from *"Moneta is not a memory service"* to *"do not describe cognitive **state**
   as vector-similarity-recalled; Moneta the memory backend keeps its name."* **Held** until item 5 is ruled —
   these charters drive the autonomous team, and the correct wording depends on the two-Monetas question.
4. **Blueprint:** C3 is a *corrected load-bearing fact* → warrants a **v2.1** correction per §10 rule 2.
   Escalated to Joe; the harness does not self-revise the blueprint.
5. **RESERVED TO JOE (the one brand call):** Does a **separate** "Moneta" Nuke inside-out host actually exist
   (README:273 `Moneta/Nuke`), distinct from the memory-substrate repo `JosephOIbrahim/Moneta`?
   - **If yes** → two projects share the name; one needs a rename (brand decision, yours).
   - **If no** → README:273's Nuke-host framing is loose, and C3's "Nuke host" premise simply drops.

## Until ruled

- **No doc surgery on the Moneta lines.** They are substantially correct.
- The **safe G7 residuals proceed independently:** test-count badge `4,186` → ratchet floor **`4118`**
  (`README.md:364`; re-derive from `harness/verify/suite_baseline.json`), and add the loopback-only ingress
  sentence. Neither touches the Moneta question.

---
*First artifact under the review lane for the C3 reconciliation. Merge-to-main is the human gate; the v2.1
blueprint correction and the guardrail softening are yours to sanction.*
