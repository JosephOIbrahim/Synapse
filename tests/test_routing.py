"""
Synapse Tiered Routing Tests

Tests for the routing cascade: parser (Tier 0), knowledge (Tier 1),
recipes, response cache (He2025), and the TieredRouter orchestrator.

Run without Houdini or API key:
    python -m pytest tests/test_routing.py -v
"""

import sys
import os
import json
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.core.protocol import SynapseCommand, SynapseResponse
from synapse.core.gates import GateLevel

from synapse.routing.parser import CommandParser, ParseResult
from synapse.routing.knowledge import KnowledgeIndex, KnowledgeLookupResult
from synapse.routing.recipes import Recipe, RecipeStep, RecipeRegistry
from synapse.routing.cache import ResponseCache
from synapse.routing.router import (
    TieredRouter,
    RoutingResult,
    RoutingTier,
    RoutingConfig,
)
from synapse.core.audit import AuditCategory


# =============================================================================
# HELPERS
# =============================================================================

def _make_rag_dir(tmp_dir):
    """Create a minimal RAG directory structure for testing."""
    meta_dir = os.path.join(tmp_dir, "documentation", "_metadata")
    os.makedirs(meta_dir, exist_ok=True)

    # Semantic index
    index = {
        "three_point_lighting": {
            "summary": "Three-point lighting consists of key, fill, and rim lights.",
            "description": "Standard lighting setup used in photography and VFX.",
            "keywords": ["lighting", "three-point", "key", "fill", "rim"],
        },
        "scatter_points": {
            "summary": "Scattering distributes points across a surface.",
            "description": "Use the scatter SOP to distribute points on geometry.",
            "keywords": ["scatter", "points", "distribute", "surface"],
        },
        "karma_rendering": {
            "summary": "Karma is SideFX's production renderer.",
            "description": "Karma supports both XPU and CPU rendering modes.",
            "keywords": ["karma", "render", "xpu", "cpu", "renderer"],
        },
        "compositing_fundamentals": {
            "summary": "COPs is Houdini's node-based image compositing system.",
            "description": "Copernicus replaces legacy COPs with GPU-accelerated compositing.",
            "keywords": ["compositing", "cops", "copernicus", "image", "color", "blur"],
            "reference_file": "compositing",
        },
    }
    with open(os.path.join(meta_dir, "semantic_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f)

    # Agent relevance map
    relevance = {
        "three_point_lighting": "lighting_agent",
        "scatter_points": "geometry_agent",
        "compositing_fundamentals": "compositing_agent",
    }
    with open(os.path.join(meta_dir, "agent_relevance_map.json"), "w", encoding="utf-8") as f:
        json.dump(relevance, f)

    # Reference files
    ref_dir = os.path.join(tmp_dir, "skills", "houdini21-reference")
    os.makedirs(ref_dir, exist_ok=True)

    with open(os.path.join(ref_dir, "lighting.md"), "w", encoding="utf-8") as f:
        f.write("# Lighting in Houdini\n\nHoudini supports area, point, and dome lights.\n\n## Three-Point Setup\n\nA classic approach using key, fill, and rim.\n")

    with open(os.path.join(ref_dir, "rendering.md"), "w", encoding="utf-8") as f:
        f.write("# Rendering with Karma\n\nKarma is the default production renderer.\n\n## XPU Mode\n\nUses GPU acceleration for interactive previews.\n")

    with open(os.path.join(ref_dir, "compositing.md"), "w", encoding="utf-8") as f:
        f.write(
            "# Compositing with COPs\n\n"
            "COPs (Compositing Operations) is Houdini's node-based image compositing system.\n"
            "In Houdini 21, Copernicus replaces legacy COPs with a GPU-accelerated framework.\n\n"
            "## Key Concepts\n\n"
            "- Images flow through nodes as multi-plane data (color, alpha, depth, id)\n"
            "- Resolution is controlled per-network via Compositor Options\n\n"
            "## Common Nodes\n\n"
            "- **color_correct** - Hue, saturation, value adjustment\n"
            "- **grade** - Lift/gamma/gain color grading\n"
            "- **blur** - Gaussian, box, or custom kernel blur\n"
            "- **merge/composite** - Layer compositing (over, add, multiply)\n"
        )

    return tmp_dir


def _mock_command_fn(cmd):
    """Mock command_fn that returns success for any command."""
    return SynapseResponse(id=cmd.id, success=True, data={"mock": True})


# =============================================================================
# TEST: CommandParser (Tier 0)
# =============================================================================

class TestCommandParser:
    """Tests for regex-based command parsing."""

    def setup_method(self):
        self.parser = CommandParser()

    # --- Utility commands ---

    def test_ping(self):
        result = self.parser.parse("ping")
        assert result.matched
        assert result.command.type == "ping"
        assert result.confidence == 1.0
        assert result.pattern_name == "ping"

    def test_status(self):
        result = self.parser.parse("status")
        assert result.matched
        assert result.command.type == "ping"

    def test_health(self):
        result = self.parser.parse("health")
        assert result.matched
        assert result.command.type == "ping"

    def test_help(self):
        result = self.parser.parse("help")
        assert result.matched
        assert result.command.type == "get_help"
        assert result.confidence == 0.95

    def test_what_can_you_do(self):
        result = self.parser.parse("what can you do")
        assert result.matched
        assert result.command.type == "get_help"

    # --- Scene queries ---

    def test_get_selection(self):
        result = self.parser.parse("what's selected")
        assert result.matched
        assert result.command.type == "get_selection"
        assert result.confidence == 0.95

    def test_get_selection_alt(self):
        result = self.parser.parse("selected nodes")
        assert result.matched
        assert result.command.type == "get_selection"

    def test_scene_info(self):
        result = self.parser.parse("scene info")
        assert result.matched
        assert result.command.type == "get_scene_info"

    def test_stage_info(self):
        result = self.parser.parse("stage info")
        assert result.matched
        assert result.command.type == "get_stage_info"

    # --- Node creation ---

    def test_create_node(self):
        result = self.parser.parse("create a hlight at /obj")
        assert result.matched
        assert result.command.type == "create_node"
        assert result.command.payload["type"] == "hlight"
        assert result.command.payload["parent"] == "/obj"
        assert result.confidence == 0.9

    def test_create_node_named(self):
        result = self.parser.parse("create hlight called key_light at /obj")
        assert result.matched
        assert result.command.type == "create_node"
        assert result.command.payload["type"] == "hlight"
        assert result.command.payload["name"] == "key_light"
        assert result.command.payload["parent"] == "/obj"
        assert result.confidence == 0.95

    def test_create_new_node(self):
        result = self.parser.parse("create a new geo in /obj")
        assert result.matched
        assert result.command.type == "create_node"
        assert result.command.payload["type"] == "geo"

    # --- Parameter operations ---

    def test_set_parm(self):
        result = self.parser.parse("set intensity on /obj/key to 1.5")
        assert result.matched
        assert result.command.type == "set_parm"
        assert result.command.payload["parm"] == "intensity"
        assert result.command.payload["node"] == "/obj/key"
        assert result.command.payload["value"] == 1.5

    def test_set_parm_int(self):
        result = self.parser.parse("set divisions on /obj/geo1 to 10")
        assert result.matched
        assert result.command.payload["value"] == 10
        assert isinstance(result.command.payload["value"], int)

    def test_set_parm_string(self):
        result = self.parser.parse("set file on /obj/geo1 to test.bgeo")
        assert result.matched
        assert result.command.payload["value"] == "test.bgeo"

    def test_get_parm(self):
        result = self.parser.parse("get intensity from /obj/key")
        assert result.matched
        assert result.command.type == "get_parm"
        assert result.command.payload["parm"] == "intensity"
        assert result.command.payload["node"] == "/obj/key"

    def test_get_parm_whats(self):
        result = self.parser.parse("what's intensity on /obj/key?")
        assert result.matched
        assert result.command.type == "get_parm"

    # --- Connections ---

    def test_connect(self):
        result = self.parser.parse("connect /obj/a to /obj/b")
        assert result.matched
        assert result.command.type == "connect_nodes"
        assert result.command.payload["source"] == "/obj/a"
        assert result.command.payload["target"] == "/obj/b"

    # --- Deletion ---

    def test_delete(self):
        result = self.parser.parse("delete /obj/old_node")
        assert result.matched
        assert result.command.type == "delete_node"
        assert result.command.payload["node"] == "/obj/old_node"

    def test_remove(self):
        result = self.parser.parse("remove /obj/old_node")
        assert result.matched
        assert result.command.type == "delete_node"

    # --- Edge cases ---

    def test_empty_input(self):
        result = self.parser.parse("")
        assert not result.matched

    def test_whitespace_only(self):
        result = self.parser.parse("   ")
        assert not result.matched

    def test_unrecognized_input(self):
        result = self.parser.parse("tell me about the meaning of life")
        assert not result.matched
        assert result.confidence == 0.0

    def test_case_insensitive(self):
        result = self.parser.parse("CREATE a hlight AT /obj")
        assert result.matched
        assert result.command.type == "create_node"

    def test_path_with_dash(self):
        result = self.parser.parse("delete /obj/scatter-1")
        assert result.matched
        assert result.command.payload["node"] == "/obj/scatter-1"

    def test_command_has_id(self):
        result = self.parser.parse("ping")
        assert result.command.id  # Non-empty UUID

    def test_set_parm_with_parm_keyword(self):
        result = self.parser.parse("set parm intensity on /obj/key to 1.5")
        assert result.matched
        assert result.command.type == "set_parm"
        assert result.command.payload["parm"] == "intensity"

    # --- Compositing (COPs) ---

    def test_composite_over(self):
        result = self.parser.parse("composite /img/fg over /img/bg")
        assert result.matched
        assert result.command.type == "connect_nodes"
        assert result.command.payload["source"] == "/img/fg"
        assert result.command.payload["target"] == "/img/bg"
        assert result.command.payload["domain"] == "compositing"
        assert result.confidence == 0.9

    def test_apply_cop_filter_blur(self):
        result = self.parser.parse("apply blur to /img/render1")
        assert result.matched
        assert result.command.type == "create_node"
        assert result.command.payload["type"] == "blur"
        assert result.command.payload["parent"] == "/img/render1"
        assert result.command.payload["domain"] == "compositing"

    def test_apply_cop_filter_shorthand(self):
        result = self.parser.parse("blur /img/render1")
        assert result.matched
        assert result.command.type == "create_node"
        assert result.command.payload["type"] == "blur"
        assert result.command.payload["parent"] == "/img/render1"

    def test_apply_cop_filter_color_correct(self):
        result = self.parser.parse("apply color_correct to /img/render1")
        assert result.matched
        assert result.command.type == "create_node"
        assert result.command.payload["type"] == "colorcorrect"


# =============================================================================
# TEST: KnowledgeIndex (Tier 1)
# =============================================================================

class TestKnowledgeIndex:
    """Tests for in-memory knowledge lookup."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        _make_rag_dir(self.tmp_dir)

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_init_with_rag(self):
        index = KnowledgeIndex(rag_root=self.tmp_dir)
        assert index.topic_count == 4
        assert index.reference_count == 3

    def test_init_without_rag(self):
        index = KnowledgeIndex()
        assert index.topic_count == 0
        assert index.reference_count == 0

    def test_keyword_match(self):
        index = KnowledgeIndex(rag_root=self.tmp_dir)
        result = index.lookup("three-point lighting setup")
        assert result.found
        assert result.topic == "three_point_lighting"
        assert result.confidence > 0.4
        assert "key" in result.answer.lower() or "three-point" in result.answer.lower()

    def test_keyword_match_scatter(self):
        index = KnowledgeIndex(rag_root=self.tmp_dir)
        result = index.lookup("scatter points on surface")
        assert result.found
        assert result.topic == "scatter_points"

    def test_karma_lookup(self):
        index = KnowledgeIndex(rag_root=self.tmp_dir)
        result = index.lookup("karma rendering xpu")
        assert result.found
        assert result.topic == "karma_rendering"

    def test_no_match(self):
        index = KnowledgeIndex(rag_root=self.tmp_dir)
        result = index.lookup("quantum physics entanglement")
        assert not result.found

    def test_empty_query(self):
        index = KnowledgeIndex(rag_root=self.tmp_dir)
        result = index.lookup("")
        assert not result.found

    def test_reference_section_match(self):
        index = KnowledgeIndex(rag_root=self.tmp_dir)
        # "xpu mode" should match the section header in rendering.md
        result = index.lookup("xpu mode")
        assert result.found

    def test_memory_fallback(self):
        mock_memory = Mock()
        mock_result = Mock()
        mock_result.score = 0.7
        mock_result.memory = Mock()
        mock_result.memory.id = "mem-123"
        mock_result.memory.content = "Use Karma XPU for fast previews"
        mock_result.memory.summary = "Karma XPU tip"
        mock_memory.search.return_value = [mock_result]

        # No RAG, memory-only
        index = KnowledgeIndex(memory=mock_memory)
        result = index.lookup("karma xpu fast preview")
        assert result.found
        assert "Karma XPU" in result.answer

    def test_memory_fallback_low_score(self):
        mock_memory = Mock()
        mock_result = Mock()
        mock_result.score = 0.1
        mock_result.memory = Mock()
        mock_result.memory.id = "mem-456"
        mock_result.memory.content = "unrelated"
        mock_result.memory.summary = ""
        mock_memory.search.return_value = [mock_result]

        index = KnowledgeIndex(memory=mock_memory)
        result = index.lookup("something totally unrelated")
        assert not result.found

    def test_graceful_degradation_no_rag_no_memory(self):
        index = KnowledgeIndex()
        result = index.lookup("anything")
        assert not result.found

    def test_stats(self):
        index = KnowledgeIndex(rag_root=self.tmp_dir)
        s = index.stats()
        assert s["topics"] == 4
        assert s["references"] == 3
        assert s["has_rag"]
        assert not s["has_memory"]

    def test_agent_hint_returned(self):
        index = KnowledgeIndex(rag_root=self.tmp_dir)
        result = index.lookup("three-point lighting")
        assert result.found
        assert result.agent_hint == "lighting_agent"

    def test_compositing_knowledge_lookup(self):
        index = KnowledgeIndex(rag_root=self.tmp_dir)
        result = index.lookup("cops compositing")
        assert result.found
        assert result.topic == "compositing_fundamentals"
        assert result.agent_hint == "compositing_agent"


# =============================================================================
# TEST: RecipeRegistry
# =============================================================================

class TestRecipeRegistry:
    """Tests for pre-built recipe templates."""

    def setup_method(self):
        self.registry = RecipeRegistry()

    def test_builtin_recipes_registered(self):
        assert len(self.registry.recipes) == 42

    def test_three_point_lighting_match(self):
        match = self.registry.match("set up three-point lighting at /obj")
        assert match is not None
        recipe, params = match
        assert recipe.name == "three_point_lighting"
        assert params["parent"] == "/obj"

    def test_three_point_lighting_steps(self):
        match = self.registry.match("setup three point lighting at /stage")
        recipe, params = match
        commands = recipe.instantiate(params)
        assert len(commands) == 6  # 3 creates + 3 set_parm
        assert commands[0].type == "create_node"
        assert commands[0].payload["name"] == "key_light"
        assert commands[0].payload["parent"] == "/stage"
        assert commands[1].type == "set_parm"
        assert commands[1].payload["parm"] == "light_exposure"
        assert commands[1].payload["value"] == 4

    def test_scatter_match(self):
        match = self.registry.match("scatter /obj/rocks onto /obj/terrain")
        assert match is not None
        recipe, params = match
        assert recipe.name == "scatter_copy"
        assert params["source"] == "/obj/rocks"
        assert params["target"] == "/obj/terrain"

    def test_scatter_steps(self):
        match = self.registry.match("scatter /obj/rocks over /obj/ground")
        recipe, params = match
        commands = recipe.instantiate(params)
        assert len(commands) == 3
        assert commands[0].type == "create_node"
        assert commands[2].type == "connect_nodes"

    def test_null_controller_match(self):
        match = self.registry.match("create a controller at /obj")
        assert match is not None
        recipe, params = match
        assert recipe.name == "null_controller"
        assert params["parent"] == "/obj"

    def test_null_controller_steps(self):
        match = self.registry.match("create controller at /obj")
        recipe, params = match
        commands = recipe.instantiate(params)
        assert len(commands) == 2
        assert commands[0].payload["type"] == "null"

    def test_no_match(self):
        match = self.registry.match("tell me a joke")
        assert match is None

    def test_custom_recipe_registration(self):
        custom = Recipe(
            name="test_recipe",
            description="Test recipe",
            triggers=[r"^run test$"],
            parameters=[],
            steps=[
                RecipeStep(
                    action="ping",
                    payload_template={},
                ),
            ],
        )
        self.registry.register(custom)
        assert len(self.registry.recipes) == 43
        match = self.registry.match("run test")
        assert match is not None
        assert match[0].name == "test_recipe"

    def test_case_insensitive_match(self):
        match = self.registry.match("SET UP Three-Point Lighting at /obj")
        assert match is not None

    def test_three_point_no_parent(self):
        """Match three-point lighting without specifying parent."""
        match = self.registry.match("set up three-point lighting")
        assert match is not None
        recipe, params = match
        assert params["parent"] == ""

    # --- Color Correction (COPs) ---

    def test_color_correction_match(self):
        match = self.registry.match("set up color correction at /img")
        assert match is not None
        recipe, params = match
        assert recipe.name == "color_correction_setup"
        assert params["parent"] == "/img"

    def test_color_correction_steps(self):
        match = self.registry.match("setup color correction at /img")
        recipe, params = match
        commands = recipe.instantiate(params)
        assert len(commands) == 4
        assert commands[0].type == "create_node"
        assert commands[0].payload["type"] == "colorcorrect"
        assert commands[1].type == "set_parm"
        assert commands[1].payload["parm"] == "saturation"
        assert commands[2].type == "create_node"
        assert commands[2].payload["type"] == "grade"
        assert commands[3].type == "connect_nodes"
        assert commands[3].payload["source"] == "/img/color_correct1"
        assert commands[3].payload["target"] == "/img/grade1"

    def test_color_correction_no_parent(self):
        match = self.registry.match("set up color correction")
        assert match is not None
        recipe, params = match
        assert params["parent"] == ""


# =============================================================================
# TEST: AuditCategory (COPs)
# =============================================================================

class TestAuditCategory:
    """Tests for audit category additions."""

    def test_compositing_category_exists(self):
        assert AuditCategory.COMPOSITING.value == "compositing"


# =============================================================================
# TEST: ResponseCache (He2025)
# =============================================================================

class TestResponseCache:
    """Tests for deterministic response caching."""

    def setup_method(self):
        self.cache = ResponseCache(max_size=10, ttl_seconds=3600)

    def test_put_and_get(self):
        result = RoutingResult(
            success=True, tier=RoutingTier.FAST, answer="test"
        )
        self.cache.put("fast", "hello", "ctx1", result)
        cached = self.cache.get("fast", "hello", "ctx1")
        assert cached is not None
        assert cached.answer == "test"

    def test_miss(self):
        cached = self.cache.get("fast", "nonexistent", "ctx1")
        assert cached is None

    def test_canonicalization(self):
        """Same text with different whitespace/case → same cache entry."""
        result = RoutingResult(
            success=True, tier=RoutingTier.FAST, answer="canonical"
        )
        self.cache.put("fast", "  Hello World  ", "ctx1", result)
        cached = self.cache.get("fast", "hello world", "ctx1")
        assert cached is not None
        assert cached.answer == "canonical"

    def test_different_context_hash(self):
        result = RoutingResult(
            success=True, tier=RoutingTier.FAST, answer="test"
        )
        self.cache.put("fast", "hello", "ctx1", result)
        cached = self.cache.get("fast", "hello", "ctx2")
        assert cached is None  # Different context → miss

    def test_ttl_expiry(self):
        cache = ResponseCache(max_size=10, ttl_seconds=1)
        result = RoutingResult(
            success=True, tier=RoutingTier.FAST, answer="temporary"
        )
        cache.put("fast", "hello", "", result, ttl=1)
        # Should be available immediately
        assert cache.get("fast", "hello", "") is not None
        # Wait for expiry
        time.sleep(1.1)
        assert cache.get("fast", "hello", "") is None

    def test_no_cache_for_instant_tier(self):
        """Tier 0 (instant) should not be cached (TTL=0)."""
        result = RoutingResult(
            success=True, tier=RoutingTier.INSTANT, answer="fast"
        )
        self.cache.put("instant", "ping", "", result)
        cached = self.cache.get("instant", "ping", "")
        assert cached is None  # TTL 0 = don't cache

    def test_invalidate_all(self):
        result = RoutingResult(
            success=True, tier=RoutingTier.FAST, answer="test"
        )
        self.cache.put("fast", "a", "", result)
        self.cache.put("fast", "b", "", result)
        assert self.cache.stats()["size"] == 2
        self.cache.invalidate()
        assert self.cache.stats()["size"] == 0

    def test_max_size_eviction(self):
        for i in range(15):
            result = RoutingResult(
                success=True, tier=RoutingTier.FAST, answer=f"item{i}"
            )
            self.cache.put("fast", f"query{i}", "", result)
        assert self.cache.stats()["size"] <= 10
        assert self.cache.stats()["evictions"] > 0

    def test_stats(self):
        result = RoutingResult(
            success=True, tier=RoutingTier.FAST, answer="test"
        )
        self.cache.put("fast", "q1", "", result)
        self.cache.get("fast", "q1", "")  # hit
        self.cache.get("fast", "q2", "")  # miss
        s = self.cache.stats()
        assert s["hits"] == 1
        assert s["misses"] == 1
        assert s["hit_rate"] == 0.5


# =============================================================================
# TEST: TieredRouter
# =============================================================================

class TestTieredRouter:
    """Tests for the routing cascade orchestrator."""

    def setup_method(self):
        self.config = RoutingConfig(
            enable_tier2=False,
            enable_tier3=False,
        )
        self.router = TieredRouter(config=self.config)

    # --- Tier 0 routing ---

    def test_tier0_ping(self):
        result = self.router.route("ping")
        assert result.success
        assert result.tier == RoutingTier.INSTANT
        assert result.confidence == 1.0

    def test_tier0_create_node(self):
        result = self.router.route("create a hlight at /obj")
        assert result.success
        assert result.tier == RoutingTier.INSTANT
        assert len(result.commands) == 1
        assert result.commands[0].type == "create_node"

    def test_tier0_with_command_fn(self):
        mock_fn = Mock(return_value=SynapseResponse(
            id="test", success=True, data={"created": True}
        ))
        router = TieredRouter(command_fn=mock_fn, config=self.config)
        result = router.route("create a hlight at /obj")
        assert result.success
        assert len(result.responses) == 1
        assert result.responses[0].success
        mock_fn.assert_called_once()

    def test_tier0_command_fn_error(self):
        mock_fn = Mock(side_effect=RuntimeError("Houdini not connected"))
        router = TieredRouter(command_fn=mock_fn, config=self.config)
        result = router.route("ping")
        assert result.success  # Routing succeeded even if execution failed
        assert len(result.responses) == 1
        assert not result.responses[0].success

    # --- Recipe routing ---

    def test_recipe_three_point(self):
        result = self.router.route("set up three-point lighting at /obj")
        assert result.success
        assert result.tier == RoutingTier.RECIPE
        assert len(result.commands) == 6
        assert result.metadata["recipe"] == "three_point_lighting"

    def test_recipe_with_command_fn(self):
        mock_fn = Mock(return_value=SynapseResponse(
            id="test", success=True, data={}
        ))
        router = TieredRouter(command_fn=mock_fn, config=self.config)
        result = router.route("set up three-point lighting at /obj")
        assert result.success
        assert mock_fn.call_count == 6  # 6 steps in recipe

    # --- Tier 1 routing ---

    def test_tier1_knowledge_lookup(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            _make_rag_dir(tmp_dir)
            config = RoutingConfig(
                rag_root=tmp_dir,
                enable_tier2=False,
                enable_tier3=False,
            )
            router = TieredRouter(config=config)
            result = router.route("karma rendering xpu")
            assert result.success
            assert result.tier == RoutingTier.FAST
            assert "karma" in result.answer.lower()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # --- Cache behavior ---

    def test_cache_hit(self):
        """Tier 1 results are cached (TTL=1h). Tier 0 is not (TTL=0, already instant)."""
        tmp_dir = tempfile.mkdtemp()
        try:
            _make_rag_dir(tmp_dir)
            config = RoutingConfig(
                rag_root=tmp_dir,
                enable_tier0=False,  # Disable T0 so query goes to T1
                enable_tier2=False,
                enable_tier3=False,
            )
            router = TieredRouter(config=config)

            # First call → Tier 1 lookup (cached)
            r1 = router.route("karma rendering xpu")
            assert r1.tier == RoutingTier.FAST
            assert not r1.cached

            # Second call → cache hit
            r2 = router.route("karma rendering xpu")
            assert r2.cached
            assert r2.tier == RoutingTier.FAST
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_cache_disabled(self):
        config = RoutingConfig(
            enable_cache=False,
            enable_tier2=False,
            enable_tier3=False,
        )
        router = TieredRouter(config=config)
        r1 = router.route("ping")
        r2 = router.route("ping")
        assert not r1.cached
        assert not r2.cached  # No caching

    # --- Cascade behavior ---

    def test_escalation_to_fallback(self):
        """Unrecognized input with no LLM → falls through all tiers."""
        result = self.router.route("explain quantum entanglement in detail")
        assert not result.success
        assert result.tier == RoutingTier.DEEP  # Fell through to last tier

    def test_tier_disable(self):
        config = RoutingConfig(
            enable_tier0=False,
            enable_recipes=False,
            enable_tier2=False,
            enable_tier3=False,
        )
        router = TieredRouter(config=config)
        result = router.route("ping")
        assert not result.success  # Tier 0 disabled, no other tier handles it

    # --- Stats ---

    def test_stats(self):
        self.router.route("ping")
        self.router.route("ping")  # cache hit
        s = self.router.stats()
        assert s["total_routes"] == 2
        assert s["tiers"]["instant"]["count"] >= 1

    def test_stats_initial(self):
        s = self.router.stats()
        assert s["total_routes"] == 0

    # --- Config ---

    def test_default_config(self):
        config = RoutingConfig()
        assert config.enable_tier0
        assert config.enable_tier1
        assert config.enable_tier2
        assert config.enable_tier3
        assert config.enable_recipes
        assert config.enable_cache
        assert config.tier0_confidence == 0.8
        assert config.tier1_confidence == 0.5

    # --- as_command_fn wrapper ---

    def test_as_command_fn(self):
        wrapper = self.router.as_command_fn()
        cmd = SynapseCommand(
            type="route",
            id="test-cmd",
            payload={"text": "ping"},
        )
        response = wrapper(cmd)
        assert response.success
        assert response.data["tier"] == "instant"

    def test_as_command_fn_no_text(self):
        wrapper = self.router.as_command_fn()
        cmd = SynapseCommand(
            type="route",
            id="test-cmd",
            payload={},
        )
        response = wrapper(cmd)
        assert not response.success

    # --- Tier properties ---

    def test_parser_property(self):
        assert isinstance(self.router.parser, CommandParser)

    def test_knowledge_property(self):
        assert isinstance(self.router.knowledge, KnowledgeIndex)

    def test_recipe_registry_property(self):
        assert isinstance(self.router.recipe_registry, RecipeRegistry)

    def test_cache_property(self):
        assert isinstance(self.router.cache, ResponseCache)

    # --- Tier 2 (mocked) ---

    def test_tier2_with_mock_anthropic(self):
        """Test Tier 2 with a mocked Anthropic client."""
        config = RoutingConfig(
            enable_tier0=False,
            enable_tier1=False,
            enable_recipes=False,
            enable_tier2=True,
            enable_tier3=False,
            llm_api_key="test-key",
        )
        router = TieredRouter(config=config)

        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = json.dumps({
            "action": "answer",
            "answer": "A displacement shader offsets surface points.",
            "confidence": 0.8,
            "reasoning": "Answering from knowledge.",
        })
        mock_client.messages.create.return_value = mock_response
        router._llm_client = mock_client

        result = router.route("what is a displacement shader?")
        assert result.success
        assert result.tier == RoutingTier.STANDARD
        assert "displacement" in result.answer.lower()
        assert result.confidence == 0.8

    def test_tier2_command_response(self):
        """Test Tier 2 returning a command."""
        config = RoutingConfig(
            enable_tier0=False,
            enable_tier1=False,
            enable_recipes=False,
            enable_tier2=True,
            enable_tier3=False,
            llm_api_key="test-key",
        )
        mock_cmd_fn = Mock(return_value=SynapseResponse(
            id="test", success=True, data={}
        ))
        router = TieredRouter(command_fn=mock_cmd_fn, config=config)

        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = json.dumps({
            "action": "command",
            "command_type": "create_node",
            "payload": {"type": "geo", "parent": "/obj"},
            "answer": "Creating a geometry node.",
            "confidence": 0.85,
            "reasoning": "User wants a geo node.",
        })
        mock_client.messages.create.return_value = mock_response
        router._llm_client = mock_client

        result = router.route("make me a geometry node")
        assert result.success
        assert result.tier == RoutingTier.STANDARD
        assert len(result.commands) == 1
        assert result.commands[0].type == "create_node"
        mock_cmd_fn.assert_called_once()

    # --- Tier 3 async ---

    def test_tier3_async_returns_handle(self):
        config = RoutingConfig(
            enable_tier0=False,
            enable_tier1=False,
            enable_recipes=False,
            enable_tier2=False,
            enable_tier3=True,
            tier3_async=True,
            llm_api_key="test-key",
        )
        router = TieredRouter(config=config)

        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = json.dumps({
            "action": "answer",
            "answer": "Plan complete.",
            "confidence": 0.7,
        })
        mock_client.messages.create.return_value = mock_response
        router._llm_client = mock_client

        result = router.route("build a complex particle system")
        assert result.success
        assert result.tier == RoutingTier.DEEP
        assert result.async_handle is not None

        # Poll for result (with timeout)
        for _ in range(50):
            async_result = router.get_async_result(result.async_handle)
            if async_result is not None:
                break
            time.sleep(0.05)

        assert async_result is not None
        assert async_result.success

    def test_tier3_sync(self):
        config = RoutingConfig(
            enable_tier0=False,
            enable_tier1=False,
            enable_recipes=False,
            enable_tier2=False,
            enable_tier3=True,
            tier3_async=False,
            llm_api_key="test-key",
        )
        router = TieredRouter(config=config)

        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = json.dumps({
            "action": "answer",
            "answer": "Here is your plan.",
            "confidence": 0.8,
        })
        mock_client.messages.create.return_value = mock_response
        router._llm_client = mock_client

        result = router.route("plan a rendering pipeline")
        assert result.success
        assert result.tier == RoutingTier.DEEP
        assert result.async_handle is None  # Sync mode

    # --- Latency tracking ---

    def test_latency_is_tracked(self):
        result = self.router.route("ping")
        assert result.latency_ms > 0
        assert result.latency_ms < 1000  # Should be well under 1s

    # --- RoutingTier enum ---

    def test_routing_tier_values(self):
        assert RoutingTier.CACHE.value == "cache"
        assert RoutingTier.RECIPE.value == "recipe"
        assert RoutingTier.INSTANT.value == "instant"
        assert RoutingTier.FAST.value == "fast"
        assert RoutingTier.STANDARD.value == "standard"
        assert RoutingTier.DEEP.value == "deep"

    # --- LLM response parsing ---

    def test_parse_json_response(self):
        router = TieredRouter(config=self.config)
        parsed = router._parse_llm_response('{"action": "answer", "answer": "hello"}')
        assert parsed["action"] == "answer"
        assert parsed["answer"] == "hello"

    def test_parse_markdown_json_response(self):
        router = TieredRouter(config=self.config)
        text = '```json\n{"action": "answer", "answer": "hello"}\n```'
        parsed = router._parse_llm_response(text)
        assert parsed["action"] == "answer"

    def test_parse_plain_text_fallback(self):
        router = TieredRouter(config=self.config)
        parsed = router._parse_llm_response("Just a plain text answer.")
        assert parsed["action"] == "answer"
        assert "plain text" in parsed["answer"]

    # --- Partial context forwarding ---

    def test_tier2_receives_tier1_partial_context(self):
        """Tier 1 below-threshold result is forwarded to Tier 2 as enrichment."""
        tmp_dir = tempfile.mkdtemp()
        try:
            _make_rag_dir(tmp_dir)
            config = RoutingConfig(
                rag_root=tmp_dir,
                enable_tier0=False,
                enable_recipes=False,
                enable_tier1=True,
                tier1_confidence=0.99,  # Artificially high — forces T1 to reject
                enable_tier2=True,
                enable_tier3=False,
                llm_api_key="test-key",
            )
            router = TieredRouter(config=config)

            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock()]
            mock_response.content[0].text = json.dumps({
                "action": "answer",
                "answer": "Karma XPU uses GPU for fast previews.",
                "confidence": 0.85,
            })
            mock_client.messages.create.return_value = mock_response
            router._llm_client = mock_client

            result = router.route("karma rendering xpu")
            assert result.success
            assert result.tier == RoutingTier.STANDARD

            # Verify the LLM received Tier 1 context
            call_args = mock_client.messages.create.call_args
            user_msg = call_args[1]["messages"][0]["content"]
            assert "<context" in user_msg
            assert "tier1" in user_msg
            assert "karma" in user_msg.lower()

            # Verify metadata tracks enrichment
            assert "tier1_enrichment" in result.metadata
            assert result.metadata["tier1_enrichment"]["topic"] == "karma_rendering"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_tier2_no_enrichment_when_no_knowledge(self):
        """No Tier 1 context forwarded when knowledge has no match."""
        config = RoutingConfig(
            enable_tier0=False,
            enable_recipes=False,
            enable_tier1=True,
            enable_tier2=True,
            enable_tier3=False,
            llm_api_key="test-key",
        )
        router = TieredRouter(config=config)

        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = json.dumps({
            "action": "answer",
            "answer": "I don't know about that.",
            "confidence": 0.5,
        })
        mock_client.messages.create.return_value = mock_response
        router._llm_client = mock_client

        result = router.route("quantum entanglement in VFX")
        assert result.success
        assert result.tier == RoutingTier.STANDARD

        # No enrichment metadata when knowledge had nothing
        assert "tier1_enrichment" not in result.metadata

    def test_knowledge_lookup_called_once(self):
        """Knowledge lookup is not duplicated between Tier 1 and Tier 2."""
        tmp_dir = tempfile.mkdtemp()
        try:
            _make_rag_dir(tmp_dir)
            config = RoutingConfig(
                rag_root=tmp_dir,
                enable_tier0=False,
                enable_recipes=False,
                enable_tier1=True,
                tier1_confidence=0.99,  # Force T1 reject
                enable_tier2=True,
                enable_tier3=False,
                llm_api_key="test-key",
            )
            router = TieredRouter(config=config)

            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock()]
            mock_response.content[0].text = json.dumps({
                "action": "answer",
                "answer": "test",
                "confidence": 0.7,
            })
            mock_client.messages.create.return_value = mock_response
            router._llm_client = mock_client

            with patch.object(router._knowledge, "lookup", wraps=router._knowledge.lookup) as spy:
                router.route("karma rendering xpu")
                assert spy.call_count == 1  # Called once in route(), not again in _try_tier2
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# =============================================================================
# ROUTING ACCURACY BENCHMARK
# =============================================================================
#
# Labeled corpus of artist utterances with expected routing outcomes.
# Run with: python -m pytest tests/test_routing.py -v -k "benchmark"
#
# Purpose: catch regressions when adding new patterns (new pattern steals
# matches from existing ones) and measure routing coverage.
#
# Format: (utterance, expected_tier, expected_pattern_or_recipe, expected_type)
#   - expected_tier: RoutingTier value
#   - expected_pattern_or_recipe: pattern_name, recipe name, or None
#   - expected_type: command type or None (for knowledge/fallback)

_ROUTING_BENCHMARK = [
    # --- Tier 0: Utility ---
    ("ping", RoutingTier.INSTANT, "ping", "ping"),
    ("status", RoutingTier.INSTANT, "ping", "ping"),
    ("health", RoutingTier.INSTANT, "ping", "ping"),
    ("help", RoutingTier.INSTANT, "get_help", "get_help"),
    ("what can you do?", RoutingTier.INSTANT, "get_help", "get_help"),

    # --- Tier 0: Scene queries ---
    ("what's selected", RoutingTier.INSTANT, "get_selection", "get_selection"),
    ("selected nodes", RoutingTier.INSTANT, "get_selection", "get_selection"),
    ("scene info", RoutingTier.INSTANT, "get_scene_info", "get_scene_info"),
    ("stage info", RoutingTier.INSTANT, "get_stage_info", "get_stage_info"),

    # --- Tier 0: Node creation ---
    ("create a hlight at /obj", RoutingTier.INSTANT, "create_node", "create_node"),
    ("create hlight called key_light at /obj", RoutingTier.INSTANT, "create_node_named", "create_node"),
    ("create a new geo in /obj", RoutingTier.INSTANT, "create_node", "create_node"),

    # --- Tier 0: Parameters ---
    ("set intensity on /obj/key to 1.5", RoutingTier.INSTANT, "set_parm_alt", "set_parm"),
    ("get intensity from /obj/key", RoutingTier.INSTANT, "get_parm", "get_parm"),
    ("what's intensity on /obj/key?", RoutingTier.INSTANT, "get_parm_alt", "get_parm"),

    # --- Tier 0: Connections & Deletion ---
    ("connect /obj/a to /obj/b", RoutingTier.INSTANT, "connect", "connect_nodes"),
    ("delete /obj/old_node", RoutingTier.INSTANT, "delete", "delete_node"),
    ("remove /obj/old_node", RoutingTier.INSTANT, "delete", "delete_node"),

    # --- Tier 0: COPs ---
    ("composite /img/fg over /img/bg", RoutingTier.INSTANT, "composite_over", "connect_nodes"),
    ("comp /img/fg onto /img/bg", RoutingTier.INSTANT, "composite_over", "connect_nodes"),
    ("apply blur to /img/render1", RoutingTier.INSTANT, "apply_cop_filter", "create_node"),
    ("blur /img/render1", RoutingTier.INSTANT, "apply_cop_filter", "create_node"),
    ("apply color_correct to /img/render1", RoutingTier.INSTANT, "apply_cop_filter", "create_node"),
    ("sharpen /img/plate1", RoutingTier.INSTANT, "apply_cop_filter", "create_node"),
    ("apply denoise to /img/noisy", RoutingTier.INSTANT, "apply_cop_filter", "create_node"),

    # --- Recipe ---
    ("set up three-point lighting at /obj", RoutingTier.RECIPE, "three_point_lighting", None),
    ("setup three point lighting", RoutingTier.RECIPE, "three_point_lighting", None),
    ("scatter /obj/rocks onto /obj/terrain", RoutingTier.RECIPE, "scatter_copy", None),
    ("create a controller at /obj", RoutingTier.RECIPE, "null_controller", None),
    ("set up color correction at /img", RoutingTier.RECIPE, "color_correction_setup", None),
    ("setup color correction", RoutingTier.RECIPE, "color_correction_setup", None),

    # --- New recipes ---
    ("setup a dome light", RoutingTier.RECIPE, "dome_light_environment", None),
    ("create dome light with studio.exr", RoutingTier.RECIPE, "dome_light_environment", None),
    ("add an environment light", RoutingTier.RECIPE, "dome_light_environment", None),
    ("setup a camera at /obj", RoutingTier.RECIPE, "camera_rig", None),
    ("add a render camera", RoutingTier.RECIPE, "camera_rig", None),
    ("setup pyro source at /obj/geo1", RoutingTier.RECIPE, "pyro_source_setup", None),
    ("create a quick material named chrome", RoutingTier.RECIPE, "material_quick_setup", None),
    ("setup material named gold", RoutingTier.RECIPE, "material_quick_setup", None),
    ("setup karma render", RoutingTier.RECIPE, "karma_render_setup", None),
    ("create karma render setup", RoutingTier.RECIPE, "karma_render_setup", None),
    ("import /obj/geo1/sphere1 into the stage", RoutingTier.RECIPE, "sopimport_chain", None),
    ("bring /obj/geo1/out to the usd stage", RoutingTier.RECIPE, "sopimport_chain", None),
    ("edit /World/hero translate", RoutingTier.RECIPE, "edit_transform", None),
    ("transform /World/props/chair position", RoutingTier.RECIPE, "edit_transform", None),

    # --- HDA generate recipes ---
    ("generate an HDA that scatters points", RoutingTier.RECIPE, "hda_generate", None),
    ("generate a tool to deform geometry", RoutingTier.RECIPE, "hda_generate", None),
    ("hda generate color by height gradient", RoutingTier.RECIPE, "hda_generate", None),
    ("generate an HDA that masks points by proximity", RoutingTier.RECIPE, "hda_generate", None),
    ("generate a tool to extrude along normals", RoutingTier.RECIPE, "hda_generate", None),

    # --- Production recipes ---
    ("setup cloth sim at /obj", RoutingTier.RECIPE, "vellum_cloth_sim", None),
    ("create vellum cloth at /obj/geo1", RoutingTier.RECIPE, "vellum_cloth_sim", None),
    ("setup destruction at /obj/geo1", RoutingTier.RECIPE, "rbd_destruction", None),
    ("setup rbd fracture simulation at /obj/hero", RoutingTier.RECIPE, "rbd_destruction", None),
    ("setup a turntable render for /obj/hero", RoutingTier.RECIPE, "turntable_render", None),
    ("create turntable for /obj/geo1", RoutingTier.RECIPE, "turntable_render", None),
    ("setup an ocean at /obj", RoutingTier.RECIPE, "ocean_setup", None),
    ("create ocean surface at /obj", RoutingTier.RECIPE, "ocean_setup", None),
    ("setup fire sim at /obj", RoutingTier.RECIPE, "pyro_fire_sim", None),
    ("setup pyro simulation at /obj/emitter", RoutingTier.RECIPE, "pyro_fire_sim", None),
    ("setup wire sim at /obj", RoutingTier.RECIPE, "vellum_wire_sim", None),
    ("create vellum cable simulation at /obj", RoutingTier.RECIPE, "vellum_wire_sim", None),
    ("setup a terrain at /obj", RoutingTier.RECIPE, "terrain_environment", None),
    ("build a landscape at /obj", RoutingTier.RECIPE, "terrain_environment", None),
    ("setup lookdev scene", RoutingTier.RECIPE, "lookdev_scene", None),
    ("create a lookdev environment", RoutingTier.RECIPE, "lookdev_scene", None),
    ("create file cache for /obj/geo1/null1", RoutingTier.RECIPE, "file_cache", None),
    ("sweep roughness from 0.1 to 0.9 in 5 steps", RoutingTier.RECIPE, "tops_parameter_sweep", None),
    ("quick cook /obj/topnet1/ropfetch1", RoutingTier.RECIPE, "tops_quick_cook", None),
    ("cook and check /obj/topnet1/fetch1", RoutingTier.RECIPE, "tops_quick_cook", None),
    ("diagnose /obj/topnet1/ropfetch1", RoutingTier.RECIPE, "tops_diagnose_recipe", None),
    ("render at preview quality", RoutingTier.RECIPE, "render_preview", None),
    ("do a quick render", RoutingTier.RECIPE, "render_preview", None),
    ("test render", RoutingTier.RECIPE, "render_preview", None),
    ("create an hda called scatter_tool for scattering points", RoutingTier.RECIPE, "hda_scaffold", None),
    ("scaffold hda named wave_deformer", RoutingTier.RECIPE, "hda_scaffold", None),
    ("debug wrangle on /obj/geo1/wrangle1", RoutingTier.RECIPE, "vex_debug_wrangle", None),
    ("inspect vex at /obj/geo1/attribwrangle1", RoutingTier.RECIPE, "vex_debug_wrangle", None),
    ("assign /materials/chrome to /World/hero", RoutingTier.RECIPE, "material_assign", None),
    ("bind material /materials/gold to /World/props", RoutingTier.RECIPE, "material_assign", None),
    ("create noise deformer at /obj/geo1", RoutingTier.RECIPE, "vex_noise_deformer", None),
    ("add fbm noise at /obj/terrain", RoutingTier.RECIPE, "vex_noise_deformer", None),

    # --- Should NOT match (falls through) ---
    ("tell me about the meaning of life", None, None, None),
    ("explain quantum entanglement in detail", None, None, None),
    ("what's the weather", None, None, None),
]


class TestRoutingBenchmark:
    """
    Regression benchmark for routing accuracy.

    Each entry is a labeled (utterance, expected_tier, expected_pattern/recipe).
    Parametrized so failures report the exact utterance that regressed.
    """

    def setup_method(self):
        self.config = RoutingConfig(
            enable_tier2=False,
            enable_tier3=False,
        )
        self.router = TieredRouter(config=self.config)

    @pytest.mark.parametrize(
        "utterance,expected_tier,expected_name,expected_type",
        _ROUTING_BENCHMARK,
        ids=[f"{i:02d}_{row[0][:40]}" for i, row in enumerate(_ROUTING_BENCHMARK)],
    )
    def test_routing_accuracy(self, utterance, expected_tier, expected_name, expected_type):
        result = self.router.route(utterance)

        if expected_tier is None:
            # Should fall through (no match)
            assert not result.success, f"Expected no match for '{utterance}', got tier={result.tier.value}"
            return

        assert result.success, f"Expected match for '{utterance}'"
        assert result.tier == expected_tier, (
            f"Tier mismatch for '{utterance}': "
            f"expected {expected_tier.value}, got {result.tier.value}"
        )

        if expected_name:
            if result.tier == RoutingTier.RECIPE:
                assert result.metadata.get("recipe") == expected_name, (
                    f"Recipe mismatch for '{utterance}': "
                    f"expected {expected_name}, got {result.metadata.get('recipe')}"
                )
            elif result.tier == RoutingTier.INSTANT:
                assert result.metadata.get("pattern") == expected_name, (
                    f"Pattern mismatch for '{utterance}': "
                    f"expected {expected_name}, got {result.metadata.get('pattern')}"
                )

        if expected_type and result.commands:
            assert result.commands[0].type == expected_type, (
                f"Command type mismatch for '{utterance}': "
                f"expected {expected_type}, got {result.commands[0].type}"
            )

    def test_benchmark_coverage_report(self):
        """Run full benchmark and report coverage stats."""
        tier_counts = {}
        failures = []

        for utterance, expected_tier, expected_name, expected_type in _ROUTING_BENCHMARK:
            result = self.router.route(utterance)

            if expected_tier is None:
                tier_name = "fallthrough"
                matched = not result.success
            else:
                tier_name = expected_tier.value
                matched = result.success and result.tier == expected_tier

            tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1
            if not matched:
                failures.append(utterance)

        total = len(_ROUTING_BENCHMARK)
        correct = total - len(failures)
        accuracy = correct / total if total else 0

        # This test always passes — it's a report
        assert accuracy >= 0.95, (
            f"Routing accuracy {accuracy:.1%} below 95% threshold. "
            f"Failures: {failures}"
        )


# =============================================================================
# ROUTE_CHAT HANDLER TESTS (P0)
# =============================================================================

class TestRouteChatHandler:
    """Tests for the route_chat command handler (P0: Chat Routing Dispatch)."""

    def setup_method(self):
        """Fresh router + handler for each test."""
        # Reset singleton to avoid cross-test pollution
        TieredRouter._instance = None
        self.router = TieredRouter(config=RoutingConfig(
            enable_tier2=False,
            enable_tier3=False,
        ))
        # Install as singleton so handler's get_instance() finds it
        TieredRouter._instance = self.router

    def teardown_method(self):
        TieredRouter._instance = None

    def test_route_chat_command_type_exists(self):
        """ROUTE_CHAT CommandType is defined in protocol."""
        from synapse.core.protocol import CommandType
        assert hasattr(CommandType, "ROUTE_CHAT")
        assert CommandType.ROUTE_CHAT.value == "route_chat"

    def test_route_chat_registered_in_handler(self):
        """route_chat is registered in the handler registry."""
        import types

        # Minimal hou stub (needs Node class for guards.py type annotations)
        mock_hou = types.ModuleType("hou")
        mock_hou.hipFile = Mock()
        mock_hou.hipFile.name = Mock(return_value="untitled.hip")
        mock_hou.applicationVersion = Mock(return_value=(21, 0, 0))
        mock_hou.node = Mock(return_value=None)
        mock_hou.undos = Mock()
        mock_hou.NodeTypeCategory = Mock()
        mock_hou.Node = type("Node", (), {})
        mock_hou.Parm = type("Parm", (), {})
        mock_hou.OperationFailed = type("OperationFailed", (Exception,), {})
        saved_hou = sys.modules.get("hou")
        sys.modules["hou"] = mock_hou
        # Clear cached imports so fresh hou stub is picked up
        _cached = {}
        for mod_name in list(sys.modules):
            if mod_name.startswith("synapse.server"):
                _cached[mod_name] = sys.modules.pop(mod_name)
        try:
            from synapse.server.handlers import SynapseHandler
            handler = SynapseHandler()
            assert handler._registry.has("route_chat"), "route_chat not registered"
        finally:
            # Restore everything
            for mod_name in list(sys.modules):
                if mod_name.startswith("synapse.server"):
                    sys.modules.pop(mod_name, None)
            sys.modules.update(_cached)
            if saved_hou is not None:
                sys.modules["hou"] = saved_hou
            else:
                sys.modules.pop("hou", None)

    def test_route_chat_create_node_routes_to_command(self):
        """'create a sphere at /obj' should route to Tier 0 regex, not execute_python."""
        result = self.router.route("create a sphere at /obj")
        assert result.success
        # Should route to instant (regex) tier
        assert result.tier == RoutingTier.INSTANT, (
            f"Expected instant tier, got {result.tier.value}"
        )
        # Should produce a create_node command, not execute_python
        assert len(result.commands) > 0
        for cmd in result.commands:
            assert cmd.type != "execute_python", (
                "Chat should never route to execute_python"
            )
            assert cmd.type == "create_node"

    def test_route_chat_scene_info_routes_correctly(self):
        """'scene info' should route to get_scene_info via Tier 0 regex."""
        result = self.router.route("scene info")
        assert result.success
        assert result.tier == RoutingTier.INSTANT, (
            f"Expected instant tier, got {result.tier.value}"
        )
        assert len(result.commands) > 0
        assert result.commands[0].type == "get_scene_info"

    def test_route_chat_unknown_falls_through(self):
        """Unknown/ambiguous query should fall through gracefully."""
        result = self.router.route("xyzzy plugh 12345")
        # Either fails gracefully or gets a low-confidence answer
        assert isinstance(result, RoutingResult)
        assert isinstance(result.answer, str)
        assert result.tier is not None

    def test_route_chat_response_format(self):
        """Handler response has required keys."""
        result = self.router.route("create a box")
        # Simulate what the handler does: build the dict
        response = {
            "response": result.answer,
            "tier": result.tier.value,
            "commands": [
                {"type": cmd.type, "id": cmd.id, "payload": cmd.payload}
                for cmd in result.commands
            ] if result.commands else [],
            "confidence": result.confidence,
            "cached": result.cached,
            "latency_ms": result.latency_ms,
        }
        assert "response" in response
        assert "tier" in response
        assert "commands" in response
        assert "confidence" in response
        assert isinstance(response["tier"], str)
        assert isinstance(response["commands"], list)
        assert isinstance(response["confidence"], float)

    def test_route_chat_with_context(self):
        """route_chat accepts optional context dict."""
        result = self.router.route(
            "add a light",
            context={"scene_path": "/obj", "frame": 1},
        )
        assert isinstance(result, RoutingResult)

    def test_route_chat_singleton_accessor(self):
        """TieredRouter.get_instance() returns singleton."""
        TieredRouter._instance = None
        r1 = TieredRouter.get_instance()
        r2 = TieredRouter.get_instance()
        assert r1 is r2
        TieredRouter._instance = None

    def test_route_chat_message_alias_resolution(self):
        """'message' param alias resolves to 'content' canonical."""
        from synapse.core.aliases import resolve_param
        payload = {"message": "create a sphere"}
        val = resolve_param(payload, "content")
        assert val == "create a sphere"

    def test_route_chat_text_alias_resolution(self):
        """'text' param alias resolves to 'content' canonical."""
        from synapse.core.aliases import resolve_param
        payload = {"text": "create a light"}
        val = resolve_param(payload, "content")
        assert val == "create a light"
