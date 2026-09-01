# BP2-HEALTHWIRE — health-row wiring notes (2026-09-01)

Branch `bp2/healthwire`, worktree `.claude/worktrees/bp2-healthwire`.
Companion to `harness/notes/receipts/BP2-HEALTHWIRE.json`. Runtime is truth;
every claim carries a `file:line`, a command, or a probe transcript.

Closing leg proposed by BP2-STORE (`harness/battleplan/notes/BP2-STORE.md` sec.3
DRAFT — "applied by a server-owning pass"). STORE's `backend_health()` is on
master after its merge; this leg branched from master and reads it — it does
**not** touch `python/synapse/memory/`.

## What shipped (the STORE sec.3 draft, applied)

`python/synapse/server/write_plane.py::store_health()` now, on the evaluated
path only, ADDITIVELY:

1. Calls `synapse.memory.store.backend_health(store)` — reusing the SAME live
   store object `store_health()` already resolved via `_live_store()` (no second
   construction; observer law preserved).
2. Merges the two W1 operator fields it lacked into the top-level info dict:
   `info["embedder_id"]`, `info["embedding_dim"]` (honest `None` on jsonl).
3. Attaches the full `backend_health()` dict under `info["backend_health"]`,
   with one operator-facing alias added on write_plane's side:
   `info["backend_health"]["verdict"] = <status>`.

### The `status` vs `verdict` reconciliation (why the alias)

`backend_health()` (memory territory, `store.py:818`) emits its ratified
verdict under the key **`status`** (SUCCESS | UNAVAILABLE | BLOCKED). The
brief's T3 predicate reads `info['backend_health']['verdict']`. Because
`store.py` is territory-frozen (STORE owns it; crucible criterion: memory/ diff
empty), the key there cannot be renamed. Resolution: attach the dict **verbatim**
(so `status` — the runtime word — is preserved) and add a `verdict` alias equal
to `status` on write_plane's side. Both keys are present in the sub-dict and
carry the **identical** value; the alias is never a fork
(`test_two_vocabularies_stay_separate`, `..._attaches_unavailable_verdict...`
assert `verdict == status`). This satisfies the literal T3 predicate AND
acceptance #1 ("backend_health with the ratified verdict") without touching
`store.py`.

`write_plane`'s OWN word (`ok`/`degraded`/`unknown`) is untouched — its doctor,
panel-strip, and `test_w3_harden_write_plane_store.py` consumers keep reading it.
The ratified verdict rides alongside; the two vocabularies stay separate.

Product: `python/synapse/server/write_plane.py` store_health() (merge block after
the Moneta durability check, before the `if broken:` verdict) + a docstring note.

## Targets

- **T1** `write_plane.py store_health()` merges embedder_id + embedding_dim and
  attaches the full `backend_health()` dict under `info["backend_health"]`.
  Existing keys + status words unchanged. → `python/synapse/server/write_plane.py`.
- **T2** `synapse_health` response carries the same sub-dict. Chain:
  `store_health()` → `write_plane_state()["store"]` (`write_plane.py:457,485`) →
  `_handle_get_health()["write_plane"]` (`handlers.py:901`) → the `synapse_health`
  tool (`mcp/_tool_registry.py:129` maps `synapse_health`→`get_health`). Proven
  end-to-end by the probe below. sec.4 tool surface byte-identical — empty diff
  attached below.
- **T3** tests: moneta-requested + unimportable →
  `info["backend_health"]["verdict"] == "UNAVAILABLE"` while write_plane keeps
  `"degraded"`; healthy → SUCCESS with embedder fields present.
  `test_w3_harden_write_plane_store.py` byte-identical + green; full `pytest -q`
  green. → `tests/test_bp2_healthwire_write_plane_backend_health.py` (7 tests).
- **T4** one line naming the five operator fields → `docs/help/health_row.md`.

## Evidence

### T2 — sec.4 tool surface byte-identical against master (empty diff)

```
$ git diff master -- python/synapse/mcp/ \
    python/synapse/server/handlers.py python/synapse/server/handlers_memory.py \
    python/synapse/server/handlers_render.py python/synapse/server/handlers_node.py \
    python/synapse/server/tracker.py python/synapse/server/scene_memory.py
        (no output — byte-identical)
$ git diff master -- python/synapse/mcp/_tool_registry.py | wc -l
0
```

`store_health()` is server internals, NOT a registered MCP tool — the tool
surface (names/arities/docstrings) is untouched. The only code file this leg
changes vs master is `write_plane.py`. (An unrelated `python/synapse/__init__.py`
VERSION delta 5.59.0↔5.58.0 is master moving ahead of the branch base during the
live merge train — `git diff HEAD -- python/synapse/__init__.py` is empty; this
leg did not edit it, and VERSION is a ratified surface.)

### T3 — tests green

- New file `tests/test_bp2_healthwire_write_plane_backend_health.py`: 7 tests,
  all pass (the gated moneta-serves test RAN this seat — moneta importable —
  proving real embedder id + dim, not a skip).
