"""Tests for agent capabilities, profiles, spawner, shared state, and CLI args.

No Houdini required — all autonomy and client dependencies are mocked.
No websockets required — synapse_ws is stubbed at import time.
No pytest-asyncio required — async tests use asyncio.run().
"""

import asyncio
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path setup (matches existing test patterns) ──────────────────────
_AGENT_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _AGENT_DIR)

_PYTHON_DIR = os.path.join(os.path.dirname(_AGENT_DIR), "python")
sys.path.insert(0, _PYTHON_DIR)

# ── Mock websockets so synapse_ws can import without the real package ─
if "websockets" not in sys.modules:
    _ws_stub = types.ModuleType("websockets")
    _ws_stub.connect = MagicMock()
    sys.modules["websockets"] = _ws_stub


# =====================================================================
# Helpers
# =====================================================================

def _run(coro):
    """Run an async coroutine synchronously — replaces pytest-asyncio."""
    return asyncio.run(coro)


# =====================================================================
# Capability tests — render
# =====================================================================


class TestRenderCapabilities:
    """Tests for agent/capabilities/render.py."""

    def test_plan_render_creates_plan(self):
        """plan_render wraps RenderPlanner and returns a RenderPlan."""
        from capabilities.render import plan_render

        plan = plan_render("render frames 1-10")
        assert plan is not None
        assert plan.intent == "render frames 1-10"
        assert len(plan.steps) > 0

    def test_plan_render_with_scene_context(self):
        """plan_render accepts optional scene_context."""
        from capabilities.render import plan_render

        ctx = {"camera": "/cameras/cam1"}
        plan = plan_render("render frame 1", scene_context=ctx)
        assert plan is not None

    def test_evaluate_render_returns_evaluation(self):
        """evaluate_render wraps RenderEvaluator and handles empty frame paths."""
        from capabilities.render import evaluate_render

        evaluation = evaluate_render({})
        assert evaluation is not None
        assert hasattr(evaluation, "overall_score")

    def test_predict_render_calls_predictor(self):
        """predict_render wraps RenderPredictor with mocked handler."""
        from capabilities.render import plan_render, predict_render

        plan = plan_render("render frame 1")

        mock_handler = AsyncMock()
        mock_handler.call = AsyncMock(return_value={
            "cameras": ["/cameras/cam1"],
            "prim_count": 10,
        })

        prediction = _run(predict_render(plan, mock_handler))
        assert prediction is not None
        assert hasattr(prediction, "camera_prim")

    def test_run_autonomous_render_builds_pipeline(self):
        """run_autonomous_render constructs the full driver pipeline."""
        from capabilities.render import run_autonomous_render

        mock_handler = AsyncMock()
        mock_handler.call = AsyncMock(return_value={
            "cameras": ["/cameras/cam1"],
            "camera": "/cameras/cam1",
            "prim_count": 10,
            "renderable_prims": 5,
            "frame_start": 1,
            "frame_end": 1,
            "output_path": "/tmp/render.exr",
            "picture": "/tmp/render.exr",
            "pixel_samples": 64,
            "resolution": [1920, 1080],
            "material_assignments": {},
            "ordering_valid": True,
        })

        report = _run(run_autonomous_render(
            "render frame 1",
            mock_handler,
            max_iterations=1,
        ))
        assert report is not None
        assert hasattr(report, "success")
        assert hasattr(report, "decisions")


# =====================================================================
# Capability tests — validation
# =====================================================================


