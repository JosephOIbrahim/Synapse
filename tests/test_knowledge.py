"""Tests for RAG knowledge lookup handler and KnowledgeIndex integration."""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Load modules without Houdini
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

# Load knowledge module directly
_kspec = importlib.util.spec_from_file_location(
    "knowledge", ROOT / "python" / "synapse" / "routing" / "knowledge.py"
)
_knowledge_mod = importlib.util.module_from_spec(_kspec)
_kspec.loader.exec_module(_knowledge_mod)
KnowledgeIndex = _knowledge_mod.KnowledgeIndex
KnowledgeLookupResult = _knowledge_mod.KnowledgeLookupResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rag_dir(tmp_path):
    """Create a minimal RAG directory structure with test data."""
    meta_dir = tmp_path / "documentation" / "_metadata"
    meta_dir.mkdir(parents=True)

    skills_dir = tmp_path / "skills" / "houdini21-reference"
    skills_dir.mkdir(parents=True)

    # Semantic index with 3 test topics
    index = {
        "solaris_parameter_names": {
            "summary": "Encoded parameter names for Solaris light, camera, material nodes",
            "description": "Light intensity: xn__inputsintensity_i0a. Light color: xn__inputscolor_zya.",
            "keywords": ["parameter", "parm", "intensity", "color", "solaris", "encoded"]
        },
        "karma_rendering": {
            "summary": "Karma XPU/CPU rendering setup",
            "description": "Use usdrender ROP in /out. Set loppath, outputimage, override_res.",
            "keywords": ["karma", "render", "xpu", "cpu", "usdrender", "rop"]
        },
        "pyro_simulation": {
            "summary": "Pyro FX simulation setup chain",
            "description": "sphere -> scatter -> attribwrangle -> volumerasterizeattributes -> pyrosolver",
            "keywords": ["pyro", "fire", "smoke", "simulation", "volume", "fx"]
        },
    }
    (meta_dir / "semantic_index.json").write_text(
        json.dumps(index), encoding="utf-8"
    )

    # Agent relevance map
    agent_map = {
        "solaris_parameter_names": {"agent": "houdini_set_parm"},
        "karma_rendering": {"agent": "houdini_render"},
        "pyro_simulation": {"agent": "houdini_execute_python"},
    }
    (meta_dir / "agent_relevance_map.json").write_text(
        json.dumps(agent_map), encoding="utf-8"
    )

    # Reference files
    (skills_dir / "solaris_parameters.md").write_text(
        "# Solaris Parameters\n\n## Light Intensity\n`xn__inputsintensity_i0a`\n",
        encoding="utf-8",
    )
    (skills_dir / "rendering.md").write_text(
        "# Karma Rendering\n\n## ROP Types\n`usdrender` in /out\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def knowledge(rag_dir):
    """Create a KnowledgeIndex with the test RAG directory."""
    return KnowledgeIndex(rag_root=str(rag_dir))


# ---------------------------------------------------------------------------
# KnowledgeIndex unit tests
# ---------------------------------------------------------------------------

class TestKnowledgeIndex:
    """Tests for the KnowledgeIndex class."""

    def test_loads_semantic_index(self, knowledge):
        """Index should load all topics from semantic_index.json."""
        assert len(knowledge._semantic_index) == 3
        assert "solaris_parameter_names" in knowledge._semantic_index

    def test_builds_keyword_index(self, knowledge):
        """Inverted keyword index should map words to topics."""
        assert "intensity" in knowledge._keyword_to_topics
        assert "solaris_parameter_names" in knowledge._keyword_to_topics["intensity"]

    def test_lookup_finds_topic_by_keyword(self, knowledge):
        """Lookup by keyword should find matching topic."""
        result = knowledge.lookup("light intensity parameter")
        assert result.found
        assert result.confidence > 0
        assert "solaris_parameter_names" in result.topic or "intensity" in result.answer.lower()

    def test_lookup_finds_pyro(self, knowledge):
        """Pyro-related queries should match pyro_simulation."""
        result = knowledge.lookup("pyro fire simulation setup")
        assert result.found
        assert "pyro" in result.topic.lower() or "pyro" in result.answer.lower()

    def test_lookup_finds_karma(self, knowledge):
        """Karma/render queries should match karma_rendering."""
        result = knowledge.lookup("karma render setup")
        assert result.found

    def test_lookup_not_found(self, knowledge):
        """Unrelated queries should not find anything."""
        result = knowledge.lookup("quantum physics entanglement")
        # Either not found, or very low confidence
        assert not result.found or result.confidence < 0.3

    def test_no_rag_root_returns_not_found(self):
        """KnowledgeIndex with no rag_root should return not-found."""
        ki = KnowledgeIndex(rag_root=None)
        result = ki.lookup("anything")
        assert not result.found

    def test_empty_rag_dir_returns_not_found(self, tmp_path):
        """Empty rag directory should return not-found gracefully."""
        ki = KnowledgeIndex(rag_root=str(tmp_path))
        result = ki.lookup("anything")
        assert not result.found

    def test_result_has_sources(self, knowledge):
        """Found results should include source references."""
        result = knowledge.lookup("karma render xpu")
        if result.found:
            # Sources list exists (may be empty if only keyword match)
            assert isinstance(result.sources, list)

    def test_agent_hint(self, knowledge):
        """Agent relevance map should populate agent_hint."""
        # This depends on the agent_relevance_map being loaded
        assert isinstance(knowledge._agent_relevance, dict)


class TestSchemaAdapter:
    """Tests for nested-to-flat schema normalization."""

    def test_flat_schema_passes_through(self):
        """Flat SYNAPSE format should be returned unchanged."""
        flat = {
            "karma_rendering": {
                "summary": "Karma setup",
                "keywords": ["karma", "render"],
            }
        }
        result = KnowledgeIndex._normalize_semantic_index(flat)
        assert result == flat

    def test_nested_schema_normalized(self):
        """Nested HOUDINI21_RAG format should be flattened."""
        nested = {
            "semantic_index": {
                "topics": {
                    "pyro_simulation": {
                        "primary_doc": "Pyro FX chain",
                        "description": "sphere -> scatter -> pyrosolver",
                        "keywords": ["pyro", "fire"],
                        "agent_relevance": "fx_agent",
                        "common_queries": [
                            "how to set up pyro",
                            "fire simulation chain",
                        ],
                    },
                    "karma_rendering": {
                        "primary_doc": "Karma XPU setup",
                        "keywords": ["karma", "render"],
                    },
                }
            }
        }
        result = KnowledgeIndex._normalize_semantic_index(nested)
        assert len(result) == 2
        assert "pyro_simulation" in result
        assert "karma_rendering" in result
        # primary_doc maps to summary
        assert result["pyro_simulation"]["summary"] == "Pyro FX chain"
        # description preserved
        assert "pyrosolver" in result["pyro_simulation"]["description"]
        # keywords preserved
        assert result["pyro_simulation"]["keywords"] == ["pyro", "fire"]
        # common_queries preserved
        assert len(result["pyro_simulation"]["common_queries"]) == 2
        # When no description, primary_doc used as description
        assert result["karma_rendering"]["description"] == "Karma XPU setup"

    def test_nested_schema_loads_in_index(self, tmp_path):
        """KnowledgeIndex should handle nested schema end-to-end."""
        meta_dir = tmp_path / "documentation" / "_metadata"
        meta_dir.mkdir(parents=True)
        nested = {
            "semantic_index": {
                "topics": {
                    "rbd_simulation": {
                        "primary_doc": "RBD fracture simulation",
                        "keywords": ["rbd", "fracture", "bullet"],
                    }
                }
            }
        }
        (meta_dir / "semantic_index.json").write_text(
            json.dumps(nested), encoding="utf-8"
        )
        ki = KnowledgeIndex(rag_root=str(tmp_path))
        assert ki.topic_count == 1
        result = ki.lookup("rbd fracture simulation")
        assert result.found

    def test_empty_nested_topics(self):
        """Nested format with empty topics should return empty dict."""
        nested = {"semantic_index": {"topics": {}}}
        result = KnowledgeIndex._normalize_semantic_index(nested)
        assert result == {}

    def test_non_dict_topic_skipped(self):
        """Non-dict topic entries in nested format should be skipped."""
        nested = {
            "semantic_index": {
                "topics": {
                    "valid_topic": {
                        "primary_doc": "Valid",
                        "keywords": ["valid"],
                    },
                    "invalid_topic": "just a string",
                }
            }
        }
        result = KnowledgeIndex._normalize_semantic_index(nested)
        assert len(result) == 1
        assert "valid_topic" in result


# ---------------------------------------------------------------------------
# Common Queries: query -> expected topic resolution
# ---------------------------------------------------------------------------

# These fixtures validate that realistic artist queries resolve to the correct
# topic. Ported from the HOUDINI21_RAG common_queries pattern.
COMMON_QUERIES = [
    # (query, expected_topic_substring)
    ("what is the light intensity parameter name", "solaris_parameter"),
    ("how to set up karma xpu rendering", "karma"),
    ("pyro fire smoke simulation chain", "pyro"),
    ("materialx base color roughness", "materialx"),
    ("lighting setup exposure three point rig", "lighting"),
    ("usd stage prim operations", "usd_stage"),
    ("flip fluid simulation setup", "flip"),
    ("rbd bullet fracture", "rbd"),
    ("vellum cloth sim", "vellum"),
    ("tops wedge parameter sweep", "tops"),
    ("solaris lop node types", "solaris_node"),
    ("camera setup focal length", "camera"),
    ("sop geometry operations", "sop"),
    ("vex attribute wrangle", "vex"),
    ("scene assembly merge reference", "scene_assembly"),
    ("ocean spectrum wave", "ocean"),
    ("terrain heightfield erode", "terrain"),
    ("kinefx skeleton rig", "kinefx"),
    ("uv unwrap flatten", "uv"),
    ("sop solver feedback loop", "sop_solver"),
    ("cops compositing", "cops"),
    ("common houdini errors", "common_errors"),
    ("houdini expressions ch chf", "expressions"),
    ("pipeline integration alembic usd", "pipeline"),
    # Developer/TD queries (merged from HOUDINI21_RAG)
    ("hapi engine session initialize", "hapi"),
    ("hdk GU_Detail compiled SOP", "hdk"),
    ("hydra render delegate plugin", "hydra"),
    ("usd schema registration pluginfo", "usd_schema"),
    ("pxr pluginpath discovery", "pxr_plugin"),
]


class TestCommonQueries:
    """Validate that common artist/TD queries resolve to correct topics."""

    @pytest.fixture
    def real_knowledge(self):
        rag_path = ROOT / "rag"
        if not (rag_path / "documentation" / "_metadata" / "semantic_index.json").exists():
            pytest.skip("Real RAG content not available")
        return KnowledgeIndex(rag_root=str(rag_path))

    @pytest.mark.parametrize("query,expected_topic", COMMON_QUERIES)
    def test_common_query_resolves(self, real_knowledge, query, expected_topic):
        """Each common query should resolve to a topic containing the expected substring."""
        result = real_knowledge.lookup(query)
        assert result.found, f"Query '{query}' should find a result"
        assert expected_topic in result.topic.lower(), (
            f"Query '{query}' resolved to '{result.topic}', "
            f"expected topic containing '{expected_topic}'"
        )


class TestKnowledgeLookupResult:
    """Tests for the KnowledgeLookupResult dataclass."""

    def test_default_not_found(self):
        result = KnowledgeLookupResult(found=False)
        assert not result.found
        assert result.answer == ""
        assert result.confidence == 0.0
        assert result.sources == []

    def test_found_result(self):
        result = KnowledgeLookupResult(
            found=True,
            answer="Use xn__inputsintensity_i0a",
            confidence=0.85,
            topic="solaris_parameter_names",
            sources=["solaris_parameters.md"],
            agent_hint="houdini_set_parm",
        )
        assert result.found
        assert result.confidence == 0.85
        assert result.agent_hint == "houdini_set_parm"


# ---------------------------------------------------------------------------
# Integration: Test against real RAG content
# ---------------------------------------------------------------------------

class TestRealRAGContent:
    """Tests against the actual RAG content in the repo."""

    @pytest.fixture
    def real_knowledge(self):
        rag_path = ROOT / "rag"
        if not (rag_path / "documentation" / "_metadata" / "semantic_index.json").exists():
            pytest.skip("Real RAG content not available")
        return KnowledgeIndex(rag_root=str(rag_path))

    def test_loads_all_topics(self, real_knowledge):
        """Real semantic index should have 13 topics."""
        assert len(real_knowledge._semantic_index) >= 10

    def test_dome_light_intensity(self, real_knowledge):
        """Should find dome light intensity parameter name."""
        result = real_knowledge.lookup("dome light intensity parameter name")
        assert result.found

    def test_pyro_chain(self, real_knowledge):
        """Should find pyro simulation setup chain."""
        result = real_knowledge.lookup("how to set up pyro fire simulation")
        assert result.found

    def test_karma_render_setup(self, real_knowledge):
        """Should find Karma rendering reference."""
        result = real_knowledge.lookup("karma xpu render rop setup")
        assert result.found

    def test_materialx_shader(self, real_knowledge):
        """Should find MaterialX shader parameters."""
        result = real_knowledge.lookup("materialx base color metalness")
        assert result.found


# ---------------------------------------------------------------------------
# Phase P2: Tool group knowledge preambles
# ---------------------------------------------------------------------------

class TestToolGroupKnowledge:
    """Validate that tool group modules expose GROUP_KNOWLEDGE constants."""

    @pytest.fixture
    def tool_group_modules(self):
        """Import all 5 tool group modules."""
        import importlib
        modules = {}
        for name in ["mcp_tools_scene", "mcp_tools_render", "mcp_tools_usd",
                      "mcp_tools_tops", "mcp_tools_memory"]:
            spec = importlib.util.spec_from_file_location(
                name, ROOT / f"{name}.py"
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            modules[name] = mod
        return modules

    def test_all_groups_have_knowledge(self, tool_group_modules):
        """Every tool group module must have a non-empty GROUP_KNOWLEDGE constant."""
        for name, mod in tool_group_modules.items():
            assert hasattr(mod, "GROUP_KNOWLEDGE"), f"{name} missing GROUP_KNOWLEDGE"
            assert isinstance(mod.GROUP_KNOWLEDGE, str), f"{name}.GROUP_KNOWLEDGE not a string"
            assert len(mod.GROUP_KNOWLEDGE) > 50, f"{name}.GROUP_KNOWLEDGE too short"

    def test_all_groups_have_tool_names(self, tool_group_modules):
        """Every tool group module must have a TOOL_NAMES list."""
        for name, mod in tool_group_modules.items():
            assert hasattr(mod, "TOOL_NAMES"), f"{name} missing TOOL_NAMES"
            assert isinstance(mod.TOOL_NAMES, list), f"{name}.TOOL_NAMES not a list"
            assert len(mod.TOOL_NAMES) >= 3, f"{name}.TOOL_NAMES has too few tools"

    def test_all_groups_have_dispatch_keys(self, tool_group_modules):
        """Every tool group module must have a DISPATCH_KEYS dict."""
        for name, mod in tool_group_modules.items():
            assert hasattr(mod, "DISPATCH_KEYS"), f"{name} missing DISPATCH_KEYS"
            assert isinstance(mod.DISPATCH_KEYS, dict)
            # DISPATCH_KEYS should cover all TOOL_NAMES
            for tool in mod.TOOL_NAMES:
                assert tool in mod.DISPATCH_KEYS, (
                    f"{name}: tool '{tool}' in TOOL_NAMES but missing from DISPATCH_KEYS"
                )

    def test_render_knowledge_mentions_exposure(self, tool_group_modules):
        """Render group knowledge must mention the Lighting Law (exposure)."""
        knowledge = tool_group_modules["mcp_tools_render"].GROUP_KNOWLEDGE
        assert "exposure" in knowledge.lower()
        assert "1.0" in knowledge

    def test_usd_knowledge_mentions_encoded_params(self, tool_group_modules):
        """USD group knowledge must mention encoded parameter names."""
        knowledge = tool_group_modules["mcp_tools_usd"].GROUP_KNOWLEDGE
        assert "xn__" in knowledge

    def test_memory_knowledge_mentions_project_setup(self, tool_group_modules):
        """Memory group knowledge must mention synapse_project_setup."""
        knowledge = tool_group_modules["mcp_tools_memory"].GROUP_KNOWLEDGE
        assert "project_setup" in knowledge.lower() or "synapse_project_setup" in knowledge


# ---------------------------------------------------------------------------
# Phase P2: Context enrichment module
# ---------------------------------------------------------------------------

# Load context_enrichment module
_ce_spec = importlib.util.spec_from_file_location(
    "context_enrichment",
    ROOT / "python" / "synapse" / "routing" / "context_enrichment.py",
)
_ce_mod = importlib.util.module_from_spec(_ce_spec)
_ce_spec.loader.exec_module(_ce_mod)
enrich_context = _ce_mod.enrich_context
register_group_knowledge = _ce_mod.register_group_knowledge
get_group_for_tool = _ce_mod.get_group_for_tool


class TestContextEnrichment:
    """Tests for the context_enrichment module."""

    def test_plain_message_passes_through(self):
        """Without any enrichment sources, message is returned as-is."""
        result = enrich_context("hello world")
        assert result == "hello world"

    def test_tier1_hint_injected(self):
        """Tier 1 knowledge should be injected as XML context."""
        hint = KnowledgeLookupResult(
            found=True,
            answer="Use xn__inputsintensity_i0a for intensity",
            confidence=0.85,
        )
        result = enrich_context("set light intensity", tier1_hint=hint)
        assert '<context source="tier1"' in result
        assert "xn__inputsintensity_i0a" in result
        assert "set light intensity" in result

    def test_tier1_not_found_skipped(self):
        """Tier 1 hint with found=False should not inject context."""
        hint = KnowledgeLookupResult(found=False)
        result = enrich_context("set light intensity", tier1_hint=hint)
        assert "<context" not in result
        assert result == "set light intensity"

    def test_group_knowledge_injected(self):
        """Tool group knowledge should be injected when group specified."""
        register_group_knowledge({"render": "Intensity ALWAYS 1.0"})
        result = enrich_context("render scene", tool_group="render")
        assert '<context source="tool_group"' in result
        assert "Intensity ALWAYS 1.0" in result

    def test_unknown_group_ignored(self):
        """Unknown tool group should not inject anything."""
        result = enrich_context("hello", tool_group="nonexistent")
        assert "<context" not in result

    def test_memory_injected(self):
        """Memory search results should be included."""
        mock_memory = MagicMock()
        mock_result = MagicMock()
        mock_result.memory.summary = "Previous render used Karma XPU"
        mock_result.memory.content = "Full memory content here"
        mock_memory.search.return_value = [mock_result]

        result = enrich_context("render setup", memory=mock_memory)
        assert "<memory>" in result
        assert "Previous render used Karma XPU" in result

    def test_memory_failure_graceful(self):
        """Memory search failure should not crash enrichment."""
        mock_memory = MagicMock()
        mock_memory.search.side_effect = RuntimeError("DB unavailable")

        result = enrich_context("render setup", memory=mock_memory)
        assert "render setup" in result
        # No crash, no memory section
        assert "<memory>" not in result

    def test_all_sources_combined(self):
        """All enrichment sources should combine in order."""
        register_group_knowledge({"usd": "USD composition rules"})
        hint = KnowledgeLookupResult(
            found=True, answer="Stage hierarchy", confidence=0.7,
        )
        mock_memory = MagicMock()
        mock_result = MagicMock()
        mock_result.memory.summary = "Prev session context"
        mock_result.memory.content = "Full"
        mock_memory.search.return_value = [mock_result]

        result = enrich_context(
            "query stage",
            tier1_hint=hint,
            memory=mock_memory,
            tool_group="usd",
        )
        # All sections present
        assert "tool_group" in result
        assert "tier1" in result
        assert "<memory>" in result
        assert "query stage" in result

        # Order: group knowledge before tier1 before memory before message
        group_pos = result.index("tool_group")
        tier1_pos = result.index("tier1")
        memory_pos = result.index("<memory>")
        msg_pos = result.index("query stage")
        assert group_pos < tier1_pos < memory_pos < msg_pos


class TestGetGroupForTool:
    """Tests for tool-to-group resolution."""

    def test_render_tools(self):
        assert get_group_for_tool("houdini_render") == "render"
        assert get_group_for_tool("houdini_capture_viewport") == "render"
        assert get_group_for_tool("synapse_validate_frame") == "render"

    def test_usd_tools(self):
        assert get_group_for_tool("houdini_stage_info") == "usd"
        assert get_group_for_tool("houdini_create_material") == "usd"
        assert get_group_for_tool("houdini_assign_material") == "usd"

    def test_tops_tools(self):
        assert get_group_for_tool("tops_cook_node") == "tops"
        assert get_group_for_tool("tops_diagnose") == "tops"

    def test_memory_tools(self):
        assert get_group_for_tool("synapse_knowledge_lookup") == "memory"
        assert get_group_for_tool("houdini_hda_create") == "memory"

    def test_scene_default(self):
        """Unmatched houdini_/synapse_ tools default to scene group."""
        assert get_group_for_tool("synapse_ping") == "scene"
        assert get_group_for_tool("houdini_create_node") == "scene"

    def test_unknown_tool(self):
        """Completely unknown tools return None."""
        assert get_group_for_tool("unknown_tool") is None


# ---------------------------------------------------------------------------
# Phase P2: Semantic index coverage validation
# ---------------------------------------------------------------------------

class TestSemanticIndexCoverage:
    """Validate that the semantic index meets P2 coverage targets."""

    @pytest.fixture
    def real_index(self):
        index_path = ROOT / "rag" / "documentation" / "_metadata" / "semantic_index.json"
        if not index_path.exists():
            pytest.skip("Real semantic index not available")
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_minimum_topic_count(self, real_index):
        """Semantic index must have >= 40 topics (P2 target)."""
        # Index is flat format: each key is a topic
        assert len(real_index) >= 40, (
            f"Only {len(real_index)} topics, need >= 40"
        )

    def test_minimum_keyword_count(self, real_index):
        """Semantic index must have >= 600 total keywords (P2 target)."""
        total_keywords = sum(
            len(topic.get("keywords", []))
            for topic in real_index.values()
            if isinstance(topic, dict)
        )
        assert total_keywords >= 600, (
            f"Only {total_keywords} keywords, need >= 600"
        )

    def test_cops_topic_exists(self, real_index):
        """COPs/compositing topic must exist."""
        cops_topics = [k for k in real_index if "cop" in k.lower()]
        assert cops_topics, "No COPs-related topic in semantic index"

    def test_usd_composition_topic_exists(self, real_index):
        """USD composition patterns topic must exist."""
        usd_topics = [k for k in real_index if "usd" in k.lower() and "compos" in k.lower()]
        assert usd_topics, "No USD composition topic in semantic index"

    def test_tops_topic_exists(self, real_index):
        """TOPS/PDG batch processing topic must exist."""
        tops_topics = [k for k in real_index if "tops" in k.lower() or "pdg" in k.lower()]
        assert tops_topics, "No TOPS/PDG topic in semantic index"
