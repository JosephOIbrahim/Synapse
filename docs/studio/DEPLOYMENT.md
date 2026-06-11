# Synapse Studio Deployment Guide

Deploy Synapse for multi-user studio environments with per-artist roles,
session tracking, and optional TLS encryption.

## Deployment Modes

| Mode | Bind | Auth | RBAC | TLS | Use Case |
|------|------|------|------|-----|----------|
| `local` | 127.0.0.1 | Optional | Off | No | Single artist, same machine (default) |
| `studio-lan` | 0.0.0.0 | Required | On | No | Multi-artist, trusted LAN |
| `studio-vpn` | 0.0.0.0 | Required | On | Yes | Multi-artist, over VPN/internet |

## Quick Start

### 1. Create deploy.json

```json
{
    "mode": "studio-lan",
    "bind": "0.0.0.0",
    "port": 9999,
    "auth_required": true,
    "session_timeout": 3600.0
}
```

Save to `~/.synapse/deploy.json` or set `SYNAPSE_DEPLOY_CONFIG` env var to a custom path.

### 2. Create User Directory

```json
{
    "users": [
        {
            "id": "alice",
            "name": "Alice Chen",
            "role": "lead",
            "key_hash": "sha256:..."
        },
        {
            "id": "bob",
            "name": "Bob Kim",
            "role": "artist",
            "key_hash": "sha256:..."
        }
    ]
}
```

Save to `~/.synapse/users.json`.

### 3. Generate API Key Hashes

Use the `hash_api_key()` utility to generate hashes for storage:

```python
from synapse.server.sessions import hash_api_key
print(hash_api_key("alice-secret-key-here"))
# Output: sha256:a1b2c3d4e5f6...
```

Give each artist their raw key. Store only the hash in `users.json`.

### 4. Connect from Client

Each artist sets their API key in the environment:

```bash
export SYNAPSE_API_KEY="alice-secret-key-here"
```

Or configure it in their Claude Code MCP settings.

## Configuration Reference

### deploy.json

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | `"local"` | Deployment mode: `local`, `studio-lan`, `studio-vpn` |
| `bind` | string | `"127.0.0.1"` | Network interface to bind. Auto-set to `0.0.0.0` for studio modes |
| `port` | int | `9999` | WebSocket port |
| `auth_required` | bool | `false` | Require API key authentication. Auto-enabled for studio modes |
| `users_file` | string | `"~/.synapse/users.json"` | Path to user directory file |
| `tls_enabled` | bool | `false` | Enable TLS. Auto-enabled for `studio-vpn` |
| `tls_certfile` | string | `""` | Path to PEM certificate file |
| `tls_keyfile` | string | `""` | Path to PEM private key file |
| `default_role` | string | `"artist"` | Fallback role for authenticated users not in directory |
| `session_timeout` | float | `3600.0` | Idle session timeout in seconds (1 hour) |

### Environment Variables

Complete reference — every `SYNAPSE_*` environment variable read by production
code, enforced by `tests/test_m3_env_conformance.py` (a new env read without a
row here fails CI; a stale row fails CI).

