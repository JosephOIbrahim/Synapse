# SYNAPSE — MCP Protocol Sprint Instructions

> **Sprint Goal:** Add MCP (Model Context Protocol) conformance to SYNAPSE's hwebserver,
> making SYNAPSE a universal MCP server accessible by Claude Code, Cursor, VS Code, and any
> MCP-compliant client. This is a force-multiplier — every subsequent feature (including TOPS)
> becomes available to the entire AI tooling ecosystem.
>
> **Protocol Version Target:** MCP 2025-06-18 (Streamable HTTP transport)

---

## 0. TOPS INTEGRATION — PARKED

**Status: PARKED — Do not work on TOPS/PDG until Section 5 criteria are met.**

### What Was In Progress
- PDG/TOPs workflow integration for distributed cooking, wedging, and dependency management
- Work item generation, scheduler configuration, farm submission
- Dependency graph management

### Parking Protocol
1. **Do NOT modify any files in the TOPS/PDG integration paths**
2. **Do NOT refactor TOPS-related code as part of MCP work**
3. If you encounter TOPS code while implementing MCP, leave it untouched
4. If MCP implementation reveals a natural interface point for TOPS, **document it as a note
   in `docs/mcp/TOPS_INTEGRATION_POINTS.md`** but do not implement
5. All TOPS-related branches should remain as-is — no rebasing, no merging

### TOPS Context Snapshot (For Resumption)
```
WHERE IT WAS:
- [Claude Code: fill this in from current codebase state on first run]

WHAT WAS BEING THOUGHT ABOUT:
- [Claude Code: inspect any TOPS-related branches/files and summarize]

IMMEDIATE NEXT ACTION WHEN RESUMED:
- [Claude Code: determine from code state]

BLOCKERS:
- MCP protocol layer must be complete first (this sprint)
```

**Action on first run:** Scan the codebase for TOPS/PDG work-in-progress. Populate the
snapshot above into `docs/tops/PARKING_SNAPSHOT.md` so resumption is clean.

---

## 1. ARCHITECTURE OVERVIEW

### Current SYNAPSE Stack
```
┌─────────────────────────────────────────────┐
│  AI Client (Claude Desktop, custom, etc.)   │
└──────────────────┬──────────────────────────┘
                   │ websocket / http
┌──────────────────▼──────────────────────────┐
│  SYNAPSE Server (hwebserver)                │
│  ┌────────────────────────────────────────┐ │
│  │  Safety Middleware                     │ │
│  │  • Atomic scripts (1 mutation/call)    │ │
│  │  • Idempotent guards (check → mutate) │ │
│  │  • Undo-group transactions            │ │
│  └────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────┐ │
│  │  Command Handlers                     │ │
│  │  • execute_vex, create_node, etc.     │ │
│  └────────────────────────────────────────┘ │
└──────────────────┬──────────────────────────┘
                   │ hou module
┌──────────────────▼──────────────────────────┐
│  Houdini Session                            │
└─────────────────────────────────────────────┘
```

### Target Stack (After This Sprint)
```
┌─────────────────────────────────────────────┐
│  ANY MCP Client                             │
│  Claude Code, Cursor, VS Code, Windsurf,    │
│  Cline, custom agents, etc.                 │
└──────────────────┬──────────────────────────┘
                   │ MCP protocol (Streamable HTTP)
                   │ JSON-RPC 2.0 over POST /mcp
┌──────────────────▼──────────────────────────┐
│  SYNAPSE MCP Layer (NEW)                    │
│  ┌────────────────────────────────────────┐ │
│  │  MCP Protocol Handler                 │ │
│  │  • initialize / initialized           │ │
│  │  • tools/list, tools/call             │ │
│  │  • resources/list, resources/read     │ │
│  │  • prompts/list, prompts/get          │ │
│  │  • Session management (Mcp-Session-Id)│ │
│  └────────────────┬───────────────────────┘ │
│  ┌────────────────▼───────────────────────┐ │
│  │  Safety Middleware (UNCHANGED)         │ │
│  │  • Atomic scripts (1 mutation/call)    │ │
│  │  • Idempotent guards (check → mutate) │ │
│  │  • Undo-group transactions            │ │
│  └────────────────┬───────────────────────┘ │
│  ┌────────────────▼───────────────────────┐ │
│  │  Command Handlers (UNCHANGED)         │ │
│  └────────────────────────────────────────┘ │
│                                             │
│  Legacy API (existing endpoints preserved)  │
└──────────────────┬──────────────────────────┘
                   │ hou module
┌──────────────────▼──────────────────────────┐
│  Houdini Session                            │
└─────────────────────────────────────────────┘
```

