"""
Synapse Scene Memory -- Living Memory System

Persistent, layered memory that lives alongside Houdini scene files.
Memory evolves: Charmander (markdown) -> Charmeleon (USD) -> Charizard (composed USD).

This module handles all file operations for the scene memory system.
Every function is idempotent, non-destructive, and encoding-safe.
"""

import logging
import os
import threading
import time
from typing import Dict, List, Optional, Any

logger = logging.getLogger("synapse.scene_memory")

# Schema version for memory files
SCHEMA_VERSION = "0.1.0"

# Thread-safe file locking for concurrent writes
_file_locks: Dict[str, threading.Lock] = {}
_file_locks_lock = threading.Lock()


def _get_file_lock(path: str) -> threading.Lock:
    """Get or create a threading lock for a file path."""
    with _file_locks_lock:
        if path not in _file_locks:
            _file_locks[path] = threading.Lock()
        return _file_locks[path]


# =============================================================================
# DIRECTORY & FILE MANAGEMENT
# =============================================================================

def ensure_scene_structure(hip_path: str, job_path: str) -> Dict[str, str]:
    """
    Create claude/ directories at $JOB and $HIP levels if they don't exist.
    Seed memory.md and agent.usd if they don't exist.

    Returns paths dict:
        {project_dir, scene_dir, project_md, scene_md, agent_usd}

    Idempotent: safe to call repeatedly. Never overwrites existing files.
    """
    hip_path = os.path.normpath(hip_path)
    job_path = os.path.normpath(job_path)

    hip_dir = os.path.dirname(hip_path) if os.path.isfile(hip_path) else hip_path
    hip_name = os.path.basename(hip_path)
    job_name = os.path.basename(job_path)

    project_dir = os.path.join(job_path, "claude")
    scene_dir = os.path.join(hip_dir, "claude")

    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(scene_dir, exist_ok=True)

    # Seed project.md
    project_md = os.path.join(project_dir, "project.md")
    if not os.path.exists(project_md):
        seed_project_md(project_md, job_name, fps=24.0)

    # Seed scene memory.md
    scene_md = os.path.join(scene_dir, "memory.md")
    if not os.path.exists(scene_md):
        seed_scene_md(scene_md, hip_name, job_name)

    # Seed agent.usd
    agent_usd = os.path.join(scene_dir, "agent.usd")
    if not os.path.exists(agent_usd):
        try:
            from .agent_state import initialize_agent_usd
            initialize_agent_usd(agent_usd)
        except ImportError:
            _seed_agent_usd_stub(agent_usd)

    paths = {
        "project_dir": project_dir,
        "scene_dir": scene_dir,
        "project_md": project_md,
        "scene_md": scene_md,
        "agent_usd": agent_usd,
    }
    logger.info("Scene structure ready: %s", scene_dir)
    return paths


