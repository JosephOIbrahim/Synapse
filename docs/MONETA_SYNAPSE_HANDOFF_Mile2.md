# CLAUDE CODE HANDOFF CAPSULE — Moneta ↔ SYNAPSE, Mile 2

### Desktop → Code. Hand this to Claude Code **alongside** `MONETA_SYNAPSE_INTEGRATION_HARNESS.md`.

> **Purpose:** transfer this session's verified ground truth + the locked embedder decision into
> Claude Code so FORGE starts cold without re-discovering anything. The harness is the constitution;
> this capsule is the current position + first task.

---

## WHERE WE ARE
- **Mile 1 CLOSED.** Connectability proven end-to-end in graphical Houdini 21.0.671.
- **Entering Mile 2:** build the bootstrap embedder.
- Operating under `MONETA_SYNAPSE_INTEGRATION_HARNESS.md`. Lenses = ARCHITECT / FORGE / CRUCIBLE.
  Mode = SIMULATED TEAM, SOLO spine. Marathon-mile structure; gate criteria cite line numbers.

## VERIFIED GROUND TRUTH — do NOT re-verify (confirmed live in H21.0.671)
- **Moneta imports from:** `C:\Users\User\Moneta\src` — **NOT** on graphical Houdini's path by
  default (separate site-packages). Added via `sys.path.insert` for now. Packaging is a Mile 3 item.
- **L0 PASSED 10/10:** `Moneta`, `MonetaConfig`, `MonetaConfig.ephemeral`, `deposit`, `query`,
  `signal_attention`, `get_consolidation_manifest`, `run_sleep_pass`, `MockUsdTarget` all present.
- **Op signatures (confirmed):**
  ```
  deposit(payload: str, embedding: List[float], protected_floor: float = 0.0) -> UUID
  query(embedding: List[float], limit: int = 5) -> List[Memory]
  signal_attention(weights: Dict[UUID, float]) -> None
  get_consolidation_manifest() -> List[Memory]
  run_sleep_pass() -> ConsolidationResult
  ```
- **MonetaConfig fields:** `storage_uri`, `quota_override`, `half_life_seconds`,
  `embedding_dim (Optional[int])`, `max_entities`, `snapshot_path`, `wal_path`,
  `vector_persist_path`, `mock_target_log_path`, `use_real_usd (bool)`, `usd_target_path`.
  - `use_real_usd` = the pxr / MockUsdTarget toggle → **config flag, not a code fork** (de-risks AP9).
  - `embedding_dim` is `Optional` → Moneta does **not** force a dimension.
- **Memory object fields:** `attended_count`, `entity_id`, `last_evaluated (float ts)`,
  `payload (str — round-trips byte-for-byte intact)`, `protected_floor`,
  `semantic_vector (List[float])`, `state (EntityState; VOLATILE=0)`,
  `usd_link (None under Mock → USD prim when use_real_usd)`, `utility (float ~1.0 fresh, decays)`.
  - `utility` is the recency/salience signal → `get_recent` becomes "highest utility."
  - `usd_link` is the provenance anchor.
- **`ephemeral()` = pxr-free, in-memory, MockUsdTarget.** Canonical pattern (from `moneta.smoke_check`):
  ```python
  with Moneta(MonetaConfig.ephemeral()) as m:
      eid  = m.deposit(payload, embedding)
      hits = m.query(embedding, limit=5)
  ```

## DECISION LOCKED (Mile 2)
**Embedder = swappable component behind `synapse.memory.embedding`.**
- **Bootstrap NOW** with a deterministic embedder (option #3): hash / char-ngram → fixed-dim vector.
- **Swap in** a local semantic model (option #2, MiniLM-class ~384-dim) at the quality pass.
- **Rationale:** defuses FC2 (deterministic + offline + instant can't block the build); keeps the
  embedder off the critical path; keeps shadow-parity high for a clean cutover, then the semantic
  swap improves recall deliberately.

## FIRST TASK (FORGE) — build `synapse.memory.embedding`
**Pure Python. Zero deps. No Houdini, no Moneta, no pxr. Fully buildable + testable standalone.**

Interface (ARCHITECT spec — FORGE implements):
```python
class Embedder(Protocol):
    id: str            # pinned identifier, stamped onto deposits for provenance
    dim: int
    def embed(self, text: str) -> list[float]: ...   # deterministic, L2-normalized

# Bootstrap impl: HashEmbedder(dim=256 or 384)
#   - char/word n-gram -> hashed buckets -> fixed-dim vector -> L2-normalize
#   - PURE function of input: same text -> same vector, always. No randomness, no network.
#   - id like "hash-ngram-v1"
```

CRUCIBLE (hostile tests, standalone — **never weaken a test to pass; fix-forward**):
- **determinism** — same input → identical vector across calls *and* process restarts
- **fixed dim** — every output is exactly `dim` long
- **normalization** — ‖v‖ == 1 (within float tol) for non-empty input
- **edges** — empty string, whitespace-only, unicode, very long text, near-duplicate strings

## HALT-AND-SURFACE TRIGGERS (hard)
1. **HALT before writing ANY `MonetaBackedStore` adapter code (Mile 4)** until Joe ratifies the
   **Reconcile → Replace reversal.** The embedder + pxr path (Miles 2–3) do NOT require it; the
   adapter does. Surface and wait.
2. **`dir()`-verify any Moneta API surface NOT listed in "Verified Ground Truth" above**, in the H21
   env, before using it (e.g. `MockUsdTarget` construction args, `ConsolidationResult` fields,
   `EntityState` members). Docs and Gemini hallucinate H21 APIs.
3. Atomic scripts, idempotent guards, transaction wrappers, USD-provenance — per harness invariants.

## PARKED (later miles, not now)
- **Embedder swap requires re-embedding.** Hash vectors and semantic vectors live in different
  spaces — not comparable. **Mechanism:** stamp the embedder `id` into each deposit's JSON payload
  (e.g. `"_embedder": "hash-ngram-v1"`) — payload round-trips intact, so on swap you query, find
  non-matching ids, and re-embed those. Connects to the Mile 8 backfill of the 176 entries.
- **protected-quota ceiling** (`ProtectedQuotaExceededError`) vs. mapping decisions → high
  `protected_floor` (AP8). Don't blindly pin every decision at the ceiling.
- **`last_evaluated` semantics** — created-at, or last-decay-eval? Verify before ordering on it.

## NEXT MILES
- **Mile 3:** pxr / CI path (`use_real_usd` toggle; `MockUsdTarget` for standalone/CI).
- **Mile 4:** `MonetaBackedStore` adapter — **HALT for the reversal first.**
- **Mile 5:** shadow / dual-write + parity diff harness.
