# SYNAPSE — Debut Readiness

> **Date:** 2026-08-05
> **Version:** v5.42.0
> **Target:** Houdini 22.0.368 / Python 3.13
> **Purpose:** What SYNAPSE is, what works, what doesn't, and how to start using it.

---

## What SYNAPSE Is

SYNAPSE is an AI agent that runs **inside** Houdini's own Python interpreter — not beside it, not bridged over HTTP, not in a separate process. It calls `hou.*` directly on the main thread, reads the scene through the same API the artist uses, and writes back through an undo-wrapped, integrity-verified execution path.

The architecture is **inside-out**: instead of serializing the entire scene to a cloud model on every turn (which scales with scene size, not with what you asked about), SYNAPSE reads only what the task requires and acts in place. The cost scales with what you ask about, not with the size of your scene.

It exposes 115 tools across two transport paths: an audited `/mcp` bridge (undo-wrapped, consent-gated, integrity-verified) and a direct `/synapse` WebSocket path (RBAC-guarded, main-thread-marshalled, observe-only provenance). Both reach the same Houdini API; the bridge path adds structural safety guarantees.

---

## What's Ready

These features are production-hardened — tested, verified on H22.0.368, and running in live sessions.

### Moneta Memory Backend

Moneta is SYNAPSE's in-process memory engine. It is the live substrate: `packages/synapse.json` sets `SYNAPSE_MEMORY_BACKEND=moneta`, and 159 production rows exist in a real Moneta snapshot as of 2026-08-05.

- **Durable storage** — snapshots to `snapshot.json` under `.moneta/` on clean exit (atexit handler) and on explicit `save()` calls. A 30-second periodic save timer bounds the crash-loss window: at most 30 seconds of deposits are at risk between snapshots.
- **Corrupt-snapshot quarantine** — if `hydrate()` finds a corrupt snapshot, it renames it (`.corrupt-` suffix), logs an ERROR, and starts fresh. No silent data loss, no crash on startup.
- **Thread-safe** — `RLock` guards every engine access (`add`, `_iter_memories`, `count`, `save`, `run_sleep_pass`, `close`). The adapter makes zero `hou.*` calls, so the lock is never held across an `hdefereval` main-thread hop.
- **Backend fallback is loud** — if Moneta cannot be imported or initialized, `_make_store` falls back to JSONL with a WARNING and records the event for `synapse_doctor` to surface. The flag can never break startup.
- **Backfill** — `python -m synapse.memory.backfill` migrates JSONL stores to Moneta, backup-first.

### Vector Recall

`MonetaBackedStore.search()` uses a **hybrid** strategy: when `query.text` is present, it embeds the text with `HashEmbedder`, runs Moneta's vector query to retrieve a candidate pool (over-fetched 3x, minimum 50), then reranks with keyword/tag/text scoring. For non-text queries, it falls back to pure keyword scoring over the full memory set.

The `HashEmbedder` is deterministic (PYTHONHASHSEED-independent), dependency-free, and produces 256-dim L2-normalized vectors. Every deposit is stamped with the embedder's `id` for provenance — hash vectors and semantic vectors live in different spaces and are not comparable, so a later embedder swap can detect and re-embed non-matching entries.

### Consolidation

`run_sleep_pass()` triggers Moneta's decay/consolidation engine. It is **auditable**: returns a `PruneAudit` (pruned ids, payloads, types, before/after counts) and logs a WARNING on any prune. Loss is never silent. Decisions, SHOW-tier memories, and gate-protected memories are excluded from pruning.

The consolidation engine is **not** wired to a periodic timer in production — it only fires on explicit calls. This is deliberate: the destructive op must be gated before it runs automatically.

### USD Substrate

The MonetaMemory USD schema is **registered** in `packages/synapse.json` via `PXR_PLUGINPATH_NAME`, pointing at the schema assets (`plugInfo.json`, `generatedSchema.usda`, `MonetaSchema.usda`). The runtime knows the type.

`schema_registered()` in `moneta_runtime.py` reports condition 3 of the 5-condition substrate probe: does this USD runtime know the `MonetaMemory` type? It returns `True`/`False`/`None` (tri-state, never conflates "could not check" with "not registered"). `synapse_doctor` surfaces this as the `moneta_substrate` check.

### Unified Memory

SYNAPSE has three memory systems that coexist:

1. **Moneta-backed `MemoryStore`** — structured memory (add/search/recall), the primary store for agent memory operations. Live in production.
2. **Scene memory** (`scene_memory.py`) — markdown-based "Living Memory" written to `memory.md` / `project.md` files, with its own TF-IDF search. Used for session context and project notes.
3. **RAG corpus** — the retrieval-augmented generation corpus at `rag/`, containing H22 node reference and H21 documentation prose.