- `tests/test_w3_harden_write_plane_store.py`: byte-identical to master
  (`git diff master --` empty), 10 passed.
- Full suite: `6912 passed, 186 skipped, 0 failed` in 275.59s
  (`python -m pytest -q`; 186 skips are pre-existing Houdini/hython-gated;
  warnings are pre-existing vendored-ABI on Py3.14 + headless scout gate).

### T1/T2 — end-to-end probe through the real `_handle_get_health` (synapse_health)

Read-only probe (`_global_synapse` injected; not committed):

```
(1) moneta requested + un-importable -> jsonl fallback
    write_plane.status    : degraded          # own word kept
    backend_health.verdict: UNAVAILABLE  | .status: UNAVAILABLE
    five fields           : {requested_backend: moneta, active_backend: jsonl,
                             embedder_id: None, embedding_dim: None, row_count: 0}
(2) jsonl requested + served
    write_plane.status    : ok
    backend_health.verdict: SUCCESS
    five fields           : {requested_backend: jsonl, active_backend: jsonl,
                             embedder_id: None, embedding_dim: None, row_count: 0}
(3) moneta LIVE this seat
    write_plane.status    : ok
    backend_health.verdict: SUCCESS
    five fields           : {requested_backend: moneta, active_backend: moneta,
                             embedder_id: minilm-l6-v2-d384, embedding_dim: 384,
                             row_count: 0}
    get_health top keys   : [healthy, houdini_available, protocol_version, write_plane]
```

Scenario (3) shows the real embedder id + dim surfacing at the health line —
exactly what BP2-LATENCY's probe reads "from the health line"
(`docs/BATTLEPLAN.md:214`). Top-level `get_health` keys are UNCHANGED, so
`test_health_keys_are_additive` (`test_write_plane_health.py:233`) holds and no
consumer breaks.

## Predicate #4 (gui_required) — UNKNOWN, with data-layer proven

"health row observed in the .400 GUI panel strip shows the five fields (Joe)" is
a human/GUI acceptance. It is **UNKNOWN** headless (constitution: unobtainable
renders UNKNOWN; skip ≠ pass). Two honest facts:

- The DATA reaches the surface the GUI health line renders — proven end-to-end
  above (the five fields + ratified verdict in the `synapse_health` response).
- The always-visible 4-cell panel strip (`python/synapse/panel/health_strip.py`)
  renders `connection · memory · project · job` and deliberately does **not**
  call `get_health` (it avoids a main-thread stall; `health_strip.py:43-44`), so
  it does not itself render these five fields. `panel/` is PANELTRUTH territory —
  out of this leg's scope. If Joe wants the five fields shown in the STRIP
  specifically, that is a panel-side follow-up → see receipt `spawn`.

## Adversarial verification (5-skeptic panel)

Workflow `bp2-healthwire-verify` (run `wf_0984f599-7ff`): 5 skeptics, each
prompted to REFUTE one axis, read-only, 0 errors. **All 5 held (`holds=true`,
severity `none`) — no refutation survived.**

1. **Territory** — `git diff master -- python/synapse/memory/` EMPTY;
   `python/synapse/loop/pgdrm.py` does not exist in tree (nothing to touch); the
   only tracked working-tree change is `python/synapse/server/write_plane.py`.
   (The master-vs-branch delta — CLAUDE.md, README.md, VERSION, pyproject.toml,
   `__init__.py`, harness files — is all master-ahead of the base, not this leg.)
2. **Vocabulary + W3 byte-identical** — blob-hash proof:
   `master:tests/test_w3_harden_write_plane_store.py` ==
   `hash-object(worktree)` == `404f6469…`; 10 passed; write_plane's
   ok/degraded/unknown assignments are unchanged CONTEXT (no +/-); no key
   collision (the `verdict` alias lives inside the sub-dict, never at top level).
3. **Tool surface** — `_tool_registry.py` blob `8c538a85…` identical master vs
   worktree; every `mcp/` file identical; `store_health` is not a registered
   tool; the `synapse_health` entry is intact (and its write_plane-mentioning
   docstring exists in master too — not added here).
4. **Anti-masquerade** — `sub["verdict"] = bh.get("status")` is a single-expr
   copy of the same dict's status, so verdict can never fork from status; a
   BLOCKED probe (moneta importable but init raises) → `verdict: BLOCKED`,
   write_plane `degraded`; `MonetaBackedStore`/`ShadowMemoryStore` are NOT
   `MemoryStore` subclasses, so backend_health's `isinstance` and store_health's
   name-check are equivalent — no masquerade path; `'ok'` ∉ `ports.STATUS`.
5. **Honesty/safety** — the `store is None` early return sits BEFORE the merge,
   so an empty process (`evaluated=False`) grows no `backend_health`/embedder
   keys; embedder fields are honest `None` on jsonl; no consumer of
   `store_health()` breaks on the additive keys; `store_health()` still never
   raises.
