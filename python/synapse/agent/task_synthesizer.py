"""
Synthetic Task Environment Generator (v8-DSA)

Generates synthetic test environments for agent evaluation, adapted
from DeepSeek-V3.2's agentic training pipeline (arxiv:2512.02556).

Robustness comes from exposure to diverse task structures, not just
diverse content. This module generates parameterized task environments
with varying complexity, constraints, and failure modes for testing
the agent layer without requiring a live Houdini session.

Phase 1: Standalone generator with deterministic output via seed.
"""

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..core.determinism import DeterministicRandom, deterministic_uuid, round_float


# =============================================================================
# ENUMS
# =============================================================================

class Complexity(Enum):
    """Task complexity levels."""
    MINIMAL = "minimal"         # 1-2 tools, no dependencies
    SIMPLE = "simple"           # 2-4 tools, linear chain
    MODERATE = "moderate"       # 4-8 tools, some branching
    COMPLEX = "complex"         # 8-15 tools, conditional logic
    PRODUCTION = "production"   # 15+ tools, full pipeline


class ConstraintType(Enum):
    """Types of constraints that can be applied to a task."""
    TIME_BUDGET = "time_budget"         # Max execution time in seconds
    QUALITY_FLOOR = "quality_floor"     # Minimum quality threshold
    VRAM_CEILING = "vram_ceiling"       # Max GPU memory in GB
    TOOL_WHITELIST = "tool_whitelist"   # Only these tools allowed
    TOOL_BLACKLIST = "tool_blacklist"   # These tools forbidden
    MAX_RETRIES = "max_retries"         # Max retry attempts


class FailureMode(Enum):
    """Simulated failure modes for robustness testing."""
    NONE = "none"                       # No failure
    MISSING_ASSET = "missing_asset"     # Referenced asset doesn't exist
    INVALID_PARAM = "invalid_param"     # Parameter value out of range
    TIMEOUT = "timeout"                 # Tool call exceeds time limit
    PERMISSION = "permission"           # Gate rejects the operation
    COOK_ERROR = "cook_error"           # Houdini cook fails
    DEPENDENCY = "dependency"           # Upstream node missing


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class TaskConstraint:
    """A single constraint on task execution."""
    constraint_type: ConstraintType
    value: Any
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.constraint_type.value,
            "value": self.value,
            "description": self.description,
        }


@dataclass
class SuccessCriterion:
    """A measurable success criterion for a task."""
    name: str
    check: str       # "exists", "equals", "range", "count"
    target: Any
    weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "check": self.check,
            "target": self.target,
            "weight": round_float(self.weight, 4),
        }


@dataclass
class TaskEnvironment:
    """A synthetic task environment for agent testing.

    Contains everything needed to evaluate an agent's performance
    on a parameterized task without a live Houdini session.
    """
    task_id: str
    description: str
    complexity: Complexity
    constraints: List[TaskConstraint] = field(default_factory=list)
    expected_tool_chain: List[str] = field(default_factory=list)
    success_criteria: List[SuccessCriterion] = field(default_factory=list)
    failure_mode: FailureMode = FailureMode.NONE
    domain: str = "general"
    seed: int = 42

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "complexity": self.complexity.value,
            "constraints": [c.to_dict() for c in self.constraints],
            "expected_tool_chain": list(self.expected_tool_chain),
            "success_criteria": [s.to_dict() for s in self.success_criteria],
            "failure_mode": self.failure_mode.value,
            "domain": self.domain,
            "seed": self.seed,
        }


# =============================================================================
# TASK TEMPLATES
# =============================================================================

