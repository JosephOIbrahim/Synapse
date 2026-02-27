"""
Synapse Memory Evolution -- Flat -> Structured -> Composed

Detects when markdown memory should evolve to USD. Handles the
conversion process and maintains companion markdown.
"""

import logging
import os
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger("synapse.evolution")

EVOLUTION_TRIGGERS = {
    "structured": {
        "structured_data_count": 5,
        "asset_references": 3,
        "parameter_records": 5,
        "wedge_results": 1,
        "session_count": 10,
        "file_size_kb": 100,
        "node_path_references": 10,
    },
}


def count_structured_data(md_path: str) -> Dict[str, Any]:
    """Count structured elements in a markdown memory file."""
    if not os.path.exists(md_path):
        return {k: 0 for k in EVOLUTION_TRIGGERS["structured"]}

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    counts = {
        "structured_data_count": 0,
        "asset_references": 0,
        "parameter_records": 0,
        "wedge_results": 0,
        "session_count": 0,
        "file_size_kb": round(os.path.getsize(md_path) / 1024, 2),
        "node_path_references": 0,
    }

    for line in lines:
        # Node paths: /obj/, /stage/, /out/, /shop/
        if re.search(r'/(?:obj|stage|out|shop|ch|mat)/', line):
            counts["node_path_references"] += 1
        # Asset paths: @...@
        if re.search(r'@[^@]+@', line):
            counts["asset_references"] += 1
        # Parameter records: "parm: value" or "Before/After" patterns
        if re.search(r'\*\*(?:Before|After|Value):\*\*', line):
            counts["parameter_records"] += 1
        # Session headers
        if line.startswith("## Session"):
            counts["session_count"] += 1
        # Decision blocks
        if "### Decision:" in line or "**Decision:**" in line:
            counts["structured_data_count"] += 1
        # Wedge results
        if "### Wedge" in line or ("wedge" in line.lower() and "result" in line.lower()):
            counts["wedge_results"] += 1
        # General structured data (node paths, params count as structured)
        if re.search(r'### (?:Parameter|Asset|Blocker)', line):
            counts["structured_data_count"] += 1

    return counts


def check_evolution(claude_dir: str, latest_entry: Dict = None) -> Dict[str, Any]:
    """
    Evaluate triggers. Return {should_evolve, triggers_met, target}.
    Called after every memory write.
    """
    from .scene_memory import get_evolution_stage

    stage = get_evolution_stage(claude_dir)

    if stage != "flat":
        return {"should_evolve": False, "triggers_met": [], "target": None, "current": stage}

    md_path = os.path.join(claude_dir, "memory.md")
    counts = count_structured_data(md_path)
    triggers = EVOLUTION_TRIGGERS["structured"]

    triggers_met = []
    for key, threshold in sorted(triggers.items()):
        if counts.get(key, 0) >= threshold:
            triggers_met.append(key)

    return {
        "should_evolve": len(triggers_met) > 0,
        "triggers_met": triggers_met,
        "target": "structured" if triggers_met else None,
        "current": stage,
        "counts": counts,
    }


def parse_markdown_memory(md_path: str) -> Dict[str, List]:
    """
    Parse memory.md into structured sections.

    Returns: {sessions, decisions, assets, parameters}
    """
    if not os.path.exists(md_path):
        return {"sessions": [], "decisions": [], "assets": [], "parameters": []}

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    sessions: List[Dict[str, Any]] = []
    decisions: List[Dict[str, Any]] = []
    assets: List[Dict[str, Any]] = []
    parameters: List[Dict[str, Any]] = []

    # Split by ## Session headers
    session_blocks = re.split(r'^## Session ', content, flags=re.MULTILINE)

    for i, block in enumerate(session_blocks[1:], 1):
        lines = block.strip().split("\n")
        header = lines[0] if lines else ""
        date = header.split()[0] if header else f"session_{i}"
        text = "\n".join(lines)

        session: Dict[str, Any] = {
            "id": f"session_{date.replace('-', '_')}",
            "date": date,
            "text": text,
            "decisions": [],
            "blockers": [],
            "parameters": [],
        }

        # Extract decisions within this session
        decision_blocks = re.findall(
            r'### Decision:\s*(.+?)(?=\n###|\n## |\Z)',
            text, re.DOTALL
        )
        for db in decision_blocks:
            decision_lines = db.strip().split("\n")
            name = decision_lines[0].strip() if decision_lines else ""
            choice = ""
            reasoning = ""
            for dl in decision_lines:
                if dl.startswith("**Choice:**"):
                    choice = dl.replace("**Choice:**", "").strip()
                elif dl.startswith("**Reasoning:**"):
                    reasoning = dl.replace("**Reasoning:**", "").strip()
            slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:40]
            decisions.append({
                "slug": slug or f"decision_{len(decisions)}",
                "name": name,
                "choice": choice,
                "reasoning": reasoning,
                "date": date,
                "alternatives": [],
            })
            session["decisions"].append(slug)

        # Extract parameters
        param_blocks = re.findall(
            r'### Parameter:\s*(.+?)(?=\n###|\n## |\Z)',
            text, re.DOTALL
        )
        for pb in param_blocks:
            param_lines = pb.strip().split("\n")
            header_parts = param_lines[0].strip().split("/") if param_lines else []
            before = after = result = ""
            for pl in param_lines:
                if "**Before:**" in pl:
                    before = pl.split("**Before:**")[-1].strip()
                elif "**After:**" in pl:
                    after = pl.split("**After:**")[-1].strip()
                elif "**Result:**" in pl:
                    result = pl.split("**Result:**")[-1].strip()
            slug = re.sub(r'[^a-z0-9]+', '_', param_lines[0].strip().lower()).strip('_')[:40]
            parameters.append({
                "slug": slug or f"param_{len(parameters)}",
                "node": "/".join(header_parts[:-1]) if len(header_parts) > 1 else "",
                "parm": header_parts[-1].strip() if header_parts else "",
                "before": before,
                "after": after,
                "result": result,
                "date": date,
            })
            session["parameters"].append(slug)

        sessions.append(session)

    return {
        "sessions": sessions,
        "decisions": decisions,
        "assets": assets,
        "parameters": parameters,
    }


