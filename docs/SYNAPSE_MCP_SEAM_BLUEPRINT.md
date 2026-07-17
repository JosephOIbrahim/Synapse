# SYNAPSE — MCP Blueprint v2 (adjusted, first-principles)

> **Supersedes:** external doc "Houdini Bridge MCP" (adjudicated 2026-07-17).
> **Grounded against:** `JosephOIbrahim/Synapse` @ `87553ab` · v5.29.0 · 2,364 tracked files · 4,303 test functions.
> **Intake:** Blueprint v2.0 §10 — external doc reduced to an adjudication; this is the *replacement*, authored against the live tree, not the paper.
> **F3:** committed before any Claude Code execution it governs.
> **Truth contract:** every load-bearing claim carries an anchor. **Repo claims** anchor to `file:line` @ `87553ab`. **External claims** are quarantined to §0.5 — dated, sourced, and marked as decaying. Nothing outside §0.5 depends on an unanchored fact.

---

## 0 · Verdict

**The MCP does not need to be built. It needs to be *typed*.**

SYNAPSE at `87553ab` already contains every layer the external blueprint proposes, plus two it doesn't imagine. The blueprint's Phase 0–4 plan would rebuild — worse, from zero, in a second codebase — what `python/synapse/` already ships.

The real question ("fits inside, not bolted on, swappable later") has a small, precise answer:

- **Fits inside:** it already does. The seam is `Dispatcher`, not a package boundary.
- **Bolted on:** yes, but not where it looks. The bolt is a *second dispatch spine*, not a directory.
- **Swappable:** the mount point exists — `synapse/providers/` — and its only implementation already satisfies the contract. **Nobody has written the contract down.**

Net delta: **~5 moves, none large.** Not 4 phases.

---

## 0.5 · External facts (dated · decaying · not repo-anchored)

> Everything in this section came from outside the tree on **2026-07-17** and has a shorter half-life than the rest of this document. Re-verify before acting. Nothing in §1–§10 depends on a fact that isn't either here or `file:line`-anchored.

### H22 platform — shipped 2026-07-15, build 22.0.368

| Dependency | Version |
|---|---|
| Python | **3.13.10** — *a separate Python 3.11 build remains available* |
| USD | 26.05 |
| MaterialX | 1.39.5 |
| OpenColorIO | 2.5.0 |
| OpenEXR | 3.4.3 |
| OpenVDB | 13.0 |
| Qt 5 | **dropped** |

Targets VFX Reference Platform CY2026. macOS now Apple-Silicon-only; Windows 11 minimum; Linux Arm technical preview.

**Consequences this document depends on:**

- **`python3.11libs/` (external blueprint §18) is the wrong directory** on default H22 → §1, §7.
- **Vendored ABI exposure is live, not forecast.** `pydantic_core.cp311-win_amd64.pyd` and `jiter.cp311-win_amd64.pyd` do not load under 3.13 → §8.
- **Gate 0.1 has a third door not present in `gate-0.1-sidecar-vs-abi3.md`:** the separate H22 **py3.11 build**. Vendored wheels survive untouched.
  - *Buys:* an H22 baseline without spending the sidecar-vs-abi3 decision.
  - *Costs:* alternate Python builds historically get thinner third-party support (HtoA, Deadline, Flow target the default build).
  - *Defers the gate; does not close it.* **Human gate. Do not automate.**
- **PySide2 fallback is dead code on H22** (Qt 5 dropped).
- OCIO env-var preservation now points at OCIO 2.5.0.

### SideFX's APEX MCP — what `providers/apex_mcp.py` is actually pointed at

Ships inside H22's **APEX Script Comfort Package**: a VS Code extension, an in-Houdini Python panel, and an MCP server serving **a curated library of syntax rules and snippets**.

**Scope, and why it matters for §8:** this is *knowledge retrieval for APEX scripting*. **It is not scene control.** It cannot and does not overlap the 115-tool registry. It also sits entirely inside **APEX/rigging — SYNAPSE's locked non-goal**, enforced by `check_no_rigging_drift`.

> Mount it, don't fear it. The vendor is in the space, not in the lane. Task 1.7 is an integration, not a defence.

**Flag:** SideFX is now making a **token-efficiency** claim. That is G6's claim, made by the vendor. G6's priority rises → §9.

### Foreign scene-control MCPs — the §6 candidate pool

Named in §6 as future providers. Context so the precedence table in M3 can be reasoned about:

| Project | Scale | Transport | Note |
|---|---|---:|---|
| `healkeiser/fxhoudinimcp` | **179 tools**, 8 resources, 6 prompts | hwebserver / HTTP:8100 | PyPI v1.3.0 (2026-06-11), MIT. Covers SOP/LOP/DOP/TOP/COP/HDA/anim/render/VEX. Built on **hwebserver — SYNAPSE's locked non-goal** |
| `oculairmedia/houdini-mcp` | — | hrpyc:18811 | 224★, MIT, carries ADRs |
| `arybashov/houdini-mcp` | fork of above | hrpyc | Tested on **Win11 + H21.0.671 + Codex Desktop** — our exact runtime |
| `eliiik` / `otakusquirrel` | 35 / — | RPyC | Multi-instance, pooling, WebUI |

The external blueprint's MVP target was *"25–35 tools; do not chase 150."* The incumbent shipped 179 five weeks before it was written. **This is why §0's verdict is "type it, don't build it": the tool count was never the differentiator, and the one place SYNAPSE is uniquely positioned is the provider seam none of these have.**

---

## 1 · Delta map — blueprint § vs. live tree

| Blueprint § | Proposes | Reality at `87553ab` | Status |
|---|---|---|---|
| §3 A/B/C topology debate | Pick in-process *or* RPC | **Both**, behind `TransportFn` Protocol, chosen by env var | `inspector/transport.py:60,76` · `host/transport.py` (78 LOC) · **RESOLVED, 2 sprints ago** |
| §5 L1 transport | Build stdio | `mcp_server.py` (1,080 LOC) + `mcp/protocol.py` (155) | VERIFIED |
| §5 L2 tool registry | Build registry | `mcp/_tool_registry.py` — 1,415 LOC, **115 tools**, transport-agnostic, zero `hou` | VERIFIED (imported, counted) |
| §5 L3 services | Build `NodeService`… | `cognitive/dispatcher.py:101` — `Dispatcher`, `ToolFn`, `AgentToolError` | VERIFIED |
| §5 L4 adapters | Build `Hou*Adapter` | `host/` — 15 modules, 8,459 LOC | VERIFIED |
| §5 L5 bridge runtime | Build RPC runtime | `host/daemon.py` (753) + `host/main_thread_executor.py` (242) | VERIFIED |
| §8 resources | Build resource URIs | `mcp/resources.py` (195) | VERIFIED |
| §12 main-thread dispatch | "expose `execute_on_main_thread`" | `host/main_thread_exec` — shipped, timeout-honouring | VERIFIED |
| §13 event bus | "internally, still build an event bus" | `mcp/server.py:125` — `SSEEventBus` | VERIFIED |
| §15 error model | Structured errors | `AgentToolError` — **fail-visible, not fail-fast**. Errors *return* as tool output so the LLM self-corrects | VERIFIED — **strictly better than the blueprint** |
| §17 extension contract | `HoudiniBridgeExtension` Protocol | `providers/__init__.py:34,41` — `register()`/`get()`, lazy, fail-loud | VERIFIED — exists, **untyped** |
| §20 "target 25–35 tools" | 25–35 | **115** | **INVERTED — 4× regression** |
| §18 `python3.11libs/` | py3.11 | H22 = **Python 3.13.10** (§0.5) | CORRECTED |
| §19 `hrpyc` MVP | hrpyc | Wire Protocol 4.0.0, `ws://localhost:9999/synapse` | CORRECTED |
| §16 versioning | Version 3 surfaces | v5.29.0 · MCP protocol `2025-06-18` | VERIFIED |
| — | *(not imagined)* | **Foreign-MCP provider** — `providers/apex_mcp.py:53` | **The blueprint has no concept for this** |
| — | *(not imagined)* | **Truth-contract envelopes** — `observed` vs `claimed`, enforced by `check_mcp_truth_contract` | **No concept for this** |

**Tool namespace histogram (empirical, `TOOL_DISPATCH` keys):**

| Namespace | Count | | Namespace | Count |
|---|---:|---|---|---:|
| `houdini_*` | 40 | | `render_*` | 4 |
| `synapse_*` | ~30 | | `inspect_*` | 3 |
| `cops_*` | 21 | | `memory_*` | 3 |
| `tops_*` | 17 | | `solaris_*` | 2 |

**SOP · DOP · CHOP · VOP: zero specialized tools.** That is G1, measured. The registry is the proof.

---

## 2 · First principles

### P1 — The MCP is not a component. It is a face.

