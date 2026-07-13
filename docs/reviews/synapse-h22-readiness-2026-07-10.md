# SYNAPSE H22 readiness review — 2026-07-10

> External CTO-style review received 2026-07-10 against HEAD `314acd6` (v5.22.0).
> This document is the evidence anchor the **R track** (release-readiness) wraps into
> durable regression gates — see `harness/notes/spec-R-release-readiness.md`.
> Every code claim below was adversarially verified against the live tree on 2026-07-10
> (11-agent verification sweep; all claims CONFIRMED, several refined — refinements are
> recorded in the spec, not edited into this document. This file preserves the review verbatim.)

## Verdict

**Do not ship the current `master` as "Houdini 22 ready."**

Treat HEAD `314acd6` as **H22 RC0**:

* **Compatibility detection:** strong
* **Clean installation:** not proven
* **Dependency isolation:** release-blocking
* **Mutation safety:** contains a fail-open path
* **Runtime lifecycle:** tied too closely to the panel
* **CI evidence:** does not cover the environment most likely to break

The repository has unusually good machinery for discovering Houdini drift. The weakness is that **the detection system is more mature than the product's install, lifecycle, and failure behavior**.

The latest commit claims 4,186 passing tests and a July 15 H22 drop, but the count is also presented through a static badge rather than a dynamically verified test result. I could not independently confirm the full suite against the current HEAD or a real H22 runtime.

SideFX's public system-requirements page still identifies the current release as **Houdini 21** as of July 10, 2026. I could not independently verify the repository's exact **July 15, 2026** date from SideFX's public site, so that date should remain a planning assumption rather than product truth.

---

# First-principles model

For SYNAPSE to be H22-ready, seven invariants must hold:

1. A clean artist machine can install and see the panel.
2. SYNAPSE discovers host capabilities from the running build.
3. Dependencies cannot silently resolve from an incompatible Python environment.
4. Every mutation is either protected and recorded or rejected.
5. Safety services survive panel open, close, and reload cycles.
6. Tests exercise the actual shipping platform and host interpreter.
7. Every release claim is backed by a reproducible build-specific receipt.

SYNAPSE is strong on **2**. It is currently weak on **1, 3, 4, 5, and 6**.

---

# What is already strong

## 1. The H22 delta probe is the right architecture

`scripts/h22_api_delta.py` does three useful things against the running Houdini:

* Regenerates and diffs `hou` symbols.
* Rebuilds and diffs node-type/parameter catalogs.
* Re-probes Solaris/USD punycode parameter names.

It also ranks removed symbols using real SYNAPSE call sites and writes machine-readable and human-readable reports. This is much better than betting on documentation or a hand-maintained compatibility matrix.

**Keep this. Make its output a required release artifact.**

## 2. The drop-day sequence is operationally coherent

The runbook correctly separates:

* Host fact capture.
* Dependency ABI decision.
* Symbol-table generation.
* API and punycode probes.
* Test gates.
* Human promotion.

That is a sound release mechanism.

## 3. Houdini loading is mostly cleanly separated

The `.pypanel` is a thin loader with PySide6-first behavior and an in-panel traceback if construction fails. That is the right boundary between Houdini registration and product code.

## 4. Several previous H22 risks have been addressed honestly

The code now:

* Detects an incompatible vendored ABI rather than blindly loading it.
* Uses a Python-3.12-safe event-loop setup.
* Seeds panel surfaces from the live Houdini theme.
* Bounds PDG cooking rather than polling forever.

Those are real improvements, not cosmetic compatibility flags.

---

# Release blockers

## P0.1 — The dependency strategy is still an H22 boot cliff

The bundled native dependencies are activated only for:

```python
Python 3.11 + Windows
```

On another Python minor, the vendor tree is disabled and SYNAPSE relies on whatever `pydantic` and `anthropic` happen to be available in Houdini's environment. A clean artist installation does not install those packages into H22. The resulting diagnostic is better now, but the brain still does not start.