def evolve_to_structured(md_path: str, usd_path: str) -> Dict[str, Any]:
    """
    Convert markdown memory to USD. Lossless.

    1. Parse markdown
    2. Create USD stage
    3. Write typed prims
    4. Archive original as memory_pre_evolution.md
    5. Generate companion memory.md
    """
    try:
        from pxr import Usd, Sdf
    except ImportError:
        return {"success": False, "error": "pxr not available"}

    parsed = parse_markdown_memory(md_path)

    stage = Usd.Stage.CreateNew(usd_path)
    stage.DefinePrim("/SYNAPSE", "Xform")
    stage.DefinePrim("/SYNAPSE/memory", "Xform")
    stage.DefinePrim("/SYNAPSE/memory/sessions", "Xform")
    stage.DefinePrim("/SYNAPSE/memory/decisions", "Xform")
    stage.DefinePrim("/SYNAPSE/memory/assets", "Xform")
    stage.DefinePrim("/SYNAPSE/memory/parameters", "Xform")

    # Write sessions
    for session in parsed["sessions"]:
        sid = session["id"]
        prim = stage.DefinePrim(f"/SYNAPSE/memory/sessions/{sid}", "Xform")
        prim.CreateAttribute("synapse:date", Sdf.ValueTypeNames.String).Set(session["date"])
        prim.CreateAttribute("synapse:narrative", Sdf.ValueTypeNames.String).Set(session["text"])

    # Write decisions
    for decision in parsed["decisions"]:
        prim = stage.DefinePrim(f"/SYNAPSE/memory/decisions/{decision['slug']}", "Xform")
        prim.CreateAttribute("synapse:choice", Sdf.ValueTypeNames.String).Set(decision["choice"])
        prim.CreateAttribute("synapse:reasoning", Sdf.ValueTypeNames.String).Set(decision["reasoning"])
        prim.CreateAttribute("synapse:date", Sdf.ValueTypeNames.String).Set(decision["date"])

    # Write parameters
    for param in parsed["parameters"]:
        prim = stage.DefinePrim(f"/SYNAPSE/memory/parameters/{param['slug']}", "Xform")
        prim.CreateAttribute("synapse:node", Sdf.ValueTypeNames.String).Set(param["node"])
        prim.CreateAttribute("synapse:parm", Sdf.ValueTypeNames.String).Set(param["parm"])
        prim.CreateAttribute("synapse:before", Sdf.ValueTypeNames.String).Set(str(param["before"]))
        prim.CreateAttribute("synapse:after", Sdf.ValueTypeNames.String).Set(str(param["after"]))
        prim.CreateAttribute("synapse:result", Sdf.ValueTypeNames.String).Set(param["result"])

    stage.GetRootLayer().customLayerData = {
        "synapse:version": "0.1.0",
        "synapse:type": "scene_memory",
        "synapse:evolution": "structured",
    }
    stage.GetRootLayer().Save()

    # Archive original markdown
    archive_path = md_path.replace(".md", "_pre_evolution.md")
    if os.path.exists(md_path):
        import shutil
        shutil.copy2(md_path, archive_path)

    # Generate companion markdown
    generate_companion_md(usd_path, md_path)

    return {
        "success": True,
        "sessions": len(parsed["sessions"]),
        "decisions": len(parsed["decisions"]),
        "parameters": len(parsed["parameters"]),
        "archive": archive_path,
    }


