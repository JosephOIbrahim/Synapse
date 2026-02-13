# SYNAPSE — TOPS/PDG Integration Sprint Instructions

> **Sprint Goal:** Add PDG/TOPs integration to SYNAPSE, exposing distributed cooking,
> wedging, dependency management, and scheduler control as MCP tools. Every TOPS capability
> is registered in the MCP tool registry from day one — no separate API, no retrofit.
>
> **Prerequisite:** MCP Protocol Sprint must be complete before this work begins.
> The MCP layer is the delivery mechanism for all TOPS functionality.

---

## 0. PRE-FLIGHT — Read Before Coding

1. **Read `docs/tops/PARKING_SNAPSHOT.md`** — this was written when TOPS was parked for
   the MCP sprint. It contains where the work was, what was being thought about, and the
   immediate next action. Resume from there, not from scratch.

2. **Read `docs/mcp/TOPS_INTEGRATION_POINTS.md`** (if it exists) — during the MCP sprint, any natural
   interface points between MCP and TOPS were noted here. These are integration hints.

3. **Verify MCP is working** before touching TOPS code:
   ```bash
   # This must succeed or TOPS sprint has not been approved
   claude mcp add --transport http synapse http://localhost:PORT/mcp
   ```

---

## 1. ARCHITECTURE

### TOPS in the SYNAPSE Stack

```
MCP Client (Claude Code, Cursor, etc.)
    |  MCP Streamable HTTP
MCP Protocol Layer (synapse/mcp/)
    |  tools/call → dispatch
    |
    ├── TOPS Tools (NEW)
    │   ├── tops_cook_node
    │   ├── tops_generate_items
    │   ├── tops_get_work_items
    │   ├── tops_get_dependency_graph
    │   ├── tops_configure_scheduler
    │   ├── tops_cancel_cook
    │   ├── tops_dirty_node
    │   └── tops_get_cook_stats
    │
    ├── Existing Tools (UNCHANGED)
    │   ├── execute_vex, create_node, etc.
    │   └── ...
    │
Safety Middleware (atomic, idempotent, undo-groups)
    |
handlers.py → hou.* / pdg.* Python API
    |
Houdini PDG Graph Contexts
```

### Key Principle

TOPS handlers follow the exact same pattern as every other SYNAPSE handler:
- Register in `handlers.py` via `SynapseHandler._register_handlers()`
- Register in `mcp/tools.py` with `inputSchema` and `annotations`
- Safety middleware applies automatically
- Parameter aliases resolve through `aliases.py`

**No special TOPS subsystem.** TOPS tools are just more tools in the existing registry.

---

## 2. MCP TOOL DEFINITIONS

### 2.1 Read-Only Tools (Safe, no side effects)

```python
{
    "name": "tops_get_work_items",
    "description": (
        "List work items for a TOP node with their status, attributes, and "
        "output files. Supports filtering by state (scheduled, cooking, cooked, "
        "failed, cancelled)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "node_path": {
                "type": "string",
                "description": "Full path to the TOP node (e.g., /obj/topnet1/ropgeometry1)"
            },
            "state_filter": {
                "type": "string",
                "enum": ["all", "scheduled", "cooking", "cooked", "failed", "cancelled"],
                "default": "all",
                "description": "Filter work items by cook state"
            },
            "include_attributes": {
                "type": "boolean",
                "default": True,
                "description": "Include work item attributes in output"
            },
            "limit": {
                "type": "integer",
                "default": 100,
                "description": "Maximum number of work items to return"
            }
        },
        "required": ["node_path"]
    },
    "annotations": {
        "title": "Get TOP Work Items",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
},
{
    "name": "tops_get_dependency_graph",
    "description": (
        "Return the dependency graph for a TOP network, showing node connections, "
        "dependency types (automatic, explicit, partition, feedback), and data flow."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "topnet_path": {
                "type": "string",
                "description": "Path to the TOP network (e.g., /obj/topnet1)"
            },
            "depth": {
                "type": "integer",
                "default": -1,
                "description": "Traversal depth (-1 for full graph)"
            }
        },
        "required": ["topnet_path"]
    },
    "annotations": {
        "title": "Get TOP Dependency Graph",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
},
{
    "name": "tops_get_cook_stats",
    "description": (
        "Get cooking statistics for a TOP node or network: total work items, "
        "items by state, cook times, memory usage, scheduler utilization."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "node_path": {
                "type": "string",
                "description": "Path to TOP node or network"
            }
        },
        "required": ["node_path"]
    },
    "annotations": {
        "title": "Get TOP Cook Statistics",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
}
```

