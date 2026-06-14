# SYNAPSE Egress — What Leaves the Building

The answer to a studio security review's first question: **what leaves the
workstation, to where, and when.** Two lanes exist: **in-process egress**
(SYNAPSE's own API calls) and **client-relay egress** (external MCP clients
SYNAPSE does not control). Conformance-pinned by
`tests/test_m3_egress_docs.py` — a new remote-egress call site fails CI
until this document is updated.

## The single remote endpoint

`api.anthropic.com:443` (TLS, `POST /v1/messages`) is the **only remote
host in first-party code**. Three call sites:

| Lane | Code | Transport |
|---|---|---|
| Panel worker | `python/synapse/panel/claude_worker.py` → `panel/providers/anthropic_provider.py` | stdlib `http.client.HTTPSConnection`, streaming |
| Host daemon agent loop | `host/daemon.py` → `cognitive/agent_loop.py` | vendored `anthropic` SDK |
| Routing tiers 2/3 | `routing/router.py` | `anthropic` SDK |

No telemetry, analytics, crash-reporting, or update-check endpoint exists
anywhere in the codebase.

## Payload classes per lane

| Lane | What is sent, per turn |
|---|---|
| **Panel worker** (`claude_worker`) | The system prompt (identity + TONE.md + current network path + **selected node paths** + frame + hip basename); the full chat history including drag-and-dropped node paths; the ~110 tool names + descriptions; and **every tool result serialized in full** — scene inspection output, parameter values, memory recall/search/context content, render metadata. |
| **Daemon agent loop** (`agent_loop` / daemon) | The user prompt + registered cognitive tool results (today: `synapse_inspect_stage` stage summaries). |
| **Routing tiers 2/3** (`router`) | The user query + tier-1 RAG knowledge + up to 3 project-memory search results embedded in the user message. |

## What NEVER leaves

- The **Fernet encryption key** — in-process only. Only the non-secret
  8-hex `key.fingerprint` is ever written, and only locally.
- The **ANTHROPIC_API_KEY** — leaves only as the `x-api-key` auth header
  to `api.anthropic.com` itself, never inside payloads.
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
