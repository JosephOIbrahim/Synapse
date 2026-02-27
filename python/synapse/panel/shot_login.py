"""
Synapse Shot Login -- Context Hydration from Memory Layers

When an artist opens a hip file, this module loads context from all
available memory layers (project + scene), like logging into a shot
in a VFX pipeline.

Memory layers:
  Layer 1: Cognitive Substrate (global behavior -- system prompt, not files)
  Layer 2: Project Memory at $JOB/claude/project.md (or project.usd if evolved)
  Layer 3: Scene Memory at $HIP/claude/memory.md (or memory.usd if evolved)

Evolution stages: "flat" (markdown), "structured" (USD), "composed" (USD + arcs).
"""

import logging
import os
import time
from typing import Dict, Optional

logger = logging.getLogger("synapse.shot_login")

# Houdini API -- optional for testing outside Houdini
_HOU_AVAILABLE = False
try:
    import hou
    _HOU_AVAILABLE = True
except ImportError:
    hou = None

# Memory system -- optional, degrades gracefully
_MEMORY_AVAILABLE = False
try:
    from synapse.memory.scene_memory import (
        load_memory,
        get_evolution_stage,
        ensure_scene_structure,
        SCHEMA_VERSION,
    )
    _MEMORY_AVAILABLE = True
except ImportError:
    load_memory = None
    get_evolution_stage = None
    ensure_scene_structure = None
    SCHEMA_VERSION = "0.1.0"


# Map internal evolution names to the canonical stage names
_EVOLUTION_MAP = {
    "charmander": "flat",
    "charmeleon": "structured",
    "charizard": "composed",
    "flat": "flat",
    "structured": "structured",
    "composed": "composed",
    "none": "none",
}


def _normalize_evolution(stage: str) -> str:
    """Map internal evolution names to canonical flat/structured/composed."""
    return _EVOLUTION_MAP.get(stage, stage)


def shot_login(hip_path: str = "") -> dict:
    """
    Main entry point for shot login. Loads context from all memory layers.

    Args:
        hip_path: Path to the hip file. If empty, attempts hou.hipFile.path().

    Returns:
        Context dict with project/scene memory content, evolution stages,
        and a logged_in flag. Returns logged_in=False if memory system
        is unavailable.
    """
    # Resolve hip path
    if not hip_path:
        hip_path = _get_hip_path()

    if not hip_path:
        logger.warning("No hip path available -- returning minimal login")
        return _minimal_login("No hip path available")

    hip_path = os.path.normpath(hip_path)
    scene_dir = os.path.dirname(hip_path) if os.path.isfile(hip_path) else hip_path

    # Resolve project directory
    project_dir = _resolve_project_dir(scene_dir)

    # Paths to claude/ directories
    claude_scene = os.path.join(scene_dir, "claude")
    claude_project = os.path.join(project_dir, "claude") if project_dir else ""

    # Initialize directories and seed files
    ensure_claude_dir(scene_dir)
    if project_dir:
        ensure_claude_dir(project_dir)

    # Initialize scene memory if missing
    hip_name = os.path.basename(hip_path)
    init_scene_memory(claude_scene, hip_name)

    # Initialize project memory if missing
    if claude_project:
        _init_project_memory(claude_project, project_dir)

    # Load memory content
    project_context = ""
    project_evolution = "none"
    scene_context = ""
    scene_evolution = "none"

    if _MEMORY_AVAILABLE:
        # Load project memory
        if claude_project and os.path.isdir(claude_project):
            proj_data = load_memory(claude_project, "project")
            project_context = proj_data.get("content", "")
            project_evolution = _normalize_evolution(proj_data.get("evolution", "none"))

        # Load scene memory
        if os.path.isdir(claude_scene):
            scene_data = load_memory(claude_scene, "memory")
            scene_context = scene_data.get("content", "")
            scene_evolution = _normalize_evolution(scene_data.get("evolution", "none"))
    else:
        # Fallback: read files directly if memory module unavailable
        project_context, project_evolution = _load_memory_fallback(
            claude_project, "project"
        )
        scene_context, scene_evolution = _load_memory_fallback(
            claude_scene, "memory"
        )

    result = {
        "project_dir": project_dir or "",
        "scene_dir": scene_dir,
        "project_context": project_context,
        "scene_context": scene_context,
        "project_evolution": project_evolution,
        "scene_evolution": scene_evolution,
        "hip_file": hip_path,
        "logged_in": True,
    }

    logger.info(
        "Shot login complete: project=%s scene=%s",
        project_evolution,
        scene_evolution,
    )
    return result


def check_login_needed(current_hip: str, last_hip: str) -> bool:
    """
    Check if the hip file changed and we need to re-login.

    Args:
        current_hip: Current hip file path.
        last_hip: Previously logged-in hip file path.

    Returns:
        True if a new login is needed.
    """
    if not current_hip or not last_hip:
        return True
    return os.path.normpath(current_hip) != os.path.normpath(last_hip)


