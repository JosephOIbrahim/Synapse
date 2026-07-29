"""S1 producer path — the UNREACHABLE test.

A registered MCP tool is REACHABLE only if the command_type it dispatches has a
handler registered on the live-path CommandRegistry. This walks the registration
sites statically (AST, so no hou import) and diffs the handler key set against
the command_type set the canonical tool registry emits.

Emits harness/notes/forensic/s1_reachability.json.

Law 1 — how this check fails: if any TOOL_DEFS command_type has no matching
reg.register("<type>", ...) call anywhere under python/synapse/server/, it lands
in `unreachable_command_types` and the tools that dispatch it are UNREACHABLE.
The positive control is the inverse list: handlers registered that no tool
reaches (dead handler surface), which proves the diff runs in both directions.
"""

import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "python"))

from synapse.mcp._tool_registry import TOOL_DEFS  # noqa: E402

SERVER = ROOT / "python" / "synapse" / "server"

# --- every reg.register("<cmd>", handler) site, statically ------------------
registered: dict[str, list[str]] = {}
register_sites = 0

for py in sorted(SERVER.rglob("*.py")):
    if "__pycache__" in py.parts:
        continue
    try:
        tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not isinstance(fn, ast.Attribute) or fn.attr != "register":
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            register_sites += 1
            rel = str(py.relative_to(ROOT)).replace("\\", "/")
            registered.setdefault(first.value, []).append(f"{rel}:{node.lineno}")

# --- what the tools ask for -------------------------------------------------
tool_cmd: dict[str, str] = {}
cmd_tools: dict[str, list[str]] = {}
for name, cmd_type, *_rest in TOOL_DEFS:
    tool_cmd[name] = cmd_type
    cmd_tools.setdefault(cmd_type, []).append(name)

wanted = set(cmd_tools)
have = set(registered)

unreachable_cmds = sorted(wanted - have)
dead_handlers = sorted(have - wanted)

unreachable_tools = sorted(t for t, c in tool_cmd.items() if c in set(unreachable_cmds))

out = {
    "producer": "harness/notes/forensic/_s1_reachability.py",
    "method": "AST walk of reg.register(<str>, ...) under python/synapse/server/**, "
    "diffed against TOOL_DEFS command_type set. Static; confirm live.",
    "register_call_sites": register_sites,
    "distinct_handler_command_types": len(have),
    "distinct_tool_command_types": len(wanted),
    "unreachable_command_types": unreachable_cmds,
    "unreachable_tools": unreachable_tools,
    "unreachable_tool_count": len(unreachable_tools),
    "dead_handlers_no_tool_reaches": dead_handlers,
    "dead_handler_count": len(dead_handlers),
    "handler_sites": {k: v for k, v in sorted(registered.items())},
    "command_type_to_tools": {k: sorted(v) for k, v in sorted(cmd_tools.items())},
}

dest = ROOT / "harness" / "notes" / "forensic" / "s1_reachability.json"
dest.write_text(json.dumps(out, indent=1), encoding="utf-8")

print(
    json.dumps(
        {
            k: v
            for k, v in out.items()
            if k not in ("handler_sites", "command_type_to_tools")
        },
        indent=1,
    )
)
print(f"wrote {dest}")
