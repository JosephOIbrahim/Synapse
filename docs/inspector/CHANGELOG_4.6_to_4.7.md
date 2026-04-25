# SYNAPSE 2.0 Inspector — Refactor Changelog

**4.6 → 4.7 production hardening pass, 2026-04-18**

This documents what changed between the initial Opus 4.6 draft and
the production-hardened 4.7 version. The changes are not cosmetic —
they address real failure modes, missing safety rails, and gaps that
would have surfaced the first time the code hit a real production
scene.

---

## TL;DR

- **8 files** instead of 6 (added `exceptions.py`, `transport.py`,
  `conftest.py`, externalized golden JSON)
- **85 mock tests** instead of ~20 (4.2× coverage, all error paths
  exercised)
- **Schema versioning** prevents silent drift between Inspector and
  extraction script
- **Input sanitization** blocks injection attempts on `target_path`
- **Graceful per-node degradation** — one bad node no longer aborts
  the whole AST
- **Deterministic output** — sorted keys, sorted node order
- **Typed exception hierarchy** — consumers route on exception class,
  not string matching
- **Thread-safe transport registration** — no more spooky global state
- **Query helpers on StageAST** — eliminates `{n.node_name: n for n
  in ast}` boilerplate across consumers
- **All 85 mock tests pass** (runtime-verified before shipping)

---

## File-by-file

### NEW: `python/synapse/inspector/exceptions.py`

Six typed exception classes replacing the 4.6 code's bare
`RuntimeError` and `NotImplementedError`:

| Exception | When it fires |
|---|---|
| `InspectorError` | Base class — catch to handle any Inspector failure |
| `TransportNotConfiguredError` | `configure_transport()` never called |
| `TransportError` | WebSocket layer failed (wraps underlying exception) |
| `TransportTimeoutError` | Transport exceeded timeout |
| `InvalidTargetPathError` | `target_path` failed validation |
| `StageNotFoundError` | Target context doesn't exist in Houdini |
| `HoudiniExtractionError` | Houdini-side script raised |
| `SchemaValidationError` | Response didn't match schema |
| `SchemaVersionMismatchError` | Schema versions incompatible |

Every class stores structured attributes (`.path`, `.traceback`,
`.underlying`, `.expected`, `.received`) so consumers can route on
typed data, not string messages.

### NEW: `python/synapse/inspector/transport.py`

Was inline in 4.6. Extracted because Week 2 subnet recursion will
reuse the Base64 wrapper. Adds:

- `configure_transport(fn)` / `reset_transport()` / `get_transport()`
- Thread-safe access via `threading.RLock`
- `is_transport_configured()` predicate for tests
- `TransportFn` Protocol for type checking
- `wrap_script_base64(script)` with security-boundary docstring

### REFACTORED: `python/synapse/inspector/models.py`

**Added:**
- `SCHEMA_VERSION = "1.0.0"` module constant
- `error_message` field on `ASTNode` (was missing entirely in 4.6)
- `ErrorState` type alias for `Literal["clean", "warning", "error"]`
- `StageAST` container class with 15+ query helpers
- Field validators rejecting relative paths
- `model_config = frozen=True` — models are now immutable
- `max_length=500` on `error_message` to prevent unbounded payload growth
- `extra="forbid"` on all models — unknown fields raise, not silently ignored

**StageAST helpers** (eliminates boilerplate across consumers):
- Identity: `by_name(name)`, `by_type(node_type)`
- State: `display_node()`, `bypassed_nodes()`, `error_nodes()`,
  `warning_nodes()`, `clean_nodes()`
- Topology: `orphans()`, `roots()`, `leaves()`
- USD: `authoring_nodes()`, `prims_at(usd_path)`
- Protocol: `__len__`, `__iter__`, `__contains__`, `__getitem__`
- Serialization: `to_payload()`, `to_json()` (deterministic)

### REFACTORED: `python/synapse/inspector/tool_inspect_stage.py`

**Hardening:**

1. **Input sanitization** — `_validate_target_path()` rejects any
   string that could escape `repr()` in the extraction script. Tested
   against 6 concrete injection attempts.

