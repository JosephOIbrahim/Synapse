"""Tests for the HDA (Houdini Digital Asset) handlers.

Mock-based -- no Houdini required.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load handlers without Houdini
# ---------------------------------------------------------------------------

# Minimal hou stub
if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=24.0)
    _hou.selectedNodes = MagicMock(return_value=[])
    _hou.undos = MagicMock()
    _hou.hda = MagicMock()
    _hou.exprLanguage = MagicMock()
    _hou.exprLanguage.Hscript = "Hscript"
    _hou.scriptLanguage = MagicMock()
    _hou.scriptLanguage.Python = "Python"
    _hou.FolderParmTemplate = MagicMock()
    _hou.Keyframe = MagicMock
    _hou.OperationFailed = type("OperationFailed", (Exception,), {})
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]
    # Ensure required attributes exist (may be missing if another test set up hou first)
    if not hasattr(_hou, "undos"):
        _hou.undos = MagicMock()
    if not hasattr(_hou, "hda"):
        _hou.hda = MagicMock()
    if not hasattr(_hou, "exprLanguage"):
        _hou.exprLanguage = MagicMock()
        _hou.exprLanguage.Hscript = "Hscript"
    if not hasattr(_hou, "scriptLanguage"):
        _hou.scriptLanguage = MagicMock()
        _hou.scriptLanguage.Python = "Python"
    if not hasattr(_hou, "FolderParmTemplate"):
        _hou.FolderParmTemplate = MagicMock()

if "hdefereval" not in sys.modules:
    _hde = types.ModuleType("hdefereval")
    _hde.executeDeferred = lambda fn: fn()
    _hde.executeInMainThreadWithResult = lambda fn: fn()
    sys.modules["hdefereval"] = _hde

# Import handlers via importlib to bypass package __init__
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

# Get the hou module that handlers.py actually imported
_handlers_hou = handlers_mod.hou

# Ensure the handler's hou reference has all attributes we need
if not hasattr(_handlers_hou, "undos"):
    _handlers_hou.undos = MagicMock()
if not hasattr(_handlers_hou, "hda"):
    _handlers_hou.hda = MagicMock()
if not hasattr(_handlers_hou, "exprLanguage"):
    _handlers_hou.exprLanguage = MagicMock()
    _handlers_hou.exprLanguage.Hscript = "Hscript"
if not hasattr(_handlers_hou, "scriptLanguage"):
    _handlers_hou.scriptLanguage = MagicMock()
    _handlers_hou.scriptLanguage.Python = "Python"
if not hasattr(_handlers_hou, "FolderParmTemplate"):
    _handlers_hou.FolderParmTemplate = MagicMock()
if not hasattr(_handlers_hou, "OperationFailed"):
    _handlers_hou.OperationFailed = type("OperationFailed", (Exception,), {})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def handler():
    h = handlers_mod.SynapseHandler()
    h._bridge = MagicMock()
    return h


def _make_subnet(path="/obj/geo1/my_subnet"):
    """Create a mock subnet node suitable for HDA creation."""
    node = MagicMock()
    node.path.return_value = path

    # Mock the HDA node returned by createDigitalAsset
    hda_node = MagicMock()
    hda_node.path.return_value = path
    definition = MagicMock()
    node_type = MagicMock()
    node_type.definition.return_value = definition
    hda_node.type.return_value = node_type

    node.createDigitalAsset.return_value = hda_node
    return node, hda_node, definition


def _make_hda_node(path="/obj/geo1/my_hda"):
    """Create a mock HDA instance node."""
    hda_node = MagicMock()
    hda_node.path.return_value = path

    definition = MagicMock()
    node_type = MagicMock()
    node_type.definition.return_value = definition
    node_type_category = MagicMock()
    node_type_category.name.return_value = "Sop"
    definition.nodeTypeCategory.return_value = node_type_category
    hda_node.type.return_value = node_type

    # Parameter template group
    ptg = MagicMock()
    ptg.find.return_value = None  # No existing parm by default
    ptg.findFolder.return_value = None  # No existing folder by default
    definition.parmTemplateGroup.return_value = ptg

    return hda_node, definition, ptg


# ---------------------------------------------------------------------------
# Tests: hda_create
# ---------------------------------------------------------------------------

class TestHdaCreate:
    def test_hda_create_from_valid_subnet(self, handler):
        """Create HDA from a valid subnet -- verify createDigitalAsset called."""
        subnet, hda_node, definition = _make_subnet()

        with patch.object(_handlers_hou, "node", return_value=subnet):
            result = handler._handle_hda_create({
                "subnet_path": "/obj/geo1/my_subnet",
                "operator_name": "my_tool",
                "operator_label": "My Tool",
                "category": "Sop",
                "save_path": "/tmp/my_tool.hda",
            })

        assert result["status"] == "ok"
        assert result["operator_type"] == "Sop/my_tool"
        assert result["save_path"] == "/tmp/my_tool.hda"

        subnet.createDigitalAsset.assert_called_once_with(
            name="my_tool",
            hda_file_name="/tmp/my_tool.hda",
            description="My Tool",
            min_num_inputs=0,
            max_num_inputs=1,
        )

    def test_hda_create_fails_missing_subnet(self, handler):
        """Non-existent subnet returns error with coaching tone."""
        with patch.object(_handlers_hou, "node", return_value=None):
            with pytest.raises(ValueError, match="Couldn't find subnet"):
                handler._handle_hda_create({
                    "subnet_path": "/obj/nonexistent",
                    "operator_name": "my_tool",
                    "operator_label": "My Tool",
                    "category": "Sop",
                    "save_path": "/tmp/my_tool.hda",
                })

    def test_hda_create_validates_category(self, handler):
        """Invalid category is rejected."""
        with pytest.raises(ValueError, match="isn't a valid HDA category"):
            handler._handle_hda_create({
                "subnet_path": "/obj/geo1/my_subnet",
                "operator_name": "my_tool",
                "operator_label": "My Tool",
                "category": "InvalidCategory",
                "save_path": "/tmp/my_tool.hda",
            })

    def test_hda_create_sets_metadata(self, handler):
        """Verify HDADefinition metadata is set (version, comment)."""
        subnet, hda_node, definition = _make_subnet()

        with patch.object(_handlers_hou, "node", return_value=subnet):
            handler._handle_hda_create({
                "subnet_path": "/obj/geo1/my_subnet",
                "operator_name": "my_tool",
                "operator_label": "My Tool",
                "category": "Sop",
                "version": "2.1.0",
                "save_path": "/tmp/my_tool.hda",
            })

        definition.setVersion.assert_called_once_with("2.1.0")
        definition.setComment.assert_called_once_with("My Tool")

    def test_hda_create_installs_file(self, handler):
        """Verify hou.hda.installFile is called."""
        subnet, hda_node, definition = _make_subnet()

        with patch.object(_handlers_hou, "node", return_value=subnet):
            with patch.object(_handlers_hou, "hda", create=True) as mock_hda:
                handler._handle_hda_create({
                    "subnet_path": "/obj/geo1/my_subnet",
                    "operator_name": "my_tool",
                    "operator_label": "My Tool",
                    "category": "Sop",
                    "save_path": "/tmp/my_tool.hda",
                })

        mock_hda.installFile.assert_called_once_with("/tmp/my_tool.hda")


# ---------------------------------------------------------------------------
# Tests: hda_promote_parm
# ---------------------------------------------------------------------------

class TestHdaPromoteParm:
    def test_hda_promote_single_parm(self, handler):
        """Verify a parameter template is added to the group."""
        hda_node, definition, ptg = _make_hda_node()

        # Internal node with a parameter
        internal = MagicMock()
        source_parm = MagicMock()
        source_template = MagicMock()
        source_template.label.return_value = "Count"
        cloned_template = MagicMock()
        source_template.clone.return_value = cloned_template
        source_parm.parmTemplate.return_value = source_template
        internal.parm.return_value = source_parm

        # hda_node.node("scatter1") returns internal
        hda_node.node.return_value = internal
        # promoted parm lookup
        hda_node.parm.return_value = MagicMock()

        with patch.object(_handlers_hou, "node", return_value=hda_node):
            result = handler._handle_hda_promote_parm({
                "hda_path": "/obj/geo1/my_hda",
                "internal_node": "scatter1",
                "parm_name": "npts",
            })

        assert result["status"] == "ok"
        assert result["promoted_parm"] == "scatter1_npts"

        cloned_template.setName.assert_called_once_with("scatter1_npts")
        cloned_template.setLabel.assert_called_once_with("Count")
        ptg.append.assert_called_once_with(cloned_template)
        definition.setParmTemplateGroup.assert_called_once_with(ptg)

    def test_hda_promote_to_folder(self, handler):
        """Verify folder template is created when folder param is given."""
        hda_node, definition, ptg = _make_hda_node()

        internal = MagicMock()
        source_parm = MagicMock()
        source_template = MagicMock()
        source_template.label.return_value = "Seed"
        cloned_template = MagicMock()
        source_template.clone.return_value = cloned_template
        source_parm.parmTemplate.return_value = source_template
        internal.parm.return_value = source_parm
        hda_node.node.return_value = internal
        hda_node.parm.return_value = MagicMock()

        with patch.object(_handlers_hou, "node", return_value=hda_node):
            with patch.object(_handlers_hou, "FolderParmTemplate", create=True) as mock_folder_cls:
                mock_folder = MagicMock()
                mock_folder_cls.return_value = mock_folder

                result = handler._handle_hda_promote_parm({
                    "hda_path": "/obj/geo1/my_hda",
                    "internal_node": "scatter1",
                    "parm_name": "seed",
                    "folder": "Advanced Settings",
                })

        assert result["folder"] == "Advanced Settings"
        # Should have created a new folder and appended to ptg
        mock_folder_cls.assert_called_once()
        mock_folder.addParmTemplate.assert_called_once_with(cloned_template)

    def test_hda_promote_idempotent(self, handler):
        """Re-promoting same parm removes old and re-adds."""
        hda_node, definition, ptg = _make_hda_node()

        # Simulate existing parm in the group
        existing_template = MagicMock()
        ptg.find.return_value = existing_template

        internal = MagicMock()
        source_parm = MagicMock()
        source_template = MagicMock()
        source_template.label.return_value = "Count"
        cloned_template = MagicMock()
        source_template.clone.return_value = cloned_template
        source_parm.parmTemplate.return_value = source_template
        internal.parm.return_value = source_parm
        hda_node.node.return_value = internal
        hda_node.parm.return_value = MagicMock()

        with patch.object(_handlers_hou, "node", return_value=hda_node):
            result = handler._handle_hda_promote_parm({
                "hda_path": "/obj/geo1/my_hda",
                "internal_node": "scatter1",
                "parm_name": "npts",
            })

        assert result["status"] == "ok"
        # Should remove the old one first
        ptg.remove.assert_called_once_with("scatter1_npts")
        # Then append the new one
        ptg.append.assert_called_once_with(cloned_template)

    def test_hda_promote_fails_missing_node(self, handler):
        """Internal node doesn't exist -- coaching tone error."""
        hda_node, definition, ptg = _make_hda_node()
        hda_node.node.return_value = None

        with patch.object(_handlers_hou, "node", return_value=hda_node):
            with pytest.raises(ValueError, match="Couldn't find internal node"):
                handler._handle_hda_promote_parm({
                    "hda_path": "/obj/geo1/my_hda",
                    "internal_node": "nonexistent",
                    "parm_name": "count",
                })


