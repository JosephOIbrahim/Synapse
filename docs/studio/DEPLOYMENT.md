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

| Variable | Purpose |
|----------|---------|
| `SYNAPSE_DEPLOY_CONFIG` | Path to deploy.json (overrides default location) |
| `SYNAPSE_DEPLOY_MODE` | Quick mode override without a config file |
| `SYNAPSE_API_KEY` | Legacy shared API key (still works alongside user directory) |

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
