# SYNAPSE Solaris Auto-Assembly Fix — Blueprint + MOE Orchestration
## Quick Fix + Full Fix in One Sprint

> **Problem:** SYNAPSE creates the right Solaris nodes in /stage but doesn't 
> wire them into a linear chain. Nodes float independently — the artist has 
> to manually assemble the pipe.
>
> **Root cause:** Individual `create_node` tool calls don't chain. The AI 
> skips `connect_nodes` calls or orders them wrong. The planner's 
> `execute_python` recipes wire correctly, but ad-hoc requests bypass 
> the planner entirely.
>
> **D1 metaphor:** We fixed the lane assignment (nodes land in /stage). 
> Now we need the relay handoffs (nodes wire to each other).

---

## Architecture of the Fix

Three layers, each catches what the previous misses:

```
Layer 1: SYSTEM PROMPT (Quick Fix)
  └─ Tells AI: "In Solaris, use execute_python for multi-node chains.
     Wire every node to the previous one. Never leave nodes floating."
  └─ Catches: ~70% of cases (AI follows instructions)

Layer 2: SOLARIS SCENE RECIPE + PLANNER (Full Fix A)  
  └─ Atomic execute_python recipes for common Solaris chains
  └─ Planner intent patterns: "set up scene", "create render setup"
  └─ Catches: ~25% of cases (pattern-matched workflows)

Layer 3: AUTO-ASSEMBLE MCP TOOL (Full Fix B — Safety Net)
  └─ New tool: solaris_assemble_chain
  └─ Scans /stage for unwired LOP nodes, wires them in logical order
  └─ Called automatically after multi-node creation, or manually
  └─ Catches: remaining ~5% (ad-hoc requests that bypass everything)
```

---

## QUICK FIX — System Prompt Solaris Wiring Guidance

### File: `python/synapse/panel/system_prompt.py`

**What changed in the last sprint:** We added `_solaris_context_block()` 
that injects Solaris guidance when `network="/stage"`. Now we need to 
strengthen that guidance with explicit wiring instructions.

**Replace** the existing `_SOLARIS_CONTEXT_GUIDANCE` constant with this:

```python
_SOLARIS_CONTEXT_GUIDANCE = """\
## Solaris Context — Active

You are working in the `/stage` (LOP/Solaris) context. Follow these rules:

### CRITICAL: Node Assembly
In Solaris, nodes MUST be wired into a linear chain. Unlike /obj where nodes 
can float independently, LOP nodes compose a USD stage — unwired nodes are 
invisible to downstream nodes and the renderer.

**For ANY request that creates 2+ Solaris nodes, use execute_python with 
the full chain wired in a single script.** Do NOT use individual create_node 
calls followed by connect_nodes — this is unreliable and leaves nodes unwired.

Example — CORRECT (atomic script, wired):
```
import hou
stage = hou.node('/stage')
cam = stage.createNode('camera', 'cam')
cam.parm('primpath').set('/cameras/main')
light = stage.createNode('domelight', 'dome')
light.parm('primpath').set('/lights/dome')
light.setInput(0, cam)  # Wire dome AFTER camera
out = stage.createNode('null', 'OUTPUT')
out.setInput(0, light)
out.setDisplayFlag(True)
stage.layoutChildren()
```

Example — WRONG (individual calls, likely unwired):
```
create_node(type=camera, parent=/stage)
create_node(type=domelight, parent=/stage)
# Artist now has two floating nodes with no connections
```

### Wiring Rule
Every new LOP node connects to the previous node via input 0:
`new_node.setInput(0, previous_node)`

The chain is always: geometry → materials → assignment → cameras → lights → render settings → OUTPUT null.

### Node Creation
- ALL new nodes go in `/stage`. NEVER create LOP nodes under `/obj`.
- Use `sopcreate` (not `sopimport`) for new geometry.
- Only use `sopimport` when referencing geometry that ALREADY exists in `/obj`.

### Canonical Chain Order
When building a complete scene, wire in this order:
1. SOPCreate (geometry source)
2. MaterialLibrary (define materials)  
3. AssignMaterial (bind materials to geometry)
4. Camera
5. Key Light (rectlight)
6. Fill Light (rectlight) 
7. Dome Light (environment)
8. Karma Render Properties
9. OUTPUT null (display flag here)

You may skip nodes that aren't needed (e.g., no materials for a lighting test),
but the ORDER of what you include must follow this sequence.

### Materials
- Call `matlib.cook(force=True)` BEFORE `matlib.node("name").createNode()`.
- Use MaterialX `mtlxstandard_surface` as the default shader.

### Lighting Law
- Intensity is ALWAYS 1.0 on all lights.
- Control brightness ONLY via exposure (in stops).
- Enable exposure: `xn__inputsexposure_control_wcb` = "set"
- Set exposure: `xn__inputsexposure_vya` = desired stops value.

### Encoded Parameters
- USD parameters use encoded names (e.g., `xn__inputsintensity_i0a`).
- ALWAYS use `synapse_inspect_node` to discover parameter names before setting.

### After Creating Nodes
- Set display flag on the LAST node: `output.setDisplayFlag(True)`
- Call `stage.layoutChildren()` to arrange the network visually.
- If you created nodes individually (single node request), still wire to 
  the existing chain by finding the current display-flagged node and 
  inserting after it.

### Inserting Into Existing Chains
When adding a node to an existing Solaris network:
```python
import hou
stage = hou.node('/stage')
# Find current display node
display = None
for child in stage.children():
    if child.isDisplayFlagSet():
        display = child
        break

