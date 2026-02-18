"""Tests for the material handlers (tools 27-29).

Mock-based — no Houdini required.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load handlers without Houdini
# ---------------------------------------------------------------------------

# Minimal hou stub — use existing if already in sys.modules (from other test files)
if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=24.0)
    _hou.selectedNodes = MagicMock(return_value=[])
    _hou.undos = MagicMock()
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]

if "hdefereval" not in sys.modules:
    _hde = types.ModuleType("hdefereval")
    # Stub executeDeferred to call fn synchronously (no Houdini main thread)
    _hde.executeDeferred = lambda fn: fn()
    _hde.executeInMainThreadWithResult = lambda fn: fn()
    sys.modules["hdefereval"] = _hde

# Import handlers via importlib to bypass package __init__
_handlers_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "server" / "handlers.py"
_proto_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "core" / "protocol.py"
_aliases_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "core" / "aliases.py"

for mod_name, mod_path in [
    ("synapse", Path(__file__).resolve().parent.parent / "python" / "synapse"),
    ("synapse.core", Path(__file__).resolve().parent.parent / "python" / "synapse" / "core"),
    ("synapse.server", Path(__file__).resolve().parent.parent / "python" / "synapse" / "server"),
    ("synapse.session", Path(__file__).resolve().parent.parent / "python" / "synapse" / "session"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

for mod_name, fpath in [
    ("synapse.core.protocol", _proto_path),
    ("synapse.core.aliases", _aliases_path),
    ("synapse.server.handlers", _handlers_path),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

handlers_mod = sys.modules["synapse.server.handlers"]

# Get the hou module that handlers.py actually imported
_handlers_hou = handlers_mod.hou


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def handler():
    h = handlers_mod.SynapseHandler()
    h._bridge = MagicMock()
    return h


def _make_lop_node(path="/stage/node1"):
    """Create a mock LOP node with stage support."""
    node = MagicMock()
    node.path.return_value = path
    node.stage = MagicMock()  # Having .stage makes it a LOP node
    node.parent.return_value = MagicMock()
    return node


# ---------------------------------------------------------------------------
# Tests: create_material
# ---------------------------------------------------------------------------

class TestCreateMaterial:
    def test_happy_path_defaults(self, handler):
        """Create a material with all defaults."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value

        matlib = MagicMock()
        matlib.path.return_value = "/stage/material"
        shader = MagicMock()
        shader.path.return_value = "/stage/material/material_shader"

        parent.createNode.return_value = matlib
        matlib.createNode.return_value = shader

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            with patch.object(_handlers_hou, "selectedNodes", create=True, return_value=[]):
                result = handler._handle_create_material({"node": "/stage/node1"})

        assert result["matlib_path"] == "/stage/material"
        assert result["shader_path"] == "/stage/material/material_shader"
        assert result["material_usd_path"] == "/materials/material"
        assert result["shader_type"] == "mtlxstandard_surface"
        assert result["name"] == "material"

        # Verify matlib was created, wired, and cooked
        parent.createNode.assert_called_once_with("materiallibrary", "material")
        matlib.setInput.assert_called_once_with(0, lop_node)
        matlib.moveToGoodPosition.assert_called_once()
        assert matlib.cook.call_count >= 1
        matlib.cook.assert_any_call(force=True)

        # Verify shader was created inside matlib
        matlib.createNode.assert_called_once_with("mtlxstandard_surface", "material_shader")

    def test_custom_name_and_shader_type(self, handler):
        """Create with custom name and shader type."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value

        matlib = MagicMock()
        matlib.path.return_value = "/stage/chrome"
        shader = MagicMock()
        shader.path.return_value = "/stage/chrome/chrome_shader"
        parent.createNode.return_value = matlib
        matlib.createNode.return_value = shader

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            result = handler._handle_create_material({
                "node": "/stage/node1",
                "name": "chrome",
                "shader_type": "mtlxstandard_surface",
            })

        assert result["name"] == "chrome"
        assert result["material_usd_path"] == "/materials/chrome"
        parent.createNode.assert_called_once_with("materiallibrary", "chrome")
        matlib.createNode.assert_called_once_with("mtlxstandard_surface", "chrome_shader")

    def test_base_color_set(self, handler):
        """Setting base_color writes to shader parm channels."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value

        matlib = MagicMock()
        matlib.path.return_value = "/stage/material"
        shader = MagicMock()
        shader.path.return_value = "/stage/material/material_shader"

        # Create mock parms for r, g, b channels
        parm_r = MagicMock()
        parm_g = MagicMock()
        parm_b = MagicMock()

        def mock_parm(name):
            return {"base_colorr": parm_r, "base_colorg": parm_g, "base_colorb": parm_b,
                    "metalness": None, "specular_roughness": None}.get(name)

        shader.parm = mock_parm
        parent.createNode.return_value = matlib
        matlib.createNode.return_value = shader

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            handler._handle_create_material({
                "node": "/stage/node1",
                "base_color": [0.8, 0.2, 0.1],
            })

        parm_r.set.assert_called_once_with(0.8)
        parm_g.set.assert_called_once_with(0.2)
        parm_b.set.assert_called_once_with(0.1)

    def test_metalness_and_roughness_set(self, handler):
        """Setting metalness and roughness writes to correct shader parms."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value

        matlib = MagicMock()
        matlib.path.return_value = "/stage/material"
        shader = MagicMock()
        shader.path.return_value = "/stage/material/material_shader"

        parm_metal = MagicMock()
        parm_rough = MagicMock()

        def mock_parm(name):
            return {"metalness": parm_metal, "specular_roughness": parm_rough}.get(name)

        shader.parm = mock_parm
        parent.createNode.return_value = matlib
        matlib.createNode.return_value = shader

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            handler._handle_create_material({
                "node": "/stage/node1",
                "metalness": 1.0,
                "roughness": 0.3,
            })

        parm_metal.set.assert_called_once_with(1.0)
        parm_rough.set.assert_called_once_with(0.3)

    def test_shader_creation_fails_raises(self, handler):
        """If shader creation returns None, raise RuntimeError."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value

        matlib = MagicMock()
        matlib.path.return_value = "/stage/material"
        parent.createNode.return_value = matlib
        matlib.createNode.return_value = None  # Shader creation fails

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            with pytest.raises(RuntimeError, match="Couldn't create"):
                handler._handle_create_material({"node": "/stage/node1"})

    def test_cook_called_before_shader_creation(self, handler):
        """Verify cook(force=True) is called before createNode on the shader."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value

        call_order = []

        matlib = MagicMock()
        matlib.path.return_value = "/stage/material"
        matlib.cook.side_effect = lambda **kw: call_order.append("cook")

        shader = MagicMock()
        shader.path.return_value = "/stage/material/material_shader"
        matlib.createNode.side_effect = lambda *a, **kw: (call_order.append("createNode"), shader)[1]

        parent.createNode.return_value = matlib

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            handler._handle_create_material({"node": "/stage/node1"})

        # cook before createNode, optional second cook for stage query
        assert call_order[0] == "cook"
        assert call_order[1] == "createNode"

    def test_node_not_found_raises(self, handler):
        """Non-existent node path raises ValueError."""
        with patch.object(_handlers_hou, "node", create=True, return_value=None):
            with patch.object(_handlers_hou, "selectedNodes", create=True, return_value=[]):
                with pytest.raises(ValueError, match="Couldn't find"):
                    handler._handle_create_material({"node": "/stage/nonexistent"})

    def test_uses_selection_when_no_node(self, handler):
        """Falls back to selected node when no node param given."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value

        matlib = MagicMock()
        matlib.path.return_value = "/stage/material"
        shader = MagicMock()
        shader.path.return_value = "/stage/material/material_shader"
        parent.createNode.return_value = matlib
        matlib.createNode.return_value = shader

        with patch.object(_handlers_hou, "selectedNodes", create=True, return_value=[lop_node]):
            result = handler._handle_create_material({})

        assert result["matlib_path"] == "/stage/material"

    def test_extended_params_set(self, handler):
        """Extended params (opacity, emission, subsurface) are set on shader."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value

        matlib = MagicMock()
        matlib.path.return_value = "/stage/glass"
        shader = MagicMock()
        shader.path.return_value = "/stage/glass/glass_shader"
        parent.createNode.return_value = matlib
        matlib.createNode.return_value = shader

        opacity_parm = MagicMock()
        emission_parm = MagicMock()
        subsurface_parm = MagicMock()
        emission_r = MagicMock()
        emission_g = MagicMock()
        emission_b = MagicMock()
        subsurface_r = MagicMock()
        subsurface_g = MagicMock()
        subsurface_b = MagicMock()

        def _shader_parm(name):
            return {
                "opacity": opacity_parm,
                "emission": emission_parm,
                "subsurface": subsurface_parm,
                "emission_colorr": emission_r,
                "emission_colorg": emission_g,
                "emission_colorb": emission_b,
                "subsurface_colorr": subsurface_r,
                "subsurface_colorg": subsurface_g,
                "subsurface_colorb": subsurface_b,
            }.get(name)

        shader.parm.side_effect = _shader_parm

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            handler._handle_create_material({
                "node": "/stage/node1",
                "name": "glass",
                "opacity": 0.5,
                "emission": 0.8,
                "emission_color": [1.0, 0.5, 0.0],
                "subsurface": 0.3,
                "subsurface_color": [0.8, 0.2, 0.1],
            })

        opacity_parm.set.assert_called_once_with(0.5)
        emission_parm.set.assert_called_once_with(0.8)
        subsurface_parm.set.assert_called_once_with(0.3)
        emission_r.set.assert_called_once_with(1.0)
        emission_g.set.assert_called_once_with(0.5)
        emission_b.set.assert_called_once_with(0.0)
        subsurface_r.set.assert_called_once_with(0.8)
        subsurface_g.set.assert_called_once_with(0.2)
        subsurface_b.set.assert_called_once_with(0.1)


# ---------------------------------------------------------------------------
# Tests: assign_material
# ---------------------------------------------------------------------------

class TestAssignMaterial:
    def test_happy_path(self, handler):
        """Assign a material to a prim pattern."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value

        assign_node = MagicMock()
        assign_node.path.return_value = "/stage/assign_chrome"
        assign_node.parm.return_value = MagicMock()  # All parms exist
        parent.createNode.return_value = assign_node

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            result = handler._handle_assign_material({
                "node": "/stage/node1",
                "prim_pattern": "/World/geo/*",
                "material_path": "/materials/chrome",
            })

        assert result["node_path"] == "/stage/assign_chrome"
        assert result["prim_pattern"] == "/World/geo/*"
        assert result["material_path"] == "/materials/chrome"

        parent.createNode.assert_called_once_with("assignmaterial", "assign_chrome")
        assign_node.setInput.assert_called_once_with(0, lop_node)
        assign_node.moveToGoodPosition.assert_called_once()

    def test_prim_pattern_and_matspec_set(self, handler):
        """Verify primpattern1 and matspecpath1 are set correctly."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value

        assign_node = MagicMock()
        assign_node.path.return_value = "/stage/assign_gold"
        parm_pattern = MagicMock()
        parm_matspec = MagicMock()
        assign_node.parm.side_effect = lambda name: {
            "primpattern1": parm_pattern,
            "matspecpath1": parm_matspec,
        }.get(name, MagicMock())
        parent.createNode.return_value = assign_node

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            handler._handle_assign_material({
                "node": "/stage/node1",
                "prim_pattern": "/World/hero",
                "material_path": "/materials/gold",
            })

        parm_pattern.set.assert_called_once_with("/World/hero")
        parm_matspec.set.assert_called_once_with("/materials/gold")

    def test_missing_prim_pattern_raises(self, handler):
        """Missing prim_pattern raises ValueError."""
        lop_node = _make_lop_node()
        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            with pytest.raises(ValueError, match="Missing required"):
                handler._handle_assign_material({
                    "node": "/stage/node1",
                    "material_path": "/materials/chrome",
                })

    def test_missing_material_path_raises(self, handler):
        """Missing material_path raises ValueError."""
        lop_node = _make_lop_node()
        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            with pytest.raises(ValueError, match="Missing required"):
                handler._handle_assign_material({
                    "node": "/stage/node1",
                    "prim_pattern": "/World/geo/*",
                })

    def test_node_not_found_raises(self, handler):
        """Non-existent node raises ValueError."""
        with patch.object(_handlers_hou, "node", create=True, return_value=None):
            with patch.object(_handlers_hou, "selectedNodes", create=True, return_value=[]):
                with pytest.raises(ValueError, match="Couldn't find"):
                    handler._handle_assign_material({
                        "node": "/stage/nonexistent",
                        "prim_pattern": "/World/geo/*",
                        "material_path": "/materials/chrome",
                    })


# ---------------------------------------------------------------------------
# Tests: read_material
# ---------------------------------------------------------------------------

class TestReadMaterial:
    def _make_stage_with_binding(self, has_material=True):
        """Helper to create a mock USD stage with material binding."""
        stage = MagicMock()
        prim = MagicMock()
        prim.IsValid.return_value = True
        stage.GetPrimAtPath.return_value = prim

        # Mock UsdShade classes
        mock_binding_api = MagicMock()
        mock_bound = MagicMock()

        if has_material:
            mock_bound.GetMaterialPath.return_value = "/materials/gold"
            mock_material = MagicMock()
            mock_bound.GetMaterial.return_value = mock_material

            # Mock surface output and shader
            mock_surface_output = MagicMock()
            mock_material.GetSurfaceOutput.return_value = mock_surface_output

            mock_source_info = MagicMock()
            shader_prim = MagicMock()
            mock_source_info.source.GetPrim.return_value = shader_prim
            mock_surface_output.GetConnectedSources.return_value = [[mock_source_info]]

            mock_shader = MagicMock()
            mock_shader.GetIdAttr.return_value.Get.return_value = "mtlxstandard_surface"

            # Mock shader inputs
            mock_input_roughness = MagicMock()
            mock_input_roughness.GetBaseName.return_value = "specular_roughness"
            mock_input_roughness.Get.return_value = 0.3

            mock_input_metalness = MagicMock()
            mock_input_metalness.GetBaseName.return_value = "metalness"
            mock_input_metalness.Get.return_value = 1.0

            mock_shader.GetInputs.return_value = [mock_input_roughness, mock_input_metalness]
        else:
            mock_bound.GetMaterial.return_value = None
            mock_bound.GetMaterialPath.return_value = ""

        mock_binding_api.GetDirectBinding.return_value = mock_bound

        return stage, mock_binding_api, prim

    def test_happy_path_with_material(self, handler):
        """Read material from a prim that has one bound."""
        lop_node = _make_lop_node()
        stage, mock_binding_api, prim = self._make_stage_with_binding(has_material=True)
        lop_node.stage.return_value = stage

        # Patch UsdShade module
        mock_usdshade = MagicMock()
        mock_usdshade.MaterialBindingAPI.return_value = mock_binding_api

        # Make UsdShade.Material(prim) return a non-material for geometry prims
        # (GetSurfaceOutput returns falsy so the handler falls through to binding lookup)
        non_mat = MagicMock()
        non_mat.GetPrim.return_value.IsValid.return_value = False
        non_mat.GetSurfaceOutput.return_value = None
        mock_usdshade.Material.return_value = non_mat

        # The shader mock
        bound = mock_binding_api.GetDirectBinding.return_value
        material = bound.GetMaterial.return_value
        surface_output = material.GetSurfaceOutput.return_value
        sources = surface_output.GetConnectedSources.return_value
        shader_prim_mock = sources[0][0].source.GetPrim.return_value

        mock_shader_instance = MagicMock()
        mock_shader_instance.GetIdAttr.return_value.Get.return_value = "mtlxstandard_surface"
        mock_input_r = MagicMock()
        mock_input_r.GetBaseName.return_value = "specular_roughness"
        mock_input_r.Get.return_value = 0.3
        mock_shader_instance.GetInputs.return_value = [mock_input_r]
        mock_usdshade.Shader.return_value = mock_shader_instance

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            with patch.dict(sys.modules, {"pxr": MagicMock(), "pxr.UsdShade": mock_usdshade}):
                # We need to patch the import inside the handler method
                with patch("builtins.__import__", side_effect=_make_import_patcher(mock_usdshade)):
                    result = handler._handle_read_material({
                        "node": "/stage/node1",
                        "prim_path": "/World/hero",
                    })

        assert result["prim_path"] == "/World/hero"
        assert result["has_material"] is True
        assert result["material_path"] == "/materials/gold"
        assert result["shader_type"] == "mtlxstandard_surface"
        assert "specular_roughness" in result["shader_params"]

    def test_no_material_bound(self, handler):
        """Read material from a prim with no material bound."""
        lop_node = _make_lop_node()
        stage, mock_binding_api, prim = self._make_stage_with_binding(has_material=False)
        lop_node.stage.return_value = stage

        mock_usdshade = MagicMock()
        mock_usdshade.MaterialBindingAPI.return_value = mock_binding_api

        # Geometry prim is not a material — direct_mat check should fail
        non_mat = MagicMock()
        non_mat.GetPrim.return_value.IsValid.return_value = False
        non_mat.GetSurfaceOutput.return_value = None
        mock_usdshade.Material.return_value = non_mat

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            with patch("builtins.__import__", side_effect=_make_import_patcher(mock_usdshade)):
                result = handler._handle_read_material({
                    "node": "/stage/node1",
                    "prim_path": "/World/unshaded",
                })

        assert result["prim_path"] == "/World/unshaded"
        assert result["has_material"] is False
        assert result["material_path"] == ""
        assert result["shader_params"] == {}

    def test_invalid_prim_raises(self, handler):
        """Non-existent prim path raises ValueError."""
        lop_node = _make_lop_node()
        stage = MagicMock()
        invalid_prim = MagicMock()
        invalid_prim.IsValid.return_value = False
        stage.GetPrimAtPath.return_value = invalid_prim
        lop_node.stage.return_value = stage

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            with pytest.raises(ValueError, match="Couldn't find a prim"):
                handler._handle_read_material({
                    "node": "/stage/node1",
                    "prim_path": "/World/nonexistent",
                })

    def test_no_stage_raises(self, handler):
        """Node with no stage raises ValueError."""
        lop_node = _make_lop_node()
        lop_node.stage.return_value = None

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            with pytest.raises(ValueError, match="doesn't have an active USD stage"):
                handler._handle_read_material({
                    "node": "/stage/node1",
                    "prim_path": "/World/hero",
                })

    def test_missing_prim_path_raises(self, handler):
        """Missing prim_path raises ValueError."""
        lop_node = _make_lop_node()
        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            with pytest.raises(ValueError, match="Missing required"):
                handler._handle_read_material({"node": "/stage/node1"})


# ---------------------------------------------------------------------------
# Import patcher helper for `from pxr import UsdShade`
# ---------------------------------------------------------------------------

_original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__


def _make_import_patcher(mock_usdshade):
    """Create an import side_effect that intercepts `from pxr import UsdShade`."""
    def _patched_import(name, *args, **kwargs):
        if name == "pxr":
            mod = types.ModuleType("pxr")
            mod.UsdShade = mock_usdshade
            return mod
        return _original_import(name, *args, **kwargs)
    return _patched_import


# ---------------------------------------------------------------------------
# Tests: read_material is in _READ_ONLY_COMMANDS
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tests: create_textured_material
# ---------------------------------------------------------------------------

class TestCreateTexturedMaterial:
    def _make_matlib_with_shader(self, name="textured_material"):
        """Create mock matlib and shader for textured material tests."""
        matlib = MagicMock()
        matlib.path.return_value = f"/stage/{name}"
        shader = MagicMock()
        shader.path.return_value = f"/stage/{name}/{name}_shader"

        uv_node = MagicMock()
        uv_node.path.return_value = f"/stage/{name}/uv_reader"

        img_nodes = {}
        def _create_node(node_type, node_name):
            if node_type == "mtlxstandard_surface":
                return shader
            if node_type == "mtlxgeompropvalue":
                return uv_node
            node = MagicMock()
            node.path.return_value = f"/stage/{name}/{node_name}"
            img_nodes[node_name] = node
            return node

        matlib.createNode.side_effect = _create_node
        return matlib, shader, uv_node, img_nodes

    def test_diffuse_only(self, handler):
        """Create textured material with just a diffuse map."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value
        matlib, shader, uv_node, img_nodes = self._make_matlib_with_shader()
        parent.createNode.return_value = matlib

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            result = handler._handle_create_textured_material({
                "node": "/stage/node1",
                "name": "textured_material",
                "diffuse_map": "D:/textures/wood_diffuse.exr",
            })

        assert result["name"] == "textured_material"
        assert len(result["connected_maps"]) == 1
        assert result["connected_maps"][0]["map"] == "diffuse_tex"
        assert result["connected_maps"][0]["shader_input"] == "base_color"
        assert result["connected_maps"][0]["file"] == "D:/textures/wood_diffuse.exr"

    def test_full_texture_set(self, handler):
        """Create with diffuse, roughness, metalness, and normal maps."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value
        matlib, shader, uv_node, img_nodes = self._make_matlib_with_shader()
        parent.createNode.return_value = matlib

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            result = handler._handle_create_textured_material({
                "node": "/stage/node1",
                "diffuse_map": "D:/tex/diffuse.<UDIM>.exr",
                "roughness_map": "D:/tex/roughness.<UDIM>.exr",
                "metalness_map": "D:/tex/metal.<UDIM>.exr",
                "normal_map": "D:/tex/normal.<UDIM>.exr",
            })

        # Should have 4 connected maps (diffuse, roughness, metalness, normal)
        assert len(result["connected_maps"]) == 4
        map_names = [m["map"] for m in result["connected_maps"]]
        assert "diffuse_tex" in map_names
        assert "roughness_tex" in map_names
        assert "metalness_tex" in map_names
        assert "normal_tex" in map_names

        # UDIM detection
        for m in result["connected_maps"]:
            assert m["udim"] is True

    def test_scalar_fallback_when_no_texture(self, handler):
        """Roughness/metalness scalar values used when no texture map provided."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value
        matlib, shader, uv_node, img_nodes = self._make_matlib_with_shader()
        parent.createNode.return_value = matlib

        rough_parm = MagicMock()
        metal_parm = MagicMock()
        shader.parm.side_effect = lambda n: {
            "specular_roughness": rough_parm,
            "metalness": metal_parm,
        }.get(n)

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            result = handler._handle_create_textured_material({
                "node": "/stage/node1",
                "roughness": 0.4,
                "metalness": 0.9,
            })

        rough_parm.set.assert_called_once_with(0.4)
        metal_parm.set.assert_called_once_with(0.9)
        assert result["connected_maps"] == []

    def test_geo_pattern_creates_assign_node(self, handler):
        """geo_pattern creates an assignmaterial node wired after matlib."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value
        matlib, shader, uv_node, img_nodes = self._make_matlib_with_shader()

        assign_node = MagicMock()
        assign_node.path.return_value = "/stage/assign_textured_material"
        assign_node.parm.return_value = MagicMock()

        call_count = {"n": 0}
        def _create_node(node_type, name):
            call_count["n"] += 1
            if node_type == "materiallibrary":
                return matlib
            if node_type == "assignmaterial":
                return assign_node
            return MagicMock()

        parent.createNode.side_effect = _create_node

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            result = handler._handle_create_textured_material({
                "node": "/stage/node1",
                "name": "textured_material",
                "diffuse_map": "D:/tex/diffuse.exr",
                "geo_pattern": "/World/hero/mesh",
            })

        assert "assign_node" in result
        assert result["geo_pattern"] == "/World/hero/mesh"

    def test_shader_creation_failure_raises(self, handler):
        """If shader creation returns None, raise RuntimeError."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value

        matlib = MagicMock()
        matlib.path.return_value = "/stage/textured_material"
        matlib.createNode.return_value = None  # Shader fails
        parent.createNode.return_value = matlib

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            with pytest.raises(RuntimeError, match="Couldn't create"):
                handler._handle_create_textured_material({
                    "node": "/stage/node1",
                    "diffuse_map": "D:/tex/diffuse.exr",
                })

    def test_uv_reader_created_and_connected(self, handler):
        """Verify UV reader node is created and wired to texture nodes."""
        lop_node = _make_lop_node()
        parent = lop_node.parent.return_value
        matlib, shader, uv_node, img_nodes = self._make_matlib_with_shader()
        parent.createNode.return_value = matlib

        with patch.object(_handlers_hou, "node", create=True, return_value=lop_node):
            handler._handle_create_textured_material({
                "node": "/stage/node1",
                "diffuse_map": "D:/tex/diffuse.exr",
            })

        # UV node should have had signature and geomprop set
        uv_node.parm.assert_any_call("signature")
        uv_node.parm.assert_any_call("geomprop")

        # Diffuse texture should be connected to UV reader
        diffuse_img = img_nodes.get("diffuse_tex")
        if diffuse_img:
            diffuse_img.setNamedInput.assert_any_call("texcoord", uv_node, 0)


class TestReadOnlyClassification:
    def test_read_material_is_read_only(self):
        """read_material should not trigger memory logging."""
        assert "read_material" in handlers_mod._READ_ONLY_COMMANDS
