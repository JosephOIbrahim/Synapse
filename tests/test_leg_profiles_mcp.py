"""Every leg profile answers Claude Code's project MCP dialog in advance (BP12 item 6).

A leg starts as ``claude --settings <profile>`` in a fresh worktree. The repo's
``.mcp.json`` declares project MCP servers, and Claude Code asks whether to
approve them before the leg does anything. On 2026-09-28 that dialog stalled the
BP11 legs until ``disabledMcpjsonServers`` was set by hand in the two profiles
they launched with, and the edit was never committed. Each leg profile now lists
every server in ``.mcp.json``, so a server added there without a profile update
fails here. Joe's own sessions are left alone.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ("harness/agent-settings.json", "harness/relay-settings.json",
            "harness/readonly-settings.json")


def _project_servers() -> set:
    return set(json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"])


@pytest.mark.parametrize("profile", PROFILES)
def test_leg_profile_disables_every_project_mcp_server(profile):
    data = json.loads((ROOT / profile).read_text(encoding="utf-8"))
    disabled = data.get("disabledMcpjsonServers")
    assert isinstance(disabled, list), f"{profile} has no disabledMcpjsonServers list"
    missing = _project_servers() - set(disabled)
    assert not missing, f"{profile} would stop a leg at the MCP approval dialog for {sorted(missing)}"


def test_interactive_project_settings_keep_the_servers():
    """``.claude/settings.json`` governs Joe's own sessions and never disables them."""
    data = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert not set(data.get("disabledMcpjsonServers") or ()) & _project_servers()