**Key Principle:** The MCP layer is a **protocol adapter** that sits on top of the existing
SYNAPSE architecture. It does NOT replace the safety middleware or command handlers. It
translates MCP JSON-RPC calls into existing SYNAPSE commands. Existing non-MCP endpoints
continue to work.

---

## 2. MCP PROTOCOL IMPLEMENTATION

### 2.1 Transport: Streamable HTTP

The MCP endpoint is a single URL that accepts both POST and GET:

```
POST /mcp   →  Client sends JSON-RPC requests/notifications
GET  /mcp   →  Optional SSE stream for server-to-client messages
```

**Integration with hwebserver:**
- Register a single handler on the `/mcp` path
- POST handler: parse JSON-RPC, route to method handlers, return response
- GET handler: optionally open SSE stream (can defer to Phase 2)
- Existing SYNAPSE endpoints remain on their current paths (no breaking changes)

### 2.2 Session Management

Each MCP session gets a unique `Mcp-Session-Id`:

```python
import uuid

class MCPSessionManager:
    """Manages MCP client sessions."""

    def __init__(self):
        self.sessions = {}  # session_id -> session_state

    def create_session(self, client_info: dict) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "client_info": client_info,
            "created_at": time.time(),
            "protocol_version": "2025-06-18",
            "initialized": False,
        }
        return session_id

    def get_session(self, session_id: str) -> dict | None:
        return self.sessions.get(session_id)

    def destroy_session(self, session_id: str):
        self.sessions.pop(session_id, None)
```

**Response headers must include:**
```
Mcp-Session-Id: <session-id>
Content-Type: application/json  (or text/event-stream for SSE)
```

### 2.3 JSON-RPC 2.0 Message Format

All MCP messages use JSON-RPC 2.0:

```python
# Request (client → server)
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "execute_vex",
        "arguments": {"code": "@P.y = sin(@P.x);", "node_path": "/obj/geo1/wrangle1"}
    }
}

# Response (server → client)
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "content": [
            {"type": "text", "text": "VEX executed successfully on /obj/geo1/wrangle1"}
        ]
    }
}

# Error response
{
    "jsonrpc": "2.0",
    "id": 1,
    "error": {
        "code": -32603,
        "message": "Safety guard rejected: mutation without idempotent check",
        "data": {"guard": "idempotent", "operation": "execute_vex"}
    }
}
```

### 2.4 Required Method Handlers

Implement these in order of priority:

#### Phase 1 — Core (MVP for Claude Code connectivity)

| Method | Purpose | Priority |
|--------|---------|----------|
| `initialize` | Capability negotiation, version handshake | **P0** |
| `notifications/initialized` | Client confirms init complete | **P0** |
| `tools/list` | Enumerate available SYNAPSE tools | **P0** |
| `tools/call` | Execute a tool (routes to existing handlers) | **P0** |

#### Phase 2 — Resources & Prompts

| Method | Purpose | Priority |
|--------|---------|----------|
| `resources/list` | Expose scene state, node trees, attributes | **P1** |
| `resources/read` | Read specific resource by URI | **P1** |
| `prompts/list` | Reusable prompt templates for Houdini tasks | **P2** |
| `prompts/get` | Retrieve specific prompt | **P2** |

#### Phase 3 — Advanced

| Method | Purpose | Priority |
|--------|---------|----------|
| `resources/subscribe` | Watch for scene changes | **P3** |
| `notifications/resources/updated` | Push scene change notifications | **P3** |
| `logging/setLevel` | Configure server logging | **P3** |

### 2.5 Initialize Handler