def seed_project_md(path: str, job_name: str, fps: float = 24.0) -> None:
    """Create initial project.md with header and empty sections."""
    now = _now()
    content = (
        f"# Project Memory: {job_name}\n"
        f"# Created: {now}\n"
        f"# Evolution: Charmander (markdown)\n"
        f"# Schema: {SCHEMA_VERSION}\n\n---\n\n"
        f"## Pipeline Configuration\n"
        f"- **Frame Rate:** {fps}fps\n\n"
        f"## Key Decisions\n\n"
        f"## Notes\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("Seeded project.md: %s", path)


def seed_scene_md(path: str, scene_name: str, project_name: str) -> None:
    """Create initial memory.md with header."""
    now = _now()
    content = (
        f"# Scene Memory: {scene_name}\n"
        f"# Project: {project_name}\n"
        f"# Created: {now}\n"
        f"# Evolution: Charmander (markdown)\n"
        f"# Schema: {SCHEMA_VERSION}\n\n---\n\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("Seeded memory.md: %s", path)


def _seed_agent_usd_stub(path: str) -> None:
    """Create a placeholder agent.usd file. Full USD impl in Phase 2."""
    # Write a minimal USDA that can be parsed later
    content = (
        '#usda 1.0\n'
        '(\n'
        f'    customLayerData = {{\n'
        f'        string "synapse:version" = "{SCHEMA_VERSION}"\n'
        f'        string "synapse:type" = "agent_state"\n'
        f'        string "synapse:status" = "idle"\n'
        f'    }}\n'
        ')\n\n'
        'def Xform "SYNAPSE"\n'
        '{\n'
        '    def Xform "agent"\n'
        '    {\n'
        '    }\n'
        '}\n'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("Seeded agent.usd stub: %s", path)


def _now() -> str:
    """UTC timestamp string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# =============================================================================
# MEMORY READ/WRITE OPERATIONS
# =============================================================================

def load_memory(claude_dir: str, name: str = "memory") -> Dict[str, Any]:
    """
    Load memory from either USD or markdown, preferring USD if evolved.

    Returns: {format: "md"|"usd"|"none", path: str, content: str, evolution: str}
    """
    claude_dir = os.path.normpath(claude_dir)
    usd_path = os.path.join(claude_dir, f"{name}.usd")
    md_path = os.path.join(claude_dir, f"{name}.md")

    if os.path.exists(usd_path) and name != "agent":
        # Check if it's a real evolved USD (not the agent stub)
        try:
            content = _read_file(usd_path)
            if '"synapse:type" = "agent_state"' not in content:
                return {
                    "format": "usd",
                    "path": usd_path,
                    "content": content,
                    "evolution": "charmeleon",
                }
        except Exception as e:
            logger.warning("Could not read USD %s: %s", usd_path, e)

    if os.path.exists(md_path):
        content = _read_file(md_path)
        return {
            "format": "md",
            "path": md_path,
            "content": content,
            "evolution": "charmander",
        }

    return {
        "format": "none",
        "path": "",
        "content": "",
        "evolution": "none",
    }


def write_session_start(scene_dir: str, goal: str = "") -> None:
    """Append session start header to memory.md."""
    md_path = os.path.join(scene_dir, "memory.md")
    if not os.path.exists(md_path):
        return

    now = _now()
    date = now.split("T")[0]
    time_str = now.split("T")[1].rstrip("Z")

    lines = [
        f"\n## Session {date} {time_str}\n",
    ]
    if goal:
        lines.append(f"**Goal:** {goal}\n")
    lines.append("")

    with open(md_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info("Session start written to %s", md_path)


def write_decision(scene_dir: str, decision: Dict[str, str], scope: str = "scene") -> None:
    """
    Write decision to memory.

    decision: {name, choice, reasoning, alternatives}
    scope: "scene" | "project" | "both"
    """
    entry = (
        f"### Decision: {decision.get('name', 'Untitled')}\n"
        f"**Choice:** {decision.get('choice', '')}\n"
        f"**Reasoning:** {decision.get('reasoning', '')}\n"
    )
    alternatives = decision.get("alternatives", [])
    if alternatives:
        entry += "**Alternatives:**\n"
        for alt in alternatives:
            entry += f"- {alt}\n"
    entry += "\n"

    if scope in ("scene", "both"):
        _append_to_md(os.path.join(scene_dir, "memory.md"), entry)

    if scope in ("project", "both"):
        # scene_dir is $HIP/claude, project is $JOB/claude
        # Caller provides project_dir explicitly via write_memory_entry
        project_md = _find_project_md(scene_dir)
        if project_md:
            _append_to_md(project_md, entry)


def write_parameter_experiment(scene_dir: str, experiment: Dict[str, Any]) -> None:
    """Write parameter experiment. experiment: {node, parm, before, after, result}"""
    entry = (
        f"### Parameter: {experiment.get('node', '')} / {experiment.get('parm', '')}\n"
        f"- **Before:** {experiment.get('before', '')}\n"
        f"- **After:** {experiment.get('after', '')}\n"
        f"- **Result:** {experiment.get('result', '')}\n\n"
    )
    _append_to_md(os.path.join(scene_dir, "memory.md"), entry)


def write_blocker(scene_dir: str, blocker: Dict[str, Any]) -> None:
    """Write blocker entry. blocker: {description, attempts, status}"""
    status = blocker.get("status", "open")
    prefix = "Blocker" if status == "open" else "Blocker Resolved"
    entry = (
        f"### {prefix}: {blocker.get('description', '')}\n"
        f"- **Attempts:** {blocker.get('attempts', '')}\n"
        f"- **Status:** {status}\n\n"
    )
    _append_to_md(os.path.join(scene_dir, "memory.md"), entry)


def write_session_end(scene_dir: str, summary: Dict[str, Any]) -> None:
    """
    Append session end block.
    summary: {stopped_at, next_actions, accomplishments}
    """
    entry = (
        f"### Session End\n"
        f"- **Stopped at:** {summary.get('stopped_at', _now())}\n"
    )
    accomplishments = summary.get("accomplishments", [])
    if accomplishments:
        entry += "- **Accomplished:**\n"
        for a in accomplishments:
            entry += f"  - {a}\n"
    next_actions = summary.get("next_actions", [])
    if next_actions:
        entry += "- **Next:**\n"
        for n in next_actions:
            entry += f"  - {n}\n"
    entry += "\n---\n\n"

    _append_to_md(os.path.join(scene_dir, "memory.md"), entry)


def write_memory_entry(scene_dir: str, entry: Dict[str, Any], entry_type: str) -> None:
    """
    Write a memory entry to the scene's memory file.

    entry_type: session_start, session_end, decision, parameter_experiment,
                blocker, blocker_resolved, asset_reference, wedge_result, note
    """
    writers = {
        "session_start": lambda: write_session_start(scene_dir, entry.get("goal", "")),
        "session_end": lambda: write_session_end(scene_dir, entry),
        "decision": lambda: write_decision(scene_dir, entry, entry.get("scope", "scene")),
        "parameter_experiment": lambda: write_parameter_experiment(scene_dir, entry),
        "blocker": lambda: write_blocker(scene_dir, {**entry, "status": "open"}),
        "blocker_resolved": lambda: write_blocker(scene_dir, {**entry, "status": "resolved"}),
        "asset_reference": lambda: _write_generic_entry(scene_dir, "Asset Reference", entry),
        "wedge_result": lambda: _write_generic_entry(scene_dir, "Wedge Result", entry),
        "note": lambda: _write_generic_entry(scene_dir, "Note", entry),
    }
    writer = writers.get(entry_type)
    if writer:
        writer()
        # Check if evolution should happen
        try:
            from .evolution import check_evolution
            evo_status = check_evolution(scene_dir)
            if evo_status.get("should_evolve"):
                logger.info(
                    "Memory evolution recommended: %s -> %s (triggers: %s). "
                    "Call synapse_evolve_memory to upgrade.",
                    evo_status["current"], evo_status["target"],
                    evo_status["triggers_met"],
                )
        except ImportError:
            pass
        except Exception as e:
            logger.warning("Evolution check failed: %s", e)
    else:
        logger.warning("Unknown entry type: %s", entry_type)


def load_full_context(hip_dir: str, job_dir: str) -> Dict[str, Any]:
    """
    Load all memory layers into a single context dict.

    Returns: {project: {...}, scene: {...}, agent: {...}, summary: str}
    Truncates to ~8000 tokens max, prioritizing recent sessions and unresolved blockers.
    """
    hip_dir = os.path.normpath(hip_dir)
    job_dir = os.path.normpath(job_dir)

    project_claude = os.path.join(job_dir, "claude")
    scene_claude = os.path.join(hip_dir, "claude")

    project = load_memory(project_claude, "project") if os.path.isdir(project_claude) else {
        "format": "none", "path": "", "content": "", "evolution": "none"
    }
    scene = load_memory(scene_claude, "memory") if os.path.isdir(scene_claude) else {
        "format": "none", "path": "", "content": "", "evolution": "none"
    }

    # Agent state
    agent = {"status": "idle", "has_suspended_tasks": False, "suspended_count": 0}
    try:
        from .agent_state import load_agent_state
        agent = load_agent_state(scene_claude)
    except ImportError:
        agent_usd = os.path.join(scene_claude, "agent.usd")
        if os.path.exists(agent_usd):
            agent["path"] = agent_usd

    # Build summary text with smart prioritization
    summary_parts = []

    if project["content"]:
        decisions = _extract_decisions(project["content"])
        if decisions:
            summary_parts.append("## Project Decisions\n" + "\n".join(decisions))
        else:
            summary_parts.append("## Project Context\n" + _truncate(project["content"], 2000))

    if scene["content"]:
        blockers = _extract_blockers(scene["content"])
        recent = _extract_recent_sessions(scene["content"], max_sessions=3)
        decisions = _extract_decisions(scene["content"])

        if blockers:
            summary_parts.append("## Active Blockers\n" + "\n".join(blockers))
        if decisions:
            summary_parts.append("## Scene Decisions\n" + "\n".join(decisions))
        if recent:
            summary_parts.append("## Recent Sessions\n" + "\n".join(recent))

        # Fill remaining budget with older content
        budget_used = sum(len(p) for p in summary_parts)
        if budget_used < 6000 and not (blockers or decisions or recent):
            summary_parts.append("## Scene Memory\n" + _truncate(scene["content"], 6000 - budget_used))

    summary = "\n\n".join(summary_parts) if summary_parts else "No memory loaded."

    return {
        "project": project,
        "scene": scene,
        "agent": agent,
        "summary": summary,
    }


# =============================================================================
# HELPERS
# =============================================================================

def _read_file(path: str) -> str:
    """Read a file with UTF-8 encoding."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _append_to_md(md_path: str, text: str) -> None:
    """Append text to a markdown file if it exists. Thread-safe."""
    if not os.path.exists(md_path):
        logger.warning("Cannot append to missing file: %s", md_path)
        return
    lock = _get_file_lock(md_path)
    with lock:
        with open(md_path, "a", encoding="utf-8") as f:
            f.write(text)


def _write_generic_entry(scene_dir: str, title: str, entry: Dict[str, Any]) -> None:
    """Write a generic markdown entry."""
    content = entry.get("content", "")
    if isinstance(content, dict):
        import json
        content = json.dumps(content, indent=2, sort_keys=True)
    text = f"### {title}\n{content}\n\n"
    _append_to_md(os.path.join(scene_dir, "memory.md"), text)


def _find_project_md(scene_dir: str) -> Optional[str]:
    """Walk up from scene claude dir to find project.md."""
    # scene_dir is $HIP/claude, project is $JOB/claude
    # Walk up: $HIP/claude -> $HIP -> parent -> parent/claude
    current = os.path.dirname(scene_dir)  # $HIP
    for _ in range(5):  # max depth
        parent = os.path.dirname(current)
        if parent == current:
            break
        candidate = os.path.join(parent, "claude", "project.md")
        if os.path.exists(candidate):
            return candidate
        current = parent
    return None


def _extract_blockers(content: str) -> List[str]:
    """Extract unresolved blocker sections from markdown memory."""
    import re
    blockers = []
    for match in re.finditer(
        r'### Blocker: (.+?)(?=\n###|\n## |\Z)', content, re.DOTALL
    ):
        block = match.group(1)
        if "**Status:** resolved" not in block:
            blockers.append("- " + block.strip()[:200])
    return blockers


def _extract_decisions(content: str) -> List[str]:
    """Extract decision summaries from markdown memory."""
    import re
    decisions = []
    for match in re.finditer(
        r'### Decision: (.+?)\n.*?\*\*Choice:\*\* (.+)', content
    ):
        decisions.append(f"- {match.group(1).strip()}: {match.group(2).strip()}")
    return decisions


def _extract_recent_sessions(content: str, max_sessions: int = 3) -> List[str]:
    """Extract last N session blocks from markdown memory."""
    import re
    sessions = re.findall(
        r'(## Session .+?)(?=\n## Session |\Z)', content, re.DOTALL
    )
    return [s.strip()[:500] for s in sessions[-max_sessions:]]


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, preserving complete lines."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_newline = truncated.rfind("\n")
    if last_newline > max_chars // 2:
        truncated = truncated[:last_newline]
    return truncated + "\n...(truncated)"


def get_evolution_stage(claude_dir: str, name: str = "memory") -> str:
    """Detect current evolution stage: charmander, charmeleon, or charizard."""
    claude_dir = os.path.normpath(claude_dir)
    usd_path = os.path.join(claude_dir, f"{name}.usd")
    md_path = os.path.join(claude_dir, f"{name}.md")

    if os.path.exists(usd_path):
        # Try pxr first (works for both binary USDC and text USDA)
        try:
            from pxr import Usd
            stage = Usd.Stage.Open(usd_path)
            layer_data = stage.GetRootLayer().customLayerData
            evo = layer_data.get("synapse:evolution", "")
            if evo == "charizard":
                return "charizard"
            if evo == "charmeleon":
                return "charmeleon"
            # Check sublayers as fallback
            if list(stage.GetRootLayer().subLayerPaths):
                return "charizard"
            return "charmeleon"
        except ImportError:
            pass
        # Fallback: text scan for USDA files
        try:
            content = _read_file(usd_path)
            if '"synapse:evolution" = "charizard"' in content:
                return "charizard"
            if "subLayers" in content or "references" in content:
                return "charizard"
        except Exception:
            pass
        return "charmeleon"

    if os.path.exists(md_path):
        return "charmander"

    return "none"


def get_memory_status(scene_dir: str, project_dir: str) -> Dict[str, Any]:
    """Get current memory system status."""
    scene_claude = os.path.join(scene_dir, "claude") if not scene_dir.endswith("claude") else scene_dir
    project_claude = os.path.join(project_dir, "claude") if not project_dir.endswith("claude") else project_dir

    def _dir_status(d: str, name: str) -> Dict[str, Any]:
        path = os.path.join(d, f"{name}.md")
        usd_path = os.path.join(d, f"{name}.usd")
        status = {
            "evolution": get_evolution_stage(d, name),
            "size_kb": 0.0,
            "session_count": 0,
        }
        if os.path.exists(usd_path):
            status["size_kb"] = round(os.path.getsize(usd_path) / 1024, 2)
        elif os.path.exists(path):
            status["size_kb"] = round(os.path.getsize(path) / 1024, 2)
            content = _read_file(path)
            status["session_count"] = content.count("## Session ")
        return status

    return {
        "project": _dir_status(project_claude, "project"),
        "scene": _dir_status(scene_claude, "memory"),
        "agent": {
            "status": "idle",
            "task_count": 0,
            "suspended_count": 0,
        },
    }


# =============================================================================
# CORRUPTION RECOVERY
# =============================================================================

def validate_memory(claude_dir: str) -> List[str]:
    """Validate memory files and return list of issues found."""
    issues: List[str] = []
    claude_dir = os.path.normpath(claude_dir)

    # Check markdown files
    for name in ("memory.md", "project.md"):
        path = os.path.join(claude_dir, name)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                if len(content) == 0:
                    issues.append(f"{name}: Empty file")
            except UnicodeDecodeError:
                issues.append(f"{name}: Encoding error")

    # Check USD files
    for name in ("memory.usd", "agent.usd"):
        path = os.path.join(claude_dir, name)
        if os.path.exists(path):
            try:
                from pxr import Usd
                stage = Usd.Stage.Open(path)
                if not stage.GetPrimAtPath("/SYNAPSE"):
                    issues.append(f"{name}: Missing /SYNAPSE root prim")
                # Schema version check
                layer_data = stage.GetRootLayer().customLayerData
                file_version = layer_data.get("synapse:version", "0.0.0")
                if file_version != SCHEMA_VERSION:
                    issues.append(
                        f"{name}: Schema version mismatch "
                        f"(file={file_version}, current={SCHEMA_VERSION})"
                    )
            except ImportError:
                pass  # pxr not available, skip USD validation
            except Exception as e:
                issues.append(f"{name}: Corrupted - {e}")
                # Backup corrupted file
                import shutil
                backup = path + f".corrupted.{int(time.time())}"
                shutil.move(path, backup)
                issues.append(f"{name}: Backed up to {backup}")
                if name == "agent.usd":
                    try:
                        from .agent_state import initialize_agent_usd
                        initialize_agent_usd(path)
                        issues.append(f"{name}: Reinitialized")
                    except Exception:
                        pass

    return issues