The recall/search path sees Moneta first, then augments with RAG knowledge additively (`_augment_with_knowledge()` — best-effort, never raises). The markdown scene memory is a separate system with separate data.

---

## What's Staged

These features work but need tuning or a configuration step before they are production-ready.

### Semantic Embedder

`SemanticEmbedder` (MiniLM-L6-v2 via ONNX Runtime) exists behind the same `Embedder` interface as `HashEmbedder`. It degrades gracefully to `HashEmbedder` when the model file is missing or dependencies are absent.

**What's needed:** The ONNX model file must be downloaded and placed at `~/.synapse/models/minilm-l6-v2/model.onnx` (with `tokenizer.json`). No model ships with the repo. Once present, the embedder produces 384-dim semantic vectors that enable meaningful similarity search — the hash-based bootstrap vectors are useful for identity but not semantic proximity.

### Attention Weighting

Moneta's `signal_attention` API exists and is wired in the adapter. It boosts a memory's utility on access, which feeds the decay/consolidation engine.

**What's needed:** The WAL (write-ahead log) is configured but never written to — `signal_attention` is Moneta's only WAL writer, and SYNAPSE never calls it. The WAL path is inert. Wiring attention signaling requires a production caller (e.g., boosting utility on recall) and is deferred until the vector recall path is the primary search mechanism.

---

## What's Coming

These features are in design or early implementation.

### USD Read Path

Moneta's `UsdTarget` writes typed prims but has zero read APIs. Even with `use_real_usd=True`, there is no way to read the authored USD back. The `usd_link` field is never assigned anywhere in the Moneta package. This is an upstream gap that must be fixed before the "USD cognitive substrate" claim is literally true.

### Cross-Session Hydration

Moneta snapshots persist per-session. Cross-session memory — loading one session's memories into another — is not wired. The backfill tool exists for JSONL-to-Moneta migration, but there is no mechanism to merge or query across session stores.

### Multi-Process Locking

Moneta enforces single-owner URI locking. Two Houdini processes cannot share the same Moneta store. A multi-process coordination layer (file locking, lease-based access) is not designed.

---

## Known Limitations

Honest about what doesn't work yet.

### ~72 Moneta Tests Skip on CI

Moneta tests are `skipif not moneta_available` and skip on CI. The CI workflow has conditional checkout gated on `MONETA_DEPLOY_KEY` (a GitHub repo secret not yet provisioned). Until the deploy key exists, CI never exercises Moneta. All ~72 tests pass locally where Moneta is present.

**Full suite:** 5,724 tests collected locally. The 15 pre-existing failures are the pxr-env baseline (tests that expect pxr-absent and fail because pxr IS installed locally) — zero new regressions.

### Cosine Clamp Fix Is in Moneta Source, Not in Installed Package

`Moneta.query()` ranks by `cosine_similarity * utility`. Cosine can be negative (5.74% for short tokens, 36.4% for disjoint symbols). A negative cosine times positive utility = negative score, which ranks below a zero-score item — reinforcing a memory can bury it.

The fix (`max(cos, 0.0)`) is documented in the Moneta source but not yet applied. SYNAPSE never calls `Moneta.query()` directly (it uses the hybrid search path), so this is unreachable today — but if anyone later wires `MonetaBackedStore.search` to `self._handle.query(...)`, this bug activates immediately.

### Schema Registration Requires Houdini Restart

`PXR_PLUGINPATH_NAME` is set in `packages/synapse.json`, which is read at Houdini startup. Changing the schema path or registering a new schema requires a full Houdini restart. There is no hot-reload path for USD plugin registration.

### `evolution.py` Is Deprecated but Present

`python/synapse/memory/evolution.py` has been renamed to `evolution.py.deprecated`. It declares itself SUPERSEDED by the Moneta backend and says "do not extend it." Under the moneta backend, `_check_evolution` is never called. Under the jsonl fallback, it still fires. The file will be removed when `SYNAPSE_MEMORY_BACKEND` defaults to `moneta` unconditionally.

### Vector Index Is Write-Only

Every deposit writes to Moneta's vector index. Nothing reads it in the primary path — the hybrid search uses `Moneta.query()` for candidate pre-filtering, but the final ranking is pure-Python keyword scoring. The vector index is write amplification: CPU time, memory, and I/O for a data structure that is populated and barely queried.

### No Per-Deposit Durability

`deposit()` writes to the in-memory ECS and returns. No `save()`, no WAL write, no daemon. The only persistence is the atexit handler (clean exit only) and the 30-second periodic save timer. A hard crash (kill -9, power loss, native crash) loses at most 30 seconds of deposits.

### Two Memory Systems Coexist

Moneta backs the structured `MemoryStore`. The markdown "Living Memory" system (`scene_memory.py`) is a separate system with separate data. A memory written through one is invisible to the other. Unification is Phase 5 of the Moneta production plan.