new_node = stage.createNode('domelight', 'dome')
new_node.parm('primpath').set('/lights/dome')

if display:
    # Insert: steal display's output connections
    outputs = [(c, c.inputIndex(display)) for c in display.outputs()]
    new_node.setInput(0, display)
    for out_node, idx in outputs:
        out_node.setInput(idx, new_node)
    new_node.setDisplayFlag(True)
else:
    new_node.setDisplayFlag(True)

stage.layoutChildren()
```
"""
```

---

## FULL FIX A — Solaris Scene Planner Workflow

### File: `python/synapse/routing/planner.py`

Add a new workflow builder and intent pattern for complete Solaris scene assembly.

**Add to `_WORKFLOW_INTENTS` list** (after the render_pipeline entry):

```python
# Solaris complete scene setup
(re.compile(
    r"(?:set up|setup|create|build|make)\s+(?:a\s+)?(?:complete\s+|full\s+)?"
    r"(?:solaris\s+)?(?:scene|render\s+scene|lop\s+scene)\s*"
    r"(?:with\s+(?P<modifiers>.+))?",
    re.IGNORECASE,
), "solaris_scene_pipeline", ["modifiers"]),

# Broader catch: "set up a scene with X"
(re.compile(
    r"(?:set up|setup|create|build)\s+(?:a\s+)?scene\s+"
    r"(?:with|that has|containing)\s+(?P<modifiers>.+)",
    re.IGNORECASE,
), "solaris_scene_pipeline", ["modifiers"]),
```

**Add modifier keywords** to `_MODIFIER_KEYWORDS`:

```python
# Solaris scene pipeline
"geometry": "add_geometry",
"sphere": "add_geometry", 
"cube": "add_geometry",
"box": "add_geometry",
"font": "add_geometry",
"grid": "add_geometry",
"material": "add_material",
"shader": "add_material",
"camera": "add_camera",
"three-point": "add_three_point",
"three point": "add_three_point",
"3-point": "add_three_point",
"3 point": "add_three_point",
"lighting": "add_lighting",
"light": "add_lighting",
"karma": "add_render",
"render": "add_render",
"render settings": "add_render",
```

**Add the builder function** (before `_WORKFLOW_BUILDERS` dict):

