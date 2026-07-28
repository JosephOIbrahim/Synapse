# SYNAPSE Egress — What Leaves the Building

The answer to a studio security review's first question: **what leaves the
workstation, to where, and when.** Two lanes exist: **in-process egress**
(SYNAPSE's own API calls) and **client-relay egress** (external MCP clients
SYNAPSE does not control). Conformance-pinned by
`tests/test_m3_egress_docs.py` — a new remote-egress call site fails CI
until this document is updated.

## Remote endpoints

Three remote hosts exist in first-party code:

- `api.anthropic.com:443` (TLS, `POST /v1/messages`) — the Claude lanes.
- `generativelanguage.googleapis.com:443` (TLS, `POST …:streamGenerateContent`)
  — the **optional** Gemini panel provider, dormant unless the artist switches
  the panel to Gemini.
- `integrate.api.nvidia.com:443` (TLS, `POST /v1/chat/completions`) — the
  **optional** NVIDIA / Nemotron panel provider, dormant unless the artist
  switches the panel to Nemotron. Endpoint-overridable via `NVIDIA_BASE_URL`
  (OpenRouter / Ollama-cloud / self-hosted vLLM/NIM) — the default is the
  NVIDIA NIM cloud above.

Two further panel engines carry **no fixed first-party endpoint**:

- **Ollama** (`panel/providers/ollama_provider.py`) is localhost-first
  (`http://localhost:11434` — see "Localhost surfaces") but `OLLAMA_HOST`
  can redirect it to a remote/TLS host (e.g. Ollama cloud), making it egress.
- **Custom** (`panel/providers/custom_provider.py`) streams to a
  **user-configured** OpenAI-compatible base URL
  (`.synapse/panel_settings.json`, set via the model chip → Configure…
  dialog). Where it points is entirely operator-chosen.

Both reuse the streaming transport pinned in `nemotron_provider.py`, so the
frozen-egress pin (`tests/test_m3_egress_docs.py`) already covers their code
path; this document is the control for where they are pointed.

### The capability-probe lane (metadata only)

`panel/providers/probe.py` reaches the **same three hosts** — no new host is
introduced — plus a user-configured Custom base URL, using **read-only
list/metadata endpoints**:

| Host | Method | What it asks |
|---|---|---|
| `api.anthropic.com:443` | `GET /v1/models?limit=100` | which models the account is served |
| `integrate.api.nvidia.com:443` (or `NVIDIA_BASE_URL`) | `GET /v1/models` | same |
| `generativelanguage.googleapis.com:443` | `GET /v1beta/models` | same, Gemini only |
| `{custom base_url}` | `GET /models` | same, operator-configured |
| `localhost:11434` (or `OLLAMA_HOST`) | `GET /api/tags` | local tag list — loopback by default |

**No prompt, no scene data, no chat history, no tool schema and no memory
content is sent on this lane.** The request bodies are empty (every call is a
`GET`); the only thing that leaves is the auth header and the fact that a probe
happened. It is the lightest-payload lane in the product, and the one a security
review should find easiest to clear.

**No completion is ever requested from this module.** That is enforced, not
asserted: the endpoint allowlist is `probe.FREE_ENDPOINTS`, and
`tests/test_v3_provider_probe.py` parses the module with `ast` and fails if any
non-docstring string literal names a completions path.

**Frequency:** demand-driven, never on a timer. A probe fires only when a caller
reads provider state *and* the last result is older than
`probe.REFRESH_INTERVAL_S` (60 s). An idle panel issues **zero** probes; the
ceiling under continuous use is 60 requests/hour/provider.

Call sites:

| Lane | Code | Transport |
|---|---|---|
| Panel worker (Claude) | `python/synapse/panel/claude_worker.py` → `panel/providers/anthropic_provider.py` | stdlib `http.client.HTTPSConnection`, streaming |
| Panel worker (Gemini) | `claude_worker.py` → `panel/providers/gemini_provider.py` | stdlib `http.client.HTTPSConnection`, streaming SSE |
| Panel worker (Nemotron) | `claude_worker.py` → `panel/providers/nemotron_provider.py` | stdlib `http.client.HTTPSConnection`, streaming SSE (OpenAI-compatible) |
| Panel worker (Ollama) | `claude_worker.py` → `panel/providers/ollama_provider.py` | inherited nemotron transport — plaintext HTTP to localhost by default; TLS when `OLLAMA_HOST` is https |
| Panel worker (Custom) | `claude_worker.py` → `panel/providers/custom_provider.py` | inherited nemotron transport to the configured base URL (http or https, scheme preserved) |
| Host daemon agent loop | `host/daemon.py` → `cognitive/agent_loop.py` | vendored `anthropic` SDK |
| Routing tiers 2/3 | `routing/router.py` | `anthropic` SDK |
| Capability probe (all engines) | `panel/providers/probe.py` | stdlib `http.client.HTTPSConnection` / `HTTPConnection`, single bounded `GET`, no retry, no redirect |

