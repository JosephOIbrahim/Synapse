# SCOUT H6 — Memory store degradation on turn 2

**VERDICT: CONFIRMED**

## Mechanism

`_repoint_router_memory(owner)` calls `_memory_owner()` on every turn, which triggers `refresh_memory_owner()` → `ensure_current_memory()` on the main thread. When a scene rebind occurs (turn 2 after the first scene switch), `ensure_current_memory()` may call `_adopt_scene_store()` (line 386 of memory_lifecycle.py), which creates a `MemoryStore(source, background_load=False)` with synchronous loading. The `_load()` method acquires a write lock (line 389 of store.py) while parsing the JSON file. If the store is degraded (from the ae34ed96 fix for duplicate deposits), `_write_refusal_reason()` returns a degradation message, and subsequent calls to `memory.search()` in `enrich_context()` will see a store in write-refusal state. The 30s slow-op timeout governs this path; if the store load or degradation check blocks, the handler times out on turn 2.

## Evidence

**File:line** — Store degradation state checks:
- `python/synapse/memory/store.py:227-228` — `_degraded_load` and `_degraded_reason` flags set during load
- `python/synapse/memory/store.py:501-519` — `_write_refusal_reason()` checks degradation and returns refusal reason
- `python/synapse/memory/store.py:379-389` — `_load()` acquires write lock synchronously when `background_load=False`

**File:line** — Turn 2 memory owner refresh path:
- `python/synapse/server/handlers.py:1757` — `owner = self._memory_owner()` called on every turn
- `python/synapse/server/handlers.py:1850` — `_memory_owner()` calls `_memory_on_main()` with refresh callback
- `python/synapse/server/handlers_memory.py:128` — `refresh_memory_owner()` calls `ensure_current_memory()`
- `python/synapse/host/memory_lifecycle.py:378-379` — `ensure_current_memory()` may call `rebind_owner()` or `_adopt_scene_store()`
- `python/synapse/host/memory_lifecycle.py:338-341` — `_adopt_scene_store()` creates `MemoryStore(source, background_load=False)`

**File:line** — Memory tier access during routing:
- `python/synapse/routing/context_enrichment.py:82` — `recent = memory.search(query=message, limit=memory_limit)` in enrich_context
- `python/synapse/routing/router.py:679-682` — `enrich_context()` called with `memory=self._memory` during Tier 2+ routing

**File:line** — Exception handling:
- `python/synapse/routing/context_enrichment.py:91-92` — `memory.search()` exception caught as debug log (does not propagate)
- `python/synapse/server/handlers.py:1853-1858` — `_memory_owner()` exceptions caught and logged WARNING; returns None (memory tier degraded but handler continues)

## Reproduction

1. Open Houdini with SYNAPSE on a project with an existing memory store
2. Send a chat message (turn 1) — answers normally
3. In the Houdini file menu, save the file to a new scene or use "Save As" → triggers scene rebind
4. Send a second chat message (turn 2) — observe:
   - Panel shows spinner, no response within 30 seconds
   - SessionStart logs show a `route_chat` timeout or slow-op boundary exceeded
   - Server logs show a WARNING about "Chat router could not borrow the memory owner" (handlers.py:1854) OR the `_load()` of the legacy store holds the lock past the timeout

## Smallest fix shape

The `_adopt_scene_store()` function should detect a degraded store before opening it synchronously. Add a check: before line 341 (`MemoryStore(..., background_load=False)`), read the degradation flags from the legacy store's snapshot or metadata file without fully loading it, and skip adoption if the store is marked degraded. Alternatively, move the `_adopt_scene_store()` call to a background thread so the main-thread router path is not blocked by the lock acquisition. The current synchronous path on the main thread violates the 30s slow-op timeout contract.