```python
def _build_solaris_scene_pipeline(
    params: Dict[str, str], modifiers: set
) -> List[SynapseCommand]:
    """Build a complete Solaris scene as a single atomic execute_python.
    
    Unlike other pipeline builders that emit individual create_node steps,
    this emits ONE execute_python with the entire chain wired inside.
    This guarantees nodes are connected — the core assembly fix.
    """
    cmds: List[SynapseCommand] = []
    
    # Default: include everything for a complete scene
    # If specific modifiers given, include only those sections
    has_specific = bool(modifiers & {
        "add_geometry", "add_material", "add_camera", 
        "add_lighting", "add_three_point", "add_render"
    })
    
    include_geo = not has_specific or "add_geometry" in modifiers
    include_mat = not has_specific or "add_material" in modifiers
    include_cam = not has_specific or "add_camera" in modifiers
    include_light = not has_specific or "add_lighting" in modifiers or "add_three_point" in modifiers
    include_render = not has_specific or "add_render" in modifiers
    three_point = "add_three_point" in modifiers
    
    # Build the code string piece by piece
    code_parts = [
        "import hou",
        "",
        "stage = hou.node('/stage')",
        "if stage is None:",
        "    stage = hou.node('/').createNode('lopnet', 'stage')",
        "",
        "prev = None  # Chain tracker",
        "created = {}  # Track all created nodes",
        "",
    ]
    
    if include_geo:
        code_parts.extend([
            "# ── GEOMETRY (SOPCreate) ──",
            "sop_create = stage.createNode('sopcreate', 'geo')",
            "sop_create.parm('primpath').set('/World/geo/mesh')",
            "inner = sop_create.node('sopnet')",
            "sphere = inner.createNode('sphere', 'sphere1')",
            "sphere.parm('rows').set(24)",
            "sphere.parm('cols').set(24)",
            "out = inner.createNode('null', 'OUT')",
            "out.setInput(0, sphere)",
            "out.setDisplayFlag(True)",
            "out.setRenderFlag(True)",
            "if prev: sop_create.setInput(0, prev)",
            "prev = sop_create",
            "created['geometry'] = sop_create.path()",
            "",
        ])
    
    if include_mat:
        code_parts.extend([
            "# ── MATERIAL ──",
            "matlib = stage.createNode('materiallibrary', 'materials')",
            "matlib.parm('matpathprefix').set('/materials')",
            "matlib.parm('matname1').set('surface_mat')",
            "if prev: matlib.setInput(0, prev)",
            "matlib.cook(force=True)",
            "mat_sub = matlib.node('surface_mat')",
            "if mat_sub:",
            "    shader = mat_sub.createNode('mtlxstandard_surface', 'mtlx_surface')",
            "    shader.parm('base_colorr').set(0.8)",
            "    shader.parm('base_colorg').set(0.2)",
            "    shader.parm('base_colorb').set(0.2)",
            "    shader.parm('specular_roughness').set(0.35)",
            "prev = matlib",
            "created['material'] = matlib.path()",
            "",
            "# ── ASSIGN MATERIAL ──",
            "assign = stage.createNode('assignmaterial', 'assign_mat')",
            "assign.parm('primpattern1').set('/World/geo/*')",
            "assign.parm('matspecpath1').set('/materials/surface_mat')",
            "if prev: assign.setInput(0, prev)",
            "prev = assign",
            "created['assign'] = assign.path()",
            "",
        ])
    
    if include_cam:
        code_parts.extend([
            "# ── CAMERA ──",
            "cam = stage.createNode('camera', 'render_cam')",
            "cam.parm('primpath').set('/cameras/render_cam')",
            "cam.parm('focalLength').set(50.0)",
            "cam.parm('tx').set(0.0)",
            "cam.parm('ty').set(1.0)",
            "cam.parm('tz').set(5.0)",
            "cam.parm('rx').set(-10.0)",
            "if prev: cam.setInput(0, prev)",
            "prev = cam",
            "created['camera'] = cam.path()",
            "",
        ])
    
    if include_light:
        if three_point:
            code_parts.extend([
                "# ── THREE-POINT LIGHTING ──",
                "key = stage.createNode('rectlight', 'key_light')",
                "key.parm('primpath').set('/lights/key')",
                "key.parm('xn__inputsintensity_i0a').set(1.0)",
                "key.parm('xn__inputsexposure_control_wcb').set('set')",
                "key.parm('xn__inputsexposure_vya').set(4.0)",
                "key.parm('xn__inputswidth_e5a').set(2.0)",
                "key.parm('xn__inputsheight_k5a').set(1.5)",
                "key.parm('tx').set(-3.0); key.parm('ty').set(4.0); key.parm('tz').set(3.0)",
                "key.parm('rx').set(-45.0); key.parm('ry').set(-30.0)",
                "if prev: key.setInput(0, prev)",
                "prev = key",
                "created['key_light'] = key.path()",
                "",
                "fill = stage.createNode('rectlight', 'fill_light')",
                "fill.parm('primpath').set('/lights/fill')",
                "fill.parm('xn__inputsintensity_i0a').set(1.0)",
                "fill.parm('xn__inputsexposure_control_wcb').set('set')",
                "fill.parm('xn__inputsexposure_vya').set(2.0)",
                "fill.parm('xn__inputswidth_e5a').set(3.0)",
                "fill.parm('xn__inputsheight_k5a').set(2.0)",
                "fill.parm('tx').set(4.0); fill.parm('ty').set(2.0); fill.parm('tz').set(2.0)",
                "fill.parm('rx').set(-25.0); fill.parm('ry').set(45.0)",
                "fill.setInput(0, prev)",
                "prev = fill",
                "created['fill_light'] = fill.path()",
                "",
                "rim = stage.createNode('rectlight', 'rim_light')",
                "rim.parm('primpath').set('/lights/rim')",
                "rim.parm('xn__inputsintensity_i0a').set(1.0)",
                "rim.parm('xn__inputsexposure_control_wcb').set('set')",
                "rim.parm('xn__inputsexposure_vya').set(5.0)",
                "rim.parm('xn__inputswidth_e5a').set(1.0)",
                "rim.parm('xn__inputsheight_k5a').set(3.0)",
                "rim.parm('tx').set(0.0); rim.parm('ty').set(3.0); rim.parm('tz').set(-4.0)",
                "rim.parm('rx').set(-30.0); rim.parm('ry').set(180.0)",
                "rim.setInput(0, prev)",
                "prev = rim",
                "created['rim_light'] = rim.path()",
                "",
            ])
        else:
            code_parts.extend([
                "# ── KEY LIGHT ──",
                "key = stage.createNode('rectlight', 'key_light')",
                "key.parm('primpath').set('/lights/key')",
                "key.parm('xn__inputsintensity_i0a').set(1.0)",
                "key.parm('xn__inputsexposure_control_wcb').set('set')",
                "key.parm('xn__inputsexposure_vya').set(4.0)",
                "key.parm('xn__inputswidth_e5a').set(2.0)",
                "key.parm('xn__inputsheight_k5a').set(1.5)",
                "key.parm('tx').set(3.0); key.parm('ty').set(4.0); key.parm('tz').set(2.0)",
                "key.parm('rx').set(-45.0); key.parm('ry').set(45.0)",
                "if prev: key.setInput(0, prev)",
                "prev = key",
                "created['key_light'] = key.path()",
                "",
                "# ── DOME LIGHT ──",
                "dome = stage.createNode('domelight', 'dome_light')",
                "dome.parm('primpath').set('/lights/dome')",
                "dome.parm('xn__inputsintensity_i0a').set(1.0)",
                "dome.parm('xn__inputsexposure_control_wcb').set('set')",
                "dome.parm('xn__inputsexposure_vya').set(0.0)",
                "dome.setInput(0, prev)",
                "prev = dome",
                "created['dome_light'] = dome.path()",
                "",
            ])
    
    if include_render:
        code_parts.extend([
            "# ── KARMA RENDER PROPERTIES ──",
            "krp = stage.createNode('karmarenderproperties', 'karma_settings')",
            "try:",
            "    krp.parm('karma:global:pathtracedsamples').set(64)",
            "    krp.parm('engine').set('xpu')",
            "except: pass  # Parm names may vary",
            "if prev: krp.setInput(0, prev)",
            "prev = krp",
            "created['render_settings'] = krp.path()",
            "",
        ])
    
    code_parts.extend([
        "# ── OUTPUT (display flag) ──",
        "output = stage.createNode('null', 'OUTPUT')",
        "if prev: output.setInput(0, prev)",
        "output.setDisplayFlag(True)",
        "created['output'] = output.path()",
        "",
        "stage.layoutChildren()",
        "",
        "result = created",
    ])
    
    code = "\n".join(code_parts)
    
    cmds.append(_cmd("execute_python", {"code": code}))
    return cmds
```