No telemetry, analytics, crash-reporting, or update-check endpoint exists
anywhere in the codebase.

## Payload classes per lane

| Lane | What is sent, per turn |
|---|---|
| **Panel worker** (`claude_worker`) | The system prompt (identity + TONE.md + current network path + **selected node paths** + frame + hip basename); the full chat history including drag-and-dropped node paths; the 121 advertised tool schemas (115 registry + 6 group-info) — names + descriptions; and **every tool result serialized in full** — scene inspection output, parameter values, memory recall/search/context content, render metadata. |
| **Daemon agent loop** (`agent_loop` / daemon) | The user prompt + registered cognitive tool results (today: `synapse_inspect_stage` stage summaries). |
| **Routing tiers 2/3** (`router`) | The user query + tier-1 RAG knowledge + up to 3 project-memory search results embedded in the user message. |
| **Capability probe** (`providers/probe.py`) | Nothing. Every call is a `GET` with an empty body; only the auth header transits. |

## What NEVER leaves

- The **Fernet encryption key** — in-process only. Only the non-secret
  8-hex `key.fingerprint` is ever written, and only locally.
- The **ANTHROPIC_API_KEY** — leaves only as the `x-api-key` auth header
  to `api.anthropic.com` itself, never inside payloads.
- The **GEMINI_API_KEY** (Gemini provider only) — leaves only as the
  `x-goog-api-key` auth header to `generativelanguage.googleapis.com`, never
  inside payloads.
- The **NVIDIA_API_KEY** (Nemotron provider only) — leaves only as the
  `Authorization: Bearer` auth header to the `NVIDIA_BASE_URL` host
  (`integrate.api.nvidia.com` by default), never inside payloads.
- The **OLLAMA_API_KEY** (Ollama provider, optional — cloud/proxied posture
  only; local Ollama needs no key) — leaves only as the `Authorization:
  Bearer` auth header to the `OLLAMA_HOST` endpoint, never inside payloads.
- The **Custom engine key** (optional; the env var *named* in the Configure…
  dialog) — leaves only as the `Authorization: Bearer` auth header to the
  user-configured base URL, never inside payloads.
- The **memory store ciphertext** — at-rest only.
- **Viewport/render pixels** — `capture_viewport` and render tools return
  *path strings*, not image bytes.
- The `.hip` file and geometry buffers.

> **Load-bearing caveat:** encryption-at-rest does **not** bound egress.
> Recalled memory content leaves in **plaintext** inside tool results
> whenever recall/search/context tools run. If it's in the store and the
> agent reads it, it can transit the API.

## Localhost surfaces (not egress)

- Panel → MCP loopback `http://localhost:<port>`.
- The Ollama panel engine talks to the local daemon at
  `http://localhost:11434` (`POST /v1/chat/completions` for chat +
  `GET /api/tags` for the model menu) — plaintext HTTP, loopback by default.
  **Caveat:** `OLLAMA_HOST` can redirect this lane to a remote (TLS) host,
  at which point it is egress (see "Remote endpoints").
- The WS fallback server binds localhost by default (deploy-config
  override for studio modes).
- The hwebserver endpoint (port 9999) has origin validation and optional
  shared-key auth — but `hwebserver.run()` is invoked **without a bind
  argument**, so the listening interface is Houdini's default. **Verify
  with `netstat` per build**; this document does not claim enforced
  localhost-only.
- Subprocess egress is local-only (`iconvert`/`hoiiotool` conversions,
  PowerShell toast notifications).

## What bounds agent-initiated egress

- The **worker allowlist** (`panel/worker_policy.py`,
  `SYNAPSE_WORKER_TOOL_MODE` strict/standard/unrestricted; `standard`
  denies review/approve/critical-gated tools, fail-closed on unknown)
  applies to the **autonomous worker only** — the interactive panel is
  human-in-the-loop with the policy off (your request is the consent).
- Bridge-path consent gates govern `/mcp` operations.
- The live `/synapse` path runs `execute_python` **ungated** — the
  documented single-user-localhost posture (CLAUDE.md §1.2 / D1).
- Iteration cap 25 per worker turn; autonomy runs carry a wall-clock
  bound and clamped iterations; **no token/dollar budget exists** (see
  DEPLOYMENT.md "Autonomy & Cost Bounds").

## Client-relay lane

When Claude Code or Claude Desktop is the MCP client, tool results
transit the **client's** LLM provider under the client's account. SYNAPSE
cannot bound that lane. Mitigations: deployment modes and the `viewer`
role (see DEPLOYMENT.md).

## Open items

- C19's redaction/opt-out hook (a `build_system_prompt` hook + per-tool-
  result filter before serialization) is **not implemented** — this
  document records the posture; gating code is separate work.
- SEC-1/RBAC is the gate before any non-local deploy mode (D4).
