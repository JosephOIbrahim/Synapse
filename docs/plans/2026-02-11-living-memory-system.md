# Living Memory System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add persistent, layered, evolving memory to SYNAPSE that stores AI context alongside Houdini scene files — starting as markdown, automatically upgrading to USD when structured data demands it.

**Architecture:** Three-layer context system: Cognitive Substrate (global behavior, unchanged), Project Memory (`$JOB/claude/`), and Scene Memory (`$HIP/claude/`). Memory evolves: Charmander (markdown) -> Charmeleon (USD) -> Charizard (composed USD with cross-scene queries). New module `synapse_scene_memory.py` handles file ops; existing `SynapseBridge` gains dual-write to file + in-memory store; 5 new MCP tools + modified existing tools.

**Tech Stack:** Python 3.10+ (Houdini embedded), `pxr.Usd`/`pxr.Sdf` (USD API from Houdini), `os`/`json`/`shutil`/`datetime` (stdlib). No new pip dependencies for Phase 1-4.

**Blueprint:** `C:/Users/User/SYNAPSE_SCENE_MEMORY_BLUEPRINT.md` (1672 lines, authoritative spec)

**Codebase entry points:**
- Core memory: `python/synapse/memory/store.py` (MemoryStore, SynapseMemory)
- Memory models: `python/synapse/memory/models.py` (Memory, MemoryType, etc.)
- Markdown sync: `python/synapse/memory/markdown.py` (MarkdownSync, ShotContext)
- Session tracker: `python/synapse/session/tracker.py` (SynapseBridge — delegates memory handlers)
- Handlers: `python/synapse/server/handlers.py:334-338` (memory handler registration)
- WebSocket: `python/synapse/server/websocket.py:248-356` (client connect/disconnect)
- MCP Server: `mcp_server.py` (38 tools in `list_tools()` / `call_tool()`)
- Shelf tool: `~/.synapse/houdini/scripts/python/synapse_shelf.py`

---

## Phase 1: Foundation — Markdown Memory + Shot Login

**This is the critical path. Everything depends on this working cleanly.**

---

### Task 1: Create `synapse_scene_memory.py` — Directory & File Management

**Files:**
- Create: `python/synapse/memory/scene_memory.py`
- Test: `tests/test_scene_memory.py`

**Step 1: Write the failing test for `ensure_scene_structure`**

Create `tests/test_scene_memory.py`:

```python
"""Tests for the Living Memory scene memory system."""

import os
import sys
import time
import json
import shutil
import tempfile

import pytest


# ── Bootstrap hou stub ──────────────────────────────────────────────
class _MockHipFile:
    def path(self):
        return "/tmp/test_project/scenes/shot_010.hip"
    def basename(self):
        return "shot_010.hip"
    def name(self):
        return "shot_010.hip"

class _MockPlaybar:
    def frameRange(self):
        return (1001, 1100)

class _MockUI:
    def displayMessage(self, *a, **kw):
        pass
    def copyTextToClipboard(self, *a, **kw):
        pass

class _MockHou:
    hipFile = _MockHipFile()
    playbar = _MockPlaybar()
    ui = _MockUI()

    def fps(self):
        return 24.0
    def frame(self):
        return 1001
    def getenv(self, name, default=None):
        if name == "JOB":
            return "/tmp/test_project"
        return default

_mock_hou = _MockHou()
sys.modules.setdefault("hou", _mock_hou)

# ── Import module under test ────────────────────────────────────────
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "scene_memory",
    os.path.join(os.path.dirname(__file__), "..", "python", "synapse", "memory", "scene_memory.py"),
)
sm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sm)


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project structure."""
    job_dir = tmp_path / "my_project"
    hip_dir = job_dir / "scenes"
    hip_dir.mkdir(parents=True)
    hip_file = hip_dir / "shot_010.hip"
    hip_file.write_text("")  # placeholder
    return {
        "job": str(job_dir),
        "hip": str(hip_file),
        "hip_dir": str(hip_dir),
    }


# ── Tests ───────────────────────────────────────────────────────────

class TestEnsureSceneStructure:
    """Tests for ensure_scene_structure()."""

    def test_creates_directories_fresh(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        assert os.path.isdir(result["project_dir"])
        assert os.path.isdir(result["scene_dir"])

    def test_idempotent(self, tmp_project):
        r1 = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        r2 = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        assert r1 == r2

    def test_seeds_project_md(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        project_md = result["project_md"]
        assert os.path.exists(project_md)
        content = open(project_md, "r", encoding="utf-8").read()
        assert "# Project Memory" in content

    def test_seeds_scene_md(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        scene_md = result["scene_md"]
        assert os.path.exists(scene_md)
        content = open(scene_md, "r", encoding="utf-8").read()
        assert "# Scene Memory" in content

    def test_does_not_overwrite_existing_project_md(self, tmp_project):
        # Pre-create project.md with custom content
        job_claude = os.path.join(tmp_project["job"], "claude")
        os.makedirs(job_claude, exist_ok=True)
        custom = "# My custom project memory\n"
        with open(os.path.join(job_claude, "project.md"), "w", encoding="utf-8") as f:
            f.write(custom)
        sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        content = open(os.path.join(job_claude, "project.md"), "r", encoding="utf-8").read()
        assert content == custom

    def test_does_not_overwrite_existing_scene_md(self, tmp_project):
        scene_claude = os.path.join(tmp_project["hip_dir"], "claude")
        os.makedirs(scene_claude, exist_ok=True)
        custom = "# My custom scene memory\n"
        with open(os.path.join(scene_claude, "memory.md"), "w", encoding="utf-8") as f:
            f.write(custom)
        sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        content = open(os.path.join(scene_claude, "memory.md"), "r", encoding="utf-8").read()
        assert content == custom

    def test_returns_correct_paths(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        assert "project_dir" in result
        assert "scene_dir" in result
        assert "project_md" in result
        assert "scene_md" in result
        assert "agent_usd" in result

    def test_utf8_encoding(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        # Verify files are valid UTF-8
        with open(result["project_md"], "r", encoding="utf-8") as f:
            f.read()
        with open(result["scene_md"], "r", encoding="utf-8") as f:
            f.read()

    def test_windows_path_normalization(self, tmp_project):
        # Pass path with mixed separators
        hip_path = tmp_project["hip"].replace("/", "\\")
        job_path = tmp_project["job"].replace("/", "\\")
        result = sm.ensure_scene_structure(hip_path, job_path)
        assert os.path.isdir(result["project_dir"])
        assert os.path.isdir(result["scene_dir"])
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scene_memory.py -v`
Expected: FAIL (module not found / import error)

**Step 3: Write the `scene_memory.py` module — directory management**

Create `python/synapse/memory/scene_memory.py`:

```python
"""
Synapse Scene Memory — Living Memory System

Persistent, layered memory that lives alongside Houdini scene files.
Memory evolves: Charmander (markdown) -> Charmeleon (USD) -> Charizard (composed USD).

This module handles all file operations for the scene memory system.
Every function is idempotent, non-destructive, and encoding-safe.
"""

import logging
import os
import time
from typing import Dict, List, Optional, Any

logger = logging.getLogger("synapse.scene_memory")

# Schema version for memory files
SCHEMA_VERSION = "0.1.0"


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

    # Seed agent.usd (stub for Phase 1 — full impl in Phase 2)
    agent_usd = os.path.join(scene_dir, "agent.usd")
    if not os.path.exists(agent_usd):
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
        # Stub: Phase 3 adds check_evolution() here
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

    # Agent state (simple read for Phase 1)
    agent_usd = os.path.join(scene_claude, "agent.usd")
    agent = {"status": "idle", "has_suspended_tasks": False, "suspended_count": 0}
    if os.path.exists(agent_usd):
        agent["path"] = agent_usd

    # Build summary text (truncated)
    summary_parts = []
    if project["content"]:
        summary_parts.append("## Project Context\n" + _truncate(project["content"], 2000))
    if scene["content"]:
        summary_parts.append("## Scene Memory\n" + _truncate(scene["content"], 4000))

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
    """Append text to a markdown file if it exists."""
    if not os.path.exists(md_path):
        logger.warning("Cannot append to missing file: %s", md_path)
        return
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


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, preserving complete lines."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_newline = truncated.rfind("\n")
    if last_newline > max_chars // 2:
        truncated = truncated[:last_newline]
    return truncated + "\n...(truncated)"


def get_evolution_stage(claude_dir: str) -> str:
    """Detect current evolution stage: charmander, charmeleon, or charizard."""
    claude_dir = os.path.normpath(claude_dir)
    usd_path = os.path.join(claude_dir, "memory.usd")
    md_path = os.path.join(claude_dir, "memory.md")

    if os.path.exists(usd_path):
        # Check for composition arcs (charizard indicator)
        try:
            content = _read_file(usd_path)
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
            "evolution": get_evolution_stage(d),
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
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scene_memory.py -v`
Expected: All 9 tests PASS