# ---------------------------------------------------------------------------
# Tests: hda_set_help
# ---------------------------------------------------------------------------

class TestHdaSetHelp:
    def test_hda_set_help_summary(self, handler):
        """Verify setComment is called for summary."""
        hda_node, definition, _ = _make_hda_node()

        with patch.object(_handlers_hou, "node", return_value=hda_node):
            result = handler._handle_hda_set_help({
                "hda_path": "/obj/geo1/my_hda",
                "summary": "Scatters points on a surface",
            })

        assert result["status"] == "ok"
        assert result["help_set"] is True
        definition.setComment.assert_called_once_with("Scatters points on a surface")

    def test_hda_set_help_full(self, handler):
        """Verify help sections are created with all fields."""
        hda_node, definition, _ = _make_hda_node()

        with patch.object(_handlers_hou, "node", return_value=hda_node):
            result = handler._handle_hda_set_help({
                "hda_path": "/obj/geo1/my_hda",
                "summary": "Point Scatter",
                "description": "Scatters points randomly on surfaces.",
                "parameters_help": {
                    "count": "Number of points to scatter",
                    "seed": "Random seed for reproducibility",
                },
                "tips": ["Use higher count for dense coverage"],
                "author": "Synapse",
            })

        assert result["help_set"] is True
        definition.setComment.assert_called_once_with("Point Scatter")
        # Verify addSection was called with HelpText
        definition.addSection.assert_called_once()
        section_name, help_content = definition.addSection.call_args[0]
        assert section_name == "HelpText"
        assert "Point Scatter" in help_content
        assert "Scatters points randomly" in help_content
        assert "@parameters" in help_content
        assert "count:" in help_content
        assert "seed:" in help_content
        assert "TIP:" in help_content
        assert "@author Synapse" in help_content