The runbook says the durable sidecar solution is **post-release** and that a Python bump will trigger a drop-day re-vendor commit. That means drop day is still surgery, despite the runbook describing it as verification.

### Required fix

Before release, choose one:

**Preferred:** ship the sidecar now.

**Minimum acceptable:** package versioned vendor roots:

```text
_vendor/
├── cp311-win_amd64/
├── cp312-win_amd64/
└── cp313-win_amd64/
```

Select exactly one from `sys.version_info` and platform. Do not depend on global or user site-packages.

### Exit gate

On a clean Windows account with no pip-installed packages:

```python
import synapse
from synapse.host.daemon import SynapseDaemon
```

must succeed in H22's Python, and the daemon must construct its provider client.

---

## P0.2 — Mutations fail open when the integrity bridge is unavailable

This is the most important code-level finding.

`ToolExecutor` attempts to send mutating operations through `execute_through_bridge()`. But an import failure falls back to direct `handler.handle(command)`. Inside the adapter, a missing bridge also falls back to direct dispatch.

That means an H22 packaging or import regression can produce this behavior:

```text
Safety layer failed to import
        ↓
Mutation still executes
        ↓
No guaranteed bridge receipt / integrity verification
```

That contradicts SYNAPSE's central product invariant.

### Required fix

Read-only tools may degrade gracefully. Mutations must fail closed:

```python
if is_read_only(tool_name):
    return handler.handle(command)

bridge = get_bridge()
if bridge is None:
    return SynapseResponse(
        id=command.id,
        success=False,
        error=(
            "Mutation blocked: SYNAPSE's integrity bridge is unavailable. "
            "No scene changes were made."
        ),
    )
```

Remove both direct-mutation fallbacks.

### Exit gate

Force `shared.bridge` to fail import and verify:

* Inspection still works.
* Create/delete/set/render operations do not run.
* The UI names the missing safety subsystem.
* No Houdini node or parameter changes.

---

## P0.3 — Freeze protection is owned by the panel widget

The 1-second freeze heartbeat is a `QTimer` parented to `SynapsePanel`. The code explicitly identifies the panel as the heartbeat source.

When the panel closes or is destroyed, its timer goes with it. Safety behavior therefore depends on whether an artist has a particular pane tab open.

The repository's own preparedness report previously identified daemon-side heartbeat behavior with the panel closed as the remaining live-Houdini ship blocker. Current code still has the panel-owned architecture.

### Required fix

Move heartbeat ownership into a process-lifetime service:

```text
Houdini process
└── SynapseRuntime singleton
    ├── freeze heartbeat
    ├── telemetry flushing
    ├── bridge/server lifecycle
    └── panel connections: 0..N
```

The panel should display runtime state, not create the runtime's liveness source.

### Exit gate

In a real graphical Houdini session:

1. Open SYNAPSE.
2. Start the runtime.
3. Close every SYNAPSE panel.
4. Verify heartbeat continues.
5. Stall the Houdini main thread.
6. Verify the breaker and emergency path fire.
7. Reopen the panel and verify it reconnects to the same runtime.

---

## P0.4 — Production panel loading has unsafe hot-reload semantics

Every time Houdini creates the panel, the `.pypanel` deletes all cached `synapse.*` modules:

```python
for _m in sorted(k for k in sys.modules if k.startswith("synapse.")):
    del sys.modules[_m]
sys.modules.pop("synapse", None)
```

That is useful during development but dangerous in production. Existing threads, servers, callbacks and singletons can retain objects from the old module graph while the new panel imports a second module graph.

Likely failure modes include:

* Duplicate bridge instances.
* Old and new class identities coexisting.
* Callbacks referencing unloaded module state.
* Reopened panels attaching to different singleton objects.
* Daemon threads surviving while their modules have been replaced.

### Required fix

Disable hot reload by default:

```python
if os.environ.get("SYNAPSE_DEV_HOT_RELOAD") == "1":
    # controlled reload
```

Production reopening should import normally and connect to the existing process runtime.

---

## P0.5 — Clean installation is not release-proven

