"""
synapse_tools.py — Tool definitions for the Synapse Agent.

These are registered as Anthropic API tools and called by Opus 4.6 during the
agent loop. Each tool wraps a WebSocket call to Synapse running inside Houdini.

Tool docstrings are used as tool descriptions in the LLM context.
"""

import json
import logging
from typing import Any

from synapse_ws import SynapseClient, SynapseExecutionError

logger = logging.getLogger("synapse.tools")

# Shared client instance — set once during agent init
_client: SynapseClient | None = None


def set_client(client: SynapseClient):
    """Set the shared WebSocket client. Called once during agent init."""
    global _client
    _client = client


def get_client() -> SynapseClient:
    if _client is None:
        raise RuntimeError("Synapse client not initialized. Call set_client() first.")
    return _client


# ─────────────────────────────────────────────────────────────
# Tool definitions as Anthropic API tool schemas
# ─────────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "synapse_ping",
        "description": (
            "Check if Synapse and Houdini are reachable. "
            "Call this first to verify the connection before doing any scene work. "
            "Returns protocol version and connection status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "synapse_scene_info",
        "description": (
            "Get an overview of the current Houdini scene. "
            "Returns the HIP file path, current frame, frame range, and FPS. "
            "Good for orientation — call this early to understand what we're working with."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "synapse_inspect_scene",
        "description": (
            "Walk the Houdini scene graph and return a structured overview. "
            "Shows network topology, node counts, flagged nodes, errors, and warnings. "
            "Use this when you need to understand what's in the scene before making changes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "root": {
                    "type": "string",
                    "description": "Where to start walking (default '/' for everything).",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "How deep to recurse (default 3).",
                },
                "context_filter": {
                    "type": "string",
                    "description": "Limit to a specific context like 'Lop' or 'Sop' (empty = all).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "synapse_inspect_selection",
        "description": (
            "Analyze all currently selected nodes in Houdini. "
            "Returns detailed info: paths, types, modified parameters, connections, "
            "geometry attributes (for SOPs), errors, and warnings. "
            "Use this when the artist says 'look at what I have selected'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "depth": {
                    "type": "integer",
                    "description": "How many levels of input nodes to also inspect (default 1).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "synapse_inspect_node",
        "description": (
            "Deep inspection of a single node — gets EVERYTHING. "
            "All parameters (grouped by folder), expressions, code content for wrangles, "
            "geometry attributes with value ranges, HDA info, and cook dependencies. "
            "Use this when you need to fully understand one specific node before modifying it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "node_path": {
                    "type": "string",
                    "description": "Absolute path to the node (e.g., '/stage/key_light').",
                },
                "include_code": {
                    "type": "boolean",
                    "description": "Include VEX/Python code from wrangle nodes (default true).",
                },
                "include_geometry": {
                    "type": "boolean",
                    "description": "Include geometry attribute summary (default true).",
                },
                "include_expressions": {
                    "type": "boolean",
                    "description": "Include parameter expressions and references (default true).",
                },
            },
            "required": ["node_path"],
        },
    },
    {
        "name": "synapse_execute",
        "description": (
            "Execute Python code in Houdini. Use this to create nodes, set parameters, "
            "connect wires, and modify the scene.\n\n"
            "SAFETY: The Synapse server automatically wraps all execution in an undo group. "
            "If anything fails, all changes are rolled back.\n\n"
            "IMPORTANT CONVENTIONS:\n"
            "- One mutation per call. Don't create + connect + set parms in one script.\n"
            "- Use guard functions for idempotency: ensure_node(), ensure_connection(), ensure_parm()\n"
            "- These guards are auto-available in the namespace (no import needed).\n"
            "- Set a `result` variable to return data to the agent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. Has access to `hou` module and guard functions.",
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable description of what this operation does.",
                },
                "verify_paths": {
                    "type": "string",
                    "description": "Comma-separated node paths to verify after execution.",
                },
            },
            "required": ["code"],
        },
    },
    {
        "name": "synapse_render_preview",
        "description": (
            "Trigger a render via Karma. Returns the rendered image path and metadata. "
            "Use this for rapid visual feedback during lighting/shading work."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "ROP node path (e.g. '/stage/karma1'). Auto-discovers if omitted.",
                },
                "width": {
                    "type": "integer",
                    "description": "Override resolution width in pixels.",
                },
                "height": {
                    "type": "integer",
                    "description": "Override resolution height in pixels.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "synapse_knowledge_lookup",
        "description": (
            "Look up Houdini knowledge: parameter names, node types, workflow guides. "
            "Uses the RAG index for fast, grounded answers. "
            "Use this before guessing parameter names or node types."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query (e.g. 'dome light intensity parameter').",
                },
            },
            "required": ["query"],
        },
    },
    # ─── Living Memory tools ───────────────────────────────────
    {
        "name": "synapse_project_setup",
        "description": (
            "Initialize the Living Memory structure for the current Houdini scene. "
            "Creates claude/ directories alongside the HIP file and project, seeds "
            "memory.md and agent.usd, and returns the full project context. "
            "Call this after synapse_ping to load prior session memory and pick up "
            "where we left off."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "synapse_memory_write",
        "description": (
            "Write an entry to the scene's Living Memory. Use this to persist "
            "decisions, parameter experiments, blockers, and session notes so "
            "they survive across sessions.\n\n"
            "Entry types: session_start, session_end, decision, "
            "parameter_experiment, blocker, blocker_resolved, note, "
            "asset_reference, wedge_result"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entry_type": {
                    "type": "string",
                    "description": "Type of entry to write.",
                    "enum": [
                        "session_start", "session_end", "decision",
                        "parameter_experiment", "blocker", "blocker_resolved",
                        "note", "asset_reference", "wedge_result",
                    ],
                },
                "content": {
                    "type": "object",
                    "description": (
                        "Entry content. Structure depends on entry_type:\n"
                        "- decision: {name, choice, reasoning, alternatives}\n"
                        "- parameter_experiment: {node, parm, before, after, result}\n"
                        "- blocker: {description, attempts}\n"
                        "- note: {content}\n"
                        "- session_start: {goal}\n"
                        "- session_end: {accomplishments, next_actions}"
                    ),
                },
                "scope": {
                    "type": "string",
                    "description": "Where to write: scene (default), project, or both.",
                    "enum": ["scene", "project", "both"],
                },
            },
            "required": ["entry_type", "content"],
        },
    },
    {
        "name": "synapse_memory_query",
        "description": (
            "Search Living Memory across scene, project, or all scenes in the project. "
            "Returns ranked results with relevance scores. Use this to recall past "
            "decisions, find what settings worked, or check for unresolved blockers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g., 'displacement settings', 'exposure values').",
                },
                "scope": {
                    "type": "string",
                    "description": "Search scope: scene, project, or all (default).",
                    "enum": ["scene", "project", "all"],
                },
                "type_filter": {
                    "type": "string",
                    "description": "Limit to specific entry type (decision, parameter, blocker, etc.).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "synapse_memory_status",
        "description": (
            "Get the current Living Memory system status — evolution stage "
            "(charmander/charmeleon/charizard), file sizes, session count, "
            "and agent task state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# ─────────────────────────────────────────────────────────────
# Tool execution functions
# ─────────────────────────────────────────────────────────────


async def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Execute a tool by name with the given input. Returns JSON string result.
    This is the single dispatch point called by the agent loop.
    """
    client = get_client()

    try:
        if tool_name == "synapse_ping":
            result = await client.ping()
            return json.dumps({"status": "connected", "details": result}, indent=2, default=str)

        elif tool_name == "synapse_scene_info":
            result = await client.scene_info()
            return json.dumps(result, indent=2, default=str)

        elif tool_name == "synapse_inspect_scene":
            result = await client.inspect_scene(
                root=tool_input.get("root", "/"),
                max_depth=tool_input.get("max_depth", 3),
                context_filter=tool_input.get("context_filter", ""),
            )
            return json.dumps(result, indent=2, default=str)

        elif tool_name == "synapse_inspect_selection":
            result = await client.inspect_selection(
                depth=tool_input.get("depth", 1),
            )
            return json.dumps(result, indent=2, default=str)

        elif tool_name == "synapse_inspect_node":
            result = await client.inspect_node(
                node=tool_input["node_path"],
                include_code=tool_input.get("include_code", True),
                include_geometry=tool_input.get("include_geometry", True),
                include_expressions=tool_input.get("include_expressions", True),
            )
            return json.dumps(result, indent=2, default=str)

        elif tool_name == "synapse_execute":
            return await _execute_with_verification(client, tool_input)

        elif tool_name == "synapse_render_preview":
            payload = {k: v for k, v in tool_input.items() if v is not None}
            result = await client.render(**payload)
            return json.dumps(result, indent=2, default=str)

        elif tool_name == "synapse_knowledge_lookup":
            result = await client.knowledge_lookup(tool_input["query"])
            return json.dumps(result, indent=2, default=str)

        # Living Memory tools
        elif tool_name == "synapse_project_setup":
            result = await client.project_setup()
            return json.dumps(result, indent=2, default=str)

        elif tool_name == "synapse_memory_write":
            result = await client.memory_write(
                entry_type=tool_input["entry_type"],
                content=tool_input.get("content", {}),
                scope=tool_input.get("scope", "scene"),
            )
            return json.dumps(result, indent=2, default=str)

        elif tool_name == "synapse_memory_query":
            result = await client.memory_query(
                query=tool_input["query"],
                scope=tool_input.get("scope", "all"),
                type_filter=tool_input.get("type_filter", ""),
            )
            return json.dumps(result, indent=2, default=str)

        elif tool_name == "synapse_memory_status":
            result = await client.memory_status()
            return json.dumps(result, indent=2, default=str)

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except SynapseExecutionError as e:
        return json.dumps(
            {
                "executed": False,
                "error": str(e),
                "rolled_back": True,
                "hint": "The scene was rolled back. Check the code and try again.",
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


async def _execute_with_verification(client: SynapseClient, tool_input: dict) -> str:
    """Execute Python code and optionally verify node paths after."""
    code = tool_input["code"]
    description = tool_input.get("description", "")

    logger.info("Executing: %s", description or "unlabeled operation")

    try:
        result = await client.execute_python(code)

        # Verification pass
        verify_paths_str = tool_input.get("verify_paths", "")
        if verify_paths_str:
            paths = [p.strip() for p in verify_paths_str.split(",") if p.strip()]
            verify_code = (
                "import hou, json\n"
                "checks = {}\n"
                f"for path in {paths}:\n"
                "    node = hou.node(path)\n"
                "    checks[path] = {\n"
                "        'exists': node is not None,\n"
                "        'type': node.type().name() if node else None,\n"
                "        'errors': node.errors() if node else None\n"
                "    }\n"
                "result = json.dumps(checks, indent=2)\n"
            )
            verification = await client.execute_python(verify_code)
            return json.dumps(
                {
                    "executed": True,
                    "result": result,
                    "verification": json.loads(verification) if isinstance(verification, str) else verification,
                    "description": description,
                },
                indent=2,
                default=str,
            )

        return json.dumps(
            {"executed": True, "result": result, "description": description},
            indent=2,
            default=str,
        )

    except SynapseExecutionError as e:
        return json.dumps(
            {
                "executed": False,
                "error": str(e),
                "rolled_back": True,
                "description": description,
                "hint": "The scene was rolled back to its previous state. Check the code and try again.",
            },
            indent=2,
        )