# ---------------------------------------------------------------------------
# Tests: hda_package
# ---------------------------------------------------------------------------

class TestHdaPackage:
    def test_hda_package_orchestration(self, handler):
        """Verify the full pipeline calls in order."""
        parent_node = MagicMock()
        container = MagicMock()
        subnet = MagicMock()

        # Container creates subnet
        parent_node.createNode.return_value = container
        container.createNode.return_value = subnet

        # Subnet creates HDA
        hda_node = MagicMock()
        hda_node.path.return_value = "/obj/temp_my_tool/my_tool"
        definition = MagicMock()
        node_type = MagicMock()
        node_type.definition.return_value = definition
        hda_node.type.return_value = node_type
        subnet.createDigitalAsset.return_value = hda_node

        ptg = MagicMock()
        ptg.find.return_value = None
        definition.parmTemplateGroup.return_value = ptg

        with patch.object(_handlers_hou, "node", return_value=parent_node):
            with patch.object(_handlers_hou, "hda", create=True):
                result = handler._handle_hda_package({
                    "description": "Scatters points on surfaces",
                    "name": "my_tool",
                    "category": "Sop",
                    "save_path": "/tmp/my_tool.hda",
                })

        assert result["status"] == "ok"
        assert result["operator_type"] == "Sop/my_tool"
        assert result["save_path"] == "/tmp/my_tool.hda"

        # Verify container and subnet creation
        parent_node.createNode.assert_called_once_with("geo", "temp_my_tool")
        container.createNode.assert_called_once_with("subnet", "my_tool")

        # Verify createDigitalAsset was called
        subnet.createDigitalAsset.assert_called_once()

    def test_hda_package_rollback(self, handler):
        """Verify undo on failure."""
        parent_node = MagicMock()
        container = MagicMock()
        subnet = MagicMock()

        parent_node.createNode.return_value = container
        container.createNode.return_value = subnet

        # Make createDigitalAsset fail
        subnet.createDigitalAsset.side_effect = RuntimeError("Something broke")

        with patch.object(_handlers_hou, "node", return_value=parent_node):
            with pytest.raises(RuntimeError, match="Something broke"):
                handler._handle_hda_package({
                    "description": "Scatters points on surfaces",
                    "name": "my_tool",
                    "category": "Sop",
                    "save_path": "/tmp/my_tool.hda",
                })

        # Verify undo was attempted
        _handlers_hou.undos.performUndo.assert_called()


