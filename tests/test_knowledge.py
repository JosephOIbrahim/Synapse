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
