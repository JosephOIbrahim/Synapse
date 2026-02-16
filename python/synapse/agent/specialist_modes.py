"""
Domain Specialist Modes (v8-DSA)

Configures domain-specific specialist behaviors for the agent layer,
adapted from DeepSeek-V3.2's expert selection pattern (arxiv:2512.02556).

Each specialist mode provides:
- System prompt extensions with domain expertise
- Parameter vocabulary (canonical names, encoded USD names)
- Quality signals for validating tool outputs

Specialists don't change routing — they enhance the agent's context
when a domain is detected. Phase 1: standalone definitions only.

Lighting Law enforced: intensity always 1.0, brightness via exposure.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Sequence


# =============================================================================
# SPECIALIST MODE
# =============================================================================

class SpecialistDomain(Enum):
    """Available specialist domains."""
    LIGHTING = "lighting"
    MATERIAL = "material"
    RENDER = "render"
    SCENE = "scene"
    MEMORY = "memory"


@dataclass(frozen=True)
class QualitySignal:
    """A measurable quality indicator for domain output validation."""
    name: str
    description: str
    check_type: str   # "range", "exists", "equals", "pattern"
    expected: Any     # Expected value or range tuple


@dataclass(frozen=True)
class SpecialistMode:
    """Domain-specific specialist configuration.

    Frozen dataclass — specialist definitions are immutable once created.
    """
    domain: SpecialistDomain
    system_prompt_extension: str
    parameter_vocabulary: Dict[str, str]   # friendly_name -> USD/Houdini parm
    quality_signals: tuple                  # Tuple of QualitySignal (frozen)
    related_tools: FrozenSet[str]          # Tools commonly used in this domain

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain.value,
            "system_prompt_extension": self.system_prompt_extension,
            "parameter_vocabulary": dict(sorted(self.parameter_vocabulary.items())),
            "quality_signals": [
                {
                    "name": qs.name,
                    "description": qs.description,
                    "check_type": qs.check_type,
                    "expected": qs.expected,
                }
                for qs in self.quality_signals
            ],
            "related_tools": sorted(self.related_tools),
        }


# =============================================================================
# BUILT-IN SPECIALISTS
# =============================================================================

LIGHTING_SPECIALIST = SpecialistMode(
    domain=SpecialistDomain.LIGHTING,
    system_prompt_extension=(
        "You are a lighting specialist for Solaris/Karma in Houdini. "
        "LIGHTING LAW: Intensity is ALWAYS 1.0 — brightness is controlled "
        "by exposure (logarithmic, in stops). Never set intensity above 1.0. "
        "Key:fill ratio 3:1 = 1.585 stops, 4:1 = 2.0 stops. "
        "Always use HDRI on dome lights. Enable color temperature for "
        "natural warmth on key lights. Dome exposure ~0.25 for studio HDRIs."
    ),
    parameter_vocabulary={
        "intensity": "xn__inputsintensity_i0a",
        "intensity_control": "xn__inputsintensity_control_r0b",
        "exposure": "xn__inputsexposure_vya",
        "exposure_control": "xn__inputsexposure_control_wcb",
        "color": "xn__inputscolor_vya",
        "color_control": "xn__inputscolor_control_wcb",
        "color_temperature": "xn__inputscolortemperature_ica",
        "color_temperature_control": "xn__inputscolortemperature_control_jdb",
        "texture_file": "xn__inputstexturefile_i1a",
        "texture_file_control": "xn__inputstexturefile_control_j2b",
        "normalize": "xn__inputsnormalize_01a",
    },
    quality_signals=(
        QualitySignal(
            name="intensity_law",
            description="Light intensity must be 1.0 or below",
            check_type="range",
            expected=(0.0, 1.0),
        ),
        QualitySignal(
            name="exposure_set",
            description="Exposure control must be explicitly set",
            check_type="equals",
            expected="set",
        ),
        QualitySignal(
            name="dome_has_hdri",
            description="Dome lights should have an HDRI texture",
            check_type="exists",
            expected="texture_file",
        ),
    ),
    related_tools=frozenset({
        "create_usd_prim",
        "set_usd_attribute",
        "get_usd_attribute",
        "set_keyframe",
        "render",
        "capture_viewport",
    }),
)

MATERIAL_SPECIALIST = SpecialistMode(
    domain=SpecialistDomain.MATERIAL,
    system_prompt_extension=(
        "You are a material specialist for Solaris/Karma MaterialX workflows. "
        "Use mtlxstandard_surface as the default shader. Always cook the "
        "materiallibrary before creating shader children (matlib.cook(force=True)). "
        "Material prim patterns must match exact USD prim paths — not wildcards. "
        "Keep material assignments inside the matlib node, not as separate assign nodes."
    ),
    parameter_vocabulary={
        "base_color": "base_color",
        "metalness": "metalness",
        "roughness": "specular_roughness",
        "ior": "specular_IOR",
        "opacity": "opacity",
        "emission": "emission",
        "emission_color": "emission_color",
        "normal": "normal",
        "coat": "coat",
        "coat_roughness": "coat_roughness",
        "subsurface": "subsurface",
        "subsurface_color": "subsurface_color",
    },
    quality_signals=(
        QualitySignal(
            name="roughness_range",
            description="Roughness should be 0.0-1.0",
            check_type="range",
            expected=(0.0, 1.0),
        ),
        QualitySignal(
            name="metalness_binary",
            description="Metalness should be 0.0 or 1.0 for PBR correctness",
            check_type="pattern",
            expected="0.0|1.0",
        ),
        QualitySignal(
            name="matlib_cooked",
            description="Material library must be cooked before child creation",
            check_type="exists",
            expected="cook_step",
        ),
    ),
    related_tools=frozenset({
        "create_material",
        "assign_material",
        "read_material",
        "execute_python",
        "create_usd_prim",
    }),
)

RENDER_SPECIALIST = SpecialistMode(
    domain=SpecialistDomain.RENDER,
    system_prompt_extension=(
        "You are a render specialist for Karma XPU/CPU in Houdini Solaris. "
        "Follow progressive validation: test at 256x256 low samples first, "
        "then scale up. Set picture on Karma LOP AND outputimage on ROP. "
        "Never use soho_foreground=1 for heavy scenes — it blocks Houdini. "
        "Use iconvert.exe from $HFS/bin/ for EXR-to-JPEG preview conversion."
    ),
    parameter_vocabulary={
        "resolution": "res",
        "pixel_samples": "karma_pixelsamples",
        "denoiser": "karma_denoiser",
        "picture": "picture",
        "output_image": "outputimage",
        "camera": "camera",
        "override_resolution": "override_res",
        "lop_path": "loppath",
        "foreground": "soho_foreground",
    },
    quality_signals=(
        QualitySignal(
            name="output_path_set",
            description="Render output path must be configured",
            check_type="exists",
            expected="picture",
        ),
        QualitySignal(
            name="camera_assigned",
            description="Camera must be assigned to render settings",
            check_type="exists",
            expected="camera",
        ),
        QualitySignal(
            name="not_foreground",
            description="Heavy renders should not block Houdini",
            check_type="equals",
            expected=0,
        ),
    ),
    related_tools=frozenset({
        "render",
        "render_settings",
        "capture_viewport",
        "execute_python",
        "get_parm",
        "set_parm",
    }),
)

SCENE_SPECIALIST = SpecialistMode(
    domain=SpecialistDomain.SCENE,
    system_prompt_extension=(
        "You are a scene assembly specialist for Houdini Solaris. "
        "Use Asset Reference nodes for production geometry — not inline prims. "
        "Houdini ships test assets at $HFS/houdini/usd/assets/ (rubbertoy, pig). "
        "Wire order in merge: geometry first, then lights, then referenced assets. "
        "Clean chain: merge -> matlib -> camera -> render_settings -> karma. "
        "No orphan assign nodes."
    ),
    parameter_vocabulary={
        "node_type": "type",
        "node_name": "name",
        "parent": "parent",
        "translate": "t",
        "rotate": "r",
        "scale": "s",
        "display_flag": "display",
        "render_flag": "render",
    },
    quality_signals=(
        QualitySignal(
            name="no_orphan_assigns",
            description="Material assignments should be inside matlib",
            check_type="pattern",
            expected="materiallibrary",
        ),
        QualitySignal(
            name="merge_order",
            description="Merge should wire geo before lights",
            check_type="pattern",
            expected="geo,lights,refs",
        ),
    ),
    related_tools=frozenset({
        "create_node",
        "delete_node",
        "connect_nodes",
        "get_parm",
        "set_parm",
        "get_scene_info",
        "get_selection",
        "inspect_scene",
        "inspect_node",
    }),
)

MEMORY_SPECIALIST = SpecialistMode(
    domain=SpecialistDomain.MEMORY,
    system_prompt_extension=(
        "You are a memory and context specialist for Synapse project memory. "
        "Use decisions for recording choices with reasoning. Use notes for "
        "observations and insights. Tag entries for retrieval. Memory entries "
        "are append-only JSONL with async write buffering. Always include "
        "reasoning when recording decisions — future sessions depend on it."
    ),
    parameter_vocabulary={
        "memory_content": "content",
        "memory_type": "memory_type",
        "tags": "tags",
        "decision": "decision",
        "reasoning": "reasoning",
        "alternatives": "alternatives",
        "query": "query",
    },
    quality_signals=(
        QualitySignal(
            name="decision_has_reasoning",
            description="Decisions must include reasoning",
            check_type="exists",
            expected="reasoning",
        ),
        QualitySignal(
            name="entries_tagged",
            description="Memory entries should have tags for retrieval",
            check_type="exists",
            expected="tags",
        ),
    ),
    related_tools=frozenset({
        "add_memory",
        "decide",
        "context",
        "search",
        "recall",
    }),
)


# =============================================================================
# REGISTRY
# =============================================================================

SPECIALIST_REGISTRY: Dict[SpecialistDomain, SpecialistMode] = {
    SpecialistDomain.LIGHTING: LIGHTING_SPECIALIST,
    SpecialistDomain.MATERIAL: MATERIAL_SPECIALIST,
    SpecialistDomain.RENDER: RENDER_SPECIALIST,
    SpecialistDomain.SCENE: SCENE_SPECIALIST,
    SpecialistDomain.MEMORY: MEMORY_SPECIALIST,
}


def get_specialist(domain: SpecialistDomain) -> Optional[SpecialistMode]:
    """Get the specialist mode for a domain."""
    return SPECIALIST_REGISTRY.get(domain)


def get_specialist_by_name(name: str) -> Optional[SpecialistMode]:
    """Get specialist by domain name string."""
    try:
        domain = SpecialistDomain(name.lower())
        return SPECIALIST_REGISTRY.get(domain)
    except ValueError:
        return None


def build_enhanced_prompt(
    base_prompt: str,
    domain: SpecialistDomain,
) -> str:
    """Extend a base prompt with specialist domain knowledge.

    Args:
        base_prompt: The original system/user prompt.
        domain: Which specialist to activate.

    Returns:
        Enhanced prompt with specialist context prepended.
    """
    specialist = SPECIALIST_REGISTRY.get(domain)
    if specialist is None:
        return base_prompt
    return f"{specialist.system_prompt_extension}\n\n{base_prompt}"


def list_specialists() -> List[Dict[str, Any]]:
    """List all registered specialists with their metadata."""
    return [
        spec.to_dict()
        for spec in sorted(
            SPECIALIST_REGISTRY.values(),
            key=lambda s: s.domain.value,
        )
    ]
