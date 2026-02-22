"""
Synapse Render Diagnostics

Maps validation issues to remedies and integrates with memory for
learned fixes. The recursive self-improvement loop: diagnose -> fix ->
record -> recall.

Scene classification tags enable cross-shot learning: "all cave shots
need 128 samples" instead of fixing each shot independently.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..memory.models import MemoryType, MemoryQuery

logger = logging.getLogger("synapse.render_farm")


# =========================================================================
# Remedy definitions
# =========================================================================

@dataclass
class Remedy:
    """A parameter adjustment that may fix a validation issue."""
    issue_type: str           # Validation check name (e.g. "saturation")
    description: str          # Human-readable explanation
    parm_name: str            # Render settings parameter to adjust
    adjust_fn: str            # How to compute the new value: "multiply", "add", "set"
    adjust_value: float       # Multiplier, addend, or absolute value
    max_value: Optional[float] = None  # Cap to prevent runaway values
    confidence: float = 0.5   # How likely this fix resolves the issue (0-1)
    priority: int = 0         # Higher = tried first among same-issue remedies

    def compute_new_value(self, current: float) -> float:
        """Compute the adjusted parameter value."""
        if self.adjust_fn == "multiply":
            new = current * self.adjust_value
        elif self.adjust_fn == "add":
            new = current + self.adjust_value
        elif self.adjust_fn == "set":
            new = self.adjust_value
        else:
            new = current
        if self.max_value is not None:
            new = min(new, self.max_value)
        return new


# Default remedies for each validation issue type.
# Ordered by priority (highest first). The orchestrator tries them
# in order, stopping after the first successful re-render.
ISSUE_REMEDIES: Dict[str, List[Remedy]] = {
    "saturation": [
        Remedy(
            issue_type="saturation",
            description="Double pixel samples to reduce fireflies",
            parm_name="pathtracedsamples",
            adjust_fn="multiply",
            adjust_value=2.0,
            max_value=256,
            confidence=0.9,
            priority=10,
        ),
        Remedy(
            issue_type="saturation",
            description="Tighten color limit clamp to suppress fireflies",
            parm_name="colorlimit",
            adjust_fn="multiply",
            adjust_value=0.5,
            confidence=0.7,
            priority=8,
        ),
        Remedy(
            issue_type="saturation",
            description="Lower max diffuse bounce depth to reduce firefly sources",
            parm_name="diffuselimit",
            adjust_fn="set",
            adjust_value=2,
            confidence=0.5,
            priority=5,
        ),
    ],
    "black_frame": [
        Remedy(
            issue_type="black_frame",
            description="Double pixel samples for underlit scene",
            parm_name="pathtracedsamples",
            adjust_fn="multiply",
            adjust_value=2.0,
            max_value=256,
            confidence=0.8,
            priority=10,
        ),
    ],
    "nan_check": [
        Remedy(
            issue_type="nan_check",
            description="Tighten color limit clamp to contain NaN propagation",
            parm_name="colorlimit",
            adjust_fn="set",
            adjust_value=10.0,
            confidence=0.7,
            priority=10,
        ),
    ],
    "clipping": [
        Remedy(
            issue_type="clipping",
            description="Tighten color limit to prevent clipping",
            parm_name="colorlimit",
            adjust_fn="multiply",
            adjust_value=0.5,
            confidence=0.7,
            priority=10,
        ),
    ],
    "underexposure": [
        Remedy(
            issue_type="underexposure",
            description="Double pixel samples for underexposed scene",
            parm_name="pathtracedsamples",
            adjust_fn="multiply",
            adjust_value=2.0,
            max_value=256,
            confidence=0.8,
            priority=10,
        ),
    ],
}


# =========================================================================
# Scene classification
# =========================================================================

# Keywords in USD prim types/names that suggest scene characteristics.
_SCENE_TAG_RULES = {
    "interior": ["room", "interior", "indoor", "cave", "tunnel", "corridor"],
    "outdoor": ["outdoor", "exterior", "sky", "terrain", "landscape"],
    "many_lights": [],  # detected by count, not keywords
    "has_environment": ["domelight", "dome_light", "env_light", "hdri"],
    "has_volumes": ["volume", "vdb", "fog", "smoke", "pyro", "cloud"],
    "high_poly": [],  # detected by prim count, not keywords
}


def classify_scene(stage_info: Dict) -> List[str]:
    """Classify a USD stage into scene-type tags for cross-shot learning.

    Args:
        stage_info: Response from get_stage_info handler. Expected keys:
            - prims: list of {"path": str, "type": str} dicts
            - (optional) prim_count: int

    Returns:
        Sorted list of scene tags (e.g. ["has_environment", "interior"]).
    """
    tags: List[str] = []
    prims = stage_info.get("prims", [])
    prim_count = stage_info.get("prim_count", len(prims))

    # Collect all prim paths and types as lowercase for keyword matching
    all_text = []
    light_count = 0
    for p in prims:
        path = (p.get("path") or "").lower()
        ptype = (p.get("type") or "").lower()
        all_text.append(path)
        all_text.append(ptype)
        if "light" in ptype:
            light_count += 1

    joined = " ".join(all_text)

    # Keyword-based tags
    for tag, keywords in sorted(_SCENE_TAG_RULES.items()):
        if not keywords:
            continue
        if any(kw in joined for kw in keywords):
            tags.append(tag)

    # Count-based tags
    if light_count >= 5:
        tags.append("many_lights")
    if prim_count > 50000:
        tags.append("high_poly")

    return sorted(dict.fromkeys(tags))


# =========================================================================
# Memory-assisted diagnosis
# =========================================================================

def query_known_fixes(
    memory,
    issue_type: str,
    scene_tags: List[str],
    limit: int = 5,
) -> List[Dict]:
    """Search memory for past successful fixes matching the issue and scene.

    Args:
        memory: SynapseMemory instance.
        issue_type: The validation check that failed (e.g. "saturation").
        scene_tags: Scene classification tags.
        limit: Max results.

    Returns:
        List of memory dicts with content and confidence, sorted by
        relevance (best match first).
    """
    if memory is None:
        return []

    search_tags = ["render_fix", "success", issue_type]
    # Add scene tags to improve match quality
    search_tags.extend(scene_tags[:3])

    query = MemoryQuery(
        text=f"render fix for {issue_type}",
        memory_types=[MemoryType.FEEDBACK],
        tags=search_tags,
        limit=limit,
    )

    try:
        results = memory.store.search(query)
    except Exception:
        logger.debug("Memory query failed for render fixes", exc_info=True)
        return []

    return [
        {
            "content": r.memory.content,
            "tags": r.memory.tags,
            "score": r.score,
            "memory_id": r.memory.id,
        }
        for r in results
        if "success" in r.memory.tags
    ]


def diagnose_issues(
    validation_result: Dict,
    memory=None,
    scene_tags: Optional[List[str]] = None,
) -> List[Tuple[str, Remedy, Optional[Dict]]]:
    """Diagnose validation failures and return remedies.

    For each failed check, returns the best remedy — either from memory
    (if a past fix is known) or from the default ISSUE_REMEDIES table.

    Args:
        validation_result: Response from validate_frame handler.
            Expected: {"valid": bool, "checks": {check_name: {"passed": bool, ...}}}
        memory: Optional SynapseMemory for learned-fix lookup.
        scene_tags: Optional scene classification tags.

    Returns:
        List of (issue_type, remedy, memory_match_or_None) tuples,
        sorted by remedy priority (highest first).
    """
    if scene_tags is None:
        scene_tags = []

    checks = validation_result.get("checks", {})
    diagnostics: List[Tuple[str, Remedy, Optional[Dict]]] = []

    for check_name in sorted(checks.keys()):
        check = checks[check_name]
        if check.get("passed", True):
            continue

        # Try memory first
        known_fixes = []
        if memory is not None:
            known_fixes = query_known_fixes(memory, check_name, scene_tags)

        # Get default remedies for this issue type
        default_remedies = ISSUE_REMEDIES.get(check_name, [])

        if known_fixes and default_remedies:
            # Memory match found — use the highest-priority default remedy
            # but flag the memory match for context
            best_remedy = sorted(
                default_remedies, key=lambda r: r.priority, reverse=True
            )[0]
            diagnostics.append((check_name, best_remedy, known_fixes[0]))
        elif default_remedies:
            # No memory match — use default remedies in priority order
            best_remedy = sorted(
                default_remedies, key=lambda r: r.priority, reverse=True
            )[0]
            diagnostics.append((check_name, best_remedy, None))
        else:
            # No remedy known for this check type — skip
            logger.warning(
                "No remedy available for validation issue: %s", check_name
            )

    # Sort by remedy priority (highest first)
    diagnostics.sort(key=lambda d: d[1].priority, reverse=True)
    return diagnostics


def record_fix_outcome(
    memory,
    issue_type: str,
    remedy: Remedy,
    success: bool,
    scene_tags: List[str],
    settings_applied: Dict,
    frame: int = 0,
):
    """Record a fix attempt in memory for future learning.

    Args:
        memory: SynapseMemory instance.
        issue_type: The validation issue that was addressed.
        remedy: The remedy that was applied.
        success: Whether the re-render passed validation.
        scene_tags: Scene classification tags.
        settings_applied: The actual parameter values set.
        frame: Frame number (for context).
    """
    if memory is None:
        return

    result_word = "Success" if success else "Failure"
    content = (
        f"**Render Fix:** {result_word}\n"
        f"**Issue:** {issue_type}\n"
        f"**Remedy:** {remedy.description}\n"
        f"**Parameter:** {remedy.parm_name} = {settings_applied.get(remedy.parm_name, '?')}\n"
        f"**Frame:** {frame}\n"
        f"**Scene Tags:** {', '.join(scene_tags)}"
    )

    tags = [
        "render_fix",
        "success" if success else "failure",
        issue_type,
        *scene_tags[:5],
    ]
    # Sort tags for He2025 determinism
    tags = sorted(dict.fromkeys(tags))

    keywords = [
        "render", "fix", issue_type, remedy.parm_name,
        *scene_tags[:3],
    ]
    keywords = sorted(dict.fromkeys(keywords))

    try:
        memory.add(
            content=content,
            memory_type=MemoryType.FEEDBACK,
            tags=tags,
            keywords=keywords,
            source="auto",
        )
    except Exception:
        logger.debug("Failed to record fix outcome in memory", exc_info=True)
