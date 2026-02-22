"""End-to-end integration tests for the HDA + Chat Panel + Network Explainer sprint.

Verifies cross-workstream data flow:
- network_explain output feeds into HDA creation pipeline
- Quick actions map to registered handlers
- MCP tool registries are complete and in sync
- message_formatter renders handler outputs correctly
- Handler cross-references and pattern detection coverage

Mock-based -- no Houdini required.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    _hou.text = MagicMock()
    _hou.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]
    for attr in ["undos", "hda", "exprLanguage", "FolderParmTemplate", "scriptLanguage"]:
        if not hasattr(_hou, attr):
            setattr(_hou, attr, MagicMock())
    if not hasattr(_hou.exprLanguage, "Hscript"):
        _hou.exprLanguage.Hscript = "Hscript"
    if not hasattr(_hou.scriptLanguage, "Python"):
        _hou.scriptLanguage.Python = "Python"

# Stub hdefereval
if "hdefereval" not in sys.modules:
    _hde = types.ModuleType("hdefereval")
    _hde.executeDeferred = lambda fn: fn()
    _hde.executeInMainThreadWithResult = lambda fn: fn()
    sys.modules["hdefereval"] = _hde
else:
    _hde = sys.modules["hdefereval"]
    if not hasattr(_hde, "executeInMainThreadWithResult"):
        _hde.executeInMainThreadWithResult = lambda fn: fn()
    if not hasattr(_hde, "executeDeferred"):
        _hde.executeDeferred = lambda fn: fn()

# Import handlers via importlib to bypass package __init__
_base = Path(__file__).resolve().parent.parent / "python" / "synapse"

for mod_name, mod_path in [
    ("synapse", _base),
    ("synapse.core", _base / "core"),
    ("synapse.server", _base / "server"),
    ("synapse.session", _base / "session"),
    ("synapse.panel", _base / "panel" if (_base / "panel").exists() else _base),
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
for attr in ["undos", "hda", "exprLanguage", "scriptLanguage", "FolderParmTemplate"]:
    if not hasattr(_handlers_hou, attr):
        setattr(_handlers_hou, attr, MagicMock())
if not hasattr(_handlers_hou.exprLanguage, "Hscript"):
    _handlers_hou.exprLanguage.Hscript = "Hscript"
if not hasattr(_handlers_hou.scriptLanguage, "Python"):
    _handlers_hou.scriptLanguage.Python = "Python"

# Load handlers_node module (for _NETWORK_PATTERNS)
if "synapse.server.handlers_node" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "synapse.server.handlers_node",
        _base / "server" / "handlers_node.py",
    )
    handlers_node_mod = importlib.util.module_from_spec(spec)
    sys.modules["synapse.server.handlers_node"] = handlers_node_mod
    spec.loader.exec_module(handlers_node_mod)
else:
    handlers_node_mod = sys.modules["synapse.server.handlers_node"]

# Load mcp/tools.py
_mcp_path = _base / "mcp"
if "synapse.mcp" not in sys.modules:
    pkg = types.ModuleType("synapse.mcp")
    pkg.__path__ = [str(_mcp_path)]
    sys.modules["synapse.mcp"] = pkg
if "synapse.mcp.tools" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "synapse.mcp.tools", _mcp_path / "tools.py"
    )
    mcp_tools_mod = importlib.util.module_from_spec(spec)
    sys.modules["synapse.mcp.tools"] = mcp_tools_mod
    spec.loader.exec_module(mcp_tools_mod)
else:
    mcp_tools_mod = sys.modules["synapse.mcp.tools"]

# Load panel/quick_actions.py
_panel_path = _base / "panel"
if "synapse.panel.quick_actions" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "synapse.panel.quick_actions", _panel_path / "quick_actions.py"
    )
    quick_actions_mod = importlib.util.module_from_spec(spec)
    sys.modules["synapse.panel.quick_actions"] = quick_actions_mod
    spec.loader.exec_module(quick_actions_mod)
else:
    quick_actions_mod = sys.modules["synapse.panel.quick_actions"]

# Load panel/message_formatter.py
if "synapse.panel.message_formatter" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "synapse.panel.message_formatter", _panel_path / "message_formatter.py"
    )
    formatter_mod = importlib.util.module_from_spec(spec)
    sys.modules["synapse.panel.message_formatter"] = formatter_mod
    spec.loader.exec_module(formatter_mod)
else:
    formatter_mod = sys.modules["synapse.panel.message_formatter"]


# ---------------------------------------------------------------------------
# Mock node builder helpers (same pattern as test_network_explain.py)
# ---------------------------------------------------------------------------

def _make_mock_node(name, type_name, type_label=None, inputs=None, outputs=None,
                    children=None, parms=None, path_prefix="/obj/geo1"):
    """Create a mock Houdini node for testing."""
    node = MagicMock()
    node.name.return_value = name
    node.path.return_value = f"{path_prefix}/{name}"

    node_type = MagicMock()
    node_type.name.return_value = type_name
    node_type.description.return_value = type_label or type_name.title()
    node.type.return_value = node_type

    node.inputs.return_value = inputs or []
    node.outputs.return_value = outputs or []
    node.children.return_value = children or []
    node.parms.return_value = parms or []

    return node


def _make_mock_parm(name, current_value, default_value):
    """Create a mock parameter with non-default detection support."""
    parm = MagicMock()
    parm.name.return_value = name
    parm.eval.return_value = current_value

    template = MagicMock()
    template.defaultValue.return_value = (default_value,)
    parm_type = MagicMock()
    parm_type.name.return_value = "Float"
    template.type.return_value = parm_type
    template.label.return_value = name.replace("_", " ").title()
    parm.parmTemplate.return_value = template
    parm.expression.side_effect = Exception("No expression")

    return parm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def handler():
    h = handlers_mod.SynapseHandler()
    h._session_id = "test"
    h._bridge = MagicMock()
    return h


# ===========================================================================
# 1. Explain -> HDA Pipeline
# ===========================================================================


class TestExplainFeedsHdaInterface:
    """network_explain's suggested_hda_interface feeds into hda_promote_parm."""

    def test_explain_feeds_hda_interface(self, handler):
        """Suggested HDA interface entries have the shape hda_promote_parm expects."""
        parm_npts = _make_mock_parm("npts", 1000, 100)
        parm_seed = _make_mock_parm("seed", 42, 0)
        scatter = _make_mock_node("scatter1", "scatter", "Scatter",
                                  parms=[parm_npts, parm_seed])
        copy = _make_mock_node("copytopoints1", "copytopoints", "Copy to Points",
                               inputs=[scatter])
        scatter.outputs.return_value = [copy]

        root = MagicMock()
        root.children.return_value = [scatter, copy]

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain({"node": "/obj/geo1"})

        suggestions = result["suggested_hda_interface"]
        assert len(suggestions) >= 2, "Should suggest at least npts and seed"

        # Each suggestion must have the keys that hda_promote_parm expects
        for s in suggestions:
            assert "node" in s, "Missing 'node' key (maps to internal_node)"
            assert "parm" in s, "Missing 'parm' key (maps to parm_name)"
            assert "label" in s, "Missing 'label' key"
            assert isinstance(s["node"], str)
            assert isinstance(s["parm"], str)

    def test_explain_help_card_feeds_hda_set_help(self, handler):
        """network_explain format='help_card' output is usable by hda_set_help."""
        node_a = _make_mock_node("grid1", "grid", "Grid")
        root = MagicMock()
        root.children.return_value = [node_a]

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain(
                {"node": "/obj/geo1", "format": "help_card"}
            )

        assert result["format"] == "help_card"
        help_text = result["text"]
        assert isinstance(help_text, str)
        assert len(help_text) > 0
        # The help_card text is valid input for hda_set_help's 'description' field
        # Verify it contains wiki markup structure
        assert "= Network Overview =" in help_text

    def test_full_explain_to_hda_pipeline(self, handler):
        """Full pipeline: explain -> create HDA -> promote suggested parms -> set help."""
        # Step 1: Build mock network
        parm_npts = _make_mock_parm("npts", 500, 100)
        scatter = _make_mock_node("scatter1", "scatter", "Scatter",
                                  parms=[parm_npts])
        copy = _make_mock_node("copytopoints1", "copytopoints", "Copy to Points",
                               inputs=[scatter])
        scatter.outputs.return_value = [copy]

        root = MagicMock()
        root.children.return_value = [scatter, copy]

        # Step 2: network_explain
        with patch.object(_handlers_hou, "node", return_value=root):
            explain_result = handler._handle_network_explain(
                {"node": "/obj/geo1", "format": "help_card"}
            )

        assert explain_result["status"] == "ok"
        suggestions = explain_result.get("suggested_hda_interface") or []

        # Step 3: hda_create (mock the subnet + HDA creation)
        subnet_node = MagicMock()
        subnet_node.path.return_value = "/obj/geo1/my_scatter"
        hda_node = MagicMock()
        hda_node.path.return_value = "/obj/geo1/my_scatter"
        definition = MagicMock()
        node_type = MagicMock()
        node_type.definition.return_value = definition
        node_type_cat = MagicMock()
        node_type_cat.name.return_value = "Sop"
        definition.nodeTypeCategory.return_value = node_type_cat
        hda_node.type.return_value = node_type
        subnet_node.createDigitalAsset.return_value = hda_node

        with patch.object(_handlers_hou, "node", return_value=subnet_node):
            with patch.object(_handlers_hou, "hda", create=True):
                create_result = handler._handle_hda_create({
                    "subnet_path": "/obj/geo1/my_scatter",
                    "operator_name": "scatter_on_surface",
                    "operator_label": "Scatter on Surface",
                    "category": "Sop",
                    "save_path": "/tmp/scatter_on_surface.hda",
                })
        assert create_result["status"] == "ok"

        # Step 4: hda_promote_parm for each suggested parm
        ptg = MagicMock()
        ptg.find.return_value = None
        ptg.findFolder.return_value = None
        definition.parmTemplateGroup.return_value = ptg

        internal = MagicMock()
        source_parm = MagicMock()
        source_template = MagicMock()
        source_template.label.return_value = "Count"
        cloned = MagicMock()
        source_template.clone.return_value = cloned
        source_parm.parmTemplate.return_value = source_template
        internal.parm.return_value = source_parm
        hda_node.node.return_value = internal
        hda_node.parm.return_value = MagicMock()

        for suggestion in suggestions:
            with patch.object(_handlers_hou, "node", return_value=hda_node):
                promote_result = handler._handle_hda_promote_parm({
                    "hda_path": "/obj/geo1/my_scatter",
                    "internal_node": suggestion["node"],
                    "parm_name": suggestion["parm"],
                    "label": suggestion["label"],
                })
            assert promote_result["status"] == "ok"

        # Step 5: hda_set_help with help_card text
        with patch.object(_handlers_hou, "node", return_value=hda_node):
            help_result = handler._handle_hda_set_help({
                "hda_path": "/obj/geo1/my_scatter",
                "description": explain_result["text"],
                "summary": "Scatter on Surface",
            })
        assert help_result["status"] == "ok"
        assert help_result["help_set"] is True


