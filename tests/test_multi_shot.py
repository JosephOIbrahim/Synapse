"""Tests for multi-shot render pipeline.

Tests the multi_shot_render recipe and tops_multi_shot handler.
Mock-based -- no Houdini or PDG required.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: hou + pdg + hdefereval stubs
# ---------------------------------------------------------------------------

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=1.0)
    _hou.text = MagicMock()
    _hou.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]

if "hdefereval" not in sys.modules:
    _hdefereval = types.ModuleType("hdefereval")
    _hdefereval.executeInMainThreadWithResult = lambda fn, *args, **kwargs: fn(*args, **kwargs)
    sys.modules["hdefereval"] = _hdefereval
else:
    _hdefereval = sys.modules["hdefereval"]
    if not hasattr(_hdefereval, "executeInMainThreadWithResult"):
        _hdefereval.executeInMainThreadWithResult = lambda fn, *args, **kwargs: fn(*args, **kwargs)

if "pdg" not in sys.modules:
    _pdg = types.ModuleType("pdg")

    class _WorkItemState:
        CookedSuccess = "CookedSuccess"
        CookedFail = "CookedFail"
        Cooking = "Cooking"
        Scheduled = "Scheduled"
        Uncooked = "Uncooked"
        CookedCancel = "CookedCancel"

    _pdg.workItemState = _WorkItemState
    sys.modules["pdg"] = _pdg
else:
    _pdg = sys.modules["pdg"]

# Bootstrap synapse package modules
_base = Path(__file__).resolve().parent.parent / "python" / "synapse"

for mod_name, mod_path in [
    ("synapse", _base),
    ("synapse.core", _base / "core"),
    ("synapse.server", _base / "server"),
    ("synapse.session", _base / "session"),
    ("synapse.routing", _base / "routing"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

for mod_name, fpath in [
    ("synapse.core.protocol", _base / "core" / "protocol.py"),
    ("synapse.core.aliases", _base / "core" / "aliases.py"),
    ("synapse.core.errors", _base / "core" / "errors.py"),
    ("synapse.core.determinism", _base / "core" / "determinism.py"),
    ("synapse.core.gates", _base / "core" / "gates.py"),
    ("synapse.server.handlers", _base / "server" / "handlers.py"),
    ("synapse.routing.recipes", _base / "routing" / "recipes.py"),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

handlers_mod = sys.modules["synapse.server.handlers"]
protocol_mod = sys.modules["synapse.core.protocol"]
recipes_mod = sys.modules["synapse.routing.recipes"]

# Get hou reference from handlers_tops module for patching
_tops_mod = sys.modules.get("synapse.server.handlers_tops")
_handlers_hou = _tops_mod.hou if _tops_mod else handlers_mod.hou

if not hasattr(_handlers_hou, "node"):
    _handlers_hou.node = MagicMock()

RecipeRegistry = recipes_mod.RecipeRegistry
SynapseHandler = handlers_mod.SynapseHandler


# ---------------------------------------------------------------------------
# Recipe tests
# ---------------------------------------------------------------------------

class TestMultiShotRecipe:
    """Tests for the multi_shot_render recipe."""

    def setup_method(self):
        self.registry = RecipeRegistry()

    def test_multi_shot_recipe_exists(self):
        """The multi_shot_render recipe should be registered."""
        names = [r.name for r in self.registry.recipes]
        assert "multi_shot_render" in names

    def test_multi_shot_recipe_triggers(self):
        """Recipe should match multi-shot render trigger phrases."""
        test_phrases = [
            "render shots sq010_sh010,sq010_sh020",
            "multi-shot render sq010_sh010,sq010_sh020",
            "render all shots sq010_sh010,sq010_sh020",
            "batch render shots sq010_sh010,sq010_sh020,sq010_sh030",
        ]
        for phrase in test_phrases:
            match = self.registry.match(phrase)
            assert match is not None, f"No match for: {phrase}"
            recipe, params = match
            assert recipe.name == "multi_shot_render"

    def test_multi_shot_recipe_parameters(self):
        """Recipe should extract shots and optional frame range."""
        match = self.registry.match(
            "render shots sq010_sh010,sq010_sh020 frames 1001-1048"
        )
        assert match is not None
        recipe, params = match
        assert "shots" in params
        assert "sq010_sh010" in params["shots"]

    def test_multi_shot_recipe_steps(self):
        """Recipe should have 2 steps: parse shots + tops_multi_shot."""
        match = self.registry.match("render shots sq010_sh010,sq010_sh020")
        assert match is not None
        recipe, params = match
        assert len(recipe.steps) == 2
        assert recipe.steps[0].action == "execute_python"
        assert recipe.steps[1].action == "tops_multi_shot"

    def test_multi_shot_recipe_category(self):
        """Recipe should be in the pipeline category."""
        match = self.registry.match("render shots sq010_sh010")
        assert match is not None
        recipe, _ = match
        assert recipe.category == "pipeline"


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------

class TestMultiShotHandler:
    """Tests for the tops_multi_shot handler."""

    def test_multi_shot_handler_validates_input(self):
        """Handler should reject empty or non-list shots."""
        handler = SynapseHandler()

        # Empty list
        with pytest.raises(ValueError, match="shots"):
            handler._handle_tops_multi_shot({"shots": []})

        # Not a list
        with pytest.raises(ValueError, match="shots"):
            handler._handle_tops_multi_shot({"shots": "not_a_list"})

    def test_multi_shot_handler_validates_shot_names(self):
        """Handler should reject shots without a name field."""
        handler = SynapseHandler()

        with pytest.raises(ValueError, match="missing a 'name' field"):
            handler._handle_tops_multi_shot({
                "shots": [{"frame_start": 1001}]
            })

    def test_multi_shot_handler_empty_shots_error(self):
        """Handler should error on empty shots list."""
        handler = SynapseHandler()

        with pytest.raises(ValueError, match="shots"):
            handler._handle_tops_multi_shot({"shots": []})

    def test_multi_shot_handler_creates_work_items(self):
        """Handler should create TOPS network with per-shot work items."""
        handler = SynapseHandler()

        # Build mock hierarchy
        mock_topnet = MagicMock()
        mock_topnet.path.return_value = "/tasks/multi_shot_render"
        mock_topnet.type.return_value.category.return_value.name.return_value = "TopNet"
        mock_topnet.children.return_value = [
            MagicMock(type=MagicMock(return_value=MagicMock(
                name=MagicMock(return_value="localscheduler")
            )))
        ]

        mock_gen = MagicMock()
        mock_gen.path.return_value = "/tasks/multi_shot_render/shot_generator"
        mock_gen.parm.return_value = MagicMock()
        mock_pdg_node = MagicMock()
        mock_pdg_node.workItems = [MagicMock(), MagicMock(), MagicMock()]
        mock_gen.getPDGNode.return_value = mock_pdg_node

        mock_rop_fetch = MagicMock()
        mock_rop_fetch.path.return_value = "/tasks/multi_shot_render/render_shots"
        mock_rop_fetch.parm.return_value = MagicMock()

        mock_partition = MagicMock()
        mock_partition.path.return_value = "/tasks/multi_shot_render/partition_by_shot"
        mock_partition.parm.return_value = MagicMock()

        mock_tasks_net = MagicMock()
        mock_tasks_net.createNode.return_value = mock_topnet
        mock_topnet.createNode.side_effect = [mock_gen, mock_rop_fetch, mock_partition]

        mock_out = MagicMock()
        mock_out.children.return_value = []

        def _mock_node(path):
            if path == "/tasks":
                return mock_tasks_net
            if path == "/out":
                return mock_out
            return None

        with patch.object(_handlers_hou, "node", side_effect=_mock_node):
            result = handler._handle_tops_multi_shot({
                "shots": [
                    {"name": "sq010_sh010", "frame_start": 1001, "frame_end": 1048},
                    {"name": "sq010_sh020", "frame_start": 1001, "frame_end": 1048},
                    {"name": "sq010_sh030", "frame_start": 1001, "frame_end": 1048},
                ],
                "output_dir": "$HIP/render",
            })

        assert result["shot_count"] == 3
        assert result["work_items_generated"] == 3
        assert result["created_network"] is True
        assert "job_id" in result
        assert result["job_id"].startswith("multi-shot-")

    def test_multi_shot_handler_partitions_by_shot(self):
        """Handler should create a partitionbyattribute node keyed on shot_name."""
        handler = SynapseHandler()

        mock_topnet = MagicMock()
        mock_topnet.path.return_value = "/tasks/multi_shot_render"
        mock_topnet.type.return_value.category.return_value.name.return_value = "TopNet"
        mock_topnet.children.return_value = [
            MagicMock(type=MagicMock(return_value=MagicMock(
                name=MagicMock(return_value="localscheduler")
            )))
        ]

        mock_gen = MagicMock()
        mock_gen.path.return_value = "/tasks/multi_shot_render/shot_generator"
        mock_pdg_node = MagicMock()
        mock_pdg_node.workItems = [MagicMock()]
        mock_gen.getPDGNode.return_value = mock_pdg_node

        mock_rop_fetch = MagicMock()
        mock_rop_fetch.path.return_value = "/tasks/multi_shot_render/render_shots"

        mock_partition = MagicMock()
        mock_partition.path.return_value = "/tasks/multi_shot_render/partition_by_shot"
        partition_attr_parm = MagicMock()
        mock_partition.parm.return_value = partition_attr_parm

        mock_tasks_net = MagicMock()
        mock_tasks_net.createNode.return_value = mock_topnet
        mock_topnet.createNode.side_effect = [mock_gen, mock_rop_fetch, mock_partition]

        mock_out = MagicMock()
        mock_out.children.return_value = []

        def _mock_node(path):
            if path == "/tasks":
                return mock_tasks_net
            if path == "/out":
                return mock_out
            return None

        with patch.object(_handlers_hou, "node", side_effect=_mock_node):
            result = handler._handle_tops_multi_shot({
                "shots": [{"name": "sq010_sh010"}],
            })

        # Verify partitionbyattribute was created
        assert result["partition"] == "/tasks/multi_shot_render/partition_by_shot"
        # Verify the attribute was set to shot_name
        mock_topnet.createNode.assert_any_call("partitionbyattribute", "partition_by_shot")
        partition_attr_parm.set.assert_called_with("shot_name")

    def test_multi_shot_handler_registered(self):
        """tops_multi_shot should be registered in the handler registry."""
        handler = SynapseHandler()
        assert handler._registry.has("tops_multi_shot")