There is an unresolved public issue from a Windows 11/Houdini 21.0.671 user who could import SYNAPSE but could not find either its shelf or Python panel. The issue remains open without a maintainer response. It also captured incompatible user-site packages leaking into hython.

The current installer is much better than the package JSON used in that report, but it has a drop-day trap:

* It only considers preference directories that already exist.
* A fresh H22 preference directory does not exist until Houdini has launched.
* Therefore auto-detection can omit H22 unless the user launches once or passes `--pref-dir`.

The runbook itself acknowledges this.

The installer tests verify generated JSON and temporary filesystem behavior. They do not prove Houdini parses the package, discovers the `.pypanel`, registers the shelf, or creates a node.

### Required fix

Add an explicit host-targeted installer:

```powershell
python scripts/install_synapse_package.py `
    --houdini-exe "C:\Program Files\Side Effects Software\Houdini 22.0.xxx\bin\houdini.exe"
```

From the executable, derive:

* Major/minor preference directory.
* Hython path.
* Expected Qt/Python environment.
* Package destination.

After writing, run a host verification command that confirms:

```text
package parsed
SYNAPSE_ROOT correct
synapse importable
pypanel file discoverable
shelf file discoverable
```

Then perform one graphical clean-room test from a ZIP, not from Joe's development checkout.

---

## P0.6 — CI does not test the shipping failure surface

The public workflow covers:

```text
Ubuntu + macOS
Python 3.11 + 3.14
stock pytest
```

It does not cover:

* Windows.
* The bundled Windows native wheels.
* Hython.
* Houdini's `hou`, `pxr` or PySide.
* Package registration.
* Graphical panel construction.
* Shelf registration.
* A real node mutation and undo.

Several panel tests explicitly skip under stock Python when PySide is unavailable. The docking test warns that such a skip exits successfully and can be mistaken for a passing goalpost unless run through hython. The main GitHub workflow invokes ordinary `pytest`, not the hython shim.

### Required CI shape

```text
PR CI
├── Linux CP311
├── Linux newest supported CPython
├── macOS CP311
└── Windows CP311
    └── verifies bundled native dependencies

