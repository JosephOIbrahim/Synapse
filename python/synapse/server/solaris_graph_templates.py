"""
Synapse Solaris Graph Templates

Pre-built topology templates for common Solaris DAG patterns.
Each function returns {"nodes": [...], "connections": [...], "display_node": "..."}.

CANONICAL SOLARIS ORDER (FORGE Pattern 1):
  Primitive → SOPCreate → MaterialLibrary → Camera → Lights →
  KarmaRenderProperties → USD Render ROP → OUTPUT null

Key rules:
  - Scene elements chain LINEARLY — each LOP adds prims to the stage
  - Merge is ONLY for combining separate USD layer streams (parallel
    asset pipelines, department outputs), NOT for individual elements
  - Every template must produce a RENDERABLE scene by default
"""

from typing import Dict, List, Any, Optional


# ── Canonical render tail (reused across templates) ──────────────

def _build_render_tail(
    nodes: List[Dict[str, Any]],
    connections: List[Dict[str, Any]],
    tail: str,
    include_camera: bool = True,
    include_lights: bool = True,
    include_render: bool = True,
) -> str:
    """Append the canonical Solaris tail chain after a merge/source node.

    Order follows FORGE Pattern 1:
      [tail] → materiallibrary → camera → domelight →
      karmarenderproperties → usdrender_rop → OUTPUT null

    Returns the final tail node id.
    """
    # Materials — always included (scene without materials = grey default)
    nodes.append({"id": "matlib", "type": "materiallibrary", "name": "materials"})
    connections.append({"from": tail, "to": "matlib", "input": 0})
    tail = "matlib"

    if include_camera:
        nodes.append({"id": "camera", "type": "camera", "name": "camera1"})
        connections.append({"from": tail, "to": "camera", "input": 0})
        tail = "camera"

    if include_lights:
        nodes.append({"id": "domelight", "type": "domelight", "name": "env_light"})
        connections.append({"from": tail, "to": "domelight", "input": 0})
        tail = "domelight"

    if include_render:
        nodes.append({
            "id": "karma_settings", "type": "karmarenderproperties",
            "name": "karma_settings",
        })
        connections.append({"from": tail, "to": "karma_settings", "input": 0})
        tail = "karma_settings"

    # OUTPUT null — display flag target, continues the main chain
    nodes.append({"id": "output", "type": "null", "name": "OUTPUT"})
    connections.append({"from": tail, "to": "output", "input": 0})

    if include_render:
        # usdrender_rop is a RopNode (terminal, zero outputs) — it branches
        # off karmarenderproperties, it does NOT continue the chain.
        nodes.append({
            "id": "rop", "type": "usdrender_rop", "name": "render",
        })
        connections.append({"from": "karma_settings", "to": "rop", "input": 0})

    return "output"


# ── Templates ────────────────────────────────────────────────────


def multi_asset_merge(
    stream_count: int = 2,
    include_camera: bool = True,
    include_lights: bool = True,
    include_render: bool = True,
) -> Dict[str, Any]:
    """N geometry streams → merge → canonical render tail.

    Produces a RENDERABLE scene: merge → materials → camera →
    lights → karma settings → render ROP → OUTPUT.

    Merge is used correctly here: combining parallel asset streams
    into a single stage. Everything after merge chains linearly.

    Args:
        stream_count: Number of geometry streams (sopcreate nodes).
        include_camera: Add a camera node (default: True).
        include_lights: Add a domelight for environment lighting (default: True).
        include_render: Add karma render settings + ROP (default: True).
    """
    if stream_count < 1:
        raise ValueError("stream_count must be >= 1")

    nodes: List[Dict[str, Any]] = []
    connections: List[Dict[str, Any]] = []

    # Geometry streams (parallel asset pipelines — valid merge use case)
    for i in range(stream_count):
        nodes.append({
            "id": f"geo_{i}",
            "type": "sopcreate",
            "name": f"geo_{i}",
        })

    # Merge separate asset streams into single stage
    nodes.append({"id": "merge", "type": "merge", "name": "scene_merge"})
    for i in range(stream_count):
        connections.append({"from": f"geo_{i}", "to": "merge", "input": i})

    # Canonical render tail: materials → camera → lights → render → output
    display = _build_render_tail(
        nodes, connections, "merge",
        include_camera=include_camera,
        include_lights=include_lights,
        include_render=include_render,
    )

    return {"nodes": nodes, "connections": connections, "display_node": display}


def sublayer_stack(
    layer_count: int = 3,
    include_camera: bool = False,
    include_lights: bool = False,
    include_render: bool = True,
) -> Dict[str, Any]:
    """N sublayer inputs → merge → render tail.

    Combines separate USD layers (e.g. geo layer, material layer,
    lighting layer from different departments). Merge is correct here
    because each sublayer is a separate USD layer stream.

    Camera/lights default to False because sublayers typically already
    contain them. Render settings default to True because you always
    need them to render.

    Args:
        layer_count: Number of sublayer input references.
        include_camera: Add camera to tail (default: False — layers usually have one).
        include_lights: Add domelight to tail (default: False — layers usually have one).
        include_render: Add karma + ROP to tail (default: True).
    """
    if layer_count < 1:
        raise ValueError("layer_count must be >= 1")

    nodes: List[Dict[str, Any]] = []
    connections: List[Dict[str, Any]] = []

    # Individual sublayer reference nodes (separate USD layer streams)
    for i in range(layer_count):
        nodes.append({
            "id": f"layer_{i}",
            "type": "sublayer",
            "name": f"layer_{i}",
        })

    # Merge layer streams (valid merge: combining USD layers)
    nodes.append({"id": "sublayer_merge", "type": "merge", "name": "sublayer_merge"})
    for i in range(layer_count):
        connections.append({"from": f"layer_{i}", "to": "sublayer_merge", "input": i})

    # Render tail
    display = _build_render_tail(
        nodes, connections, "sublayer_merge",
        include_camera=include_camera,
        include_lights=include_lights,
        include_render=include_render,
    )

    return {"nodes": nodes, "connections": connections, "display_node": display}


