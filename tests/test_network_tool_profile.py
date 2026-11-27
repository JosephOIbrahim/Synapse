"""Compact 8-tool 'network' worker profile: policy, roster, prompt parity, settings, and worker gate."""
from __future__ import annotations

import os
import re
import sys
import types
from unittest.mock import MagicMock

import pytest

import pkgbootstrap

from synapse.mcp._tool_registry import TOOL_DEFS
from synapse.panel import settings as pset
from synapse.panel import system_prompt as sp
from synapse.panel import tool_bridge as tb
from synapse.panel import worker_policy as policy

TOOL_TOKEN_RE = re.compile(r"\b(?:synapse|houdini)_[A-Za-z0-9_]+\b")

EXPECTED_NETWORK_TOOLS = frozenset({
    "houdini_create_node",
    "houdini_connect_nodes",
    "houdini_get_parm",
    "houdini_set_parm",
    "synapse_inspect_scene",
    "synapse_inspect_node",
    "houdini_layout_network",
    "houdini_network_explain",
})


@pytest.fixture(autouse=True)
def _clean_env_and_cache(monkeypatch):
    monkeypatch.delenv(policy._ENV_VAR, raising=False)
    monkeypatch.delenv(policy._PROFILE_ENV_VAR, raising=False)
    tb._WORKER_TOOLS_CACHE.clear()
    yield
    tb._WORKER_TOOLS_CACHE.clear()


def test_network_mode_allows_exact_eight_tools_and_denies_all_others():
    assert policy.NETWORK_TOOLS == EXPECTED_NETWORK_TOOLS
    assert policy.resolve_mode("network") == "network"
    allowed_set = set()
    for entry in TOOL_DEFS:
        name = entry[0]
        allowed, reason = policy.is_tool_allowed_for_worker(name, profile="network")
        assert isinstance(reason, str) and reason
        if allowed:
            allowed_set.add(name)
    assert allowed_set == EXPECTED_NETWORK_TOOLS
    for denied in (
        "houdini_execute_python",
        "houdini_execute_vex",
        "houdini_delete_node",
        "houdini_render",
        "synapse_solaris_build_graph",
        "synapse_group_scene",
        "synapse_ping",
        "totally_unknown_tool",
    ):
        assert policy.is_tool_allowed_for_worker(denied, profile="network")[0] is False


def test_effective_panel_tool_profile_narrows_default_but_never_overrides_env(monkeypatch):
    assert policy.effective_panel_tool_profile("standard") is None
    assert policy.effective_panel_tool_profile(None) is None
    assert policy.effective_panel_tool_profile("bogus") is None
    assert policy.effective_panel_tool_profile("network") == "network"

    for env_mode in ("strict", "demo", "proposal", "standard", "unrestricted"):
        monkeypatch.setenv(policy._ENV_VAR, env_mode)
        assert policy.effective_panel_tool_profile("network") is None
        monkeypatch.delenv(policy._ENV_VAR, raising=False)

    monkeypatch.setenv(policy._PROFILE_ENV_VAR, "demo")
    assert policy.effective_panel_tool_profile("network") is None


def test_tool_bridge_advertises_exact_eight_tools_in_registry_order():
    standard_tools = tb.get_anthropic_tools_for_worker()
    network_tools = tb.get_anthropic_tools_for_worker(profile="network")
    assert len(network_tools) == 8
    assert len(standard_tools) > 50
    expected_order = [entry[0] for entry in TOOL_DEFS if entry[0] in EXPECTED_NETWORK_TOOLS]
    assert [t["name"] for t in network_tools] == expected_order
    # Ensure standard cache remains untouched after querying network profile.
    assert len(tb.get_anthropic_tools_for_worker()) == len(standard_tools)


def test_network_system_prompt_has_zero_unavailable_tool_references():
    for network in ("/obj", "/obj/geo1", "/stage", "/lop", "/unknown"):
        prompt = sp.build_network_system_prompt(
            {"network": network, "selection": [], "frame": 1, "hip": "untitled.hip"},
            houdini_build="Houdini 22.0.400",
        )
        mentioned = set(TOOL_TOKEN_RE.findall(prompt))
        assert mentioned <= EXPECTED_NETWORK_TOOLS, (network, mentioned - EXPECTED_NETWORK_TOOLS)
        assert "Houdini 22.0.400" in prompt
        assert f"- Network: {network}" in prompt


def test_settings_persists_and_sanitizes_tool_profile(tmp_path):
    p = tmp_path / "panel_settings.json"
    st = pset.default_settings()
    assert st["tool_profile"] == "standard"
    st["tool_profile"] = "network"
    assert pset.save_settings(st, path=p) is True
    assert pset.load_settings(path=p)["tool_profile"] == "network"

    p.write_text('{"tool_profile": "unrestricted"}', encoding="utf-8")
    assert pset.load_settings(path=p)["tool_profile"] == "standard"


def test_claude_worker_network_profile_filters_roster_and_blocks_dispatch(monkeypatch):
    touched = [
        "PySide6", "PySide6.QtCore",
        "PySide2", "PySide2.QtCore",
        "synapse.panel.claude_worker",
        "synapse.panel.tool_executor",
    ]
    saved = pkgbootstrap.snapshot_modules(touched)
    try:
        class _StubBase:
            def __init__(self, *a, **kw):
                pass

        class _QtCoreStub(types.ModuleType):
            QThread = _StubBase
            QObject = _StubBase

            @staticmethod
            def Signal(*a, **kw):
                return MagicMock()

            @staticmethod
            def Slot(*a, **kw):
                return lambda fn: fn

            def __getattr__(self, name):
                return MagicMock()

        qtcore = _QtCoreStub("PySide6.QtCore")
        pyside = types.ModuleType("PySide6")
        pyside.QtCore = qtcore
        sys.modules["PySide6"] = pyside
        sys.modules["PySide6.QtCore"] = qtcore
        sys.modules.pop("synapse.panel.tool_executor", None)
        sys.modules.pop("synapse.panel.claude_worker", None)

        import synapse.panel.claude_worker as cw

        sentinel = MagicMock(name="try_mcp_tool_call")
        monkeypatch.setattr(cw, "try_mcp_tool_call", sentinel)

        worker = cw.ClaudeWorker(
            [{"role": "user", "content": "connect box1 to OUT"}],
            system_prompt="",
            tools=None,
            enforce_worker_policy=True,
            tool_profile="network",
        )
        worker.tool_status = MagicMock()
        assert {t["name"] for t in worker._tools} == EXPECTED_NETWORK_TOOLS

        # A tool allowed in 'standard' mode (synapse_solaris_build_graph) is denied in 'network' mode.
        denied = worker._execute_tool_block({
            "id": "tu_net_1",
            "name": "synapse_solaris_build_graph",
            "input": {"parent": "/stage"},
        })
        assert denied["is_error"] is True
        assert "network mode" in denied["content"]
        sentinel.assert_not_called()
    finally:
        pkgbootstrap.restore_modules(saved)
