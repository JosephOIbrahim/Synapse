"""Tests for the Living Memory scene memory system."""

import os
import sys
import time
import json
import shutil
import tempfile
import threading

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
        assert "Project" in ctx["summary"]

    def test_load_full_context_prioritizes_blockers(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        # Add a blocker and a decision to scene memory
        sm.write_blocker(result["scene_dir"], {
            "description": "SSS artifacts on hero skin",
            "attempts": "Increased samples",
        })
        sm.write_decision(result["scene_dir"], {
            "name": "Render Engine",
            "choice": "Karma XPU",
            "reasoning": "GPU speed",
        })
        ctx = sm.load_full_context(tmp_project["hip_dir"], tmp_project["job"])
        # Smart extraction should surface blockers and decisions
        assert "Blocker" in ctx["summary"] or "SSS" in ctx["summary"]
        assert "Karma XPU" in ctx["summary"] or "Render Engine" in ctx["summary"]

    def test_write_memory_entry_dispatch(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        sm.write_memory_entry(result["scene_dir"], {"content": "Test note"}, "note")
        content = open(result["scene_md"], "r", encoding="utf-8").read()
        assert "Test note" in content


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


# ── Phase 2: Agent State Tests ─────────────────────────────────────

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


# ── Phase 3: Evolution Tests ──────────────────────────────────────

# Register scene_memory as a package-relative module so evolution's
# "from .scene_memory import ..." resolves correctly.
import types
_memory_pkg = types.ModuleType("synapse.memory")
_memory_pkg.__path__ = [os.path.join(os.path.dirname(__file__), "..", "python", "synapse", "memory")]
sys.modules.setdefault("synapse", types.ModuleType("synapse"))
sys.modules.setdefault("synapse.memory", _memory_pkg)
sys.modules.setdefault("synapse.memory.scene_memory", sm)

_evo_spec = importlib.util.spec_from_file_location(
    "synapse.memory.evolution",
    os.path.join(os.path.dirname(__file__), "..", "python", "synapse", "memory", "evolution.py"),
    submodule_search_locations=[],
)
evo = importlib.util.module_from_spec(_evo_spec)
evo.__package__ = "synapse.memory"
_evo_spec.loader.exec_module(evo)
sys.modules["synapse.memory.evolution"] = evo


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

    def test_prune_memory_no_op_when_few_sessions(self, tmp_path):
        md = tmp_path / "memory.md"
        content = "# Scene Memory\n\n## Session 2026-02-11\nNotes\n"
        md.write_text(content, encoding="utf-8")
        result = evo.prune_memory(str(tmp_path))
        assert result["pruned_sessions"] == 0

    def test_count_nonexistent_file(self, tmp_path):
        counts = evo.count_structured_data(str(tmp_path / "missing.md"))
        assert counts["structured_data_count"] == 0
        assert counts["session_count"] == 0


# ── Phase 4: Charizard Evolution Tests ────────────────────────────

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

    def test_charizard_metadata_updated(self, tmp_path):
        project_claude = tmp_path / "project" / "claude"
        project_claude.mkdir(parents=True)
        scene_claude = tmp_path / "project" / "scenes" / "shot_010" / "claude"
        scene_claude.mkdir(parents=True)

        project_usd = str(project_claude / "project.usd")
        stage = Usd.Stage.CreateNew(project_usd)
        stage.DefinePrim("/SYNAPSE", "Xform")
        stage.GetRootLayer().Save()

        scene_usd = str(scene_claude / "memory.usd")
        stage2 = Usd.Stage.CreateNew(scene_usd)
        stage2.DefinePrim("/SYNAPSE", "Xform")
        stage2.GetRootLayer().customLayerData = {"synapse:evolution": "charmeleon"}
        stage2.GetRootLayer().Save()

        evo.evolve_to_charizard(scene_usd, project_usd)

        stage3 = Usd.Stage.Open(scene_usd)
        data = dict(stage3.GetRootLayer().customLayerData)
        assert data.get("synapse:evolution") == "charizard"

    def test_charizard_missing_files(self, tmp_path):
        result = evo.evolve_to_charizard(
            str(tmp_path / "missing.usd"),
            str(tmp_path / "also_missing.usd"),
        )
        assert result["success"] is False


# ── Phase 5: Hardening Tests ─────────────────────────────────────

class TestValidateMemory:
    """Tests for corruption detection and recovery."""

    def test_validate_healthy_dir(self, tmp_project):
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        issues = sm.validate_memory(result["scene_dir"])
        assert issues == []

    def test_validate_empty_md(self, tmp_path):
        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()
        (claude_dir / "memory.md").write_text("", encoding="utf-8")
        issues = sm.validate_memory(str(claude_dir))
        assert any("Empty file" in i for i in issues)

    def test_validate_nonexistent_dir(self, tmp_path):
        issues = sm.validate_memory(str(tmp_path / "missing"))
        assert issues == []


class TestFileLocking:
    """Tests for thread-safe file writes."""

    def test_concurrent_appends(self, tmp_project):
        """Multiple threads writing simultaneously should not corrupt the file."""
        result = sm.ensure_scene_structure(tmp_project["hip"], tmp_project["job"])
        md_path = result["scene_md"]

        def write_note(n):
            sm._append_to_md(md_path, f"\nNote {n}\n")

        threads = [threading.Thread(target=write_note, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        content = open(md_path, "r", encoding="utf-8").read()
        # All 10 notes should be present
        for i in range(10):
            assert f"Note {i}" in content