**Step 5: Commit**

```bash
git add python/synapse/memory/scene_memory.py tests/test_scene_memory.py
git commit -m "feat(memory): add scene_memory module — directory mgmt and markdown read/write

Phase 1A/1B of Living Memory System. Creates claude/ directories at $JOB
and $HIP levels, seeds project.md and memory.md, loads/writes session
entries. All operations are idempotent and non-destructive."
```

---

### Task 2: Add write operation tests

**Files:**
- Modify: `tests/test_scene_memory.py`

**Step 1: Write failing tests for session/decision/end writing**

Append to `tests/test_scene_memory.py`:

```python
class TestSessionWriteOps:
    """Tests for session start, decision, session end writing."""

    def test_write_session_start(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        sm.write_session_start(result["scene_dir"], goal="Set up hero lighting")
        content = open(result["scene_md"], "r", encoding="utf-8").read()
        assert "## Session" in content
        assert "Set up hero lighting" in content

    def test_write_decision(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        sm.write_decision(
            result["scene_dir"],
            {"name": "Render Engine", "choice": "Karma XPU", "reasoning": "GPU acceleration"},
        )
        content = open(result["scene_md"], "r", encoding="utf-8").read()
        assert "### Decision: Render Engine" in content
        assert "Karma XPU" in content

    def test_write_decision_scope_both(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        sm.write_decision(
            result["scene_dir"],
            {"name": "OCIO Config", "choice": "ACES 1.3", "reasoning": "Studio standard"},
            scope="both",
        )
        scene_content = open(result["scene_md"], "r", encoding="utf-8").read()
        project_content = open(result["project_md"], "r", encoding="utf-8").read()
        assert "ACES 1.3" in scene_content
        assert "ACES 1.3" in project_content

    def test_write_session_end(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        sm.write_session_start(result["scene_dir"])
        sm.write_session_end(result["scene_dir"], {
            "stopped_at": "2026-02-11T15:00:00Z",
            "accomplishments": ["Set up lighting", "Fixed SSS"],
            "next_actions": ["Render turntable"],
        })
        content = open(result["scene_md"], "r", encoding="utf-8").read()
        assert "Session End" in content
        assert "Set up lighting" in content
        assert "Render turntable" in content
        assert "---" in content  # separator

    def test_write_parameter_experiment(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        sm.write_parameter_experiment(result["scene_dir"], {
            "node": "/stage/karma1",
            "parm": "samples",
            "before": 64,
            "after": 256,
            "result": "Noise eliminated, render time 2x",
        })
        content = open(result["scene_md"], "r", encoding="utf-8").read()
        assert "/stage/karma1" in content
        assert "256" in content

    def test_write_blocker(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        sm.write_blocker(result["scene_dir"], {
            "description": "SSS artifacts on hero skin",
            "attempts": "Increased samples, tried different SSS model",
        })
        content = open(result["scene_md"], "r", encoding="utf-8").read()
        assert "Blocker:" in content
        assert "SSS artifacts" in content


class TestLoadMemory:
    """Tests for load_memory and load_full_context."""

    def test_load_memory_returns_md_when_exists(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        mem = sm.load_memory(result["scene_dir"])
        assert mem["format"] == "md"
        assert "Scene Memory" in mem["content"]
        assert mem["evolution"] == "charmander"

    def test_load_memory_returns_none_when_empty_dir(self, tmp_path):
        empty = str(tmp_path / "empty_claude")
        os.makedirs(empty, exist_ok=True)
        mem = sm.load_memory(empty)
        assert mem["format"] == "none"

    def test_load_full_context_combines(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        ctx = sm.load_full_context(tmp_project["hip_dir"], tmp_project["job"])
        assert "project" in ctx
        assert "scene" in ctx
        assert "agent" in ctx
        assert "summary" in ctx
        assert "Project Context" in ctx["summary"]

    def test_write_memory_entry_dispatch(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        sm.write_memory_entry(result["scene_dir"], {"content": "Test note"}, "note")
        content = open(result["scene_md"], "r", encoding="utf-8").read()
        assert "Test note" in content
```

**Step 2: Run tests**

Run: `python -m pytest tests/test_scene_memory.py -v`
Expected: All tests PASS (implementation already covers these)

**Step 3: Commit**

```bash
git add tests/test_scene_memory.py
git commit -m "test(memory): add write operation and load tests for scene memory"
```

---

### Task 3: Register new MCP tools — `synapse_project_setup` and `synapse_memory_write`

**Files:**
- Modify: `python/synapse/server/handlers.py` (add handler methods + register)
- Modify: `python/synapse/session/tracker.py` (add bridge methods)
- Modify: `python/synapse/core/protocol.py` (add CommandType variants)
- Modify: `mcp_server.py` (add Tool entries + dispatch cases)

**Step 1: Write failing test for project_setup handler**

Append to `tests/test_scene_memory.py`:

```python
class TestProjectSetupHandler:
    """Test the project_setup handler via bridge."""

    def test_handle_project_setup_creates_structure(self, tmp_project):
        """Simulate what the handler would do."""
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        ctx = sm.load_full_context(tmp_project["hip_dir"], tmp_project["job"])
        assert ctx["project"]["format"] == "md"
        assert ctx["scene"]["format"] == "md"

    def test_get_memory_status(self, tmp_project):
        sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        status = sm.get_memory_status(tmp_project["hip_dir"], tmp_project["job"])
        assert status["scene"]["evolution"] == "charmander"
        assert status["project"]["evolution"] == "charmander"
```

**Step 2: Run test to verify pass**

Run: `python -m pytest tests/test_scene_memory.py::TestProjectSetupHandler -v`
Expected: PASS

**Step 3: Add handler registration in `handlers.py`**

In `python/synapse/server/handlers.py`, add to `_register_handlers()` after memory operations (line ~338):

```python
        # Scene memory operations (Living Memory)
        reg.register("project_setup", self._handle_project_setup)
        reg.register("memory_write", self._handle_memory_write)
        reg.register("memory_query", self._handle_memory_query)
        reg.register("memory_status", self._handle_memory_status)
```

Add handler methods (near end of memory section, ~line 1540):

```python
    # =========================================================================
    # SCENE MEMORY HANDLERS (Living Memory System)
    # =========================================================================

    def _handle_project_setup(self, payload: Dict) -> Dict:
        """Initialize or load SYNAPSE project structure for current scene."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from ..memory.scene_memory import ensure_scene_structure, load_full_context

        hip_path = hou.hipFile.path()
        job_path = hou.getenv("JOB", os.path.dirname(hip_path))

        paths = ensure_scene_structure(hip_path, job_path)
        hip_dir = os.path.dirname(hip_path)
        ctx = load_full_context(hip_dir, job_path)

        return {
            "paths": paths,
            "project_memory": ctx["project"].get("content", "")[:2000],
            "scene_memory": ctx["scene"].get("content", "")[:3000],
            "agent_state": ctx["agent"],
            "evolution_stage": ctx["scene"].get("evolution", "none"),
            "suspended_tasks": [],
        }

    def _handle_memory_write(self, payload: Dict) -> Dict:
        """Write a memory entry to scene or project memory."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from ..memory.scene_memory import write_memory_entry, ensure_scene_structure

        hip_path = hou.hipFile.path()
        job_path = hou.getenv("JOB", os.path.dirname(hip_path))
        paths = ensure_scene_structure(hip_path, job_path)

        entry_type = resolve_param(payload, "entry_type")
        content = resolve_param(payload, "content")
        scope = resolve_param_with_default(payload, "scope", "scene")

        if isinstance(content, str):
            content = {"content": content}
        content["scope"] = scope

        write_memory_entry(paths["scene_dir"], content, entry_type)
        return {"written": True, "entry_type": entry_type, "scope": scope}

    def _handle_memory_query(self, payload: Dict) -> Dict:
        """Query scene or project memory."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from ..memory.scene_memory import load_full_context

        hip_path = hou.hipFile.path()
        job_path = hou.getenv("JOB", os.path.dirname(hip_path))
        hip_dir = os.path.dirname(hip_path)

        query = resolve_param(payload, "query")
        scope = resolve_param_with_default(payload, "scope", "all")

        ctx = load_full_context(hip_dir, job_path)
        results = []

        # Simple text search in markdown for Phase 1
        query_lower = query.lower()
        for layer_name in ("project", "scene"):
            if scope not in ("all", layer_name):
                continue
            content = ctx[layer_name].get("content", "")
            if query_lower in content.lower():
                # Find matching lines
                for i, line in enumerate(content.split("\n")):
                    if query_lower in line.lower():
                        results.append({
                            "layer": layer_name,
                            "line": i + 1,
                            "text": line.strip(),
                        })

        return {
            "query": query,
            "scope": scope,
            "count": len(results),
            "results": results[:50],
        }

    def _handle_memory_status(self, payload: Dict) -> Dict:
        """Get memory system status."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from ..memory.scene_memory import get_memory_status

        hip_path = hou.hipFile.path()
        hip_dir = os.path.dirname(hip_path)
        job_path = hou.getenv("JOB", hip_dir)

        return get_memory_status(hip_dir, job_path)
```

