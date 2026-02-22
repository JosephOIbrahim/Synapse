## P1 Complete
- MCP initialize instructions enriched with workflow protocol (inspect before mutating, one mutation per call, USD encoded names, lighting law, tone, session start guidance)
- Critical tool descriptions enhanced: execute_python (one mutation + undo group), set_parm (encoded USD names), project_setup (FIRST in every session)
- project_setup auto-init on session start (best-effort dispatch in _handle_initialize, cached on MCPSession.project_context)
- synapse://project/context resource added to resources/list
- mcp_server.py split into 5 tool group modules with domain knowledge preambles:
  - mcp_tools_scene.py (18 tools) -- node graph, params, execution, introspection
  - mcp_tools_render.py (10 tools) -- Karma, viewport, validation, farm
  - mcp_tools_usd.py (14 tools) -- stage assembly, materials, composition
  - mcp_tools_tops.py (18 tools) -- PDG pipelines, wedging, monitoring
  - mcp_tools_memory.py (20 tools) -- memory, knowledge, HDA, metrics
- Tests passing: 82 (62 original + 20 new P1 tests)

### Files Changed
- `python/synapse/mcp/server.py` -- enriched instructions, auto-init project context
- `python/synapse/mcp/session.py` -- added project_context slot to MCPSession
- `python/synapse/mcp/resources.py` -- added synapse://project/context resource
- `python/synapse/mcp/tools.py` -- enriched descriptions for execute_python, set_parm, project_setup
- `mcp_server.py` -- enriched tool descriptions, group knowledge section headers, tool group imports
- `mcp_tools_scene.py` -- NEW: scene tool group module
- `mcp_tools_render.py` -- NEW: render tool group module
- `mcp_tools_usd.py` -- NEW: USD tool group module
- `mcp_tools_tops.py` -- NEW: TOPS tool group module
- `mcp_tools_memory.py` -- NEW: memory tool group module
- `tests/test_mcp_protocol.py` -- 20 new P1 intelligence tests
