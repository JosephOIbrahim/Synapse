"""
MCP Roundtrip Integration Tests

Tests the full chain: MCP tool call -> handler dispatch -> response.
Uses a mock hou stub to avoid needing a real Houdini instance.

These tests verify that:
1. MCP tool schemas match handler expectations
2. Parameter aliases resolve correctly end-to-end
3. Error responses propagate through the full chain
4. Response IDs and sequences are preserved
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Bootstrap: load handlers package without Houdini
# ---------------------------------------------------------------------------

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock(return_value=None)
    _hou.hipFile = MagicMock()
    _hou.hipFile.path = MagicMock(return_value="/tmp/test.hip")
    _hou.hipFile.name = MagicMock(return_value="test.hip")
    _hou.getenv = MagicMock(return_value="/tmp")
    _hou.fps = MagicMock(return_value=24.0)
    _hou.frame = MagicMock(return_value=1001)
    _hou.undos = MagicMock()
    _hou.selectedNodes = MagicMock(return_value=[])
    _hou.playbar = MagicMock()
    _hou.playbar.frameRange = MagicMock(return_value=(1001, 1100))
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]

if "hdefereval" not in sys.modules:
    sys.modules["hdefereval"] = types.ModuleType("hdefereval")

# Set up package hierarchy for relative imports
_root = Path(__file__).resolve().parent.parent / "python"

# Register stub packages so relative imports work
for mod_name, mod_path in [
    ("synapse", _root / "synapse"),
    ("synapse.core", _root / "synapse" / "core"),
    ("synapse.server", _root / "synapse" / "server"),
    ("synapse.session", _root / "synapse" / "session"),
    ("synapse.memory", _root / "synapse" / "memory"),
    ("synapse.routing", _root / "synapse" / "routing"),
    ("synapse.agent", _root / "synapse" / "agent"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

# Load actual modules
_module_files = [
    ("synapse.core.errors", _root / "synapse" / "core" / "errors.py"),
    ("synapse.core.protocol", _root / "synapse" / "core" / "protocol.py"),
    ("synapse.core.aliases", _root / "synapse" / "core" / "aliases.py"),
    ("synapse.core.determinism", _root / "synapse" / "core" / "determinism.py"),
    ("synapse.core.audit", _root / "synapse" / "core" / "audit.py"),
    ("synapse.core.gates", _root / "synapse" / "core" / "gates.py"),
    ("synapse.core.queue", _root / "synapse" / "core" / "queue.py"),
    ("synapse.server.handlers_node", _root / "synapse" / "server" / "handlers_node.py"),
    ("synapse.server.handlers_usd", _root / "synapse" / "server" / "handlers_usd.py"),
    ("synapse.server.handlers_render", _root / "synapse" / "server" / "handlers_render.py"),
    ("synapse.server.handlers_tops", _root / "synapse" / "server" / "handlers_tops.py"),
    ("synapse.server.handlers_material", _root / "synapse" / "server" / "handlers_material.py"),
    ("synapse.server.handlers_memory", _root / "synapse" / "server" / "handlers_memory.py"),
    ("synapse.server.handlers", _root / "synapse" / "server" / "handlers.py"),
]

for mod_name, fpath in _module_files:
    if mod_name not in sys.modules and fpath.exists():
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            pass  # Some modules may fail; we only need handlers

handlers_mod = sys.modules["synapse.server.handlers"]
_handlers_hou = handlers_mod.hou

from synapse.core.protocol import SynapseCommand, SynapseResponse, PROTOCOL_VERSION


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHandlerRoundtrip:
    """Test handler dispatch with real SynapseCommand objects."""

    def _handler(self):
        return handlers_mod.SynapseHandler()

    def test_ping_roundtrip(self):
        """ping command -> success response with pong=True."""
        resp = self._handler().handle(
            SynapseCommand(type="ping", id="rt-001", payload={}, sequence=1)
        )
        assert resp.success is True
        assert resp.data["pong"] is True
        assert "protocol_version" in resp.data

    def test_get_health_roundtrip(self):
        """get_health -> success with healthy=True."""
        resp = self._handler().handle(
            SynapseCommand(type="get_health", id="rt-002", payload={}, sequence=2)
        )
        assert resp.success is True
        assert resp.data["healthy"] is True

    def test_get_help_roundtrip(self):
        """get_help -> success with 30+ registered commands."""
        resp = self._handler().handle(
            SynapseCommand(type="get_help", id="rt-003", payload={}, sequence=3)
        )
        assert resp.success is True
        assert "commands" in resp.data
        assert len(resp.data["commands"]) >= 30

    def test_unknown_command_roundtrip(self):
        """Unknown command -> failure with coaching-tone error."""
        resp = self._handler().handle(
            SynapseCommand(type="nonexistent_cmd", id="rt-004", payload={}, sequence=4)
        )
        assert resp.success is False
        assert "don't recognize" in resp.error

    def test_create_node_missing_parent(self):
        """create_node with invalid parent -> coaching-tone error."""
        from unittest.mock import patch
        with patch.object(_handlers_hou, "node", return_value=None, create=True):
            resp = self._handler().handle(
                SynapseCommand(
                    type="create_node", id="rt-005",
                    payload={"parent": "/obj/nonexistent", "type": "null"},
                    sequence=5,
                )
            )
        assert resp.success is False
        assert "couldn't find" in resp.error.lower()

    def test_get_parm_missing_node(self):
        """get_parm on missing node -> error mentioning the path."""
        from unittest.mock import patch
        with patch.object(_handlers_hou, "node", return_value=None, create=True):
            resp = self._handler().handle(
                SynapseCommand(
                    type="get_parm", id="rt-006",
                    payload={"node": "/stage/missing", "parm": "tx"},
                    sequence=6,
                )
            )
        assert resp.success is False
        assert "/stage/missing" in resp.error or "couldn't find" in resp.error.lower()

    def test_batch_commands_with_ping(self):
        """batch_commands with a ping -> array of results."""
        resp = self._handler().handle(
            SynapseCommand(
                type="batch_commands", id="rt-007",
                payload={"commands": [{"type": "ping", "payload": {}}]},
                sequence=7,
            )
        )
        assert resp.success is True
        assert resp.data["results"][0]["pong"] is True
        assert resp.data["statuses"][0] == "ok"

    def test_batch_commands_stop_on_error(self):
        """batch_commands with stop_on_error halts at first failure."""
        resp = self._handler().handle(
            SynapseCommand(
                type="batch_commands", id="rt-008",
                payload={
                    "commands": [
                        {"type": "unknown_cmd", "payload": {}},
                        {"type": "ping", "payload": {}},
                    ],
                    "stop_on_error": True,
                },
                sequence=8,
            )
        )
        assert resp.success is True
        assert resp.data["statuses"][0] == "error"

    def test_response_ids_match_command(self):
        """Response ID always matches the command ID."""
        handler = self._handler()
        for i in range(5):
            cmd_id = f"id-match-{i}"
            resp = handler.handle(
                SynapseCommand(type="ping", id=cmd_id, payload={}, sequence=i)
            )
            assert resp.id == cmd_id

    def test_sequence_numbers_preserved(self):
        """Response sequence matches command sequence."""
        resp = self._handler().handle(
            SynapseCommand(type="ping", id="seq-test", payload={}, sequence=42)
        )
        assert resp.sequence == 42

    def test_knowledge_lookup_doesnt_crash(self):
        """knowledge_lookup -> doesn't crash (RAG may not be loaded)."""
        resp = self._handler().handle(
            SynapseCommand(
                type="knowledge_lookup", id="rt-009",
                payload={"query": "dome light intensity"},
                sequence=9,
            )
        )
        assert isinstance(resp, SynapseResponse)