**Register in `_WORKFLOW_BUILDERS`:**

```python
_WORKFLOW_BUILDERS = {
    "cloth_pipeline": _build_cloth_pipeline,
    "destruction_pipeline": _build_destruction_pipeline,
    "lighting_pipeline": _build_lighting_pipeline,
    "render_pipeline": _build_render_pipeline,
    "ocean_pipeline": _build_ocean_pipeline,
    "pyro_pipeline": _build_pyro_pipeline,
    "solaris_scene_pipeline": _build_solaris_scene_pipeline,  # NEW
}
```

---

## FULL FIX B — Auto-Assemble MCP Tool (Safety Net)

### New File: `python/synapse/server/handlers_solaris_assemble.py`

This is the safety net. When nodes ARE created individually (ad-hoc requests, 
single-node additions), this tool wires them into logical order.

```python
"""
Synapse Solaris Chain Assembly Handler

Scans /stage for unwired LOP nodes and assembles them into a logical
linear chain based on node type ordering rules.

This is the safety net — catches nodes that were created individually
without wiring, and connects them in the canonical Solaris order.
"""

from typing import Any, Dict, List, Tuple

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.errors import HoudiniUnavailableError, NodeNotFoundError
from ..core.aliases import resolve_param, resolve_param_with_default


# Canonical ordering: lower number = earlier in chain
# Nodes not in this map get inserted at position 500 (middle)
_SOLARIS_NODE_ORDER: Dict[str, int] = {
    # Geometry sources
    "sopcreate": 100,
    "sopimport": 100,
    "sceneimport": 100,
    "reference": 110,
    "sublayer": 110,
    
    # Materials
    "materiallibrary": 200,
    "materiallinker": 210,
    "assignmaterial": 220,
    
    # Transforms / edits
    "edit": 300,
    "configureprimitive": 310,
    "xform": 320,
    
    # Camera
    "camera": 400,
    
    # Lights (key before fill before dome — by convention)
    "rectlight": 500,
    "spherelight": 510,
    "distantlight": 520,
    "disklight": 530,
    "cylinderlight": 540,
    "domelight": 600,  # Dome last among lights
    
    # Render settings
    "karmarenderproperties": 700,
    "karmarendersettings": 710,
    "rendergeometrysettings": 720,
    "rendersettings": 730,
    "renderproduct": 740,
    
    # Output
    "usdrender_rop": 800,
    "usdrender": 800,
    "null": 900,
}


def _get_sort_key(node) -> Tuple[int, str]:
    """Return (order, name) for sorting. Stable sort within same type."""
    type_name = node.type().name()
    order = _SOLARIS_NODE_ORDER.get(type_name, 500)
    return (order, node.name())


def _is_unwired(node) -> bool:
    """Check if a node has no input connections."""
    return all(inp is None for inp in node.inputs())


def _is_chain_end(node) -> bool:
    """Check if a node has no output connections."""
    return len(node.outputs()) == 0


class SolarisAssembleMixin:
    """Mixin providing the solaris_assemble_chain handler."""

    def _handle_solaris_assemble_chain(self, payload: Dict) -> Dict:
        """Scan /stage and wire unwired LOP nodes into a logical chain.
        
        Modes:
            "all"   — Wire ALL unwired nodes in /stage (default)
            "nodes" — Wire only the specified node paths
            "after" — Wire specified nodes after the current chain end
        
        Payload:
            parent: str — Parent network path (default: /stage)
            mode: str — "all", "nodes", or "after" 
            nodes: list[str] — Node paths (for "nodes" and "after" modes)
            dry_run: bool — If true, return plan without executing
        """
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        parent_path = resolve_param_with_default(payload, "parent", "/stage")
        mode = resolve_param_with_default(payload, "mode", "all")
        node_paths = resolve_param_with_default(payload, "nodes", [])
        dry_run = resolve_param_with_default(payload, "dry_run", False)

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise NodeNotFoundError(parent_path)

            # Gather target nodes
            if mode == "all":
                # Find all unwired children
                candidates = [
                    c for c in parent.children()
                    if _is_unwired(c) and c.type().name() != "subnet"
                ]
                # Also find the existing chain end to append to
                chain_ends = [
                    c for c in parent.children()
                    if _is_chain_end(c) and not _is_unwired(c)
                ]
            elif mode in ("nodes", "after"):
                candidates = []
                for p in node_paths:
                    n = hou.node(p)
                    if n is None:
                        raise NodeNotFoundError(p)
                    candidates.append(n)
                chain_ends = [
                    c for c in parent.children()
                    if c.isDisplayFlagSet()
                ]
            else:
                return {"error": f"Unknown mode: {mode}"}

            if not candidates:
                return {
                    "status": "ok",
                    "message": "No unwired nodes found — chain is already assembled.",
                    "wired": 0,
                }

            # Sort candidates by canonical order
            sorted_nodes = sorted(candidates, key=_get_sort_key)

            # Build the wiring plan
            plan = []
            
            # Find what to attach to: existing chain end, or start fresh
            attach_to = None
            if chain_ends:
                # Pick the display-flagged one, or the last chain end
                for ce in chain_ends:
                    if ce.isDisplayFlagSet():
                        attach_to = ce
                        break
                if attach_to is None:
                    attach_to = chain_ends[0]

            prev = attach_to
            for node in sorted_nodes:
                if prev is not None:
                    plan.append({
                        "action": "wire",
                        "source": prev.path(),
                        "target": node.path(),
                        "target_input": 0,
                    })
                prev = node

            # Last node gets display flag
            if sorted_nodes:
                plan.append({
                    "action": "set_display_flag",
                    "node": sorted_nodes[-1].path(),
                })

            if dry_run:
                return {
                    "status": "dry_run",
                    "plan": plan,
                    "order": [n.path() for n in sorted_nodes],
                    "attach_to": attach_to.path() if attach_to else None,
                }

            # Execute the plan
            wired = 0
            for step in plan:
                if step["action"] == "wire":
                    target = hou.node(step["target"])
                    source = hou.node(step["source"])
                    if target and source:
                        target.setInput(step["target_input"], source)
                        wired += 1
                elif step["action"] == "set_display_flag":
                    node = hou.node(step["node"])
                    if node:
                        # Clear display flag from old node
                        if attach_to and attach_to.isDisplayFlagSet():
                            attach_to.setDisplayFlag(False)
                        node.setDisplayFlag(True)

            parent.layoutChildren()

            return {
                "status": "ok",
                "wired": wired,
                "order": [n.path() for n in sorted_nodes],
                "chain_end": sorted_nodes[-1].path() if sorted_nodes else None,
                "attach_to": attach_to.path() if attach_to else None,
            }

        return run_on_main(_on_main)
```

