"""The two spatial tools' wiring (D6, R-5): registry, policy, RBAC, the D-1 pin.

Pure Python, no Houdini and no OpenUSD, so every check here runs on stock CI.
The measurement itself is pinned by test_spatial_path.py (known answers),
test_spatial_trail_pxr.py (the trail's code on a real stage) and
test_spatial_handlers_pxr.py (the handlers over a real stage).

What R-5 ratified, and what this file holds it to:

    synapse_spatial_path   read. Viewer and up. Allowed in every worker mode.
    synapse_spatial_trail  one build. Artist and up. Standard and unrestricted
                           worker modes only; demo, strict and proposal deny it.
                           It carries build_graph's tier (review) and sits on
                           the worker's builder allowlist beside build_graph.

Nothing else in the lane is registered: describe, classify and frustum stay
unregistered (rule D-1), and SYNAPSE_SPATIAL_LANE stays unread.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
for _p in (str(_REPO), str(_REPO / "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.core.errors import HoudiniUnavailableError, SynapseUserError  # noqa: E402
from synapse.mcp import _tool_registry as registry  # noqa: E402
from synapse.panel import bridge_adapter, worker_policy  # noqa: E402
from synapse.server import handlers as handlers_mod  # noqa: E402
from synapse.server import handlers_spatial as hs  # noqa: E402
from synapse.server.rbac import Role, check_permission  # noqa: E402

READ, TRAIL = "synapse_spatial_path", "synapse_spatial_trail"
_DEFS = {d[0]: d for d in registry.TOOL_DEFS}


# --------------------------------------------------------------------------- #
#  Rule D-1, as R-5 amended it                                                #
# --------------------------------------------------------------------------- #
def _scanned():
    """Every runtime module a registration could hide in: python/**, shared/,
    host/, scripts/, and the repo-root modules (mcp_server.py and the
    mcp_tools_*.py files BP4-CRUX found unscanned). harness/ is review tooling
    that quotes the lane's names on purpose, and nothing imports it at runtime."""
    files = [p for p in (_REPO / "python").rglob("*.py") if "/synapse/spatial/" not in p.as_posix()]
    for folder in ("shared", "host", "scripts"):
        files += sorted((_REPO / folder).rglob("*.py"))
    return files + sorted(_REPO.glob("*.py"))


def test_d1_lifts_for_exactly_two_tools():
    """Outside the spatial package: one module imports it, two tool names
    exist, the three stage queries and the lane's env flag appear nowhere."""
    importers, queries, env, names = [], [], [], set()
    for py in _scanned():
        text = py.read_text(encoding="utf-8", errors="ignore")
        rel = py.relative_to(_REPO).as_posix()
        if re.search(r"synapse\.spatial\b|from \.+spatial\b|\bimport spatial\b", text):
            importers.append(rel)
        if re.search(r"synapse_spatial_(describe|classify|frustum)", text):
            queries.append(rel)
        if "SYNAPSE_SPATIAL_LANE" in text:
            env.append(rel)
        names.update(re.findall(r"synapse_spatial_[a-z_]+", text))
    assert importers == ["python/synapse/server/handlers_spatial.py"], importers
    assert queries == [], "the three stage queries are referenced outside their package: %s" % queries
    assert env == [], "SYNAPSE_SPATIAL_LANE is wired outside the package: %s" % env
    assert names == {READ, TRAIL}, names


def test_the_registry_holds_exactly_the_two_spatial_tools():
    spatial = sorted(d[0] for d in registry.TOOL_DEFS if "spatial" in d[0] or "spatial" in d[1])
    assert spatial == [READ, TRAIL]
    assert not [d[0] for d in registry.PENDING_TOOL_DEFS if "spatial" in d[0]]
    assert READ in registry.TOOL_NAMES and TRAIL in registry.TOOL_NAMES


def test_the_spatial_module_serves_exactly_two_commands():
    """Whatever a command is called: the live dispatcher holds two handlers
    that live in handlers_spatial.py, and no third one under another name."""
    reg = handlers_mod.SynapseHandler()._registry
    served = sorted(cmd for cmd in reg.registered_types
                    if getattr(reg.get(cmd), "__func__", reg.get(cmd)).__module__ == hs.__name__)
    assert served == ["get_spatial_path", "spatial_trail"]
    public = sorted(name for name in vars(hs.SpatialHandlerMixin) if name.startswith("_handle_"))
    assert public == ["_handle_get_spatial_path", "_handle_spatial_trail"]


def test_no_tool_in_the_lane_names_a_vendor():
    """D4: the lane is ``spatial``. No vendor in a tool's name, text or schema."""
    for name in (READ, TRAIL):
        text = json.dumps(registry.TOOL_JSON[name]).lower()
        assert "world labs" not in text and "worldlabs" not in text and "marble" not in text


# --------------------------------------------------------------------------- #
#  The registry entries                                                       #
# --------------------------------------------------------------------------- #
def test_the_read_is_read_only_and_the_trail_is_a_build():
    _, cmd, _, _, _, read_only, destructive, idempotent = _DEFS[READ]
    assert (cmd, read_only, destructive, idempotent) == ("get_spatial_path", True, False, True)
    _, cmd, _, _, _, read_only, destructive, idempotent = _DEFS[TRAIL]
    assert (cmd, read_only, destructive, idempotent) == ("spatial_trail", False, False, True)
    assert registry.TOOL_JSON[READ]["annotations"]["readOnlyHint"] is True
    assert registry.TOOL_JSON[TRAIL]["annotations"]["readOnlyHint"] is False


def test_nothing_is_required_and_only_the_declared_inputs_pass():
    """Each tool works with no arguments (the display node and its render
    camera), and the payload carries only what the schema declares, so a model
    cannot hand the trail code or coordinates."""
    for name, keys in ((READ, {"node", "camera", "frames", "against"}),
                       (TRAIL, {"node", "camera", "frames", "purpose"})):
        schema = _DEFS[name][4]
        assert set(schema["properties"]) == keys and schema["required"] == []
        build = _DEFS[name][2]
        assert build({}) == {}
        stuffed = dict({k: "x" for k in keys}, code="import os", python="x", points=[[0, 0, 0]])
        assert set(build(stuffed)) == keys
    assert _DEFS[READ][4]["properties"]["against"]["enum"] == list(hs.AGAINST)
    assert _DEFS[TRAIL][4]["properties"]["purpose"]["enum"] == list(hs.PURPOSES)


def test_each_description_is_two_sentences():
    """Two tools ride every model round, so each says its piece briefly."""
    for name in (READ, TRAIL):
        desc = _DEFS[name][3]
        assert len(desc) < 420, len(desc)
        assert len(re.findall(r"[.;:]\s+[A-Z]", desc)) <= 2


# --------------------------------------------------------------------------- #
#  Handlers, RBAC, the bridge and the worker                                  #
# --------------------------------------------------------------------------- #
def test_both_commands_are_registered_and_classified():
    handler = handlers_mod.SynapseHandler()
    assert handler._registry.get("get_spatial_path") is not None
    assert handler._registry.get("spatial_trail") is not None
    assert "get_spatial_path" in handlers_mod._READ_ONLY_COMMANDS
    assert "spatial_trail" not in handlers_mod._READ_ONLY_COMMANDS      # it takes the mutation lock
    assert handlers_mod._CMD_CATEGORY["spatial_trail"] is handlers_mod.AuditCategory.PIPELINE


def test_rbac_viewers_read_and_artists_build():
    assert check_permission(Role.VIEWER, "get_spatial_path")
    assert not check_permission(Role.VIEWER, "spatial_trail")
    for role in (Role.ARTIST, Role.LEAD, Role.ADMIN):
        assert check_permission(role, "get_spatial_path") and check_permission(role, "spatial_trail")


def test_the_bridge_skips_the_read_and_gives_the_trail_build_graphs_tier():
    """The trail builds through solaris_build_graph, so it is classed as that
    is (review), not as a lighter one; the worker reaches both the same way."""
    assert bridge_adapter.is_read_only(READ)
    assert not bridge_adapter.is_read_only(TRAIL)
    assert READ not in bridge_adapter._TOOL_TO_OPERATION
    ops = bridge_adapter._TOOL_TO_OPERATION
    assert ops[TRAIL] == ops["synapse_solaris_build_graph"] == "build_from_manifest"
    assert worker_policy.OPERATION_GATES["build_from_manifest"] == "review"
    assert TRAIL not in bridge_adapter._DISK_WRITING_TOOLS              # it writes no file
    assert worker_policy._WORKER_BUILDER_ALLOWLIST == frozenset({
        "synapse_solaris_build_graph", "synapse_solaris_assemble_chain", TRAIL})
    allowed, why = worker_policy.is_tool_allowed_for_worker(TRAIL, profile="standard")
    assert allowed and "composite Solaris builder" in why


def _through_the_bridge(monkeypatch, tool, command_type, payload):
    """What the panel's bridge is handed for one tool call: the Operation."""
    from types import SimpleNamespace
    from synapse.core.protocol import SynapseCommand, SynapseResponse
    operations = []
    command = SynapseCommand(type=command_type, id="label-test", payload=payload)
    response = SynapseResponse(id=command.id, success=True, data={"status": "SUCCESS"})

    class Bridge:
        def execute(self, operation):
            operations.append(operation)
            return SimpleNamespace(success=True, result=operation.fn(), integrity=None)

    monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: Bridge())
    handler = SimpleNamespace(handle=lambda received: response if received is command else None)
    assert bridge_adapter.execute_through_bridge(tool, handler, command) is response
    assert len(operations) == 1
    return operations[0]


def test_the_trails_undo_step_is_named_in_words_and_named_once(monkeypatch):
    """UNDOLABEL (the recorded GUI checks, 2026-10-02). Houdini's Edit menu and
    status bar named the step ``SYNAPSE: synapse_spatial_trail: {}``: the tool's
    internal name and its empty arguments, while the tool's own result called it
    ``SYNAPSE: spatial_trail``. The bridge's group is the outer one, so its name
    is the one Houdini shows. Now there is one name, in words, and the result
    reports the name the artist sees."""
    from synapse.panel import turn_revert
    from synapse.server.handler_helpers import undo_receipt

    operation = _through_the_bridge(monkeypatch, TRAIL, "spatial_trail", {})
    shown = "SYNAPSE: " + operation.summary            # shared/bridge.py opens the group under this
    assert shown == "SYNAPSE: Draw camera path"
    assert shown == hs.TRAIL_UNDO                      # the label the tool's result reports
    assert "spatial_trail" not in shown and "{" not in shown
    assert turn_revert.is_synapse_label(shown)         # REVERT still knows the step as SYNAPSE's
    assert operation.operation_type == "build_from_manifest"
    # Arguments do not change the name: one step, one name.
    with_args = _through_the_bridge(monkeypatch, TRAIL, "spatial_trail",
                                    {"node": "/stage/out", "camera": "/cameras/a", "frames": "1-48"})
    assert with_args.summary == operation.summary
    assert with_args.kwargs["node_path"] == "/stage/out"       # the target still reaches integrity
    assert undo_receipt(hs.TRAIL_UNDO)["undo"]["artist"] == "One Ctrl+Z reverses: Draw camera path"


def test_other_tools_keep_the_label_they_had(monkeypatch):
    """The plain name is the trail's. Every other tool's summary is also the
    text of its consent card, so it is not reworded in passing."""
    payload = {"parent": "/obj", "type": "geo"}
    operation = _through_the_bridge(monkeypatch, "houdini_create_node", "create_node", payload)
    assert operation.summary == "houdini_create_node: %s" % str(payload)[:80]


@pytest.mark.parametrize("mode, read_ok, trail_ok", [
    ("standard", True, True), ("unrestricted", True, True),
    ("demo", True, False), ("strict", True, False), ("proposal", True, False),
])
def test_worker_policy_by_mode(mode, read_ok, trail_ok):
    assert worker_policy.is_tool_allowed_for_worker(READ, profile=mode)[0] is read_ok
    assert worker_policy.is_tool_allowed_for_worker(TRAIL, profile=mode)[0] is trail_ok


def test_without_houdini_both_say_so(monkeypatch):
    monkeypatch.setattr(hs, "HOU_AVAILABLE", False)
    mixin = hs.SpatialHandlerMixin()
    with pytest.raises(HoudiniUnavailableError):
        mixin._handle_get_spatial_path({})
    with pytest.raises(HoudiniUnavailableError):
        mixin._handle_spatial_trail({})


# --------------------------------------------------------------------------- #
#  Frames                                                                     #
# --------------------------------------------------------------------------- #
def test_frames_default_to_the_scene_range():
    frames = hs.parse_frames(None, 1, 120)
    assert frames[0] == 1.0 and frames[-1] == 120.0 and len(frames) == 120
    assert hs.parse_frames("", 1001, 1003) == [1001.0, 1002.0, 1003.0]


@pytest.mark.parametrize("spec, expect", [
    ("40", [40.0]), (40, [40.0]), ("1-4", [1.0, 2.0, 3.0, 4.0]),
    (" 1 - 9 x 4 ", [1.0, 5.0, 9.0]),
    ("1-10x4", [1.0, 5.0, 9.0, 10.0]),          # the last frame is always sampled
    ("-2-1", [-2.0, -1.0, 0.0, 1.0]),
])
def test_frames_spec(spec, expect):
    assert hs.parse_frames(spec, 0, 0) == expect


def test_a_long_range_widens_its_step_instead_of_sampling_more():
    frames = hs.parse_frames("1-5000", 0, 0)
    assert len(frames) == hs.MAX_SAMPLES and frames[0] == 1.0 and frames[-1] == 5000.0


@pytest.mark.parametrize("bad", ["10-1", "1-10x0", "all", "1,2,3", "1-10x-2", "1-10\nimport os"])
def test_bad_frames_are_a_user_error(bad):
    with pytest.raises(SynapseUserError):
        hs.parse_frames(bad, 1, 120)


def test_the_measure_budget_is_stated():
    """The read thins points past MAX_PAIRS and says so; the constants are the
    contract (about 2 s on the demo workstation, inside the 10 s transport)."""
    assert hs.MAX_SAMPLES == 1000 and hs.MAX_PAIRS == 150_000_000
    assert hs.CHECK_MM == 1.0 and hs.CHECK_DEG == 0.05