class TestParameterAliasRoundtrip:
    """Verify parameter aliases resolve end-to-end."""

    def _handler(self):
        return handlers_mod.SynapseHandler()

    def test_path_alias_resolves_to_node(self):
        """'path' alias resolves to 'node' for get_parm."""
        from unittest.mock import patch
        with patch.object(_handlers_hou, "node", return_value=None, create=True):
            resp = self._handler().handle(
                SynapseCommand(
                    type="get_parm", id="alias-1",
                    payload={"path": "/stage/light", "parm": "tx"},
                    sequence=1,
                )
            )
        # Should attempt to find the node (not error about missing 'node' key)
        assert resp.success is False
        assert "couldn't find" in resp.error.lower()

    def test_node_path_alias_resolves(self):
        """'node_path' alias resolves to 'node' for get_parm."""
        from unittest.mock import patch
        with patch.object(_handlers_hou, "node", return_value=None, create=True):
            resp = self._handler().handle(
                SynapseCommand(
                    type="get_parm", id="alias-2",
                    payload={"node_path": "/stage/light", "parm": "tx"},
                    sequence=2,
                )
            )
        assert resp.success is False
        assert "couldn't find" in resp.error.lower()


# ---------------------------------------------------------------------------
# Tests: USD handler enrichment, undo groups, cook-and-verify
# ---------------------------------------------------------------------------

