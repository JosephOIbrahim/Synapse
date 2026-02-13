"""Tests for synapse_agent.py -- agent entry point, system prompt, and sub-goal runners."""

import sys
import os
import pytest
from unittest.mock import MagicMock, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from synapse_agent import (
    _load_system_prompt,
    run_subgoal,
    run_subgoal_with_healing,
    MAX_SUBGOAL_TURNS,
    MAX_AGENT_TURNS,
)


def test_system_prompt_loads():
    """System prompt loads without error and contains key phrases."""
    prompt = _load_system_prompt()
    assert "Synapse VFX Co-Pilot" in prompt
    assert "Inspect scene" in prompt or "inspect" in prompt.lower()
    assert "undo group" in prompt.lower()
    assert "ONE mutation" in prompt or "one mutation" in prompt.lower()


def test_system_prompt_includes_claude_md():
    """System prompt includes content from CLAUDE.md."""
    prompt = _load_system_prompt()
    # CLAUDE.md has these unique phrases
    assert "supportive senior artist" in prompt.lower()
    assert "ensure_node" in prompt
    assert "xn__" in prompt


def test_max_subgoal_turns_less_than_agent():
    """Sub-goal turn limit is tighter than the overall agent limit."""
    assert MAX_SUBGOAL_TURNS < MAX_AGENT_TURNS
    assert MAX_SUBGOAL_TURNS == 10


def test_validate_tops_cook_hook():
    """validate_tops_cook warns on high max_retries."""
    from synapse_hooks import validate_tops_cook
    assert validate_tops_cook({"node": "/obj/topnet1/fetch1"}) is None
    assert validate_tops_cook({"max_retries": 3}) is None
    warning = validate_tops_cook({"max_retries": 10})
    assert warning is not None
    assert "long waits" in warning


@pytest.mark.asyncio
async def test_run_subgoal_injects_goal_message():
    """run_subgoal injects SUB-GOAL message into conversation."""
    from synapse_planner import SubGoal

    sg = SubGoal(id="test", description="Create a light", verification="Light exists")

    # Mock the anthropic client to return end_turn immediately
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "Done!"

    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_response.stop_reason = "end_turn"

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    messages = [{"role": "user", "content": "Initial context"}]

    success, updated_msgs = await run_subgoal(
        mock_client, sg, messages, "system prompt", [],
        lambda code: None, lambda inp: None,
        max_turns=1,
    )

    assert success is True
    # Check that SUB-GOAL message was injected
    goal_msgs = [m for m in updated_msgs if isinstance(m.get("content"), str) and "SUB-GOAL:" in m["content"]]
    assert len(goal_msgs) == 1
    assert "Create a light" in goal_msgs[0]["content"]


@pytest.mark.asyncio
async def test_run_subgoal_with_healing_marks_completed():
    """run_subgoal_with_healing marks sub-goal as completed on success."""
    from synapse_planner import SubGoal

    sg = SubGoal(id="test", description="Test", max_retries=2)

    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "Done"

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    success, _ = await run_subgoal_with_healing(
        mock_client, sg, [], "prompt", [],
        lambda code: None, lambda inp: None,
    )

    assert success is True
    assert sg.status == "completed"
    assert sg.attempts == 1