### 2.2 Mutation Tools (Scene-modifying)

```python
{
    "name": "tops_cook_node",
    "description": (
        "Cook a TOP node, generating and processing its work items. "
        "This triggers the full PDG cook cycle: generate → schedule → cook. "
        "Can cook a single node or the full upstream chain. "
        "WARNING: Heavy cooks can block Houdini for extended periods."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "node_path": {
                "type": "string",
                "description": "Full path to the TOP node to cook"
            },
            "generate_only": {
                "type": "boolean",
                "default": False,
                "description": "If true, only generate work items without cooking them"
            },
            "blocking": {
                "type": "boolean",
                "default": True,
                "description": "If true, wait for cook to complete before returning"
            },
            "top_down": {
                "type": "boolean",
                "default": True,
                "description": "Cook all upstream dependencies (true) or just this node (false)"
            }
        },
        "required": ["node_path"]
    },
    "annotations": {
        "title": "Cook TOP Node",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False
    }
},
{
    "name": "tops_generate_items",
    "description": (
        "Generate work items for a TOP node without cooking them. "
        "Useful for previewing what will be cooked, inspecting wedge variations, "
        "or validating dependency chains before committing to a full cook."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "node_path": {
                "type": "string",
                "description": "Full path to the TOP node"
            }
        },
        "required": ["node_path"]
    },
    "annotations": {
        "title": "Generate TOP Work Items",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False
    }
},
{
    "name": "tops_cancel_cook",
    "description": (
        "Cancel an active cook on a TOP node or network. "
        "Currently cooking work items will be cancelled."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "node_path": {
                "type": "string",
                "description": "Path to TOP node or network to cancel"
            }
        },
        "required": ["node_path"]
    },
    "annotations": {
        "title": "Cancel TOP Cook",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False
    }
},
{
    "name": "tops_dirty_node",
    "description": (
        "Dirty a TOP node, invalidating its work items so they will be "
        "regenerated on next cook. Use to force recomputation."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "node_path": {
                "type": "string",
                "description": "Path to the TOP node to dirty"
            },
            "dirty_upstream": {
                "type": "boolean",
                "default": False,
                "description": "Also dirty all upstream dependencies"
            }
        },
        "required": ["node_path"]
    },
    "annotations": {
        "title": "Dirty TOP Node",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False
    }
},
{
    "name": "tops_configure_scheduler",
    "description": (
        "Configure the scheduler for a TOP network. Supports Local, HQueue, "
        "and Deadline schedulers. Sets concurrency limits, working directories, "
        "and scheduler-specific options."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "topnet_path": {
                "type": "string",
                "description": "Path to the TOP network"
            },
            "scheduler_type": {
                "type": "string",
                "enum": ["local", "hqueue", "deadline"],
                "default": "local",
                "description": "Scheduler type"
            },
            "max_concurrent": {
                "type": "integer",
                "description": "Maximum concurrent work items (local scheduler)"
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory for output files (must be accessible to all workers)"
            }
        },
        "required": ["topnet_path"]
    },
    "annotations": {
        "title": "Configure TOP Scheduler",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False
    }
}
```

### 2.3 MCP Resources for TOPS

Add these to `mcp/resources.py`:

```python
TOPS_RESOURCES = [
    {
        "uri": "houdini://tops/{topnet_path}/graph",
        "name": "TOP Network Graph",
        "description": "Full dependency graph with node states and work item counts",
        "mimeType": "application/json"
    },
    {
        "uri": "houdini://tops/{topnet_path}/scheduler",
        "name": "Scheduler Status",
        "description": "Active scheduler configuration, utilization, and queue depth",
        "mimeType": "application/json"
    },
    {
        "uri": "houdini://tops/{node_path}/items",
        "name": "Work Items",
        "description": "All work items for a TOP node with state, attributes, and output paths",
        "mimeType": "application/json"
    },
    {
        "uri": "houdini://tops/{node_path}/cook-log",
        "name": "Cook Log",
        "description": "Cook log output for a TOP node's most recent cook",
        "mimeType": "text/plain"
    }
]
```