```python
async def handle_initialize(params: dict, session: dict) -> dict:
    """MCP initialize handshake."""

    # Store client capabilities
    session["client_info"] = params.get("clientInfo", {})
    session["protocol_version"] = params.get("protocolVersion", "2025-06-18")

    return {
        "protocolVersion": "2025-06-18",
        "capabilities": {
            "tools": {
                "listChanged": True  # We can notify when tools change
            },
            "resources": {
                "subscribe": False,  # Phase 3
                "listChanged": False  # Phase 3
            },
            # "prompts": {},  # Uncomment in Phase 2
        },
        "serverInfo": {
            "name": "synapse",
            "version": "2.1.0"  # Match current SYNAPSE version
        },
        "instructions": (
            "SYNAPSE is a bridge between AI agents and SideFX Houdini. "
            "All mutations go through safety middleware enforcing atomic scripts, "
            "idempotent guards, and undo-group transactions. "
            "Tools that modify the scene are destructive unless noted otherwise."
        )
    }
```

### 2.6 Tools — Mapping Existing SYNAPSE Commands

**Each existing SYNAPSE command handler becomes an MCP tool.** The tool definition provides
the JSON Schema that MCP clients use for tool discovery.

Example tool registration pattern:

```python
# Registry of MCP tools backed by existing SYNAPSE handlers
MCP_TOOLS = [
    {
        "name": "execute_vex",
        "description": (
            "Execute VEX code on a wrangle node in the Houdini scene. "
            "The code runs through SYNAPSE safety middleware: atomic execution, "
            "idempotent guards, and undo-group wrapping."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "VEX source code to execute"
                },
                "node_path": {
                    "type": "string",
                    "description": "Full path to the wrangle node (e.g., /obj/geo1/attribwrangle1)"
                },
                "run_over": {
                    "type": "string",
                    "enum": ["Points", "Vertices", "Primitives", "Detail"],
                    "default": "Points",
                    "description": "What geometry element to iterate over"
                }
            },
            "required": ["code", "node_path"]
        },
        "annotations": {
            "title": "Execute VEX Code",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False
        }
    },
    {
        "name": "read_attributes",
        "description": (
            "Read geometry attributes from a node. Returns attribute names, types, "
            "and optionally sample values. This is a read-only operation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_path": {
                    "type": "string",
                    "description": "Full path to the SOP node"
                },
                "attribute_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific attributes to read (empty = all)"
                },
                "sample_count": {
                    "type": "integer",
                    "default": 10,
                    "description": "Number of sample values to return per attribute"
                }
            },
            "required": ["node_path"]
        },
        "annotations": {
            "title": "Read Geometry Attributes",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        }
    },
    {
        "name": "create_node",
        "description": (
            "Create a new node in the Houdini scene graph. "
            "Goes through undo-group transaction wrapping."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "parent_path": {
                    "type": "string",
                    "description": "Path to the parent network (e.g., /obj/geo1)"
                },
                "node_type": {
                    "type": "string",
                    "description": "Houdini node type (e.g., 'attribwrangle', 'null', 'merge')"
                },
                "node_name": {
                    "type": "string",
                    "description": "Desired name for the new node (optional, auto-named if omitted)"
                }
            },
            "required": ["parent_path", "node_type"]
        },
        "annotations": {
            "title": "Create Node",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False
        }
    },
    {
        "name": "get_scene_tree",
        "description": (
            "Return the node hierarchy of the current Houdini scene or a subtree. "
            "Useful for understanding scene structure before making modifications."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "root_path": {
                    "type": "string",
                    "default": "/obj",
                    "description": "Root path to start traversal"
                },
                "depth": {
                    "type": "integer",
                    "default": 3,
                    "description": "Maximum traversal depth"
                },
                "include_types": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include node type info in output"
                }
            }
        },
        "annotations": {
            "title": "Get Scene Tree",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        }
    },
    {
        "name": "set_parameter",
        "description": (
            "Set a parameter value on a node. Goes through safety middleware. "
            "Supports numeric, string, and expression values."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_path": {
                    "type": "string",
                    "description": "Full path to the node"
                },
                "parm_name": {
                    "type": "string",
                    "description": "Parameter name (e.g., 'tx', 'divisions', 'file')"
                },
                "value": {
                    "description": "Value to set (number, string, or expression string)"
                },
                "is_expression": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, value is treated as a Houdini expression"
                }
            },
            "required": ["node_path", "parm_name", "value"]
        },
        "annotations": {
            "title": "Set Parameter",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False
        }
    },
    {
        "name": "get_parameter",
        "description": "Read a parameter's current value, expression, and metadata from a node.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_path": {"type": "string", "description": "Full path to the node"},
                "parm_name": {"type": "string", "description": "Parameter name"}
            },
            "required": ["node_path", "parm_name"]
        },
        "annotations": {
            "title": "Get Parameter",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        }
    }
]
```