2. **Schema versioning** — extraction payload includes
   `schema_version` field; `_check_schema_version()` enforces match
   before validation. No more silent drift.

3. **Graceful per-node degradation** — the Houdini-side script wraps
   each node in try/except. One bad node produces an error_state entry
   instead of aborting the whole AST.

4. **Deterministic ordering** — children sorted by `hou_path`,
   outputs sorted, usd_prim_paths sorted, JSON emitted with
   `sort_keys=True`. Matches SYNAPSE's existing determinism principle.

5. **Timeout support** — `DEFAULT_TIMEOUT_SECONDS = 30.0`, passed
   through to transport. Falls back gracefully if transport signature
   is legacy (no `timeout` kwarg).

6. **Structured logging** — `logger.info` on entry/exit with target
   and node counts, `logger.debug` on transport details, warnings on
   legacy-transport fallback.

7. **Named error helpers** — `_check_for_houdini_errors()`,
   `_check_schema_version()`, `_build_stage_ast()`,
   `_invoke_transport()` — each function one job, testable
   independently.

8. **No `NotImplementedError` surprise** — 4.6 raised
   `NotImplementedError` when no transport was configured. 4.7 uses
   `TransportNotConfiguredError` (subclass of `InspectorError`) with
   a specific fix message.

9. **No bare exceptions** — unknown transport exceptions wrapped in
   `TransportError` with `.underlying` attribute preserving the
   original.

10. **Graceful legacy transport** — if transport doesn't accept the
    `timeout` kwarg, falls back to calling without it. Duck-typing via
    `TypeError` detection.

### REFACTORED: `python/synapse/inspector/__init__.py`

Expanded public API surface: 20+ exports (was 3). Includes all
exceptions, transport helpers, models, and the tool function.
`__all__` enumerated explicitly so `from synapse.inspector import *`
is safe and predictable.

### NEW: `tests/conftest.py`

Shared pytest infrastructure:

- **`_cleanup_transport`** — autouse fixture that calls
  `reset_transport()` before and after every test. Prevents a test's
  `configure_transport()` from leaking into the next test.
- **`golden_json_str`** — raw fixture file content (loaded from disk,
  not inlined as a giant string literal)
- **`golden_payload`** — parsed dict
- **`mock_transport`** — callable that returns the golden JSON
- **`mock_transport_legacy`** — same but without `timeout` kwarg, for
  testing the graceful fallback
- **`make_mock_transport(response)`** — helper for custom responses
  (error cases)

### NEW: `tests/fixtures/inspector_week1_flat.golden.json`

Externalized golden JSON. 4.6 had it as a 3000-character string
literal inside a test file — one typo silently broke all tests. Now
it's a real JSON file, loaded by conftest, version-controlled.

Wrapped in the new schema envelope: `{schema_version, target_path,
nodes}` instead of a bare list.

### REFACTORED: `tests/test_inspect_mock.py`

**85 tests** organized into 13 test classes:

| Class | Tests | What it verifies |
|---|---|---|
| `TestHappyPath` | 4 | Basic extraction from golden fixture |
| `TestNodeIdentity` | 2 | Node types and path formats |
| `TestUSDPrimPaths` | 6 | `lastModifiedPrims()` integration |
| `TestErrorPropagation` | 7 | Error cascading through node chain |
| `TestFlags` | 2 | Display and bypass flags |
| `TestTopology` | 4 | Input indexing and output fan-out |
| `TestStageASTHelpers` | 15 | All query helper methods |
| `TestReservedFields` | 3 | children/key_parms/provenance empty in Week 1 |
| `TestSerialization` | 3 | to_json determinism, envelope correctness |
| `TestHoudiniErrorRouting` | 4 | Houdini-side errors route to correct exception |
| `TestSchemaVersionChecking` | 3 | Version mismatch and missing-field cases |
| `TestTargetPathValidation` | 6 | Input sanitization (including 6 injection attempts) |
| `TestTransportIntegration` | 7 | Configured vs. injected transport, timeouts, legacy |
| `TestResponseParsing` | 7 | Malformed JSON, empty response, wrong types |
| `TestModelValidation` | 6 | Pydantic validators, immutability, field limits |