**Step 4: Add MCP tool entries in `mcp_server.py`**

In `list_tools()`, add 4 new `Tool(...)` entries after existing tools:

```python
        Tool(
            name="synapse_project_setup",
            description="Initialize or load SYNAPSE project structure for the current scene. Creates claude/ directories, seeds memory files, loads existing context. Idempotent. Call this after synapse_ping to load full scene context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "force_refresh": {
                        "type": "boolean",
                        "description": "Force re-read all memory files even if cached. Default: false",
                    }
                },
            },
        ),
        Tool(
            name="synapse_memory_write",
            description="Write a memory entry to scene or project memory. Handles markdown vs USD format automatically.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_type": {
                        "type": "string",
                        "enum": ["decision", "parameter_experiment", "blocker", "blocker_resolved",
                                 "asset_reference", "wedge_result", "note", "session_end"],
                        "description": "Type of memory entry",
                    },
                    "content": {
                        "type": "object",
                        "description": "Entry content — structure depends on entry_type",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["scene", "project", "both"],
                        "description": "Where to write. Default: scene",
                    },
                },
                "required": ["entry_type", "content"],
            },
        ),
        Tool(
            name="synapse_memory_query",
            description="Query scene or project memory. Text search in Charmander (markdown), structured queries in Charmeleon+ (USD).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["scene", "project", "all"],
                        "description": "Search scope. Default: all",
                    },
                    "type_filter": {
                        "type": "string",
                        "enum": ["all", "decisions", "parameters", "blockers", "assets", "sessions"],
                        "description": "Filter by entry type. Default: all",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="synapse_memory_status",
            description="Get memory system status: evolution stage, file sizes, session count, agent state.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
```

In `call_tool()`, add dispatch cases:

```python
        elif name == "synapse_project_setup":
            cmd_type = "project_setup"
        elif name == "synapse_memory_write":
            cmd_type = "memory_write"
        elif name == "synapse_memory_query":
            cmd_type = "memory_query"
        elif name == "synapse_memory_status":
            cmd_type = "memory_status"
```

**Step 5: Commit**

```bash
git add python/synapse/server/handlers.py mcp_server.py
git commit -m "feat(memory): register 4 new MCP tools for Living Memory System

synapse_project_setup, synapse_memory_write, synapse_memory_query,
synapse_memory_status. Handler methods in handlers.py dispatch to
scene_memory module."
```

---

### Task 4: Modify existing tools — dual-write to file + in-memory store

**Files:**
- Modify: `python/synapse/session/tracker.py` (add file-based writes to bridge methods)

**Step 1: Write failing test**

Add to `tests/test_scene_memory.py`:

```python
class TestDualWrite:
    """Test that existing tools also write to file-based memory."""

    def test_decide_writes_to_scene_memory(self, tmp_project):
        """Verify write_decision is called for decisions."""
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        # Simulate what the modified handle_memory_decide would do
        sm.write_decision(
            result["scene_dir"],
            {"name": "Rim light color", "choice": "warm amber", "reasoning": "sunset scene"},
        )
        content = open(result["scene_md"], "r", encoding="utf-8").read()
        assert "Rim light color" in content
        assert "warm amber" in content
```

**Step 2: Run test**

Run: `python -m pytest tests/test_scene_memory.py::TestDualWrite -v`
Expected: PASS

**Step 3: Modify `tracker.py` bridge methods**

In `python/synapse/session/tracker.py`, modify `handle_memory_decide()` around line 454:

After `self._markdown_sync.append_decision(memory)`, add:

```python
        # Living Memory: dual-write to file-based scene memory
        try:
            from ..memory.scene_memory import write_decision, ensure_scene_structure
            if HOU_AVAILABLE:
                hip_path = hou.hipFile.path()
                job_path = hou.getenv("JOB", os.path.dirname(hip_path))
                paths = ensure_scene_structure(hip_path, job_path)
                scope = "both" if "project" in tags else "scene"
                write_decision(paths["scene_dir"], {
                    "name": decision,
                    "choice": decision,
                    "reasoning": reasoning,
                    "alternatives": alternatives,
                }, scope=scope)
        except Exception as e:
            logger.warning("Scene memory dual-write failed: %s", e)
```

Similarly modify `handle_memory_add()` around line 425:

After `self.store.add(memory)`, add:

```python
        # Living Memory: dual-write to file-based scene memory
        try:
            from ..memory.scene_memory import write_memory_entry, ensure_scene_structure
            if HOU_AVAILABLE:
                hip_path = hou.hipFile.path()
                job_path = hou.getenv("JOB", os.path.dirname(hip_path))
                paths = ensure_scene_structure(hip_path, job_path)
                scope = "project" if "project" in tags else "scene"
                write_memory_entry(paths["scene_dir"], {"content": content}, "note")
        except Exception as e:
            logger.warning("Scene memory dual-write failed: %s", e)
```

Modify `handle_memory_context()` around line 481:

After the existing return, merge in file-based memory:

```python
    def handle_memory_context(self, payload: Dict) -> Dict:
        """Handle context request — now includes file-based scene memory."""
        format_type = payload.get("format", "json")

        base_context = self.get_connection_context() if format_type != "markdown" else {}

        # Living Memory: merge file-based memory
        file_context = {}
        try:
            from ..memory.scene_memory import load_full_context
            if HOU_AVAILABLE:
                hip_path = hou.hipFile.path()
                hip_dir = os.path.dirname(hip_path)
                job_path = hou.getenv("JOB", hip_dir)
                file_context = load_full_context(hip_dir, job_path)
        except Exception as e:
            logger.warning("Scene memory load failed: %s", e)

        if format_type == "markdown":
            md = self.get_context_markdown()
            if file_context.get("summary"):
                md += "\n\n" + file_context["summary"]
            return {"format": "markdown", "context": md}
        else:
            if file_context:
                base_context["scene_memory"] = file_context.get("summary", "")
                base_context["evolution_stage"] = file_context.get("scene", {}).get("evolution", "none")
            return {"format": "json", "context": base_context}
```

**Step 4: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All existing tests PASS + new tests PASS

**Step 5: Commit**

```bash
git add python/synapse/session/tracker.py
git commit -m "feat(memory): dual-write existing tools to file-based scene memory

synapse_decide writes decisions to memory.md. synapse_add_memory writes
notes. synapse_context merges file-based memory into response. All wrapped
in try/except to preserve existing behavior if scene memory fails."
```

---

### Task 5: Shelf tool — `synapse_connect.py`

**Files:**
- Create: `C:/Users/User/.synapse/houdini/scripts/python/synapse_connect.py`

**Step 1: Write the shelf tool script**