**Extend this list** by auditing all existing SYNAPSE command handlers. Each handler that
accepts a request and returns a result maps 1:1 to an MCP tool. Use `annotations` to
declare read-only vs destructive behavior — MCP clients use this for UI/safety decisions.

### 2.7 Resources — Exposing Scene State

Resources are read-only data that clients can browse. For Houdini:

```python
MCP_RESOURCES = [
    {
        "uri": "houdini://scene/info",
        "name": "Scene Info",
        "description": "Current hip file path, frame range, FPS, and scene statistics",
        "mimeType": "application/json"
    },
    {
        "uri": "houdini://scene/tree",
        "name": "Node Tree",
        "description": "Full node hierarchy of the current scene",
        "mimeType": "application/json"
    },
    {
        "uri": "houdini://node/{path}/parameters",
        "name": "Node Parameters",
        "description": "All parameter values for a specific node",
        "mimeType": "application/json"
    },
    {
        "uri": "houdini://node/{path}/attributes",
        "name": "Geometry Attributes",
        "description": "Attribute metadata and sample values for a SOP node",
        "mimeType": "application/json"
    },
    {
        "uri": "houdini://node/{path}/cook-stats",
        "name": "Cook Statistics",
        "description": "Cook time, memory usage, and dependency info",
        "mimeType": "application/json"
    }
]
```

Resource URIs with `{path}` are **resource templates** — the client fills in the parameter.

### 2.8 Prompts — Reusable Houdini Workflows (Phase 2)

```python
MCP_PROMPTS = [
    {
        "name": "vex_debug",
        "description": "Debug a VEX wrangle by inspecting inputs, running code, and checking outputs",
        "arguments": [
            {"name": "node_path", "description": "Path to the wrangle node", "required": True}
        ]
    },
    {
        "name": "lighting_setup",
        "description": "Set up a standard 3-point lighting rig in the current scene",
        "arguments": [
            {"name": "target_path", "description": "Node to point lights at", "required": False}
        ]
    },
    {
        "name": "scene_audit",
        "description": "Audit the scene for common issues: unnamed nodes, missing textures, heavy geometry",
        "arguments": []
    }
]
```

### 2.9 Main Request Router

```python
async def handle_mcp_request(request_body: bytes, headers: dict) -> tuple[int, dict, bytes]:
    """
    Main MCP endpoint handler for hwebserver.

    Returns: (status_code, response_headers, response_body)
    """
    try:
        message = json.loads(request_body)
    except json.JSONDecodeError:
        return 400, {}, json.dumps({
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": "Parse error"}
        }).encode()

    # Validate JSON-RPC structure
    if message.get("jsonrpc") != "2.0":
        return 400, {}, json.dumps({
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {"code": -32600, "message": "Invalid Request: missing jsonrpc 2.0"}
        }).encode()

    method = message.get("method")
    params = message.get("params", {})
    msg_id = message.get("id")  # None for notifications

    # Session management
    session_id = headers.get("Mcp-Session-Id") or headers.get("mcp-session-id")
    session = session_manager.get_session(session_id) if session_id else None

    response_headers = {"Content-Type": "application/json"}

    # Route methods
    if method == "initialize":
        session_id = session_manager.create_session(params.get("clientInfo", {}))
        result = await handle_initialize(params, session_manager.get_session(session_id))
        response_headers["Mcp-Session-Id"] = session_id
        return 200, response_headers, _jsonrpc_result(msg_id, result)

    elif method == "notifications/initialized":
        if session:
            session["initialized"] = True
        return 202, {}, b""  # Accepted, no body

    elif method == "tools/list":
        result = {"tools": MCP_TOOLS}
        return 200, response_headers, _jsonrpc_result(msg_id, result)

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        result = await dispatch_tool(tool_name, tool_args)
        return 200, response_headers, _jsonrpc_result(msg_id, result)

    elif method == "resources/list":
        result = {"resources": MCP_RESOURCES}
        return 200, response_headers, _jsonrpc_result(msg_id, result)

    elif method == "resources/read":
        uri = params.get("uri")
        result = await read_resource(uri)
        return 200, response_headers, _jsonrpc_result(msg_id, result)

    elif method == "ping":
        return 200, response_headers, _jsonrpc_result(msg_id, {})

    else:
        return 200, response_headers, json.dumps({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }).encode()


def _jsonrpc_result(msg_id, result: dict) -> bytes:
    return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}).encode()
```

