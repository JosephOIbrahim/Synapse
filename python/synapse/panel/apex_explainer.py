"""APEX Explainer module for the SYNAPSE Houdini panel.

Provides contextual understanding of Houdini's APEX rigging system:
  /apex explain  -- select an APEX node, get a plain-English explanation
  /apex overview -- high-level introduction to APEX concepts

Key principle: APEX is powerful but poorly documented.  This module bridges
the gap between Houdini's sparse tooltips and real artist understanding.

Outside Houdini the module still imports cleanly -- gather functions return
minimal dicts immediately.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Houdini import guard
# ---------------------------------------------------------------------------

_HOU_AVAILABLE = False
try:
    import hou  # type: ignore[import-untyped]

    _HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]


# ============================================================================
# 1. APEX Concept Reference
# ============================================================================

APEX_CONCEPTS: Dict[str, Dict[str, Any]] = {
    "apex_graph": {
        "title": "APEX Graph",
        "what_artists_think": "Some kind of VOP network?",
        "what_it_is": (
            "An execution program stored as geometry. Think of it as a "
            "visual script that travels with your scene as packed geometry "
            "data. Unlike VOPs which compile to VEX, APEX graphs stay as "
            "inspectable geometry you can debug, layer, and compose."
        ),
        "mental_model": (
            "VEX wrangles are text programs. APEX graphs are visual "
            "programs stored AS geometry. They're inspectable, composable, "
            "and travel with your scene. You can unpack them, view their "
            "nodes, and even edit them procedurally."
        ),
        "related": ["invoke", "packed_folder", "apex_network"],
    },
    "invoke": {
        "title": "APEX Invoke SOP",
        "what_artists_think": "Runs something?",
        "what_it_is": (
            "Executes an APEX graph on input geometry. Input 0 = the data "
            "to process (your skeleton, mesh, etc). Input 1 = the APEX "
            "graph (as packed geo) that describes the operations to perform."
        ),
        "mental_model": (
            "Think of Invoke as a 'run program' button. The program comes "
            "in as geometry on input 1. The data to transform comes in on "
            "input 0. It's like a for-each loop that applies graph logic "
            "to your rig data every frame."
        ),
        "related": ["apex_graph", "rig_execution"],
    },
    "packed_folder": {
        "title": "Packed Folder Structure",
        "what_artists_think": "Just a group or container?",
        "what_it_is": (
            "A hierarchical container for rig components, stored as packed "
            "geometry primitives. Each folder can hold APEX graphs, "
            "skeleton data, shapes, and other folders. It's how APEX "
            "organizes a character into logical sections (body, face, "
            "fingers, etc)."
        ),
        "mental_model": (
            "Like a file system for your rig. '/Base/Skeleton' holds joint "
            "transforms, '/Base/ControlChannels' holds animator controls, "
            "'/Rig' holds the APEX graphs that connect them. The hierarchy "
            "IS the rig structure."
        ),
        "related": ["character_definition", "apex_graph"],
    },
    "rig_logic": {
        "title": "Rig Logic (Build Phase)",
        "what_artists_think": "The rig itself?",
        "what_it_is": (
            "APEX graphs that CONSTRUCT the rig -- they define what "
            "controls exist, how joints are connected, and what "
            "constraints to use. Rig logic runs once (or when the rig "
            "structure changes), not every frame. It builds the execution "
            "graph that runs per-frame."
        ),
        "mental_model": (
            "Rig logic is the architect's blueprint. It doesn't move "
            "anything -- it decides WHAT will move and HOW. The output "
            "is an APEX graph that the Invoke SOP runs every frame."
        ),
        "related": ["rig_execution", "autorig", "character_definition"],
    },
    "rig_execution": {
        "title": "Rig Execution (Per-Frame Evaluation)",
        "what_artists_think": "When the rig actually moves?",
        "what_it_is": (
            "The per-frame evaluation of the APEX graph that rig logic "
            "built. This is where controls drive joints, constraints "
            "solve, and deformers run. The Invoke SOP handles this -- it "
            "takes the built graph and evaluates it every frame."
        ),
        "mental_model": (
            "If rig logic is the blueprint, execution is the building "
            "doing its job. Every frame, the Invoke SOP runs the graph: "
            "read controls -> solve constraints -> update joints -> "
            "deform mesh. Fast because the graph is pre-built."
        ),
        "related": ["rig_logic", "invoke", "solvers"],
    },
    "autorig": {
        "title": "APEX Autorig Component",
        "what_artists_think": "Auto-rigging tool?",
        "what_it_is": (
            "Pre-built APEX graphs for standard rig tasks -- FK chains, "
            "IK solvers, twist extractors, space switching. They're not "
            "black boxes: each autorig component is an APEX graph you can "
            "inspect, modify, or replace entirely."
        ),
        "mental_model": (
            "Like shelf tools but for rigging. 'apex::sop::TransformObject' "
            "creates a transform control, 'apex::sop::FK' builds an FK "
            "chain. They output APEX graphs you can wire together. Think "
            "of them as rig building blocks."
        ),
        "related": ["rig_logic", "apex_graph", "constraints"],
    },
    "character_definition": {
        "title": "Character Definition",
        "what_artists_think": "Character setup?",
        "what_it_is": (
            "A structured packed folder hierarchy that defines the complete "
            "rig structure. It follows a convention: '/Base' holds the "
            "skeleton and shapes, '/Rig' holds the APEX logic graphs, "
            "and the Invoke SOP assembles and evaluates them together."
        ),
        "mental_model": (
            "A character definition is the 'contract' that all rig "
            "components agree on. It says: these joints exist at these "
            "paths, these controls drive them, and these graphs connect "
            "them. Everything references the same hierarchy."
        ),
        "related": ["packed_folder", "rig_logic", "kinefx_skeleton"],
    },
    "apex_network": {
        "title": "APEX Network",
        "what_artists_think": "Like a VOP network for rigging?",
        "what_it_is": (
            "A network of APEX nodes that define operations -- similar to "
            "VOPs but specifically for rigging and character work. APEX "
            "nodes operate on typed ports (transforms, arrays, strings) "
            "and compile into an APEX graph stored as geometry."
        ),
        "mental_model": (
            "VOPs compile to VEX code. APEX networks compile to APEX "
            "graphs (geometry). The key difference: APEX graphs are "
            "data you can inspect, layer, and compose. You can even "
            "build APEX networks procedurally from SOPs."
        ),
        "related": ["apex_graph", "invoke"],
    },
    "kinefx_skeleton": {
        "title": "KineFX Skeleton",
        "what_artists_think": "Bones? Joints?",
        "what_it_is": (
            "A point-based skeleton where each point is a joint. Joint "
            "hierarchy is defined by point connectivity (polygon edges "
            "between points). Transforms are stored as point attributes. "
            "APEX builds on KineFX skeletons as its data foundation."
        ),
        "mental_model": (
            "Forget the old Object-level bones. In KineFX, joints are "
            "points. Bones are edges. The skeleton is just geometry with "
            "special attributes ('transform', 'name'). APEX reads this "
            "geometry and rigs it."
        ),
        "related": ["character_definition", "apex_graph"],
    },
    "control_channels": {
        "title": "Control Channels",
        "what_artists_think": "Animator controls?",
        "what_it_is": (
            "Named parameters that animators manipulate to drive the rig. "
            "In APEX, control channels live inside the packed folder "
            "hierarchy (typically under '/Base/ControlChannels'). The rig "
            "logic graphs read these channels and feed them into "
            "constraints and solvers."
        ),
        "mental_model": (
            "Control channels are the rig's public API. Animators only "
            "see and keyframe these. Everything else (joint transforms, "
            "constraint weights, solver inputs) is internal plumbing "
            "driven by the APEX graph."
        ),
        "related": ["rig_logic", "character_definition", "packed_folder"],
    },
    "constraints": {
        "title": "APEX Constraints",
        "what_artists_think": "Like old CHOP constraints?",
        "what_it_is": (
            "Transform relationships defined inside APEX graphs. Parent "
            "constraints, aim constraints, blend constraints -- they all "
            "exist as APEX graph nodes that read source transforms and "
            "write target transforms. Much faster than CHOP constraints "
            "and fully inspectable."
        ),
        "mental_model": (
            "Same concept as traditional constraints, but expressed as "
            "nodes inside an APEX graph rather than separate CHOP "
            "networks. They evaluate as part of the rig graph, so "
            "ordering is explicit and predictable."
        ),
        "related": ["rig_execution", "solvers", "autorig"],
    },
    "solvers": {
        "title": "APEX Solvers (IK, etc.)",
        "what_artists_think": "IK?",
        "what_it_is": (
            "Iterative or analytical solvers that run inside APEX graphs. "
            "IK solvers find joint rotations to reach a target. They're "
            "APEX graph nodes with typed inputs (chain root, chain tip, "
            "target transform) and outputs (solved joint transforms)."
        ),
        "mental_model": (
            "Same IK you know, but running inside the APEX graph. The "
            "solver is a node in the graph, not a separate network. "
            "This means IK, FK, and blending can all live in one "
            "unified graph with clear data flow."
        ),
        "related": ["constraints", "rig_execution", "autorig"],
    },
}


# ============================================================================
# 2. Node context gathering
# ============================================================================

# Node type patterns for APEX classification.
_APEX_TYPE_PATTERNS: Dict[str, List[str]] = {
    "invoke": ["invoke", "apex::sop::invoke"],
    "autorig": [
        "apex::sop::rig",
        "apex::sop::fk",
        "apex::sop::ik",
        "apex::sop::transformobject",
        "apex::sop::blendtransform",
        "apex::sop::parentconstraint",
        "apex::sop::aimconstraint",
    ],
    "packfolder": ["packfolder", "pack", "packfolderpath"],
    "apex_network": ["apex::sop::apexedit", "apexedit"],
    "kinefx": [
        "kinefx",
        "skeleton",
        "rigpose",
        "jointcapture",
        "bonedeform",
        "rig_doctor",
        "configurejoints",
    ],
}


def _classify_apex_type(type_name: str) -> str:
    """Return the APEX sub-type for a node type name."""
    lower = type_name.lower()
    for apex_type, patterns in _APEX_TYPE_PATTERNS.items():
        for pat in patterns:
            if pat in lower:
                return apex_type
    if "apex" in lower:
        return "apex_network"
    return "other"


def _is_apex_related(type_name: str) -> bool:
    """Return True if *type_name* belongs to the APEX/KineFX ecosystem."""
    lower = type_name.lower()
    if "apex" in lower:
        return True
    apex_type = _classify_apex_type(lower)
    return apex_type != "other"


def _gather_graph_info(node: Any) -> Dict[str, Any]:
    """Best-effort inspection of an APEX graph on input 1 of an invoke node."""
    info: Dict[str, Any] = {
        "has_graph_input": False,
        "graph_prim_count": 0,
        "graph_node_names": [],
    }
    if not _HOU_AVAILABLE or node is None:
        return info
    try:
        inputs = node.inputs()
        if len(inputs) < 2 or inputs[1] is None:
            return info
        graph_node = inputs[1]
        geo = graph_node.geometry()
        if geo is None:
            return info
        info["has_graph_input"] = True
        prims = geo.prims()
        info["graph_prim_count"] = len(prims)
        # Try to extract names from packed prims (graph operations)
        names = []
        for prim in prims[:50]:  # Cap to avoid huge graphs
            try:
                name_attr = prim.attribValue("name")
                if name_attr:
                    names.append(str(name_attr))
            except Exception:
                pass
        info["graph_node_names"] = names[:30]
    except Exception:
        pass
    return info


def _gather_skeleton_info(geo: Any) -> Dict[str, Any]:
    """Check for KineFX skeleton attributes on geometry."""
    info: Dict[str, Any] = {
        "has_skeleton": False,
        "joint_count": 0,
        "has_transform_attr": False,
        "has_name_attr": False,
        "has_parent_attr": False,
        "joint_names": [],
        "hierarchy_depth": 0,
    }
    if geo is None:
        return info
    try:
        point_attribs = [a.name() for a in geo.pointAttribs()]
        info["has_transform_attr"] = "transform" in point_attribs
        info["has_name_attr"] = "name" in point_attribs
        info["has_parent_attr"] = "parent" in point_attribs

        if info["has_transform_attr"] or info["has_name_attr"]:
            info["has_skeleton"] = True
            points = geo.points()
            info["joint_count"] = len(points)

            if info["has_name_attr"]:
                names = []
                for pt in points[:100]:
                    try:
                        names.append(pt.attribValue("name"))
                    except Exception:
                        pass
                info["joint_names"] = names[:50]

            # Estimate hierarchy depth from parent attribute
            if info["has_parent_attr"]:
                max_depth = 0
                for pt in points[:100]:
                    try:
                        depth = 0
                        current = pt.attribValue("parent")
                        seen = set()
                        while current >= 0 and current not in seen and depth < 50:
                            seen.add(current)
                            depth += 1
                            current = points[current].attribValue("parent")
                        max_depth = max(max_depth, depth)
                    except Exception:
                        break
                info["hierarchy_depth"] = max_depth
    except Exception:
        pass
    return info


def _gather_packed_info(geo: Any) -> Dict[str, Any]:
    """Inspect packed primitives for folder structure."""
    info: Dict[str, Any] = {
        "packed_prim_count": 0,
        "folder_names": [],
    }
    if geo is None:
        return info
    try:
        prims = geo.prims()
        packed_count = 0
        folder_names = []
        for prim in prims[:200]:
            try:
                if prim.type().name() == "PackedGeometry":
                    packed_count += 1
                    name_val = prim.attribValue("name") if "name" in [
                        a.name() for a in geo.primAttribs()
                    ] else None
                    if name_val:
                        folder_names.append(str(name_val))
            except Exception:
                pass
        info["packed_prim_count"] = packed_count
        info["folder_names"] = folder_names[:50]
    except Exception:
        pass
    return info


def _gather_non_default_parms(node: Any) -> List[Dict[str, Any]]:
    """Return parameters that differ from their defaults."""
    parms: List[Dict[str, Any]] = []
    if not _HOU_AVAILABLE or node is None:
        return parms
    try:
        for parm in node.parms():
            try:
                if not parm.isAtDefault():
                    parms.append({
                        "name": parm.name(),
                        "label": parm.description(),
                        "value": str(parm.eval()),
                    })
            except Exception:
                pass
    except Exception:
        pass
    return parms[:40]


def _gather_output_geo(node: Any) -> Dict[str, Any]:
    """Compact summary of the node's output geometry."""
    info: Dict[str, Any] = {
        "point_count": 0,
        "prim_count": 0,
        "attributes": {},
    }
    if not _HOU_AVAILABLE or node is None:
        return info
    try:
        geo = node.geometry()
        if geo is None:
            return info
        info["point_count"] = len(geo.points())
        info["prim_count"] = len(geo.prims())
        attribs: Dict[str, List[str]] = {}
        for label, accessor in (
            ("point", "pointAttribs"),
            ("prim", "primAttribs"),
            ("vertex", "vertexAttribs"),
            ("detail", "globalAttribs"),
        ):
            try:
                names = [a.name() for a in getattr(geo, accessor)()]
                if names:
                    attribs[label] = names
            except Exception:
                pass
        info["attributes"] = attribs
    except Exception:
        pass
    return info