```python
"""
SYNAPSE Connect — One-Click Shot Login

Shelf tool that initializes the Living Memory system for the current scene.
Creates claude/ directories, loads memory, copies handshake payload to clipboard.

Always safe to click — idempotent. Never overwrites existing files.
"""

import hou
import os
import json
import socket
import time


def synapse_connect():
    """One-click SYNAPSE shot login."""
    # 1. Check server
    port = _check_server()
    if not port:
        hou.ui.displayMessage(
            "SYNAPSE server is not running on localhost:9999.\n\n"
            "Start the server first, then click Connect again.",
            title="SYNAPSE Connect",
            severity=hou.severityType.Error,
        )
        return

    # 2. Detect context
    hip_path = hou.hipFile.path()
    hip_dir = os.path.dirname(hip_path)
    hip_name = hou.hipFile.basename()
    job = hou.getenv("JOB", hip_dir)

    context = {
        "port": port,
        "hip": hip_path,
        "hip_dir": hip_dir,
        "hip_name": hip_name,
        "job": job,
        "fps": hou.fps(),
        "frame_range": [hou.playbar.frameRange()[0], hou.playbar.frameRange()[1]],
        "current_frame": hou.frame(),
    }

    # 3. Ensure directory structure (idempotent)
    try:
        # Import scene memory from the synapse package
        import importlib.util
        sm_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "..", "..", "Synapse", "python", "synapse", "memory", "scene_memory.py"
        )
        # Fallback: try from SYNAPSE install path
        if not os.path.exists(sm_path):
            synapse_root = os.environ.get("SYNAPSE_ROOT", "")
            if synapse_root:
                sm_path = os.path.join(synapse_root, "python", "synapse", "memory", "scene_memory.py")

        if os.path.exists(sm_path):
            spec = importlib.util.spec_from_file_location("scene_memory", sm_path)
            sm = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sm)

            paths = sm.ensure_scene_structure(hip_path, job)
            full_ctx = sm.load_full_context(hip_dir, job)
        else:
            # Minimal fallback — just create directories
            paths = _ensure_dirs_fallback(hip_dir, job, context)
            full_ctx = {"summary": "Scene memory module not found — basic setup only."}
    except Exception as e:
        hou.ui.displayMessage(
            f"Memory setup encountered an issue: {e}\n\n"
            "Basic connection info will still be copied.",
            title="SYNAPSE Connect",
            severity=hou.severityType.Warning,
        )
        paths = _ensure_dirs_fallback(hip_dir, job, context)
        full_ctx = {"summary": "Error loading memory."}

    # 4. Build handshake payload
    payload = _build_handshake(context, full_ctx)

    # 5. Copy to clipboard
    hou.ui.copyTextToClipboard(payload)

    # 6. Status message
    agent = full_ctx.get("agent", {})
    msg = "SYNAPSE ready -- context copied to clipboard."
    if agent.get("has_suspended_tasks"):
        msg += f"\n\nNote: {agent['suspended_count']} suspended tasks from last session."
    hou.ui.displayMessage(msg, title="SYNAPSE Connect")


def _check_server(port=9999):
    """Check if SYNAPSE server is running. Returns port or None."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("localhost", port))
        s.close()
        return port
    except (ConnectionRefusedError, socket.timeout, OSError):
        return None


def _ensure_dirs_fallback(hip_dir, job, context):
    """Minimal directory creation without scene_memory module."""
    project_dir = os.path.join(job, "claude")
    scene_dir = os.path.join(hip_dir, "claude")
    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(scene_dir, exist_ok=True)
    return {"project_dir": project_dir, "scene_dir": scene_dir}


def _build_handshake(context, full_ctx):
    """Build clipboard payload."""
    summary = full_ctx.get("summary", "No memory loaded.")
    lines = [
        "SYNAPSE CONNECT",
        "=" * 50,
        f"Port: {context['port']}",
        f"Scene: {context['hip_name']}",
        f"HIP: {context['hip']}",
        f"JOB: {context['job']}",
        f"FPS: {context['fps']} | Range: {context['frame_range']}",
        f"Frame: {context['current_frame']}",
        "",
        "-- MEMORY --",
        summary[:4000],
        "",
        "=" * 50,
    ]
    return "\n".join(lines)
```

**Step 2: Commit**

```bash
git add C:/Users/User/.synapse/houdini/scripts/python/synapse_connect.py
git commit -m "feat(shelf): add synapse_connect shelf tool for one-click shot login

Creates claude/ directories, loads memory, copies handshake to clipboard.
Falls back gracefully if scene_memory module not importable."
```

---

### Task 6: Run full Phase 1 test suite

**Step 1: Run all scene memory tests**

Run: `python -m pytest tests/test_scene_memory.py -v`
Expected: All tests PASS

**Step 2: Run full Synapse test suite (regression check)**

Run: `python -m pytest tests/ -v`
Expected: All ~788+ tests PASS (no regressions)

**Step 3: Commit Phase 1 checkpoint**

```bash
git add -A
git commit -m "milestone: Phase 1 complete — Living Memory foundation

- scene_memory.py: directory mgmt, markdown read/write, session ops
- 4 new MCP tools: project_setup, memory_write, memory_query, memory_status
- Dual-write: existing decide/add_memory/context now also write to files
- Shelf tool: synapse_connect.py for one-click shot login
- 20+ tests, all passing"
```

---

## Phase 2: Agent State — agent.usd

**Do not start until all Phase 1 tests pass.**

---

### Task 7: Create `synapse_agent_state.py` — USD agent operations

**Files:**
- Create: `python/synapse/memory/agent_state.py`
- Modify: `tests/test_scene_memory.py` (add Phase 2 tests)

**Step 1: Write failing tests for agent USD operations**

Add to `tests/test_scene_memory.py`:

```python
# ── Import agent_state module ────────────────────────────────────────
# Only if pxr is available (skip in CI without Houdini)
_pxr_available = False
try:
    from pxr import Usd, Sdf
    _pxr_available = True
except ImportError:
    pass

_agent_spec = importlib.util.spec_from_file_location(
    "agent_state",
    os.path.join(os.path.dirname(__file__), "..", "python", "synapse", "memory", "agent_state.py"),
)
if _agent_spec:
    agent = importlib.util.module_from_spec(_agent_spec)
    try:
        _agent_spec.loader.exec_module(agent)
    except Exception:
        agent = None


@pytest.mark.skipif(not _pxr_available, reason="pxr (USD) not available")
class TestAgentState:
    """Tests for agent.usd operations (require pxr)."""

    def test_initialize_creates_valid_usd(self, tmp_path):
        path = str(tmp_path / "agent.usd")
        agent.initialize_agent_usd(path)
        stage = Usd.Stage.Open(path)
        assert stage.GetPrimAtPath("/SYNAPSE/agent")
        status = stage.GetPrimAtPath("/SYNAPSE/agent").GetAttribute("synapse:status").Get()
        assert status == "idle"

    def test_create_task(self, tmp_path):
        path = str(tmp_path / "agent.usd")
        agent.initialize_agent_usd(path)
        agent.create_task(path, "task_001", "Set up hero lighting")
        stage = Usd.Stage.Open(path)
        task = stage.GetPrimAtPath("/SYNAPSE/agent/tasks/task_001")
        assert task.IsValid()
        assert task.GetAttribute("synapse:status").Get() == "pending"

    def test_update_task_status(self, tmp_path):
        path = str(tmp_path / "agent.usd")
        agent.initialize_agent_usd(path)
        agent.create_task(path, "task_001", "Test task")
        agent.update_task_status(path, "task_001", "executing")
        stage = Usd.Stage.Open(path)
        task = stage.GetPrimAtPath("/SYNAPSE/agent/tasks/task_001")
        assert task.GetAttribute("synapse:status").Get() == "executing"

    def test_suspend_all_tasks(self, tmp_path):
        path = str(tmp_path / "agent.usd")
        agent.initialize_agent_usd(path)
        agent.create_task(path, "task_001", "Task A")
        agent.create_task(path, "task_002", "Task B")
        agent.update_task_status(path, "task_001", "executing")
        agent.suspend_all_tasks(path)
        stage = Usd.Stage.Open(path)
        t1 = stage.GetPrimAtPath("/SYNAPSE/agent/tasks/task_001")
        t2 = stage.GetPrimAtPath("/SYNAPSE/agent/tasks/task_002")
        assert t1.GetAttribute("synapse:status").Get() == "suspended"
        assert t2.GetAttribute("synapse:status").Get() == "suspended"

    def test_resume_task(self, tmp_path):
        path = str(tmp_path / "agent.usd")
        agent.initialize_agent_usd(path)
        agent.create_task(path, "task_001", "Task A")
        agent.suspend_all_tasks(path)
        agent.resume_task(path, "task_001")
        stage = Usd.Stage.Open(path)
        t = stage.GetPrimAtPath("/SYNAPSE/agent/tasks/task_001")
        assert t.GetAttribute("synapse:status").Get() == "pending"

    def test_load_agent_state_detects_suspended(self, tmp_path):
        path = str(tmp_path / "agent.usd")
        agent.initialize_agent_usd(path)
        agent.create_task(path, "task_001", "A")
        agent.create_task(path, "task_002", "B")
        agent.suspend_all_tasks(path)
        state = agent.load_agent_state(str(tmp_path))
        assert state["has_suspended_tasks"] is True
        assert state["suspended_count"] == 2

    def test_log_session(self, tmp_path):
        path = str(tmp_path / "agent.usd")
        agent.initialize_agent_usd(path)
        agent.log_session(path, {
            "start_time": "2026-02-11T14:00:00Z",
            "end_time": "2026-02-11T15:00:00Z",
            "tasks_completed": 3,
            "tasks_failed": 0,
            "tasks_suspended": 1,
            "summary_text": "Lighting setup session",
        })
        stage = Usd.Stage.Open(path)
        history = stage.GetPrimAtPath("/SYNAPSE/agent/session_history")
        assert len(list(history.GetChildren())) == 1

    def test_100_sequential_operations(self, tmp_path):
        """Agent USD remains valid after many operations."""
        path = str(tmp_path / "agent.usd")
        agent.initialize_agent_usd(path)
        for i in range(50):
            agent.create_task(path, f"task_{i:03d}", f"Task {i}")
        for i in range(50):
            agent.update_task_status(path, f"task_{i:03d}", "completed")
        stage = Usd.Stage.Open(path)
        assert stage.GetPrimAtPath("/SYNAPSE/agent").IsValid()
```

**Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_scene_memory.py::TestAgentState -v`
Expected: FAIL (module not found) or SKIP (no pxr)

**Step 3: Implement `agent_state.py`**

Create `python/synapse/memory/agent_state.py`:

```python
"""
Synapse Agent State — USD-based agent execution tracking.

Stores task state, session history, and verification logs in agent.usd.
Uses pxr.Usd and pxr.Sdf (available in Houdini's Python).
"""

import logging
import os
import time
from typing import Dict, List, Optional, Any

logger = logging.getLogger("synapse.agent_state")

try:
    from pxr import Usd, Sdf
    PXR_AVAILABLE = True
except ImportError:
    PXR_AVAILABLE = False

SCHEMA_VERSION = "0.1.0"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def initialize_agent_usd(path: str) -> None:
    """Create fresh agent.usd with empty /SYNAPSE/agent prim hierarchy."""
    if not PXR_AVAILABLE:
        logger.warning("pxr not available — writing USDA stub")
        _write_usda_stub(path)
        return

    stage = Usd.Stage.CreateNew(path)
    root = stage.DefinePrim("/SYNAPSE", "Xform")
    agent_prim = stage.DefinePrim("/SYNAPSE/agent", "Xform")
    agent_prim.CreateAttribute("synapse:status", Sdf.ValueTypeNames.String).Set("idle")
    agent_prim.CreateAttribute("synapse:version", Sdf.ValueTypeNames.String).Set(SCHEMA_VERSION)

    stage.DefinePrim("/SYNAPSE/agent/current_plan", "Xform")
    stage.DefinePrim("/SYNAPSE/agent/tasks", "Xform")
    stage.DefinePrim("/SYNAPSE/agent/verification_log", "Xform")
    stage.DefinePrim("/SYNAPSE/agent/session_history", "Xform")

    stage.GetRootLayer().customLayerData = {
        "synapse:version": SCHEMA_VERSION,
        "synapse:type": "agent_state",
    }
    stage.GetRootLayer().Save()
    logger.info("Initialized agent.usd: %s", path)


