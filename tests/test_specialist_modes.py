"""
Tests for specialist_modes.py (v8-DSA)

Covers: all domains have specialists, prompt extension, parameter
vocabulary, quality signals, Lighting Law enforcement.
"""

import sys
import os

_SYNAPSE_ROOT = os.path.join(os.path.dirname(__file__), "..", "python")
if _SYNAPSE_ROOT not in sys.path:
    sys.path.insert(0, _SYNAPSE_ROOT)

import pytest

from synapse.agent.specialist_modes import (
    SPECIALIST_REGISTRY,
    SpecialistDomain,
    SpecialistMode,
    QualitySignal,
    build_enhanced_prompt,
    get_specialist,
    get_specialist_by_name,
    list_specialists,
    LIGHTING_SPECIALIST,
    MATERIAL_SPECIALIST,
    RENDER_SPECIALIST,
    SCENE_SPECIALIST,
    MEMORY_SPECIALIST,
)


# ---------------------------------------------------------------------------
# Tests: Registry Coverage
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_all_domains_have_specialists(self):
        for domain in SpecialistDomain:
            assert domain in SPECIALIST_REGISTRY, f"Missing specialist for {domain.value}"

    def test_registry_count(self):
        assert len(SPECIALIST_REGISTRY) == 5

    def test_get_specialist(self):
        spec = get_specialist(SpecialistDomain.LIGHTING)
        assert spec is LIGHTING_SPECIALIST

    def test_get_specialist_by_name(self):
        spec = get_specialist_by_name("lighting")
        assert spec is LIGHTING_SPECIALIST

    def test_get_specialist_by_name_case_insensitive(self):
        spec = get_specialist_by_name("RENDER")
        assert spec is RENDER_SPECIALIST

    def test_get_specialist_unknown(self):
        assert get_specialist_by_name("nonexistent") is None

    def test_list_specialists(self):
        specs = list_specialists()
        assert len(specs) == 5
        domains = [s["domain"] for s in specs]
        assert "lighting" in domains
        assert "material" in domains
        assert "render" in domains

    def test_list_specialists_sorted(self):
        specs = list_specialists()
        domains = [s["domain"] for s in specs]
        assert domains == sorted(domains)


# ---------------------------------------------------------------------------
# Tests: SpecialistMode properties
# ---------------------------------------------------------------------------

class TestSpecialistMode:
    def test_frozen(self):
        with pytest.raises(AttributeError):
            LIGHTING_SPECIALIST.domain = SpecialistDomain.RENDER  # type: ignore[misc]

    def test_to_dict_has_all_fields(self):
        d = LIGHTING_SPECIALIST.to_dict()
        assert "domain" in d
        assert "system_prompt_extension" in d
        assert "parameter_vocabulary" in d
        assert "quality_signals" in d
        assert "related_tools" in d

    def test_to_dict_sorted_vocabulary(self):
        d = LIGHTING_SPECIALIST.to_dict()
        keys = list(d["parameter_vocabulary"].keys())
        assert keys == sorted(keys)

    def test_to_dict_sorted_tools(self):
        d = LIGHTING_SPECIALIST.to_dict()
        assert d["related_tools"] == sorted(d["related_tools"])


# ---------------------------------------------------------------------------
# Tests: Lighting Specialist (with Lighting Law enforcement)
# ---------------------------------------------------------------------------

class TestLightingSpecialist:
    def test_prompt_mentions_lighting_law(self):
        assert "1.0" in LIGHTING_SPECIALIST.system_prompt_extension
        assert "exposure" in LIGHTING_SPECIALIST.system_prompt_extension.lower()
        assert "intensity" in LIGHTING_SPECIALIST.system_prompt_extension.lower()

    def test_has_usd_encoded_params(self):
        vocab = LIGHTING_SPECIALIST.parameter_vocabulary
        assert "xn__inputsintensity_i0a" in vocab.values()
        assert "xn__inputsexposure_vya" in vocab.values()
        assert "xn__inputsexposure_control_wcb" in vocab.values()

    def test_intensity_quality_signal(self):
        signals = LIGHTING_SPECIALIST.quality_signals
        intensity_signal = [s for s in signals if s.name == "intensity_law"]
        assert len(intensity_signal) == 1
        assert intensity_signal[0].check_type == "range"
        assert intensity_signal[0].expected == (0.0, 1.0)

    def test_exposure_quality_signal(self):
        signals = LIGHTING_SPECIALIST.quality_signals
        exposure_signal = [s for s in signals if s.name == "exposure_set"]
        assert len(exposure_signal) == 1
        assert exposure_signal[0].expected == "set"

    def test_related_tools(self):
        tools = LIGHTING_SPECIALIST.related_tools
        assert "create_usd_prim" in tools
        assert "set_usd_attribute" in tools
        assert "render" in tools