def render_pass_split(
    pass_count: int = 2,
    pass_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Assembled scene → N karma settings → N ROPs for multi-pass rendering.

    The source is a null node (connect your assembled scene to it).
    Each pass gets its own karmarenderproperties → usdrender_rop chain
    so you can configure different quality/AOV settings per pass.

    Args:
        pass_count: Number of render passes.
        pass_names: Names for each pass (defaults to pass_0, pass_1, ...).
    """
    if pass_count < 1:
        raise ValueError("pass_count must be >= 1")

    if pass_names and len(pass_names) != pass_count:
        raise ValueError("pass_names length must match pass_count")

    names = pass_names or [f"pass_{i}" for i in range(pass_count)]
    nodes: List[Dict[str, Any]] = []
    connections: List[Dict[str, Any]] = []

    # Scene input — null node as connection point for upstream scene
    nodes.append({"id": "scene_input", "type": "null", "name": "SCENE_INPUT"})

    # Per-pass render chains (fan-out from assembled scene)
    for i, name in enumerate(names):
        settings_id = f"karma_{name}"
        rop_id = f"rop_{name}"
        nodes.append({
            "id": settings_id,
            "type": "karmarenderproperties",
            "name": f"karma_{name}",
        })
        nodes.append({
            "id": rop_id,
            "type": "usdrender_rop",
            "name": f"render_{name}",
        })
        connections.append({"from": "scene_input", "to": settings_id, "input": 0})
        connections.append({"from": settings_id, "to": rop_id, "input": 0})

    # Display on first karma settings (ROP is terminal, no display flag)
    return {
        "nodes": nodes,
        "connections": connections,
        "display_node": f"karma_{names[0]}",
    }


def lighting_rig(
    light_types: Optional[List[str]] = None,
    include_render: bool = True,
) -> Dict[str, Any]:
    """Linear chain of lights → render tail.

    Lights chain LINEARLY in Solaris — each light LOP adds a new light
    prim to the stage. They do NOT need merging because they're not
    separate USD layer streams.

    The first light connects to a null input node so the rig can be
    wired into an existing scene chain.

    Args:
        light_types: List of light node types (defaults to domelight + key + fill).
        include_render: Add karma render settings + ROP (default: True).
    """
    types = light_types or ["domelight", "rectlight", "rectlight"]
    if not types:
        raise ValueError("light_types must not be empty")

    nodes: List[Dict[str, Any]] = []
    connections: List[Dict[str, Any]] = []
    light_names = ["env", "key", "fill", "rim", "accent", "bg", "hair", "kicker"]

    # Scene input — connect upstream scene here
    nodes.append({"id": "scene_input", "type": "null", "name": "SCENE_INPUT"})

    # Lights chain LINEARLY — each adds a prim to the stage
    tail = "scene_input"
    for i, lt in enumerate(types):
        name = light_names[i] if i < len(light_names) else f"light_{i}"
        nodes.append({"id": name, "type": lt, "name": f"{name}_light"})
        connections.append({"from": tail, "to": name, "input": 0})
        tail = name

    if include_render:
        nodes.append({
            "id": "karma_settings", "type": "karmarenderproperties",
            "name": "karma_settings",
        })
        connections.append({"from": tail, "to": "karma_settings", "input": 0})
        tail = "karma_settings"

    # OUTPUT null — display flag target
    nodes.append({"id": "output", "type": "null", "name": "OUTPUT"})
    connections.append({"from": tail, "to": "output", "input": 0})

    if include_render:
        # usdrender_rop branches off karma_settings (terminal, zero outputs)
        nodes.append({
            "id": "rop", "type": "usdrender_rop", "name": "render",
        })
        connections.append({"from": "karma_settings", "to": "rop", "input": 0})

    return {"nodes": nodes, "connections": connections, "display_node": "output"}


# Template registry — maps name to function
TEMPLATES = {
    "multi_asset_merge": multi_asset_merge,
    "sublayer_stack": sublayer_stack,
    "render_pass_split": render_pass_split,
    "lighting_rig": lighting_rig,
}


def expand_template(
    name: str,
    params: Optional[Dict[str, Any]] = None,
    overlay_nodes: Optional[List[Dict[str, Any]]] = None,
    overlay_connections: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Expand a template by name, then overlay any explicit nodes/connections.

    Args:
        name: Template name (must be in TEMPLATES).
        params: Parameters for the template function.
        overlay_nodes: Additional or override nodes (matched by id).
        overlay_connections: Additional connections.

    Returns:
        Merged {"nodes": [...], "connections": [...], "display_node": "..."}.
    """
    if name not in TEMPLATES:
        raise ValueError(
            f"Unknown template '{name}' — available: {', '.join(sorted(TEMPLATES))}"
        )

    result = TEMPLATES[name](**(params or {}))

    if overlay_nodes:
        existing_ids = {n["id"]: i for i, n in enumerate(result["nodes"])}
        for node in overlay_nodes:
            if node["id"] in existing_ids:
                # Override: merge parms, update type/name if provided
                idx = existing_ids[node["id"]]
                existing = result["nodes"][idx]
                if "type" in node:
                    existing["type"] = node["type"]
                if "name" in node:
                    existing["name"] = node["name"]
                if "parms" in node:
                    existing.setdefault("parms", {}).update(node["parms"])
            else:
                # Append new node
                result["nodes"].append(node)

    if overlay_connections:
        result["connections"].extend(overlay_connections)

    return result