# ---------------------------------------------------------------------------
# Tests: registration
# ---------------------------------------------------------------------------

class TestHdaPackageNodes:
    """Tests for hda_package with nodes and connections spec."""

    def _make_package_mocks(self):
        """Set up parent/container/subnet/hda mocks for package tests."""
        parent_node = MagicMock()
        container = MagicMock()
        subnet = MagicMock()

        parent_node.createNode.return_value = container
        container.createNode.return_value = subnet

        # Internal nodes created inside subnet
        created_internal = {}

        def _subnet_create_node(node_type, node_name=None):
            node = MagicMock()
            actual_name = node_name or node_type
            node.name.return_value = actual_name
            node.path.return_value = f"/obj/temp_test/{actual_name}"
            node.parm.return_value = MagicMock()
            created_internal[actual_name] = node
            return node

        subnet.createNode.side_effect = _subnet_create_node
        subnet.indirectInputs.return_value = [MagicMock()]

        # HDA node
        hda_node = MagicMock()
        hda_node.path.return_value = "/obj/temp_test/test_tool"
        definition = MagicMock()
        node_type = MagicMock()
        node_type.definition.return_value = definition
        hda_node.type.return_value = node_type
        subnet.createDigitalAsset.return_value = hda_node

        ptg = MagicMock()
        ptg.find.return_value = None
        definition.parmTemplateGroup.return_value = ptg

        # hda_node.node() looks up internal nodes by name
        hda_node.node.side_effect = lambda n: created_internal.get(n)

        return parent_node, subnet, hda_node, definition, created_internal

    def test_package_creates_internal_nodes(self, handler):
        """Nodes spec creates internal nodes inside the subnet."""
        parent, subnet, hda_node, defn, created = self._make_package_mocks()

        with patch.object(_handlers_hou, "node", return_value=parent):
            with patch.object(_handlers_hou, "hda", create=True):
                result = handler._handle_hda_package({
                    "description": "Test tool",
                    "name": "test_tool",
                    "category": "Sop",
                    "save_path": "/tmp/test.hda",
                    "nodes": [
                        {"type": "scatter", "name": "scatter1"},
                        {"type": "null", "name": "OUT"},
                    ],
                })

        assert result["status"] == "ok"
        assert result["node_count"] == 2
        # subnet.createNode called for the subnet itself + 2 internal nodes
        assert subnet.createNode.call_count >= 2

    def test_package_wires_connections(self, handler):
        """Connections spec wires nodes including __input0 convention."""
        parent, subnet, hda_node, defn, created = self._make_package_mocks()

        with patch.object(_handlers_hou, "node", return_value=parent):
            with patch.object(_handlers_hou, "hda", create=True):
                result = handler._handle_hda_package({
                    "description": "Test tool",
                    "name": "test_tool",
                    "category": "Sop",
                    "save_path": "/tmp/test.hda",
                    "nodes": [
                        {"type": "scatter", "name": "scatter1"},
                        {"type": "null", "name": "OUT"},
                    ],
                    "connections": [
                        ["__input0", "scatter1", "0"],
                        ["scatter1", "OUT", "0"],
                    ],
                })

        assert result["status"] == "ok"
        # scatter1 should have setInput called (from __input0)
        scatter_node = created["scatter1"]
        scatter_node.setInput.assert_called()
        # OUT should have setInput called (from scatter1)
        out_node = created["OUT"]
        out_node.setInput.assert_called()

    def test_package_sets_node_parms(self, handler):
        """Nodes spec sets parameters on created nodes."""
        parent, subnet, hda_node, defn, created = self._make_package_mocks()

        with patch.object(_handlers_hou, "node", return_value=parent):
            with patch.object(_handlers_hou, "hda", create=True):
                result = handler._handle_hda_package({
                    "description": "Test tool",
                    "name": "test_tool",
                    "category": "Sop",
                    "save_path": "/tmp/test.hda",
                    "nodes": [
                        {"type": "scatter", "name": "scatter1",
                         "parms": {"npts": 100, "seed": 42}},
                    ],
                })

        assert result["status"] == "ok"
        scatter_node = created["scatter1"]
        # parm() was called for each parameter
        scatter_node.parm.assert_any_call("npts")
        scatter_node.parm.assert_any_call("seed")

    def test_package_invalid_node_type_raises(self, handler):
        """Invalid node type triggers rollback with coaching tone error."""
        parent_node = MagicMock()
        container = MagicMock()
        subnet = MagicMock()

        parent_node.createNode.return_value = container
        container.createNode.return_value = subnet

        # Make subnet.createNode return None for invalid type
        subnet.createNode.return_value = None
        subnet.indirectInputs.return_value = [MagicMock()]

        with patch.object(_handlers_hou, "node", return_value=parent_node):
            with pytest.raises(ValueError, match="Couldn't create node"):
                handler._handle_hda_package({
                    "description": "Test tool",
                    "name": "test_tool",
                    "category": "Sop",
                    "save_path": "/tmp/test.hda",
                    "nodes": [
                        {"type": "nonexistent_type", "name": "bad_node"},
                    ],
                })

        _handlers_hou.undos.performUndo.assert_called()

    def test_package_validation_catches_cook_errors(self, handler):
        """Cook errors are captured as warnings, not exceptions."""
        parent, subnet, hda_node, defn, created = self._make_package_mocks()

        # Make cook raise an error
        hda_node.cook.side_effect = RuntimeError("Cook failed: missing input")

        with patch.object(_handlers_hou, "node", return_value=parent):
            with patch.object(_handlers_hou, "hda", create=True):
                result = handler._handle_hda_package({
                    "description": "Test tool",
                    "name": "test_tool",
                    "category": "Sop",
                    "save_path": "/tmp/test.hda",
                })

        assert result["status"] == "ok"
        assert any("Cook warning" in w for w in result["warnings"])

    def test_package_validation_missing_promoted_node(self, handler):
        """Promoted parm referencing nonexistent node produces warning."""
        parent, subnet, hda_node, defn, created = self._make_package_mocks()

        # hda_node.node returns None for missing nodes
        hda_node.node.side_effect = lambda n: None

        with patch.object(_handlers_hou, "node", return_value=parent):
            with patch.object(_handlers_hou, "hda", create=True):
                result = handler._handle_hda_package({
                    "description": "Test tool",
                    "name": "test_tool",
                    "category": "Sop",
                    "save_path": "/tmp/test.hda",
                    "promoted_parms": [
                        {"node": "ghost_node", "parm": "count"},
                    ],
                })

        assert result["status"] == "ok"
        assert any("ghost_node" in w for w in result["warnings"])

    def test_package_validation_missing_promoted_parm(self, handler):
        """Promoted parm referencing nonexistent parameter produces warning."""
        parent, subnet, hda_node, defn, created = self._make_package_mocks()

        # Node exists but parm returns None
        ref_node = MagicMock()
        ref_node.parm.return_value = None
        hda_node.node.side_effect = lambda n: ref_node if n == "scatter1" else None

        with patch.object(_handlers_hou, "node", return_value=parent):
            with patch.object(_handlers_hou, "hda", create=True):
                result = handler._handle_hda_package({
                    "description": "Test tool",
                    "name": "test_tool",
                    "category": "Sop",
                    "save_path": "/tmp/test.hda",
                    "nodes": [
                        {"type": "scatter", "name": "scatter1"},
                    ],
                    "promoted_parms": [
                        {"node": "scatter1", "parm": "nonexistent_parm"},
                    ],
                })

        assert result["status"] == "ok"
        assert any("nonexistent_parm" in w for w in result["warnings"])

    def test_package_lop_context_uses_stage(self, handler):
        """Lop category creates subnet under /stage, not /obj."""
        parent_node = MagicMock()
        subnet = MagicMock()

        parent_node.createNode.return_value = subnet

        hda_node = MagicMock()
        hda_node.path.return_value = "/stage/test_lop"
        definition = MagicMock()
        node_type = MagicMock()
        node_type.definition.return_value = definition
        hda_node.type.return_value = node_type
        subnet.createDigitalAsset.return_value = hda_node
        subnet.indirectInputs.return_value = [MagicMock()]

        ptg = MagicMock()
        ptg.find.return_value = None
        definition.parmTemplateGroup.return_value = ptg

        with patch.object(_handlers_hou, "node", return_value=parent_node):
            with patch.object(_handlers_hou, "hda", create=True):
                result = handler._handle_hda_package({
                    "description": "LOP tool",
                    "name": "test_lop",
                    "category": "Lop",
                    "save_path": "/tmp/test_lop.hda",
                })

        assert result["status"] == "ok"
        # For Lop, no geo container — subnet created directly on parent
        parent_node.createNode.assert_called_once_with("subnet", "test_lop")