def format_memory_for_prompt(login_data: dict) -> str:
    """
    Convert login data into a formatted string for the system prompt.

    Includes project context, scene context, and a brief status line.
    Returns empty string if not logged in.
    """
    if not login_data.get("logged_in"):
        return ""

    parts = []

    # Status line
    proj_evo = login_data.get("project_evolution", "none")
    scene_evo = login_data.get("scene_evolution", "none")
    parts.append(f"Memory: project={proj_evo}, scene={scene_evo}")
    parts.append("")

    # Project context
    project_context = login_data.get("project_context", "")
    if project_context:
        parts.append("## Project Memory")
        parts.append("")
        parts.append(project_context.strip())
        parts.append("")

    # Scene context
    scene_context = login_data.get("scene_context", "")
    if scene_context:
        parts.append("## Scene Memory")
        parts.append("")
        parts.append(scene_context.strip())
        parts.append("")

    if not project_context and not scene_context:
        parts.append("No memory loaded for this shot.")

    return "\n".join(parts)


def ensure_claude_dir(base_dir: str) -> str:
    """
    Idempotently create {base_dir}/claude/ directory.

    Args:
        base_dir: Parent directory (scene dir or project dir).

    Returns:
        Path to the claude/ directory.
    """
    claude_dir = os.path.join(os.path.normpath(base_dir), "claude")
    os.makedirs(claude_dir, exist_ok=True)
    return claude_dir


def init_scene_memory(claude_dir: str, hip_name: str) -> None:
    """
    Create initial memory.md with header if it doesn't exist.

    Idempotent: never overwrites existing files.

    Args:
        claude_dir: Path to the claude/ directory.
        hip_name: Name of the hip file (for the header).
    """
    claude_dir = os.path.normpath(claude_dir)
    md_path = os.path.join(claude_dir, "memory.md")

    if os.path.exists(md_path):
        return

    # Ensure directory exists
    os.makedirs(claude_dir, exist_ok=True)

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    content = (
        f"# Scene Memory: {hip_name}\n"
        f"# Created: {now}\n"
        f"# Evolution: flat\n"
        f"# Schema: {SCHEMA_VERSION}\n"
        "\n---\n\n"
    )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("Initialized scene memory: %s", md_path)


# =============================================================================
# INTERNAL HELPERS
# =============================================================================


def _get_hip_path() -> str:
    """Get current hip file path from Houdini, or empty string."""
    if not _HOU_AVAILABLE:
        return ""
    try:
        path = hou.hipFile.path()
        # hou.hipFile.path() returns "untitled.hip" for unsaved files
        if path and os.path.basename(path) != "untitled.hip":
            return path
        return ""
    except Exception:
        return ""


def _resolve_project_dir(scene_dir: str) -> Optional[str]:
    """
    Resolve the project directory.

    Priority:
      1. $JOB environment variable (via hou or os.environ)
      2. Walk up from scene_dir looking for a directory with a claude/ folder
    """
    # Try $JOB from Houdini
    job_dir = None
    if _HOU_AVAILABLE:
        try:
            job_dir = hou.getenv("JOB")
        except Exception:
            pass

    # Try $JOB from environment
    if not job_dir:
        job_dir = os.environ.get("JOB", "")

    if job_dir and os.path.isdir(job_dir):
        return os.path.normpath(job_dir)

    # Walk up from scene_dir looking for claude/ folder
    current = os.path.normpath(scene_dir)
    for _ in range(10):  # max depth to avoid infinite loops
        parent = os.path.dirname(current)
        if parent == current:
            break  # filesystem root
        candidate_claude = os.path.join(parent, "claude")
        if os.path.isdir(candidate_claude):
            return parent
        current = parent

    # No project dir found -- use scene_dir as fallback
    return None


def _init_project_memory(claude_dir: str, project_dir: str) -> None:
    """Create initial project.md with header if it doesn't exist."""
    claude_dir = os.path.normpath(claude_dir)
    md_path = os.path.join(claude_dir, "project.md")

    if os.path.exists(md_path):
        return

    os.makedirs(claude_dir, exist_ok=True)

    project_name = os.path.basename(os.path.normpath(project_dir))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    content = (
        f"# Project Memory: {project_name}\n"
        f"# Created: {now}\n"
        f"# Evolution: flat\n"
        f"# Schema: {SCHEMA_VERSION}\n"
        "\n---\n\n"
        "## Pipeline Configuration\n\n"
        "## Key Decisions\n\n"
        "## Notes\n"
    )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("Initialized project memory: %s", md_path)


def _load_memory_fallback(
    claude_dir: str, name: str
) -> tuple:
    """
    Fallback memory loader when synapse.memory is not available.

    Returns (content, evolution_stage) tuple.
    """
    if not claude_dir or not os.path.isdir(claude_dir):
        return "", "none"

    usd_path = os.path.join(claude_dir, f"{name}.usd")
    md_path = os.path.join(claude_dir, f"{name}.md")

    # Prefer USD if it exists and isn't an agent stub
    if os.path.exists(usd_path):
        try:
            with open(usd_path, "r", encoding="utf-8") as f:
                content = f.read()
            if '"synapse:type" = "agent_state"' not in content:
                # Check for composition arcs
                if "subLayers" in content or "references" in content:
                    return content, "composed"
                return content, "structured"
        except Exception:
            pass

    # Fall back to markdown
    if os.path.exists(md_path):
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content, "flat"
        except Exception:
            return "", "none"

    return "", "none"


def _minimal_login(reason: str = "") -> dict:
    """Return a minimal login dict when full login isn't possible."""
    return {
        "project_dir": "",
        "scene_dir": "",
        "project_context": "",
        "scene_context": "",
        "project_evolution": "none",
        "scene_evolution": "none",
        "hip_file": "",
        "logged_in": False,
        "reason": reason,
    }
