# flow — the journey rig (W6-FLOWRIG)

**hython 22.0.400 drives real panel-to-network flows and measures every step.**

Flow 2/4 of wave 6. Consumes the JRNY user-flow map (`docs/USER-FLOW-MAP.md`
@`10d3746f`, bus `n=18cc62114a72930c`): **6 journeys · 30 predicates**, one
assertable proposition per step. This rig turns each predicate into a first-hand
measurement under the live seat.

Usability is **measured, not opined**. Every number in `flow_results.json` traces
to the `hython_stdout.txt` printed alongside it.

---

## Run it (the seat recipe)

```bash
env -u SYNAPSE_ROOT -u HOUDINI_PACKAGE_DIR \
    HOUDINI_USER_PREF_DIR="C:/Users/User/OneDrive/Documents/houdini22.0" \
    "C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" \
    harness/probes/flow/probe_flow.py
```

`SYNAPSE_ROOT` / `HOUDINI_PACKAGE_DIR` are **unset on purpose** so the SYNAPSE
package loads only through the prefs-dir scan — the exact mechanism the GUI seat
uses (W5-PARITY/W5-SEAT recipe). The panel and handlers load from the **main
tree** (`<repo>/python/synapse`); the rig asserts against the shipped source.

The bad-prompt acceptance test (acceptance #2, evidence `test`):

```bash
... hython.exe -m pytest harness/probes/flow/test_bad_prompt_journey.py -q
```

---

## What it measures

Per journey step (`target #2`): **wall latency**, **panel feedback** presence +
readability (non-empty, non-traceback), **node count / names / layout-bbox
sanity** (no stacked-at-origin spaghetti), **undo-group name** present +
descriptive, and **error-path humanity** for the bad-prompt journey.

Two paths reach Houdini, per `CLAUDE.md`:

- **/synapse handler-direct** — `SynapseHandler()._handle_*` builds real nodes and
  opens the LIVE inline undo group (`synapse_node_create` / `_connect` /
  `synapse_set_parm`), captured from the real undo stack
  (`hou.undos.undoLabels()`; `areEnabled()==True` at this seat).
- **panel spine** (`target #1`) — `SynapsePanel()` instantiated offscreen; a build
  is driven **through** the panel's own `ToolExecutor.execute_tool`, so a real
  node lands in a scratch `.hip` and the panel's feedback is read back headless.

---

## Files

- `probe_flow.py` — the rig. Runs all 6 journeys, writes `flow_results.json`,
  prints the receipt.
- `flow_results.json` — structured per-step verdicts + measurements (last run).
- `hython_stdout.txt` — the raw first-hand hython receipt every number traces to.
- `test_bad_prompt_journey.py` — acceptance #2 pytest (readable in-panel error,
  no traceback, session alive). Runs under `hython -m pytest`.
- `test_bad_prompt_stdout.txt` — that test's receipt.

---

## Last run (product HEAD `8e278b65`)

**30 predicates · PASS 28 · FAIL 2 · UNKNOWN 0.**

- **FAIL J4.3 / J4.4** are the map's **expected-red** friction, confirmed
  first-hand — not rig failures:
  - `J4.3` `compositor._repolish_tree` imports `qtpy` (uninstalled at the seat →
    the density repaint no-ops entirely) **and** has a premature `break` (root-only
    repolish even when `qtpy` is present).
  - `J4.4` `compositor._apply_spec` collapses one-way (`setMaximumHeight(0)` with no
    restore branch); a switch-back never un-collapses. Confirmed by a micro-probe.
- **DIVERGENCE J1.1** — the map marks `SYNAPSE_synapse.png` as today-FAIL/absent;
  it is **PRESENT** at HEAD (blob `23149fd8`). A good-news correction (the fix
  already landed at `2dd6bab6`); threaded back to JRNY.
- **Advisory J5.4** — the pypanel help says "115 built-in tools"; the live
  registry `synapse.mcp._tool_registry.TOOL_DEFS == 129`. A **doc-fix flag**, not a
  code defect (the step predicate — the "/" palette substring — passes).

## Known limitations (stated, not hidden)

- **No live model call.** Builds are driven through the deterministic
  ToolExecutor/handler seam; the provider (LLM) stage is bypassed by construction,
  so every number is reproducible from committed stdout. No generation is looped
  (`target #4`). The **LLM-narration half** of panel feedback is recorded UNKNOWN.
- **The four `†` proxies keep their gui-only half UNKNOWN by construction** — the
  headless proxy is measured, the visible half is not:
  `J1.5` live per-task counter render · `J2.4` the single artist Ctrl+Z reversing a
  full rig · `J4.3` the visible density change · `J6.5` the visible transcript
  repaint on reopen. All four proxies were **reachable** — none had to be weakened
  to a source-presence assertion.
- **True pixel rendering stays UNKNOWN** (Joe seat) — this rig never claims a
  rendered frame.