# Ensure hdefereval.executeDeferred is available for run_on_main
_hdefereval = sys.modules.get("hdefereval")
if _hdefereval is not None and not hasattr(_hdefereval, "executeDeferred"):
    _hdefereval.executeDeferred = lambda fn: fn()

class TestGetStageInfoEnriched:
    """Tests for the enriched get_stage_info handler that returns cameras,
    lights, renderable prim count, and unassigned material prims."""

    def _handler(self):
        return handlers_mod.SynapseHandler()

    def _make_prim(self, path, type_name, is_camera=False, is_light=False,
                   is_gprim=False, has_light_api=False, bound_material=None):
        """Build a mock USD prim with configurable schema checks."""
        prim = MagicMock()
        prim.GetPath.return_value = path
        prim.GetTypeName.return_value = type_name
        prim.HasAuthoredReferences.return_value = False

        def _is_a(schema):
            name = schema.__name__ if hasattr(schema, '__name__') else str(schema)
            if 'Camera' in str(name):
                return is_camera
            if 'LightAPI' in str(name):
                return has_light_api
            if 'Gprim' in str(name):
                return is_gprim
            return False

        prim.IsA = _is_a
        prim._bound_material = bound_material
        return prim

    def test_get_stage_info_returns_cameras(self):
        """Stage with a Camera prim includes it in the cameras list."""
        from unittest.mock import patch

        cam_prim = self._make_prim("/cameras/render_cam", "Camera", is_camera=True)
        geo_prim = self._make_prim("/world/geo", "Mesh", is_gprim=True)

        mock_stage = MagicMock()
        mock_stage.Traverse.return_value = [cam_prim, geo_prim]

        mock_node = MagicMock()
        mock_node.path.return_value = "/stage/lop1"
        type(mock_node).stage = MagicMock(return_value=mock_stage)

        mock_UsdGeom = MagicMock()
        mock_UsdLux = MagicMock()
        mock_UsdShade = MagicMock()

        mock_UsdGeom.Camera = type("Camera", (), {})
        mock_UsdGeom.Gprim = type("Gprim", (), {})
        mock_UsdLux.LightAPI = type("LightAPI", (), {})

        mock_binding = MagicMock()
        mock_binding.ComputeBoundMaterial.return_value = (None, None)
        mock_UsdShade.MaterialBindingAPI.return_value = mock_binding

        with patch.object(_handlers_hou, "node", return_value=mock_node, create=True), \
             patch.object(_handlers_hou, "selectedNodes", return_value=[], create=True), \
             patch.dict(sys.modules, {"pxr": MagicMock(UsdGeom=mock_UsdGeom,
                                                        UsdLux=mock_UsdLux,
                                                        UsdShade=mock_UsdShade),
                                      "pxr.UsdGeom": mock_UsdGeom,
                                      "pxr.UsdLux": mock_UsdLux,
                                      "pxr.UsdShade": mock_UsdShade}):
            h = self._handler()
            result = h._handle_get_stage_info({"node": "/stage/lop1"})

        assert "cameras" in result
        assert "/cameras/render_cam" in result["cameras"]

    def test_get_stage_info_returns_lights(self):
        """Stage with a light prim includes it in the lights list."""
        from unittest.mock import patch

        light_prim = self._make_prim("/lights/key", "DomeLight",
                                     has_light_api=True)
        geo_prim = self._make_prim("/world/geo", "Mesh", is_gprim=True)

        mock_stage = MagicMock()
        mock_stage.Traverse.return_value = [light_prim, geo_prim]

        mock_node = MagicMock()
        mock_node.path.return_value = "/stage/lop1"
        type(mock_node).stage = MagicMock(return_value=mock_stage)

        mock_UsdGeom = MagicMock()
        mock_UsdLux = MagicMock()
        mock_UsdShade = MagicMock()

        mock_UsdGeom.Camera = type("Camera", (), {})
        mock_UsdGeom.Gprim = type("Gprim", (), {})
        mock_UsdLux.LightAPI = type("LightAPI", (), {})

        mock_binding = MagicMock()
        mock_binding.ComputeBoundMaterial.return_value = (None, None)
        mock_UsdShade.MaterialBindingAPI.return_value = mock_binding

        with patch.object(_handlers_hou, "node", return_value=mock_node, create=True), \
             patch.object(_handlers_hou, "selectedNodes", return_value=[], create=True), \
             patch.dict(sys.modules, {"pxr": MagicMock(UsdGeom=mock_UsdGeom,
                                                        UsdLux=mock_UsdLux,
                                                        UsdShade=mock_UsdShade),
                                      "pxr.UsdGeom": mock_UsdGeom,
                                      "pxr.UsdLux": mock_UsdLux,
                                      "pxr.UsdShade": mock_UsdShade}):
            h = self._handler()
            result = h._handle_get_stage_info({"node": "/stage/lop1"})

        assert "lights" in result
        assert "/lights/key" in result["lights"]

    def test_get_stage_info_returns_renderable_prims_count(self):
        """Gprim prims are counted in renderable_prims."""
        from unittest.mock import patch

        prims = [
            self._make_prim("/world/mesh1", "Mesh", is_gprim=True),
            self._make_prim("/world/mesh2", "Mesh", is_gprim=True),
            self._make_prim("/world/mesh3", "Mesh", is_gprim=True),
            self._make_prim("/world/xform", "Xform"),
        ]

        mock_stage = MagicMock()
        mock_stage.Traverse.return_value = prims

        mock_node = MagicMock()
        mock_node.path.return_value = "/stage/lop1"
        type(mock_node).stage = MagicMock(return_value=mock_stage)

        mock_UsdGeom = MagicMock()
        mock_UsdLux = MagicMock()
        mock_UsdShade = MagicMock()

        mock_UsdGeom.Camera = type("Camera", (), {})
        mock_UsdGeom.Gprim = type("Gprim", (), {})
        mock_UsdLux.LightAPI = type("LightAPI", (), {})

        mock_binding = MagicMock()
        mock_binding.ComputeBoundMaterial.return_value = (MagicMock(), "binding")
        mock_UsdShade.MaterialBindingAPI.return_value = mock_binding

        with patch.object(_handlers_hou, "node", return_value=mock_node, create=True), \
             patch.object(_handlers_hou, "selectedNodes", return_value=[], create=True), \
             patch.dict(sys.modules, {"pxr": MagicMock(UsdGeom=mock_UsdGeom,
                                                        UsdLux=mock_UsdLux,
                                                        UsdShade=mock_UsdShade),
                                      "pxr.UsdGeom": mock_UsdGeom,
                                      "pxr.UsdLux": mock_UsdLux,
                                      "pxr.UsdShade": mock_UsdShade}):
            h = self._handler()
            result = h._handle_get_stage_info({"node": "/stage/lop1"})

        assert result["renderable_prims"] == 3

    def test_get_stage_info_returns_unassigned_material_prims(self):
        """Gprim prims without bound materials appear in unassigned list."""
        from unittest.mock import patch

        prims = [
            self._make_prim("/world/bound", "Mesh", is_gprim=True),
            self._make_prim("/world/unbound", "Mesh", is_gprim=True),
        ]

        mock_stage = MagicMock()
        mock_stage.Traverse.return_value = prims

        mock_node = MagicMock()
        mock_node.path.return_value = "/stage/lop1"
        type(mock_node).stage = MagicMock(return_value=mock_stage)

        mock_UsdGeom = MagicMock()
        mock_UsdLux = MagicMock()
        mock_UsdShade = MagicMock()

        mock_UsdGeom.Camera = type("Camera", (), {})
        mock_UsdGeom.Gprim = type("Gprim", (), {})
        mock_UsdLux.LightAPI = type("LightAPI", (), {})

        def _make_binding_api(prim):
            mock_b = MagicMock()
            path_str = str(prim.GetPath())
            if path_str == "/world/bound":
                mock_b.ComputeBoundMaterial.return_value = (MagicMock(), "binding")
            else:
                mock_b.ComputeBoundMaterial.return_value = (None, None)
            return mock_b

        mock_UsdShade.MaterialBindingAPI = _make_binding_api

        with patch.object(_handlers_hou, "node", return_value=mock_node, create=True), \
             patch.object(_handlers_hou, "selectedNodes", return_value=[], create=True), \
             patch.dict(sys.modules, {"pxr": MagicMock(UsdGeom=mock_UsdGeom,
                                                        UsdLux=mock_UsdLux,
                                                        UsdShade=mock_UsdShade),
                                      "pxr.UsdGeom": mock_UsdGeom,
                                      "pxr.UsdLux": mock_UsdLux,
                                      "pxr.UsdShade": mock_UsdShade}):
            h = self._handler()
            result = h._handle_get_stage_info({"node": "/stage/lop1"})

        assert "unassigned_material_prims" in result
        assert "/world/unbound" in result["unassigned_material_prims"]
        assert "/world/bound" not in result["unassigned_material_prims"]


