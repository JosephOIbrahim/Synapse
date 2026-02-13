# SYNAPSE -- Studio Deployment Sprint Instructions

> **Sprint Goal:** Transform SYNAPSE from a single-artist localhost tool into a
> studio-deployable service with multi-user authentication, role-based access control,
> remote access over LAN/VPN, and deployment automation. Studios should be able to
> run one SYNAPSE instance per Houdini seat and manage access centrally.
>
> **Prerequisite:** Agent SDK v2 Sprint must be complete. The agent needs checkpoint/resume
> to survive network interruptions common in studio deployments.

---

## 0. PRE-FLIGHT -- Read Before Coding

1. **Read existing auth:**
   - `python/synapse/server/auth.py` -- API key auth (hmac.compare_digest)
   - MCP Bearer token auth (Phase 3 of MCP sprint, partially specified in CLAUDE.md)
   - `~/.synapse/auth.key` -- file-based key storage

2. **Read existing security:**
   - `python/synapse/core/crypto.py` -- Fernet encryption (AES-128-CBC + HMAC-SHA256)
   - `python/synapse/server/resilience.py` -- Rate limiter, circuit breaker
   - MCP origin validation (DNS rebinding mitigation)

3. **Understand the current limitation:**
   - SYNAPSE binds to `127.0.0.1` only -- no remote access
   - Single API key -- no per-user identity
   - No session isolation -- all clients share the same Houdini scene
   - No audit trail per user (audit log exists but doesn't track who)

---

## 1. ARCHITECTURE

### Studio Deployment Model

```
Studio Network (LAN / VPN)
    |
    |-- Artist Workstation A
    |   |-- Houdini + SYNAPSE Server (port 9999)
    |   |-- Bound to 0.0.0.0 (LAN-accessible)
    |   |
    |   +-- Claude Code / Agent SDK (local or remote)
    |
    |-- Artist Workstation B
    |   |-- Houdini + SYNAPSE Server (port 9999)
    |   +-- ...
    |
    +-- Central Auth Server (optional)
        |-- User directory (LDAP/AD integration or local JSON)
        |-- API key management
        |-- Role definitions
        +-- Audit log aggregation
```

### Deployment Modes

| Mode | Binding | Auth | Use Case |
|------|---------|------|----------|
| **Local** (current) | `127.0.0.1` | Optional API key | Single artist, localhost only |
| **Studio LAN** | `0.0.0.0` | Required Bearer + RBAC | Multi-user, LAN access |
| **Studio VPN** | `0.0.0.0` + TLS | Required Bearer + RBAC + TLS | Remote artists via VPN |

Mode is controlled by `SYNAPSE_DEPLOY_MODE` environment variable (default: `local`).

---

## 2. NEW MODULES

### 2.1 `server/rbac.py` -- Role-Based Access Control

```python
class Role(Enum):
    VIEWER = "viewer"       # Read-only: inspect, capture, query
    ARTIST = "artist"       # Read + write: create, edit, execute, render
    LEAD = "lead"           # Artist + admin: delete, configure, manage users
    ADMIN = "admin"         # Full access including server config

# Permission matrix
ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.VIEWER: {"ping", "get_health", "get_scene_info", "get_selection",
                  "get_parm", "get_stage_info", "get_usd_attribute",
                  "capture_viewport", "inspect_*", "knowledge_lookup",
                  "search", "recall", "context", "list_recipes",
                  "get_metrics", "router_stats",
                  "tops_get_*", "tops_pipeline_status", "tops_diagnose"},
    Role.ARTIST: {"*"},     # Everything except admin operations
    Role.LEAD: {"*"},       # Same as artist + user management
    Role.ADMIN: {"*"},      # Unrestricted
}

# Deny list (operations explicitly blocked per role)
ROLE_DENIALS: dict[Role, set[str]] = {
    Role.VIEWER: {"create_*", "delete_*", "set_*", "execute_*",
                  "render", "wedge", "batch_commands",
                  "tops_cook_*", "tops_dirty_*", "tops_cancel_*",
                  "tops_generate_*", "tops_configure_*", "tops_setup_*"},
    Role.ARTIST: {"server_config", "manage_users"},
    Role.LEAD: {"server_config"},
    Role.ADMIN: set(),
}
```

### 2.2 `server/sessions.py` -- Multi-User Session Management

```python
@dataclass
class UserSession:
    session_id: str              # Deterministic from user_id + timestamp
    user_id: str                 # From auth token
    role: Role                   # RBAC role
    created_at: float            # time.monotonic()
    last_active: float           # Updated on each request
    metadata: dict               # User agent, IP, etc.

class SessionManager:
    """Track active user sessions. Thread-safe."""
    _sessions: dict[str, UserSession]    # session_id -> UserSession
    _lock: threading.Lock

    def create_session(self, user_id: str, role: Role) -> UserSession: ...
    def get_session(self, session_id: str) -> UserSession | None: ...
    def validate_permission(self, session_id: str, command: str) -> bool: ...
    def expire_stale(self, max_idle: float = 3600.0) -> int: ...
```

### 2.3 `server/tls.py` -- TLS Wrapper (VPN Mode)

Optional TLS termination for `studio-vpn` deploy mode. Uses Python `ssl` stdlib module.

```python
def create_ssl_context(
    certfile: str,    # Path to PEM certificate
    keyfile: str,     # Path to PEM private key
    cafile: str | None = None,  # Optional CA for client cert verification
) -> ssl.SSLContext: ...
```

### 2.4 Deployment Configuration

`~/.synapse/deploy.json` (or `SYNAPSE_DEPLOY_CONFIG` env var):

```json
{
  "mode": "studio-lan",
  "bind": "0.0.0.0",
  "port": 9999,
  "auth": {
    "required": true,
    "token_source": "local",
    "users_file": "~/.synapse/users.json"
  },
  "tls": {
    "enabled": false,
    "certfile": "",
    "keyfile": ""
  },
  "rbac": {
    "default_role": "artist",
    "deny_unknown_users": false
  }
}
```

### 2.5 User Directory

`~/.synapse/users.json`:

```json
{
  "users": [
    {"id": "alice", "name": "Alice Chen", "role": "lead", "key_hash": "sha256:abc..."},
    {"id": "bob", "name": "Bob Kim", "role": "artist", "key_hash": "sha256:def..."},
    {"id": "viewer-ci", "name": "CI Pipeline", "role": "viewer", "key_hash": "sha256:ghi..."}
  ]
}
```

Keys are stored as SHA-256 hashes. Comparison uses `hmac.compare_digest` (constant-time).

---

## 3. PHASES

| Phase | Scope | Gate Files |
|-------|-------|------------|
| **Phase 1 -- RBAC** | Role definitions, permission matrix, middleware integration | `server/rbac.py` exists, tests pass |
| **Phase 2 -- Multi-User** | Session manager, per-user audit, user directory | `server/sessions.py` exists, tests pass |
| **Phase 3 -- Remote** | LAN binding, TLS option, deploy config | `docs/studio/DEPLOYMENT.md` exists |
| **Phase 4 -- Tooling** | CLI for user management, deploy scripts, monitoring | Integration tests pass |

### Phase 1 Rules
- RBAC middleware wraps existing handler dispatch -- does NOT modify handlers
- Permission check happens AFTER parameter resolution, BEFORE handler execution
- Local mode (`127.0.0.1`) skips RBAC entirely -- backward compatible
- Wildcard matching for permission patterns (`inspect_*` matches `inspect_scene`, `inspect_node`)

### Phase 2 Rules
- Sessions are server-side only -- no cookies, no JWT
- Session ID returned in `Mcp-Session-Id` header (reuses existing MCP session mechanism)
- Audit log entries include `user_id` field when sessions are active
- Session expiry: 1 hour idle by default, configurable

### Phase 3 Rules
- LAN binding requires `SYNAPSE_DEPLOY_MODE=studio-lan` -- never auto-bind to 0.0.0.0
- TLS is optional, only for VPN mode
- Origin validation remains active for all modes
- Document firewall rules for studio IT teams

### Phase 4 Rules
- CLI commands via `python -m synapse.cli` (new module)
- `synapse user add alice --role lead` / `synapse user list` / `synapse user remove bob`
- Deploy config validation on startup

---

## 4. FILESYSTEM GATES

Sprint D is complete when ALL of these exist:

```
python/synapse/server/rbac.py          -- Role-based access control
python/synapse/server/sessions.py      -- Multi-user session management
docs/studio/DEPLOYMENT.md              -- Studio deployment guide
```

**Verification:**
```bash
ls python/synapse/server/rbac.py python/synapse/server/sessions.py \
   docs/studio/DEPLOYMENT.md 2>/dev/null | wc -l
# Must return 3
python -m pytest tests/test_rbac.py tests/test_sessions.py -v
# Must pass
```

---

## 5. SECURITY CONSIDERATIONS

- **Key rotation**: Support key rotation without downtime (accept old + new key during grace period)
- **Brute force**: Rate limiter already exists in `resilience.py` -- apply per-IP for auth attempts
- **Audit**: Every auth failure logged with IP, timestamp, attempted user
- **Secrets**: Never log API keys or tokens. User file stores hashes only.
- **Network**: Document that SYNAPSE transmits scene data in cleartext unless TLS is enabled
- **Cloud awareness**: Claude Code sends tool results to Anthropic API -- document data flow for studio compliance teams

---

## 6. He2025 COMPLIANCE

| Pattern | Applied In |
|---------|-----------|
| `deterministic_uuid()` | Session IDs (from user_id + monotonic timestamp) |
| `hmac.compare_digest()` | All key comparisons (constant-time) |
| `dict(sorted())` | Permission sets serialization |
| `sorted()` | User lists, session lists |
| `encoding="utf-8"` | users.json, deploy.json, all config files |

---

*Cross-reference: auth.py for existing key auth, resilience.py for rate limiting, CLAUDE.md for security section.*