### The Recall/RAG Seam

`recall`/`search` see Moneta only, not the RAG corpus. `_augment_with_knowledge()` bridges the gap additively — best-effort, never raises. The VEX corpus goal (seed Moneta pointers via `seed_corpus.py`) is partially addressed but has not been run.

### `use_real_usd` Is Not Enabled

`MonetaConfig` is built without `use_real_usd=True`. All 159 production rows have `usd_link=None`. SYNAPSE authors zero USD through Moneta. Enabling it requires schema registration (done) plus a config change, but the USD read path (B-M3) must exist first for it to be useful.

### `run_sleep_pass` Is Ungated

`run_sleep_pass` permanently prunes unprotected memories and is currently ungated. It has no production caller yet, so this is not urgent — but when wired to a periodic timer, it must route through `HumanGate` at APPROVE.

### Memory.id Collision

`Memory.__post_init__` generates `id` before defaulting `created_at`, so identical content+type collides. JSONL deduplicates by id; Moneta appends both. The fix is a reorder in `__post_init__` (15-minute change, deferred to avoid touching shared `models.py` before the cutover).

### Moneta Is an Unpinned Dependency

No version pin in `pyproject.toml`. CI checks out branch tip, not a tagged release. `importlib.metadata.version("moneta")` returns `1.2.0rc1` for rc1, rc2, and rc2+N — cannot discriminate builds. SYNAPSE's `moneta_runtime.py` works around this by reading git SHA from filesystem metadata.

---

## Quick Start

### 1. Install

Add the `packages/` directory to Houdini's package search path:

```
set HOUDINI_PACKAGE_DIR=%HOUDINI_PACKAGE_DIR%;C:\Users\User\SYNAPSE\packages
```

Or run the install script:

```
python scripts/install_synapse_package.py
```

This deploys a resolved copy of `packages/synapse.json` into your Houdini preferences. The package sets `SYNAPSE_ROOT`, `PYTHONPATH`, `MONETA_SRC`, `PXR_PLUGINPATH_NAME`, and `SYNAPSE_MEMORY_BACKEND=moneta`.

### 2. Verify

Start Houdini and call `synapse_doctor`:

```
synapse_doctor(bundle=True)
```

This runs all diagnostic checks: bridge endpoint, Moneta substrate (5-condition probe), symbol table freshness, log file health, telemetry, encryption-key fingerprint. The `bundle` flag writes a diagnostic zip to `~/.synapse/diagnostics/` (secrets are never collected).

Key checks to confirm:

| Check | Expected Status |
|---|---|
| `bridge_endpoint` | `ok` — WebSocket is reachable |
| `moneta_substrate` | `ok` — Moneta imports, schema registered |
| `symbol_table` | `ok` — stamped against running H22 build |
| `write_plane` | `ok` — memory/report targets accept writes |

### 3. Start

Call `synapse_project_setup` to load project history, scene context, and memory:

```
synapse_project_setup()
```

This is the first call in every session. It returns project memory, scene memory, agent state, and evolution stage. Without it, the agent has no context.

From there, the full tool surface is available: scene inspection, node creation, USD/Solaris assembly, Copernicus image processing, PDG orchestration, memory operations, and rendering.

---

## Key Files

| File | Role |
|---|---|
| `packages/synapse.json` | Houdini package manifest (env vars, paths) |
| `python/synapse/memory/moneta_store.py` | MonetaBackedStore adapter (464 lines) |
| `python/synapse/memory/moneta_runtime.py` | Import guard + 5-condition substrate probe (702 lines) |
| `python/synapse/memory/store.py` | Backend selector + JSONL MemoryStore (1360 lines) |
| `python/synapse/memory/embedding.py` | HashEmbedder + SemanticEmbedder (117 lines) |
| `python/synapse/memory/backfill.py` | JSONL-to-Moneta migration (120 lines) |
| `python/synapse/memory/scene_memory.py` | Markdown Living Memory system (~1200 lines) |
| `python/synapse/memory/evolution.py.deprecated` | Legacy evolution (SUPERSEDED, 443 lines) |
| `python/synapse/server/doctor.py` | Diagnostics (moneta substrate check at H6/R64) |
| `python/synapse/server/handlers_memory.py` | Memory MCP handlers (~315 lines) |
| `shared/bridge.py` | LosslessExecutionBridge (~700 lines) |
| `shared/evolution.py` | Legacy evolution pipeline (shared/, not memory/) |
| `docs/MONETA_SYNAPSE_SHIP_REPORT.md` | Miles 2-8 ship report |
| `docs/moneta-deep-review-2026-08-05.md` | Deep review + phased architecture |
| `docs/moneta-production-harness-architecture.md` | Production harness architecture |