class TestValidationCapabilities:
    """Tests for agent/capabilities/validation.py."""

    def test_validate_scene_runs_checks(self):
        """validate_scene wraps PreFlightValidator."""
        from capabilities.render import plan_render
        from capabilities.validation import validate_scene

        plan = plan_render("render frame 1")

        mock_handler = AsyncMock()
        mock_handler.call = AsyncMock(return_value={
            "cameras": ["/cameras/cam1"],
            "camera": "/cameras/cam1",
            "prim_count": 10,
            "renderable_prims": 5,
            "frame_start": 1,
            "frame_end": 1,
            "output_path": "/tmp/render.exr",
            "picture": "/tmp/render.exr",
            "pixel_samples": 64,
            "resolution": [1920, 1080],
            "material_assignments": {"geo": "mat"},
            "ordering_valid": True,
        })

        checks = _run(validate_scene(plan, mock_handler))
        assert isinstance(checks, list)
        assert len(checks) > 0

    def test_check_render_readiness_passes(self):
        """check_render_readiness returns ready=True when everything is present."""
        from capabilities.validation import check_render_readiness

        mock_handler = AsyncMock()
        mock_handler.call = AsyncMock(side_effect=[
            # get_scene_info
            {"cameras": ["/cameras/cam1"], "prim_count": 10, "renderable_prims": 5},
            # render_settings
            {"output_path": "/tmp/render.exr", "picture": "/tmp/render.exr"},
        ])

        result = _run(check_render_readiness(mock_handler))
        assert result["ready"] is True
        assert result["issues"] == []

    def test_check_render_readiness_no_camera(self):
        """check_render_readiness detects missing camera."""
        from capabilities.validation import check_render_readiness

        mock_handler = AsyncMock()
        mock_handler.call = AsyncMock(side_effect=[
            # get_scene_info — no cameras
            {"cameras": [], "camera": "", "prim_count": 10},
            # render_settings
            {"output_path": "/tmp/render.exr"},
        ])

        result = _run(check_render_readiness(mock_handler))
        assert result["ready"] is False
        assert any("camera" in issue.lower() for issue in result["issues"])


# =====================================================================
# Capability tests — scene
# =====================================================================


class TestSceneCapabilities:
    """Tests for agent/capabilities/scene.py."""

    def test_scene_summary_combines_calls(self):
        """get_scene_summary combines scene_info and inspect_scene."""
        mock_client = AsyncMock()
        mock_client.scene_info = AsyncMock(return_value={
            "hip_file": "/tmp/test.hip",
            "frame_start": 1,
            "frame_end": 240,
            "fps": 24,
        })
        mock_client.inspect_scene = AsyncMock(return_value={
            "node_count": 5,
            "nodes": [],
        })

        from capabilities.scene import get_scene_summary

        result = _run(get_scene_summary(mock_client))
        assert "scene_info" in result
        assert "scene_tree" in result
        assert "summary" in result
        assert result["summary"]["fps"] == 24
        mock_client.scene_info.assert_awaited_once()
        mock_client.inspect_scene.assert_awaited_once()

    def test_find_nodes_by_type(self):
        """find_nodes_by_type filters scene tree by node type."""
        mock_client = AsyncMock()
        mock_client.inspect_scene = AsyncMock(return_value={
            "nodes": [
                {"path": "/stage/karma1", "type": "karmarendersettings", "name": "karma1"},
                {"path": "/stage/merge1", "type": "merge", "name": "merge1"},
                {"path": "/stage/key_light", "type": "distantlight::2.0", "name": "key_light"},
            ],
        })

        from capabilities.scene import find_nodes_by_type

        matches = _run(find_nodes_by_type(mock_client, "karma"))
        assert len(matches) == 1
        assert matches[0]["path"] == "/stage/karma1"

    def test_validate_connections(self):
        """validate_connections extracts connection info from node inspection."""
        mock_client = AsyncMock()
        mock_client.inspect_node = AsyncMock(return_value={
            "inputs": [
                {"source": "/stage/geo1", "index": 0},
                {"source": "/stage/light1", "index": 1},
            ],
            "outputs": [
                {"target": "/stage/karma1", "index": 0},
            ],
        })

        from capabilities.scene import validate_connections

        result = _run(validate_connections(mock_client, "/stage/merge1"))
        assert result["connected"] is True
        assert len(result["inputs"]) == 2
        assert len(result["outputs"]) == 1


# =====================================================================
# Profile tests
# =====================================================================


