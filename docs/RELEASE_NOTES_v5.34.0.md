# v5.34.0 — five tools nothing could call

*2026-07-25: the Solaris tool family shipped in Phase 2 and was **never reachable**. All five lived in `synapse/mcp/tools/solaris/` — a tree outside the installable `python/synapse/` package — and none appeared in `_tool_registry.py`. No `/mcp` or `/synapse` path could invoke any of them. Their tests sat outside `testpaths` and drove a `MagicMock` `hou`, so they had never run and could not have failed if they had. `import_megascans` raised `hou.PermissionError` on **every** invocation. `set_purpose` returned `status="set"` having set nothing. All five are now relocated, registered, live-verified on 22.0.368, and tested against a real Houdini. **4,873 passing · 0 failed · 128 skipped** — +231 against v5.33.0. Gate 0.1 closes with them.*

---

## What changed for you

- **Five Solaris tools exist for the first time.** `component_builder`, `scene_template`, `create_variants`, `set_purpose` and `import_megascans` are registered and callable. Previously they were unreachable code with passing tests — the tests asserted against a mock, so no amount of breakage could have surfaced.

- **`import_megascans` completes.** It targeted `usdimport` at a `componentgeometry`, which is a locked HDA: `hou.PermissionError`, every time, under every parameter set. Worse, it raised *inside* `hou.undos.group` after the subnet already existed, leaving partial state. It now targets the interior `sopnet/geo` subnet, live-probed as writable.

- **`set_purpose` no longer reports success for work it did not do.** There is no `purpose` parm on `componentgeometry` in 22.0.368 — a live parm sweep finds none containing the word. Every call took the fallback and returned `status="set"`.

- **Consent gates no longer announce decisions that never landed.** `_on_approve` and `_on_reject` caught every exception from `gate.decide()`, logged it, then marked the card decided and emitted the announcement anyway. The artist saw APPROVED, the chat said APPROVED, the gate recorded nothing. The reject path was worse: a reject that never reached the gate had blocked nothing. Emits are now conditional; a failed decision reads `NOT RECORDED — GATE UNREACHABLE` and stays live.

- **Copernicus has a coverage number.** 384 live COP types on 22.0.368, integrity-hashed, zero probe errors — against LOP's 218. It had never been counted. Grounding stands at 6.2%, which is the point of measuring it.

---

## The corrections

Three claims in this repository were wrong. They are the reason this release exists in the shape it does.

**`hou.undos.group` groups; it does not reverse.** The stated guarantee — *"every mutation is reversible"* — was overstated. It groups undo entries so one Ctrl+Z reverses a completed operation. It does **not** roll back when the wrapped block raises: a partial network survives and the artist must undo it deliberately, while `IntegrityBlock` still reports `undo_group_active=True` at fidelity 1.0. Corrected in `CLAUDE.md` and `README.md`.

`python/synapse/host/graph_builder.py:165-181` is the exception and is now named as one — it carries explicit unwind bookkeeping and returns a structured `FAILED` with zero net mutation. Generalising that to the handler paths is open work.

**`hpath`, not `path`.** The checked-in `packages/synapse.json` claimed `hpath` in its comment and emitted the deprecated `path` in its body. SideFX's own H22 packages use `hpath` exclusively — six occurrences across `apex.json`, `apex_cop.json`, `kinefx.json` and three others, zero of `path`. `path` still works, which is why nobody noticed.

**The suite count now carries its interpreter.** 4,873 passing describes system Python 3.14.2. Under `hython3.13` — what Houdini actually runs — the vendored SDK is active and the number is different. Both are now recorded as a tuple; neither substitutes for the other.

---

## Gate 0.1 closes

Open since drop week. Task number one in the ledger, and the longest-open item in it.

The question was sidecar versus abi3 for the cp311/cp313 vendored seam, and it was blocked on a segfault: under `hython3.13` the suite took a Windows access violation. That looked like an ABI problem.

It was not. The crashing frame is `QApplication::font()` at `tests/panel/test_font_scale.py:65`, with **zero frames under `python/synapse/_vendor`** anywhere in the traceback, `_VENDOR_ABI_RISK` reporting `False`, and `import synapse` clean. Isolation with controls on both sides:

```
tests/panel/ alone                        27 passed, no crash
tests/panel/ + tests/test_hda_panel.py    ACCESS VIOLATION
tests/test_font_scale.py alone            8 passed
```

`tests/test_hda_panel.py` plants `sys.modules["PySide6"]` stubs at module scope. pytest imports every test module at collection, so the fake Qt is resident before the first panel test runs.

**The vendored path stands. No sidecar is required on ABI grounds.** It remains available for process isolation, crash containment or independent release cadence — each of which would need its own case.

---

## The mechanism

The repair was **roots before symptoms**, in a fixed order, and the order was the whole method.

1. **One tree.** `synapse/mcp/tools/solaris/` → `python/synapse/mcp/tool_impls/solaris/`, registered in `_tool_registry.py`. (`tool_impls`, not `tools`, because `mcp/tools.py` already exists as a module — a `tools/` package beside it collides.)
2. **Collect the tests.** `pyproject.toml` `testpaths` corrected.
3. **Delete the `MagicMock` `hou` fixture.** This was the load-bearing move. A mock-`hou` test asserts your assumptions back at you and cannot fail when reality disagrees — which is exactly how a tool that raised on every invocation stayed green. Replaced with hython-gated tests that **skip** without Houdini. A skip is honest; a pass is a lie.
4. Only then repair the defects, each with a pin shown to fail before and pass after.

Repairing before step 3 would have produced fixes verified by tests that could not fail. One did happen — a defect was repaired whose premise was later refuted live, its regression pin passing against both the fix and its inverse. Adversarial mutation testing caught it, and mutation testing is now the standard for every pin.

---

## Known limitations

Stated here because they are real, they are not new, and they have shipped in every prior version undocumented.

- **Stop cannot cancel an in-flight cook.** `_on_stop` aborts the agent loop cooperatively and is honest about it — it refuses to claim idle and waits for the worker. But cancelling the running tool needs off-UI-thread dispatch against a live bridge, which is deferred. An artist mid-Karma-render has a Stop that will not stop the render. `EmergencyProtocol.trigger_emergency_halt` exists and is not yet surfaced as a distinct control.

  > **CORRECTION, added 2026-07-28 (R73, H3b).** The sentence above is right about `_on_stop` and right that the gap shipped, but it was read at the time as meaning *Houdini exposes no way to stop a render*. **That is false, and the error was ours.** A render **can** be stopped: the hscript command `rkill` works and has been available the whole time (`hou.hscript("rkill <pid>")`, with `rps` to list background renders). What is actually missing is narrower and both halves are verified on 22.0.368: **`hou.RopNode` carries no cancel/abort/interrupt verb**, so a Python integrator holding a ROP has nothing to call; and **`hou.ActiveRender` — the documented HOM replacement for `rkill`/`rps` — is `#status: ni` and absent at runtime.** The limitation is a missing *HOM surface*, not a missing capability. Closed in v5.37.0 by `render_stop` / `render_processes`; see `python/synapse/server/render_stop.py` for the measured ROP→process mapping and the partial-frame behaviour of each renderer.
- **`websockets` and `mcp` are required and not vendored.** They must be present in the Python running SYNAPSE. Fresh installs on Houdini's Python will not have them.
- **The tool schemas have zero consumers.** `set_purpose`'s declared return enum has already drifted from its implementation. Schemas are what the model is told a tool returns, so a drifted schema misinforms the agent rather than merely failing to document it.
- **COP grounding is 6.2%** of 384 Copernicus types; LOP is 40 of 218.
- **The panel is 23,365 LOC** and 41% of its affordances were found ORPHAN or SILENT. Removal and repair are scoped, not done.

---

## Verifying any of this

```
python harness/relay_status.py
python harness/heats_status.py
powershell harness/run_suite_shipping_python.ps1
```

Live catalogues in `harness/notes/`: `h22_lop_catalog_live_22.0.368.json` (218 types) and `h22_cop_catalog_live_22.0.368.json` (384 Cop, 169 Cop2), both integrity-hashed, zero probe errors.

House rule, adopted this release: **no number enters a document without a producer path beside it.**