---

## 3. HANDLER IMPLEMENTATION

### 3.1 PDG API Surface

TOPS tools use the `pdg` Python module (available inside Houdini) alongside `hou`:

```python
import hou
import pdg  # Only available in Houdini with TOPs license

# Key pdg entry points:
# pdg.GraphContext       — Access the PDG graph for a TOP network
# pdg.WorkItem           — Individual work item with attributes
# pdg.Scheduler          — Scheduler interface
# pdg.WorkItemState      — Enum: Undefined, Uncooked, Waiting, Scheduled, Cooking, Cooked, Failed, Cancelled

# Getting a graph context from a TOP network node:
topnet_node = hou.node("/obj/topnet1")
context = topnet_node.getPDGGraphContext()

# Getting work items from a TOP node:
top_node = hou.node("/obj/topnet1/ropgeometry1")
pdg_node = top_node.getPDGNode()
work_items = pdg_node.workItems  # List of pdg.WorkItem
```

### 3.2 Handler Pattern

Follow the existing handler pattern exactly:

```python
# In handlers.py — register alongside existing handlers

def _handle_tops_get_work_items(self, payload: dict) -> dict:
    """Get work items for a TOP node."""
    node_path = self._resolve_param(payload, "node_path")
    state_filter = payload.get("state_filter", "all")
    include_attrs = payload.get("include_attributes", True)
    limit = payload.get("limit", 100)

    node = hou.node(node_path)
    if node is None:
        raise ValueError(f"Couldn't find node at '{node_path}'")

    pdg_node = node.getPDGNode()
    if pdg_node is None:
        raise ValueError(
            f"Node '{node_path}' is not a TOP node or has no PDG node. "
            f"Make sure the node is inside a TOP network."
        )

    items = []
    for wi in pdg_node.workItems:
        state_name = wi.state.name
        if state_filter != "all" and state_name.lower() != state_filter:
            continue

        item_data = {
            "id": wi.id,
            "index": wi.index,
            "name": wi.name,
            "state": state_name,
            "cook_time": round(wi.cookTime, 3) if hasattr(wi, "cookTime") else None,
        }

        if include_attrs:
            item_data["attributes"] = {}
            for attr in wi.attribs:
                item_data["attributes"][attr.name] = attr.values

        items.append(item_data)
        if len(items) >= limit:
            break

    return {
        "node": node_path,
        "total_items": len(pdg_node.workItems),
        "returned": len(items),
        "filter": state_filter,
        "items": items
    }
```

### 3.3 Safety Considerations

- **`tops_cook_node` with `blocking=True`** can block for minutes or hours on heavy jobs.
  Add to `_SLOW_COMMANDS` in `mcp_server.py` with a generous timeout (300s+).
  Consider returning a cook ID and providing a status-polling tool instead.

- **`tops_configure_scheduler`** with HQueue/Deadline talks to external services. This is
  an `openWorldHint: True` scenario if the scheduler submits to a remote farm.
  Update annotations accordingly.

- **Work item cancellation** is not always instant — PDG may finish the currently cooking
  item before the cancel takes effect. The handler should note this in the response.

- **`pdg` module availability** — `import pdg` only works inside Houdini with an active
  TOPs license. The handler should gracefully fail with a coaching-tone message:
  `"Couldn't access PDG — make sure you're running inside Houdini with a TOPs-enabled license."`

---

## 4. IMPLEMENTATION PLAN

### Phase 1 — Core TOPS Tools

**Deliverables:**
- [ ] `_handle_tops_get_work_items` in `handlers.py`
- [ ] `_handle_tops_get_dependency_graph` in `handlers.py`
- [ ] `_handle_tops_get_cook_stats` in `handlers.py`
- [ ] `_handle_tops_cook_node` in `handlers.py`
- [ ] `_handle_tops_generate_items` in `handlers.py`
- [ ] All five tools registered in `mcp/tools.py` with schemas and annotations
- [ ] All five tools registered in `mcp_server.py` (stdio bridge)
- [ ] `CommandType` variants in `core/protocol.py`
- [ ] Parameter aliases in `core/aliases.py`
- [ ] Timeout overrides in `_SLOW_COMMANDS` for cook operations
- [ ] `tests/test_tops.py` — handler tests with `hou`/`pdg` stubs
- [ ] `tests/test_mcp_protocol.py` — updated with TOPS tool discovery and dispatch tests