_TASK_TEMPLATES: List[Dict[str, Any]] = [
    {
        "description": "Create a simple sphere with a material",
        "complexity": Complexity.MINIMAL,
        "domain": "scene",
        "tools": ["create_node", "create_material"],
        "criteria": [
            SuccessCriterion("node_exists", "exists", "/obj/sphere1"),
            SuccessCriterion("material_bound", "exists", "material"),
        ],
    },
    {
        "description": "Set up three-point lighting rig",
        "complexity": Complexity.SIMPLE,
        "domain": "lighting",
        "tools": [
            "create_usd_prim", "set_usd_attribute",
            "create_usd_prim", "set_usd_attribute",
            "create_usd_prim", "set_usd_attribute",
        ],
        "criteria": [
            SuccessCriterion("key_light", "exists", "/lights/key"),
            SuccessCriterion("fill_light", "exists", "/lights/fill"),
            SuccessCriterion("rim_light", "exists", "/lights/rim"),
            SuccessCriterion("intensity_law", "range", (0.0, 1.0)),
        ],
    },
    {
        "description": "Build a Solaris scene with geometry, materials, and camera",
        "complexity": Complexity.MODERATE,
        "domain": "scene",
        "tools": [
            "create_node", "create_node", "connect_nodes",
            "create_material", "assign_material",
            "create_node", "set_parm",
        ],
        "criteria": [
            SuccessCriterion("geo_exists", "exists", "geometry"),
            SuccessCriterion("material_assigned", "exists", "material"),
            SuccessCriterion("camera_exists", "exists", "camera"),
        ],
    },
    {
        "description": "Full render pipeline: scene, lights, materials, camera, render settings, karma",
        "complexity": Complexity.COMPLEX,
        "domain": "render",
        "tools": [
            "create_node", "create_node", "connect_nodes",
            "create_material", "assign_material",
            "create_usd_prim", "set_usd_attribute",
            "create_usd_prim", "set_usd_attribute",
            "create_node", "set_parm",
            "render_settings", "render",
        ],
        "criteria": [
            SuccessCriterion("render_output", "exists", "picture"),
            SuccessCriterion("camera_set", "exists", "camera"),
            SuccessCriterion("no_black_frame", "equals", True),
        ],
    },
    {
        "description": "Production asset pipeline with TOPS wedging and validation",
        "complexity": Complexity.PRODUCTION,
        "domain": "render",
        "tools": [
            "create_node", "create_node", "create_node", "connect_nodes",
            "create_material", "assign_material",
            "create_usd_prim", "set_usd_attribute",
            "create_usd_prim", "set_usd_attribute",
            "create_usd_prim", "set_usd_attribute",
            "create_node", "set_parm", "set_parm",
            "render_settings",
            "tops_setup_wedge", "tops_cook_node",
            "tops_get_work_items", "tops_get_cook_stats",
            "render",
        ],
        "criteria": [
            SuccessCriterion("wedge_complete", "equals", True),
            SuccessCriterion("all_frames_valid", "equals", True),
            SuccessCriterion("render_count", "count", 5),
        ],
    },
]

# Constraint templates per complexity
_CONSTRAINT_TEMPLATES: Dict[Complexity, List[TaskConstraint]] = {
    Complexity.MINIMAL: [
        TaskConstraint(ConstraintType.TIME_BUDGET, 10, "Complete in 10 seconds"),
    ],
    Complexity.SIMPLE: [
        TaskConstraint(ConstraintType.TIME_BUDGET, 30, "Complete in 30 seconds"),
        TaskConstraint(ConstraintType.QUALITY_FLOOR, 0.8, "80% quality minimum"),
    ],
    Complexity.MODERATE: [
        TaskConstraint(ConstraintType.TIME_BUDGET, 60, "Complete in 60 seconds"),
        TaskConstraint(ConstraintType.QUALITY_FLOOR, 0.8, "80% quality minimum"),
        TaskConstraint(ConstraintType.MAX_RETRIES, 2, "Max 2 retries"),
    ],
    Complexity.COMPLEX: [
        TaskConstraint(ConstraintType.TIME_BUDGET, 120, "Complete in 120 seconds"),
        TaskConstraint(ConstraintType.QUALITY_FLOOR, 0.9, "90% quality minimum"),
        TaskConstraint(ConstraintType.VRAM_CEILING, 8, "Max 8GB VRAM"),
        TaskConstraint(ConstraintType.MAX_RETRIES, 3, "Max 3 retries"),
    ],
    Complexity.PRODUCTION: [
        TaskConstraint(ConstraintType.TIME_BUDGET, 300, "Complete in 5 minutes"),
        TaskConstraint(ConstraintType.QUALITY_FLOOR, 0.95, "95% quality minimum"),
        TaskConstraint(ConstraintType.VRAM_CEILING, 16, "Max 16GB VRAM"),
        TaskConstraint(ConstraintType.MAX_RETRIES, 3, "Max 3 retries"),
    ],
}


