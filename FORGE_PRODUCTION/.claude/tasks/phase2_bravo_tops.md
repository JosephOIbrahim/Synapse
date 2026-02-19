# TEAM BRAVO — Phase 2: TOPS Enhancement + Live Monitoring

> **File ownership:** `synapse/handlers_tops.py`, `synapse/handlers_solaris.py`, `synapse/mcp/tools.py`, `synapse/mcp/mcp_server.py`
> **Do NOT modify:** rag/, routing/, agent/, autonomy/, tests/

## Context

Read these first:
- `CLAUDE.md` (project conventions, safety middleware)
- `docs/forge/FORGE_PRODUCTION.md` (your deliverables)
- `.claude/agent.md` (task rules)
- `synapse/handlers_tops.py` (existing 16 TOPS handlers, 1,213 lines)
- `synapse/render_farm.py` (existing render farm, 514 lines)
- `synapse/mcp/tools.py` (tool registration patterns)
- `synapse/mcp/mcp_server.py` (stdio bridge registration)
- `rag/skills/houdini21-reference/tops_wedging.md`
- `rag/skills/houdini21-reference/render_farm.md`

## Handler 1: `tops_monitor_stream`

Replace polling `tops_pipeline_status` with event-driven push.

### Architecture
```
TOPS cook → hou.pdg callback → asyncio queue → WebSocket message → client
```

### Events to emit
```python
@dataclass
class TOPSEvent:
    event_type: str   # work_item_started | work_item_completed | work_item_failed | cook_progress | cook_complete
    timestamp: float
    data: dict

# work_item_started:  {item_id, node, frame}
# work_item_completed: {item_id, node, frame, duration_seconds, output_path}
# work_item_failed:   {item_id, node, frame, error_message}
# cook_progress:      {completed, total, percent}
# cook_complete:      {total_time_seconds, results_summary}
```

### Implementation notes
- Register callback via `pdg.EventHandler` (H21 API — check RAG for exact pattern)
- Callback MUST NOT block TOPS cook thread
- Use `asyncio.Queue` to decouple callback from WebSocket send
- Unregister callback when monitoring stops (cleanup)
- If H21 doesn't support `pdg.EventHandler`, fall back to `hou.pdg.WorkItem.addEventHandler`

### Registration
```python
# In mcp/tools.py
{
    "name": "tops_monitor_stream",
    "description": "Start live monitoring of TOPS cook progress. Emits events via WebSocket as work items progress.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "top_node": {"type": "string", "description": "Path to TOP node to monitor"},
            "include_output_paths": {"type": "boolean", "default": True}
        },
        "required": ["top_node"]
    },
    "annotations": {"readOnlyHint": True}
}
```

---

## Handler 2: `tops_render_sequence`

Single-call interface for "render frames 1-48."

### Behavior
1. Validate Solaris stage is renderable (call existing `get_stage_info` or similar)
2. Check for existing TOPS network matching the request (idempotent)
3. If none, create TOPS network: fetch node → Karma ROP → file output
4. Set frame range, camera, render settings, output directory
5. Generate work items for frame range
6. Start cook with monitoring (calls `tops_monitor_stream` internally)
7. Return `job_id` for status queries

### Registration
```python
{
    "name": "tops_render_sequence",
    "description": "Render a frame sequence through TOPS. Creates/reuses TOPS network, generates work items, cooks with live monitoring.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "frame_start": {"type": "integer", "description": "First frame to render"},
            "frame_end": {"type": "integer", "description": "Last frame to render"},
            "camera": {"type": "string", "description": "Camera path (e.g., /cameras/cam1)"},
            "render_settings": {"type": "object", "description": "Optional render setting overrides"},
            "output_dir": {"type": "string", "description": "Output directory for rendered frames"},
            "renderer": {"type": "string", "enum": ["karma_xpu", "karma_cpu"], "default": "karma_xpu"}
        },
        "required": ["frame_start", "frame_end"]
    },
    "annotations": {"readOnlyHint": False}
}
```

### Safety
- All scene mutations through undo groups
- Idempotent: calling twice with same params reuses existing TOPS network
- Don't create duplicate schedulers
- Validate frame range (start <= end, positive values)

---

## Handler 3: TOPS Warm Standby

Enhancement to existing connection flow, not a separate handler.

### Behavior
On Houdini connect (or when first TOPS tool is called):
1. Check if a local scheduler node exists in the scene
2. If none, create a default local scheduler at `/obj/topnet1/localscheduler1` (or find the standard TOPS location)
3. Configure with sensible defaults (max procs = CPU count - 2, temp dir)
4. Store warm state in session metadata: `session.tops_warm = True`
5. Log: "TOPS warm standby active"

### Integration
- Hook into the existing session/connection lifecycle
- Check `synapse/server/` and `synapse/session/` for where to add the warm-up call
- Must not block connection — run async if needed

---

## General Requirements

- Follow EXACT patterns from existing `handlers_tops.py`
- All 3 handlers registered in both `mcp/tools.py` AND `mcp_server.py`
- Type hints on all functions
- Docstrings matching existing style
- Error handling through existing error taxonomy

## Done Criteria

- [ ] `tops_monitor_stream` handler implemented
- [ ] `tops_render_sequence` handler implemented
- [ ] TOPS warm standby logic added
- [ ] All 3 registered in `mcp/tools.py` with `inputSchema` + `annotations`
- [ ] All 3 registered in `mcp_server.py`
- [ ] Existing tests still pass
- [ ] Report: handler signatures, safety middleware usage, any edge case questions