**Verification:** Claude Code can list TOPS tools via MCP, generate work items, and
read work item status from a live TOP network in Houdini.

### Phase 2 — Scheduler & Control

**Deliverables:**
- [ ] `_handle_tops_configure_scheduler` in `handlers.py`
- [ ] `_handle_tops_cancel_cook` in `handlers.py`
- [ ] `_handle_tops_dirty_node` in `handlers.py`
- [ ] All three tools in both MCP registries
- [ ] TOPS resources in `mcp/resources.py` (graph, scheduler, items, cook-log)
- [ ] Tests for scheduler configuration and cancellation

**Verification:** Claude Code can configure a local scheduler, cook a TOP network,
monitor progress via resources, and cancel a running cook.

### Phase 3 — Advanced Patterns

**Deliverables:**
- [ ] Wedge parameter setup tool (create Wedge TOP with attribute ranges)
- [ ] Batch cook tool (cook multiple TOP nodes in sequence)
- [ ] Work item attribute query/filter tool
- [ ] Cook progress notifications via MCP `resources/subscribe` (if Phase 3 of MCP sprint implemented SSE)
- [ ] Integration test: end-to-end wedge → cook → inspect results

**Verification:** Full PDG workflow controllable from any MCP client.

---

## 5. TESTING

### Stubbing `pdg`

The `pdg` module only exists inside Houdini. Stub it the same way as `hou`:

```python
import sys
from unittest.mock import MagicMock, PropertyMock

# Create pdg stub
mock_pdg = MagicMock()
mock_pdg.WorkItemState = MagicMock()
mock_pdg.WorkItemState.Cooked = "Cooked"
mock_pdg.WorkItemState.Failed = "Failed"
mock_pdg.WorkItemState.Cooking = "Cooking"
mock_pdg.WorkItemState.Scheduled = "Scheduled"

sys.modules["pdg"] = mock_pdg
```

### Test Files

| File | Coverage |
|------|----------|
| `tests/test_tops.py` | Handler logic with `hou`/`pdg` stubs |
| `tests/test_mcp_protocol.py` | TOPS tools in `tools/list`, `tools/call` dispatch |
| `tests/test_integration_tops.py` | Full cook cycle (requires Houdini, CI-excluded) |

---

## 6. SUCCESS CRITERIA

This sprint is complete when:

1. **All TOPS tools appear in `tools/list`** from any MCP client
2. **Work items can be generated, cooked, inspected, and cancelled** via MCP
3. **Scheduler can be configured** (at minimum local scheduler)
4. **TOPS resources are browseable** via `resources/list` and `resources/read`
5. **All operations go through existing safety middleware** — no shortcuts
6. **Tests pass without Houdini** (stubs for `hou` and `pdg`)
7. **Both MCP registries in sync** (`mcp/tools.py` and `mcp_server.py`)

---

## 7. REFERENCE

### PDG Work Item States

| State | Meaning |
|-------|---------|
| Undefined | Not yet generated |
| Uncooked | Generated but not scheduled |
| Waiting | Waiting for dependencies |
| Scheduled | Assigned to scheduler |
| Cooking | Currently processing |
| Cooked | Completed successfully |
| Failed | Cook failed |
| Cancelled | Cancelled by user or system |

### Common PDG Gotchas

- **`getPDGNode()` returns None** if the TOP node hasn't been cooked at least once or if
  the PDG graph context hasn't been created. Call `topnet.getPDGGraphContext()` first.
- **Work item attributes are typed** — `intAttribValue`, `floatAttribValue`,
  `stringAttribValue`. The handler should detect type and use the right accessor.
- **`pdg_output` vs `pdg_input`** — work items have separate input and output file lists.
  Output files are what the item produces; input files are dependencies.
- **Scheduler working directory** must be accessible from all worker machines for farm
  schedulers. Use `$PDG_DIR` or `$PDG_TEMP` for local.
- **Cook callbacks are async** — `pdg.GraphContext.cook()` returns immediately unless
  `block=True`. For MCP, prefer blocking with timeout for simple cases.

---

*This document is the single source of truth for the TOPS sprint.*
*When in doubt, refer here and to `docs/tops/PARKING_SNAPSHOT.md`.*