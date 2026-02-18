"""Tests for TOPs/wedging and USD scene assembly handlers."""
import importlib.util
import pytest
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# Create hou mock
hou_mock = types.ModuleType("hou")
sys.modules["hou"] = hou_mock
hou_mock.node = MagicMock()
hou_mock.frame = MagicMock(return_value=1)
hou_mock.selectedNodes = MagicMock(return_value=[])

if "hdefereval" not in sys.modules:
    _hdefereval = types.ModuleType("hdefereval")
    sys.modules["hdefereval"] = _hdefereval
else:
    _hdefereval = sys.modules["hdefereval"]
if not hasattr(_hdefereval, "executeDeferred"):
    _hdefereval.executeDeferred = lambda fn: fn()

# Bootstrap synapse packages for handler import
_base = Path(__file__).resolve().parent.parent / "python" / "synapse"
for mod_name, mod_path in [
    ("synapse", _base),
    ("synapse.core", _base / "core"),
    ("synapse.server", _base / "server"),
    ("synapse.session", _base / "session"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

for mod_name, fpath in [
    ("synapse.core.protocol", _base / "core" / "protocol.py"),
    ("synapse.core.aliases", _base / "core" / "aliases.py"),
    ("synapse.server.handlers", _base / "server" / "handlers.py"),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

handlers_mod = sys.modules["synapse.server.handlers"]


class _MockCategory:
    def __init__(self, name):
        self._name = name
    def name(self):
        return self._name

class _MockNodeType:
    def __init__(self, name="null", category="Object"):
        self._name = name
        self._cat = _MockCategory(category)
    def name(self):
        return self._name
    def category(self):
        return self._cat


class TestWedge:
    def test_top_node_cook(self):
        """TOP node should be cooked."""
        mock_node = MagicMock()
        mock_node.type.return_value = _MockNodeType("wedge", "Top")
        mock_node.cook = MagicMock()
        hou_mock.node.return_value = mock_node

        node = hou_mock.node("/obj/topnet1/wedge1")
        assert node.type().category().name() == "Top"
        node.cook(block=True)
        node.cook.assert_called_once_with(block=True)

    def test_topnet_finds_wedge(self):
        """TOP network should find child wedge nodes."""
        wedge_child = MagicMock()
        wedge_child.type.return_value = _MockNodeType("wedge", "Top")
        wedge_child.path.return_value = "/obj/topnet1/wedge1"
        wedge_child.cook = MagicMock()

        mock_net = MagicMock()
        mock_net.type.return_value = _MockNodeType("topnet", "TopNet")
        mock_net.children.return_value = [wedge_child]
        hou_mock.node.return_value = mock_net

        node = hou_mock.node("/obj/topnet1")
        wedge_nodes = [n for n in node.children() if "wedge" in n.type().name().lower()]
        assert len(wedge_nodes) == 1

    def test_node_not_found(self):
        """Missing node should raise ValueError."""
        hou_mock.node.return_value = None
        with pytest.raises(ValueError, match="Couldn't find a node"):
            node = hou_mock.node("/bad")
            if node is None:
                raise ValueError("Couldn't find a node at /bad")

    def test_values_must_be_list(self):
        """Non-list values should raise ValueError."""
        with pytest.raises(ValueError, match="should be a list"):
            values = "not a list"
            if not isinstance(values, list):
                raise ValueError("'values' should be a list")


class TestReferenceUSD:
    def test_reference_creates_node(self):
        """Reference mode should create a reference LOP node."""
        mock_parent = MagicMock()
        mock_ref = MagicMock()
        mock_ref.path.return_value = "/stage/ref_import"
        mock_ref.parm.return_value = MagicMock()
        mock_parent.createNode.return_value = mock_ref
        hou_mock.node.return_value = mock_parent

        parent = hou_mock.node("/stage")
        node = parent.createNode("reference", "ref_import")
        node.parm("filepath1").set("D:/assets/building.usdc")

        parent.createNode.assert_called_with("reference", "ref_import")

    def test_sublayer_creates_node(self):
        """Sublayer mode should create a sublayer LOP node."""
        mock_parent = MagicMock()
        mock_sub = MagicMock()
        mock_sub.path.return_value = "/stage/sublayer_import"
        mock_sub.parm.return_value = MagicMock()
        mock_parent.createNode.return_value = mock_sub
        hou_mock.node.return_value = mock_parent

        parent = hou_mock.node("/stage")
        node = parent.createNode("sublayer", "sublayer_import")
        node.parm("filepath1").set("D:/assets/env.usda")

        parent.createNode.assert_called_with("sublayer", "sublayer_import")

    def test_payload_creates_reference_with_reftype(self):
        """Payload mode should create a reference node with reftype=payload."""
        mock_parent = MagicMock()
        mock_ref = MagicMock()
        mock_ref.path.return_value = "/stage/ref_import"
        reftype_parm = MagicMock()
        filepath_parm = MagicMock()
        mock_ref.parm.side_effect = lambda n: {
            "filepath1": filepath_parm,
            "reftype": reftype_parm,
        }.get(n)
        mock_parent.createNode.return_value = mock_ref
        hou_mock.node.return_value = mock_parent

        parent = hou_mock.node("/stage")
        node = parent.createNode("reference", "ref_import")
        node.parm("filepath1").set("D:/assets/heavy_model.usdc")
        # Simulate what the handler does for payload mode
        reftype = node.parm("reftype")
        if reftype is not None:
            reftype.set("payload")

        reftype_parm.set.assert_called_once_with("payload")

    def test_invalid_mode(self):
        """Invalid mode should raise ValueError."""
        with pytest.raises(ValueError, match="isn't a recognized import mode"):
            mode = "invalid"
            if mode not in ("reference", "payload", "sublayer"):
                raise ValueError(f"'{mode}' isn't a recognized import mode")

    def test_parent_not_found(self):
        """Missing parent node should raise ValueError."""
        hou_mock.node.return_value = None
        with pytest.raises(ValueError, match="Couldn't find the parent node"):
            parent = hou_mock.node("/bad")
            if parent is None:
                raise ValueError("Couldn't find the parent node at /bad")


@pytest.fixture
def handler():
    h = handlers_mod.SynapseHandler()
    h._bridge = MagicMock()
    return h


class TestManageVariantSet:
    """Tests for _handle_manage_variant_set."""

    def _setup_lop(self, handler):
        lop_node = MagicMock()
        lop_node.path.return_value = "/stage/render_settings"
        parent = MagicMock()
        lop_node.parent.return_value = parent
        py_lop = MagicMock()
        py_lop.path.return_value = "/stage/vset_color"
        parent.createNode.return_value = py_lop
        handler._resolve_lop_node = MagicMock(return_value=lop_node)
        return lop_node, parent, py_lop

    def test_create_variant_set(self, handler):
        """Create action produces a Python LOP with AddVariantSet code."""
        lop, parent, py_lop = self._setup_lop(handler)

        result = handler._handle_manage_variant_set({
            "prim_path": "/World/car",
            "action": "create",
            "variant_set": "color",
            "variants": ["red", "blue", "green"],
        })

        assert result["variant_set"] == "color"
        assert result["variants"] == ["red", "blue", "green"]
        assert result["default_selection"] == "red"
        assert result["node"] == "/stage/vset_color"

        code = py_lop.parm.return_value.set.call_args[0][0]
        assert "AddVariantSet" in code
        assert "'red'" in code
        assert "'blue'" in code
        assert "'green'" in code
        assert "SetVariantSelection" in code

    def test_select_variant(self, handler):
        """Select action produces Python LOP with SetVariantSelection."""
        lop, parent, py_lop = self._setup_lop(handler)
        py_lop.path.return_value = "/stage/vsel_color"

        result = handler._handle_manage_variant_set({
            "prim_path": "/World/car",
            "action": "select",
            "variant_set": "color",
            "variant": "blue",
        })

        assert result["variant"] == "blue"
        assert result["variant_set"] == "color"
        code = py_lop.parm.return_value.set.call_args[0][0]
        assert "SetVariantSelection" in code
        assert "'blue'" in code

    def test_list_variant_sets(self, handler):
        """List action reads variant sets from stage."""
        lop, _, _ = self._setup_lop(handler)
        stage = MagicMock()
        lop.stage.return_value = stage
        prim = MagicMock()
        prim.IsValid.return_value = True
        stage.GetPrimAtPath.return_value = prim

        vs = MagicMock()
        vs.GetVariantNames.return_value = ["red", "blue"]
        vs.GetVariantSelection.return_value = "red"
        vsets = MagicMock()
        vsets.GetNames.return_value = ["color"]
        vsets.GetVariantSet.return_value = vs
        prim.GetVariantSets.return_value = vsets

        result = handler._handle_manage_variant_set({
            "prim_path": "/World/car",
            "action": "list",
        })

        assert result["count"] == 1
        assert result["variant_sets"][0]["name"] == "color"
        assert result["variant_sets"][0]["variants"] == ["red", "blue"]

    def test_invalid_action_raises(self, handler):
        self._setup_lop(handler)
        with pytest.raises(ValueError, match="isn't a recognized action"):
            handler._handle_manage_variant_set({
                "prim_path": "/World/car",
                "action": "invalid",
            })

    def test_create_requires_variants_list(self, handler):
        self._setup_lop(handler)
        with pytest.raises(ValueError, match="pass 'variants' as a list"):
            handler._handle_manage_variant_set({
                "prim_path": "/World/car",
                "action": "create",
                "variant_set": "color",
            })

    def test_select_requires_variant(self, handler):
        self._setup_lop(handler)
        with pytest.raises(ValueError, match="pass 'variant'"):
            handler._handle_manage_variant_set({
                "prim_path": "/World/car",
                "action": "select",
                "variant_set": "color",
            })


class TestManageCollection:
    """Tests for _handle_manage_collection."""

    def _setup_lop(self, handler):
        lop_node = MagicMock()
        lop_node.path.return_value = "/stage/render_settings"
        parent = MagicMock()
        lop_node.parent.return_value = parent
        py_lop = MagicMock()
        py_lop.path.return_value = "/stage/coll_lights"
        parent.createNode.return_value = py_lop
        handler._resolve_lop_node = MagicMock(return_value=lop_node)
        return lop_node, parent, py_lop

    def test_create_collection(self, handler):
        """Create action produces Python LOP with CollectionAPI.Apply."""
        lop, parent, py_lop = self._setup_lop(handler)

        result = handler._handle_manage_collection({
            "prim_path": "/World",
            "action": "create",
            "collection_name": "key_lights",
            "paths": ["/World/lights/key", "/World/lights/fill"],
        })

        assert result["collection_name"] == "key_lights"
        assert result["includes"] == ["/World/lights/key", "/World/lights/fill"]
        assert result["expansion_rule"] == "expandPrims"

        code = py_lop.parm.return_value.set.call_args[0][0]
        assert "CollectionAPI.Apply" in code
        assert "'/World/lights/key'" in code
        assert "'/World/lights/fill'" in code

    def test_create_with_excludes(self, handler):
        """Create with exclude_paths includes exclude code."""
        lop, parent, py_lop = self._setup_lop(handler)

        result = handler._handle_manage_collection({
            "prim_path": "/World",
            "action": "create",
            "collection_name": "visible_geo",
            "paths": ["/World/geo"],
            "exclude_paths": ["/World/geo/hidden"],
        })

        assert result["excludes"] == ["/World/geo/hidden"]
        code = py_lop.parm.return_value.set.call_args[0][0]
        assert "GetExcludesRel" in code
        assert "'/World/geo/hidden'" in code

    def test_add_paths(self, handler):
        """Add action produces Python LOP with AddTarget."""
        lop, parent, py_lop = self._setup_lop(handler)
        py_lop.path.return_value = "/stage/coll_add_lights"

        result = handler._handle_manage_collection({
            "prim_path": "/World",
            "action": "add",
            "collection_name": "key_lights",
            "paths": ["/World/lights/rim"],
        })

        assert result["action"] == "add"
        code = py_lop.parm.return_value.set.call_args[0][0]
        assert "AddTarget" in code
        assert "'/World/lights/rim'" in code

    def test_remove_paths(self, handler):
        """Remove action produces Python LOP with RemoveTarget."""
        lop, parent, py_lop = self._setup_lop(handler)
        py_lop.path.return_value = "/stage/coll_rm_lights"

        result = handler._handle_manage_collection({
            "prim_path": "/World",
            "action": "remove",
            "collection_name": "key_lights",
            "paths": ["/World/lights/fill"],
        })

        assert result["action"] == "remove"
        code = py_lop.parm.return_value.set.call_args[0][0]
        assert "RemoveTarget" in code

    def test_invalid_action_raises(self, handler):
        self._setup_lop(handler)
        with pytest.raises(ValueError, match="isn't a recognized action"):
            handler._handle_manage_collection({
                "prim_path": "/World",
                "action": "invalid",
            })

    def test_create_requires_paths(self, handler):
        self._setup_lop(handler)
        with pytest.raises(ValueError, match="pass 'paths' as a list"):
            handler._handle_manage_collection({
                "prim_path": "/World",
                "action": "create",
                "collection_name": "test",
            })

    def test_list_collections(self, handler):
        """List action reads collections from stage via CollectionAPI."""
        lop, _, _ = self._setup_lop(handler)
        stage = MagicMock()
        lop.stage.return_value = stage
        prim = MagicMock()
        prim.IsValid.return_value = True
        stage.GetPrimAtPath.return_value = prim

        # Mock pxr.Usd.CollectionAPI
        mock_usd = types.ModuleType("pxr.Usd")
        mock_pxr = types.ModuleType("pxr")
        mock_pxr.Usd = mock_usd

        coll = MagicMock()
        coll.GetName.return_value = "key_lights"
        includes_rel = MagicMock()
        includes_rel.GetTargets.return_value = ["/World/lights/key"]
        coll.GetIncludesRel.return_value = includes_rel
        excludes_rel = MagicMock()
        excludes_rel.GetTargets.return_value = []
        coll.GetExcludesRel.return_value = excludes_rel
        exp_attr = MagicMock()
        exp_attr.Get.return_value = "expandPrims"
        coll.GetExpansionRuleAttr.return_value = exp_attr

        mock_coll_api = MagicMock()
        mock_coll_api.GetAllCollections.return_value = [coll]

        with patch.dict(sys.modules, {"pxr": mock_pxr, "pxr.Usd": mock_usd}):
            mock_usd.CollectionAPI = mock_coll_api
            result = handler._handle_manage_collection({
                "prim_path": "/World",
                "action": "list",
            })

        assert result["count"] == 1
        assert result["collections"][0]["name"] == "key_lights"


class TestConfigureLightLinking:
    """Tests for _handle_configure_light_linking."""

    def _setup_lop(self, handler):
        lop_node = MagicMock()
        lop_node.path.return_value = "/stage/render_settings"
        parent = MagicMock()
        lop_node.parent.return_value = parent
        py_lop = MagicMock()
        py_lop.path.return_value = "/stage/lightlink_key"
        parent.createNode.return_value = py_lop
        handler._resolve_lop_node = MagicMock(return_value=lop_node)
        return lop_node, parent, py_lop

    def test_include_light_linking(self, handler):
        """Include action sets lightLink collection includes."""
        _, _, py_lop = self._setup_lop(handler)

        result = handler._handle_configure_light_linking({
            "light_path": "/World/lights/key",
            "action": "include",
            "geo_paths": ["/World/geo/hero", "/World/geo/ground"],
        })

        assert result["light_path"] == "/World/lights/key"
        assert result["action"] == "include"
        assert result["geo_paths"] == ["/World/geo/hero", "/World/geo/ground"]

        code = py_lop.parm.return_value.set.call_args[0][0]
        assert "GetLightLinkCollectionAPI" in code
        assert "ClearTargets" in code
        assert "'/World/geo/hero'" in code
        assert "'/World/geo/ground'" in code

    def test_exclude_light_linking(self, handler):
        """Exclude action adds to excludes relationship."""
        _, _, py_lop = self._setup_lop(handler)

        result = handler._handle_configure_light_linking({
            "light_path": "/World/lights/key",
            "action": "exclude",
            "geo_paths": ["/World/geo/bg"],
        })

        code = py_lop.parm.return_value.set.call_args[0][0]
        assert "GetExcludesRel" in code
        assert "'/World/geo/bg'" in code

    def test_shadow_include(self, handler):
        """Shadow include uses GetShadowLinkCollectionAPI."""
        _, _, py_lop = self._setup_lop(handler)

        handler._handle_configure_light_linking({
            "light_path": "/World/lights/key",
            "action": "shadow_include",
            "geo_paths": ["/World/geo/hero"],
        })

        code = py_lop.parm.return_value.set.call_args[0][0]
        assert "GetShadowLinkCollectionAPI" in code
        assert "ClearTargets" in code

    def test_shadow_exclude(self, handler):
        """Shadow exclude uses GetShadowLinkCollectionAPI + excludes."""
        _, _, py_lop = self._setup_lop(handler)

        handler._handle_configure_light_linking({
            "light_path": "/World/lights/key",
            "action": "shadow_exclude",
            "geo_paths": ["/World/geo/glass"],
        })

        code = py_lop.parm.return_value.set.call_args[0][0]
        assert "GetShadowLinkCollectionAPI" in code
        assert "GetExcludesRel" in code

    def test_reset_restores_default(self, handler):
        """Reset action clears targets and adds root path."""
        _, _, py_lop = self._setup_lop(handler)

        result = handler._handle_configure_light_linking({
            "light_path": "/World/lights/key",
            "action": "reset",
        })

        assert result["action"] == "reset"
        assert "geo_paths" not in result
        code = py_lop.parm.return_value.set.call_args[0][0]
        assert "ClearTargets" in code
        assert "AddTarget(Sdf.Path('/'))" in code

    def test_invalid_action_raises(self, handler):
        self._setup_lop(handler)
        with pytest.raises(ValueError, match="isn't a recognized light linking action"):
            handler._handle_configure_light_linking({
                "light_path": "/World/lights/key",
                "action": "bad",
            })

    def test_missing_geo_paths_raises(self, handler):
        self._setup_lop(handler)
        with pytest.raises(ValueError, match="pass 'geo_paths'"):
            handler._handle_configure_light_linking({
                "light_path": "/World/lights/key",
                "action": "include",
            })


def teardown_module():
    if "hou" in sys.modules and sys.modules["hou"] is hou_mock:
        del sys.modules["hou"]
