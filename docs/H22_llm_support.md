# H22 SYNAPSE REPORT — Multi-LLM Support Strategy
**Prepared:** 2026-06-22 | **Target Release:** Houdini 22 | **Synapse Version:** 5.14.0 / Protocol 4.0.0

---

## Executive Summary

Synapse currently assumes Claude (Anthropic) as the primary LLM client over MCP stdio/WebSocket. This document defines what it would take to support other LLMs — OpenAI GPT-4o, Google Gemini, Mistral, local models via Ollama, and open-source alternatives — without rewriting the core bridge. The MCP protocol is the abstraction layer; the goal is to make Synapse LLM-agnostic at the transport and tool-schema level.

---

## 1. Current LLM Coupling Points

Despite MCP being LLM-neutral in principle, several assumptions are baked into the current Synapse design:

| Coupling Point | Where | Impact |
|----------------|-------|--------|
| Tool schema format | `tools/*.json` | MCP spec-compliant but uses Claude-style `input_schema` |
| System prompt injection | Project setup / `synapse_project_setup` | Claude-specific prompt structure |
| Context window handling | Memory system (project.md, scene memory) | Assumes ~200K context; smaller models need chunking |
| Error verbosity | Tool response `_integrity` blocks | Claude handles verbose JSON; smaller models may truncate |
| Streaming expectations | None currently | GPT-4o and Gemini prefer streaming by default |
| Image tool results | `houdini_capture_viewport` returns base64 | Only vision-capable models can use this |

---

## 2. MCP as the Portability Layer

The Model Context Protocol (MCP) defines:
- **Tools** — callable functions with JSON Schema input/output
- **Resources** — readable data sources
- **Prompts** — template messages

Synapse only uses the **Tools** surface today. For multi-LLM support, we need to also use **Resources** (expose scene memory as a readable resource) and **Prompts** (expose the Synapse voice guide as a prompt template).

### 2.1 Tool Schema Compatibility

The MCP tool schema is compatible with all major LLM providers, but there are differences in how they handle:

| Feature | Claude | GPT-4o | Gemini 1.5 | Mistral | Ollama (local) |
|---------|--------|--------|------------|---------|----------------|
| Parallel tool calls | ✅ Native | ✅ Native | ✅ Native | ⚠️ Sequential | ❌ Single |
| Streaming tool results | ⚠️ Partial | ✅ Full | ✅ Full | ⚠️ Partial | ❌ None |
| Image in tool result | ✅ `image` type | ✅ `image_url` | ✅ `inline_data` | ❌ | Model-dependent |
| Max tool definitions | ~200 | 128 | 512 | 64 | Model-dependent |
| Tool call nesting | ✅ Allowed | ❌ Flat only | ❌ Flat only | ❌ Flat only | ❌ Flat only |
| JSON mode | ✅ Strong | ✅ Strong | ✅ Strong | ⚠️ | ❌ |

**H22 Action:** Synapse currently exposes **~80 tools**. This is under all provider limits, but tool group meta-tools (e.g. `synapse_group_scene`) push the logical count higher. Audit and consider a **tool routing layer** (see §4).

### 2.2 Parallel Tool Call Handling

Synapse already supports parallel tool calls (multiple `<function_calls>` in one turn). For providers that don't support parallel calls, the bridge should:
- Queue sequential calls transparently.
- Return partial results with a `continuation_token` so the LLM can chain calls.

---

## 3. Provider Integration Patterns

### 3.1 OpenAI GPT-4o / GPT-4.1

**Transport:** HTTP REST + SSE streaming  
**Tool format:** Same JSON Schema as MCP — direct compatibility  
**Vision:** Supported via `image_url` in tool result content

**Integration path:**
```
GPT-4o (Responses API or Chat Completions with tools)
    │  HTTP / SSE
    ▼
MCP-to-OpenAI adapter (thin translation layer)
    │  JSON-RPC 2.0
    ▼
Synapse MCP Server (unchanged)
```

**Adapter responsibilities:**
- Translate `tool_use` → OpenAI `tool_calls` format
- Wrap base64 image results in `{"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}`
- Handle `parallel_tool_calls: true` (default in GPT-4o)

### 3.2 Google Gemini 1.5 / 2.0

**Transport:** HTTP REST  
**Tool format:** `FunctionDeclaration` — needs schema translation  
**Vision:** Supported via `inline_data`

**Schema translation required:**
```python
# MCP tool schema → Gemini FunctionDeclaration
def mcp_to_gemini(tool: dict) -> dict:
    return {
        "name": tool["name"],
        "description": tool["description"],
        "parameters": tool["inputSchema"]  # Gemini uses "parameters" not "input_schema"
    }
```

**Key difference:** Gemini does not support `$defs` / `$ref` in JSON Schema. All schemas must be inlined (no references). Synapse tool schemas should be pre-flattened for Gemini compatibility.

### 3.3 Mistral (Le Chat / API)

**Transport:** HTTP REST  
**Tool format:** OpenAI-compatible (direct)  
**Parallel calls:** Sequential by default — enable `parallel_tool_calls` in API call

**Limitation:** 64-tool limit in some tiers. Synapse may need to expose tool *groups* as the top-level interface and dynamically reveal sub-tools on demand.

### 3.4 Ollama (Local Models)

**Use case:** Air-gapped studios, cost control, proprietary asset security  
**Models:** Llama 3.1 70B, Qwen2.5-Coder 72B, Mistral Nemo, DeepSeek-V2.5

**Challenges:**
- Most local models have weaker tool-call reliability than frontier models.
- Context windows: 32K–128K vs Claude's 200K — scene memory must be chunked.
- No native vision — `houdini_capture_viewport` results cannot be used.

