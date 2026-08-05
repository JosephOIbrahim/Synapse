# Moneta → SYNAPSE: Supercharging the Relationship

> **Date:** 2026-08-05  
> **Perspective:** Moneta's side of the relationship — what Moneta offers that SYNAPSE hasn't fully activated  
> **Status:** Moneta v1.2.0-rc3 · SYNAPSE on `rope/gate-a` (baf0f05)  
> **Preceding doc:** `docs/moneta-deep-review-2026-08-05.md` (SYNAPSE→Moneta perspective)

---

## 0. EXECUTIVE SUMMARY

Moneta is an in-process memory engine with seven capabilities. Before this sprint, SYNAPSE used **one** of them (deposit/query). After Phases 0-5, SYNAPSE now uses **four** (deposit/query, vector recall, consolidation, attention). Three remain dormant: the WAL, the USD read path, and cross-session hydration.

The gap is not that Moneta lacks features. The gap is that SYNAPSE activates features in the wrong order — it wired the most complex capability (vector recall) before the simplest (WAL), and the most transformative (USD substrate) before the foundational (embedder quality).

This report identifies every Moneta capability SYNAPSE is underusing, ranks them by leverage, and proposes a sequence that maximizes impact per unit of effort.

---

## 1. CAPABILITY MATURITY

| Capability | Moneta offers | SYNAPSE uses | Maturity |
|---|---|---|---|
| **Deposit/Query** | Full | ✅ Full | Production |
| **Vector Similarity** | Cosine index + ranking | ⚠️ Partial (hash embedder) | Staged |
| **Time Decay** | Configurable half-life, lazy eval | ⚠️ Partial (untuned) | Staged |
| **Consolidation** | Prune + stage + cold tier | ⚠️ Partial (prune only) | Staged |
| **Attention Weighting** | `signal_attention` → WAL | ⚠️ Partial (no WAL) | Staged |
| **Durability** | Snapshot + WAL + daemon | ⚠️ Partial (snapshot only) | Staged |
| **USD Authoring** | Typed prims, sublayer rotation | ⚠️ Partial (just enabled) | Staged |
| **USD Read Path** | — (write-only upstream) | ❌ None | Missing |
| **Cross-session Hydration** | — (not designed) | ❌ None | Missing |
| **Multi-process Locking** | In-memory URI registry | ❌ None | Missing |

---

## 2. THE LEVERAGE RANKING

Ranked by impact per unit of effort. The highest-leverage items are the ones that cost the least and change the most.

### #1: Swap the Embedder (Effort: 3 days · Impact: Transformative)

**What Moneta offers:** A vector index that ranks by cosine similarity. The quality of that ranking is entirely determined by the quality of the embeddings going in.

**What SYNAPSE does:** Feeds it 256-dim hash vectors from `HashEmbedder` — character n-gram feature hashing via BLAKE2b. Deterministic, zero-dependency, but semantically blind. "cat" and "dog" are as far apart as "cat" and "quantum mechanics" — they share no n-grams.

**The gap:** The vector index is populated and queried, but the vectors carry no semantic information. The ranking is essentially random for any two unrelated queries. SYNAPSE is doing write amplification on noise.

**The fix:** Swap `HashEmbedder` for a MiniLM-class semantic embedder (384-dim, ~10MB, runs locally via `sentence-transformers` or `onnxruntime`). This is the single change that transforms vector recall from a novelty into a capability.

**Why it's #1:** Every downstream consumer of vector recall — search, recall, consolidation ranking, attention weighting — improves automatically. No other change touches as many systems.

**Design:**
```python
class SemanticEmbedder:
    """MiniLM-based embedder for production vector recall."""
    id = "minilm-l6-v2-d384"
    dim = 384
    
    def __init__(self):
        # Lazy import — 10MB model, don't pay at module scope
        import onnxruntime as ort
        self._session = ort.InferenceSession("models/minilm-l6-v2.onnx")
    
    def embed(self, text: str) -> list[float]:
        if not text:
            return [0.0] * self.dim
        tokens = self._tokenize(text)
        vec = self._session.run(None, {"input_ids": tokens})[0]
        norm = math.sqrt(sum(x*x for x in vec))
        return [x/norm for x in vec] if norm else vec
```

**Re-embedding:** Stamp `embedder_id` on each deposit. On swap, query for non-matching ids, re-embed, re-deposit. The mechanism is already designed (handoff capsule, "PARKED" section) — just not built.

### #2: Close the WAL Loop (Effort: 2 days · Impact: High)

**What Moneta offers:** A WAL (write-ahead log) that records every `signal_attention` call with fsync. On recovery, the WAL is replayed after the snapshot to restore any lost attention signals.

