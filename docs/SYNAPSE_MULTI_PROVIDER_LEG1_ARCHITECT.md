# SYNAPSE_MULTI_PROVIDER — LEG 1 ARCHITECT DELIVERABLE

> **Governing doc:** `docs/SYNAPSE_MULTI_PROVIDER_HARNESS_v1.md` (committed `86ef9bc`, clean — F3 ✔).
> **Role:** ARCHITECT — design + measurement only. **No source mutated this run.** Deliverables are docs.
> **Status:** Mile 0 re-grounded + Leg 1 measured. **HALT for D1–D4 ratification.** No FORGE begun.
> **Method integrity:** all numbers below are measured live (PY631 = Houdini 21.0.631 `python311`, real registry, real endpoints) or tagged UNVERIFIED. Raw probe JSON: `docs/SYNAPSE_MULTI_PROVIDER_LEG1_PROBE_DATA.json`. Adversarially re-checked by a crucible pass (findings folded in, undercounts corrected).

---

## DELIVERABLE 1 — RE-GROUNDED FACTS SHEET

### 1.1 The real chat client (the named module)

**`python/synapse/cognitive/agent_loop.py`** is the canonical SDK tool-loop: builds `create_kwargs` (L219-228), calls `client.messages.create(**create_kwargs)` **synchronously, no `stream`** (L232), owns the `tool_use → tool_result` re-entry loop (L264-294), zero-`hou`. **But it is NOT the only request builder** — this is the single biggest correction to the seed:

| Client site | File | Transport | Model string | Owns a loop? |
|---|---|---|---|---|
| **Cognitive SDK loop** (server turn) | `cognitive/agent_loop.py:232` | anthropic SDK, **sync** | `claude-sonnet-4-5` (`:61`) | yes (tool loop) |
| **Panel worker** (UI streaming) | `panel/claude_worker.py:361-376` | **raw SSE** over `http.client`, `stream:True` | `claude-sonnet-4-6` (`:48`) | yes (own SSE state machine) |
| **Router LLM** (Tier 2/3) | `routing/router.py:852-855` | anthropic SDK | `claude-haiku-4-5-20251001` (`:112`), `claude-sonnet-4-5-20250929` (`:113`) | no (one-shot) |

**Five distinct model strings across four files.** The harness seed's "single Anthropic client" and "claude-sonnet-4-6 default" are both wrong: `4-6` is the *panel worker's* compile-time constant; the *server loop* default is `4-5`; the router holds two more. **A Provider freeze that claims to enumerate model sources must reconcile all four sites or explicitly scope to one** — see the flagged design fork under D1.

### 1.2 Seed → live divergences (re-grounding catches)

| Seed / memory said | Live disk/runtime says | Tag |
|---|---|---|
| `SYNAPSE_ANTHROPIC_KEY` env | **`ANTHROPIC_API_KEY`** (`host/auth.py:61`); `SYNAPSE_ANTHROPIC_KEY` absent | [path:line]+[V-env] |
| `claude-sonnet-4-6` default | `agent_loop.py:61` = **`claude-sonnet-4-5`** | [path:line] |
| Python 3.14 (CLAUDE.md banner) | Houdini embeds **python311 (3.11.7)**; 3.14 is only system Py | [V1-py] |
| "112 MCP tools" | registry `TOOL_DEFS`=112, but `tool_bridge.get_anthropic_tools()`=**118** reach `messages.create` (+6 `synapse_group_*`) | [V1-import] |
| `gemini-3.5-pro` (TBD) | **phantom** — no 3.5 Pro exists; newest Pro = `gemini-3.1-pro-preview` (preview only) | [V1-list] |
| `nemotron-3-nano:4b`/`:30b` | **neither installed**; installed nano is `nemotron-3-nano:latest` 31.6B/24.3GB | [V1-tags] |
| `hou.secure` key path | structurally **phantom** on H21.0.671 (`_try_hou_secure` always returns None; `host/auth.py:65-96`) | [path:line] |