**Proposed Ollama adapter:**
```python
class OllamaAdapter:
    def __init__(self, model: str, endpoint: str = "http://localhost:11434"):
        self.model = model
        self.endpoint = endpoint
    
    def format_tools(self, tools: list[dict]) -> list[dict]:
        # Ollama uses OpenAI tool format
        return tools
    
    def chunk_context(self, memory: str, max_tokens: int = 24000) -> str:
        # Truncate project memory to fit context window
        # Prioritise: scene memory > recent decisions > project notes
        ...
    
    def handle_tool_result(self, result: dict) -> dict:
        # Strip image content (not supported)
        result.pop("image", None)
        return result
```

**Recommended local models for Synapse (ranked):**
1. **Qwen2.5-Coder 72B** — strongest tool-call reliability, good Python/VEX
2. **Llama 3.1 70B** — solid general reasoning, decent tool use
3. **DeepSeek-V2.5** — excellent code, moderate tool reliability
4. **Mistral Nemo 12B** — fast, acceptable for simple scene operations

### 3.5 Anthropic Claude (Current — Maintain)

No changes needed. Claude 3.5/3.7/4 series via MCP stdio or WebSocket transport remains the reference implementation.

---

## 4. Tool Routing Layer (H22 Priority Feature)

With 80+ tools, all providers hit limits and LLMs struggle to select the right tool from a flat list. H22 should introduce a **Tool Router**:

```
LLM Request
    │
    ▼
Tool Router
    ├── Scene Tools     (node create/delete/connect/inspect)
    ├── USD Tools       (prims, attributes, materials, stage)
    ├── Render Tools    (karma, mantra, render settings)
    ├── TOPS Tools      (PDG, wedge, batch cook)
    ├── Memory Tools    (project setup, recall, decisions)
    └── COP Tools       (image processing, compositing)
```

**Implementation:**
- `synapse_list_tools(category: str)` — return tools filtered by category
- Tool definitions include a `category` field in metadata
- For providers with small tool limits (Mistral 64), expose only the active category
- `synapse_switch_context(context: "usd"|"sop"|"render"|"tops"|"cops")` — pre-select the relevant tool subset

---

## 5. Memory System Adaptation per LLM

The current memory system writes Markdown files (`project.md`, `memory.md`). This works well with Claude's long context. For other models:

### 5.1 Context-Adaptive Memory Serialisation

```python
class MemorySerializer:
    def for_claude(self, memory: ProjectMemory) -> str:
        # Full markdown, ~50K tokens, richly structured
        return memory.to_markdown()
    
    def for_gpt4o(self, memory: ProjectMemory) -> str:
        # Trimmed markdown, ~30K tokens, prioritise recent
        return memory.to_markdown(max_decisions=20, max_notes=10)
    
    def for_ollama(self, memory: ProjectMemory) -> str:
        # Minimal JSON, ~8K tokens
        return memory.to_json_summary()
```

### 5.2 Resource Exposure

Expose scene memory as an MCP **Resource** so LLMs that support resource reading can pull it on demand rather than receiving it in the system prompt:

```json
{
  "uri": "synapse://memory/project",
  "name": "Project Memory",
  "description": "Long-term project decisions and pipeline configuration",
  "mimeType": "text/markdown"
}
```

---

## 6. Voice Guide Adaptation

The Synapse voice guide (senior artist, collaborative, action-first) is currently hardcoded into the Claude system prompt. For multi-LLM support:

- Externalise voice guide as a **Prompt Template** in MCP.
- Each provider gets the same template but formatted for their prompt style.
- `{tool_results}` and `{scene_context}` are filled dynamically.

---

## 7. Authentication & Security per Provider

| Provider | Auth Method | Studio Consideration |
|----------|-------------|---------------------|
| Anthropic (Claude) | API key | Key rotation, usage caps |
| OpenAI | API key | Data retention policy (opt-out available) |
| Google Gemini | OAuth2 / API key | GCP IAM integration possible |
| Mistral | API key | EU data residency (GDPR advantage) |
| Ollama (local) | None / local | Fully air-gapped, no data leaves studio |

**H22 Recommendation:** Add a `provider` field to `bridge.json` and a `synapse_configure_provider` tool that sets API keys, endpoints, and model names per session. Store credentials in the OS keychain, not in `.synapse/` files.

---

## 8. Testing Matrix for Multi-LLM Validation

For each provider, run the following Synapse smoke tests:

| Test | Claude | GPT-4o | Gemini | Mistral | Ollama |
|------|--------|--------|--------|---------|--------|
| `synapse_ping` | | | | | |
| `synapse_project_setup` | | | | | |
| `houdini_create_node` | | | | | |
| `houdini_set_parm` | | | | | |
| `houdini_execute_python` | | | | | |
| `houdini_capture_viewport` | | | | | |
| Parallel tool calls (3x) | | | | | |
| Memory read/write | | | | | |
| Full scene assembly | | | | | |

**Automated test runner:** Build a pytest suite that runs these against each provider using a headless Houdini instance. Run nightly in CI.

---

## 9. H22 Rollout Plan

**Month -1 (Now — H22 Beta):**
- Build MCP-to-OpenAI adapter (highest demand).
- Externalise tool schemas to `tools/` directory for per-provider customisation.
- Add `category` metadata to all tool definitions.

**H22 Launch Day:**
- Update symbol table, run smoke tests on all providers.
- Release Ollama adapter for local model users.
- Document provider-specific limitations in `README_providers.md`.

**Month +1 (Post-H22):**
- Gemini adapter (if demand warrants).
- Tool routing layer V1.
- Memory serialisation adapters.

---

*End of document. See companion reports: H22_inside_out_sdk_enhancements.md and H22_codebase_review.md*
