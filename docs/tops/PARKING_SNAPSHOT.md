# TOPS/PDG Parking Snapshot

Captured: 2026-02-13 (MCP Sprint first run)

## Where It Was

- **Handler**: `_handle_wedge()` in `python/synapse/server/handlers_render.py` (lines 364-412)
- **MCP Tool**: `houdini_wedge` registered in `mcp_server.py` (stdio transport)
- **Tests**: `tests/test_tops_assembly.py` (4 tests covering basic wedge cooking)
- **RAG**: `rag/skills/houdini21-reference/tops_wedging.md` (comprehensive reference, ~180 lines)
- **Sprint Plan**: `docs/tops/TOPS_SPRINT.md` (complete spec, unstarted)

## What Was Implemented

- Basic wedge/TOP node cooking via `node.cook(block=True)`
- TOP/TopNet type detection and child wedge node discovery
- Coaching-tone error messages
- 120s timeout for wedge operations (in `_SLOW_COMMANDS`)
- `houdini_wedge` MCP tool in `TOOL_DISPATCH` (passthrough to `wedge` command)

## What Was NOT Implemented

- Work item introspection (`tops_get_work_items`)
- Dependency graph queries (`tops_get_dependency_graph`)
- Cook statistics (`tops_get_cook_stats`)
- Scheduler configuration (`tops_configure_scheduler`)
- Cook cancellation (`tops_cancel_cook`)
- Node dirtying (`tops_dirty_node`)
- Work item attribute access
- PDG module integration (no `import pdg` anywhere)
- MCP resources for TOPS status/work items

## Immediate Next Action When Resumed

1. Read `docs/tops/TOPS_SPRINT.md` for the full implementation spec
2. Check `docs/mcp/TOPS_INTEGRATION_POINTS.md` if it exists (integration hints from MCP sprint)
3. Implement Phase 1 core tools: work items, dependency graphs, stats, generation, cooking
4. Register all new tools in both `mcp_server.py` (stdio) and `python/synapse/mcp/tools.py` (HTTP)
5. Stub `pdg` module in tests (same pattern as `hou` stubs)

## Blockers

- MCP protocol layer must be complete first (Sprint A)
- All TOPS tools should be MCP tools from day one (no separate API)

## Git State

- No TOPS-specific branches exist
- All TOPS code is on `master` branch
- Original wedge tool added in commit `e1ed0fa`
- RAG knowledge is ahead of code (describes unimplemented tools)
