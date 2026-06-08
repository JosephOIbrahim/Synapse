# SYNAPSE — Scout: Hardening → Capability Harness · v1
*Derives the next scout work from first principles. **Commit this doc before running it** (provenance — ephemeral pasting recreates the F3 class). Claude Code dispatch under ARCHITECT → FORGE → CRUCIBLE rotation.*

---

## First-principles derivation — read first
*This is why the order is not the order the todos were listed in.*

Three items came off the mile marker: corpus freshness, semantic path, phantom-rate eval. As written they look like parallel chores. They aren't. Deriving from what each actually is:

**1 · Freshness is a Floor hole, not a feature.**
The corpus at `.synapse/scout_corpus/` is a cache derived from `rag/`. Caches drift. A drifted grounding corpus produces **false phantoms** — it flags a now-real API as not-existing — which is *worse than no gate*, because it actively tells the model a real thing is fake. By the Floor (the map must match the building), a grounding tool that can silently diverge from its source is already broken. → **P0, ahead of everything.**

**2 · The eval is the linchpin, and it measures two things, not one.**
Not just retrieval quality — **corpus coverage**. The sharp consequence of (1): the eval must include known-real APIs across the H21.0.671 surface and verify they are *found*. A high false-phantom rate means the canonical corpus is missing real content — a correctness bug that **outranks the semantic enhancement**. The eval's outcome changes the rest of the plan, so by probe-first ordering it runs *before* semantic. It is also the **verdict instrument** for the semantic spike (you cannot honestly claim semantic is "better" without it).

**3 · The semantic task changed shape.**
It is no longer "probe `G:` → manifest." The canonical corpus moved to `.synapse/scout_corpus/` (built fresh from `rag/` via KnowledgeIndex). `G:`'s vectors — if any — are over a stale, *different* corpus → misaligned with the 117 canonical entries → **unusable**. So semantic = **build fresh embeddings over the canonical entries**, gated on (a) the eval proving lexical recall is actually insufficient on conceptual queries, and (b) an embedder decision that satisfies the dual-interpreter constraint (graphical H21.0.671 + hython 21.0.631 = **separate site-packages**) without smuggling a network call into the render loop. That decision is the one **human gate**.

**Admission gate.** None of these is a search/RSI problem. Spike 1 is a straight build + a drift test. Spike 2 is a measurement instrument. Spike 3 is a build gated on a decision. No GEPA, no science loop — wrapping them in it would be the scope balloon.

**Derived order:** `freshness (P0 Floor) → eval (linchpin; coverage + quality; gates semantic) → [HUMAN GATE: review eval + choose embedder] → semantic (conditional)`.

---

## Invariants — the Floor for this harness
- **Staleness fails loud, never silent.** A missing/corrupt corpus manifest reads as *stale*, not *fresh*.
- **False-phantom rate is release-blocking.** A real API flagged as phantom is a Sev-1, not a tuning nit.
- **The eval is un-gameable.** Ground truth is fixed and external; CRUCIBLE may not "pass" it by loosening a threshold (Commandment 7 applies to the eval itself).
- **Embedder satisfies both interpreters or declares the limitation.** No silent "works in graphical, dark in hython."
- **No network in the render loop without a surfaced decision.** Query-time embedding that calls out is a conscious choice, not a default.
- **No reuse of `G:`'s vectors** — misaligned with the canonical corpus.
- **Semantic lands only if it beats lexical on the eval's conceptual bucket.** If it doesn't beat lexical, it doesn't land.
- `cognitive.tools.*` stays zero-`hou`. Quarantined phantoms (`hou.pdg.*`, `hou.secure`, `hou.lopNetworks()`, `hou.updateGraphTick()`) stay flagged-false through every change. Atomic commits; race-safe push (fetch + rebase, max 3, halt on conflict); halt-and-surface before irreversible.

---

