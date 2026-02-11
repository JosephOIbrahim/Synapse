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