### 1.3 Load-bearing measured facts

- **Tool payload:** full **118-tool** Anthropic array = **65,699 bytes (~16,424 tokens)** (`json.dumps`, compact). Wire shape: `{name, description, input_schema}` built by `panel/tool_bridge.py:56-60` (renames MCP `inputSchema`→`input_schema`, drops `annotations`).
- **Error envelope (Invariant E):** `AgentToolError` = `@dataclass(frozen=True)` (`dispatcher.py:57`), fields `tool_name/error_type/error_message/traceback_str=""/timestamp`; `to_dict()` adds marker `agent_tool_error:True`; `_TRACEBACK_MAX_LEN=4000`. `Dispatcher.execute()` **never raises** — *at the envelope layer*. ⚠ The production `_execute_via_main_thread` branch is documented in-code as **unwired** (`main_thread_executor=None` raises; dispatcher.py:250-258) — live prod dispatch is not yet functional.
- **Cost metering:** **none in first-party code.** `agent_loop` discards `response.usage`; `claude_worker` ignores the `message_delta` usage block. `Provider.cost()` has **nothing to read today** — Leg 2 must add a usage-capture seam. (Ollama natively returns `prompt_eval_count`/`eval_count`; Anthropic `response.usage` and Gemini `usageMetadata` exist but are dropped.)
- **Undo seam:** `hou.undos.group` = **99 call-sites across 37 files** (the seed's "~37" = file count, not call count). **42 live executable sites across 10 `server/handlers_*.py`** — all **hou-side**. Cognitive layer = **zero hou**, enforced by `tests/test_cognitive_boundary.py::test_cognitive_layer_has_no_hou_imports`.
- **Auth resolution:** `host/auth.py:105-128 get_anthropic_api_key()` → (1) `hou.secure` [always None on 671] → (2) `ANTHROPIC_API_KEY` env. Wrapped by `daemon._resolve_api_key` (`daemon.py:332-353`) → `Anthropic(api_key=...)` (`:424`).

### 1.4 SDK liveness matrix (`dir()`-introspected `exists_in_runtime`, not docs)

| SDK | PY631 (hython 21.0.631) | PY671 (graphical) | SYSPY (3.14.2) | Vendored? |
|---|---|---|---|---|
| `anthropic` | ✅ site **0.96.0** + vendored 0.96.0 | ✅ **vendored-only** 0.96.0 (no site copy) | ✅ user-site **0.75.0** (vendor gate skipped on 3.14) | ✅ `_vendor/` (Py3.11 ABI-locked) |
| `google.genai` | ❌ ImportError | ❌ ImportError | ❌ ImportError | ❌ |
| `ollama` | ❌ ModuleNotFound | ❌ ModuleNotFound | ✅ user-site (no `__version__`) | ❌ |

**Consequence:** the authoritative Houdini runtimes (PY631/PY671) can SDK-drive **only Anthropic** today. **`google-genai` and `ollama` must be vendored for Leg 2** (or those adapters reach their endpoints via REST). The Anthropic symbol surface (`Anthropic`, `.messages`, `types.ToolUseBlock/Message/ToolParam`, `NOT_GIVEN`) is `exists_in_runtime=true` in all three.

---

## DELIVERABLE 2 — FROZEN `Provider` PROTOCOL + ADAPTER MAPPING TABLES

### 2.1 The protocol (normalized on SYNAPSE's native Anthropic-shaped envelope)

> **PROPOSED for Leg 2 — FORGE owns the file** (likely `cognitive/providers/base.py`, zero-`hou`, enforced by `test_cognitive_boundary`). Signature **frozen** for ratification.

```python
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional, Protocol, Sequence

# Envelope = the home format (Anthropic-shaped), unchanged from agent_loop today:
#   messages : list[{role, content}]  content = str | list[block]
#     tool_use   block = {"type":"tool_use","id":str,"name":str,"input":dict}
#     tool_result block = {"type":"tool_result","tool_use_id":str,"content":str}
#   system   : top-level str (omitted when "")
#   tools    : [{"name":str,"description":str,"input_schema":dict}]  # tool_bridge shape

@dataclass(frozen=True)
class NormalizedToolCall:
    id: str        # provider call-id; adapters SYNTHESIZE a stable id when the provider emits none (Gemini)
    name: str
    input: dict    # type-faithful args — adapters MUST strict-round-trip-validate (Invariant T)

@dataclass(frozen=True)
class NormalizedResponse:
    text_blocks: list[dict]               # assistant content, normalized to plain dicts (model_dump)
    tool_calls: list[NormalizedToolCall]
    stop_reason: str                      # normalized: end_turn | tool_use | max_tokens | stop_sequence | <other>
    model_identity: str                   # the model that ACTUALLY authored this response (Invariant P)
    usage: Optional[dict]                 # {"input_tokens":int,"output_tokens":int,...} or None
    raw: Any                              # provider-native payload — telemetry/debug only

class Provider(Protocol):
    model_identity: str                   # configured model id, sourced from the registry (data, never business logic)

    def complete(
        self, *,
        messages: list[dict],
        tools: Sequence[dict],            # Anthropic-shaped (tool_bridge output)
        system: str = "",
        max_tokens: int = 1024,
        stream: bool = False,
    ) -> NormalizedResponse: ...

    def cost(self, usage: Optional[dict]) -> Optional[Decimal]: ...
    # None  => non-billed (local Ollama)            -- see D4
    # Decimal => billed (Anthropic, Gemini, :cloud)
```

**Error normalization (Invariant E).** Every provider/transport failure (auth, timeout, malformed tool call, schema rejection) is caught inside the adapter and normalized **into the existing `AgentToolError`** — *nothing new is raised past the boundary*. `AgentToolError` is **unchanged**. What the loop *does* with a normalized provider error (continue / halt / fallback) is **D3**, not the adapter's call.

**Floor (Invariant F).** The Anthropic adapter is a **zero-behavior-change wrap** of today's `agent_loop.py` path: `complete()` builds the identical `create_kwargs`, calls the identical `client.messages.create`, and returns the identical content/stop_reason. The only *addition* is reading `response.usage` and `response.model` (today discarded) into `NormalizedResponse` — read-only, no behavior change to the loop.

### 2.2 Adapter mapping tables

**(A) Anthropic — NATIVE, zero translation (the floor)**

| Envelope element | Anthropic mapping | Note |
|---|---|---|
| `messages` | verbatim | home format |
| `tools` | verbatim `{name,description,input_schema}` | already produced by `tool_bridge.py:56-60` |
| `system` | top-level `system` str | omit when `""` (matches L224-225) |
| tool call out | `content` block `type:tool_use` → `NormalizedToolCall(id,name,input)` | id always present |
| tool result in | `{"type":"tool_result","tool_use_id","content":str}` | matches L287-291 |
| `stop_reason` | verbatim | `max_tokens` currently → UNKNOWN_STOP (preserve) |
| `usage` | `response.usage` (`input_tokens`/`output_tokens`) | **add capture** (dropped today) |
| `model_identity` | `response.model` | **add capture** |
| **Verdict** | **NATIVE.** No router, no repair. | — |

**(B) Gemini — Anthropic envelope ↔ `functionDeclarations`; requires REPAIR + strict round-trip**

| Envelope element | Gemini mapping | Measured hazard |
|---|---|---|
| `messages` | `contents:[{role, parts:[{text}|{functionCall}|{functionResponse}]}]`; `assistant`→`model` | — |
| `system` | `system_instruction` (top-level) | — |
| `tools` | `[{function_declarations:[{name,description,parameters}]}]` where `parameters` = `input_schema` **REPAIRED** | see 3 repairs below |
| tool call out | `functionCall` → `NormalizedToolCall(id="<synthesized>",name,input=args)` | **Gemini emits NO call-id** → adapter synthesizes |
| tool result in | `functionResponse` part | — |
| `thinking_level` | `ThinkingConfig` (`types.ThinkingConfig` — **unverifiable, SDK absent**) | symbol surface unverified |
| `usage` | `usageMetadata.promptTokenCount`/`candidatesTokenCount` | — |
| **Verdict** | **NEITHER native nor clean-compat.** Needs loss-aware repair + strict arg round-trip validation. **H3 confirmed.** | — |

Three **mandatory schema repairs** (each measured against the live registry):
1. **Non-STRING enums → drop/stringify.** Gemini allows `enum` only on `TYPE_STRING`. `synapse_safe_render.soho_foreground` (int enum `[0,1]`) → HTTP 400 at `function_declarations[88]`.
2. **Property-less `type:object` slots (12 tools) → synthesize a minimal inner schema/type.** Gemini rejects a nested OBJECT with no `properties`. Affected: `synapse_solaris_build_graph.{nodes[].parms,template_params}`, `synapse_memory_write.content`, `houdini_render_settings.settings`, `tops_multi_shot.shots[].overrides`, `tops_setup_wedge.attributes[]`, `synapse_validate_frame.thresholds`, `houdini_hda_{promote_parm.conditions,set_help.parameters_help,package.*}`, `synapse_batch.commands[]`.
3. **Untyped `any` slots (3 tools) → assign a concrete type (e.g. STRING).** Gemini requires a type on every property; dropping them **silently loses the value** (measured: `houdini_set_parm.value`, `houdini_set_usd_attribute.value`, `tops_query_items.filter_value`).

**(C) Ollama — Anthropic envelope ↔ OpenAI-shaped `tools`/`tool_calls`; ONE adapter for local + `:cloud`**

| Envelope element | Ollama mapping | Measured |
|---|---|---|
| `messages` | `messages:[{role,content}|{role:"tool",tool_call_id,content}]` | — |
| `system` | `{role:"system",content}` | — |
| `tools` | `[{type:"function",function:{name,description,parameters}}]`, `parameters` = `input_schema` **VERBATIM** | **zero repair, lossless** |
| tool call out | `message.tool_calls[].{id,function.name,function.arguments}` → `NormalizedToolCall` | id present |
| tool result in | `{role:"tool",tool_call_id,content}` | — |
| `usage` | `prompt_eval_count`/`eval_count` (**native**) | a real local token source |
| `model_identity` | `response.model`; local vs `:cloud` differ **only by tag + auth** | server proxies `:cloud` |
| **Verdict** | **OpenAI-compat verbatim pass-through. H1 clean.** Local + cloud share one adapter. | — |

---

## DELIVERABLE 3 — FIDELITY VERDICT + ROUTER DECISION (measured)

*Probe: real 118-tool registry under PY631; subset of 10 tools spanning flat-enum / nested-object / optional-absent / high-arity; forcing target `synapse_solaris_build_graph` (array+nested-object+enum). Raw data: `docs/SYNAPSE_MULTI_PROVIDER_LEG1_PROBE_DATA.json`.*

| Provider | Model (resolved live) | Name | Call-id | **Args type-faithful** | Full-118 payload | Latency | Verdict |
|---|---|---|---|---|---|---|---|
| **Anthropic** | `claude-3-5-haiku-latest`¹ | — | — | — | — | 184ms (401) | **INCONCLUSIVE** — auth-blocked (see ²); native by construction, **H1 expected/unverified** |
| **Gemini** | `gemini-3.5-flash` | ✅ correct | ❌ none | ❌ **DROPPED nested `parms` values** (`{}` not `{intensity:2.5}`) | ❌ **400 — schema-shape (NOT size)** | 3.3s | **H3 CONFIRMED** |
| **Ollama local** | `nemotron-3-nano:latest` | ✅ correct | ✅ | ✅ faithful (only `1.0→1` int/float) | ✅ accepted | **93.4s** | **H1** |
| **Ollama cloud** | `nemotron-3-ultra:cloud` | ✅ correct | ✅ | ✅ faithful | ✅ accepted | 46.9s | **H1** |

¹ probe used a haiku alias to minimise spend; auth failed before any model mattered.
² **The `ANTHROPIC_API_KEY` in env is the Claude Code CLI credential (`sk-ant-api03-…`, 108 chars) — it returns `401 invalid x-api-key` on every call including a bare no-tools request.** Not a raw API key. The Claude **floor cannot be verified live** without a real Anthropic API key.

### Router decision

**`router_required = TRUE — but provider-scoped to Gemini only, and it is a schema-REPAIR layer, not a per-turn tool-subsetting router.**

- **H2 (size degradation past N → subsetting router) is REFUTED** for every provider actually exercised: Ollama local **and** cloud accepted all 118 tools / 65.7 KB cleanly; Gemini's full-payload failure is **schema-shape** (integer enums + property-less objects), proven because the *same constructs fail at N=1*. 65.7 KB is well within all four providers' limits. **No per-turn tool router is needed on measured evidence.**
- **The contingency that actually fired is H3 (translation lossiness)**, Gemini-only. The required layer is the **Gemini adapter's repair + strict arg round-trip validation** (Deliverable 2B). Anthropic (native) and Ollama (verbatim compat) need **no** translation layer.
- **Native-vs-compat per provider:** Anthropic = **native**; Ollama local+cloud = **OpenAI-compat verbatim**; Gemini = **functionDeclaration native target but registry schema must be repaired for the OpenAPI subset** (neither raw-native nor raw-compat suffices).

---

## DELIVERABLE 4 — PROVENANCE THREAD DESIGN (display/telemetry only — Invariant P)

**The display surfaces already exist (v9-locked); the gap is a single hardcoded constant.**

- **Wordmark** = literal `"SYNAPSE"` (`synapse_panel.py:273`, BRAND font `:277`).
- **Author token** = `self._author_lbl.setText(self._author_token())` (`synapse_panel.py:300`), DATA-tracked, `TEXT_TERTIARY`, leading the cost cluster. Formatter `_author_token()` (`synapse_panel.py:474-487`): `"claude-sonnet-4-6" → "sonnet-4.6"` (strip `claude-`, family-dash-version-dots).
- **SIGNED twins:** `face_review.set_signed()` → `"SIGNED  %s"` (`face_review.py:301`); `message_formatter` inline `"signed {who}"` (`:234`). **All annotated display-only** — "NEVER authors USD / customData" (`face_review.py:299`).
- **Telemetry:** `agent_state.log_routing_decision()` (`:403-427`) writes `synapse:fingerprint/primary_agent/advisory_agent/method/timestamp` — **agent identity, not model identity**. No `synapse:model`/`synapse:author` exists. (Writers still dormant — Phase 4.)

**The gap:** the token's model string comes from the compile-time constant `claude_worker._MODEL` (`:48`), **not the model that actually authored a result**. `_author_token()` does `from synapse.panel.claude_worker import _MODEL` (`synapse_panel.py:478-480`).

**Minimal thread (display/telemetry only):**
1. Carry the **actual per-turn `model_identity`** from `NormalizedResponse.model_identity` (the response already echoes a `model` field) into the panel, **replacing** the static `_MODEL` read in `_author_token()` with the last-result model.
2. *(optional)* add a **non-USD** telemetry field `synapse:model` to `log_routing_decision()` so the routing-log credit names the model alongside the agent (read display-only by `face_review.refresh_provenance()`).

**Author-token string contract (extend, don't redesign):** `model_identity` → strip `claude-`/`gemini-`/`nemotron-` family prefix → `family-version-dots`; e.g. `claude-opus-4-8`→`opus-4.8`, `gemini-3.5-flash`→`gemini-3.5-flash` (or `flash-3.5`), `nemotron-3-ultra:cloud`→`nemotron-ultra · cloud`. Owner finalizes the non-Claude rendering as part of D4's label contract.

> **HARD LINE (Invariant P):** **No write to `customData:synapse:signed_by`.** Confirmed zero live usage — grep finds it only in docs (Gold-RFC zone). Multi-provider is exactly the temptation; it stays carved out until Michael-Gold RFC ratifies.

---

## DELIVERABLE 5 — CAPSULE

```
WHERE WE ARE · Leg 1 ARCHITECT complete. Mile 0 re-grounded against the live 21.0.631 build;
               fidelity probe run across all four targets on the real 118-tool registry; design frozen.
               HALT for D1–D4 ratification. No source mutated, no FORGE begun.
MILE MARKER  · Provider protocol signature FROZEN; 3 adapter mapping tables written; fidelity verdict
               MEASURED (Anthropic native/auth-blocked-unverified · Gemini H3-lossy → repair+round-trip ·
               Ollama local+cloud H1 clean). Router decision: Gemini-only schema-REPAIR, NO per-turn
               subsetting router (H2 refuted; 65.7KB/118 tools accepted by Ollama, rejected by Gemini on
               shape not size). Provenance thread designed display-only; customData untouched. Invariants
               F/Z/T/P/E all mapped to live code + tests.
BLOCKERS     · (B1) env ANTHROPIC_API_KEY is the Claude Code CLI credential → 401 on the raw API; the
               Claude FLOOR (H1) and every claude-* model id are UNVERIFIED live — a real Anthropic API
               key is required. (B2) google-genai DEAD in all 3 runtimes + ollama absent from both
               python311 runtimes, neither vendored → Gemini/Ollama SDK symbol surface unverifiable until
               vendored (Leg 2). (B3) two divergent chat clients + a third router client (5 model strings,
               4+ files) — the "single client" assumption is false; D1 must scope this. (B4) D1–D4 unratified.
NEXT ACTION  · Owner ratifies D1–D4 (esp. D2 with the real 4090/install data + B3 client-multiplicity fork)
               and provides a raw Anthropic API key to confirm the floor → then FORGE dispatch (Leg 2).
```

---

## DELIVERABLE 6 — D1–D4 RATIFICATION REQUEST (with the real data to decide each)

> The harness refuses to default these. Each is presented with the measured evidence; **owner decides.**

### D1 · Abstraction strategy — OWNED thin layer vs gateway (LiteLLM)
**Harness assumes OWNED. Recommend RATIFY OWNED — and the data hardens the case.** The Gemini repair logic is **registry-specific** (it must know *which* 12 tools carry property-less object slots and *which* 3 are untyped) — a generic gateway cannot repair SYNAPSE's idiosyncratic schemas losslessly, and a lossy gateway is a silent Invariant-T violation. Vendoring into ABI-locked python311 is already the established `_vendor` pattern. **Owned, inspectable tool translation is required, not optional.**
- **⚠ FLAGGED SUB-DECISION (B3 — client multiplicity).** "One Anthropic client" is false: `agent_loop.py` (SDK sync), `claude_worker.py` (raw-SSE streaming), and `router.py` (Tier-2/3) are **three** clients with **five** model strings. **Owner must scope Leg 2:** (a) wrap **only** `agent_loop` behind `Provider` now (smallest floor, panel SSE + router untouched), or (b) unify all three behind `Provider` (true "model IDs as data", larger blast radius). *Recommend (a) for the floor; (b) as a follow-on* — but this is an owner call, not a default.

### D2 · Nemotron slot purpose — (P) local/private/$0 vs (A) best-open-agentic cloud
**Real install + fit data (4090 = 24,564 MiB / 24 GB):**

| Installed local model | Params | Size | Tools? | Fits 4090? |
|---|---|---|---|---|
| `nemotron-mini:latest` | 4.2B | 2.7 GB | ✅ | ✅ comfortable (closest to a "4b", but it is **nemotron-mini, not nemotron-3-nano:4b**) |
| `gemma4:latest` | 8B | 9.6 GB | ✅ | ✅ comfortable |
| `qwen3-vl:30b` | 30B | 19.6 GB | ✅ | ✅ tight |
| `nemotron-3-nano:latest` | 31.6B | **24.3 GB** | ✅ | ⚠ **borderline-OVER** (no KV-cache room → partial offload; **93s** probe latency) |
| `nemotron:latest` | 70.6B | 42.5 GB | ✅ | ❌ |
| `nemotron-3-super:latest` | 123.6B | 86.8 GB | ✅ | ❌ |
| **`nemotron-3-ultra:cloud`** | 550B | cloud | ✅ | **CONFIRMED live+authed+tool-calling** (real `tool_calls`, 47s) |

- **The seed's `:4b`/`:30b` tags are NOT installed.** The only local nano is 31.6B and *exceeds usable VRAM*.
- **Both paths are measured-working at H1 fidelity** — local nano and cloud ultra both faithful, both accepted all 118 tools. One adapter serves both.
- **Decision (owner):** **(P)** local works *today* via `gemma4`/`nemotron-mini` (comfortable) — private, offline, $0 — or `nemotron-3-nano` if you accept the VRAM squeeze + ~90s latency. **(A)** `nemotron-3-ultra:cloud` works *today* — best open agentic engine, but bills and data leaves the box. *If forced to recommend:* ship the one Ollama adapter, **default local (`gemma4` for a comfortable tools-capable fit)**, expose `:cloud` opt-in behind the D4 cost label. **Owner picks P or A.**

### D3 · Mid-loop provider failure policy — halt vs auto-fallback to Claude
**Harness assumes HALT + opt-in surfaced fallback. Recommend RATIFY HALT.** The Gemini H3 failure is **silent** (args dropped with *no error* — the auto-scorer even passed it; only manual inspection caught the empty `parms`). Auto-fallback would mask exactly this class of defect and muddy authorship (Invariant P). A malformed/lossy non-Claude turn must **halt-and-surface**; fallback only as a logged, surfaced opt-in. **Owner ratifies.**

### D4 · Cost meter for non-billed paths — `$0` vs `local` vs `cloud` label
**Real data:** no usage metering exists today (must be **added** — a Leg-2 dependency). Ollama returns native `prompt_eval_count`/`eval_count` ($0 spend); Anthropic `response.usage` + Gemini `usageMetadata` exist but are dropped.
- **Recommend display contract:** local Ollama → **`local · $0`** (show token count, cost $0); `nemotron-3-ultra:cloud` → **`cloud · $<billed>`** (egress honesty); Anthropic / Gemini → **`$<billed>`**. The label is the panel's honesty signal for the author-token cost cluster (Deliverable 4). **Owner picks the exact string contract.**

---

## INVARIANT CONFORMANCE (mapped to live code)

| Invariant | Status | Anchor |
|---|---|---|
| **F (Floor)** | designable — Anthropic adapter = zero-behavior wrap of `agent_loop` | ⚠ live-unverifiable until a real API key (B1) |
| **Z (Zero-hou)** | provider layer is cognitive (zero hou) | enforced by `test_cognitive_boundary.py` |
| **T (Truth)** | Gemini arg-drop is the live H3 risk → strict round-trip validation in adapter | measured; repair specified (2B) |
| **P (Provenance)** | display/telemetry thread designed; `customData` untouched | `signed_by` zero live usage confirmed |
| **E (Envelope)** | `AgentToolError` unchanged; provider errors normalize into it | `dispatcher.py:57` frozen |

**END LEG 1 — HALT. Await D1–D4 ratification + a raw Anthropic API key before any FORGE dispatch.**