## SPIKE 1 — Corpus freshness  *(Track H · P0 · straight build + drift gate)*
**ARCHITECT** — At ingest, write a **BLAKE2b** digest of the `rag/` source (path + size + mtime, stable across restarts) into the corpus manifest. Decide drift policy: default **warn-loud** (`stale: true` in every result + a log line) with a config flag to escalate to **hard-refuse**.
**FORGE** — Freshness check at scout load: recompute the `rag/` digest, compare to manifest; on mismatch, flag + (warn|refuse) per policy.
**CRUCIBLE** — Mutate `rag/` after ingest → assert drift detected and surfaced. Clean state → asserts pass silently. Missing/corrupt manifest → asserts *fail loud* (not silently "fresh").
**GATE** — Full suite holds/increases → **COMMIT** (atomic, race-safe push).
*Deferred, not now: auto re-ingest on drift — convenience layer, a deliberate command, never load-time magic.*

## SPIKE 2 — Phantom-rate & coverage eval  *(the linchpin)*
**ARCHITECT** — Define the fixed prompt set, three buckets, all with external known-answer ground truth:
- **(a) known-REAL** APIs across the H21.0.671 surface (`hou.*`, `pdg.*`, `pxr.*`, VEX) that **must be found** → false-phantom / coverage rate.
- **(b) known-PHANTOM** (incl. the four quarantined) that **must be flagged** → true-phantom catch rate.
- **(c) conceptual queries** with a known-relevant doc that **should land top-k** → recall quality *(this is the number that justifies or denies semantic)*.
Metrics: **false-phantom rate** (target → 0, release-blocking), true-phantom recall, conceptual top-k hit-rate.
**FORGE** — Eval runner over the live scout; emit a scorecard.
**CRUCIBLE** — The eval must be honest: ground truth fixed/external, not satisfiable by loosening a threshold; the eval itself fails if scout regresses.
**RUN + BRANCH** *(probe-first outcome — this is what changes the plan):*
- **High false-phantom rate** → corpus **coverage gap**. **HALT-AND-SURFACE.** This outranks semantic. Fix = expand ingest scope (`rag/` coverage, or fold in `G:`'s real entries) before anything else.
- **Conceptual top-k already high** → semantic is low-value. **Surface:** Spike 3 may be unnecessary — pin the eval and stop.
- **Conceptual poor, coverage clean** → semantic justified → proceed to the human gate.
**GATE** — **COMMIT** the eval (now the standing efficacy pin + Spike 3's verdict instrument).

## HUMAN GATE — Joe reviews
Joe reads the scorecard + branch outcome and makes the **embedder call** (the only real architectural fork):
- **Local vendored** (e.g. sentence-transformers): offline at query time, but `torch` must be in *both* interpreters' site-packages or vendored — heavy.
- **Hosted API embedder**: light deps, but a network call in the query/render path + a key (mind the `SYNAPSE_ANTHROPIC_KEY` leak rule) + an offline-failure mode.
Decision recorded **before** Spike 3 forges anything.

## SPIKE 3 — Semantic path  *(conditional · build over canonical · gated on eval + human gate)*
*Runs only if the eval said semantic is justified, coverage is clean, and an embedder is chosen.*
**ARCHITECT** — Confirm **fresh build over `.synapse/scout_corpus/`** canonical entries (not `G:` reuse). Manifest schema: embedder name + model + dim + metric. Dual-interpreter availability check.
**FORGE** — Build embeddings over the canonical corpus; write `manifest.json`; feed scout's existing numpy/faiss backend.
**CRUCIBLE** — Assert `mode` flips to `hybrid`; assert query-side embed dim == index dim (the cardinal RAG guard, already in scout); assert **hybrid beats lexical on the eval's conceptual bucket** *(the landing criterion — if it doesn't beat lexical, it doesn't land: fix-forward or abandon)*; assert the four phantoms **still flag false** under hybrid (semantic must not resurrect them).
**GATE** — Full suite + measured eval improvement → **COMMIT**.

---

## MILE MARKER — capsule out (per spike)
**WHERE WE ARE** · **MILE MARKER** (which spike closed) · **BLOCKERS** (any halt-and-surface, esp. a Spike 2 coverage gap) · **NEXT ACTION**.
Stop points that are real gates, not mechanical ones: the **HUMAN GATE** (embedder), and any **Spike 2 coverage-gap HALT**.