# ===========================================================================
# 2. Quick Action -> Handler Mapping
# ===========================================================================


class TestQuickActionHandlerMapping:
    """Quick actions in the chat panel map to registered handler capabilities."""

    def test_quick_action_explain_exists(self):
        """The QUICK_ACTIONS list has an 'Explain' action."""
        actions = quick_actions_mod.QUICK_ACTIONS
        labels = [a["label"] for a in actions]
        assert "Explain" in labels

    def test_quick_action_explain_prompt_is_reasonable(self):
        """The 'Explain' action's prompt contains language for network explanation."""
        actions = quick_actions_mod.QUICK_ACTIONS
        explain_action = next(a for a in actions if a["label"] == "Explain")
        prompt = explain_action["prompt"].lower()
        assert "explain" in prompt
        assert "node" in prompt or "network" in prompt

    def test_quick_action_make_hda_exists(self):
        """The QUICK_ACTIONS list has a 'Make HDA' action."""
        actions = quick_actions_mod.QUICK_ACTIONS
        labels = [a["label"] for a in actions]
        assert "Make HDA" in labels

    def test_quick_action_make_hda_prompt_references_hda(self):
        """The 'Make HDA' action's prompt references HDA packaging."""
        actions = quick_actions_mod.QUICK_ACTIONS
        hda_action = next(a for a in actions if a["label"] == "Make HDA")
        prompt = hda_action["prompt"].lower()
        assert "hda" in prompt

    def test_all_quick_actions_have_required_fields(self):
        """Every quick action has label, icon, prompt, and tooltip."""
        actions = quick_actions_mod.QUICK_ACTIONS
        for action in actions:
            assert "label" in action, f"Missing 'label' in action: {action}"
            assert "prompt" in action, f"Missing 'prompt' in {action['label']}"
            assert "icon" in action, f"Missing 'icon' in {action['label']}"
            assert "tooltip" in action, f"Missing 'tooltip' in {action['label']}"
            assert len(action["prompt"]) > 10, (
                f"Prompt too short for {action['label']}"
            )