| Variable | Meaning | Default | Read by | Single-seat vs studio |
|----------|---------|---------|---------|-----------------------|
| `SYNAPSE_API_KEY` | Shared API key for WS/MCP auth; env beats `~/.synapse/auth.key` | unset (auth off) | `server/auth.py`, `mcp_server.py` | Studio: required for studio-lan/vpn; per-user keys in users.json preferred |
| `SYNAPSE_AUTOSTART_HWEBSERVER` | `"1"` restores import-time start of the in-Houdini hwebserver endpoint | unset | `server/start_hwebserver.py` | Single-seat convenience |
| `SYNAPSE_BRIDGE_FILE` | Override path of the self-healing port sidecar | `~/.synapse/bridge.json` | `server/bridge_endpoint.py` | Both |
| `SYNAPSE_DEPLOY_CONFIG` | Path to deploy.json | `~/.synapse/deploy.json` | `server/sessions.py` | Studio |
| `SYNAPSE_DEPLOY_MODE` | `local` / `studio-lan` / `studio-vpn`; != `local` enforces RBAC; the WS server also WRITES this var at startup to propagate deploy.json's mode in-process | `local` | `server/sessions.py`, `server/rbac.py`, `server/hwebserver_adapter.py`, `mcp/server.py`, `server/websocket.py` (write) | Studio |
| `SYNAPSE_ENCRYPTION_KEY` | Fernet key for memory-at-rest encryption; wrong key = degraded read-only load, save refused | unset (keyfile / auto-gen) | `core/crypto.py` | Studio: escrow it; must match on restore |
| `SYNAPSE_FILE_LOG` | `"0"`/`"false"` disables the rotating file log (see docs/studio/DIAGNOSTICS.md) | on | `core/logfile.py` | Both: leave on |
| `SYNAPSE_INSPECTOR_TRANSPORT_MODULE` | Dotted module exposing `execute_python`; Inspector last-resort transport (NOT the test-only `..._LIVE_...` var) | unset | `inspector/tool_inspect_stage.py` | Dev |
| `SYNAPSE_LEDGER_DIR` | agent.usd ledger records | `<repo>/.synapse/ledger` | `memory/ledger.py` | Studio: shared storage |
| `SYNAPSE_LOG_DIR` | Directory for synapse.log + telemetry.json + freeze dumps | `~/.synapse/logs` | `core/logfile.py`, `server/doctor.py` | Both |
| `SYNAPSE_MEMORY_BACKEND` | `jsonl` (default) / `moneta` / `shadow`; unknown values fall back to jsonl with a warning; `sqlite` is NOT live (dormant factory only) | `jsonl` | `memory/store.py` | Both |
| `SYNAPSE_METRICS_INTERVAL` | Live-metrics sample interval, seconds (floor 0.5) | `2.0` | `server/live_metrics.py` | Both |
| `SYNAPSE_MONITOR_EVENT_CAP` | Max buffered events per TOPs monitor stream | `5000` | `server/handlers_tops/_common.py` | Both |
| `SYNAPSE_PATH` | Bridge WS path | `/synapse` | `mcp_server.py`, `panel/ws_bridge.py`, `panel/chat_panel.py` | Both |
| `SYNAPSE_PORT` | Bridge WS port fallback (sidecar wins) | `9999` | `mcp_server.py`, `server/bridge_endpoint.py`, `server/start_hwebserver.py`, panel | Both |
| `SYNAPSE_PROVENANCE_DIR` | Floor provenance records | `<repo>/.synapse/provenance` | `core/floor_gate.py` | Studio: audited storage |
| `SYNAPSE_PROVENANCE_MAX_RECORDS` | Provenance FIFO cap; <=0 or unparseable disables rotation | `5000` | `core/floor_gate.py` | Studio |
| `SYNAPSE_RAG_ROOT` | TWO meanings — see note below table | `<repo>/rag` (recall) / `G:\HOUDINI21_RAG_SYSTEM` (scout, dev-only) | `server/handlers.py`, `cognitive/tools/scout.py` | Both; if set, ONLY to a repo-rag tree |
| `SYNAPSE_RATE_LIMITER` | `"1"` enables the WS rate limiter, `"0"` disables | `1` (on) | `server/start_hwebserver.py` | Studio: never disable |
| `SYNAPSE_REDUCED_MOTION` | `1`/`true`/`yes`/`on` minimizes panel motion (accessibility) | off | `panel/designsystem/tokens.py` | Single-seat (accessibility) |
| `SYNAPSE_REPORTS_DIR` | `synapse_write_report` output dir | `<repo>/docs` | `server/handlers.py` | Studio: show storage |
| `SYNAPSE_RESILIENCE` | `"0"` disables rate-limiter + circuit-breaker (CI escape hatch only) | enabled | `mcp/server.py`, `server/websocket.py` | Studio: never set 0 |
| `SYNAPSE_ROOT` | Repo root for panel bootstrap + agent-health JSONL; set by `packages/synapse.json` in live Houdini | `C:\Users\User\SYNAPSE` (.pypanel) / `~` (agent_health) | `panel/synapse_chat.pypanel`, `panel/agent_health.py` | Both |
| `SYNAPSE_SCOUT_DRIFT_POLICY` | `warn` (default) / `refuse` on scout corpus drift | `warn` | `cognitive/tools/scout.py` | Studio: refuse |
| `SYNAPSE_SHOW_CONFIG` | Path to a show.json config layer; precedence env > $HIP > $JOB > defaults | unset | `core/show_config.py` | Both |
| `SYNAPSE_TELEMETRY_FLUSH_S` | Periodic telemetry.json flush interval, seconds; <=0 disables | `60.0` | `server/telemetry_dump.py` | Both |
| `SYNAPSE_TOPS_MAX_PROCS` | maxprocs for auto-created TOPs localscheduler | cpu_count-2 (min 1) | `server/handlers_tops/_common.py` | Both |
| `SYNAPSE_VEX_ROOT` | Scout VEX store root | == `SYNAPSE_RAG_ROOT` | `cognitive/tools/scout.py` | Dev |
| `SYNAPSE_WORKER_TOOL_MODE` | Autonomous-worker tool policy: `strict` / `standard` / `unrestricted` | `standard` | `panel/worker_policy.py` | Studio: standard or strict |

#### Test-only variables

Read only by the test suite — never by production code:

| Variable | Meaning | Read by |
|----------|---------|---------|
| `SYNAPSE_INTEGRATION` | Enables integration tests | `tests/test_e2e_tops.py`, `tests/test_phase1_rungs.py` |
| `SYNAPSE_LOAD_TEST` | Enables the load test | `tests/test_load.py` |
| `SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE` | Live Inspector transport for tests | `tests/test_inspect_live.py` |

#### SYNAPSE_RAG_ROOT: one name, two layouts

One env var, two incompatible consumers:

1. **recall / knowledge_lookup** (`server/handlers.py`) reads it as a
   **repo-rag tree** root — expects
   `documentation/_metadata/semantic_index.json` plus
   `skills/houdini21-reference/`. Default: `<repo>/rag`.
2. **scout** (`cognitive/tools/scout.py`) reads it as a **store** root —
   expects `corpus/` plus `semantic_index/`. Default:
   `G:\HOUDINI21_RAG_SYSTEM`. On the live MCP path this meaning is inert:
   `mcp_server.py` overrides scout's root to `<repo>/.synapse/scout_corpus`
   (materialized from the repo `rag/` tree), so the env var's scout meaning
   only applies in headless/dev/eval use.

**Operator rule:** leave it unset, or set it ONLY to a repo-rag-tree path.
Pointing it at a store-layout root silently empties recall — the
KnowledgeIndex only checks that the directory exists. There is no split
variable: no supported deployment needs the two meanings simultaneously.

## Roles

| Role | Can Do | Cannot Do |
|------|--------|-----------|
| **viewer** | Read scene, inspect nodes, capture viewport, query knowledge | Create/edit/delete anything, execute code, render |
| **artist** | Everything viewer can + create nodes, execute code, render, manage materials | Manage users, configure server |
| **lead** | Everything artist can + manage users, list sessions | Configure server |
| **admin** | Unrestricted access | Nothing restricted |

## Firewall Rules

For `studio-lan` or `studio-vpn` mode, open the WebSocket port:

```
# Windows Firewall (PowerShell, elevated)
New-NetFirewallRule -DisplayName "Synapse" -Direction Inbound -Protocol TCP -LocalPort 9999 -Action Allow

# Linux (ufw)
sudo ufw allow 9999/tcp
```

## TLS Setup (VPN Mode)

For `studio-vpn`, generate or obtain a TLS certificate:

```bash
# Self-signed (for internal use)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# In deploy.json
{
    "mode": "studio-vpn",
    "tls_certfile": "/path/to/cert.pem",
    "tls_keyfile": "/path/to/key.pem"
}
```

Clients connect via `wss://` instead of `ws://` when TLS is enabled.

## Data Flow Security

When using Claude Code or Claude Desktop as the MCP client, be aware that
tool call results (including scene data like node names, attribute values,
and viewport captures) transit through Anthropic's API infrastructure.

For studios with proprietary scenes, consider:
- Using `studio-lan` mode (data stays on LAN, only tool results go to API)
- Reviewing which tools are available to each role
- Using the `viewer` role for team members who only need to inspect

## Autonomy & Cost Bounds

### Single-seat cost posture

The panel worker loop is bounded at **25 tool-use iterations per turn**
(`synapse/panel/claude_worker.py::_MAX_TOOL_ITERATIONS`). There is **no
token/dollar budget** and the worker does not measure token usage. Per the
2026-06-09 hardening report this is accepted for **single-seat use only** —
a per-run monetary budget is a prerequisite for any unattended or
multi-seat use.

### Autonomous render bounds

- `max_iterations` is **clamped server-side to 10**
  (`synapse/autonomy/driver.py::MAX_ITERATIONS_HARD_CAP`); the schema
  default is 3.
- Every run carries a **wall-clock bound** defaulting to the canonical
  600 s client budget (`synapse/core/timeouts.py::timeout_for("autonomous_render")`).
  A run past the bound stops at the next iteration boundary and returns an
  honest partial report: `success=false`, `stop_reason="wall_clock_exceeded"`,
  with the iterations and evaluation completed so far.
- Raising `max_wall_clock_seconds` in the payload requires raising the
  **client** timeout in step, or the client abandons a run the server will
  still finish.
- Worst-case render work = `max_iterations × frames × (1 + per-frame
  retries)`; the per-frame retry default is 3.

### Kill switches

- `synapse_render_farm_cancel` reaches **both** the running farm sequence
  and a running autonomous driver. Signal semantics: the in-flight frame
  finishes first — confirm via `synapse_render_farm_status`. The command
  deliberately bypasses the mutation lock and rate limiting so it cannot
  queue behind the very render it cancels.
- The panel worker's stop is `ClaudeWorker.abort()` (the panel Stop button).
- TOPS cooks cancel via `tops_cancel_cook`.

### What cancel does NOT do

No scene rollback (undo is separate), no deletion of partial frames on
disk, no interruption of an API call already in flight.