def _write_usda_stub(path: str) -> None:
    """Fallback: write minimal USDA text when pxr unavailable."""
    content = (
        '#usda 1.0\n'
        '(\n'
        f'    customLayerData = {{\n'
        f'        string "synapse:version" = "{SCHEMA_VERSION}"\n'
        f'        string "synapse:type" = "agent_state"\n'
        f'    }}\n'
        ')\n\n'
        'def Xform "SYNAPSE"\n'
        '{\n'
        '    def Xform "agent"\n'
        '    {\n'
        '        custom string synapse:status = "idle"\n'
        '    }\n'
        '}\n'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def create_task(agent_usd_path: str, task_id: str, description: str) -> None:
    """Create a task prim under /SYNAPSE/agent/tasks/."""
    if not PXR_AVAILABLE:
        logger.warning("pxr not available — cannot create task")
        return

    stage = Usd.Stage.Open(agent_usd_path)
    task = stage.DefinePrim(f"/SYNAPSE/agent/tasks/{task_id}", "Xform")
    task.CreateAttribute("synapse:description", Sdf.ValueTypeNames.String).Set(description)
    task.CreateAttribute("synapse:status", Sdf.ValueTypeNames.String).Set("pending")
    task.CreateAttribute("synapse:createdAt", Sdf.ValueTypeNames.String).Set(_now())
    stage.GetRootLayer().Save()


def update_task_status(agent_usd_path: str, task_id: str, status: str,
                       verification: Dict = None) -> None:
    """Update task status: pending -> executing -> completed|failed."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    task = stage.GetPrimAtPath(f"/SYNAPSE/agent/tasks/{task_id}")
    if not task.IsValid():
        logger.warning("Task not found: %s", task_id)
        return

    task.GetAttribute("synapse:status").Set(status)

    if status == "completed":
        task.CreateAttribute("synapse:completedAt", Sdf.ValueTypeNames.String).Set(_now())
    elif status == "failed":
        task.CreateAttribute("synapse:failedAt", Sdf.ValueTypeNames.String).Set(_now())

    if verification:
        task.CreateAttribute("synapse:verificationResult", Sdf.ValueTypeNames.String).Set(
            verification.get("result", "unknown")
        )

    stage.GetRootLayer().Save()


def suspend_all_tasks(agent_usd_path: str) -> None:
    """Mark all pending/executing tasks as suspended. Called on disconnect."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    tasks_prim = stage.GetPrimAtPath("/SYNAPSE/agent/tasks")
    if not tasks_prim.IsValid():
        return

    now = _now()
    for task in tasks_prim.GetChildren():
        status_attr = task.GetAttribute("synapse:status")
        if status_attr and status_attr.Get() in ("pending", "executing"):
            status_attr.Set("suspended")
            task.CreateAttribute("synapse:suspendedAt", Sdf.ValueTypeNames.String).Set(now)

    stage.GetRootLayer().Save()


def resume_task(agent_usd_path: str, task_id: str) -> None:
    """Resume a suspended task — set status back to pending."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    task = stage.GetPrimAtPath(f"/SYNAPSE/agent/tasks/{task_id}")
    if task.IsValid():
        task.GetAttribute("synapse:status").Set("pending")
        stage.GetRootLayer().Save()


def abandon_task(agent_usd_path: str, task_id: str) -> None:
    """Abandon a suspended task."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    task = stage.GetPrimAtPath(f"/SYNAPSE/agent/tasks/{task_id}")
    if task.IsValid():
        task.GetAttribute("synapse:status").Set("abandoned")
        task.CreateAttribute("synapse:abandonedAt", Sdf.ValueTypeNames.String).Set(_now())
        stage.GetRootLayer().Save()


def load_agent_state(claude_dir: str) -> Dict[str, Any]:
    """Load agent state from agent.usd."""
    path = os.path.join(os.path.normpath(claude_dir), "agent.usd")
    state = {
        "status": "idle",
        "has_suspended_tasks": False,
        "suspended_count": 0,
        "suspended_tasks": [],
    }

    if not os.path.exists(path) or not PXR_AVAILABLE:
        return state

    try:
        stage = Usd.Stage.Open(path)
        agent_prim = stage.GetPrimAtPath("/SYNAPSE/agent")
        if agent_prim.IsValid():
            status_attr = agent_prim.GetAttribute("synapse:status")
            if status_attr:
                state["status"] = status_attr.Get() or "idle"

        tasks_prim = stage.GetPrimAtPath("/SYNAPSE/agent/tasks")
        if tasks_prim.IsValid():
            for task in tasks_prim.GetChildren():
                task_status = task.GetAttribute("synapse:status").Get()
                if task_status == "suspended":
                    desc_attr = task.GetAttribute("synapse:description")
                    state["suspended_tasks"].append({
                        "id": task.GetName(),
                        "description": desc_attr.Get() if desc_attr else "",
                    })

        state["suspended_count"] = len(state["suspended_tasks"])
        state["has_suspended_tasks"] = state["suspended_count"] > 0

    except Exception as e:
        logger.warning("Could not load agent state: %s", e)

    return state


def log_session(agent_usd_path: str, summary: Dict[str, Any]) -> None:
    """Write session summary to /SYNAPSE/agent/session_history/."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    now = _now()
    session_id = "session_" + now.replace("-", "_").replace(":", "_").replace("T", "_").rstrip("Z")

    prim = stage.DefinePrim(f"/SYNAPSE/agent/session_history/{session_id}", "Xform")
    prim.CreateAttribute("synapse:startTime", Sdf.ValueTypeNames.String).Set(
        summary.get("start_time", "")
    )
    prim.CreateAttribute("synapse:endTime", Sdf.ValueTypeNames.String).Set(
        summary.get("end_time", now)
    )
    prim.CreateAttribute("synapse:tasksCompleted", Sdf.ValueTypeNames.Int).Set(
        summary.get("tasks_completed", 0)
    )
    prim.CreateAttribute("synapse:tasksFailed", Sdf.ValueTypeNames.Int).Set(
        summary.get("tasks_failed", 0)
    )
    prim.CreateAttribute("synapse:tasksSuspended", Sdf.ValueTypeNames.Int).Set(
        summary.get("tasks_suspended", 0)
    )
    prim.CreateAttribute("synapse:summary", Sdf.ValueTypeNames.String).Set(
        summary.get("summary_text", "")
    )

    stage.GetRootLayer().Save()


def write_verification(agent_usd_path: str, task_id: str,
                       before_state: str, after_state: str,
                       checks: List, result: str) -> None:
    """Write verification log entry for a task."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    now = _now()
    verify_id = f"verify_{task_id}_{now.replace('-','').replace(':','').replace('T','_').rstrip('Z')}"

    prim = stage.DefinePrim(f"/SYNAPSE/agent/verification_log/{verify_id}", "Xform")
    prim.CreateAttribute("synapse:taskId", Sdf.ValueTypeNames.String).Set(task_id)
    prim.CreateAttribute("synapse:beforeState", Sdf.ValueTypeNames.String).Set(before_state)
    prim.CreateAttribute("synapse:afterState", Sdf.ValueTypeNames.String).Set(after_state)
    prim.CreateAttribute("synapse:checks", Sdf.ValueTypeNames.String).Set(str(checks))
    prim.CreateAttribute("synapse:result", Sdf.ValueTypeNames.String).Set(result)

    stage.GetRootLayer().Save()
```

**Step 4: Run Phase 2 tests**

Run: `python -m pytest tests/test_scene_memory.py::TestAgentState -v`
Expected: All PASS (or SKIP if no pxr)

**Step 5: Commit**

```bash
git add python/synapse/memory/agent_state.py tests/test_scene_memory.py
git commit -m "feat(memory): add agent_state.py — USD-based task tracking

Phase 2 of Living Memory. Create/update/suspend/resume tasks in agent.usd.
Session history logging. Verification log entries. All operations gracefully
degrade when pxr is not available."
```

---

### Task 8: Disconnect hook — suspend tasks on WebSocket close

**Files:**
- Modify: `python/synapse/server/websocket.py` (add disconnect hook)

**Step 1: Write the disconnect hook**

In `python/synapse/server/websocket.py`, in the `_handle_client` method's `finally` block (around line 330), after `bridge.end_session(session_id)`:

```python
            # Living Memory: suspend agent tasks and write session end
            if session_id:
                try:
                    from ..memory.scene_memory import write_session_end, ensure_scene_structure
                    from ..memory.agent_state import suspend_all_tasks, log_session
                    if HOU_AVAILABLE:
                        hip_path = hou.hipFile.path()
                        job_path = hou.getenv("JOB", os.path.dirname(hip_path))
                        paths = ensure_scene_structure(hip_path, job_path)

                        # Suspend any pending/executing tasks
                        agent_usd = paths.get("agent_usd", "")
                        if agent_usd and os.path.exists(agent_usd):
                            suspend_all_tasks(agent_usd)
                            log_session(agent_usd, {
                                "end_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "summary_text": f"Session ended (client: {client_id})",
                            })

                        # Write session end to memory.md
                        write_session_end(paths["scene_dir"], {
                            "stopped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        })
                except Exception as e:
                    logger.warning("Living Memory disconnect hook error: %s", e)
```

**Step 2: Commit**

```bash
git add python/synapse/server/websocket.py
git commit -m "feat(memory): add disconnect hook — suspend tasks + write session end

On WebSocket close: suspend all pending/executing tasks in agent.usd,
log session summary, write session end to memory.md. Wrapped in
try/except to never break existing disconnect flow."
```

---

### Task 9: Update `scene_memory.py` to use real agent_state

**Files:**
- Modify: `python/synapse/memory/scene_memory.py`

**Step 1: Replace agent stub with real agent_state integration**

In `ensure_scene_structure()`, replace `_seed_agent_usd_stub` call:

```python
    # Seed agent.usd
    agent_usd = os.path.join(scene_dir, "agent.usd")
    if not os.path.exists(agent_usd):
        try:
            from .agent_state import initialize_agent_usd
            initialize_agent_usd(agent_usd)
        except ImportError:
            _seed_agent_usd_stub(agent_usd)
```

In `load_full_context()`, replace the simple agent state read:

```python
    # Agent state
    agent = {"status": "idle", "has_suspended_tasks": False, "suspended_count": 0}
    try:
        from .agent_state import load_agent_state
        agent = load_agent_state(scene_claude)
    except ImportError:
        agent_usd = os.path.join(scene_claude, "agent.usd")
        if os.path.exists(agent_usd):
            agent["path"] = agent_usd
```

**Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add python/synapse/memory/scene_memory.py
git commit -m "feat(memory): wire scene_memory to real agent_state module

ensure_scene_structure uses agent_state.initialize_agent_usd.
load_full_context uses agent_state.load_agent_state. Both fall back
gracefully when pxr/agent_state unavailable."
```

---

### Task 10: Phase 2 milestone

**Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All ~790+ tests PASS

**Step 2: Commit milestone**

```bash
git add -A
git commit -m "milestone: Phase 2 complete — agent.usd state tracking

- agent_state.py: create/update/suspend/resume tasks via USD
- Disconnect hook: auto-suspend on WebSocket close
- Session history logging in agent.usd
- Verification log entries
- scene_memory.py wired to real agent_state"
```

---

## Phase 3: Evolution — Charmander to Charmeleon

**Do not start until all Phase 2 tests pass.**

---

### Task 11: Create `synapse_evolution.py` — evolution detection

**Files:**
- Create: `python/synapse/memory/evolution.py`
- Modify: `tests/test_scene_memory.py`

**Step 1: Write failing tests**

```python
# Import evolution module
_evo_spec = importlib.util.spec_from_file_location(
    "evolution",
    os.path.join(os.path.dirname(__file__), "..", "python", "synapse", "memory", "evolution.py"),
)
evo = importlib.util.module_from_spec(_evo_spec)
_evo_spec.loader.exec_module(evo)


class TestEvolutionDetection:
    """Tests for evolution trigger detection."""

    def test_count_structured_data_empty(self, tmp_path):
        md = tmp_path / "memory.md"
        md.write_text("# Scene Memory\n\n---\n\n", encoding="utf-8")
        counts = evo.count_structured_data(str(md))
        assert counts["structured_data_count"] == 0
        assert counts["node_path_references"] == 0

    def test_count_structured_data_with_node_paths(self, tmp_path):
        md = tmp_path / "memory.md"
        content = "# Scene Memory\n\n"
        for i in range(12):
            content += f"Modified /obj/geo{i}/mountain1\n"
        md.write_text(content, encoding="utf-8")
        counts = evo.count_structured_data(str(md))
        assert counts["node_path_references"] >= 10

    def test_check_evolution_not_triggered(self, tmp_path):
        md = tmp_path / "memory.md"
        md.write_text("# Scene Memory\nSimple note\n", encoding="utf-8")
        result = evo.check_evolution(str(tmp_path))
        assert result["should_evolve"] is False

    def test_check_evolution_triggered_by_node_paths(self, tmp_path):
        md = tmp_path / "memory.md"
        content = "# Scene Memory\n\n"
        for i in range(15):
            content += f"- Set /obj/geo{i}/mountain1 scale to 2.0\n"
        md.write_text(content, encoding="utf-8")
        result = evo.check_evolution(str(tmp_path))
        assert result["should_evolve"] is True
        assert "node_path_references" in result["triggers_met"]

    def test_parse_markdown_memory(self, tmp_path):
        md = tmp_path / "memory.md"
        content = (
            "# Scene Memory: test.hip\n\n---\n\n"
            "## Session 2026-02-11 14:00:00\n"
            "**Goal:** Set up lighting\n"
            "### Decision: Render Engine\n"
            "**Choice:** Karma XPU\n"
            "**Reasoning:** GPU speed\n"
            "### Parameter: /stage/karma1 / samples\n"
            "- **Before:** 64\n"
            "- **After:** 256\n"
            "- **Result:** Clean render\n\n"
            "## Session 2026-02-12 10:00:00\n"
            "Simple notes here\n"
        )
        md.write_text(content, encoding="utf-8")
        parsed = evo.parse_markdown_memory(str(md))
        assert len(parsed["sessions"]) == 2
        assert len(parsed["decisions"]) >= 1
        assert len(parsed["parameters"]) >= 1
```

**Step 2: Implement `evolution.py`**

Create `python/synapse/memory/evolution.py`:

```python
"""
Synapse Memory Evolution — Charmander -> Charmeleon -> Charizard

Detects when markdown memory should evolve to USD. Handles the
conversion process and maintains companion markdown.
"""

import logging
import os
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger("synapse.evolution")

EVOLUTION_TRIGGERS = {
    "charmeleon": {
        "structured_data_count": 5,
        "asset_references": 3,
        "parameter_records": 5,
        "wedge_results": 1,
        "session_count": 10,
        "file_size_kb": 100,
        "node_path_references": 10,
    },
}


def count_structured_data(md_path: str) -> Dict[str, int]:
    """Count structured elements in a markdown memory file."""
    if not os.path.exists(md_path):
        return {k: 0 for k in EVOLUTION_TRIGGERS["charmeleon"]}

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
        if "### Wedge" in line or "wedge" in line.lower() and "result" in line.lower():
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

    if stage != "charmander":
        return {"should_evolve": False, "triggers_met": [], "target": None, "current": stage}

    md_path = os.path.join(claude_dir, "memory.md")
    counts = count_structured_data(md_path)
    triggers = EVOLUTION_TRIGGERS["charmeleon"]

    triggers_met = []
    for key, threshold in sorted(triggers.items()):
        if counts.get(key, 0) >= threshold:
            triggers_met.append(key)

    return {
        "should_evolve": len(triggers_met) > 0,
        "triggers_met": triggers_met,
        "target": "charmeleon" if triggers_met else None,
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

    sessions = []
    decisions = []
    assets = []
    parameters = []

    # Split by ## Session headers
    session_blocks = re.split(r'^## Session ', content, flags=re.MULTILINE)

    for i, block in enumerate(session_blocks[1:], 1):
        lines = block.strip().split("\n")
        header = lines[0] if lines else ""
        date = header.split()[0] if header else f"session_{i}"
        text = "\n".join(lines)

        session = {
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


def evolve_to_charmeleon(md_path: str, usd_path: str) -> Dict[str, Any]:
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
        "synapse:evolution": "charmeleon",
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
        "# Scene Memory (Charmeleon - auto-generated from USD)",
        f"# Source: {os.path.basename(usd_path)}",
        "# Do not edit — this file is regenerated from memory.usd",
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
```

**Step 3: Run Phase 3 tests**

Run: `python -m pytest tests/test_scene_memory.py::TestEvolutionDetection -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add python/synapse/memory/evolution.py tests/test_scene_memory.py
git commit -m "feat(memory): add evolution.py — Charmander to Charmeleon detection and conversion

Phase 3 of Living Memory. Counts structured data in markdown, detects
evolution triggers, parses markdown into structured sections, converts
to USD with lossless archival. Companion markdown auto-generated."
```

---

### Task 12: Add `synapse_evolve_memory` MCP tool

**Files:**
- Modify: `python/synapse/server/handlers.py` (add handler + registration)
- Modify: `mcp_server.py` (add Tool entry + dispatch)

**Step 1: Add handler in `handlers.py`**

Register: `reg.register("evolve_memory", self._handle_evolve_memory)`

Handler method:

```python
    def _handle_evolve_memory(self, payload: Dict) -> Dict:
        """Manually trigger memory evolution."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from ..memory.evolution import check_evolution, evolve_to_charmeleon

        hip_path = hou.hipFile.path()
        hip_dir = os.path.dirname(hip_path)
        scope = resolve_param_with_default(payload, "scope", "scene")
        dry_run = resolve_param_with_default(payload, "dry_run", True)

        claude_dir = os.path.join(hip_dir, "claude")
        status = check_evolution(claude_dir)

        if dry_run:
            return {"dry_run": True, **status}

        if status["should_evolve"] and status["target"] == "charmeleon":
            md_path = os.path.join(claude_dir, "memory.md")
            usd_path = os.path.join(claude_dir, "memory.usd")
            result = evolve_to_charmeleon(md_path, usd_path)
            return {"dry_run": False, "evolved": True, **result}

        return {"dry_run": False, "evolved": False, "reason": "No evolution needed"}
```

**Step 2: Add MCP tool**

In `list_tools()`:

```python
        Tool(
            name="synapse_evolve_memory",
            description="Manually trigger memory evolution (Charmander->Charmeleon or Charmeleon->Charizard). Use dry_run=true to preview.",
            inputSchema={
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["scene", "project"]},
                    "target_stage": {"type": "string", "enum": ["charmeleon", "charizard"]},
                    "dry_run": {"type": "boolean", "description": "Preview without evolving. Default: true"},
                },
            },
        ),
```

In `call_tool()`:

```python
        elif name == "synapse_evolve_memory":
            cmd_type = "evolve_memory"
```

**Step 3: Commit**

```bash
git add python/synapse/server/handlers.py mcp_server.py
git commit -m "feat(memory): add synapse_evolve_memory MCP tool

Manual evolution trigger with dry_run preview. Dispatches to
evolution.evolve_to_charmeleon."
```

---

### Task 13: Wire evolution check into write_memory_entry

**Files:**
- Modify: `python/synapse/memory/scene_memory.py`

**Step 1: Update write_memory_entry to call check_evolution**

In `write_memory_entry()`, after calling the writer:

```python
    # Check if evolution should happen
    try:
        from .evolution import check_evolution
        evo = check_evolution(scene_dir)
        if evo.get("should_evolve"):
            logger.info("Evolution triggered: %s -> %s (triggers: %s)",
                       evo["current"], evo["target"], evo["triggers_met"])
            # Auto-evolution is logged but not auto-executed in Phase 3
            # Users can trigger via synapse_evolve_memory tool
    except ImportError:
        pass
```

**Step 2: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add python/synapse/memory/scene_memory.py
git commit -m "feat(memory): wire evolution check into write_memory_entry

Every memory write now checks evolution triggers. Logs when evolution
is recommended. Actual evolution requires explicit tool call."
```

---

### Task 14: Phase 3 milestone

**Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 2: Commit milestone**

```bash
git add -A
git commit -m "milestone: Phase 3 complete — Charmander to Charmeleon evolution

- evolution.py: trigger detection, markdown parsing, USD conversion
- Lossless evolution with archive of original markdown
- Companion markdown auto-generation from USD
- Memory pruning for old sessions
- synapse_evolve_memory MCP tool (dry_run + execute)
- Evolution check wired into every write"
```

---

## Phase 4: Evolution — Charmeleon to Charizard

**Do not start until all Phase 3 tests pass.**

---

### Task 15: USD Composition — project sublayering

**Files:**
- Modify: `python/synapse/memory/evolution.py` (add Charizard evolution)
- Modify: `tests/test_scene_memory.py`

**Step 1: Write failing test**

```python
@pytest.mark.skipif(not _pxr_available, reason="pxr not available")
class TestCharizardEvolution:
    """Tests for Charmeleon -> Charizard evolution."""

    def test_evolve_to_charizard_sublayers(self, tmp_path):
        # Set up project USD
        project_claude = tmp_path / "project" / "claude"
        project_claude.mkdir(parents=True)
        scene_claude = tmp_path / "project" / "scenes" / "shot_010" / "claude"
        scene_claude.mkdir(parents=True)

        # Create project.usd
        project_usd = str(project_claude / "project.usd")
        from pxr import Usd, Sdf
        stage = Usd.Stage.CreateNew(project_usd)
        stage.DefinePrim("/SYNAPSE", "Xform")
        stage.DefinePrim("/SYNAPSE/memory", "Xform")
        stage.GetRootLayer().Save()

        # Create scene memory.usd (Charmeleon)
        scene_usd = str(scene_claude / "memory.usd")
        stage2 = Usd.Stage.CreateNew(scene_usd)
        stage2.DefinePrim("/SYNAPSE", "Xform")
        stage2.DefinePrim("/SYNAPSE/memory", "Xform")
        stage2.GetRootLayer().customLayerData = {"synapse:evolution": "charmeleon"}
        stage2.GetRootLayer().Save()

        # Evolve to Charizard
        result = evo.evolve_to_charizard(scene_usd, project_usd)
        assert result["success"]

        # Verify sublayer
        stage3 = Usd.Stage.Open(scene_usd)
        sublayers = stage3.GetRootLayer().subLayerPaths
        assert len(sublayers) > 0
```

**Step 2: Implement `evolve_to_charizard` in `evolution.py`**

```python
def evolve_to_charizard(scene_usd_path: str, project_usd_path: str) -> Dict[str, Any]:
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

    # Add project.usd as sublayer (weaker — scene opinions override)
    project_rel = os.path.relpath(project_usd_path, os.path.dirname(scene_usd_path))
    # Normalize to forward slashes for USD
    project_rel = project_rel.replace("\\", "/")

    existing = list(layer.subLayerPaths)
    if project_rel not in existing:
        existing.append(project_rel)
        layer.subLayerPaths = existing

    # Update evolution metadata
    data = dict(layer.customLayerData)
    data["synapse:evolution"] = "charizard"
    layer.customLayerData = data

    layer.Save()

    return {"success": True, "sublayer": project_rel}
```

**Step 3: Run test**

Run: `python -m pytest tests/test_scene_memory.py::TestCharizardEvolution -v`
Expected: PASS or SKIP

**Step 4: Commit**

```bash
git add python/synapse/memory/evolution.py tests/test_scene_memory.py
git commit -m "feat(memory): add Charizard evolution — USD composition with project sublayer

Scene memory.usd sublayers project.usd. Scene opinions are stronger
(override project defaults). Relative paths for portability."
```

---

### Task 16: Cross-scene query support

**Files:**
- Modify: `python/synapse/server/handlers.py` (update memory_query handler)

**Step 1: Update `_handle_memory_query` for scope="all"**

When `scope="all"`, walk `$JOB/scenes/*/claude/memory.md` or `memory.usd` looking for matches:

```python
        # Cross-scene query
        if scope == "all" and HOU_AVAILABLE:
            job_path = hou.getenv("JOB", "")
            if job_path:
                import glob as glob_mod
                for scene_md in sorted(glob_mod.glob(os.path.join(job_path, "**", "claude", "memory.md"), recursive=True)):
                    if scene_md == os.path.join(hip_dir, "claude", "memory.md"):
                        continue  # Already searched current scene
                    scene_content = ""
                    try:
                        with open(scene_md, "r", encoding="utf-8") as f:
                            scene_content = f.read()
                    except Exception:
                        continue
                    if query_lower in scene_content.lower():
                        scene_name = os.path.basename(os.path.dirname(os.path.dirname(scene_md)))
                        for i, line in enumerate(scene_content.split("\n")):
                            if query_lower in line.lower():
                                results.append({
                                    "layer": f"scene:{scene_name}",
                                    "line": i + 1,
                                    "text": line.strip(),
                                })
```

**Step 2: Commit**

```bash
git add python/synapse/server/handlers.py
git commit -m "feat(memory): add cross-scene query support for scope=all

Walks $JOB/**/claude/memory.md to search across all scenes in the project."
```

---

### Task 17: Phase 4 milestone

**Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 2: Commit**

```bash
git add -A
git commit -m "milestone: Phase 4 complete — Charizard evolution + cross-scene queries

- USD composition: scene sublayers project memory
- Cross-scene queries via scope=all
- Full Charmander -> Charmeleon -> Charizard pipeline"
```

---

## Phase 5: Polish & Production Hardening

**Do not start until all Phase 4 tests pass.**

---

### Task 18: File locking for concurrent access

**Files:**
- Modify: `python/synapse/memory/scene_memory.py` (add file locking to writes)

**Step 1: Add file locking**

Use `msvcrt` on Windows, `fcntl` on Unix (or a simple `.lock` file approach):

```python
import threading

_file_locks: Dict[str, threading.Lock] = {}
_file_locks_lock = threading.Lock()

def _get_file_lock(path: str) -> threading.Lock:
    """Get or create a threading lock for a file path."""
    with _file_locks_lock:
        if path not in _file_locks:
            _file_locks[path] = threading.Lock()
        return _file_locks[path]
```

Wrap `_append_to_md` and write operations with the lock:

```python
def _append_to_md(md_path: str, text: str) -> None:
    if not os.path.exists(md_path):
        return
    lock = _get_file_lock(md_path)
    with lock:
        with open(md_path, "a", encoding="utf-8") as f:
            f.write(text)
```

**Step 2: Commit**

```bash
git add python/synapse/memory/scene_memory.py
git commit -m "fix(memory): add thread-safe file locking for concurrent writes"
```

---

### Task 19: Corruption recovery

**Files:**
- Modify: `python/synapse/memory/scene_memory.py` (add `validate_memory`)

**Step 1: Implement validation**

```python
def validate_memory(claude_dir: str) -> List[str]:
    """Validate memory files and return list of issues found."""
    issues = []
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
            except ImportError:
                pass  # pxr not available, skip USD validation
            except Exception as e:
                issues.append(f"{name}: Corrupted - {e}")
                # Backup corrupted file
                backup = path + f".corrupted.{int(time.time())}"
                import shutil
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
```

**Step 2: Commit**

```bash
git add python/synapse/memory/scene_memory.py
git commit -m "fix(memory): add validate_memory for corruption detection and recovery

Checks markdown encoding, USD parseability, /SYNAPSE root prim existence.
Auto-backs up corrupted files and reinitializes agent.usd."
```

---

### Task 20: Schema versioning

**Files:**
- Modify: `python/synapse/memory/scene_memory.py`

**Step 1: Add version check on load**

In `load_memory()`, after reading USD files:

```python
    # Schema version check
    try:
        from pxr import Usd
        stage = Usd.Stage.Open(usd_path)
        layer_data = stage.GetRootLayer().customLayerData
        file_version = layer_data.get("synapse:version", "0.0.0")
        if file_version != SCHEMA_VERSION:
            logger.info("Schema version mismatch: file=%s, current=%s", file_version, SCHEMA_VERSION)
    except (ImportError, Exception):
        pass
```

**Step 2: Commit**

```bash
git add python/synapse/memory/scene_memory.py
git commit -m "feat(memory): add schema version check on USD load"
```

---

### Task 21: Update CLAUDE.md + final test run

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update tool count and add Living Memory section**

In `CLAUDE.md`, update:
- MCP tool count: 38 -> 43 (5 new: project_setup, memory_write, memory_query, memory_status, evolve_memory)
- Add brief Living Memory section under Architecture

**Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Final commit**

```bash
git add -A
git commit -m "milestone: Phase 5 complete — Living Memory System production-ready

- File locking for concurrent access
- Corruption detection and recovery
- Schema versioning
- 43 MCP tools (was 38)
- Updated CLAUDE.md
- Full Charmander -> Charmeleon -> Charizard pipeline"
```

---

## Summary of Deliverables

| Phase | Module | Tests | MCP Tools |
|-------|--------|-------|-----------|
| 1 | `scene_memory.py` | ~20 | `synapse_project_setup`, `synapse_memory_write`, `synapse_memory_query`, `synapse_memory_status` |
| 2 | `agent_state.py` | ~10 | (integrated into project_setup) |
| 3 | `evolution.py` | ~6 | `synapse_evolve_memory` |
| 4 | (evolution.py ext) | ~2 | (cross-scene via memory_query) |
| 5 | (hardening) | — | — |

**Total new files:** 3 source + 1 test + 1 shelf tool
**Total new MCP tools:** 5
**Modified existing tools:** 3 (synapse_context, synapse_decide, synapse_add_memory)
**Modified existing files:** handlers.py, tracker.py, websocket.py, mcp_server.py, CLAUDE.md
