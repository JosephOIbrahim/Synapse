# L8 — Heavy cook/render freezes the GUI: design + status

> From the L8 design workflow. **Shipped (min mitigation, headless-gated):** MCP + PDG dispatch routed through `run_on_main` (PR — branch `feat/l8-mainthread-mitigation`) + the `shot_render_ready` `verify=False` readback skip (PR #32). **Owed (real GUI fix, needs live Houdini):** the husk-subprocess render in §3, and the items in 'must NOT author blind'.
>
> **⚠ LIVE-VERIFIED 2026-06-26 — the host is INDIE, which guts §3 for this user.** Probe: `hou.licenseCategory() == hou.licenseCategoryType.Indie` (and `hou.isIndieMode` does NOT exist — the §3 detection-API guess was wrong; use `licenseCategory`). **husk no-ops on Indie**, so the out-of-process husk render (§3) — the only thing that keeps the GUI heartbeat alive during a render — is **INERT on Indie** and falls back to the in-process GL flipbook. §3 therefore benefits **Commercial/Education only**; it cannot be render-verified on this host. **On Indie the GUI-freeze levers are cook-avoidance:** the `verify=False` readback skip (PR #32) is the build-cook fix; the render scene-cook freeze is largely inherent. husk binary confirmed at `$HFS/bin/husk.exe`; karmarendersettings `engine` menu = `cpu`/`xpu`.

---

Verification complete — every prime site confirmed live-in-code. Here is the design.

---

# L8 Fix — Heavy Karma-XPU cook/render freezes the GUI main thread

**Verified against:** `python/synapse/server/handlers_render.py`, `main_thread.py`, `mcp/server.py`, `solaris_compose_tools.py`, `handlers_solaris_compose.py`, `handlers_tops/_common.py` (H21.0.631 / SYNAPSE branch `feat/panel-redesign-harness`).

One correction up front: the prompt's `run_on_main(timeout=timeout_for(...))` references a helper that **does not exist yet** — there is no `timeout_for` in `main_thread.py` (only `_DEFAULT_TIMEOUT=10.0` at `main_thread.py:20` and `_SLOW_TIMEOUT=30.0` at `:21`). Designing that helper is part of this fix, not a call to existing code.

---

## 1. What actually freezes the GUI — the honest mechanism

The freeze is **the main thread executing `node.render()` to completion**, nothing else:

- `handlers_render.py:451` — `node.render(frame_range=(cur, cur), verbose=False)` runs the full Karma/XPU cook synchronously.
- It runs inside `_render_on_main` (defined `handlers_render.py:239`), dispatched at `handlers_render.py:490` via `hdefereval.executeInMainThreadWithResult(_render_on_main)` — **blocking, no timeout, no abandon**.
- The panel heartbeat is a QTimer on the **same main thread** (`synapse_panel.py` 1s beat → `freeze_chain` watchdog). A blocking main-thread call **kills the beat**, so the watchdog sees a stall at 5s and "escalates" at 30s — but over the live `hwebserver` transport there is **no resilience layer to halt** (escalation only logs unless an *active* bridge object already exists). The watchdog is a smoke detector with no sprinkler.

**Does routing through `run_on_main` unfreeze the GUI? No.** `run_on_main` (`main_thread.py:114`) swaps the *blocking* `executeInMainThreadWithResult` for `executeDeferred` + `Event.wait(timeout)`. On timeout it sets `abandoned[0]=True` (`:170-172`) and raises `RuntimeError` (`:174`) so the **caller/transport** stops waiting. But:

1. The work is still **queued onto the main thread** via `executeDeferred` (`:168`). Once `node.render()` has *started*, the abandon flag (checked only *before* `fn()` runs, `:156-158`) cannot stop it — the GUI cooks to completion regardless.
2. The QTimer heartbeat is dead for that whole window no matter which dispatch primitive you use.
3. Reentrancy caveat (`main_thread.py:127-135`): if the caller is already on the main thread, `run_on_main` runs `fn()` **directly with no timeout** — so a same-thread caller gets zero protection.

**Therefore `run_on_main` only un-wedges the agent/transport; it never un-freezes the GUI.** Only **out-of-process render (husk subprocess)** keeps the main thread free so the QTimer keeps beating. Every in-process variant freezes the GUI for the cook's duration — full stop.

---

## 2. MINIMUM MITIGATION (headless-safe, ship now)

Goal: convert "**hangs forever, agent zombied, session wedged**" into "**agent/transport fast-fails at a ceiling; GUI may still cook but the session is never permanently wedged**." This does **NOT** stop the GUI freeze and does **NOT** keep the heartbeat alive — be explicit about that with anyone reviewing.

### 2.0 New helper — `timeout_for(tool_name)` (`main_thread.py`)

Add next to the existing constants (`main_thread.py:20-21`):

```python
import os
_RENDER_TIMEOUT = float(os.environ.get("SYNAPSE_RENDER_TIMEOUT", "600"))  # cold-XPU ceiling

# Reuse the render-tool set already defined for SSE at mcp/server.py:527-531
# (single source of truth — do NOT duplicate the list).
_HEAVY_TOOLS = frozenset({
    "houdini_shot_render_ready", "synapse_solaris_build_graph",
    "synapse_solaris_assemble_chain", "synapse_configure_render_passes",
    "tops_cook_node", "tops_batch_cook", "tops_cook_and_validate",
    "houdini_execute_python", "houdini_execute_vex", "synapse_batch",
})

def timeout_for(tool_name, render_tools):
    if tool_name in render_tools:   # the SSE render set, passed in
        return _RENDER_TIMEOUT
    if tool_name in _HEAVY_TOOLS:
        return _SLOW_TIMEOUT
    return _DEFAULT_TIMEOUT
```

Render ceiling is deliberately **generous (600s)**: the point of the render-path timeout is to release a *truly wedged* transport, **not** to false-abort a legit 256s cold-XPU render. A short ceiling would regress real renders. This is the honest tension — in-process render can't have both "fast-fail" and "don't kill legit slow renders." Subprocess (§3) is what resolves it.

### 2.1 L7 — `mcp/server.py` (PRIME, highest value, lowest risk)

The MCP transport calls `executeInMainThreadWithResult` **directly** at four sites, bypassing `run_on_main` entirely — so C6 `dispatch_wait` is blind, the stall detector at `:447` is consulted but **never fed**, and nothing fast-fails. The WS/panel transport already routes per-handler through `run_on_main` (e.g. `handlers_render.py:1302`, `handlers.py:810`); **the MCP path is the unprotected sibling.** Import path is already proven safe — `mcp/server.py:59` already does `from ..server.main_thread import is_main_thread_stalled`.

| file:line | current | change |
|---|---|---|
| `mcp/server.py:489` | `executeInMainThreadWithResult(dispatch_tool, handler, tool_name, arguments)` | `run_on_main(lambda: dispatch_tool(handler, tool_name, arguments), timeout=timeout_for(tool_name, _RENDER_TOOLS))` |
| `mcp/server.py:429` | read-only dispatch | `run_on_main(lambda: dispatch_tool(handler, tool_name, arguments), timeout=_DEFAULT_TIMEOUT)` |
| `mcp/server.py:359` | `synapse_project_setup` init | `run_on_main(lambda: dispatch_tool(handler, "synapse_project_setup", {}), timeout=_SLOW_TIMEOUT)` |
| `mcp/server.py:575` | resource read | `run_on_main(lambda: handler.handle(command), timeout=_DEFAULT_TIMEOUT)` |

Add to the import at `:59`: `from ..server.main_thread import run_on_main, timeout_for, _DEFAULT_TIMEOUT, _SLOW_TIMEOUT`. Factor the SSE render set at `mcp/server.py:527-531` into a module constant `_RENDER_TOOLS` and pass it into `timeout_for`.

**Reentrancy interaction (must understand):** `dispatch_tool` → individual handlers that *already* call `run_on_main` internally (e.g. `_handle_render_settings` at `handlers_render.py:688`). When the outer `run_on_main` defers to main, `_tls.on_main` is True, so the inner `run_on_main` hits fast-path 1 (`main_thread.py:127-128`) and runs directly with no timeout — the **outer** `timeout_for` governs the whole call. Since the outer ceiling (`_RENDER_TIMEOUT`/`_SLOW_TIMEOUT`) is ≥ every inner timeout, this is **no regression** — it subsumes the inner timeouts under one ceiling. Note this in a comment so nobody "fixes" it later.

**What L7 fixes:** all MCP traffic (node creates, parm sets, cooks, renders) now fast-fails the transport at a per-tool ceiling instead of hanging forever; C6 `dispatch_wait` histogram regains visibility (`main_thread.py:155`); the stall detector gets fed via `_record_timeout` (`:173`). **What it does not fix:** the GUI freeze, the heartbeat death.

**Headless test** (`tests/test_mcp_dispatch_timeout.py`, new): stub `hdefereval.executeDeferred` to never fire; assert `_handle_tools_call` raises `JsonRpcError` (not a hang) within ~timeout; assert `timeout_for("houdini_render", render_set) == _RENDER_TIMEOUT` and `timeout_for("houdini_get_parm", render_set) == _DEFAULT_TIMEOUT`. Pattern already exists in `tests/test_main_thread_zombie.py:61-70`.

### 2.2 TOPS cluster — `handlers_tops/_common.py:76` (PRIME, one point fixes 28 sites)

`_run_in_main_thread_pdg` accepts a `timeout` arg but its docstring (`_common.py:70-73`) admits it **does not enforce it** — it calls blocking `executeInMainThreadWithResult` (`:76`) and only *logs* if >5s (`:79-93`). 28 TOPS call sites route through it.

**Change `_common.py:76`:** replace `result = hdefereval.executeInMainThreadWithResult(func)` with `result = run_on_main(func, timeout=effective_timeout)` (import from `..main_thread`). `effective_timeout` already exists at `:68`. Keep the timing logs. This restores fast-fail + C6 for cold PDG graph-context init across all 28 sites in one edit. **Headless-safe.**

**Headless test:** extend `tests/` TOPS coverage — stub the deferred queue, assert `_run_in_main_thread_pdg` raises on timeout instead of blocking.

### 2.3 L8 render dispatch — `handlers_render.py:490` and `:584`

| file:line | current | change |
|---|---|---|
| `handlers_render.py:490` | `executeInMainThreadWithResult(_render_on_main)` | `run_on_main(_render_on_main, timeout=_RENDER_TIMEOUT)` |
| `handlers_render.py:584` | `executeInMainThreadWithResult(_flipbook_on_main)` | `run_on_main(_flipbook_on_main, timeout=_DEFAULT_TIMEOUT)` |

`_handle_safe_render` (`:1308`, delegates at `:1506`) and `_handle_render_progressively` (`:1520`, calls `_handle_render` 3×) inherit the fix automatically.

**Honest verdict on the render dispatch specifically:** this buys *little*. A legit cold-XPU render genuinely needs minutes, so the ceiling must stay high (600s) to avoid false-aborting it — which means a truly-wedged render still blocks the transport for up to 10 minutes before releasing. And there's an **orphan-render race**: if the timeout fires mid-`node.render()`, `run_on_main` raises, the off-main poll at `handlers_render.py:498-502` (which is what actually sets `render_ok`) never runs, and the in-flight render output is orphaned; the agent gets "main thread busy, try again" and a retry re-renders. Acceptable as a "never wedge forever" backstop, **not** a real render fix. The render's real fix is §3.

**Headless test:** the render path can't run `node.render()` in CI (no `hou`); test only that the dispatch *routes through* `run_on_main` (monkeypatch `run_on_main` to assert it's called with the render timeout) and that a simulated timeout surfaces a clean error, not a hang.

**Gate for all of §2:** `python -m pytest tests/` (the CI command — not hython-only; per project memory the sibling PySide stubs make the full suite the real gate).

---

## 3. REAL FIX — husk subprocess (out-of-process, needs live verify)

This is the only design that keeps the GUI responsive: the main thread never runs the render, so the QTimer keeps beating and the freeze never happens. It fits the **existing two-hop structure** of `_handle_render` — the first main-thread hop just gets *lighter* (export instead of render), and the off-main middle does a subprocess instead of a pure file-poll.

### Design (all in `handlers_render.py::_handle_render`)

**Hop 1 — main thread (`_render_on_main`, replaces `node.render()` at `:451`):**
- Detect license category (Indie no-ops husk silently — project memory). **MUST verify the API** (see below).
- Resolve `$HFS` (already done at `:471`) → husk binary (`$HFS/bin/husk` / `husk.exe`).
- Export the composed stage to a temp `.usd`: `lop_node.stage().Export(usd_path)` (or drive the `usdrender_rop`'s own `lopoutput` write). **This still cooks the LOP composition on the main thread** — seconds for a heavy scene, but **not** the multi-minute Karma render. Be honest: the export cook is non-zero; it's seconds, not minutes. The bulk (BVH build, GPU kernel compile, sampling) moves out-of-process.
- Return `(is_indie, usd_path, husk_cmd, render_path_resolved, …)`.

**Off-main (WS handler thread, where `:493-502` already runs):**
- If `is_indie`: skip husk entirely → go straight to the **existing GL-flipbook fallback** (`handlers_render.py:540-584`) — it already works on all licenses.
- Else: `subprocess.run([husk, "--renderer", "<delegate>", "--frame", str(cur), "--frame-count", "1", "--output", render_path, usd_path], timeout=_RENDER_TIMEOUT, capture_output=True)`, then the **existing** output-file poll (`:498-502`) confirms success.
- If husk produces nothing (Indie slipped through, or error): fall to GL flipbook (`:533` onward) — already structured exactly this way.

**Hop 2 — flipbook fallback:** unchanged (`:540-584`), still a brief main-thread hou hop (viewport grab is seconds, acceptable).

### Blast radius
- **Scope:** `_handle_render` only. `_render_on_main` loses `node.render()`, gains export + license check. Off-main gains subprocess. Flipbook untouched. `safe_render`/`render_progressively` inherit it.
- **Risk surface:** USD-export fidelity (does the exported stage carry camera, resolution, samples, AOVs, output path identically to `node.render()`?); husk CLI flags + delegate id; Indie detection; **license-seat contention** (husk consumes a render/engine seat — on a single Indie/Core seat a husk subprocess launched *alongside* the running GUI may fail to acquire a license; this is the sharpest unknown).

### Must be LIVE-verified (do NOT author blind — Safety Rule 15)
1. **Indie detection API.** The prompt's `hou.isIndieMode()` is **unverified** — check the H21 symbol table / `synapse_scout` first. Likely real form: `hou.licenseCategory() == hou.licenseCategoryType.Indie`. Pick the one that's actually in the runtime table.
2. **husk binary path + exact flags + XPU delegate id** (`BRAY_HdKarmaXPU` vs `BRAY_HdKarma`) — confirm via `husk --help` live.
3. **Render parity:** husk-from-exported-USD must produce a pixel-equivalent result to in-process `node.render()` (camera, res, samples, AOVs, output path).
4. **License-seat contention** between the GUI and the husk subprocess.
5. **The freeze actually stops** — heartbeat keeps beating, QTimer fires, watchdog never trips during the subprocess render. This is the acceptance test and it requires live Houdini.

---

## 4. The build-readback cook (`build_karma_xpu_shot`)

`solaris_compose_tools.py:209-210`:
```python
rstage = sc.read_stage(out)        # → lop_node.stage() → COOKS the LOP chain
errs = sc.composition_errors(rstage)
```
Already marshaled with a timeout at `handlers_solaris_compose.py:93` (`run_on_main(_on_main, timeout=_SLOW_TIMEOUT)`), so the agent abandons at 30s — but the GUI cooks on, and on a cold-XPU heavy stage that cook is the freeze.

**Key observation:** the synchronous cook comes **only** from `read_stage(out)` at `:209`. Setting the Display flag at `solaris_compose_tools.py:202` marks the node for a *lazy* cook (next viewport redraw, during idle) — it does **not** force a synchronous cook inside the build. So the readback is the *only* thing forcing a heavy cook on the build path.

**Recommendation (headless-safe, do it):** gate the readback behind a `verify=True` param on `build_karma_xpu_shot`. Default `True` to preserve current behavior for the explicit `[REAL]`-verifier path; have `shot_render_ready`'s scaffold-only build pass `verify=False`. With `verify=False`:
```python
if verify:
    rstage = sc.read_stage(out)
    errs = sc.composition_errors(rstage)
else:
    errs = None  # composition validated lazily on first viewport cook
result["composition_errors"] = errs
```
This removes the synchronous cold-cook from the empty/scaffold build entirely; the Display flag still drives a lazy cook on redraw (main thread, during idle, off the build's critical path). It is pure control-flow — **no hou semantics change** — so it's gated by `python -m pytest tests/` (mock `sc.read_stage`, assert it is **not** called when `verify=False`, and **is** called when `verify=True`).

Don't go further (e.g. ripping out the Display flag) — that changes which node is the displayed terminal and would surprise the verifier. The `verify` flag is the minimal, surgical lever.

---

## 5. SHIP ORDER + blast radius

### Ship now — headless-gated (`python -m pytest tests/`)
1. **`timeout_for` + `_RENDER_TIMEOUT`** in `main_thread.py` (§2.0). Foundation for the rest.
2. **L7 — `mcp/server.py:489/429/359/575`** through `run_on_main` (§2.1). **Highest value / lowest risk** — all MCP traffic fast-fails, C6 visibility + stall feed restored, achieves parity with the already-protected WS transport. Watch the reentrancy-subsumption comment.
3. **TOPS — `handlers_tops/_common.py:76`** through `run_on_main` (§2.2). One edit, 28 sites, fixes the "logs but never enforces" timeout lie.
4. **L8 render dispatch — `handlers_render.py:490/584`** through `run_on_main` (§2.3). Lower value (barely helps legit-slow renders) but closes the "wedge forever" hole; ship it with the honest comment that it does **not** fix the freeze.
5. **Build readback — `build_karma_xpu_shot` `verify` param** (§4). Removes the cold-cook from scaffold builds.

All five are routing / timeout / control-flow only. No `hou` semantics authored. Suite-gated.

### Waits for the live bridge
- **§3 husk subprocess** — the only thing that actually stops the freeze, and the only thing that **must not be authored blind**. Every item in §3's live-verify list (Indie API, husk flags, delegate id, export parity, license-seat contention, heartbeat-survives proof) needs a running Houdini. Writing the husk command, the `Export()` call, or the `hou.licenseCategory()` check from memory and shipping it un-run is exactly the phantom-API failure class (Safety Rule 15) — gate it behind `synapse_scout` + a live render.

### Must NOT author blind (flag loudly)
- `hou.isIndieMode()` — **unverified**, likely wrong; verify against the H21 symbol table before emitting.
- husk CLI flags + `BRAY_HdKarmaXPU` delegate id.
- `lop_node.stage().Export()` render-config fidelity.

### Honest bottom line
Items 1-5 make the **session survivable** (transport fast-fails, never permanently wedged, instrumentation restored) but a heavy render **still freezes the GUI** for the cook's duration and the `freeze_chain` watchdog over `hwebserver` still has no sprinkler. **Only §3 (out-of-process husk) makes the GUI stay responsive** — and it can only be verified live. Ship 1-5 as the durability floor this session; schedule §3 for the next live-bridge window.

Key files: `C:/Users/User/SYNAPSE/python/synapse/server/main_thread.py`, `C:/Users/User/SYNAPSE/python/synapse/mcp/server.py`, `C:/Users/User/SYNAPSE/python/synapse/server/handlers_render.py`, `C:/Users/User/SYNAPSE/python/synapse/server/handlers_tops/_common.py`, `C:/Users/User/SYNAPSE/python/synapse/server/solaris_compose_tools.py`, `C:/Users/User/SYNAPSE/python/synapse/server/handlers_solaris_compose.py`.
