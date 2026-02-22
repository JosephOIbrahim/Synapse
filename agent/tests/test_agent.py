"""Tests for synapse_agent.py — agent entry point and system prompt."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from synapse_agent import _load_system_prompt


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
