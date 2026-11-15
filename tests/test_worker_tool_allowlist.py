"""Tests for SYNAPSE_WORKER_TOOL_ALLOWLIST, the explicit ceiling on the autonomous
worker's tools (worker_policy.active_tool_allowlist and its use in
is_tool_allowed_for_worker and tool_bridge.get_anthropic_tools_for_worker).

The contract under test, from the code's own comment: an unset or empty value
changes nothing; a set value is a comma-separated list of exact advertised
names that can only REMOVE tools, never grant one, in every policy mode.

Pure Python: no Qt, no hou. The import bootstrap mirrors
tests/test_worker_tool_policy.py so this worktree's panel modules are the ones
under test even when an editable install elsewhere binds ``synapse``.
"""

import os
import sys

import pytest

_PYTHON_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"
)
if sys.path and sys.path[0] != _PYTHON_DIR:
    sys.path.insert(0, _PYTHON_DIR)

_WORKTREE_PANEL_DIR = os.path.join(_PYTHON_DIR, "synapse", "panel")

import synapse.panel as _panel_pkg  # noqa: E402

_ppath = getattr(_panel_pkg, "__path__", None)
if _ppath is not None and _WORKTREE_PANEL_DIR not in list(_ppath):
    _ppath.insert(0, _WORKTREE_PANEL_DIR)
_wp = sys.modules.get("synapse.panel.worker_policy")
if _wp is None or not hasattr(_wp, "active_tool_allowlist"):
    for _name in ("synapse.panel.tool_bridge", "synapse.panel.worker_policy"):
        sys.modules.pop(_name, None)

from synapse.panel import tool_bridge as tb  # noqa: E402
from synapse.panel.worker_policy import (  # noqa: E402
    _ALLOWLIST_ENV_VAR,
    _ENV_VAR,
    _PROFILE_ENV_VAR,
    _VALID_MODES,
    active_tool_allowlist,
    is_tool_allowed_for_worker,
)

_REASON = "outside the configured worker tool allowlist"

# A realistic eight-tool list: node building plus the reads that support it.
_EXAMPLE_ALLOWLIST = (
    "houdini_create_node,houdini_connect_nodes,houdini_get_parm,houdini_set_parm,"
    "synapse_inspect_scene,synapse_inspect_node,houdini_layout_network,"
    "houdini_network_explain"
)


@pytest.fixture(autouse=True)
def _clean_worker_env(monkeypatch):
    """Every test starts unfiltered in the default mode, with an empty roster
    cache, whatever the operator's environment says."""
    for var in (_ALLOWLIST_ENV_VAR, _ENV_VAR, _PROFILE_ENV_VAR):
        monkeypatch.delenv(var, raising=False)
    tb._WORKER_TOOLS_CACHE.clear()
    yield
    tb._WORKER_TOOLS_CACHE.clear()


def _names(tools):
    return [t["name"] for t in tools]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def test_env_var_name_is_the_documented_one():
    assert _ALLOWLIST_ENV_VAR == "SYNAPSE_WORKER_TOOL_ALLOWLIST"


@pytest.mark.parametrize("raw", [None, "", "   ", ",", " , ,, "])
def test_unset_or_blank_means_unfiltered(monkeypatch, raw):
    if raw is not None:
        monkeypatch.setenv(_ALLOWLIST_ENV_VAR, raw)
    assert active_tool_allowlist() is None


def test_parses_trims_drops_empties_and_dedups_in_order(monkeypatch):
    monkeypatch.setenv(_ALLOWLIST_ENV_VAR, " b , a,,b , c ")
    assert active_tool_allowlist() == ("b", "a", "c")


def test_read_fresh_on_every_call(monkeypatch):
    monkeypatch.setenv(_ALLOWLIST_ENV_VAR, "a")
    assert active_tool_allowlist() == ("a",)
    monkeypatch.setenv(_ALLOWLIST_ENV_VAR, "b,c")
    assert active_tool_allowlist() == ("b", "c")
    monkeypatch.delenv(_ALLOWLIST_ENV_VAR)
    assert active_tool_allowlist() is None


# ---------------------------------------------------------------------------
# Policy: a ceiling in every mode, never a grant
# ---------------------------------------------------------------------------

def _every_tool_name():
    return _names(tb.get_anthropic_tools())