# ---------------------------------------------------------------------------
# Tests: hda_list
# ---------------------------------------------------------------------------

class TestHdaList:
    def test_hda_list_finds_synapse_hdas(self, handler):
        """hda_list returns HDAs with author=synapse in extraInfo."""
        # Mock hou.hda.loadedFiles and definitionsInFile
        synapse_defn = MagicMock()
        synapse_defn.extraInfo.return_value = (
            "author=synapse;version=1.0.0;created=2026-01-15 10:30:00"
        )
        synapse_defn.nodeTypeName.return_value = "scatter_tool"
        synapse_defn.description.return_value = "Scatter Tool"
        cat = MagicMock()
        cat.name.return_value = "Sop"
        synapse_defn.nodeTypeCategory.return_value = cat

        with patch.object(_handlers_hou, "hda", create=True) as mock_hda:
            mock_hda.loadedFiles.return_value = ["/tmp/scatter_tool.hda"]
            mock_hda.definitionsInFile.return_value = [synapse_defn]
            result = handler._handle_hda_list({})

        assert result["status"] == "ok"
        assert result["count"] == 1
        assert result["hdas"][0]["name"] == "scatter_tool"
        assert result["hdas"][0]["version"] == "1.0.0"
        assert result["hdas"][0]["category"] == "Sop"

    def test_hda_list_excludes_non_synapse(self, handler):
        """hda_list skips HDAs without author=synapse."""
        other_defn = MagicMock()
        other_defn.extraInfo.return_value = "author=sidefx;version=1.0"

        synapse_defn = MagicMock()
        synapse_defn.extraInfo.return_value = "author=synapse;version=2.0.0"
        synapse_defn.nodeTypeName.return_value = "my_tool"
        synapse_defn.description.return_value = "My Tool"
        cat = MagicMock()
        cat.name.return_value = "Sop"
        synapse_defn.nodeTypeCategory.return_value = cat

        with patch.object(_handlers_hou, "hda", create=True) as mock_hda:
            mock_hda.loadedFiles.return_value = ["/tmp/a.hda", "/tmp/b.hda"]
            mock_hda.definitionsInFile.side_effect = [
                [other_defn],
                [synapse_defn],
            ]
            result = handler._handle_hda_list({})

        assert result["count"] == 1
        assert result["hdas"][0]["name"] == "my_tool"

    def test_hda_list_empty_scene(self, handler):
        """hda_list returns empty list when no HDAs are loaded."""
        with patch.object(_handlers_hou, "hda", create=True) as mock_hda:
            mock_hda.loadedFiles.return_value = []
            result = handler._handle_hda_list({})

        assert result["status"] == "ok"
        assert result["count"] == 0
        assert result["hdas"] == []


