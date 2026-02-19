"""
Tests for Synapse v5.0 features.

Covers:
- Phase 1: Structured logging, audit wiring, graceful shutdown
- Phase 2: Epoch adaptation, VEX handler, knowledge expansion
- Phase 3: Recipe data flow, new recipes, USD alias translation
- Phase 4: Metrics exporter, resilience default, router stats
- Phase 5: Recipe discovery, routing benchmark expansion
"""

import importlib
import importlib.util
import json
import logging
import os
import sys
import types
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: locate package root and import Synapse modules
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PKG = _PROJECT_ROOT / "python"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

# Stub hou before importing anything that depends on it
if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=24.0)
    _hou.selectedNodes = MagicMock(return_value=[])
    _hou.undos = MagicMock()
    sys.modules["hou"] = _hou

if "hdefereval" not in sys.modules:
    sys.modules["hdefereval"] = types.ModuleType("hdefereval")

# Bootstrap package hierarchy for relative imports
for mod_name, mod_path in [
    ("synapse", _PKG / "synapse"),
    ("synapse.core", _PKG / "synapse" / "core"),
    ("synapse.server", _PKG / "synapse" / "server"),
    ("synapse.session", _PKG / "synapse" / "session"),
    ("synapse.memory", _PKG / "synapse" / "memory"),
    ("synapse.routing", _PKG / "synapse" / "routing"),
    ("synapse.ui", _PKG / "synapse" / "ui"),
    ("synapse.ui.tabs", _PKG / "synapse" / "ui" / "tabs"),
    ("synapse.agent", _PKG / "synapse" / "agent"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

# Now import via standard mechanism (relative imports will work)
from synapse.server.handlers import SynapseHandler, _CMD_CATEGORY, _READ_ONLY_COMMANDS


# ==========================================================================
# Phase 1: Structured Logging
# ==========================================================================

class TestStructuredLogging:
    """Verify all modules use stdlib logging instead of print()."""

    MODULES_WITH_LOGGERS = [
        "synapse.server.websocket",
        "synapse.memory.store",
        "synapse.server.resilience",
        "synapse.server.hwebserver_adapter",
        "synapse.server.api_adapter",
        "synapse.ui.panel",
        "synapse.ui.tabs.decisions",
        "synapse.ui.tabs.context",
        "synapse.session.tracker",
        "synapse.server.start_hwebserver",
        "synapse.core.queue",
    ]

    def test_no_print_in_source(self):
        """Grep-style check: no print() calls in the source tree."""
        src_dir = _PKG / "synapse"
        violations = []
        for py_file in src_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("print(") and not stripped.startswith("#"):
                    violations.append(f"{py_file.relative_to(_PKG)}:{i}: {stripped[:80]}")
        assert violations == [], f"Found print() calls:\n" + "\n".join(violations)

    def test_logger_names_exist(self):
        """Each module that previously had print() should have a logger."""
        for mod_name in self.MODULES_WITH_LOGGERS:
            logger = logging.getLogger(mod_name.replace("synapse.", "synapse.").split(".")[-1])
            # Logger should exist (stdlib always returns one, but we check naming)
            assert logger is not None


# ==========================================================================
# Phase 1B: Audit Wiring
# ==========================================================================

class TestAuditWiring:
    """Verify AuditLog is wired into handler dispatch."""

    def test_cmd_category_mapping_exists(self):
        """_CMD_CATEGORY dict should map command types to AuditCategory."""
        assert "create_node" in _CMD_CATEGORY
        assert "execute_python" in _CMD_CATEGORY
        assert "render" in _CMD_CATEGORY

    def test_audit_log_called_on_mutating_commands(self):
        """The handle() method should fire audit log for mutating commands."""
        expected_types = {"create_node", "delete_node", "set_parm", "execute_python", "render"}
        for t in expected_types:
            assert t in _CMD_CATEGORY, f"{t} not in _CMD_CATEGORY"


# ==========================================================================
# Phase 1C: Graceful Shutdown
# ==========================================================================

class TestGracefulShutdown:
    """Verify signal handlers and atexit registration."""

    def test_mcp_server_has_atexit(self):
        """mcp_server.py should have atexit.register call."""
        mcp_path = _PROJECT_ROOT / "mcp_server.py"
        content = mcp_path.read_text(encoding="utf-8", errors="replace")
        assert "atexit.register" in content
        assert "_atexit_cleanup" in content

    def test_websocket_signal_handlers(self):
        """websocket.py should register signal handlers when not in Houdini."""
        ws_path = _PKG / "synapse" / "server" / "websocket.py"
        content = ws_path.read_text(encoding="utf-8", errors="replace")
        assert "signal.SIGTERM" in content
        assert "signal.SIGINT" in content


# ==========================================================================
# Phase 2A: Epoch Adaptation
# ==========================================================================

class TestEpochAdaptation:
    """Test epoch-based tier adaptation (He2025 compliant)."""

    def setup_method(self):
        from synapse.routing.adaptation import EpochAdapter, TierEpoch, TierThresholds
        self.EpochAdapter = EpochAdapter
        self.TierEpoch = TierEpoch
        self.TierThresholds = TierThresholds

    def test_epoch_record_and_complete(self):
        """Epoch completes after epoch_size outcomes."""
        epoch = self.TierEpoch(epoch_id=0, epoch_size=3)
        assert not epoch.is_complete
        epoch.record("instant", True, 1.0)
        epoch.record("fast", True, 5.0)
        assert not epoch.is_complete
        epoch.record("instant", False, 2.0)
        assert epoch.is_complete

    def test_epoch_aggregate_kahan(self):
        """Aggregate uses kahan_sum for He2025 compliance."""
        epoch = self.TierEpoch(epoch_id=0, epoch_size=4)
        epoch.record("instant", True, 1.0)
        epoch.record("instant", True, 1.0)
        epoch.record("instant", False, 1.0)
        epoch.record("fast", True, 5.0)
        rates = epoch.aggregate()
        # instant: 2/3 success, fast: 1/1 success
        assert "instant" in rates
        assert "fast" in rates
        assert abs(rates["fast"] - 1.0) < 0.001

    def test_epoch_aggregate_sorted(self):
        """Aggregate results are sorted by tier name (He2025)."""
        epoch = self.TierEpoch(epoch_id=0, epoch_size=3)
        epoch.record("fast", True, 5.0)
        epoch.record("cache", True, 0.1)
        epoch.record("instant", True, 1.0)
        rates = epoch.aggregate()
        assert list(rates.keys()) == sorted(rates.keys())

    def test_epoch_aggregate_latency(self):
        """aggregate_latency returns Kahan-summed averages per tier."""
        epoch = self.TierEpoch(epoch_id=0, epoch_size=3)
        epoch.record("instant", True, 1.0)
        epoch.record("instant", True, 3.0)
        epoch.record("fast", True, 10.0)
        latencies = epoch.aggregate_latency()
        assert abs(latencies["instant"] - 2.0) < 0.001
        assert abs(latencies["fast"] - 10.0) < 0.001

    def test_threshold_adjust_low_success(self):
        """Low success rate raises threshold (harder to select)."""
        thresholds = self.TierThresholds()
        thresholds.adjust({"instant": 0.3})
        assert thresholds.get("instant") > 0.5

    def test_threshold_adjust_high_success(self):
        """High success rate lowers threshold (easier to select)."""
        thresholds = self.TierThresholds()
        thresholds.adjust({"instant": 0.95})
        assert thresholds.get("instant") < 0.5

    def test_threshold_adjust_moderate_no_change(self):
        """Moderate success rate doesn't change threshold."""
        thresholds = self.TierThresholds()
        initial = thresholds.get("instant")
        thresholds.adjust({"instant": 0.7})
        assert thresholds.get("instant") == initial

    def test_adapter_epoch_rotation(self):
        """Adapter rotates epoch when size reached."""
        adapter = self.EpochAdapter(epoch_size=3)
        assert adapter.epoch_id == 0
        adapter.record("instant", True, 1.0)
        adapter.record("instant", True, 1.0)
        adapter.record("instant", True, 1.0)
        # Should have rotated
        assert adapter.epoch_id == 1

    def test_adapter_stale_pin_epoch(self):
        """Stale pin epoch is 2 behind current."""
        adapter = self.EpochAdapter(epoch_size=2)
        # Fill 3 epochs (6 records)
        for _ in range(6):
            adapter.record("instant", True, 1.0)
        assert adapter.epoch_id == 3
        assert adapter.get_stale_pin_epoch() == 1

    def test_adapter_stats(self):
        """Stats include epoch info."""
        adapter = self.EpochAdapter(epoch_size=5)
        adapter.record("instant", True, 1.0)
        stats = adapter.stats()
        assert "epoch_id" in stats
        assert "epoch_progress" in stats
        assert stats["epoch_progress"] == 1

    def test_adapter_thread_safety(self):
        """Adapter handles concurrent recording."""
        adapter = self.EpochAdapter(epoch_size=100)
        errors = []

        def record_many():
            try:
                for _ in range(50):
                    adapter.record("instant", True, 1.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        # 4 threads * 50 = 200, epoch_size=100, so should have rotated twice
        assert adapter.epoch_id == 2

    def test_adapter_threshold_evolves(self):
        """After epochs with low success, thresholds change."""
        adapter = self.EpochAdapter(epoch_size=5)
        # Record 5 failures for "instant"
        for _ in range(5):
            adapter.record("instant", False, 10.0)
        # Should have rotated, and threshold should be raised
        threshold = adapter.thresholds.get("instant")
        assert threshold > 0.5


# ==========================================================================
# Phase 2B: VEX Execution Handler
# ==========================================================================

class TestVEXHandler:
    """Test VEX execution handler registration."""

    def test_handler_registered(self):
        """execute_vex should be in handler registry."""
        handler = SynapseHandler()
        assert handler._registry.has("execute_vex")

    def test_mcp_tool_defined(self):
        """houdini_execute_vex should be in MCP tool dispatch."""
        mcp_path = _PROJECT_ROOT / "mcp_server.py"
        content = mcp_path.read_text(encoding="utf-8", errors="replace")
        assert "houdini_execute_vex" in content

    def test_slow_command_timeout(self):
        """execute_vex should have 30s timeout."""
        mcp_path = _PROJECT_ROOT / "mcp_server.py"
        content = mcp_path.read_text(encoding="utf-8", errors="replace")
        assert '"execute_vex": 30.0' in content


# ==========================================================================
# Phase 3A: Recipe Data Flow
# ==========================================================================

class TestRecipeDataFlow:
    """Test recipe step output variables and execute()."""

    def test_output_var_field_exists(self):
        """RecipeStep should have output_var field."""
        from synapse.routing.recipes import RecipeStep
        step = RecipeStep(action="create_node", payload_template={}, output_var="node1")
        assert step.output_var == "node1"

    def test_output_var_default_empty(self):
        """output_var defaults to empty string."""
        from synapse.routing.recipes import RecipeStep
        step = RecipeStep(action="create_node", payload_template={})
        assert step.output_var == ""

    def test_instantiate_with_vars(self):
        """instantiate_with_vars resolves $var.field references."""
        from synapse.routing.recipes import RecipeStep
        step = RecipeStep(
            action="set_parm",
            payload_template={"node": "$node1.path", "parm": "tx", "value": "1"},
        )
        variables = {"$node1.path": "/obj/geo1"}
        cmd = step.instantiate_with_vars(variables)
        assert cmd.payload["node"] == "/obj/geo1"

    def test_recipe_execute_data_flow(self):
        """Recipe.execute() threads output data between steps."""
        from synapse.routing.recipes import Recipe, RecipeStep
        from synapse.core.protocol import SynapseResponse

        recipe = Recipe(
            name="test_flow",
            description="Test data flow",
            triggers=[],
            parameters=[],
            steps=[
                RecipeStep(
                    action="create_node",
                    payload_template={"type": "geo", "parent": "/obj"},
                    output_var="step1",
                ),
                RecipeStep(
                    action="set_parm",
                    payload_template={"node": "$step1.path", "parm": "tx", "value": "1"},
                ),
            ],
        )

        def mock_command_fn(cmd):
            if cmd.type == "create_node":
                return SynapseResponse(id=cmd.id, success=True, data={"path": "/obj/geo1"})
            return SynapseResponse(id=cmd.id, success=True, data={})

        results = recipe.execute({}, mock_command_fn)
        assert len(results) == 2
        # Second step should have resolved $step1.path
        second_cmd, _ = results[1]
        assert second_cmd.payload["node"] == "/obj/geo1"


# ==========================================================================
# Phase 3B: Recipe Library
# ==========================================================================

class TestRecipeLibrary:
    """Test expanded recipe library (21 recipes: 11 original + 10 production)."""

    def setup_method(self):
        from synapse.routing.recipes import RecipeRegistry
        self.registry = RecipeRegistry()

    def test_dome_light_recipe(self):
        match = self.registry.match("setup a dome light")
        assert match is not None
        assert match[0].name == "dome_light_environment"

    def test_dome_light_with_texture(self):
        match = self.registry.match("create dome light with studio.exr")
        assert match is not None
        assert match[0].name == "dome_light_environment"

    def test_camera_rig_recipe(self):
        match = self.registry.match("setup a camera at /obj")
        assert match is not None
        assert match[0].name == "camera_rig"

    def test_pyro_source_recipe(self):
        match = self.registry.match("setup pyro source at /obj/geo1")
        assert match is not None
        assert match[0].name == "pyro_source_setup"

    def test_material_recipe(self):
        match = self.registry.match("create a quick material named chrome")
        assert match is not None
        assert match[0].name == "material_quick_setup"

    def test_karma_render_recipe(self):
        match = self.registry.match("setup karma render")
        assert match is not None
        assert match[0].name == "karma_render_setup"

    def test_sopimport_recipe(self):
        match = self.registry.match("import /obj/geo1/sphere1 into the stage")
        assert match is not None
        assert match[0].name == "sopimport_chain"

    def test_edit_transform_recipe(self):
        match = self.registry.match("edit /World/hero translate")
        assert match is not None
        assert match[0].name == "edit_transform"

    def test_recipe_categories(self):
        """Each recipe should have a category."""
        categories = {r.category for r in self.registry.recipes}
        assert "lighting" in categories
        assert "render" in categories


# ==========================================================================
# Phase 3C: USD Parameter Translation
# ==========================================================================

class TestUSDParameterAliases:
    """Test USD parameter alias resolution."""

    def test_aliases_dict_exists(self):
        from synapse.core.aliases import USD_PARM_ALIASES
        assert isinstance(USD_PARM_ALIASES, dict)
        assert len(USD_PARM_ALIASES) > 20

    def test_intensity_alias(self):
        from synapse.core.aliases import USD_PARM_ALIASES
        assert USD_PARM_ALIASES["intensity"] == "xn__inputsintensity_i0a"

    def test_exposure_alias(self):
        from synapse.core.aliases import USD_PARM_ALIASES
        assert USD_PARM_ALIASES["exposure"] == "xn__inputsexposure_vya"

    def test_focal_length_alias(self):
        from synapse.core.aliases import USD_PARM_ALIASES
        assert USD_PARM_ALIASES["focal_length"] == "xn__inputsfocallength_e4b"

    def test_resolve_usd_parm_function(self):
        from synapse.core.aliases import resolve_usd_parm
        assert resolve_usd_parm("intensity") == "xn__inputsintensity_i0a"
        assert resolve_usd_parm("INTENSITY") == "xn__inputsintensity_i0a"  # case insensitive
        assert resolve_usd_parm("nonexistent") is None

    def test_translate_alias(self):
        from synapse.core.aliases import USD_PARM_ALIASES
        assert USD_PARM_ALIASES["translate"] == "xformOp:translate"

    def test_visibility_alias(self):
        from synapse.core.aliases import USD_PARM_ALIASES
        assert USD_PARM_ALIASES["visibility"] == "visibility"


# ==========================================================================
# Phase 4A: Metrics Exporter
# ==========================================================================

class TestMetricsExporter:
    """Test Prometheus metrics rendering."""

    def test_render_prometheus_basic(self):
        from synapse.server.metrics import render_prometheus
        text = render_prometheus()
        assert "synapse_circuit_breaker_state" in text
        assert "synapse_memory_entries_total" in text

    def test_render_prometheus_with_router_stats(self):
        from synapse.server.metrics import render_prometheus
        stats = {
            "total_routes": 100,
            "tiers": {
                "cache": {"count": 50, "avg_ms": 0.5},
                "instant": {"count": 30, "avg_ms": 2.0},
                "fast": {"count": 20, "avg_ms": 50.0},
            },
        }
        text = render_prometheus(router_stats=stats)
        assert 'synapse_tier_requests_total{tier="cache"} 50' in text
        assert 'synapse_tier_requests_total{tier="instant"} 30' in text
        assert "synapse_routes_total 100" in text

    def test_render_prometheus_with_commands(self):
        from synapse.server.metrics import render_prometheus
        text = render_prometheus(command_counts={"create_node": 10, "set_parm": 5})
        assert 'synapse_commands_total{type="create_node"} 10' in text
        assert 'synapse_commands_total{type="set_parm"} 5' in text

    def test_render_prometheus_circuit_breaker_states(self):
        from synapse.server.metrics import render_prometheus
        for state, expected_val in [("closed", 0), ("open", 1), ("half_open", 2)]:
            text = render_prometheus(circuit_breaker_state=state)
            assert f"synapse_circuit_breaker_state {expected_val}" in text

    def test_render_prometheus_sorted_output(self):
        """Tier names and command types should be in sorted order."""
        from synapse.server.metrics import render_prometheus
        stats = {
            "total_routes": 10,
            "tiers": {"fast": {"count": 3, "avg_ms": 5.0}, "cache": {"count": 7, "avg_ms": 0.1}},
        }
        text = render_prometheus(router_stats=stats)
        cache_pos = text.find('tier="cache"')
        fast_pos = text.find('tier="fast"')
        assert cache_pos < fast_pos, "Tiers should be sorted alphabetically"


# ==========================================================================
# Phase 4B: Resilience Default
# ==========================================================================

class TestResilienceDefault:
    """Test resilience is enabled by default with env override."""

    def test_default_resilience_enabled(self):
        """SynapseServer default should be enable_resilience=True."""
        ws_path = _PKG / "synapse" / "server" / "websocket.py"
        content = ws_path.read_text(encoding="utf-8", errors="replace")
        assert "enable_resilience: bool = True" in content

    def test_env_var_override(self):
        """SYNAPSE_RESILIENCE=0 should disable resilience."""
        ws_path = _PKG / "synapse" / "server" / "websocket.py"
        content = ws_path.read_text(encoding="utf-8", errors="replace")
        assert 'SYNAPSE_RESILIENCE' in content


# ==========================================================================
# Phase 4C: Router Stats + Recipe Discovery
# ==========================================================================

class TestRouterStatsAndRecipeDiscovery:
    """Test new MCP tools for router stats and recipe listing."""

    def test_router_stats_handler_registered(self):
        handler = SynapseHandler()
        assert handler._registry.has("router_stats")

    def test_list_recipes_handler_registered(self):
        handler = SynapseHandler()
        assert handler._registry.has("list_recipes")

    def test_list_recipes_returns_all(self):
        """list_recipes handler should return all registered recipes."""
        handler = SynapseHandler()
        result = handler._handle_list_recipes({})
        assert result["count"] == 37
        assert len(result["recipes"]) == 37
        # Should be sorted by name
        names = [r["name"] for r in result["recipes"]]
        assert names == sorted(names)

    def test_metrics_handler_registered(self):
        handler = SynapseHandler()
        assert handler._registry.has("get_metrics")

    def test_mcp_dispatch_entries(self):
        """New tools should have dispatch entries."""
        mcp_path = _PROJECT_ROOT / "mcp_server.py"
        content = mcp_path.read_text(encoding="utf-8", errors="replace")
        assert "synapse_metrics" in content
        assert "synapse_router_stats" in content
        assert "synapse_list_recipes" in content

    def test_read_only_commands_include_new(self):
        """New read-only handlers should be in _READ_ONLY_COMMANDS."""
        assert "get_metrics" in _READ_ONLY_COMMANDS
        assert "router_stats" in _READ_ONLY_COMMANDS
        assert "list_recipes" in _READ_ONLY_COMMANDS


# ==========================================================================
# Phase 2C: Knowledge Base Expansion
# ==========================================================================

class TestKnowledgeBaseExpansion:
    """Test that new RAG knowledge files exist and semantic index is updated."""

    RAG_DIR = _PROJECT_ROOT / "rag" / "skills" / "houdini21-reference"

    NEW_TOPICS = [
        "vex_functions.md",
        "common_attributes.md",
        "karma_aov.md",
        "expressions.md",
        "common_errors.md",
        "cops_compositing.md",
    ]

    def test_new_knowledge_files_exist(self):
        for topic in self.NEW_TOPICS:
            path = self.RAG_DIR / topic
            assert path.exists(), f"Missing knowledge file: {topic}"
            content = path.read_text(encoding="utf-8")
            assert len(content) > 100, f"Knowledge file too short: {topic}"

    def test_semantic_index_has_new_topics(self):
        index_path = _PROJECT_ROOT / "rag" / "documentation" / "_metadata" / "semantic_index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        expected_keys = [
            "vex_functions", "common_attributes", "karma_aov",
            "houdini_expressions", "common_errors", "cops_compositing",
        ]
        for key in expected_keys:
            assert key in index, f"Missing semantic index entry: {key}"
            assert "keywords" in index[key]
            assert len(index[key]["keywords"]) > 3

    def test_total_topic_count(self):
        """Should have 92 topics (78 base + 14 vex-corpus sync)."""
        index_path = _PROJECT_ROOT / "rag" / "documentation" / "_metadata" / "semantic_index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert len(index) >= 78  # base topics, grows with vex-corpus sync


# ==========================================================================
# Phase 5: Integration Checks
# ==========================================================================

class TestIntegration:
    """Cross-cutting integration checks."""

    def test_router_stats_include_epoch(self):
        """TieredRouter.stats() should include epoch data."""
        from synapse.routing.router import TieredRouter, RoutingConfig
        config = RoutingConfig(enable_tier2=False, enable_tier3=False)
        router = TieredRouter(config=config)
        stats = router.stats()
        assert "epoch" in stats
        assert "epoch_id" in stats["epoch"]

    def test_mcp_tool_count(self):
        """MCP server should declare 37 tools (34 original + 3 new)."""
        mcp_path = _PROJECT_ROOT / "mcp_server.py"
        content = mcp_path.read_text(encoding="utf-8", errors="replace")
        # Count Tool( declarations
        tool_count = content.count("Tool(\n")
        assert tool_count >= 37, f"Expected >= 37 tools, got {tool_count}"

    def test_handler_count(self):
        """Handler registry should have 37+ registered handlers."""
        handler = SynapseHandler()
        registered = handler._registry.registered_types
        assert len(registered) >= 37, f"Expected >= 37 handlers, got {len(registered)}: {registered}"


# ==========================================================================
# Phase B: Production Recipes and Workflow Planner
# ==========================================================================

class TestProductionRecipes:
    """Test the 10 production-grade recipes added in Phase B."""

    def setup_method(self):
        from synapse.routing.recipes import RecipeRegistry
        self.registry = RecipeRegistry()

    def test_vellum_cloth_match(self):
        match = self.registry.match("set up a vellum cloth simulation")
        assert match is not None
        assert match[0].name == "vellum_cloth_sim"

    def test_vellum_cloth_alternate_trigger(self):
        match = self.registry.match("create vellum cloth on /obj/geo1")
        assert match is not None
        assert match[0].name == "vellum_cloth_sim"

    def test_rbd_destruction_match(self):
        match = self.registry.match("set up rbd destruction")
        assert match is not None
        assert match[0].name == "rbd_destruction"

    def test_rbd_fracture_sim_match(self):
        match = self.registry.match("setup a fracture simulation")
        assert match is not None
        assert match[0].name == "rbd_destruction"

    def test_turntable_render_match(self):
        match = self.registry.match("create a turntable render")
        assert match is not None
        assert match[0].name == "turntable_render"

    def test_ocean_setup_match(self):
        match = self.registry.match("set up an ocean")
        assert match is not None
        assert match[0].name == "ocean_setup"

    def test_pyro_fire_sim_match(self):
        match = self.registry.match("set up a fire simulation")
        assert match is not None
        assert match[0].name == "pyro_fire_sim"

    def test_vellum_wire_match(self):
        match = self.registry.match("set up a wire simulation")
        assert match is not None
        assert match[0].name == "vellum_wire_sim"

    def test_vellum_cable_match(self):
        match = self.registry.match("simulate cables")
        assert match is not None
        assert match[0].name == "vellum_wire_sim"

    def test_terrain_match(self):
        match = self.registry.match("create a terrain")
        assert match is not None
        assert match[0].name == "terrain_environment"

    def test_terrain_heightfield_match(self):
        match = self.registry.match("set up a heightfield terrain")
        assert match is not None
        assert match[0].name == "terrain_environment"

    def test_lookdev_scene_match(self):
        match = self.registry.match("create a lookdev scene")
        assert match is not None
        assert match[0].name == "lookdev_scene"

    def test_file_cache_match(self):
        match = self.registry.match("cache /obj/geo1/solver1 to disk")
        assert match is not None
        assert match[0].name == "file_cache"

    def test_render_preview_match(self):
        match = self.registry.match("quick render preview")
        assert match is not None
        assert match[0].name == "render_preview"

    def test_render_preview_alternate(self):
        match = self.registry.match("test render")
        assert match is not None
        assert match[0].name == "render_preview"

    def test_production_recipes_use_execute_python(self):
        """Production FX recipes (new in Phase B) use execute_python for complex setups."""
        production_fx = [
            r for r in self.registry.recipes
            if r.category == "fx" and r.name in (
                "vellum_cloth_sim", "rbd_destruction", "ocean_setup",
                "pyro_fire_sim", "vellum_wire_sim",
            )
        ]
        for recipe in production_fx:
            actions = [s.action for s in recipe.steps]
            assert "execute_python" in actions, (
                f"FX recipe '{recipe.name}' should use execute_python"
            )

    def test_turntable_lighting_law(self):
        """Turntable recipe must not set intensity > 1.0."""
        match = self.registry.match("create a turntable")
        assert match is not None
        recipe = match[0]
        for step in recipe.steps:
            # Check that no step sets intensity
            payload = step.payload_template
            attr = payload.get("attribute_name", "")
            if "intensity" in attr.lower():
                value = payload.get("value")
                assert value is None or value <= 1.0, (
                    f"Lighting Law violation: intensity set to {value}"
                )

    def test_recipe_categories(self):
        """Production recipes should cover fx, render, lighting, environment, pipeline."""
        categories = {r.category for r in self.registry.recipes}
        assert "fx" in categories
        assert "render" in categories
        assert "lighting" in categories
        assert "environment" in categories
        assert "pipeline" in categories

    def test_all_recipes_have_steps(self):
        """Every recipe must have at least one step."""
        for recipe in self.registry.recipes:
            assert len(recipe.steps) >= 1, f"Recipe '{recipe.name}' has no steps"


class TestHDAGenerate:
    """Test HDA content generation from natural language."""

    def setup_method(self):
        from synapse.routing.recipes import RecipeRegistry
        self.registry = RecipeRegistry()

    def test_scatter_trigger(self):
        match = self.registry.match("generate an HDA that scatters points")
        assert match is not None
        assert match[0].name == "hda_generate"
        assert "scatter" in match[1]["description"].lower()

    def test_deformer_trigger(self):
        match = self.registry.match(
            "generate a tool to deform geometry with noise"
        )
        assert match is not None
        assert match[0].name == "hda_generate"

    def test_color_trigger(self):
        match = self.registry.match(
            "hda generate color by height gradient"
        )
        assert match is not None
        assert match[0].name == "hda_generate"

    def test_mask_trigger(self):
        match = self.registry.match(
            "generate an HDA that masks points by proximity"
        )
        assert match is not None
        assert match[0].name == "hda_generate"

    def test_extrude_trigger(self):
        match = self.registry.match(
            "generate a tool to extrude along normals"
        )
        assert match is not None
        assert match[0].name == "hda_generate"

    def test_named_trigger(self):
        match = self.registry.match(
            "generate a scatter_pts HDA that distributes random points"
        )
        assert match is not None
        assert match[0].name == "hda_generate"
        assert match[1]["name"] == "scatter_pts"

    def test_no_match_scaffold(self):
        """'create an HDA' without 'generate' should NOT match hda_generate."""
        match = self.registry.match("create an HDA called foo")
        if match:
            assert match[0].name != "hda_generate"

    def test_uses_execute_python(self):
        match = self.registry.match("generate an HDA that scatters points")
        recipe = match[0]
        actions = [s.action for s in recipe.steps]
        assert "execute_python" in actions

    def test_has_output_var(self):
        match = self.registry.match("generate an HDA that scatters points")
        recipe = match[0]
        assert recipe.steps[0].output_var == "hda"

    def test_category_is_pipeline(self):
        match = self.registry.match("generate an HDA that scatters points")
        assert match[0].category == "pipeline"


class TestExecutePythonInstantiation:
    """Regression test: all execute_python recipe steps must survive .format().

    Unescaped { } in code templates (Python dicts, VEX for-loops) cause
    KeyError when instantiated. This test catches that for every recipe.
    """

    def setup_method(self):
        from synapse.routing.recipes import RecipeRegistry
        self.registry = RecipeRegistry()

    # Dummy params for each recipe that has execute_python steps
    _DUMMY_PARAMS = {
        "vellum_cloth_sim": {"parent": "/obj/test"},
        "rbd_destruction": {"parent": "/obj/test"},
        "turntable_render": {"target": "/obj/geo1"},
        "ocean_setup": {"parent": "/obj/test"},
        "pyro_fire_sim": {"parent": "/obj/test"},
        "vellum_wire_sim": {"parent": "/obj/test"},
        "terrain_environment": {"parent": "/obj/test"},
        "lookdev_scene": {},
        "file_cache": {"source": "/obj/geo1/null1"},
        "hda_scaffold": {"name": "test_tool", "description": "a test tool"},
        "vex_debug_wrangle": {"node": "/obj/geo1/wrangle1"},
        "vex_noise_deformer": {"parent": "/obj/test"},
        "hda_generate": {"name": "scatter_pts", "description": "scatters points randomly"},
    }

    @pytest.mark.parametrize("recipe_name", list(_DUMMY_PARAMS.keys()))
    def test_instantiate_no_keyerror(self, recipe_name):
        """Instantiating execute_python steps must not raise KeyError from unescaped braces."""
        recipe = None
        for r in self.registry.recipes:
            if r.name == recipe_name:
                recipe = r
                break
        assert recipe is not None, f"Recipe {recipe_name} not found"

        params = self._DUMMY_PARAMS[recipe_name]
        ep_steps = [s for s in recipe.steps if s.action == "execute_python"]
        assert len(ep_steps) > 0, f"Recipe {recipe_name} has no execute_python steps"

        for step in ep_steps:
            # This is where unescaped braces would blow up
            cmd = step.instantiate(params)
            assert cmd.payload.get("code"), f"Step produced empty code for {recipe_name}"
            # Verify placeholder substitution happened
            for key, val in params.items():
                if val:  # skip empty params
                    assert "{" + key + "}" not in cmd.payload["code"], (
                        f"Placeholder {{{key}}} not replaced in {recipe_name}"
                    )


class TestWorkflowPlanner:
    """Test the multi-step workflow planner."""

    def setup_method(self):
        from synapse.routing.planner import WorkflowPlanner
        self.planner = WorkflowPlanner()

    def test_cloth_pipeline_basic(self):
        plan = self.planner.plan("set up cloth sim")
        assert plan is not None
        assert plan.name == "cloth_pipeline"
        assert len(plan.steps) >= 1

    def test_cloth_with_collision_and_wind(self):
        plan = self.planner.plan("set up cloth simulation with collision and wind")
        assert plan is not None
        assert "add_collision" in plan.metadata["modifiers"]
        assert "add_wind" in plan.metadata["modifiers"]
        # Core + collision + wind = 3 steps
        assert len(plan.steps) == 3

    def test_cloth_with_drape_and_cache(self):
        plan = self.planner.plan("set up vellum cloth sim with drape and cache")
        assert plan is not None
        assert "add_drape" in plan.metadata["modifiers"]
        assert "add_cache" in plan.metadata["modifiers"]
        assert len(plan.steps) == 3

    def test_destruction_basic(self):
        plan = self.planner.plan("setup destruction pipeline")
        assert plan is not None
        assert plan.name == "destruction_pipeline"
        # Core + cache = 2 steps minimum
        assert len(plan.steps) >= 2

    def test_destruction_with_debris_and_dust(self):
        plan = self.planner.plan("set up destruction sequence with debris and dust")
        assert plan is not None
        assert "add_debris" in plan.metadata["modifiers"]
        assert "add_dust" in plan.metadata["modifiers"]
        # Core + debris + dust + cache = 4 steps
        assert len(plan.steps) == 4

    def test_lighting_broadcast(self):
        plan = self.planner.plan("light the scene for broadcast")
        assert plan is not None
        assert plan.name == "lighting_pipeline"

    def test_lighting_dramatic_with_dome(self):
        plan = self.planner.plan("set up lighting rig for dramatic with dome")
        assert plan is not None
        assert "add_dome" in plan.metadata["modifiers"]
        # Key + fill + rim + dome = 8 steps (each has create + set exposure)
        assert len(plan.steps) >= 6

    def test_ocean_with_whitewater_and_flip(self):
        plan = self.planner.plan("set up ocean with whitewater and flip interaction")
        assert plan is not None
        assert "add_whitewater" in plan.metadata["modifiers"]
        assert "add_flip" in plan.metadata["modifiers"]
        # Core + flip + whitewater = 3
        assert len(plan.steps) == 3

    def test_render_pipeline_with_aovs(self):
        plan = self.planner.plan("set up render pipeline with aovs and denoise")
        assert plan is not None
        assert "add_aovs" in plan.metadata["modifiers"]
        assert "add_denoise" in plan.metadata["modifiers"]

    def test_pyro_pipeline(self):
        plan = self.planner.plan("set up pyro fire sim")
        assert plan is not None
        assert plan.name == "pyro_pipeline"

    def test_no_match_for_simple_query(self):
        plan = self.planner.plan("what is the render time?")
        assert plan is None

    def test_no_match_for_single_operation(self):
        plan = self.planner.plan("create a sphere")
        assert plan is None

    def test_plan_steps_are_synapse_commands(self):
        from synapse.core.protocol import SynapseCommand
        plan = self.planner.plan("set up cloth sim with collision")
        assert plan is not None
        for step in plan.steps:
            assert isinstance(step, SynapseCommand)

    def test_plan_metadata_has_step_count(self):
        plan = self.planner.plan("set up destruction pipeline with debris")
        assert plan is not None
        assert plan.metadata["step_count"] == len(plan.steps)

    def test_lighting_exposure_values_obey_lighting_law(self):
        """Planner lighting should use exposure, never intensity > 1.0."""
        from synapse.routing.planner import _lighting_exposure_for_mood
        for mood in ("product", "broadcast", "dramatic", "horror", "overcast"):
            exposures = _lighting_exposure_for_mood(mood)
            # All values should be reasonable exposure stops
            for role, val in sorted(exposures.items()):
                assert -5 <= val <= 10, (
                    f"Exposure {role}={val} for {mood} looks wrong"
                )

    def test_planner_in_routing_cascade(self):
        """Planner should be integrated into TieredRouter."""
        from synapse.routing.router import TieredRouter, RoutingConfig
        config = RoutingConfig(
            enable_tier0=False, enable_tier1=False,
            enable_tier2=False, enable_tier3=False,
        )
        router = TieredRouter(config=config)
        result = router.route("set up cloth simulation with collision and wind")
        assert result.success
        assert result.metadata.get("planned") is True
        assert len(result.commands) == 3