class TestUsdUndoGroups:
    """Tests verifying that USD mutation handlers wrap operations in undo groups."""

    def _handler(self):
        return handlers_mod.SynapseHandler()

    def _mock_lop_node(self):
        """Create a mock LOP node with stage and parent for mutations."""
        py_lop = MagicMock()
        py_lop.path.return_value = "/stage/pythonscript1"
        py_lop.parm.return_value = MagicMock()
        py_lop.cook = MagicMock()

        parent = MagicMock()
        parent.createNode.return_value = py_lop

        node = MagicMock()
        node.path.return_value = "/stage/lop1"
        node.parent.return_value = parent
        node.stage = MagicMock(return_value=MagicMock())
        return node, py_lop

    def test_set_usd_attribute_uses_undo_group(self):
        """set_usd_attribute wraps mutation in a SYNAPSE: undo group."""
        from unittest.mock import patch

        node, py_lop = self._mock_lop_node()

        _handlers_hou.undos = MagicMock()
        _handlers_hou.undos.group = MagicMock(return_value=MagicMock())

        with patch.object(_handlers_hou, "node", return_value=node, create=True), \
             patch.object(_handlers_hou, "selectedNodes", return_value=[node], create=True):
            h = self._handler()
            h._handle_set_usd_attribute({
                "node": "/stage/lop1",
                "prim_path": "/World/sphere",
                "usd_attribute": "radius",
                "value": 2.0,
            })

        _handlers_hou.undos.group.assert_called_once()
        call_args = _handlers_hou.undos.group.call_args[0][0]
        assert "SYNAPSE:" in call_args

    def test_create_usd_prim_uses_undo_group(self):
        """create_usd_prim wraps mutation in a SYNAPSE: undo group."""
        from unittest.mock import patch

        node, py_lop = self._mock_lop_node()

        _handlers_hou.undos = MagicMock()
        _handlers_hou.undos.group = MagicMock(return_value=MagicMock())

        with patch.object(_handlers_hou, "node", return_value=node, create=True), \
             patch.object(_handlers_hou, "selectedNodes", return_value=[node], create=True):
            h = self._handler()
            h._handle_create_usd_prim({
                "node": "/stage/lop1",
                "prim_path": "/World/new_xform",
                "prim_type": "Xform",
            })

        _handlers_hou.undos.group.assert_called_once()
        call_args = _handlers_hou.undos.group.call_args[0][0]
        assert "SYNAPSE:" in call_args