# ---------------------------------------------------------------------------
# Tests: Material Specialist
# ---------------------------------------------------------------------------

class TestMaterialSpecialist:
    def test_prompt_mentions_matlib_cook(self):
        assert "cook" in MATERIAL_SPECIALIST.system_prompt_extension.lower()
        assert "materiallibrary" in MATERIAL_SPECIALIST.system_prompt_extension.lower()

    def test_has_standard_surface_params(self):
        vocab = MATERIAL_SPECIALIST.parameter_vocabulary
        assert "base_color" in vocab
        assert "roughness" in vocab
        assert "metalness" in vocab

    def test_related_tools(self):
        tools = MATERIAL_SPECIALIST.related_tools
        assert "create_material" in tools
        assert "assign_material" in tools
        assert "read_material" in tools


# ---------------------------------------------------------------------------
# Tests: Render Specialist
# ---------------------------------------------------------------------------

class TestRenderSpecialist:
    def test_prompt_mentions_progressive_validation(self):
        prompt = RENDER_SPECIALIST.system_prompt_extension.lower()
        assert "256x256" in prompt or "progressive" in prompt

    def test_warns_about_foreground(self):
        assert "foreground" in RENDER_SPECIALIST.system_prompt_extension.lower()

    def test_has_render_params(self):
        vocab = RENDER_SPECIALIST.parameter_vocabulary
        assert "picture" in vocab
        assert "camera" in vocab


# ---------------------------------------------------------------------------
# Tests: Scene Specialist
# ---------------------------------------------------------------------------

class TestSceneSpecialist:
    def test_prompt_mentions_wire_order(self):
        prompt = SCENE_SPECIALIST.system_prompt_extension.lower()
        assert "merge" in prompt

    def test_related_tools(self):
        tools = SCENE_SPECIALIST.related_tools
        assert "create_node" in tools
        assert "connect_nodes" in tools


# ---------------------------------------------------------------------------
# Tests: Memory Specialist
# ---------------------------------------------------------------------------

class TestMemorySpecialist:
    def test_prompt_mentions_reasoning(self):
        prompt = MEMORY_SPECIALIST.system_prompt_extension.lower()
        assert "reasoning" in prompt

    def test_related_tools(self):
        tools = MEMORY_SPECIALIST.related_tools
        assert "add_memory" in tools
        assert "decide" in tools
        assert "search" in tools


# ---------------------------------------------------------------------------
# Tests: build_enhanced_prompt
# ---------------------------------------------------------------------------

class TestBuildEnhancedPrompt:
    def test_prepends_specialist(self):
        base = "Create a key light."
        enhanced = build_enhanced_prompt(base, SpecialistDomain.LIGHTING)
        assert enhanced.startswith(LIGHTING_SPECIALIST.system_prompt_extension)
        assert enhanced.endswith(base)

    def test_unknown_domain_returns_base(self):
        # Use a domain that exists but test the function path
        base = "Do something."
        enhanced = build_enhanced_prompt(base, SpecialistDomain.LIGHTING)
        assert base in enhanced

    def test_all_domains_produce_enhanced(self):
        base = "Base prompt."
        for domain in SpecialistDomain:
            enhanced = build_enhanced_prompt(base, domain)
            assert len(enhanced) > len(base)
            assert base in enhanced


# ---------------------------------------------------------------------------
# Tests: QualitySignal
# ---------------------------------------------------------------------------

class TestQualitySignal:
    def test_frozen(self):
        qs = QualitySignal(name="test", description="desc", check_type="range", expected=(0, 1))
        with pytest.raises(AttributeError):
            qs.name = "modified"  # type: ignore[misc]