def gather_apex_context(node_path: str) -> Dict[str, Any]:
    """Gather APEX-specific context from a node at *node_path*.

    Returns a dict with node info, APEX classification, graph inspection,
    skeleton info, packed folder info, parameters, connections, and output
    geometry.  Works outside Houdini (returns minimal dict).
    """
    context: Dict[str, Any] = {
        "node_path": node_path,
        "node_type": "",
        "is_apex_node": False,
        "apex_type": "other",
        "graph_info": {},
        "skeleton_info": {},
        "packed_info": {},
        "non_default_parms": [],
        "input_connections": [],
        "output_geo": {},
        "errors": [],
    }

    if not _HOU_AVAILABLE:
        context["errors"].append("hou module not available")
        return context

    node = hou.node(node_path)
    if node is None:
        context["errors"].append(f"Node not found: {node_path}")
        return context

    try:
        type_name = node.type().name()
        context["node_type"] = type_name
        context["is_apex_node"] = _is_apex_related(type_name)
        context["apex_type"] = _classify_apex_type(type_name)
    except Exception as exc:
        context["errors"].append(f"Failed to read node type: {exc}")
        return context

    # Graph info (invoke nodes)
    if context["apex_type"] == "invoke":
        context["graph_info"] = _gather_graph_info(node)

    # Output geometry
    context["output_geo"] = _gather_output_geo(node)

    # Skeleton info from output geo
    try:
        geo = node.geometry()
        context["skeleton_info"] = _gather_skeleton_info(geo)
    except Exception:
        pass

    # Packed folder info
    try:
        geo = node.geometry()
        context["packed_info"] = _gather_packed_info(geo)
    except Exception:
        pass

    # Non-default parameters
    context["non_default_parms"] = _gather_non_default_parms(node)

    # Input connections
    try:
        inputs = node.inputs()
        conns = []
        for i, inp in enumerate(inputs):
            if inp is not None:
                conns.append({
                    "index": i,
                    "path": inp.path(),
                    "type": inp.type().name(),
                })
        context["input_connections"] = conns
    except Exception:
        pass

    # Node errors/warnings
    try:
        errors = node.errors()
        warnings = node.warnings()
        if errors:
            context["errors"].extend(errors)
        if warnings:
            context["errors"].extend([f"WARNING: {w}" for w in warnings])
    except Exception:
        pass

    return context