### Register the handler

**File: `python/synapse/server/handlers.py`** (or wherever mixins are composed)

Add `SolarisAssembleMixin` to the handler class inheritance and register 
the command:

```python
from .handlers_solaris_assemble import SolarisAssembleMixin

class SynapseHandler(NodeHandlerMixin, SolarisAssembleMixin, ...):
    ...
```

And in the command dispatch table:

```python
"solaris_assemble_chain": self._handle_solaris_assemble_chain,
```

### Register as MCP Tool

**File: `python/synapse/mcp/mcp_tools_scene.py`** (or equivalent)

Add the tool definition so the AI can call it:

```python
{
    "name": "synapse_solaris_assemble_chain",
    "description": (
        "Wire unwired LOP nodes in /stage into a logical linear chain. "
        "Call this AFTER creating multiple Solaris nodes individually, "
        "or if nodes appear unwired in the network. "
        "Mode 'all' scans for all unwired nodes. "
        "Mode 'after' appends specified nodes after the current chain end. "
        "Use dry_run=true to preview the wiring plan without executing."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "parent": {
                "type": "string",
                "description": "Parent network path (default: /stage)",
                "default": "/stage"
            },
            "mode": {
                "type": "string",
                "enum": ["all", "nodes", "after"],
                "description": "all=wire all unwired nodes, nodes=wire specific nodes, after=append to existing chain",
                "default": "all"
            },
            "nodes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Node paths to wire (for 'nodes' and 'after' modes)"
            },
            "dry_run": {
                "type": "boolean",
                "description": "Preview wiring plan without executing",
                "default": false
            }
        }
    }
}
```