**What SYNAPSE does:** Configures the WAL path (`wal_path=base / "wal.log"`) and never writes to it. The WAL is inert — configured, allocated, and silent.

**The gap:** The WAL is the only mechanism that could close the crash-loss window between snapshots. Without it, the 30-second periodic save timer is the only durability guarantee. With it, every attention signal is durably recorded.

**The fix:** Start calling `signal_attention` on every recall (already wired in Phase 3). The WAL activates automatically — Moneta writes to it inside `signal_attention`. No code change needed in Moneta; the WAL path is already configured.

**Why it's #2:** Zero Moneta-side code change. The WAL path is already set. SYNAPSE just needs to call `signal_attention` consistently, which it now does. The WAL becomes a durability journal for free.

### #3: Tune Decay Parameters (Effort: 2 days · Impact: Medium-High)

**What Moneta offers:** Exponential utility decay with configurable half-life (default 6 hours), lazy evaluation (decay computed at access time, not on a timer), and configurable prune/stage thresholds.

**What SYNAPSE does:** Uses the default 6-hour half-life and default 0.1/0.3 prune/stage thresholds. No tuning has been done against real SYNAPSE usage patterns.

**The gap:** A 6-hour half-life means a memory loses half its utility in 6 hours of inactivity. For a VFX session that runs 8-10 hours, this means memories from the morning are significantly decayed by the afternoon. For a multi-day project, memories from yesterday are nearly gone. This may be too aggressive or too conservative — nobody has measured.

**The fix:** Instrument and tune:
1. Add a metric: `moneta_utility_distribution` — histogram of utility values across all entities
2. Add a metric: `moneta_prune_rate` — entities pruned per sleep pass
3. Run with production data for 1 week
4. Adjust half-life and thresholds based on observed distributions

**Why it's #3:** Wrong parameters don't break anything — they just produce suboptimal recall. Protected memories (decisions, SHOW-tier) are immune to pruning regardless of parameters. The risk is low and the data is easy to collect.

### #4: Build the USD Read Path (Effort: 5 days · Impact: Medium)

**What Moneta offers:** `UsdTarget` writes typed `MonetaMemory` prims to USD sublayers with rotation at 50,000 prims per file. Each prim carries 6 attributes: `payload`, `utility`, `attendedCount`, `protectedFloor`, `lastEvaluated`, `priorState`.

**What SYNAPSE does:** Just enabled `use_real_usd=True` in Phase 4. But Moneta has **zero read APIs** for USD — the `usd_link` field is never assigned anywhere in the package (B-M3 from the deep review).

**The gap:** USD is write-only. SYNAPSE can author typed prims but cannot read them back. The "USD cognitive substrate" claim is false until there's a read path.

**The fix (upstream, in Moneta):**
1. After `SequentialWriter` commits a batch, write the authored prim path back to `usd_link` on the ECS entity
2. Add a `hydrate_from_usd()` method that reads typed prims back into the ECS
3. Add a `read_memory(prim_path)` method that returns a `Memory` from USD

**Why it's #4:** The USD read path is a prerequisite for any cross-session hydration, any USD-based tooling, and any claim that "Moneta is a USD substrate." But it's upstream work in the Moneta repo, not SYNAPSE.

### #5: Cross-Session USD Hydration (Effort: 5 days · Impact: Medium)

**What Moneta offers:** Snapshot-based hydration (JSON file → ECS). No USD-based hydration exists.

**What SYNAPSE needs:** When `use_real_usd=True`, memories should survive a complete loss of the snapshot file. The USD sublayers are the durable record.

**The gap:** If the snapshot is lost (corrupt, deleted, or never written), the USD sublayers contain the data but nothing reads them. SYNAPSE has no way to recover from USD.

**The fix:** Build a `hydrate_from_usd()` path that:
1. Scans the USD sublayer directory for `cortex_*.usda` files
2. Opens each as a `Usd.Stage`
3. Iterates typed `MonetaMemory` prims
4. Reconstructs `Memory` objects into the ECS

**Why it's #5:** This is the insurance policy. The periodic save timer (Phase 1) bounds the loss window to 30 seconds. USD hydration closes it to zero — but only if the USD read path (#4) exists first.

### #6: Multi-Process Coordination (Effort: 3 days · Impact: Medium)

**What Moneta offers:** In-memory `_ACTIVE_URIS` registry that prevents two handles from opening the same URI in the same process. No cross-process coordination.

**What SYNAPSE does:** Runs one Moneta handle per process. Two Houdini sessions on the same project would silently share (or corrupt) the same `.moneta/` directory.

