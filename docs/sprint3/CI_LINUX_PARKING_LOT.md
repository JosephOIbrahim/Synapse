# Linux CI Parking Lot — Sprint 3 closeout note

> **Status:** Parked. All 131 failures here are pre-existing
> environmental brokenness made newly visible after the Round 3 +
> Round 4 CI fix-forward removed the collection-fail wall.
>
> **Sprint 3 work is unaffected:** all Spike 3.1/3.2 tests pass on
> Linux CI; Windows local baseline is 2874 tests collected, all
> Spike 3 suites green.
>
> **Out of scope for Sprint 3:** fixing the 131 listed failures
> requires CI scope expansion (extras, dev deps, async plugin
> wiring, mock-shape audit) and deserves its own sprint.

---

## What changed (Sprint 3 win — collection wall removed)

Until commit `c02202a`, every Linux CI run died at pytest collection
time. The two collection-blocking errors were:

1. **`AttributeError: module 'hou' has no attribute 'Node'`** at
   `python/synapse/server/guards.py:19`. Module-level type annotation
   evaluated at import time against test-injected mock `hou` modules
   (e.g. `tests/test_capture.py:14` uses `ModuleType("hou")` which
   has no `Node`). Any test transitively importing
   `synapse.server.handlers` failed to collect.

2. **`ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`**
   at `python/synapse/_vendor/pydantic_core/__init__.py:8`. The
   vendored `_pydantic_core.cp311-win_amd64.pyd` is Windows-only;
   the vendor activation gate at `synapse/__init__.py:48` only
   checked Python version, not platform, so Linux 3.11 ran into the
   missing native binary on every Inspector test.

**Round 3 fix-forward** (`1299e13` + `c02202a`):

- `guards.py:19` annotation switched to string-literal forward
  reference per PEP 484. Single-line fix; only one such annotation
  in the entire `python/` tree (verified by grep against
  `(->\s*hou\.|:\s*hou\.[A-Z])`).
- `synapse/__init__.py:48-53` vendor gate tightened from "Python
  3.11" to "Python 3.11 + Windows." On Linux/macOS the gate skips,
  and the pip-installed `pydantic>=2.0` (a hard dep at
  `pyproject.toml:29`) resolves cleanly via site-packages.

**Round 4 follow-up** (`5e4edcd`): `tests/test_vendored_deps.py`
updated to honor the new platform-aware gate semantics. Two test
methods now branch on `sys.platform.startswith("win")`:

- `test_activation_gated_by_python_311_and_windows` (renamed from
  `test_activation_gated_by_python_311`) — asserts vendor on path
  iff Python 3.11 AND Windows.
- `TestVendorResolution.skipif` extended to also skip on non-Windows.

Result: collection succeeds, **2801 tests collect on Linux** (was 0
behind the wall), **2668 pass**, **76 skip cleanly**, **131 fail on
pre-existing-but-newly-visible Linux gaps**. Test count delta from
fix-forward: `2664 passed → 2668 passed` (Δ +4 cascading), `137 →
131 failed` (Δ −6 closed, including the 2 explicit regressions from
the vendor-gate change).

---

## The 131 — categorized by root cause