### 2.10 Tool Dispatch — Bridge to Existing Handlers

```python
async def dispatch_tool(tool_name: str, arguments: dict) -> dict:
    """
    Bridge MCP tool calls to existing SYNAPSE command handlers.

    The safety middleware (atomic scripts, idempotent guards, undo-groups)
    is applied by the existing handlers — NOT bypassed.
    """
    handler = SYNAPSE_HANDLER_REGISTRY.get(tool_name)
    if not handler:
        raise MCPError(-32602, f"Unknown tool: {tool_name}")

    try:
        # Existing handlers already enforce safety middleware
        result = await handler(arguments)

        # Wrap result in MCP content format
        return {
            "content": [
                {"type": "text", "text": json.dumps(result) if isinstance(result, dict) else str(result)}
            ]
        }
    except SynapseError as e:
        # Safety middleware rejections, Houdini errors, etc.
        return {
            "content": [
                {"type": "text", "text": f"Error: {e.message}"}
            ],
            "isError": True
        }
```

**CRITICAL: `dispatch_tool` does not implement any safety logic itself. It delegates to
existing SYNAPSE handlers which already have the safety middleware baked in. The MCP layer
is a thin protocol translation, nothing more.**

---

## 3. CONNECTING CLAUDE CODE TO SYNAPSE

### 3.1 User-Facing Setup

Once the MCP endpoint is running in Houdini, connecting Claude Code is one command:

```bash
# Basic connection (SYNAPSE running on default port)
claude mcp add --transport http synapse http://localhost:PORT/mcp

# With project scope (shared via .mcp.json for team)
claude mcp add --transport http --scope project synapse http://localhost:PORT/mcp

# Verify connection
claude mcp list
# Inside Claude Code:
/mcp
```

### 3.2 .mcp.json for SYNAPSE Projects

For any project using SYNAPSE, include this at the repo root:

```json
{
  "synapse": {
    "type": "http",
    "url": "http://localhost:PORT/mcp"
  }
}
```

This means anyone who clones the repo and has Houdini + SYNAPSE running gets automatic
MCP connectivity in Claude Code.

### 3.3 Testing the Connection

After implementation, verify with this sequence:

```bash
# 1. Start Houdini with SYNAPSE loaded
# 2. In another terminal:
claude mcp add --transport http synapse http://localhost:PORT/mcp

# 3. Open Claude Code in your project:
claude

# 4. Test tool discovery:
> "What Houdini tools are available?"
# Claude Code should list all SYNAPSE tools

# 5. Test read-only operation:
> "Show me the scene tree"
# Should return node hierarchy

# 6. Test mutation:
> "Create a box node in /obj/geo1"
# Should create node with undo-group wrapping

# 7. Test safety:
> "Read the attributes on the node you just created"
# Should work through idempotent read path
```

### 3.4 Security Considerations

- **Localhost only by default.** SYNAPSE MCP endpoint should bind to `127.0.0.1`, not
  `0.0.0.0`. Claude Code runs locally so this is sufficient.
- **No auth required for local.** MCP spec requires auth for remote servers, but localhost
  is fine without it. Add bearer token support as an opt-in for remote/studio deployment.
- **Cloud context awareness.** Claude Code sends tool results to Anthropic's API for model
  processing. This means scene data (node names, attribute values, etc.) will transit
  through cloud infrastructure. Note this in SYNAPSE docs for users with proprietary scenes.
- **Origin validation.** Validate the `Origin` header to mitigate DNS rebinding attacks
  per MCP spec requirements for HTTP transport.

---

## 4. IMPLEMENTATION PLAN

### Phase 1 — MVP (Target: get Claude Code connected)