# ---------------------------------------------------------------------------
# Tests: registration
# ---------------------------------------------------------------------------

class TestHdaRegistration:
    def test_hda_registered_in_handlers(self, handler):
        """Verify all 5 HDA handlers are in the registry."""
        registered = handler._registry.registered_types
        assert "hda_create" in registered
        assert "hda_promote_parm" in registered
        assert "hda_set_help" in registered
        assert "hda_package" in registered
        assert "hda_list" in registered

    def test_hda_mcp_tools_listed(self):
        """Verify all 5 HDA tools appear in the MCP tool registry."""
        # Import mcp/tools.py to check tool definitions
        tools_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "mcp" / "tools.py"

        # Ensure the mcp package modules exist
        for mod_name, mod_path in [
            ("synapse.mcp", Path(__file__).resolve().parent.parent / "python" / "synapse" / "mcp"),
        ]:
            if mod_name not in sys.modules:
                pkg = types.ModuleType(mod_name)
                pkg.__path__ = [str(mod_path)]
                sys.modules[mod_name] = pkg

        if "synapse.mcp.tools" not in sys.modules:
            spec = importlib.util.spec_from_file_location("synapse.mcp.tools", tools_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["synapse.mcp.tools"] = mod
            spec.loader.exec_module(mod)
        else:
            # Reload to pick up new tool
            mod = sys.modules["synapse.mcp.tools"]
            importlib.reload(mod)

        tools_mod = sys.modules["synapse.mcp.tools"]
        tool_names = tools_mod.get_tool_names()

        assert "houdini_hda_create" in tool_names
        assert "houdini_hda_promote_parm" in tool_names
        assert "houdini_hda_set_help" in tool_names
        assert "houdini_hda_package" in tool_names
        assert "houdini_hda_list" in tool_names

        # Verify dispatch entries exist too
        assert tools_mod.has_tool("houdini_hda_create")
        assert tools_mod.has_tool("houdini_hda_promote_parm")
        assert tools_mod.has_tool("houdini_hda_set_help")
        assert tools_mod.has_tool("houdini_hda_package")
        assert tools_mod.has_tool("houdini_hda_list")