---

## FULL FIX C — RAG Document Update

### File: `rag/skills/houdini21-reference/solaris_network_blueprint.md`

**Append** this section to the existing blueprint (from the previous sprint):

```markdown
## Auto-Assembly Tool

If nodes were created individually and are floating unwired, use:

```python
# Via MCP tool:
synapse_solaris_assemble_chain(parent="/stage", mode="all")

# Preview first:
synapse_solaris_assemble_chain(parent="/stage", mode="all", dry_run=True)

# Append specific nodes to existing chain:
synapse_solaris_assemble_chain(
    parent="/stage", 
    mode="after",
    nodes=["/stage/new_light", "/stage/new_dome"]
)
```

The tool sorts nodes by canonical type order and wires them linearly.

## PREFER atomic execute_python for multi-node creation

When creating 2+ Solaris nodes, ALWAYS use execute_python with the full
chain wired in a single script. This is more reliable than individual 
create_node calls. Use solaris_assemble_chain as a SAFETY NET, not as 
the primary assembly method.
```

---

## MOE AGENT TEAM ORCHESTRATION

### Team Roster (4 Agents + Orchestrator)

| Agent | Role | Files Owned | Branch |
|-------|------|------------|--------|
| **ORCHESTRATOR** | Sequences legs, merges | `master` (read-only) | `master` |
| **UI** | System prompt wiring guidance | `system_prompt.py` | `fix/solaris-assembly-ui` |
| **ROUTING** | Planner workflow + recipe | `planner.py` | `fix/solaris-assembly-routing` |
| **HANDLER** | New MCP tool + handler | `handlers_solaris_assemble.py` (new), `handlers.py`, `mcp_tools_scene.py` | `fix/solaris-assembly-handler` |
| **VALIDATION** | Tests for all three layers | `tests/test_solaris_assembly.py` (new) | `fix/solaris-assembly-tests` |