**Deliverables:**
- [ ] `/mcp` endpoint registered on hwebserver
- [ ] JSON-RPC 2.0 request parsing and response formatting
- [ ] Session management (create, track, destroy)
- [ ] `initialize` / `notifications/initialized` handshake
- [ ] `tools/list` returning all existing SYNAPSE commands as MCP tools
- [ ] `tools/call` dispatching to existing handlers through safety middleware
- [ ] `ping` handler
- [ ] Error handling with proper JSON-RPC error codes
- [ ] Mcp-Session-Id header management
- [ ] Basic request validation (protocol version, required fields)

**Verification:** `claude mcp add --transport http synapse http://localhost:PORT/mcp`
successfully connects and Claude Code can call SYNAPSE tools.

### Phase 2 — Resources & Prompts

**Deliverables:**
- [ ] `resources/list` with scene info, node tree, parameters, attributes
- [ ] `resources/read` handler for each resource URI
- [ ] Resource templates for node-specific data (`houdini://node/{path}/...`)
- [ ] `prompts/list` and `prompts/get` for common Houdini workflows
- [ ] Updated capabilities in `initialize` response

**Verification:** Claude Code can browse Houdini scene state through resources and use
prompt templates for multi-step operations.

### Phase 3 — Polish & Advanced

**Deliverables:**
- [ ] `list_changed` notifications when tools or resources change
- [ ] Optional SSE stream on GET /mcp for server-initiated messages
- [ ] `resources/subscribe` for live scene monitoring
- [ ] Bearer token authentication (opt-in for remote deployments)
- [ ] MCP-Protocol-Version header validation
- [ ] Rate limiting for safety (prevent runaway tool calls)
- [ ] Comprehensive test suite against MCP protocol spec
- [ ] Documentation: README section on MCP connectivity

**Verification:** Full MCP spec compliance. Works with Claude Code, Cursor, VS Code.

### File Organization

```
synapse/
├── mcp/                          # NEW — all MCP protocol code
│   ├── __init__.py
│   ├── server.py                 # Main endpoint handler, request router
│   ├── session.py                # Session manager
│   ├── tools.py                  # Tool registry (maps to existing handlers)
│   ├── resources.py              # Resource definitions and readers
│   ├── prompts.py                # Prompt templates (Phase 2)
│   ├── protocol.py               # JSON-RPC utilities, error codes
│   └── types.py                  # Type definitions, schemas
├── handlers/                     # EXISTING — command handlers (UNCHANGED)
├── middleware/                    # EXISTING — safety middleware (UNCHANGED)
├── docs/
│   ├── mcp/
│   │   ├── SETUP.md              # User-facing MCP connection guide
│   │   └── TOPS_INTEGRATION_POINTS.md  # Notes for TOPS resumption
│   └── tops/
│       └── PARKING_SNAPSHOT.md   # TOPS state at time of parking
└── ...
```

---

## 5. TOPS RESUMPTION CRITERIA

**Do NOT resume TOPS work until ALL of the following are true:**

1. ✅ Phase 1 MVP is complete and verified
2. ✅ Claude Code can successfully `tools/list` and `tools/call` through SYNAPSE
3. ✅ At least one non-Claude MCP client (Cursor or VS Code) has been tested
4. ✅ Safety middleware is confirmed working through MCP path (undo-groups, idempotent guards)
5. ✅ `docs/mcp/SETUP.md` exists with user-facing setup instructions
6. ✅ Phase 2 resources are at least partially working (scene tree, node parameters)

### TOPS Resumption Protocol

When all criteria above are met:

1. Read `docs/tops/PARKING_SNAPSHOT.md` to restore context
2. Check if any MCP integration points were noted in `docs/mcp/TOPS_INTEGRATION_POINTS.md`
3. **TOPS commands should be registered as MCP tools from the start** — don't build TOPS
   with a separate API and then retrofit MCP. The MCP tool registration pattern is now the
   standard way to expose SYNAPSE functionality
4. New TOPS tools get the same treatment: JSON Schema input definitions, annotation hints,
   dispatch through safety middleware
5. Consider TOPS-specific resources: `houdini://tops/{scheduler}/status`, work item state

### TOPS as MCP Tools (Preview)

When TOPS resumes, these tools should be added to the MCP registry:

```python
# These are PLANNED — do not implement until resumption criteria are met
TOPS_MCP_TOOLS_PLANNED = [
    {
        "name": "tops_generate_work_items",
        "description": "Generate work items for a TOP node",
        "annotations": {"destructiveHint": True}
    },
    {
        "name": "tops_cook_node",
        "description": "Cook a TOP node and its dependencies",
        "annotations": {"destructiveHint": True}
    },
    {
        "name": "tops_get_work_item_status",
        "description": "Get status of work items (scheduled, cooking, cooked, failed)",
        "annotations": {"readOnlyHint": True}
    },
    {
        "name": "tops_configure_scheduler",
        "description": "Configure PDG scheduler (local, HQueue, Deadline)",
        "annotations": {"destructiveHint": True}
    },
    {
        "name": "tops_get_dependency_graph",
        "description": "Return the dependency graph for a TOP network",
        "annotations": {"readOnlyHint": True}
    }
]
```

---

## 6. REFERENCE

### JSON-RPC 2.0 Error Codes

| Code | Meaning | When to Use |
|------|---------|-------------|
| -32700 | Parse error | Invalid JSON received |
| -32600 | Invalid Request | Missing jsonrpc, method, etc. |
| -32601 | Method not found | Unknown MCP method |
| -32602 | Invalid params | Bad tool arguments, missing required fields |
| -32603 | Internal error | Houdini crash, unexpected exception |

### MCP-Specific Error Codes (Custom)

| Code | Meaning | When to Use |
|------|---------|-------------|
| -32001 | Safety guard rejection | Middleware blocked the operation |
| -32002 | Node not found | Houdini node path doesn't exist |
| -32003 | Cook error | Houdini cook failed |
| -32004 | Session invalid | Bad or expired Mcp-Session-Id |

### Key MCP Protocol Headers

| Header | Direction | Purpose |
|--------|-----------|---------|
| `Mcp-Session-Id` | Both | Session identifier |
| `MCP-Protocol-Version` | Client → Server | Protocol version (2025-06-18) |
| `Content-Type` | Both | `application/json` or `text/event-stream` |
| `Accept` | Client → Server | Must include both `application/json` and `text/event-stream` |

### Python MCP SDK (Alternative Approach)

Instead of implementing the protocol from scratch, you CAN use the official Python MCP SDK:

```bash
pip install mcp
```

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("synapse", json_response=True)

@mcp.tool(annotations={"readOnlyHint": True})
def get_scene_tree(root_path: str = "/obj", depth: int = 3) -> dict:
    """Return the node hierarchy of the current Houdini scene."""
    # Delegates to existing SYNAPSE handler
    return synapse_handlers.get_scene_tree(root_path, depth)

@mcp.tool(annotations={"destructiveHint": True})
def execute_vex(code: str, node_path: str, run_over: str = "Points") -> str:
    """Execute VEX code on a wrangle node through SYNAPSE safety middleware."""
    return synapse_handlers.execute_vex(code, node_path, run_over)

@mcp.resource("houdini://scene/info")
def scene_info() -> dict:
    """Current hip file, frame range, FPS."""
    return synapse_handlers.get_scene_info()

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

**Trade-off:** The SDK handles all protocol plumbing (JSON-RPC, session management,
capability negotiation) automatically. But it introduces an external dependency and its
own HTTP server, which may conflict with hwebserver. **Evaluate whether the SDK's HTTP
layer can be integrated with hwebserver or if you need the manual approach.**

The recommended path: **Try the SDK first.** If hwebserver integration is straightforward,
use it. If not, fall back to the manual implementation in sections 2.2–2.10 above.

---

## 7. SUCCESS CRITERIA

This sprint is complete when:

1. **A developer can type `claude mcp add --transport http synapse http://localhost:PORT/mcp`
   and immediately have Houdini-aware AI coding assistance**
2. **The same SYNAPSE server works with Cursor, VS Code, or any other MCP client**
3. **All operations go through the existing safety middleware — no shortcuts, no bypasses**
4. **Existing non-MCP SYNAPSE functionality is unbroken**
5. **TOPS integration points are documented for clean resumption**

---

*This document is the single source of truth for the MCP sprint. When in doubt, refer here.*
*When this sprint is complete, SYNAPSE becomes provider-agnostic infrastructure.*