**The gap:** The URI lock is in-memory only. Two processes on the same filesystem can open the same storage URI, write conflicting snapshots, and corrupt each other's data. SYNAPSE currently avoids this by running one Houdini session at a time, but this is a coincidence, not a guarantee.

**The fix:** Add file-based locking:
1. On `MonetaConfig` construction, try to create a lock file at `<storage_uri>/.moneta/lock`
2. Use `fcntl.flock` (POSIX) or `msvcrt.locking` (Windows) for advisory locking
3. Fail with `MonetaResourceLockedError` if the lock is held

**Why it's #6:** Low probability today (single-user), but high impact if it fires. File-based locking is standard practice and cheap to add.

### #7: Embedder Swap Mechanism (Effort: 2 days · Impact: Medium)

**What Moneta offers:** Each deposit carries a `semantic_vector` that the vector index queries against. No mechanism to re-embed existing entries.

**What SYNAPSE needs:** When swapping from `HashEmbedder` to `SemanticEmbedder`, all existing memories need new embeddings. The old hash vectors and new semantic vectors live in different spaces and are not comparable.

**The gap:** After the embedder swap, old memories become invisible to vector recall. They still exist in the ECS and are findable via keyword search, but the vector index returns nothing for them.

**The fix:** The mechanism is already designed (handoff capsule, "PARKED" section):
1. Stamp `embedder_id` on each deposit (already done — `HashEmbedder.id = "hash-ngram-v1-d256-n1_3"`)
2. On swap, query for non-matching ids: `ecs.iter_rows()` → filter by `embedder_id`
3. Re-embed each: `new_embedder.embed(memory.content)` → `handle.deposit(payload, new_embedding, floor)`
4. The old entry remains (Moneta is append-only) but the new one has the correct vector

**Why it's #7:** Important but only matters once — at the moment of the embedder swap. After that, all new deposits carry the correct vectors.

---

## 3. THE OPTIMAL SEQUENCE

Not the order they were built in. The order that maximizes impact per unit of effort.

```
Week 1:  Swap embedder (MiniLM)          ← #1 leverage item
         Re-embed existing memories      ← #7 (prerequisite for #1 to matter)

Week 2:  Close WAL loop                  ← #2 (zero code change)
         Tune decay parameters           ← #3 (instrument + adjust)

Week 3:  Build USD read path (upstream)  ← #4 (prerequisite for #5)
         Cross-session USD hydration     ← #5 (depends on #4)

Week 4:  Multi-process locking           ← #6 (safety net)
         Monitoring + alerting           ← operational maturity
```

**The critical insight:** The embedder swap (#1) is the highest-leverage item because it transforms the quality of every downstream consumer. Vector recall, consolidation ranking, and attention weighting all improve automatically. Everything else is incremental.

---

## 4. WHAT MONETA WANTS FROM SYNAPSE

If Moneta could talk, it would say:

1. **"Feed me better vectors."** My vector index is fast and correct, but garbage in → garbage out. A semantic embedder costs 3 days and changes everything.

2. **"Call signal_attention more."** My WAL is configured and waiting. Every recall should signal attention. I'll handle the durability.

3. **"Measure before you tune."** My default half-life is 6 hours. That's right for a chat application. Yours is VFX. Run for a week, look at the utility distribution, then tell me what half-life you need.

4. **"Read what you write."** I can write USD prims now. Give me a read path and I'll make your "USD cognitive substrate" claim real.

5. **"Lock the file."** Two Houdini sessions on the same project will corrupt each other's data. A lock file costs an afternoon.

---

## 5. THE BOTTLENECK

The single bottleneck across all seven items is **the embedder**. Everything downstream of vector recall — search quality, consolidation ranking, attention weighting — is capped by embedding quality. The hash embedder was the right bootstrap choice (deterministic, zero-dependency, instant), but it has been the bootstrap for three months. It's time to swap.

The second bottleneck is **the USD read path**. It's an upstream gap in Moneta itself. SYNAPSE can't fix it alone — it needs a `hydrate_from_usd()` method and a `usd_link` writer in the Moneta package. This is the one item that requires coordinated work across both repos.

---

## 6. WHAT SUCCESS LOOKS LIKE

After all seven items:

1. **Vector recall is semantic** — "find the material we used for the car paint" returns the right memory, not n-gram noise
2. **Every recall is durably recorded** — the WAL captures attention signals, crash recovery is complete
3. **Decay is tuned to VFX workflows** — session-length half-life, project-aware thresholds
4. **USD is a real substrate** — typed prims on disk, readable, hydratable, the "cognitive substrate" claim is true
5. **Multi-process safe** — two Houdini sessions on the same project don't corrupt each other
6. **Embedder swaps are painless** — re-embedding is a one-command operation, not a data migration