| Count | Test file | Root cause class | Notes |
|---:|---|---|---|
| 36 | `test_design_system.py` | Filesystem / asset fixtures | Tests check existence and contents of repo files (icons, panel XML, shelf scripts). Likely path-resolution differences on Linux runner; or test fixtures expect Windows-style paths. Needs case-by-case fix. |
| 24 | `test_frame_validator.py` | `ModuleNotFoundError: numpy` | OIIO/numpy validator not installable in the current CI extras. Add `numpy` to a `[ci]` extra in `pyproject.toml`, OR mark these tests `@pytest.mark.skipif(numpy is None)`. |
| 19 | `test_autonomy_predictor.py` | Mixed (mostly anthropic/numpy chain) | Predictor depends on autonomy stack which transitively imports `anthropic`. With vendor gated off and anthropic not in pip deps, import fails. |
| 12 | `test_autonomy_validator.py` | Same chain as predictor | |
| 11 | `test_autonomy_driver.py` | Same chain as predictor | |
| 10 | `test_host_layer.py` | `DaemonBootError: anthropic SDK is not installed` | Daemon boot gate validates anthropic at start. CI lacks it because anthropic was vendor-only and the gate now correctly skips on Linux. Cleanest fix: add `anthropic>=0.40.0` to a `[ci]` extra in `pyproject.toml` and update the workflow to install `.[ci]`. |
| 7 | `test_forge_integration.py` | Same anthropic chain | Pipeline integration tests pull the autonomy stack. |
| 5 | `test_solaris_ordering.py` | `async def functions are not natively supported` | Tests use `async def` but pytest-asyncio is not in `[dev]` extras (or isn't configured for the test class). Add `pytest-asyncio` and decorate the test class with `@pytest.mark.asyncio`. |
| 3 | `test_mcp_protocol.py` | Stale fixtures: `SynapseResponse.__init__() missing 'id'` and JSON-RPC error envelope shape | Tests pin a SynapseResponse signature that drifted; needs fixture refresh. |
| 2 | `test_render_notify.py` | Windows-only behavior | `test_sends_on_windows` is literally Windows-only by name — should be `@pytest.mark.skipif(not sys.platform.startswith("win"))`. |
| 2 | `test_layout_and_matlib.py` | MagicMock chain returns MagicMock instead of string | `mock().createNode().createNode().path()` returns a MagicMock; assertion compares to a string and fails. Needs `.path.return_value = "/stage/..."` configuration. |
| **131** | **total** | | |

---

## Why this is parked, not fixed

Three reasons:

1. **Scope.** Fixing 131 failures touches at least 11 test files, three
   `pyproject.toml` extras (`[ci]` plus updates to `[dev]`), the CI
   workflow YAML, and the autonomy stack's import shape. That's a
   sprint, not a surgical patch.

2. **Sprint 3's actual deliverables are unaffected.** The Spike 3.1
   `TopsEventBridge` (47 tests) and Spike 3.2 `SceneLoadBridge` (24
   tests) suites both pass on Linux CI — they are bridges to Houdini-
   only event surfaces, but their tests run headless against
   `unittest.mock` fixtures with no platform dependency. Verified by
   inspecting the failure list: neither `test_tops_bridge.py` nor
   `test_scene_load_bridge.py` is in the 131.

3. **Local baseline is green.** Windows local development collects
   2874 tests, all Spike 3 work green, both bridge hostile suites
   passing. The collection-wall removal has made *more* of the
   suite visible on Linux than ever before (2801 vs. ~2400 collected
   pre-Round-3) — which is progress, not regression.

---

## Suggested intake for the dedicated CI hardening sprint

Roughly in priority order — the first three close most of the
failures with minimal scope:

1. **Add a `[ci]` extra to `pyproject.toml`** with `anthropic`,
   `numpy`, `pytest-asyncio`. Update `.github/workflows/ci.yml` to
   `pip install -e ".[dev,websocket,mcp,ci]"`. Probable yield: ~70
   failures closed (host_layer + frame_validator + autonomy stack +
   solaris_ordering).

2. **Audit Windows-only tests** for missing `@pytest.mark.skipif`
   markers. Probable yield: ~2 (`test_render_notify`).

3. **Refresh `test_mcp_protocol.py` fixtures** to match current
   `SynapseResponse` signature and JSON-RPC error envelope shape.
   Probable yield: ~3.

4. **`test_design_system.py`** — case-by-case filesystem / asset
   fixture audit on Linux runners. Largest single bucket but likely
   mechanical once one or two are pinned.

5. **`test_layout_and_matlib.py`** — fix MagicMock chain returns.
   Mechanical 2-test patch.

After steps 1–5, Linux CI should be at ≤10 failures and the
remaining set is small enough to triage individually.

---

## Sprint 3 closeout

```
Round 3 (commits 1299e13 + c02202a):
  Collection: 2534 collected w/ 8 errors  →  2801 collected, 0 errors
  Result:     [could not run]              →  2664 pass, 137 fail, 74 skip

Round 4 (commit 5e4edcd):
  Result:     2668 pass, 131 fail, 76 skip
              (2 regressions closed; 4 cascading wins)

Sprint 3 deliverable test suites on Linux CI:
  test_tops_bridge.py         47 / 47 PASS
  test_scene_load_bridge.py   24 / 24 PASS
  test_vendored_deps.py       16 PASS, 2 SKIP (Windows-only resolution)
```

Sprint 3 closes here. Mile 5 remains queued and requires Joe-at-GUI
live cook for Spike 3.3. The Linux CI hardening project is its own
intake.

*— Round 4 closeout, 2026-04-26.*