# =============================================================================
# TASK SYNTHESIZER
# =============================================================================

class TaskSynthesizer:
    """Generates synthetic task environments for agent evaluation.

    Uses a deterministic random generator seeded for reproducibility.
    Generated tasks span all complexity levels and failure modes.
    """

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = DeterministicRandom(seed)
        self._generated_count = 0

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def generated_count(self) -> int:
        return self._generated_count

    def generate(
        self,
        n: int = 10,
        complexity: Optional[Complexity] = None,
        failure_mode: Optional[FailureMode] = None,
        domain: Optional[str] = None,
        diversity_threshold: float = 0.5,
    ) -> List[TaskEnvironment]:
        """Generate n synthetic task environments.

        Args:
            n: Number of tasks to generate.
            complexity: If set, only generate tasks of this complexity.
            failure_mode: If set, apply this failure mode to all tasks.
            domain: If set, only generate tasks in this domain.
            diversity_threshold: Minimum diversity score (0-1).
                Higher values force more variation across generated tasks.

        Returns:
            List of TaskEnvironment instances.
        """
        tasks: List[TaskEnvironment] = []
        seen_templates: List[int] = []

        for i in range(n):
            # Pick a template
            candidates = list(range(len(_TASK_TEMPLATES)))

            # Filter by complexity
            if complexity is not None:
                candidates = [
                    j for j in candidates
                    if _TASK_TEMPLATES[j]["complexity"] == complexity
                ]

            # Filter by domain
            if domain is not None:
                candidates = [
                    j for j in candidates
                    if _TASK_TEMPLATES[j]["domain"] == domain
                ]

            if not candidates:
                candidates = list(range(len(_TASK_TEMPLATES)))

            # Diversity: prefer unseen templates
            if diversity_threshold > 0 and seen_templates:
                unseen = [j for j in candidates if j not in seen_templates]
                if unseen and self._rng.random() < diversity_threshold:
                    candidates = unseen

            idx = self._rng.choice(candidates)
            seen_templates.append(idx)
            template = _TASK_TEMPLATES[idx]

            # Build task
            task_complexity = template["complexity"]
            if complexity is not None:
                task_complexity = complexity

            fm = failure_mode if failure_mode is not None else FailureMode.NONE
            if failure_mode is None and self._rng.random() < 0.2:
                # 20% chance of random failure mode
                modes = list(FailureMode)
                fm = self._rng.choice(modes)

            task_seed = self._seed + i
            task_id = deterministic_uuid(
                f"synth:{task_seed}:{i}:{template['description'][:20]}",
                "task",
            )

            constraints = list(_CONSTRAINT_TEMPLATES.get(
                task_complexity, []
            ))

            env = TaskEnvironment(
                task_id=task_id,
                description=template["description"],
                complexity=task_complexity,
                constraints=constraints,
                expected_tool_chain=list(template["tools"]),
                success_criteria=list(template.get("criteria", [])),
                failure_mode=fm,
                domain=template["domain"],
                seed=task_seed,
            )
            tasks.append(env)
            self._generated_count += 1

        return tasks

    def generate_for_complexity(
        self, complexity: Complexity, n: int = 5
    ) -> List[TaskEnvironment]:
        """Generate tasks targeting a specific complexity level."""
        return self.generate(n=n, complexity=complexity)

    def generate_failure_suite(self) -> List[TaskEnvironment]:
        """Generate one task per failure mode for robustness testing."""
        tasks: List[TaskEnvironment] = []
        for fm in FailureMode:
            generated = self.generate(n=1, failure_mode=fm)
            if generated:
                tasks.append(generated[0])
        return tasks

    def reset(self, seed: Optional[int] = None) -> None:
        """Reset the generator state."""
        if seed is not None:
            self._seed = seed
        self._rng.reset(self._seed)
        self._generated_count = 0
