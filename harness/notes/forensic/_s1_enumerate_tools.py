"""S1 producer path — enumerate every REGISTERED MCP tool from the canonical registry.

Read-only. No hou. Emits harness/notes/forensic/s1_tool_census.json.

Law 2: every integer in S1_INVENTORY.md traces back to this script.

The registry is the single source of truth for both transports (stdio bridge
mcp_server.py and streamable-HTTP python/synapse/mcp/tools.py). Three tool
families live OUTSIDE TOOL_DEFS and are appended here exactly as
mcp_server.list_tools() appends them:
  - group-info tools (local knowledge preambles, no Houdini)
  - the inspector tool (local python + one execute_python round trip)
  - the scout tool (pure-python federated retrieval)
"""

import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "python"))

from synapse.mcp._tool_registry import TOOL_DEFS, TOOL_DISPATCH  # noqa: E402

rows = []
for name, cmd_type, payload_fn, desc, schema, ro, destr, idemp in TOOL_DEFS:
    rows.append(
        {
            "tool": name,
            "command_type": cmd_type,
            "source": "TOOL_DEFS",
            "read_only": bool(ro),
            "destructive": bool(destr),
            "idempotent": bool(idemp),
            "desc_head": (desc or "").strip().replace("\n", " ")[:160],
        }
    )

# --- tools appended by mcp_server.list_tools() outside TOOL_DEFS -------------
# Parsed from source rather than imported: mcp_server.py imports the `mcp`
# package at module scope, which is not needed to learn the tool names.
server_src = (ROOT / "mcp_server.py").read_text(encoding="utf-8", errors="replace")
tree = ast.parse(server_src)

group_tools = []
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == "_GROUP_INFO_TOOLS":
                for k in node.value.keys:
                    group_tools.append(k.value)

for g in group_tools:
    rows.append(
        {
            "tool": g,
            "command_type": None,
            "source": "mcp_server._GROUP_INFO_TOOLS",
            "read_only": True,
            "destructive": False,
            "idempotent": True,
            "desc_head": "[TOOL GROUP] local knowledge preamble; served without Houdini",
        }
    )


def _const_str(varname: str) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == varname:
                    if isinstance(node.value, ast.Constant):
                        return node.value.value
    return None


# The inspector name is a literal in mcp_server.py; the scout name comes from
# the scout module's own schema. Read both from source (mcp_server.py:498, :668)
# so this stays importable without the `mcp` package.
extra = []
_insp = _const_str("_INSPECTOR_TOOL_NAME")
if _insp:
    extra.append((_insp, "mcp_server.py:_INSPECTOR_TOOL_NAME -> synapse.cognitive.tools.inspect_stage"))
else:  # pragma: no cover - diagnostic
    extra.append(("<inspector-unresolved>", "?"))

try:
    from synapse.cognitive.tools.scout import SYNAPSE_SCOUT_SCHEMA  # noqa: E402

    extra.append(
        (
            SYNAPSE_SCOUT_SCHEMA["name"],
            "synapse.cognitive.tools.scout:SYNAPSE_SCOUT_SCHEMA[name]",
        )
    )
except Exception as exc:  # pragma: no cover - diagnostic
    extra.append((f"<scout-unresolved: {exc}>", "?"))

for nm, src in extra:
    rows.append(
        {
            "tool": nm,
            "command_type": None,
            "source": src,
            "read_only": True,
            "destructive": False,
            "idempotent": True,
            "desc_head": "local-dispatch branch in mcp_server.call_tool()",
        }
    )

names = [r["tool"] for r in rows]
dupes = sorted({n for n in names if names.count(n) > 1})

out = {
    "producer": "harness/notes/forensic/_s1_enumerate_tools.py",
    "registered_total": len(rows),
    "from_TOOL_DEFS": sum(1 for r in rows if r["source"] == "TOOL_DEFS"),
    "group_info": len(group_tools),
    "local_dispatch": len(extra),
    "TOOL_DISPATCH_entries": len(TOOL_DISPATCH),
    "duplicate_names": dupes,
    "tools": sorted(rows, key=lambda r: r["tool"]),
}

dest = ROOT / "harness" / "notes" / "forensic" / "s1_tool_census.json"
dest.write_text(json.dumps(out, indent=1, sort_keys=False), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "tools"}, indent=1))
print(f"wrote {dest}")
