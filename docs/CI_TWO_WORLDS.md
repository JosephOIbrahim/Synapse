# CI and your machine run different suites. Here is the difference.

**Short version:** neither world runs the whole suite. Each is missing something
the other has. CI runs everything it can and prints the name of everything it
can't; hython runs the Houdini tests but is missing pip dependencies.

---

## The two commands

```
# What CI runs. Missing hou and pxr.
pytest tests/ -m "not needs_houdini" -rs

# What hython runs. Has hou and pxr; missing websockets and mcp.
hython -m pytest tests/
```

Same tests, same asserts, same conftest. What differs is what's installed.

## Measured, on Houdini 22.0.368 (Python 3.13.10)

| | stock CI runner | hython |
|---|---|---|
| `hou`, `pxr` | absent | **present** |
| `websockets`, `mcp` | present | **absent** |
| collected | 5892 | 5892 |
| the 40 `needs_houdini` tests | deselected | **39 pass, 1 fails on `websockets`** |
| collection errors | 0 | **5** |

The 5 hython collection errors are all the same missing dependency:

```
tests/test_load.py                                  ModuleNotFoundError: mcp
tests/test_passthrough_hygiene.py                   ModuleNotFoundError: mcp
tests/test_port_wave_scene1.py                      ModuleNotFoundError: websockets
tests/test_websocket_cancel_inflight_known_defect.py ModuleNotFoundError: websockets
tests/test_websocket_cancel_reachable.py            ModuleNotFoundError: websockets
```

plus `test_hwebserver_integration.py::test_hwebserver_available`, which needs
`websockets` at line 91.

`python/synapse/_vendor` does **not** carry `websockets` or `mcp` — it vendors
pydantic/anthropic and friends. Those two come from pip, and Houdini's bundled
Python has no pip install of them. To close the gap on your machine, install
them into Houdini's interpreter:

```
hython -m pip install websockets "mcp==1.26.0"
```

Until you do, "I ran the full suite locally" means 5892 collected minus 5
modules that never got there.

---

## Why CI can't run everything

A stock GitHub runner has no Houdini. That means two modules are missing:

- **`hou`** — Houdini's own Python module. It exists only inside Houdini or
  `hython`. There is no pip install for it.
- **`pxr`** — OpenUSD. Not installed on the runners.

Some test modules can't even be *imported* without one of those. Those modules
carry the `needs_houdini` marker, and CI filters them out.

---

## How a module earns the marker

You never write `needs_houdini` by hand. `tests/conftest.py` applies it during
collection, by reading the module with `ast` and looking for exactly three
things at **module level**:

1. an unguarded `import hou` / `from pxr import ...`
2. a `pytest.importorskip("hou")` / `pytest.importorskip("pxr")`
3. a `pytestmark = pytest.mark.skipif(...)` whose condition names the runtime

Anything nested doesn't count. A `try: import hou / except ImportError:` is
nested. An import inside a function is nested. An `import hou` inside a string
of code that gets shipped over the wire — `tests/test_e2e_tops.py` does this —
is not an import at all.

The bias is deliberate: **under-marking is free, over-marking hides tests.**

---

## Why the filter can't hide a broken test

This is the part worth trusting, so here is the actual guarantee.

A module only earns the marker if it **already refuses to run** without its
runtime — via its own `importorskip` or its own `skipif`. So the marker is
redundant with a gate the module was already carrying. Everything the filter
removes would have been skipped anyway.

`tests/test_needs_houdini_marker.py` enforces that. It fails if any marked
module lacks its own gate, and it fails if the detector starts marking modules
that don't need a runtime.

Measured on a CI-equivalent checkout (Python 3.14, no `pxr`, no `hou`):

```
pytest tests/                          5682 passed, 215 skipped
pytest tests/ -m "not needs_houdini"   5682 passed, 175 skipped, 40 deselected
```

Same 5682 passes. The 40 deselected come straight out of the 215 skipped.
Collection is identical either way — `--collect-only` reports 5892 both times;
only *selection* differs.

---

## Nothing leaves a CI run silently

Two mechanisms, because skips and deselections print differently:

- **`-rs`** prints every skipped test with its reason. That covers the modules
  that skip themselves at import (the `pxr` ones — they never even get
  collected, so the marker never touches them).
- **The conftest prints the deselected set.** pytest prints nothing at all for
  `-m` deselections, which would be a real hole. So the summary gets a block
  like this:

```
=============== needs_houdini deselected (NOT silently dropped) ===============
NEEDS_HOUDINI  tests/solaris/test_live_wiring.py  [27 test(s)]  -- needs a
  Houdini runtime: this module requires `hou` (Houdini's Python module --
  exists only inside Houdini/hython, never on a stock interpreter)
NEEDS_HOUDINI  tests/test_h22_cops_solver_live.py  [5 test(s)]  -- ...
NEEDS_HOUDINI  tests/test_h22_setdressing_live.py  [4 test(s)]  -- ...
NEEDS_HOUDINI  tests/test_hwebserver_integration.py  [4 test(s)]  -- ...
40 test(s) in 4 module(s) deselected by -m 'not needs_houdini'.
```

If a test didn't run, its name and its reason are in the log.

---

## What CI still cannot tell you

Stated plainly, because a doc that hides a gap is worse than one that names it.

**The 40 deselected tests are the live-Houdini surface.** Karma renders,
Solaris wiring, COPs solvers, the hwebserver bridge. CI green says nothing
about them. Only `hython -m pytest tests/` does, run by a human on a machine
with Houdini — and 1 of the 40 needs `websockets` on top of that (see the table
above). Measured 2026-08-07 on 22.0.368: **39 of the 40 pass under real `hou`.**

**The 175 skips are not all Houdini.** Some are PySide, some are
`SYNAPSE_INTEGRATION=1`, some are `SYNAPSE_H22_LIVE=1`. Read the `-rs` block
rather than assuming.

**Moneta is only active when the deploy key is configured.** Without the
`MONETA_DEPLOY_KEY` secret, the private backend is never checked out and ~70
Moneta-gated tests skip. The workflow asserts the backend is importable when
the key IS present, so it can't half-activate silently.

---

## Reproducing a CI run locally

A git *worktree* is not a faithful stand-in — `tests/test_statusline.py` reads
`.git/HEAD` as a file path, and in a linked worktree `.git` is a file, not a
directory, so 4 statusline tests fail there for reasons that have nothing to do
with your change. Use a real clone:

```
git clone . /some/short/path        # short: the vendored SDK tree hits
cd /some/short/path                 # Windows MAX_PATH under a deep prefix
git checkout <your-branch>
git branch master origin/master     # test_d_track + test_perf_ratchet anchor on master

uv venv --python 3.14 .venv && uv pip install --python .venv/Scripts/python.exe -e ".[dev,websocket,mcp]"
uv pip install --python .venv/Scripts/python.exe C:/path/to/Moneta   # the v1.2.0-rc3 pin

.venv/Scripts/python.exe -m pytest tests/ -m "not needs_houdini" -rs
```

Do **not** install `pxr` into that venv. If `pxr` is importable you are testing
a third world that is neither CI nor Houdini.

**On Windows + Python 3.11 specifically:** three tests assert `elapsed > 0` on a
clock whose granularity is ~15.6 ms, so they fail intermittently
(`test_routing.py::test_latency_is_tracked`,
`test_sessions.py::test_expire_stale`, and `test_pkg_bootstrap_invariant.py::
test_r310_shapes_leave_no_runtime_divergence`, which subprocess-runs the first).
They pass on ubuntu-3.11 and macos-3.11, which is what CI actually runs. They
are pre-existing and unrelated to the marker.