# ============================================================================
# 3. Prompt builders
# ============================================================================

def _relevant_concepts(apex_type: str) -> List[str]:
    """Return concept keys relevant to a given apex_type."""
    mapping: Dict[str, List[str]] = {
        "invoke": ["invoke", "apex_graph", "rig_execution"],
        "autorig": ["autorig", "rig_logic", "apex_graph", "constraints"],
        "packfolder": ["packed_folder", "character_definition"],
        "apex_network": ["apex_network", "apex_graph"],
        "kinefx": ["kinefx_skeleton", "character_definition", "control_channels"],
        "other": ["apex_graph", "invoke", "packed_folder"],
    }
    return mapping.get(apex_type, mapping["other"])


def _format_concepts_for_prompt(concept_keys: List[str]) -> str:
    """Format concept entries as reference text for the system prompt."""
    lines = []
    for key in concept_keys:
        concept = APEX_CONCEPTS.get(key)
        if concept is None:
            continue
        lines.append(f"### {concept['title']}")
        lines.append(f"What it is: {concept['what_it_is']}")
        lines.append(f"Mental model: {concept['mental_model']}")
        lines.append("")
    return "\n".join(lines)


def build_apex_explain_prompt(context: Dict[str, Any]) -> str:
    """Build a system prompt for explaining an APEX node.

    Includes relevant APEX concept references based on the node type and
    instructions for a friendly, jargon-explained teaching style.
    """
    apex_type = context.get("apex_type", "other")
    relevant = _relevant_concepts(apex_type)
    concept_text = _format_concepts_for_prompt(relevant)

    return (
        "You are a senior rigger explaining APEX to someone learning it for "
        "the first time. You have deep knowledge of Houdini's APEX rigging "
        "system, KineFX, and traditional rigging workflows.\n"
        "\n"
        "## Your approach\n"
        "- Start with what this SPECIFIC node is doing in this scene\n"
        "- Then explain the concept behind it\n"
        "- Use the mental models provided below -- they bridge old knowledge "
        "to new concepts\n"
        "- Never use jargon without explaining it\n"
        "- If something is complex, break it into steps\n"
        "- Compare to familiar Houdini concepts when possible (VOPs, CHOPs, "
        "Object-level rigs)\n"
        "- Be honest about what is hard -- APEX has a learning curve\n"
        "\n"
        "## APEX Reference (use these mental models)\n"
        f"{concept_text}\n"
        "## Formatting\n"
        "- Use short paragraphs\n"
        "- Bold key terms on first use\n"
        "- Use analogies freely\n"
    )