# ===========================================================================
# 3. MCP Tool Registration Completeness
# ===========================================================================


class TestMcpToolRegistration:
    """All new tools are registered in both MCP registries."""

    def test_all_new_tools_in_mcp_tools(self):
        """HDA and network_explain tools are registered in mcp/tools.py."""
        tool_names = mcp_tools_mod.get_tool_names()
        expected = [
            "houdini_hda_create",
            "houdini_hda_promote_parm",
            "houdini_hda_set_help",
            "houdini_hda_package",
            "houdini_network_explain",
        ]
        for name in expected:
            assert name in tool_names, f"{name} missing from mcp/tools.py"

    def test_mcp_tools_have_dispatch_entries(self):
        """Each new tool has a dispatch entry (can actually be called)."""
        for name in [
            "houdini_hda_create",
            "houdini_hda_promote_parm",
            "houdini_hda_set_help",
            "houdini_hda_package",
            "houdini_network_explain",
        ]:
            assert mcp_tools_mod.has_tool(name), (
                f"{name} registered but has no dispatch entry"
            )

    def test_new_handlers_registered_in_handler_registry(self, handler):
        """All new handlers exist in the SynapseHandler command registry."""
        registry = handler._registry
        for cmd in [
            "hda_create", "hda_promote_parm", "hda_set_help", "hda_package",
            "network_explain",
        ]:
            assert registry.has(cmd), f"Handler '{cmd}' not in registry"