Host verification
├── H21 graphical smoke
├── H21 hython probe
└── H22 graphical + hython smoke
```

The Houdini lanes can be self-hosted or manually dispatched if licensing prevents ordinary hosted CI. Their signed result should be attached to every release.

---

# Important P1 findings

## Shelf code still contains H22-sensitive leftovers

The shelf helper imports only PySide2 for clipboard access, while the rest of the product is PySide6-first. If PySide2 is unavailable, clipboard features quietly return `False`. Its missing-panel message also tells the user to run `python install.py`, which is not the current installer.

Fix both before release.

## Tool safety metadata has multiple sources of truth

Read-only tools, operation types, disk-writing tools and agent identities are maintained as separate hardcoded maps in `bridge_adapter.py`.

As tools are added, missing entries default to `"set_parameter"`. That is not a safe representation of unknown capability.

Move this into the canonical tool registry:

```python
ToolDefinition(
    name="houdini_create_node",
    mutability="scene",
    operation_type="create_node",
    undoable=True,
    touches_disk=False,
    consent="artist_exact_action",
    timeout_class="interactive",
)
```

Then derive routing, UI, gating and auditing from the same record.

## "User typed a prompt" is being treated as blanket consent

Panel operations auto-approve because the blocking HumanGate caused a GUI deadlock. The implementation directly clears the shared bridge's private gate field.

Avoid the deadlock, but do not collapse:

```text
User requested an outcome
```

into:

```text
User approved every exact tool call chosen by the model
```

Delete, arbitrary Python, disk writes and expensive renders need non-blocking asynchronous approval cards rather than unconditional approval.

## Authentication is disabled by default

When neither `SYNAPSE_API_KEY` nor `~/.synapse/auth.key` exists, WebSocket authentication is disabled and every token passes. Requests without a browser `Origin` header are accepted.

I could not establish from the repository whether Houdini's native server is guaranteed to bind only to loopback on every supported platform. The release should therefore require authentication for mutating endpoints unless an explicit insecure-local development flag is set.

## Packaging still depends on the repository root

Both the installer and panel bootstrap add:

```text
<repo>/python
<repo>
```

because `shared/` lives outside the package.

That makes imports depend on checkout structure rather than an installable package. It also caused the previous "panel processes but no nodes" class of failure.

Do not restructure the whole repository during the drop window, but move `shared` into a properly installed package immediately after H22 stabilization.

---

# Release plan: July 10 → mid-July

## Phase 1 — Freeze and remove catastrophic paths

Do these first, in this order:

1. **Fail closed on unprotected mutations.**
2. **Move freeze heartbeat out of the panel.**
3. **Disable production module purging/hot reload.**
4. **Pre-stage the dependency solution for multiple Python minors.**
5. **Fix the PySide2-only shelf path and stale installer message.**

No new agents, tools, UI modes or memory features until these are green.

## Phase 2 — Prove the artist loop on H21

Use a fresh Windows user profile and the downloadable ZIP:

```text
Download
→ run installer
→ restart Houdini
→ panel appears
→ shelf appears
→ provider key resolves
→ "make a box"
→ node is created
→ Ctrl+Z removes it
→ close/reopen panel
→ runtime remains healthy
→ uninstall/reinstall succeeds
```

Resolve and answer GitHub issue #3 using this exact verified process.

## Phase 3 — H22 drop verification

When an H22 build is actually available:

```powershell
hython -c "
import sys, hou
from pxr import Usd
import PySide6.QtCore as QtCore
print(
    hou.applicationVersionString(),
    sys.version_info[:3],
    Usd.GetVersion(),
    QtCore.__version__,
)
"
```

Then:

1. Record those values in `drop.json`.
2. Select the matching dependency bundle.
3. Generate the H22 symbol table.
4. Run `h22_api_delta.py`.
5. Triage every removed symbol, missing node type, changed parameter and punycode delta.
6. Run hython tests.
7. Run graphical panel tests.
8. Perform the clean artist loop.
9. Attach the evidence bundle to an RC release.
10. Promote to stable only after the RC survives a fresh Houdini restart and a clean reinstall.

---

# Binary release gates

**Do not release stable until all are true:**

* **G1 — Clean install:** panel and shelf appear from a ZIP on a fresh Windows account.
* **G2 — Dependency isolation:** brain boots with user site disabled and no globally installed Python packages.
* **G3 — Host truth:** H22 symbol, node-type and punycode artifacts are committed and stamped with the exact build.
* **G4 — Mutation integrity:** disabling the bridge blocks every mutation rather than dispatching directly.
* **G5 — Lifecycle:** runtime heartbeat continues after every SYNAPSE panel closes.
* **G6 — Core smoke:** SOP creation, LOP light setup, COP operation and TOP cook all pass or are explicitly capability-disabled.
* **G7 — Reversibility:** interactive mutations produce one undo step and one integrity receipt.
* **G8 — Restart:** save, quit Houdini, relaunch and reconnect without duplicate threads, callbacks or bridge instances.
* **G9 — Rollback:** the prior H21-compatible release can be restored with one documented operation.
* **G10 — Documentation truth:** README says "H22 verified on `22.0.xxx`" only after these receipts exist.

---

# Final assessment

SYNAPSE's **Houdini introspection system is ahead of the product around it**. The symbol/node/parameter probing work is the part I would trust most.

The release risk is concentrated in four areas:

```text
dependency ABI
        +
clean installation
        +
panel/runtime lifecycle
        +
fail-open mutation routing
```

Fix those before spending time broadening the H22 knowledge corpus or adding more features. The right release label today is:

> **SYNAPSE v5.22 H22 Release Candidate — H21 verified, H22 verification pending.**

The first implementation pass should touch `bridge_adapter.py`, `tool_executor.py`, the freeze-runtime bootstrap, the `.pypanel` loader, the installer, and CI—in that order.