### Execution Order

```
Phase 1: UI (quick fix — immediate impact, no deps)
    ↓
Phase 2: ROUTING + HANDLER (parallel — no file overlap)
    ↓
Phase 3: VALIDATION (needs all code merged)
    ↓
Phase 4: MERGE + VERIFY (orchestrator)
```

### Setup

```bash
cd C:\Users\User\SYNAPSE
git checkout master && git pull

git branch fix/solaris-assembly-ui
git branch fix/solaris-assembly-routing
git branch fix/solaris-assembly-handler
git branch fix/solaris-assembly-tests

git worktree add ../SYNAPSE-asm-ui fix/solaris-assembly-ui
git worktree add ../SYNAPSE-asm-routing fix/solaris-assembly-routing
git worktree add ../SYNAPSE-asm-handler fix/solaris-assembly-handler
git worktree add ../SYNAPSE-asm-tests fix/solaris-assembly-tests
```

Copy the blueprint into each:

```bash
xcopy /E /I _solaris_assembly_fix SYNAPSE-asm-ui\_ref
xcopy /E /I _solaris_assembly_fix SYNAPSE-asm-routing\_ref
xcopy /E /I _solaris_assembly_fix SYNAPSE-asm-handler\_ref
xcopy /E /I _solaris_assembly_fix SYNAPSE-asm-tests\_ref
```

### Agent Prompts

#### UI Agent (Phase 1 — runs first)

```
You are the UI specialist for SYNAPSE. Your job is to upgrade the Solaris 
system prompt guidance with explicit node wiring instructions.

Read _ref/SOLARIS_ASSEMBLY_BLUEPRINT.md section "QUICK FIX — System Prompt".

YOUR TASKS:
1. Open python/synapse/panel/system_prompt.py
2. REPLACE the existing _SOLARIS_CONTEXT_GUIDANCE constant with the 
   upgraded version from the blueprint (includes wiring rules, 
   canonical chain order, execute_python guidance, and chain insertion pattern)
3. Verify the constant is properly formatted (no unclosed quotes)
4. git add -A && git commit -m "feat(ui): add Solaris wiring guidance to system prompt"

DO NOT touch routing, handler, or test files.
Verify: The _SOLARIS_CONTEXT_GUIDANCE string should contain "execute_python"
and "setInput(0, prev)" and "Canonical Chain Order".
```

#### ROUTING Agent (Phase 2A — parallel with HANDLER)

```
You are the ROUTING specialist for SYNAPSE. Your job is to add a Solaris 
scene pipeline workflow to the planner.

Read _ref/SOLARIS_ASSEMBLY_BLUEPRINT.md section "FULL FIX A — Solaris Scene Planner".

YOUR TASKS:
1. In python/synapse/routing/planner.py:
   a. Add the two new regex patterns to _WORKFLOW_INTENTS 
      (solaris_scene_pipeline and the broader "scene with" catch)
   b. Add Solaris modifier keywords to _MODIFIER_KEYWORDS
   c. Add the _build_solaris_scene_pipeline() function
   d. Register "solaris_scene_pipeline" in _WORKFLOW_BUILDERS dict

2. Verify the function generates valid Python code:
   - Test that the code string has balanced parentheses
   - Test that "setInput(0, prev)" appears for every node after the first
   - Test that "layoutChildren()" appears at the end

3. git add -A && git commit -m "feat(routing): add solaris scene pipeline workflow to planner"

DO NOT touch system_prompt.py, handler files, or test files.
```

#### HANDLER Agent (Phase 2B — parallel with ROUTING)

```
You are the HANDLER specialist for SYNAPSE. Your job is to create the 
solaris_assemble_chain MCP tool — the safety net that wires unwired nodes.

Read _ref/SOLARIS_ASSEMBLY_BLUEPRINT.md section "FULL FIX B — Auto-Assemble MCP Tool".

YOUR TASKS:
1. Create python/synapse/server/handlers_solaris_assemble.py
   - Full SolarisAssembleMixin class from the blueprint
   - Include _SOLARIS_NODE_ORDER, _get_sort_key, _is_unwired, _is_chain_end
   - The _handle_solaris_assemble_chain method with all three modes

2. In python/synapse/server/handlers.py:
   - Import SolarisAssembleMixin
   - Add it to the SynapseHandler class inheritance
   - Add "solaris_assemble_chain" to the command dispatch dict

3. In the MCP tools file (mcp_tools_scene.py or equivalent):
   - Add the synapse_solaris_assemble_chain tool definition with schema

4. Update rag/skills/houdini21-reference/solaris_network_blueprint.md:
   - Append the "Auto-Assembly Tool" section from the blueprint

5. git add -A && git commit -m "feat(handler): add solaris_assemble_chain MCP tool"

DO NOT touch system_prompt.py, planner.py, or test files.
```