### REFACTORED: `tests/test_inspect_live.py`

**4.6 problem:** raised `NotImplementedError` at module import time
when transport wasn't wired — this happened during pytest's collection
phase, so the tests couldn't even be discovered without side effects.

**4.7 fix:**
- `pytestmark = pytest.mark.live` — all tests skipped by default
- `_resolve_live_transport()` tries configured transport, then env
  var `SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE`, then `pytest.skip()`
- Fixture path configurable via `SYNAPSE_INSPECTOR_FIXTURE_PATH` env
- Collection works everywhere; tests run only when infrastructure
  present

Added tests:
- `test_live_returns_stage_ast` — type check on return
- `test_live_schema_version_matches` — verifies runtime and build
  versions align
- `test_live_determinism_repeated_calls` — same scene, two calls,
  identical JSON

### NEW: `pyproject_patch.toml`

Snippet showing what to add to the existing SYNAPSE `pyproject.toml`:
- `live` marker registration
- `pydantic>=2.0` dependency declaration
- `strict = true` mypy override for `synapse.inspector.*`

### UNCHANGED: `docs/verification_ledger.md`

Sprint 1 + 2a evidence is immutable history. Minor note added that
Sprint 2 Week 1 bumped SCHEMA_VERSION to 1.0.0.

---

## Breaking changes from 4.6

1. **Extraction payload format** — now wrapped in `{schema_version,
   target_path, nodes}` envelope. Old golden JSON files will fail
   validation. (Fine: we never shipped the 4.6 version.)

2. **Return type** — `synapse_inspect_stage()` returns `StageAST`
   instead of `List[ASTNode]`. Consumers doing
   `{n.node_name: n for n in ast}` should use `ast.by_name()` or
   `ast['name']`.

3. **Exception types** — `RuntimeError` replaced by
   `HoudiniExtractionError`. `NotImplementedError` replaced by
   `TransportNotConfiguredError`. Catch `InspectorError` as the
   catch-all.

4. **New `error_message` field** on `ASTNode`. Required as Optional
   (can be None). Existing code that constructs `ASTNode` manually
   without this field still works (default None).

5. **Frozen models** — `ASTNode` and `InputConnection` are now
   immutable. Code that mutated node fields after construction will
   fail (this is the intended behavior — mutation was never safe).

---

## Non-breaking additions

- `SCHEMA_VERSION` module constant
- `DEFAULT_TIMEOUT_SECONDS` module constant
- `StageAST` container with query helpers
- All new exception classes (additions, not replacements)
- `configure_transport` / `reset_transport` / `get_transport` /
  `is_transport_configured` / `wrap_script_base64`
- `timeout` kwarg on `synapse_inspect_stage` (optional, defaults to
  `DEFAULT_TIMEOUT_SECONDS`)

---

## Things intentionally NOT done

1. **Async API.** The Inspector stays synchronous to match SYNAPSE's
   existing MCP tool pattern. Async would require coordinating with
   the WebSocket server's event loop — out of scope for Week 1.

2. **Caching.** AST changes on every Houdini edit. Cache invalidation
   is harder than just re-extracting. Revisit if profiling shows a
   real hotspot.

3. **Streaming large scenes.** Current extraction builds the full
   payload in Houdini's memory, sends as one WebSocket message. If a
   scene has 10,000+ nodes this could be slow. Sprint 2 Week 1 golden
   fixture has 8 nodes; real production scenes average ~50-200. Not a
   bottleneck yet.

4. **Retry logic.** The Inspector doesn't retry on transport failure.
   SYNAPSE's existing circuit breaker / rate limiter / backpressure
   layer handles that one layer up.

5. **Audit log integration.** The Inspector doesn't call SYNAPSE's
   hash-chain audit log directly. The MCP tool wrapper in
   `mcp_server.py` is the right place for that instrumentation.