@pytest.mark.parametrize("mode", _VALID_MODES)
def test_outside_the_list_is_denied_in_every_mode(monkeypatch, mode):
    monkeypatch.setenv(_ENV_VAR, mode)
    monkeypatch.setenv(_ALLOWLIST_ENV_VAR, "synapse_inspect_scene")
    for name in _every_tool_name():
        if name == "synapse_inspect_scene":
            continue
        allowed, reason = is_tool_allowed_for_worker(name)
        assert (allowed, reason) == (False, _REASON), name


@pytest.mark.parametrize("mode", _VALID_MODES)
def test_inside_the_list_the_mode_decides_unchanged(monkeypatch, mode):
    """For listed tools the decision is exactly what the mode alone decides:
    the allowlist neither grants nor adds a denial."""
    monkeypatch.setenv(_ENV_VAR, mode)
    names = _every_tool_name()
    without = {n: is_tool_allowed_for_worker(n) for n in names}
    monkeypatch.setenv(_ALLOWLIST_ENV_VAR, ",".join(names))
    with_list = {n: is_tool_allowed_for_worker(n) for n in names}
    assert with_list == without


def test_cannot_grant_a_tool_the_mode_denies(monkeypatch):
    allowed, reason = is_tool_allowed_for_worker("houdini_execute_python")
    assert allowed is False
    monkeypatch.setenv(_ALLOWLIST_ENV_VAR, "houdini_execute_python")
    allowed2, reason2 = is_tool_allowed_for_worker("houdini_execute_python")
    assert allowed2 is False
    assert reason2 == reason and reason2 != _REASON


def test_profile_argument_is_still_capped(monkeypatch):
    monkeypatch.setenv(_ALLOWLIST_ENV_VAR, "synapse_inspect_scene")
    assert is_tool_allowed_for_worker("houdini_create_node", profile="unrestricted") == (False, _REASON)


def test_names_are_exact(monkeypatch):
    monkeypatch.setenv(_ALLOWLIST_ENV_VAR, "SYNAPSE_INSPECT_SCENE,synapse_inspect")
    assert is_tool_allowed_for_worker("synapse_inspect_scene") == (False, _REASON)


# ---------------------------------------------------------------------------
# Advertised roster: follows the list, and the cache re-keys on it
# ---------------------------------------------------------------------------

def test_roster_is_the_mode_roster_restricted_to_the_list(monkeypatch):
    unfiltered = _names(tb.get_anthropic_tools_for_worker())
    monkeypatch.setenv(_ALLOWLIST_ENV_VAR, _EXAMPLE_ALLOWLIST)
    listed = set(_EXAMPLE_ALLOWLIST.split(","))
    assert _names(tb.get_anthropic_tools_for_worker()) == [n for n in unfiltered if n in listed]


def test_example_list_gives_a_non_empty_subset(monkeypatch):
    monkeypatch.setenv(_ALLOWLIST_ENV_VAR, _EXAMPLE_ALLOWLIST)
    roster = _names(tb.get_anthropic_tools_for_worker())
    assert roster, "the example list should leave the worker some tools"
    assert set(roster) <= set(_EXAMPLE_ALLOWLIST.split(","))


def test_cache_rekeys_when_the_list_changes(monkeypatch):
    full = _names(tb.get_anthropic_tools_for_worker())
    monkeypatch.setenv(_ALLOWLIST_ENV_VAR, "synapse_inspect_scene")
    assert _names(tb.get_anthropic_tools_for_worker()) == [n for n in full if n == "synapse_inspect_scene"]
    monkeypatch.setenv(_ALLOWLIST_ENV_VAR, "synapse_inspect_node,synapse_inspect_scene")
    assert _names(tb.get_anthropic_tools_for_worker()) == [
        n for n in full if n in ("synapse_inspect_node", "synapse_inspect_scene")]
    monkeypatch.delenv(_ALLOWLIST_ENV_VAR)
    assert _names(tb.get_anthropic_tools_for_worker()) == full


def test_full_roster_is_never_filtered(monkeypatch):
    before = _names(tb.get_anthropic_tools())
    monkeypatch.setenv(_ALLOWLIST_ENV_VAR, "synapse_inspect_scene")
    assert _names(tb.get_anthropic_tools()) == before