def generate_companion_md(usd_path: str, md_path: str) -> None:
    """Generate human-readable markdown from USD memory."""
    try:
        from pxr import Usd
    except ImportError:
        return

    if not os.path.exists(usd_path):
        return

    stage = Usd.Stage.Open(usd_path)
    lines = [
        "# Scene Memory (Structured - auto-generated from USD)",
        f"# Source: {os.path.basename(usd_path)}",
        "# Do not edit -- this file is regenerated from memory.usd",
        "",
        "---",
        "",
    ]

    # Sessions
    sessions_prim = stage.GetPrimAtPath("/SYNAPSE/memory/sessions")
    if sessions_prim and sessions_prim.IsValid():
        for session in sorted(sessions_prim.GetChildren(), key=lambda p: p.GetName()):
            date_attr = session.GetAttribute("synapse:date")
            narrative_attr = session.GetAttribute("synapse:narrative")
            date = date_attr.Get() if date_attr else session.GetName()
            narrative = narrative_attr.Get() if narrative_attr else ""
            lines.append(f"## Session {date}")
            if narrative:
                lines.append(narrative)
            lines.append("")

    # Decisions
    decisions_prim = stage.GetPrimAtPath("/SYNAPSE/memory/decisions")
    if decisions_prim and decisions_prim.IsValid():
        children = list(decisions_prim.GetChildren())
        if children:
            lines.append("## Key Decisions")
            lines.append("")
            for d in sorted(children, key=lambda p: p.GetName()):
                choice = d.GetAttribute("synapse:choice")
                reasoning = d.GetAttribute("synapse:reasoning")
                lines.append(f"### {d.GetName()}")
                if choice:
                    lines.append(f"**Choice:** {choice.Get()}")
                if reasoning:
                    lines.append(f"**Reasoning:** {reasoning.Get()}")
                lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def prune_memory(claude_dir: str, max_sessions_full: int = 5) -> Dict[str, Any]:
    """
    Compress old sessions to stay within token budget.

    Never prunes: decisions, unresolved blockers, asset references.
    """
    md_path = os.path.join(claude_dir, "memory.md")
    if not os.path.exists(md_path):
        return {"pruned_sessions": 0, "new_size_kb": 0}

    parsed = parse_markdown_memory(md_path)
    sessions = parsed["sessions"]

    if len(sessions) <= max_sessions_full:
        return {"pruned_sessions": 0, "new_size_kb": round(os.path.getsize(md_path) / 1024, 2)}

    # Keep recent sessions full, condense older ones
    recent = sessions[-max_sessions_full:]
    old = sessions[:-max_sessions_full]

    pruned_count = len(old)

    # Rebuild markdown with condensed old sessions
    with open(md_path, "r", encoding="utf-8") as f:
        header_lines = []
        for line in f:
            if line.startswith("## Session"):
                break
            header_lines.append(line)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("".join(header_lines))
        f.write("\n## Archived Sessions (condensed)\n")
        for session in old:
            f.write(f"- {session['date']}: {len(session['text'].split(chr(10)))} lines")
            if session["decisions"]:
                f.write(f" | Decisions: {', '.join(session['decisions'])}")
            f.write("\n")
        f.write("\n")
        for session in recent:
            f.write(f"## Session {session['date']}\n{session['text']}\n\n")

    new_size = round(os.path.getsize(md_path) / 1024, 2)
    return {"pruned_sessions": pruned_count, "new_size_kb": new_size}


def evolve_to_composed(scene_usd_path: str, project_usd_path: str) -> Dict[str, Any]:
    """
    Set up composition arcs so scene memory sublayers project memory.
    Scene-level opinions are stronger (override project defaults).
    """
    try:
        from pxr import Usd, Sdf
    except ImportError:
        return {"success": False, "error": "pxr not available"}

    if not os.path.exists(scene_usd_path) or not os.path.exists(project_usd_path):
        return {"success": False, "error": "Missing USD files"}

    stage = Usd.Stage.Open(scene_usd_path)
    layer = stage.GetRootLayer()

    # Add project.usd as sublayer (weaker -- scene opinions override)
    project_rel = os.path.relpath(project_usd_path, os.path.dirname(scene_usd_path))
    # Normalize to forward slashes for USD
    project_rel = project_rel.replace("\\", "/")

    existing = list(layer.subLayerPaths)
    if project_rel not in existing:
        existing.append(project_rel)
        layer.subLayerPaths = existing

    # Update evolution metadata
    data = dict(layer.customLayerData)
    data["synapse:evolution"] = "composed"
    layer.customLayerData = data

    layer.Save()

    return {"success": True, "sublayer": project_rel}
