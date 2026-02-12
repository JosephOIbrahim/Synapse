# SYNAPSE AGENT SDK BLUEPRINT
## Autonomous VFX Co-Pilot — Claude Agent SDK + Opus 4.6

> **Architecture shift:** Synapse evolves from a reactive MCP bridge (Claude Desktop → WebSocket → Houdini)
> into an autonomous agent that plans, executes, verifies, and iterates against a live Houdini scene.
>
> **Blueprint origin:** Designed in Claude Desktop (with full project memory and conversation context).
> **Execution target:** Claude Code with Opus 4.6 Extended Thinking.

---

## Table of Contents

1. [Context & Current State](#1-context--current-state)
2. [Architecture Overview](#2-architecture-overview)
3. [File Structure](#3-file-structure)
4. [Phase 0: WebSocket Client](#4-phase-0-websocket-client)
5. [Phase 1: Custom Tools](#5-phase-1-custom-tools)
6. [Phase 2: Safety Hooks](#6-phase-2-safety-hooks)
7. [Phase 3: Agent Entry Point](#7-phase-3-agent-entry-point)
8. [Phase 4: CLAUDE.md — Agent Personality](#8-phase-4-claudemd--agent-personality)
9. [Phase 5: Skills — Reusable VFX Recipes](#9-phase-5-skills--reusable-vfx-recipes)
10. [Phase 6: Test Protocol](#10-phase-6-test-protocol)
11. [Phase 7: Advanced Patterns](#11-phase-7-advanced-patterns)
12. [Consistency Checklist](#12-consistency-checklist)
13. [Execution Instructions for Claude Code](#13-execution-instructions-for-claude-code)

---

## 1. Context & Current State

### What Synapse Is Today

Synapse is a WebSocket bridge between Claude and SideFX Houdini 21. It runs as a
Python server inside Houdini's process, exposing the full `hou` module to Claude
via JSON-over-WebSocket at `ws://localhost:9999`.

**Protocol:** v4.0.0
**Existing MCP Tools:**
- `synapse_ping` — connectivity check, returns protocol version
- `houdini_execute_python` — executes arbitrary Python in Houdini, returns `result` variable
- `houdini_scene_info` — returns HIP file path, frame range, FPS
- `houdini_capture_viewport` — screenshots the viewport

**Safety Layers (implemented or in-progress):**
- **Atomic scripts:** One mutation per `houdini_execute_python` call
- **Idempotent guards:** `guards.py` module with `ensure_node()`, `ensure_connection()`,
  `ensure_parm()`, `node_exists()`, etc. — auto-injected into exec namespace
- **Transaction wrapper:** `hou.undos.group("synapse_operation")` with `hou.undos.performUndo()`
  on exception — wraps all execute_python calls in the server handler

**Tone System (designed, implementation in progress):**
- Server-side message rewrites (errors → coaching language)
- MCP tool description tone guidance
- `TONE.md` voice guide for LLM context
- Smart error enrichment (fuzzy node type matching, parameter discovery)

**Planned MCP Tools (from roadmap, not yet built):**
- `synapse_inspect_selection` — structured data on selected nodes
- `synapse_inspect_scene` — hierarchical scene overview
- `synapse_inspect_node` — deep single-node analysis

**Known Houdini 21 Conventions:**
- USD/Solaris nodes live at `/stage/`
- USD light parameter names use encoded form: `xn__inputsintensity_i0a` (not `intensity`)
- MaterialX shading via `mtlxstandard_surface` nodes
- Karma renderer (CPU and XPU) for final output
- Scene graph connections flow through merge nodes (e.g., `/stage/scene_merge`)

**File System:**
- Synapse source: `C:/Users/User/.synapse/`
- Shared transfer dir: `C:/Users/User/.synapse/` (also used for render output)
- Houdini projects: `D:/HOUDINI_PROJECTS_2025/`

### What We're Building

An **autonomous agent** using the Claude Agent SDK (Python) that:
1. Receives high-level VFX goals from the artist
2. Plans multi-step approaches using extended thinking
3. Executes against live Houdini via WebSocket (Synapse)
4. Verifies its own work via scene inspection
5. Iterates until the result matches intent
6. Communicates progress in encouraging, coaching language

### Why the Agent SDK

| Capability | MCP Bridge (current) | Agent SDK (new) |
|------------|---------------------|-----------------|
| Thinking depth | Standard | Extended thinking (Opus 4.6) |
| Autonomy | Reactive (user drives each step) | Autonomous (agent drives loops) |
| Tool chaining | LLM decides per-turn | Agent plans multi-step sequences |
| Error recovery | Manual retry | Hooks auto-rollback + retry |
| Verification | User checks result | Agent self-verifies |
| Context mgmt | Manual | Compaction (infinite conversation) |
| Parallelism | Sequential only | Subagents for concurrent work |
| File access | None | Full filesystem (read specs, write logs) |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    ARTIST (Joe)                              │
│                                                             │
│  Claude Desktop          Claude Code                        │
│  ┌─────────────┐        ┌──────────────────────────────┐   │
│  │ Memory      │        │ synapse_agent.py              │   │
│  │ Conversation│───────>│   ┌──────────────────────┐   │   │
│  │ Intent      │ paste  │   │ Claude Agent SDK      │   │   │
│  │ Blueprint   │ prompt │   │ (Opus 4.6 Extended)   │   │   │
│  └─────────────┘        │   │                        │   │   │
│                          │   │ Custom Tools:          │   │   │
│                          │   │  ├─ synapse_execute    │   │   │
│                          │   │  ├─ synapse_inspect    │   │   │
│                          │   │  ├─ synapse_scene      │   │   │
│                          │   │  └─ synapse_ping       │   │   │
│                          │   │                        │   │   │
│                          │   │ Hooks:                 │   │   │
│                          │   │  ├─ pre_execution      │   │   │
│                          │   │  ├─ post_verify        │   │   │
│                          │   │  └─ error_recovery     │   │   │
│                          │   └──────────┬─────────────┘   │   │
│                          │              │ WebSocket        │   │
│                          └──────────────┼──────────────────┘   │
│                                         │                      │
└─────────────────────────────────────────┼──────────────────────┘
                                          │
                                          ▼
                              ┌──────────────────────┐
                              │   Houdini 21         │
                              │   ┌────────────────┐ │
                              │   │ Synapse Server │ │
                              │   │ ws://localhost  │ │
                              │   │     :9999       │ │
                              │   │                │ │
                              │   │ guards.py      │ │
                              │   │ undo groups    │ │
                              │   │ hou module     │ │
                              │   └────────────────┘ │
                              │                      │
                              │   /stage/            │
                              │   ├─ hero_sphere     │
                              │   ├─ ground_plane    │
                              │   ├─ key_light       │
                              │   ├─ scene_merge     │
                              │   └─ karma_rop       │
                              └──────────────────────┘
```

**Data Flow:**
1. Artist describes intent in Claude Desktop (memory + conversation)
2. Artist pastes goal into Claude Code as a prompt
3. Agent SDK spawns Opus 4.6 with extended thinking
4. Agent calls custom tools → WebSocket → Synapse → Houdini
5. Agent inspects results → reasons about them → iterates
6. Agent reports completion with coaching tone

---

## 3. File Structure

Create this structure at `C:/Users/User/.synapse/agent/`:

```
C:/Users/User/.synapse/agent/
├── CLAUDE.md                          # Agent personality, tone, conventions
├── .claude/
│   ├── settings.json                  # Agent SDK settings
│   └── skills/
│       ├── three_point_lighting.md    # Reusable VFX recipe
│       ├── karma_render_preview.md    # Quick render workflow
│       └── scene_health_check.md      # Diagnostic workflow
├── synapse_agent.py                   # Main entry point
├── synapse_ws.py                      # WebSocket client (async)
├── synapse_tools.py                   # Custom tool definitions
├── synapse_hooks.py                   # Safety & verification hooks
├── synapse_tone.py                    # Message formatting & coaching language
├── requirements.txt                   # Dependencies
└── logs/                              # Agent execution logs
    └── .gitkeep
```

---

## 4. Phase 0: WebSocket Client

### `synapse_ws.py`

This is the low-level async WebSocket client that talks to Synapse.
It replaces the MCP protocol hop with a direct connection.

```python
"""
synapse_ws.py — Async WebSocket client for Synapse/Houdini bridge.

Connects directly to the Synapse server running inside Houdini at ws://localhost:9999.
All calls are async and return parsed JSON responses.

This module is the ONLY place that touches the WebSocket connection.
All other modules call functions from here.
"""

import asyncio
import json
import logging
from typing import Any, Optional
from contextlib import asynccontextmanager

logger = logging.getLogger("synapse.ws")

# --- Configuration ---
SYNAPSE_HOST = "localhost"
SYNAPSE_PORT = 9999
SYNAPSE_URI = f"ws://{SYNAPSE_HOST}:{SYNAPSE_PORT}"
CONNECT_TIMEOUT = 10.0
CALL_TIMEOUT = 120.0  # Houdini operations can take time (renders, cooks)
RENDER_TIMEOUT = 600.0  # 10 min for render calls


class SynapseConnectionError(Exception):
    """Raised when we can't reach Synapse."""
    pass


class SynapseExecutionError(Exception):
    """Raised when Houdini-side execution fails."""
    def __init__(self, message: str, partial_result: Any = None):
        super().__init__(message)
        self.partial_result = partial_result


class SynapseClient:
    """
    Async WebSocket client for Synapse.

    Usage:
        client = SynapseClient()
        await client.connect()
        result = await client.execute_python("result = hou.node('/stage').children()")
        await client.disconnect()

    Or as context manager:
        async with SynapseClient() as client:
            result = await client.ping()
    """

    def __init__(self, uri: str = SYNAPSE_URI):
        self.uri = uri
        self._ws = None
        self._connected = False
        self._lock = asyncio.Lock()  # Serialize WebSocket calls

    async def connect(self) -> bool:
        """Establish WebSocket connection to Synapse."""
        try:
            import websockets
            self._ws = await asyncio.wait_for(
                websockets.connect(self.uri),
                timeout=CONNECT_TIMEOUT
            )
            self._connected = True
            logger.info(f"Connected to Synapse at {self.uri}")
            return True
        except asyncio.TimeoutError:
            raise SynapseConnectionError(
                f"Couldn't reach Synapse at {self.uri} — is Houdini running with the Synapse server active?"
            )
        except Exception as e:
            raise SynapseConnectionError(
                f"Connection to Synapse failed: {e}. Check that Houdini is running and Synapse is loaded."
            )

    async def disconnect(self):
        """Close the WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._connected = False
            logger.info("Disconnected from Synapse")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def _send_and_receive(self, message: dict, timeout: float = CALL_TIMEOUT) -> dict:
        """
        Send a JSON message and wait for the response.
        Serialized via lock to prevent interleaved WebSocket frames.
        """
        if not self._connected or not self._ws:
            raise SynapseConnectionError("Not connected to Synapse. Call connect() first.")

        async with self._lock:
            try:
                await self._ws.send(json.dumps(message))
                raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
                return json.loads(raw)
            except asyncio.TimeoutError:
                raise SynapseExecutionError(
                    f"Synapse didn't respond within {timeout}s — the operation might still be running in Houdini. "
                    f"Check the Houdini viewport."
                )
            except Exception as e:
                raise SynapseExecutionError(f"Communication error: {e}")

    # --- High-Level API ---

    async def ping(self) -> dict:
        """Check Synapse connectivity. Returns protocol version info."""
        response = await self._send_and_receive(
            {"tool": "synapse_ping"},
            timeout=5.0
        )
        return response

    async def scene_info(self) -> dict:
        """Get current scene metadata (HIP path, frame range, FPS)."""
        response = await self._send_and_receive(
            {"tool": "houdini_scene_info"}
        )
        return response

    async def execute_python(self, code: str, timeout: float = CALL_TIMEOUT) -> Any:
        """
        Execute Python code inside Houdini. Returns the value of the `result` variable.

        The Synapse server handler wraps execution in hou.undos.group() and auto-injects
        guard functions (ensure_node, ensure_connection, etc.) into the namespace.

        Args:
            code: Python source code to execute. Set a `result` variable for return value.
            timeout: Max seconds to wait (default 120, use RENDER_TIMEOUT for renders).

        Returns:
            The value of `result` from the executed code, or None.

        Raises:
            SynapseExecutionError: If the code throws an exception (scene is auto-rolled-back).
        """
        response = await self._send_and_receive(
            {"tool": "houdini_execute_python", "code": code},
            timeout=timeout
        )

        # Handle Synapse response format
        if isinstance(response, dict):
            if response.get("error"):
                raise SynapseExecutionError(
                    response.get("error", "Unknown execution error"),
                    partial_result=response.get("result")
                )
            return response.get("result")
        return response

    async def capture_viewport(self, output_path: Optional[str] = None) -> str:
        """
        Capture a viewport screenshot.

        Args:
            output_path: Where to save. Defaults to .synapse/viewport_capture.png

        Returns:
            Path to the saved screenshot.
        """
        msg = {"tool": "houdini_capture_viewport"}
        if output_path:
            msg["output_path"] = output_path
        response = await self._send_and_receive(msg, timeout=30.0)
        return response

    # --- Convenience Methods ---

    async def execute_read(self, code: str) -> Any:
        """Execute read-only code (no mutations). Same as execute_python but semantic."""
        return await self.execute_python(code)

    async def execute_render(self, code: str) -> Any:
        """Execute render-triggering code with extended timeout."""
        return await self.execute_python(code, timeout=RENDER_TIMEOUT)
```

### `requirements.txt`

```
claude-agent-sdk>=0.1.30
websockets>=12.0
anyio>=4.0
```

---

## 5. Phase 1: Custom Tools

### `synapse_tools.py`

Custom tools registered with `ClaudeSDKClient`. These are what Opus 4.6 calls
during the agent loop. Each tool is an in-process MCP server — no separate process needed.

**Design Principles:**
- Each tool does ONE thing clearly
- Read tools are separate from mutation tools
- Every mutation tool returns verification data
- Tool docstrings are written in coaching tone (these become tool descriptions in the LLM context)

```python
"""
synapse_tools.py — Custom tools for the Synapse Agent.

These tools are registered with ClaudeSDKClient and become available
to Opus 4.6 during the agent loop. They wrap WebSocket calls to Synapse
running inside Houdini 21.

Tool docstrings are important — they appear in the LLM context and shape
how the agent describes operations to the artist.
"""

import json
import logging
from typing import Optional
from synapse_ws import SynapseClient, SynapseExecutionError

logger = logging.getLogger("synapse.tools")

# Global client instance — initialized in synapse_agent.py
_client: Optional[SynapseClient] = None


def set_client(client: SynapseClient):
    """Set the shared WebSocket client. Called once during agent init."""
    global _client
    _client = client


def get_client() -> SynapseClient:
    if _client is None:
        raise RuntimeError("Synapse client not initialized. Call set_client() first.")
    return _client


# ─────────────────────────────────────────────────────────────
# CONNECTIVITY
# ─────────────────────────────────────────────────────────────

async def synapse_ping() -> str:
    """
    Check if Synapse and Houdini are reachable.
    Call this first to verify the connection before doing any scene work.
    Returns protocol version and connection status.
    """
    client = get_client()
    try:
        result = await client.ping()
        return json.dumps({"status": "connected", "details": result})
    except Exception as e:
        return json.dumps({
            "status": "disconnected",
            "message": f"Can't reach Synapse — {e}. Is Houdini running?"
        })


async def synapse_scene_info() -> str:
    """
    Get an overview of the current Houdini scene.
    Returns the HIP file path, current frame, frame range, and FPS.
    Good for orientation — call this early to understand what we're working with.
    """
    client = get_client()
    result = await client.scene_info()
    return json.dumps(result, indent=2)


# ─────────────────────────────────────────────────────────────
# SCENE INTROSPECTION (READ-ONLY — safe to call anytime)
# ─────────────────────────────────────────────────────────────

async def synapse_inspect_scene(
    root_path: str = "/",
    max_depth: int = 3,
    context_filter: str = ""
) -> str:
    """
    Walk the Houdini scene graph and return a structured overview.
    Shows network topology, node counts, flagged nodes, errors, and warnings.
    This is a quick orientation tool — not a full parameter dump.

    Use this when you need to understand what's in the scene before making changes.

    Args:
        root_path: Where to start walking (default "/" for everything).
        max_depth: How deep to recurse (default 3).
        context_filter: Limit to a specific context like "Lop" or "Sop" (empty = all).
    """
    client = get_client()
    code = f'''
import hou
import json
from collections import defaultdict

def inspect_network(parent, depth=0, max_depth={max_depth}, context_filter="{context_filter}"):
    if depth > max_depth:
        return None

    children = parent.children()
    if not children:
        return None

    network = {{
        "path": parent.path(),
        "node_count": len(children),
        "types": defaultdict(int),
        "flagged": [],
        "issues": [],
        "children": []
    }}

    for node in children:
        cat = node.type().category().name()
        if context_filter and cat.lower() != context_filter.lower():
            continue

        network["types"][node.type().name()] += 1

        # Check flags
        flags = []
        try:
            if node.isDisplayFlagSet(): flags.append("display")
        except: pass
        try:
            if node.isRenderFlagSet(): flags.append("render")
        except: pass
        try:
            if node.isBypassed(): flags.append("bypass")
        except: pass
        if flags:
            network["flagged"].append({{"path": node.path(), "flags": flags}})

        # Check issues
        errors = node.errors()
        warnings = node.warnings()
        if errors:
            network["issues"].append({{"path": node.path(), "errors": errors}})
        if warnings:
            network["issues"].append({{"path": node.path(), "warnings": warnings}})

        # Recurse
        child_network = inspect_network(node, depth + 1, max_depth, context_filter)
        if child_network:
            network["children"].append(child_network)

    network["types"] = dict(network["types"])
    return network

root = hou.node("{root_path}")
if root:
    result = json.dumps(inspect_network(root), indent=2)
else:
    result = json.dumps({{"error": "Root path not found", "path": "{root_path}"}})
'''
    return await client.execute_read(code)


async def synapse_inspect_selection(depth: int = 1) -> str:
    """
    Analyze all currently selected nodes in Houdini.
    Returns detailed info: paths, types, modified parameters, connections,
    geometry attributes (for SOPs), errors, and warnings.

    Use this when the artist says "look at what I have selected" or when you
    need to understand the current working context.

    Args:
        depth: How many levels of input nodes to also inspect (default 1).
    """
    client = get_client()
    code = f'''
import hou
import json

def inspect_node(node, depth=0, max_depth={depth}):
    data = {{
        "path": node.path(),
        "type": node.type().name(),
        "category": node.type().category().name(),
        "modified_parms": {{}},
        "inputs": [],
        "outputs": [],
        "errors": node.errors(),
        "warnings": node.warnings()
    }}

    # Modified parameters only (skip defaults)
    for p in node.parms():
        try:
            if not p.isAtDefault():
                val = p.eval()
                # Handle non-serializable types
                if isinstance(val, (hou.Vector3, hou.Vector4)):
                    val = list(val)
                elif isinstance(val, hou.Matrix4):
                    val = str(val)
                data["modified_parms"][p.name()] = val
        except:
            pass

    # Connections
    for i, inp in enumerate(node.inputs()):
        if inp:
            data["inputs"].append({{"index": i, "path": inp.path(), "type": inp.type().name()}})
    for out in node.outputs():
        data["outputs"].append({{"path": out.path(), "type": out.type().name()}})

    # Geometry attributes (SOP context)
    if node.type().category().name() == "Sop":
        try:
            geo = node.geometry()
            if geo:
                data["geometry"] = {{
                    "points": geo.intrinsicValue("pointcount"),
                    "prims": geo.intrinsicValue("primitivecount"),
                    "attribs": {{}}
                }}
                for context, method in [("point", geo.pointAttribs),
                                         ("prim", geo.primAttribs),
                                         ("vertex", geo.vertexAttribs),
                                         ("detail", geo.globalAttribs)]:
                    data["geometry"]["attribs"][context] = [
                        {{"name": a.name(), "type": str(a.dataType()), "size": a.size()}}
                        for a in method()
                    ]
        except:
            pass

    # Recurse into inputs
    if depth < max_depth:
        data["input_nodes"] = []
        for inp in node.inputs():
            if inp:
                data["input_nodes"].append(inspect_node(inp, depth + 1, max_depth))

    return data

selected = hou.selectedNodes()
if not selected:
    result = json.dumps({{"message": "No nodes selected — select some nodes in Houdini and try again", "count": 0}})
else:
    nodes_data = [inspect_node(n) for n in selected]
    result = json.dumps({{
        "count": len(nodes_data),
        "nodes": nodes_data
    }}, indent=2)
'''
    return await client.execute_read(code)


async def synapse_inspect_node(
    node_path: str,
    include_code: bool = True,
    include_geometry: bool = True,
    include_expressions: bool = True
) -> str:
    """
    Deep inspection of a single node — gets EVERYTHING.
    All parameters (including defaults), expressions, code content for wrangles,
    geometry attributes with value ranges, HDA info, and cook dependencies.

    Use this when you need to fully understand one specific node before modifying it.

    Args:
        node_path: Absolute path to the node (e.g., "/stage/key_light").
        include_code: Include VEX/Python code from wrangle nodes (default true).
        include_geometry: Include geometry attribute summary (default true).
        include_expressions: Include parameter expressions and references (default true).
    """
    client = get_client()
    code = f'''
import hou
import json

node = hou.node("{node_path}")
if not node:
    result = json.dumps({{"error": "Node not found", "path": "{node_path}",
        "hint": "Check the path — try synapse_inspect_scene to see what's available"}})
else:
    data = {{
        "path": node.path(),
        "type": node.type().name(),
        "category": node.type().category().name(),
        "label": node.type().description(),
        "parameters": {{}},
        "inputs": [],
        "outputs": [],
        "flags": {{}},
        "errors": node.errors(),
        "warnings": node.warnings(),
        "cook_time": None
    }}

    # All parameters grouped by folder
    for parm_tuple in node.parmTuples():
        folder = parm_tuple.containingFolders()
        folder_key = " > ".join(folder) if folder else "Main"
        if folder_key not in data["parameters"]:
            data["parameters"][folder_key] = {{}}
        for p in parm_tuple:
            parm_data = {{
                "value": None,
                "is_default": p.isAtDefault(),
            }}
            try:
                parm_data["value"] = p.eval()
                if isinstance(parm_data["value"], (hou.Vector3, hou.Vector4)):
                    parm_data["value"] = list(parm_data["value"])
            except:
                parm_data["value"] = "<unevaluable>"

            if {str(include_expressions).lower()}:
                try:
                    expr = p.expression()
                    if expr:
                        parm_data["expression"] = expr
                        parm_data["expression_language"] = str(p.expressionLanguage())
                except:
                    pass
                # Channel references
                try:
                    ref = p.getReferencedParm()
                    if ref and ref != p:
                        parm_data["references"] = ref.path()
                except:
                    pass

            data["parameters"][folder_key][p.name()] = parm_data

    # Connections
    for i, inp in enumerate(node.inputs()):
        if inp:
            data["inputs"].append({{"index": i, "path": inp.path()}})
    for out in node.outputs():
        data["outputs"].append({{"path": out.path()}})

    # Flags
    try: data["flags"]["display"] = node.isDisplayFlagSet()
    except: pass
    try: data["flags"]["render"] = node.isRenderFlagSet()
    except: pass
    try: data["flags"]["bypass"] = node.isBypassed()
    except: pass

    # Code content (wrangles, python nodes)
    if {str(include_code).lower()}:
        for parm_name in ["snippet", "python", "code", "script", "vexcode"]:
            parm = node.parm(parm_name)
            if parm:
                try:
                    data["code_content"] = {{
                        "parameter": parm_name,
                        "code": parm.eval()
                    }}
                    break
                except:
                    pass

    # HDA info
    definition = node.type().definition()
    if definition:
        data["hda"] = {{
            "library_path": definition.libraryFilePath(),
            "embedded": definition.isEmbedded(),
            "sections": list(definition.sections().keys())[:10]
        }}

    # Geometry
    if {str(include_geometry).lower()} and node.type().category().name() == "Sop":
        try:
            geo = node.geometry()
            if geo:
                data["geometry"] = {{
                    "points": geo.intrinsicValue("pointcount"),
                    "prims": geo.intrinsicValue("primitivecount"),
                    "bounds": list(geo.boundingBox().minvec()) + list(geo.boundingBox().maxvec()),
                    "attribs": {{}}
                }}
                for ctx_name, method in [("point", geo.pointAttribs),
                                          ("prim", geo.primAttribs),
                                          ("vertex", geo.vertexAttribs),
                                          ("detail", geo.globalAttribs)]:
                    attribs = []
                    for a in method():
                        attr_data = {{"name": a.name(), "type": str(a.dataType()), "size": a.size()}}
                        # Sample first few values for numeric types
                        try:
                            if a.dataType() in (hou.attribData.Float, hou.attribData.Int):
                                if ctx_name == "point" and geo.intrinsicValue("pointcount") > 0:
                                    samples = [geo.point(i).attribValue(a) for i in range(min(3, geo.intrinsicValue("pointcount")))]
                                    attr_data["samples"] = samples
                        except:
                            pass
                        attribs.append(attr_data)
                    data["geometry"]["attribs"][ctx_name] = attribs
        except:
            pass

    # Cook time
    try:
        profile = node.cookProfile()
        if profile:
            data["cook_time"] = profile.cookTime()
    except:
        pass

    result = json.dumps(data, indent=2, default=str)
'''
    return await client.execute_read(code)


# ─────────────────────────────────────────────────────────────
# EXECUTION (MUTATIONS — these change the scene)
# ─────────────────────────────────────────────────────────────

async def synapse_execute(
    code: str,
    description: str = "",
    verify_paths: str = ""
) -> str:
    """
    Execute Python code in Houdini. Use this to create nodes, set parameters,
    connect wires, and modify the scene.

    SAFETY: The Synapse server automatically wraps all execution in an undo group.
    If anything fails, all changes are rolled back — the scene won't be left in a
    broken state.

    IMPORTANT CONVENTIONS:
    - One mutation per call. Don't create + connect + set parms in one script.
    - Use guard functions for idempotency: ensure_node(), ensure_connection(), ensure_parm()
    - These guards are auto-available in the namespace (no import needed).
    - Set a `result` variable to return data to the agent.

    Args:
        code: Python code to execute. Has access to `hou` module and guard functions.
        description: Human-readable description of what this operation does.
        verify_paths: Comma-separated node paths to verify after execution.

    When things go well, you'll get the result back. When they don't, you'll get a
    clear error explaining what happened and the scene will be rolled back to its
    previous state.
    """
    client = get_client()
    logger.info(f"Executing: {description or 'unlabeled operation'}")

    try:
        result = await client.execute_python(code)

        # If verify_paths provided, check they exist
        if verify_paths:
            paths = [p.strip() for p in verify_paths.split(",") if p.strip()]
            verify_code = f"""
import hou
import json
checks = {{}}
for path in {paths}:
    node = hou.node(path)
    checks[path] = {{
        "exists": node is not None,
        "type": node.type().name() if node else None,
        "errors": node.errors() if node else None
    }}
result = json.dumps(checks, indent=2)
"""
            verification = await client.execute_read(verify_code)
            return json.dumps({
                "executed": True,
                "result": result,
                "verification": json.loads(verification) if isinstance(verification, str) else verification,
                "description": description
            }, indent=2, default=str)

        return json.dumps({
            "executed": True,
            "result": result,
            "description": description
        }, indent=2, default=str)

    except SynapseExecutionError as e:
        return json.dumps({
            "executed": False,
            "error": str(e),
            "rolled_back": True,
            "description": description,
            "hint": "The scene was rolled back to its previous state. Check the code and try again."
        }, indent=2)


async def synapse_render_preview(
    rop_path: str = "/stage/karma_rop",
    output_path: str = "C:/Users/User/.synapse/renders/preview.exr",
    resolution_x: int = 512,
    resolution_y: int = 512,
    samples: int = 32
) -> str:
    """
    Trigger a quick render preview via Karma. Uses low resolution and samples
    for fast iteration. The rendered image is saved to disk for review.

    This is for rapid visual feedback during lighting/shading work — not final renders.

    Args:
        rop_path: Path to the Karma ROP node.
        output_path: Where to save the render.
        resolution_x: Width in pixels (default 512 for speed).
        resolution_y: Height in pixels (default 512 for speed).
        samples: Pixel samples (default 32 for speed, increase for quality).
    """
    client = get_client()
    code = f'''
import hou
import os

rop = hou.node("{rop_path}")
if not rop:
    result = "Karma ROP not found at {rop_path} — check the path"
else:
    # Ensure output directory exists
    os.makedirs(os.path.dirname(r"{output_path}"), exist_ok=True)

    # Set preview render settings
    # These use encoded USD parameter names for H21
    try:
        if rop.parm("resolutionx"): rop.parm("resolutionx").set({resolution_x})
        if rop.parm("resolutiony"): rop.parm("resolutiony").set({resolution_y})
    except:
        pass

    try:
        if rop.parm("picture"): rop.parm("picture").set(r"{output_path}")
    except:
        pass

    # Render
    try:
        rop.render()
        if os.path.exists(r"{output_path}"):
            size = os.path.getsize(r"{output_path}")
            result = f"Render complete — saved to {output_path} ({{size}} bytes)"
        else:
            result = "Render ran but output file wasn't created — check Karma settings"
    except Exception as e:
        result = f"Render encountered an issue: {{e}}"
'''
    return await client.execute_render(code)


# ─────────────────────────────────────────────────────────────
# TOOL REGISTRY — maps tool names to functions for ClaudeSDKClient
# ─────────────────────────────────────────────────────────────

TOOL_REGISTRY = {
    "synapse_ping": synapse_ping,
    "synapse_scene_info": synapse_scene_info,
    "synapse_inspect_scene": synapse_inspect_scene,
    "synapse_inspect_selection": synapse_inspect_selection,
    "synapse_inspect_node": synapse_inspect_node,
    "synapse_execute": synapse_execute,
    "synapse_render_preview": synapse_render_preview,
}
```

---

## 6. Phase 2: Safety Hooks

### `synapse_hooks.py`

Hooks fire on agent lifecycle events. These implement the three safety layers
at the agent level (complementing the server-side undo-group).

```python
"""
synapse_hooks.py — Safety and verification hooks for the Synapse Agent.

These hooks fire automatically during the agent loop:
- pre_tool_call: Validates tool calls before execution
- post_tool_call: Auto-verifies mutations after execution
- on_error: Enriches error messages with coaching tone and suggestions

The hooks complement the server-side safety (undo groups, guards.py) with
agent-side intelligence.
"""

import json
import logging
import re
from typing import Any, Optional
from synapse_tone import enrich_error_message, format_success_message

logger = logging.getLogger("synapse.hooks")


# ─────────────────────────────────────────────────────────────
# PRE-EXECUTION VALIDATION
# ─────────────────────────────────────────────────────────────

def validate_atomic_convention(code: str) -> tuple[bool, str]:
    """
    Check if a code block follows the atomic convention (one mutation per call).

    Heuristic: count mutation keywords. If >1 distinct mutation type, flag it.
    This is advisory — doesn't block execution, but warns the agent.
    """
    mutation_patterns = [
        (r'\.createNode\(', 'node creation'),
        (r'\.setInput\(', 'connection'),
        (r'\.set\(', 'parameter set'),  # parm.set()
        (r'\.destroy\(', 'node deletion'),
        (r'\.move\(', 'node move'),
    ]

    found_mutations = set()
    for pattern, label in mutation_patterns:
        if re.search(pattern, code):
            found_mutations.add(label)

    if len(found_mutations) > 1:
        return False, (
            f"This script has multiple mutation types ({', '.join(found_mutations)}). "
            f"For safety, split into separate calls — one mutation per execute. "
            f"Read operations can stay combined."
        )

    return True, "Looks good — single mutation type."


def validate_guard_usage(code: str) -> tuple[bool, str]:
    """
    Check if mutations use guard functions for idempotency.
    Advisory — encourages but doesn't block.
    """
    has_raw_create = bool(re.search(r'\.createNode\(', code))
    has_guard_create = bool(re.search(r'ensure_node\(', code))

    has_raw_connect = bool(re.search(r'\.setInput\(', code))
    has_guard_connect = bool(re.search(r'ensure_connection\(', code))

    warnings = []
    if has_raw_create and not has_guard_create:
        warnings.append(
            "Using raw createNode() — consider ensure_node() to prevent duplicates on retry."
        )
    if has_raw_connect and not has_guard_connect:
        warnings.append(
            "Using raw setInput() — consider ensure_connection() to prevent duplicate wiring."
        )

    if warnings:
        return False, " ".join(warnings)
    return True, "Guard functions used appropriately."


# ─────────────────────────────────────────────────────────────
# HOOK FUNCTIONS (for ClaudeSDKClient registration)
# ─────────────────────────────────────────────────────────────

async def pre_tool_call_hook(tool_name: str, tool_input: dict) -> Optional[str]:
    """
    Called before each tool invocation. Returns None to proceed, or a string
    message that gets injected into the agent's context as a warning.
    """
    if tool_name == "synapse_execute":
        code = tool_input.get("code", "")

        # Check atomic convention
        is_atomic, atomic_msg = validate_atomic_convention(code)
        if not is_atomic:
            logger.warning(f"Atomic convention violation: {atomic_msg}")
            return f"⚠️ Safety note: {atomic_msg}"

        # Check guard usage
        uses_guards, guard_msg = validate_guard_usage(code)
        if not uses_guards:
            logger.info(f"Guard suggestion: {guard_msg}")
            # Don't block, just log — guards are a best practice, not a hard rule

    return None  # Proceed normally


async def post_tool_call_hook(tool_name: str, tool_input: dict, tool_result: Any) -> Optional[str]:
    """
    Called after each tool invocation. Can inject follow-up context.
    Used here to auto-verify mutations.
    """
    if tool_name == "synapse_execute":
        try:
            result_data = json.loads(tool_result) if isinstance(tool_result, str) else tool_result
            if result_data.get("executed"):
                return format_success_message(
                    tool_input.get("description", "operation"),
                    result_data
                )
            elif result_data.get("error"):
                return enrich_error_message(
                    result_data.get("error", ""),
                    tool_input.get("code", "")
                )
        except (json.JSONDecodeError, AttributeError):
            pass

    return None


async def on_error_hook(error: Exception) -> Optional[str]:
    """
    Called when an unhandled error occurs. Enriches error messages
    with coaching tone and recovery suggestions.
    """
    error_msg = str(error)
    return enrich_error_message(error_msg, "")
```

### `synapse_tone.py`

The coaching language formatter used by hooks and tools.

```python
"""
synapse_tone.py — Coaching language for Synapse communications.

Every message the artist sees should pass the validation test:
"Would this message make an artist having a rough day want to keep going
 or close the application?"

Principles:
1. Never blame — "I couldn't find" not "you gave wrong path"
2. Plain language first — technical details can follow
3. Always offer a next step — every error suggests what to try
4. "We/I" framing — collaborative, not diagnostic
5. Forward momentum — success messages imply "what's next"
"""

import re
from typing import Any


def enrich_error_message(error: str, code: str) -> str:
    """
    Transform a raw error into coaching language with suggestions.
    """
    enriched = error

    # Node not found
    if "not found" in error.lower() or "none" in error.lower():
        path_match = re.search(r"['\"]?(/[a-zA-Z0-9_/]+)['\"]?", error)
        if path_match:
            path = path_match.group(1)
            enriched = (
                f"Couldn't find a node at `{path}` — it might have been renamed or "
                f"might not exist yet. I can search the scene to find the right path."
            )
        else:
            enriched = (
                f"Something I expected to find wasn't there. Let me inspect the "
                f"scene to get re-oriented."
            )

    # Parameter errors
    elif "parameter" in error.lower() or "parm" in error.lower():
        enriched = (
            f"Hit a parameter issue: {error}. H21 USD nodes use encoded parameter names "
            f"(like `xn__inputsintensity_i0a` instead of `intensity`). "
            f"I can inspect the node to find the exact parameter names."
        )

    # Permission / path errors
    elif "permission" in error.lower() or "writable" in error.lower():
        enriched = (
            f"Couldn't write to the output path — might be a permissions issue. "
            f"I'll try using C:/Users/User/.synapse/ instead."
        )

    # Type errors
    elif "NoneType" in error or "AttributeError" in error:
        enriched = (
            f"Something I expected to exist wasn't there yet — likely a node or "
            f"parameter that wasn't created in a previous step. Let me check "
            f"the scene state and try a different approach."
        )

    # Generic fallback
    elif not any(phrase in enriched for phrase in ["I can", "I'll", "Let me"]):
        enriched = f"{error}. Let me take a different approach."

    return f"🔧 {enriched}"


def format_success_message(description: str, result_data: Any) -> str:
    """
    Format a success result with forward momentum.
    """
    result = result_data.get("result", "")
    verification = result_data.get("verification", {})

    parts = [f"✓ {description} — done."]

    if verification:
        all_ok = all(v.get("exists", False) for v in verification.values())
        error_count = sum(1 for v in verification.values() if v.get("errors"))
        if all_ok and error_count == 0:
            parts.append("Verified — everything checks out.")
        elif not all_ok:
            missing = [k for k, v in verification.items() if not v.get("exists")]
            parts.append(f"Heads up: {', '.join(missing)} didn't make it. Let me investigate.")

    return " ".join(parts)
```

---

## 7. Phase 3: Agent Entry Point

### `synapse_agent.py`

The main script that Claude Code executes. This wires everything together
and starts the agent loop.

```python
"""
synapse_agent.py — Synapse VFX Co-Pilot Agent

Entry point for the Claude Agent SDK. Connects to Houdini via Synapse,
registers custom tools and safety hooks, then starts an autonomous agent
loop that can inspect, execute, verify, and iterate on VFX tasks.

USAGE (from Claude Code):
    cd C:/Users/User/.synapse/agent
    python synapse_agent.py "Set up three-point lighting for the cave scene"

Or from Claude Code directly:
    "Read C:/Users/User/.synapse/agent/CLAUDE.md, then run synapse_agent.py
     with the goal: set up dramatic top lighting with blue rim accents"
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            Path(__file__).parent / "logs" / "agent.log",
            mode='a'
        )
    ]
)
logger = logging.getLogger("synapse.agent")


async def run_agent(goal: str):
    """
    Initialize Synapse connection, register tools and hooks, and run the agent.
    """
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    from synapse_ws import SynapseClient
    from synapse_tools import (
        set_client,
        synapse_ping,
        synapse_scene_info,
        synapse_inspect_scene,
        synapse_inspect_selection,
        synapse_inspect_node,
        synapse_execute,
        synapse_render_preview,
    )
    from synapse_hooks import pre_tool_call_hook, post_tool_call_hook

    # --- Step 1: Connect to Houdini ---
    logger.info("Connecting to Synapse...")
    synapse = SynapseClient()
    await synapse.connect()
    set_client(synapse)

    # Verify connection
    ping_result = await synapse.ping()
    logger.info(f"Synapse connected: {ping_result}")

    scene = await synapse.scene_info()
    logger.info(f"Scene: {scene}")

    # --- Step 2: Create Agent ---
    client = ClaudeSDKClient()

    # Register custom tools
    # Each tool gets the @client.tool() decorator equivalent
    client.register_tool(
        name="synapse_ping",
        description="Check if Synapse and Houdini are reachable. Call first to verify connection.",
        func=synapse_ping
    )

    client.register_tool(
        name="synapse_scene_info",
        description="Get current Houdini scene overview — HIP file, frame range, FPS.",
        func=synapse_scene_info
    )

    client.register_tool(
        name="synapse_inspect_scene",
        description=(
            "Walk the Houdini scene graph and return topology overview. "
            "Shows node counts, types, flags, errors, warnings. "
            "Use this to orient yourself before making changes."
        ),
        func=synapse_inspect_scene
    )

    client.register_tool(
        name="synapse_inspect_selection",
        description=(
            "Analyze currently selected nodes in Houdini. "
            "Returns paths, types, modified parameters, connections, "
            "geometry attributes, errors, warnings."
        ),
        func=synapse_inspect_selection
    )

    client.register_tool(
        name="synapse_inspect_node",
        description=(
            "Deep-inspect a single node — ALL parameters, expressions, "
            "code content, geometry, HDA info, cook time. "
            "The 'tell me everything' tool for understanding one node."
        ),
        func=synapse_inspect_node
    )

    client.register_tool(
        name="synapse_execute",
        description=(
            "Execute Python code in Houdini. Creates nodes, sets parameters, "
            "connects wires. Auto-wrapped in undo group for safety. "
            "ONE mutation per call. Use guard functions (ensure_node, etc.) "
            "for idempotency. Set `result` variable to return data."
        ),
        func=synapse_execute
    )

    client.register_tool(
        name="synapse_render_preview",
        description=(
            "Trigger a quick Karma render preview. Low-res by default for "
            "fast iteration. Saves to disk for review."
        ),
        func=synapse_render_preview
    )

    # --- Step 3: Configure Agent Options ---
    agent_dir = Path(__file__).parent

    options = ClaudeAgentOptions(
        # Use all registered custom tools + filesystem tools for reading specs
        allowed_tools=[
            "synapse_ping",
            "synapse_scene_info",
            "synapse_inspect_scene",
            "synapse_inspect_selection",
            "synapse_inspect_node",
            "synapse_execute",
            "synapse_render_preview",
            "Read",       # Read files (specs, CLAUDE.md)
            "Glob",       # Find files
        ],
        # System prompt points to CLAUDE.md for full personality/conventions
        system_prompt=(
            "You are the Synapse VFX Co-Pilot — an AI assistant embedded in a "
            "professional VFX artist's Houdini workflow. You have direct access to "
            "their live Houdini scene via custom tools. Your communication style "
            "is that of a supportive senior artist — encouraging, specific, and "
            "forward-looking. Never blame. Always suggest next steps.\n\n"
            "WORKFLOW: Inspect scene → Plan approach → Execute (one mutation at a time) "
            "→ Verify result → Iterate until goal is met.\n\n"
            "SAFETY: Every execute call is wrapped in an undo group. If something fails, "
            "the scene rolls back. Use guard functions (ensure_node, ensure_connection, "
            "ensure_parm) for idempotent operations.\n\n"
            f"Read {agent_dir / 'CLAUDE.md'} for full conventions and personality guide."
        ),
        cwd=str(agent_dir),
        # Auto-accept file reads (agent needs to read its own specs)
        permission_mode='acceptEdits',
    )

    # --- Step 4: Run the Agent Loop ---
    prompt = (
        f"GOAL: {goal}\n\n"
        f"SCENE CONTEXT: Connected to Synapse at ws://localhost:9999. "
        f"Scene info: {scene}\n\n"
        f"START by reading CLAUDE.md for your personality and conventions guide, "
        f"then inspect the scene to understand what you're working with. "
        f"Plan your approach, then execute step by step with verification."
    )

    logger.info(f"Starting agent with goal: {goal}")

    try:
        response = await client.send_message(prompt, options=options)

        # Process the full agent conversation
        if hasattr(response, 'content'):
            for block in response.content:
                if hasattr(block, 'text'):
                    print(block.text)

        logger.info("Agent completed successfully")

    except Exception as e:
        logger.error(f"Agent error: {e}")
        raise

    finally:
        await synapse.disconnect()
        logger.info("Disconnected from Synapse")


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python synapse_agent.py \"<goal>\"")
        print("Example: python synapse_agent.py \"Set up three-point lighting\"")
        sys.exit(1)

    goal = " ".join(sys.argv[1:])
    asyncio.run(run_agent(goal))


if __name__ == "__main__":
    main()
```

**IMPORTANT NOTE ON SDK API:** The `ClaudeSDKClient` API is evolving rapidly
(v0.1.33 as of Feb 7, 2026). The `register_tool()` method shown above is
conceptual — when implementing, Claude Code should:

1. Check the actual SDK API by reading `claude_agent_sdk/client.py` source
2. Use `@client.tool()` decorator if that's the current pattern
3. Or define tools via `ClaudeAgentOptions` if that's the pattern
4. Fall back to `query()` with custom tools dict if `ClaudeSDKClient` API differs

The tool functions themselves (in `synapse_tools.py`) are the stable part.
The registration mechanism may need adaptation to the current SDK version.

---

## 8. Phase 4: CLAUDE.md — Agent Personality

### `CLAUDE.md`

This file is automatically loaded by the Claude Agent SDK when the agent runs.
It defines who Synapse is, how it communicates, and what conventions it follows.

```markdown
# SYNAPSE — VFX Co-Pilot

## Identity

You are Synapse, a VFX co-pilot that works alongside professional artists
in SideFX Houdini 21. You have direct access to their live scene through
custom tools. You're not a chatbot — you're a creative collaborator with
the ability to inspect, build, and verify VFX work in real time.

## Voice & Tone

**You sound like a supportive senior artist who has the artist's back.**

### The Validation Test
Before sending any message, ask yourself:
> "Would this message make an artist having a rough day want to keep going
>  or close the application?"

If the answer isn't clearly "keep going," rewrite it.

### Communication Principles
- **Never blame.** "I couldn't find" not "you gave me a wrong path"
- **Plain language first.** Technical details can follow, not lead
- **Always offer a next step.** Every error should suggest what to try
- **"I/we" framing.** Collaborative, not diagnostic
- **Forward momentum.** Success messages imply "ready for the next thing"
- **Celebrate wins.** Even small ones. "Nice — that's looking solid."
- **Normalize difficulty.** "This is a tricky one" not "this is simple"

### Never Say
- "Error:" as a prefix (use context-specific language)
- "Invalid" (use "didn't match" or "unexpected")
- "Failed" alone (always add what we're doing about it)
- "You need to" (use "we can" or "try")
- "Obviously" or "simply" (nothing is obvious when you're stuck)

### Always Say
- "Let me check..." (before investigating)
- "That worked — " (on success, then what's next)
- "Heads up:" (for non-blocking warnings)
- "I'll try a different approach" (on failure recovery)
- "Nice." / "Clean." / "Looking good." (genuine micro-affirmations)

## Workflow Protocol

### The Agent Loop
1. **Orient** — Inspect the scene before touching anything
2. **Plan** — Think through the approach (use extended thinking)
3. **Execute** — One mutation per call, always
4. **Verify** — Inspect the result of every mutation
5. **Iterate** — If verification fails, adjust and retry
6. **Report** — Tell the artist what was done and what's next

### Safety Rules (Non-Negotiable)
1. **Atomic:** ONE mutation per `synapse_execute` call. Never combine
   node creation + connection + parameter setting in one script.
2. **Idempotent:** Use guard functions for every mutation:
   - `ensure_node(parent_path, node_type, node_name)` — creates only if missing
   - `ensure_connection(source_path, target_path, target_input)` — connects only if not already
   - `ensure_parm(node_path, parm_name, value)` — sets only if different
   - `ensure_node_deleted(path)` — deletes only if exists
3. **Verified:** After every mutation, inspect the result. Don't assume success.
4. **Recoverable:** If something goes wrong, the undo group rolls back.
   Tell the artist what happened and what you'll try instead.

### Read Operations (Safe, Combine Freely)
- `synapse_inspect_scene` — get the lay of the land
- `synapse_inspect_selection` — understand what the artist is looking at
- `synapse_inspect_node` — deep-dive on a single node
- `synapse_scene_info` — basic scene metadata
- These never modify the scene. Call them as often as needed.

## Houdini 21 Conventions

### Scene Graph
- USD/Solaris nodes live at `/stage/`
- OBJ-level geometry at `/obj/`
- Render outputs at `/out/`
- Connections flow through merge nodes (e.g., `/stage/scene_merge`)

### USD Light Parameters (CRITICAL)
H21 USD light nodes use **encoded parameter names**, not human-readable ones:
- Intensity: `xn__inputsintensity_i0a` (not `intensity`)
- Color: `xn__inputscolor_vya` (not `color`)
- Exposure: `xn__inputsexposure_f1a` (not `exposure`)

**When in doubt, inspect the node first** using `synapse_inspect_node` to see
exact parameter names. This is the #1 source of errors.

### Node Type Names
Common USD node types in Solaris/LOPs:
- `distantlight::2.0` — directional light
- `domelight::2.0` — environment/dome light
- `rectlight::2.0` — rectangular area light
- `spherelight::2.0` — point/sphere light
- `materiallibrary` — MaterialX material container
- `karmarendersettings` — Karma render configuration
- `merge` — combines multiple LOP inputs

### MaterialX Shading
- Surface shader: `mtlxstandard_surface`
- Use `materiallibrary` node to contain shading networks
- Bind materials via `materialbindings` LOP

### Karma Rendering
- ROP node: typically at `/stage/karma_rop` or `/out/karma`
- Supports CPU and XPU (GPU) backends
- Preview renders: 512x512, 32 samples for speed
- Final renders: scene resolution, 128+ samples

### File Paths
- Synapse home: `C:/Users/User/.synapse/`
- Render output: `C:/Users/User/.synapse/renders/`
- Houdini projects: `D:/HOUDINI_PROJECTS_2025/`
- Use forward slashes in Houdini Python, or raw strings with backslashes

## Error Recovery Patterns

### "Node not found"
→ Inspect the scene. The node may have been renamed or may not exist yet.
   Check the path, search for similar names.

### "Parameter doesn't exist"
→ Encoded parameter name issue. Inspect the node to get exact parameter names.
   H21 USD parameters use `xn__` prefix encoding.

### "Duplicate inputs on merge node"
→ Idempotent guard wasn't used. Use `ensure_connection()` which checks
   existing connections before wiring.

### "Render produced no output"
→ Check: Is the output path writable? Is the camera set? Is there geometry
   in the scene? Inspect the ROP node for configuration issues.

### "Script partially executed"
→ The undo group should have rolled back. Verify by inspecting the scene.
   If partial state persists, investigate the undo system.
```

### `.claude/settings.json`

```json
{
  "permissions": {
    "allow": [
      "Read(*)",
      "Glob(*)",
      "synapse_ping",
      "synapse_scene_info",
      "synapse_inspect_scene",
      "synapse_inspect_selection",
      "synapse_inspect_node",
      "synapse_execute",
      "synapse_render_preview"
    ]
  }
}
```

---

## 9. Phase 5: Skills — Reusable VFX Recipes

### `.claude/skills/three_point_lighting.md`

```markdown
# Skill: Three-Point Lighting Setup

## When to Use
When the artist asks for a lighting rig, standard lighting, or three-point setup.

## Steps
1. Inspect the scene to find existing lights and the main subject
2. Create or configure a KEY light (warm, main illumination, 45° above-right)
3. Create or configure a FILL light (cool, softer, from the left)
4. Create or configure a RIM/BACK light (accent, behind the subject)
5. Wire all lights into the scene merge
6. Verify each light exists and has correct parameters
7. Offer a preview render

## Parameter Guidelines
- Key: warm (2800-4000K equivalent), intensity 1.0-2.0
- Fill: cool (6500-8000K equivalent), intensity 0.3-0.5
- Rim: accent color matching scene mood, intensity 0.6-1.0

## H21 Notes
- Use `distantlight::2.0` for key and rim
- Use `rectlight::2.0` for fill (softer falloff)
- Or `domelight::2.0` for ambient fill
- Parameter names are encoded: inspect nodes to confirm exact names
```

### `.claude/skills/karma_render_preview.md`

```markdown
# Skill: Karma Render Preview

## When to Use
When the artist wants to see a quick render of the current scene state.

## Steps
1. Find the Karma ROP (typically /stage/karma_rop or /out/karma)
2. If no ROP exists, create one
3. Set preview resolution (512x512)
4. Set low samples (32) for speed
5. Set output path to C:/Users/User/.synapse/renders/preview.exr
6. Trigger render
7. Report completion and file path

## Iteration Pattern
If the artist wants adjustments:
1. Adjust the scene (lights, materials, camera)
2. Re-render preview
3. Compare results
4. Repeat until satisfied
5. Offer final render at full resolution
```

### `.claude/skills/scene_health_check.md`

```markdown
# Skill: Scene Health Check

## When to Use
When the artist asks for a diagnostic, or when starting work on an unfamiliar scene.

## Steps
1. Inspect full scene graph at max_depth=3
2. Check for: nodes with errors, nodes with warnings, unconnected inputs,
   deprecated node types, bypass flags that might be accidental
3. Report findings in priority order:
   - 🔴 Errors (blocking)
   - 🟡 Warnings (may affect output)
   - 🔵 Suggestions (optimization)
4. Offer to fix issues that have clear solutions

## Report Format
Keep it scannable:
- Lead with the headline: "Scene looks healthy" or "Found 3 issues to look at"
- Group by severity
- Each issue: what, where, suggested fix
```

---

## 10. Phase 6: Test Protocol

Execute these tests in order. Each must pass before proceeding.

### Test 0: Dependencies
```bash
cd C:/Users/User/.synapse/agent
pip install -r requirements.txt
python -c "from claude_agent_sdk import ClaudeSDKClient; print('SDK OK')"
python -c "import websockets; print('WebSocket OK')"
```

### Test 1: WebSocket Connection
```python
# test_connection.py
import asyncio
from synapse_ws import SynapseClient

async def test():
    async with SynapseClient() as client:
        result = await client.ping()
        print(f"Ping: {result}")
        scene = await client.scene_info()
        print(f"Scene: {scene}")
        print("✓ Connection test passed")

asyncio.run(test())
```
**Expected:** Protocol version returned, scene info returned.

### Test 2: Read Operations
```python
# test_reads.py
import asyncio
from synapse_ws import SynapseClient
from synapse_tools import set_client, synapse_inspect_scene, synapse_inspect_selection

async def test():
    async with SynapseClient() as client:
        set_client(client)
        scene = await synapse_inspect_scene(root_path="/stage", max_depth=2)
        print(f"Scene inspection:\n{scene[:500]}...")
        print("✓ Read operations test passed")

asyncio.run(test())
```
**Expected:** JSON with node counts, types, and hierarchy.

### Test 3: Execute with Guards
```python
# test_execute.py
import asyncio
from synapse_ws import SynapseClient
from synapse_tools import set_client, synapse_execute

async def test():
    async with SynapseClient() as client:
        set_client(client)

        # Create with guard
        r1 = await synapse_execute(
            code="node = ensure_node('/stage', 'null', 'agent_test_null')\nresult = node.path()",
            description="Create test null node"
        )
        print(f"Create: {r1}")

        # Run again — should be idempotent
        r2 = await synapse_execute(
            code="node = ensure_node('/stage', 'null', 'agent_test_null')\nresult = node.path()",
            description="Create test null node (idempotent)"
        )
        print(f"Idempotent: {r2}")

        # Cleanup
        r3 = await synapse_execute(
            code="ensure_node_deleted('/stage/agent_test_null')\nresult = 'cleaned'",
            description="Clean up test node"
        )
        print(f"Cleanup: {r3}")
        print("✓ Execute test passed")

asyncio.run(test())
```
**Expected:** Same path both times, clean deletion.

### Test 4: Transaction Rollback
```python
# test_rollback.py
import asyncio
from synapse_ws import SynapseClient
from synapse_tools import set_client, synapse_execute, synapse_inspect_node

async def test():
    async with SynapseClient() as client:
        set_client(client)

        # Execute code that will error midway
        r = await synapse_execute(
            code="node = ensure_node('/stage', 'null', 'rollback_test')\nx = undefined_var",
            description="Test rollback on error"
        )
        print(f"Result: {r}")

        # Verify rollback — node should NOT exist
        check = await synapse_inspect_node("/stage/rollback_test")
        print(f"Node exists after rollback: {check}")
        print("✓ Rollback test passed (node should show 'not found')")

asyncio.run(test())
```
**Expected:** Error returned, node does NOT exist (undo rolled it back).

### Test 5: Full Agent Loop (Integration)
```bash
cd C:/Users/User/.synapse/agent
python synapse_agent.py "Inspect the current scene and tell me what you see"
```
**Expected:** Agent connects, reads CLAUDE.md, calls inspect_scene, reports findings.

---

## 11. Phase 7: Advanced Patterns

### Subagent: Parallel Scene Analysis
```python
# Use subagents for concurrent inspection tasks
# The agent can spin up subagents with isolated context:
# - Subagent A: Analyze lighting setup
# - Subagent B: Analyze material assignments
# - Subagent C: Check scene health
# Each returns a focused summary to the orchestrator
```

### Compaction: Long Render Sessions
```python
# For render iteration loops (configure → render → review → adjust),
# enable compaction in agent options:
# options.compact = True
# This auto-summarizes history when context gets long
```

### Recipe Runner Pattern
```python
# Agent reads a skill file → plans execution → adapts to current scene
# "Read the three_point_lighting skill, then set up lighting
#  adapted to what's currently in the scene"
```

### Desktop-to-Code Handoff Protocol
```
1. Artist works in Claude Desktop (has memory, conversation context)
2. Desktop generates a goal description with scene context
3. Artist copies goal to Claude Code
4. Claude Code runs: python synapse_agent.py "<goal>"
5. Agent executes autonomously
6. Results appear in Houdini
7. Artist evaluates visually
8. If adjustments needed, new goal → repeat
```

---

## 12. Consistency Checklist

Before executing, verify these match the existing Synapse codebase:

- [ ] WebSocket URI: `ws://localhost:9999` (confirmed in synapse_ws.py)
- [ ] Protocol version: v4.0.0 (confirmed in multiple sessions)
- [ ] Tool names match existing MCP tools: `synapse_ping`, `houdini_execute_python`
- [ ] Guard functions match guards.py: `ensure_node`, `ensure_connection`, `ensure_parm`,
      `ensure_node_deleted`, `node_exists`, `deduplicate_inputs`, `describe_inputs`
- [ ] H21 parameter encoding: `xn__` prefix pattern (confirmed in lighting sessions)
- [ ] File paths: `C:/Users/User/.synapse/` (confirmed across all sessions)
- [ ] Render output: `C:/Users/User/.synapse/renders/` (from roadmap)
- [ ] Houdini project path: `D:/HOUDINI_PROJECTS_2025/` (from scene info)
- [ ] Tone principles match TONE_IMPLEMENTATION.md (validated against all conversations)
- [ ] Safety protocol: atomic + idempotent + transaction (from SAFE_EXEC_SPEC.md)
- [ ] Karma ROP patterns: `/stage/karma_rop` or `/out/karma`
- [ ] USD light types: `distantlight::2.0`, `domelight::2.0`, `rectlight::2.0`

---

## 13. Execution Instructions for Claude Code

### Quick Start
```
Read C:/Users/User/.synapse/agent/CLAUDE.md for context.

Then:
1. cd C:/Users/User/.synapse/agent/
2. pip install -r requirements.txt
3. Read the existing Synapse server source at C:/Users/User/.synapse/
   to understand the WebSocket message format (the synapse_ws.py client
   must match what the server expects)
4. Adapt synapse_ws.py if the server's JSON message format differs from
   what's shown here
5. Run tests in order: test_connection → test_reads → test_execute →
   test_rollback → test_agent
6. Fix any issues before proceeding to the full agent
```

### Critical First Step
**Before writing any code, read the Synapse server source.** The WebSocket
message format in `synapse_ws.py` is based on the pattern observed in
conversations (e.g., `{"tool": "houdini_execute_python", "code": "..."}`),
but the actual server may use a different format. Adapt accordingly.

### SDK API Verification
The Claude Agent SDK is evolving rapidly. Before implementing `synapse_agent.py`:
1. Read `claude_agent_sdk/client.py` source to understand the current API
2. Check if `register_tool()` is the method, or if `@client.tool()` decorator is used
3. Check the `ClaudeAgentOptions` signature for current parameter names
4. Adapt the registration pattern to match the actual SDK version

### What Success Looks Like
```
$ python synapse_agent.py "Set up three-point lighting for this scene"

[synapse.agent] Connecting to Synapse...
[synapse.agent] Synapse connected: {"protocol": "4.0.0", ...}
[synapse.agent] Scene: synapse_demo_2026.hip
[synapse.agent] Starting agent with goal: Set up three-point lighting...

[Agent reads CLAUDE.md]
[Agent calls synapse_inspect_scene → understands current state]
[Agent plans: 3 lights needed, identifies merge node]
[Agent calls synapse_execute → creates key light with ensure_node]
[Agent calls synapse_inspect_node → verifies key light params]
[Agent calls synapse_execute → creates fill light with ensure_node]
[Agent calls synapse_inspect_node → verifies fill light params]
[Agent calls synapse_execute → creates rim light with ensure_node]
[Agent calls synapse_execute → wires all to merge with ensure_connection]
[Agent calls synapse_inspect_scene → final verification]
[Agent reports: "Three-point lighting is set up. Key at 45° warm,
 fill from left cool, rim accent from behind. Want a preview render?"]
```

The artist sees the lights appear in their Houdini viewport in real time.
The agent operated autonomously through the full inspect → plan → execute →
verify → report loop.

---

*Blueprint: Synapse Agent SDK v1.0*
*Origin: Claude Desktop Project (Synapse + VFX)*
*Target: Claude Code + Opus 4.6 Extended Thinking*
*Author: Joe (Creative Director) + Claude (Implementation Partner)*