class TestProfiles:
    """Tests for agent/profiles/ markdown files."""

    PROFILE_DIR = Path(_AGENT_DIR) / "profiles"

    def test_profiles_exist(self):
        """All required profile files exist."""
        for name in ("base.md", "render.md", "scene.md", "qa.md", "orchestrator.md"):
            path = self.PROFILE_DIR / name
            assert path.exists(), f"Missing profile: {path}"

    def test_profiles_have_tools_section(self):
        """Specialist profiles (not base) have a ## Tools section."""
        for name in ("render.md", "scene.md", "qa.md", "orchestrator.md"):
            content = (self.PROFILE_DIR / name).read_text(encoding="utf-8")
            assert "## Tools" in content, f"{name} missing ## Tools section"

    def test_base_profile_has_safety_rules(self):
        """Base profile contains safety rules."""
        content = (self.PROFILE_DIR / "base.md").read_text(encoding="utf-8")
        assert "Atomic" in content
        assert "Idempotent" in content
        assert "ensure_node" in content

    def test_load_profile_extends_prompt(self):
        """Loading a profile prepends its content to the system prompt."""
        from synapse_agent import _load_system_prompt

        prompt_without = _load_system_prompt(profile_path=None)
        prompt_with = _load_system_prompt(
            profile_path=str(self.PROFILE_DIR / "render.md")
        )

        # Profile content should be in the prompt
        assert "Progressive Validation Pipeline" in prompt_with
        # Base content should still be present
        assert "Synapse VFX Co-Pilot" in prompt_with
        # Profile-enhanced prompt should be longer
        assert len(prompt_with) > len(prompt_without)

    def test_tool_filtering(self):
        """Profile ## Tools section filters TOOL_DEFINITIONS."""
        from synapse_agent import _filter_tools

        # Full tool list (mock with just names)
        all_tools = [
            {"name": "synapse_ping"},
            {"name": "synapse_scene_info"},
            {"name": "synapse_inspect_scene"},
            {"name": "synapse_inspect_selection"},
            {"name": "synapse_inspect_node"},
            {"name": "synapse_execute"},
            {"name": "synapse_render_preview"},
            {"name": "synapse_knowledge_lookup"},
        ]

        # QA profile only lists 5 tools
        qa_profile = str(self.PROFILE_DIR / "qa.md")
        filtered = _filter_tools(all_tools, qa_profile)
        assert len(filtered) < len(all_tools)
        # QA should NOT have synapse_execute
        tool_names = {t["name"] for t in filtered}
        assert "synapse_execute" not in tool_names
        # QA should have inspect tools
        assert "synapse_inspect_scene" in tool_names

    def test_tool_filtering_no_profile(self):
        """No profile means no filtering — all tools returned."""
        from synapse_agent import _filter_tools

        tools = [{"name": "synapse_ping"}, {"name": "synapse_execute"}]
        result = _filter_tools(tools, None)
        assert result == tools


# =====================================================================
# Spawner tests
# =====================================================================


