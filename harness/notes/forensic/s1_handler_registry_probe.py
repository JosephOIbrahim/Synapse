"""S1 producer: instantiate the LIVE command-handler registry and cross-reference
it against the 120-entry canonical MCP tool registry.

Why this exists alongside s1_registry_xref.py: that script finds `reg.register(...)`
call sites with a regex and undercounts, because five `engram_*` handlers are
registered through a loop the regex cannot see. This script asks the registry
itself, so its numbers are the authoritative ones.

Pure Python. No `hou`, no Houdini process, no network. Read-only.

    python harness/notes/forensic/s1_handler_registry_probe.py

Writes harness/notes/forensic/s1_artifacts/handler_registry.json
"""
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "s1_artifacts", "handler_registry.json")
sys.path.insert(0, os.path.join(REPO, "python"))

import synapse.server.handlers as H           # noqa: E402
from synapse.mcp import _tool_registry as R   # noqa: E402

# Build the registry the way SynapseHandler does, without constructing a handler
# (which would want a live host). __new__ + the two attributes _register_handlers
# touches is enough, and it is the real method, not a reimplementation.
h = H.SynapseHandler.__new__(H.SynapseHandler)
h._registry = H.CommandHandlerRegistry()
h._register_handlers()

registered = set(h._registry._handlers)
tools = {name: cmd for name, cmd, *_ in R.TOOL_DEFS}

tools_without_handler = sorted(t for t, c in tools.items() if c not in registered)
handlers_without_tool = sorted(registered - set(tools.values()))

result = {
    "mcp_tools_in_canonical_registry": len(tools),
    "command_handlers_registered": len(registered),
    "mcp_tools_with_no_registered_handler": tools_without_handler,
    "registered_handlers_with_no_mcp_tool": handlers_without_tool,
    "pending_tool_names": R.PENDING_TOOL_NAMES,
    "note": ("A tool appearing here with a handler is NOT a claim that the tool "
             "works. It is the weakest possible clearance: a command_type that "
             "resolves. Reachability past this point is a source-and-probe "
             "question, which is what S1_INVENTORY.md answers."),
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=1)

print(f"MCP tools in canonical registry : {len(tools)}")
print(f"command handlers registered     : {len(registered)}")
print(f"tools with NO registered handler: {len(tools_without_handler)} {tools_without_handler}")
print(f"handlers with NO MCP tool       : {len(handlers_without_tool)}")
for c in handlers_without_tool:
    print(f"    {c}")
print("wrote", OUT)

# Stated failure condition (Law 1): this check FAILS if any registered MCP tool
# resolves to a command_type with no handler. It has been demonstrated to be
# able to fail -- delete any reg.register(...) line and re-run.
sys.exit(1 if tools_without_handler else 0)