#### VALIDATION Agent (Phase 3 — waits for all above)

```
You are the VALIDATION specialist for SYNAPSE. Your job is to write tests
for the Solaris auto-assembly system.

WAIT until UI, ROUTING, and HANDLER agents have committed.

YOUR TASKS:
1. Create tests/test_solaris_assembly.py with these test classes:

   TestSolarisNodeOrder:
   - Verify _SOLARIS_NODE_ORDER puts geometry < materials < cameras < lights < render
   - Verify domelight sorts AFTER rectlight
   - Verify null sorts last (900)
   - Verify unknown types get 500

   TestGetSortKey:
   - Mock hou nodes, verify sorting produces canonical order
   - Verify stable sort (same type sorted by name)

   TestSolarisScenePipeline:
   - Import _build_solaris_scene_pipeline from planner
   - Verify it returns execute_python commands
   - Verify generated code contains "setInput(0, prev)" for every node
   - Verify generated code contains "layoutChildren()"
   - Verify generated code contains "setDisplayFlag(True)"
   - Test with modifiers: {"add_camera", "add_lighting"} only includes those sections

   TestSystemPromptWiring:
   - Import _SOLARIS_CONTEXT_GUIDANCE from system_prompt
   - Verify it contains "execute_python"
   - Verify it contains "setInput(0,"
   - Verify it contains "Canonical Chain Order"
   - Verify it contains "layoutChildren"

2. Run: python -m pytest tests/test_solaris_assembly.py -v
3. Run: python -m pytest tests/test_solaris_context.py tests/test_solaris_ordering.py -v
4. git add -A && git commit -m "test(solaris): add assembly tests + ordering regression"

DO NOT modify source files. Test files only.
```

### Merge Order

```bash
cd C:\Users\User\SYNAPSE
git checkout master
git merge fix/solaris-assembly-ui --no-ff -m "feat(ui): Solaris wiring guidance in system prompt"
git merge fix/solaris-assembly-routing --no-ff -m "feat(routing): Solaris scene pipeline workflow"
git merge fix/solaris-assembly-handler --no-ff -m "feat(handler): solaris_assemble_chain MCP tool"
git merge fix/solaris-assembly-tests --no-ff -m "test(solaris): assembly tests + regression guards"

python -m pytest tests/test_solaris_assembly.py tests/test_solaris_context.py tests/test_solaris_ordering.py -v
git push origin master
```

### Cleanup

```bash
git worktree remove ../SYNAPSE-asm-ui --force
git worktree remove ../SYNAPSE-asm-routing --force
git worktree remove ../SYNAPSE-asm-handler --force
git worktree remove ../SYNAPSE-asm-tests --force
git worktree prune

git branch -d fix/solaris-assembly-ui
git branch -d fix/solaris-assembly-routing
git branch -d fix/solaris-assembly-handler
git branch -d fix/solaris-assembly-tests
```

---

## Success Criteria

- [ ] System prompt contains `execute_python` wiring guidance for Solaris
- [ ] "Set up a scene with camera and lights" triggers `solaris_scene_pipeline`
- [ ] `synapse_solaris_assemble_chain` tool exists and is callable
- [ ] Assemble tool sorts nodes: geo → mat → assign → cam → lights → dome → render → null
- [ ] All tests pass
- [ ] After restart: Asking "create font in solaris" produces a wired chain, not floating nodes

---

## Post-Merge Houdini Test

1. Restart Houdini, reconnect SYNAPSE
2. Navigate to /stage
3. Test quick fix: "Create a font with a red material and dome light"
   → Expected: Single execute_python, all nodes wired, display flag on OUTPUT
4. Test planner: "Set up a complete scene with three-point lighting"
   → Expected: solaris_scene_pipeline fires, full chain built atomically
5. Test safety net: Create nodes individually, then "assemble the chain"
   → Expected: solaris_assemble_chain wires them in canonical order

*Sprint estimated: ~90 minutes. Same relay format as last sprint.*