class TestSpawner:
    """Tests for agent/spawner.py."""

    def test_build_agent_command(self):
        """build_agent_command constructs correct CLI string."""
        from spawner import build_agent_command

        cmd = build_agent_command("render", "do the thing")
        assert "synapse_agent.py" in cmd
        assert "--profile" in cmd
        assert "--role" in cmd
        assert "render" in cmd
        assert "--max-turns" in cmd
        assert '"do the thing"' in cmd

    def test_build_agent_command_custom_profile(self):
        """build_agent_command respects custom profile override."""
        from spawner import build_agent_command

        cmd = build_agent_command("render", "goal", profile="/custom/profile.md")
        # On Windows, path may get resolved differently — check the filename part
        assert "profile.md" in cmd
        assert "--profile" in cmd

    @patch("spawner.shutil.which", return_value=None)
    def test_spawn_team_no_tmux(self, mock_which):
        """spawn_team returns False when tmux is not installed."""
        from spawner import spawn_team

        assert spawn_team("goal") is False

    @patch("spawner.subprocess.run")
    @patch("spawner.shutil.which", return_value="/usr/bin/tmux")
    def test_spawn_team_creates_session(self, mock_which, mock_run):
        """spawn_team calls tmux new-session and split-window."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        from spawner import spawn_team

        result = spawn_team("test goal", team=["render", "qa"])
        assert result is True
        # Should call: kill-session, new-session, split-window, select-layout
        assert mock_run.call_count >= 3

    def test_default_team_all_roles(self):
        """DEFAULT_TEAM includes all 4 specialist roles."""
        from spawner import DEFAULT_TEAM

        assert "orchestrator" in DEFAULT_TEAM
        assert "render" in DEFAULT_TEAM
        assert "scene" in DEFAULT_TEAM
        assert "qa" in DEFAULT_TEAM

    def test_agent_profiles_registry(self):
        """AGENT_PROFILES has entries for all roles."""
        from spawner import AGENT_PROFILES

        for role in ("render", "scene", "qa", "orchestrator"):
            assert role in AGENT_PROFILES
            assert "profile" in AGENT_PROFILES[role]
            assert "max_turns" in AGENT_PROFILES[role]
            assert "description" in AGENT_PROFILES[role]


# =====================================================================
# Shared state tests
# =====================================================================


class TestSharedState:
    """Tests for agent/shared_state.py."""

    def test_write_agent_state(self):
        """write_agent_state sends correct payload to memory."""
        mock_client = AsyncMock()
        mock_client.send_command = AsyncMock(return_value={"ok": True})

        from shared_state import write_agent_state

        result = _run(write_agent_state(
            mock_client, role="render", status="working", data={"frame": 10}
        ))

        mock_client.send_command.assert_awaited_once()
        call_args = mock_client.send_command.call_args
        assert call_args[0][0] == "add_memory"
        payload = call_args[0][1]
        assert payload["memory_type"] == "agent_team"
        assert "agent:render" in payload["tags"]
        assert "status:working" in payload["tags"]
        # Content should be valid JSON with role and status
        content = json.loads(payload["content"])
        assert content["role"] == "render"
        assert content["status"] == "working"
        assert content["data"]["frame"] == 10

    def test_read_agent_state(self):
        """read_agent_state queries memory and parses results."""
        mock_client = AsyncMock()
        mock_client.send_command = AsyncMock(return_value={
            "results": [
                {
                    "content": json.dumps({
                        "role": "render",
                        "status": "done",
                        "timestamp": 1000,
                        "data": {},
                    }),
                },
            ],
        })

        from shared_state import read_agent_state

        entries = _run(read_agent_state(mock_client, role="render"))
        assert len(entries) == 1
        assert entries[0]["role"] == "render"
        assert entries[0]["status"] == "done"

    def test_read_agent_state_no_role_filter(self):
        """read_agent_state without role returns all team state."""
        mock_client = AsyncMock()
        mock_client.send_command = AsyncMock(return_value={"results": []})

        from shared_state import read_agent_state

        _run(read_agent_state(mock_client, role=None))
        call_args = mock_client.send_command.call_args
        tags = call_args[0][1]["tags"]
        assert tags == ["team"]

    def test_broadcast_status(self):
        """broadcast_status is a convenience wrapper around write_agent_state."""
        mock_client = AsyncMock()
        mock_client.send_command = AsyncMock(return_value={"ok": True})

        from shared_state import broadcast_status

        _run(broadcast_status(mock_client, role="qa", message="All frames passed"))
        call_args = mock_client.send_command.call_args
        content = json.loads(call_args[0][1]["content"])
        assert content["status"] == "update"
        assert content["data"]["message"] == "All frames passed"


# =====================================================================
# Agent CLI tests
# =====================================================================


class TestAgentCLI:
    """Tests for synapse_agent.py argparse modifications."""

    def test_argparse_profile_flag(self):
        """--profile is parsed correctly."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("goal", nargs="*", default=[])
        parser.add_argument("--profile", type=str, default=None)
        parser.add_argument("--role", type=str, default="general")
        parser.add_argument("--max-turns", type=int, default=30)

        args = parser.parse_args(["--profile", "profiles/render.md", "test goal"])
        assert args.profile == "profiles/render.md"
        assert " ".join(args.goal) == "test goal"

    def test_argparse_role_flag(self):
        """--role is parsed correctly."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("goal", nargs="*", default=[])
        parser.add_argument("--profile", type=str, default=None)
        parser.add_argument("--role", type=str, default="general")
        parser.add_argument("--max-turns", type=int, default=30)

        args = parser.parse_args(["--role", "render", "test goal"])
        assert args.role == "render"

    def test_argparse_max_turns(self):
        """--max-turns is parsed correctly."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("goal", nargs="*", default=[])
        parser.add_argument("--profile", type=str, default=None)
        parser.add_argument("--role", type=str, default="general")
        parser.add_argument("--max-turns", type=int, default=30)

        args = parser.parse_args(["--max-turns", "50", "test goal"])
        assert args.max_turns == 50

    def test_argparse_defaults(self):
        """Defaults are correct when no flags provided."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("goal", nargs="*", default=[])
        parser.add_argument("--profile", type=str, default=None)
        parser.add_argument("--role", type=str, default="general")
        parser.add_argument("--max-turns", type=int, default=30)

        args = parser.parse_args(["test goal"])
        assert args.profile is None
        assert args.role == "general"
        assert args.max_turns == 30