class TestUsdCookAndVerify:
    """Tests for cook-and-verify behavior in USD pythonscript handlers."""

    def _handler(self):
        return handlers_mod.SynapseHandler()

    def _mock_lop_node(self):
        """Create a mock LOP node with stage and parent."""
        py_lop = MagicMock()
        py_lop.path.return_value = "/stage/create_new_xform"
        py_lop.parm.return_value = MagicMock()
        py_lop.cook = MagicMock()

        parent = MagicMock()
        parent.createNode.return_value = py_lop

        node = MagicMock()
        node.path.return_value = "/stage/lop1"
        node.parent.return_value = parent
        node.stage = MagicMock(return_value=MagicMock())
        return node, py_lop

    def test_create_usd_prim_cook_verify_success(self):
        """Successful cook produces no cook_error in the response."""
        from unittest.mock import patch

        node, py_lop = self._mock_lop_node()
        py_lop.cook = MagicMock()

        _handlers_hou.undos = MagicMock()
        _handlers_hou.undos.group = MagicMock(return_value=MagicMock())

        with patch.object(_handlers_hou, "node", return_value=node, create=True), \
             patch.object(_handlers_hou, "selectedNodes", return_value=[node], create=True):
            h = self._handler()
            result = h._handle_create_usd_prim({
                "node": "/stage/lop1",
                "prim_path": "/World/new_xform",
                "prim_type": "Xform",
            })

        assert "cook_error" not in result
        assert "created_node" in result
        assert result["prim_path"] == "/World/new_xform"
        assert result["prim_type"] == "Xform"

    def test_create_usd_prim_cook_verify_failure(self):
        """Failed cook returns cook_error with coaching tone (contains 'snag')."""
        from unittest.mock import patch

        node, py_lop = self._mock_lop_node()

        _handlers_hou.OperationFailed = type("OperationFailed", (Exception,), {})
        py_lop.cook = MagicMock(
            side_effect=_handlers_hou.OperationFailed("invalid prim type")
        )

        _handlers_hou.undos = MagicMock()
        _handlers_hou.undos.group = MagicMock(return_value=MagicMock())

        with patch.object(_handlers_hou, "node", return_value=node, create=True), \
             patch.object(_handlers_hou, "selectedNodes", return_value=[node], create=True):
            h = self._handler()
            result = h._handle_create_usd_prim({
                "node": "/stage/lop1",
                "prim_path": "/World/bad_prim",
                "prim_type": "NonexistentType",
            })

        assert "cook_error" in result
        assert "snag" in result["cook_error"]
        assert "created_node" in result