# ===========================================================================
# 4. Message Formatter for Handler Outputs
# ===========================================================================


class TestMessageFormatterIntegration:
    """message_formatter correctly renders handler response structures."""

    def test_format_network_explain_response(self):
        """format_response renders a network_explain result with node paths as links."""
        mock_response = {
            "status": "ok",
            "text": (
                "Network at /obj/geo1 contains 3 nodes.\n"
                "Sources: grid1. Outputs: null1.\n"
                "```python\nprint('hello')\n```"
            ),
        }
        html = formatter_mod.format_response(mock_response)
        # Should contain the node path as a clickable link
        assert "/obj/geo1" in html
        assert 'href="node:/obj/geo1"' in html
        # Should have a status indicator for "ok"
        assert "9679" in html  # Unicode bullet for status
        # Code block should be rendered as <pre>
        assert "<pre" in html

    def test_format_hda_create_response(self):
        """format_response renders an hda_create result."""
        mock_response = {
            "status": "ok",
            "message": "Created HDA at /obj/geo1/my_tool -- saved to /tmp/my_tool.hda",
        }
        html = formatter_mod.format_response(mock_response)
        assert "/obj/geo1/my_tool" in html
        # The /obj path should become a clickable link
        assert 'href="node:/obj/geo1/my_tool"' in html

    def test_format_plain_string(self):
        """format_response handles a plain string input."""
        html = formatter_mod.format_response("Something happened at /obj/geo1/scatter1")
        assert "/obj/geo1/scatter1" in html
        assert 'href="node:/obj/geo1/scatter1"' in html


# ===========================================================================
# 5. Handler Cross-References
# ===========================================================================


class TestHandlerCrossReferences:
    """Verify consistency between handler thresholds and pattern detection."""

    def test_complexity_thresholds_are_reasonable_for_hda(self, handler):
        """Complexity ratings (simple <5, moderate 5-15, complex >15) are sensible for HDA decisions."""
        # Simple network: 3 nodes
        nodes_simple = [_make_mock_node(f"n{i}", "null", "Null") for i in range(3)]
        root = MagicMock()
        root.children.return_value = nodes_simple
        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain({"node": "/obj/geo1"})
        assert result["complexity"] == "simple"

        # Moderate network: 10 nodes
        nodes_mod = [_make_mock_node(f"n{i}", "null", "Null") for i in range(10)]
        root.children.return_value = nodes_mod
        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain({"node": "/obj/geo1"})
        assert result["complexity"] == "moderate"

        # Complex network: 20 nodes
        nodes_cplx = [_make_mock_node(f"n{i}", "null", "Null") for i in range(20)]
        root.children.return_value = nodes_cplx
        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain({"node": "/obj/geo1"})
        assert result["complexity"] == "complex"

    def test_pattern_detection_coverage(self):
        """_NETWORK_PATTERNS covers key SOP workflows."""
        patterns = handlers_node_mod._NETWORK_PATTERNS
        expected_patterns = [
            "scatter_workflow",
            "simulation_setup",
            "terrain_generation",
            "usd_stage_assembly",
            "deformation_chain",
            "material_assignment",
            "vdb_workflow",
            "particle_system",
        ]
        for p in expected_patterns:
            assert p in patterns, f"Pattern '{p}' missing from _NETWORK_PATTERNS"
            assert "signature" in patterns[p], f"Pattern '{p}' has no signature set"
            assert "description" in patterns[p], f"Pattern '{p}' has no description"
            assert isinstance(patterns[p]["signature"], set), (
                f"Pattern '{p}' signature should be a set of type names"
            )