def build_apex_messages(context: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build messages for a Claude API call to explain an APEX node.

    Returns a list of message dicts with role and content keys.
    """
    lines = [f"Explain this APEX node: **{context.get('node_path', '?')}**\n"]
    lines.append(f"Node type: `{context.get('node_type', 'unknown')}`")
    lines.append(f"APEX classification: {context.get('apex_type', 'other')}")
    lines.append("")

    # Non-default parameters
    parms = context.get("non_default_parms", [])
    if parms:
        lines.append("### Non-default parameters")
        for p in parms:
            lines.append(f"- **{p.get('label', p.get('name', '?'))}** "
                         f"(`{p.get('name', '?')}`): {p.get('value', '?')}")
        lines.append("")

    # Input connections
    conns = context.get("input_connections", [])
    if conns:
        lines.append("### Input connections")
        for c in conns:
            lines.append(f"- Input {c.get('index', '?')}: "
                         f"`{c.get('path', '?')}` ({c.get('type', '?')})")
        lines.append("")

    # Graph info (for invoke nodes)
    graph = context.get("graph_info", {})
    if graph.get("has_graph_input"):
        lines.append("### APEX Graph on input 1")
        lines.append(f"- Graph prim count: {graph.get('graph_prim_count', 0)}")
        names = graph.get("graph_node_names", [])
        if names:
            lines.append(f"- Graph operations: {', '.join(names[:15])}")
            if len(names) > 15:
                lines.append(f"  ... and {len(names) - 15} more")
        lines.append("")

    # Skeleton info
    skel = context.get("skeleton_info", {})
    if skel.get("has_skeleton"):
        lines.append("### Skeleton data")
        lines.append(f"- Joint count: {skel.get('joint_count', 0)}")
        lines.append(f"- Hierarchy depth: {skel.get('hierarchy_depth', 0)}")
        joint_names = skel.get("joint_names", [])
        if joint_names:
            display = joint_names[:10]
            lines.append(f"- Joints: {', '.join(display)}")
            if len(joint_names) > 10:
                lines.append(f"  ... and {len(joint_names) - 10} more")
        lines.append("")

    # Packed info
    packed = context.get("packed_info", {})
    if packed.get("packed_prim_count", 0) > 0:
        lines.append("### Packed folder structure")
        lines.append(f"- Packed prims: {packed['packed_prim_count']}")
        folders = packed.get("folder_names", [])
        if folders:
            lines.append(f"- Folders: {', '.join(folders[:15])}")
        lines.append("")

    # Output geometry
    out = context.get("output_geo", {})
    if out.get("point_count", 0) > 0 or out.get("prim_count", 0) > 0:
        lines.append("### Output geometry")
        lines.append(f"- Points: {out.get('point_count', 0)}, "
                     f"Prims: {out.get('prim_count', 0)}")
        attrs = out.get("attributes", {})
        for cls, names in attrs.items():
            lines.append(f"- {cls} attrs: {', '.join(names[:15])}")
        lines.append("")

    # Errors
    errors = context.get("errors", [])
    if errors:
        lines.append("### Errors/warnings on this node")
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    user_content = "\n".join(lines)

    return [
        {"role": "user", "content": user_content},
    ]


# ============================================================================
# 4. Overview prompt
# ============================================================================

def build_apex_overview_prompt() -> str:
    """System prompt for /apex overview -- a comprehensive APEX introduction.

    Targets a Houdini artist who knows KineFX but hasn't used APEX yet.
    """
    # Include all concepts as reference
    all_keys = list(APEX_CONCEPTS.keys())
    concept_text = _format_concepts_for_prompt(all_keys)

    return (
        "You are a senior Houdini TD giving a workshop introduction to APEX.\n"
        "\n"
        "Your audience knows KineFX (point-based skeletons, SOPs-level "
        "rigging) but has NOT used APEX yet. They're experienced Houdini "
        "artists, not beginners.\n"
        "\n"
        "## Cover these topics in order\n"
        "1. What APEX is and why SideFX built it (the problem it solves)\n"
        "2. How it differs from KineFX (APEX builds ON KineFX, doesn't "
        "replace it)\n"
        "3. The key mental shift: graphs as geometry (not compiled code)\n"
        "4. The build vs execute split (rig logic vs rig execution)\n"
        "5. Packed folders as rig organization\n"
        "6. The Invoke SOP as the 'run' button\n"
        "7. Where to start: simple FK chain as first project\n"
        "\n"
        "## Style guide\n"
        "- Practical, not theoretical. Every concept gets a 'here is when "
        "you would use this' example.\n"
        "- Compare to things they already know (VOPs, CHOPs, Object-level "
        "rigs, KineFX SOPs).\n"
        "- Be honest about the learning curve. APEX is powerful but has "
        "rough edges.\n"
        "- Use short paragraphs and headers.\n"
        "- Bold key terms on first use.\n"
        "\n"
        "## APEX Concept Reference\n"
        f"{concept_text}\n"
    )


# ============================================================================
# 5. HTML concept formatter
# ============================================================================

def format_concept_html(concept_key: str) -> str:
    """Format an APEX concept as HTML for inline display in the panel.

    Returns a styled HTML snippet with title, misconception vs reality,
    mental model, and related concepts.  Returns an error message if the
    concept key is not found.
    """
    concept = APEX_CONCEPTS.get(concept_key)
    if concept is None:
        return (
            f'<div style="color:#cc6666;padding:8px;">'
            f'Unknown APEX concept: <b>{concept_key}</b>. '
            f'Available: {", ".join(sorted(APEX_CONCEPTS.keys()))}'
            f'</div>'
        )

    title = concept["title"]
    think = concept["what_artists_think"]
    actual = concept["what_it_is"]
    model = concept["mental_model"]
    related = concept.get("related", [])

    related_links = ", ".join(
        f'<span style="color:#7799cc;">{APEX_CONCEPTS.get(r, {}).get("title", r)}</span>'
        for r in related
    )

    return (
        f'<div style="font-family:sans-serif;padding:12px;'
        f'background:#2a2a2a;border-radius:6px;margin:6px 0;">'
        f'<div style="font-size:18px;font-weight:bold;color:#dddddd;'
        f'margin-bottom:8px;">{title}</div>'
        f'<div style="margin-bottom:10px;">'
        f'<div style="color:#aa8855;font-size:13px;margin-bottom:2px;">'
        f'What artists think:</div>'
        f'<div style="color:#ccaa77;font-style:italic;margin-bottom:6px;">'
        f'"{think}"</div>'
        f'<div style="color:#88aa66;font-size:13px;margin-bottom:2px;">'
        f'What it actually is:</div>'
        f'<div style="color:#cccccc;margin-bottom:6px;">{actual}</div>'
        f'</div>'
        f'<div style="border-top:1px solid #444;padding-top:8px;'
        f'margin-top:4px;">'
        f'<div style="color:#8888bb;font-size:13px;margin-bottom:2px;">'
        f'Mental model:</div>'
        f'<div style="color:#bbbbbb;font-style:italic;">{model}</div>'
        f'</div>'
        + (
            f'<div style="margin-top:8px;font-size:12px;color:#666;">'
            f'Related: {related_links}</div>'
            if related else ""
        )
        + '</div>'
    )


# ============================================================================
# 6. Network-level APEX detection
# ============================================================================

def detect_apex_context(network_path: str) -> str:
    """Check if a network contains APEX or KineFX nodes.

    Returns:
        ``"apex"`` if APEX-specific nodes are found,
        ``"kinefx"`` if KineFX nodes are present but no APEX,
        ``"none"`` if neither is detected.
    """
    if not _HOU_AVAILABLE:
        return "none"

    try:
        network = hou.node(network_path)
    except Exception:
        return "none"
    if network is None:
        return "none"

    has_apex = False
    has_kinefx = False

    try:
        children = network.children()
    except Exception:
        return "none"

    for child in children:
        try:
            type_name = child.type().name().lower()
        except Exception:
            continue

        if "apex" in type_name or "invoke" in type_name:
            has_apex = True
            break  # APEX supersedes KineFX, no need to keep scanning
        if any(kw in type_name for kw in (
            "kinefx", "skeleton", "rigpose", "jointcapture",
            "bonedeform", "rig_doctor", "configurejoints",
        )):
            has_kinefx = True

    if has_apex:
        return "apex"
    if has_kinefx:
        return "kinefx"
    return "none"