A component has behaviour. MCP has none — it is a wire format and a handshake. Every line of behaviour lives in tools; tools live behind the Dispatcher. So "fit the MCP inside SYNAPSE" is a category error: **there is nothing to fit.** What mounts inside SYNAPSE is *tool providers*. MCP is one way to reach them from outside, and one way to reach foreign ones from inside.

### P2 — Swappability is a property of contracts, not of packages.

The blueprint buys swappability with repo structure (§18: two packages, `houdini-bridge-mcp` + `houdini-bridge-runtime`). That is a filesystem answer to a typing question. **Directories don't swap. Protocols do.**

SYNAPSE already proves this: `TransportFn` (Protocol) + `configure_transport()` makes in-process-vs-WebSocket a **one-env-var** swap (`SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE`) with zero repo restructuring. `host/transport.py` and the WebSocket transport are interchangeable and neither knows the other exists.

That mechanism is the template. Apply it one layer up.

### P3 — "Bolted on" is a dispatch topology, not a directory layout.

A thing is bolted on when **it owns its own path to the target.**

The embedded Agent SDK is *not* bolted on despite being a wholly separate entry point — it shares the Dispatcher. `mcp/server.py` *is* bolted on despite living inside the package — it owns a second route (`HTTP /mcp → dispatch_tool → execute_through_bridge → handler`) that the live path never touches.

> **Rule: one dispatch spine, N front doors.**
> Front doors are free. A second spine is the bolt.

### P4 — The swap you're planning for is a retirement, not a replacement.

The blueprint imagines: SideFX ships an MCP → you swap yours out. That never happens cleanly, because a product's tools encode judgment the vendor's don't.

What actually happens: a foreign MCP arrives, it is better at *some* tools, you **mount** it, and you **retire your own, one provider at a time, on evidence.**

That is the Strangler Fig — which SYNAPSE is already running on the WS→Dispatcher migration (`_PORTED_WAVE_TOOLS`, `mcp_server.py:765`). The pattern is in the codebase. It simply hasn't been pointed at foreign MCPs.

> **The swap seam is the provider registry, not the transport.**

---

## 3 · The actual bolt-on (named, anchored)

Not the directory layout. Four specific things:

**B1 · Two disjoint dispatch spines.** *(VERIFIED — and already found by the repo's own `docs/SYNAPSE_CTO_REVIEW_2026-06-05.md:133`)*
- `mcp_server.py` — stdio → WebSocket → `/synapse` handler. **Live.** Bridge-less.
- `mcp/server.py` — HTTP `/mcp` → `dispatch_tool` → `execute_through_bridge` (`mcp/tools.py:117`). **Disjoint from the live path**, registered only as an import side-effect of `mcp/__init__.py`.
- Both import `_tool_registry`. The **registry** is shared; the **dispatch** is not. That is the bolt.
- `mcp/server.py` is built on **hwebserver** — a locked non-goal.

**B2 · `sys.path.insert` at `mcp_server.py:461`.** The signature of a bolt-on: a root-level script mutating `sys.path` to reach into `python/`. The MCP is not a package member; it path-hacks its way in.

**B3 · Six loose `mcp_tools_*.py` at repo root**, imported by bare name (`mcp_server.py:441-446`).

**B4 · Four dispatch branches inside `call_tool()`** (`mcp_server.py:956`): `_inspector_call_tool`, `_scout_call_tool`, `_ported_call_tool`, and legacy `TOOL_DISPATCH` fallback. Correct as a Strangler Fig *in flight* — it must not become the resting state.

---

## 4 · The seam that already exists

`python/synapse/providers/__init__.py` — read its own docstring:

> *"A tool provider answers `call_tool(name, args) -> envelope` — **the seam through which SYNAPSE orchestrates external MCP servers (first: H22's native APEX MCP) as one source among many.**"*

It has `register(provider_id, factory)` / `get(provider_id)`, lazy construction, fail-loud `ProviderError`, no silent fallback. `providers/__init__.py:66` already registers `apex_mcp`.

And `ApexMCPProvider` (`providers/apex_mcp.py:53`) **already implements both halves of the contract**:
- `list_tools()` → `:73`
- `call_tool(name, args)` → `:81`
- Endpoint seam: `SYNAPSE_APEX_MCP_ENDPOINT`, default `"mock"`, unknown endpoints **fail loud**
- Returns truth-contract envelopes (`observed` vs `claimed`), enforced by `check_mcp_truth_contract` (`harness/verify/checks.py`)
- Surface recorded to `science/apex_mcp_surface.json` (schema `apex_mcp_surface/v1`, recorded 2026-07-01, endpoint `mock`)

**The Protocol is satisfied by its only implementation. It has simply never been written down.** `get()` returns `Any` (`providers/__init__.py:41`).

That is the entire gap. Everything below is consequence.

---

## 5 · The adjustment — five moves

### M1 · Type the provider contract *(small, unblocks everything)*

Add to `cognitive/interfaces.py` — where the other Protocols live, zero `hou`, already the boundary file:

```python
class IToolProvider(Protocol):
    """A source of tools. Native handlers and foreign MCPs are both this."""
    provider_id: str

    def list_tools(self) -> list[ToolDef]: ...
    def call_tool(self, name: str, args: dict) -> Envelope: ...
```

`ApexMCPProvider` satisfies this **today, unmodified**. Narrow `providers.get()` from `Any` to `IToolProvider`. Zero behaviour change; the type is the deliverable.

> **Implementation note (Leg 1, verified against `apex_mcp.py` @ `1f1df25`):** the sketch above is *the blueprint's guess*, and the harness's Leg-1 discipline caught three divergences from the real implementation — type what is there, not this sketch:
> - the class attribute is **`id`**, not `provider_id` (`apex_mcp.py:56`);
> - `ToolDef` / `Envelope` do not exist as types — they are plain dicts, adopted as `dict[str, Any]` aliases so the provider satisfies the Protocol unmodified;
> - `call_tool`'s signature is `call_tool(self, name: str, args: Optional[dict] = None) -> dict`.
> The typed contract as landed uses `id: str`, `list_tools(self) -> list[ToolDef]`, `call_tool(self, name: str, args: Optional[dict] = None) -> Envelope`, and `@runtime_checkable`.

### M2 · Make the native 115 a provider

Wrap `_tool_registry.TOOL_DEFS`/`TOOL_DISPATCH` as `NativeProvider`, `register("native", …)`. A rename with a contract, nothing more. After this, native and foreign tools are **the same kind of thing** — which is the whole point.

### M3 · Federate the registry behind the Dispatcher

`Dispatcher` (`cognitive/dispatcher.py:101`) takes `tools={name: fn}`. Make that dict **one provider among N**, with an explicit, declarative precedence table:

```python
PROVIDER_PRECEDENCE = ["native", "apex_mcp"]   # per-tool overrides allowed
```

Resolution: name → provider → `call_tool` → envelope. Precedence is *data*, not code. It is how the retirement in §6 executes without a refactor.

### M4 · Collapse the second spine

`mcp/server.py`'s dispatch route: **quarantine.** It is hwebserver-based (locked non-goal) and the CTO review found it disjoint from the live path.

**Keep** (all transport-agnostic, all useful): `protocol.py`, `session.py`, `resources.py`, `SSEEventBus`.
**Retire:** the `HTTP /mcp → execute_through_bridge` dispatch route.

If Streamable HTTP is wanted later, it becomes a **front door onto the Dispatcher** — same as stdio. One spine, N doors.

### M5 · Un-bolt the front door

- `mcp_server.py` → `python/synapse/mcp/stdio_bridge.py`. Entry point declared in `pyproject` / `.mcp.json`, **not** `sys.path.insert`.
- `mcp_tools_*.py` (×6) → `python/synapse/mcp/groups/`.
- `.mcp.json` args updated to the module entry point.

This is the literal "not bolted on": MCP becomes a package member instead of a script that path-hacks its way in.

### M6 (deferred) · Namespace the 115

`houdini_*` / `cops_*` / `tops_*` / `synapse_*` is three conventions in one surface. The blueprint's §6 is right on the merits.

**But this is a breaking change to a live surface.** Do it behind an **alias table**, never a rename. Not this sprint.

---

## 6 · Swap protocol — how the day comes

When a foreign scene-control MCP ships — candidate pool and their scale in **§0.5**; note that *none* of them has a provider seam, which is why mounting is cheap for us and impossible for them:

1. **Record its surface** → `<id>_mcp_surface.json`. Schema `apex_mcp_surface/v1` already exists and generalizes.
2. **Write `<Id>MCPProvider`** — thin, envelope-returning, one endpoint env seam. `apex_mcp.py` is the reference implementation; copy its shape.
3. **`register("<id>", factory)`** — one line.
4. **Precedence entry** — per-tool, `foreign > native` only for tools it demonstrably wins.
5. **Retire native tools on evidence, provider by provider.** Benchmark, not vibes — this is where **G6's harness earns its existence.**
6. **Native tools that survive are the moat, empirically.** Not by assertion.

**Nothing is ever ripped out.** No fork in the road, no migration weekend, no rewrite. The precedence table is the only thing that moves.

That is what "swappable" actually buys you, and it is unavailable to the external blueprint's architecture at any price — because it has no provider concept at all.

---

## 7 · Do not build

| From blueprint | Why not |
|---|---|
| §18 two-package split | Packages don't swap. Protocols do. (P2) |
| §19 `hrpyc` MVP | Wire Protocol 4.0.0 exists and is faster |
| §3 Option A/B/C | Already resolved — `TransportFn` + env var, both live |
| §20 Phase 0–4 | You are 115 tools past Phase 1 |
| §17 `HoudiniBridgeExtension` | `providers.register()` **is** this |
| §18 `python3.11libs/` | H22 is Python **3.13.10** — §0.5 |
| §2 risk classes | `is_read_only()` + bridge-wrap already splits read/write (`mcp/tools.py:123`) |
| §11 stable identity | Worth harvesting — the one section with net-new value |

---

## 8 · Open, and now unblocked

**`apex_mcp_surface.json` says: *"Re-record from the shipped H22 MCP is HUMAN-GATED (task 1.7)."***

**H22 shipped 2026-07-15** (build 22.0.368 — §0.5). **Task 1.7's gate is now open**, and `SYNAPSE_APEX_MCP_ENDPOINT` still defaults to `"mock"`.

What you are pointing it at is a **knowledge-retrieval MCP for APEX scripting — syntax rules and snippets, not scene control**, sitting inside the locked rigging non-goal (§0.5). It cannot collide with the 115. Task 1.7 is an integration, not a defence.

The mount point is built, mocked, tested, and the real thing now exists to point it at. **That is the highest-leverage single action in this document** — and it is a human gate, not an automation.

**Still open, unaddressed:** `H22_PREPAREDNESS_REPORT.md` covers UI/panel only (tokens, docking, heartbeat, brand). It contains **zero** coverage of Python 3.13 / cp311 ABI / `pydantic_core` / `jiter`. The vendored-ABI exposure on default H22 (§0.5) is not tracked in the H22 preparedness surface — and §0.5 records a **third Gate 0.1 door** (the H22 py3.11 build) that `gate-0.1-sidecar-vs-abi3.md` does not contain.

---

## 9 · Sequencing

| Item | Position |
|---|---|
| M1 (type `IToolProvider`) | Cheap, unblocks §6 permanently. Can ride alongside Mile 5 |
| M5 (un-bolt front door) | Mechanical, low-risk, do when touching `mcp_server.py` anyway |
| M2–M4 | Post-Mile-5. Real refactor of a live surface — not during perception validation |
| M6 (namespace) | Deferred. Alias table only |
| Task 1.7 (re-record APEX surface) | **Unblocked today.** Human gate |
| G1 (SOP/DOP/CHOP/VOP) | Unchanged priority. The histogram in §1 is its measurement |
| **Mile 5** | **Still the next leg.** Nothing here goes in front of it |

**You are Mile 4 of 6.** None of this is Mile 5. M1 is a 30-line file edit that can ride in a gap; the rest waits for the anchor leg to finish.

---

## 10 · Ratification

```json
{
  "ratified": false,
  "supersedes": "external:houdini-bridge-mcp",
  "grounded_against": "87553ab",
  "self_contained": true,
  "external_facts_quarantined_to": "§0.5",
  "external_facts_dated": "2026-07-17",
  "moves_proposed": 6,
  "moves_approved": 0,
  "human_gates_touched": ["task-1.7", "gate-0.1"],
  "gates_advanced": [],
  "blocks_mile_5": false
}
```

**On provenance.** `SYNAPSE_MCP_ADJUDICATION.md` is **not** a peer governing document and must not be committed as one. Two documents with authority over one decision is the §3 second-spine failure in documentation form: one spine, N doors. Every fact from the adjudication that this blueprint's reasoning depends on now lives in §0.5, dated and sourced. The adjudication's residual value is the **record** — that an external document was received, checked, and superseded on 2026-07-17. That is a note (`harness/notes/`), not a spine.

**Decay note.** §0.5 is the only section that rots. When it goes stale, the architecture in §2–§7 does not — it is anchored to the tree, and the tree is checkable. That separation is deliberate: it is why this document can be re-verified in one pass instead of re-litigated.

`ratified: false` is the correct resting state. M1–M6 are proposals grounded in verified source; none is approved. Task 1.7 and Gate 0.1 are human gates and stay that way.
