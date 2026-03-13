"""
Synapse Recipe Registry -- Tops Recipes

Auto-extracted from the monolith recipes.py.
"""

from .base import Recipe, RecipeStep
from ...core.gates import GateLevel


def register_tops_recipes(registry):
    """Register tops recipes into the given registry."""

    # --- TOPS Parameter Sweep ---
    registry.register(Recipe(
        name="tops_parameter_sweep",
        description=(
            "Set up a wedge parameter sweep and cook it with validation. "
            "Sweeps an attribute from start to end in N steps."
        ),
        triggers=[
            r"^sweep\s+(?P<attr_name>\w+)\s+from\s+(?P<start>[\d.]+)\s+to\s+(?P<end>[\d.]+)(?:\s+in\s+(?P<steps>\d+)\s+steps?)?(?:\s+(?:in|on|at)\s+(?P<topnet>[\w\-./]+))?$",
        ],
        parameters=["attr_name", "start", "end", "steps", "topnet"],
        gate_level=GateLevel.REVIEW,
        category="tops",
        steps=[
            RecipeStep(
                action="tops_setup_wedge",
                payload_template={
                    "topnet_path": "{topnet}",
                    "attributes": [{"name": "{attr_name}", "type": "float",
                                    "start": "{start}", "end": "{end}",
                                    "steps": 10}],
                },
                gate_level=GateLevel.REVIEW,
                output_var="wedge",
            ),
            RecipeStep(
                action="tops_cook_and_validate",
                payload_template={
                    "node": "$wedge.wedge_node",
                    "max_retries": 1,
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="tops_get_cook_stats",
                payload_template={
                    "node": "$wedge.wedge_node",
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- TOPS Quick Cook ---
    registry.register(Recipe(
        name="tops_quick_cook",
        description="Cook a TOP node and validate results with one retry.",
        triggers=[
            r"^(?:cook\s+and\s+check|quick\s+cook)\s+(?P<node>[\w\-./]+)$",
        ],
        parameters=["node"],
        gate_level=GateLevel.REVIEW,
        category="tops",
        steps=[
            RecipeStep(
                action="tops_cook_and_validate",
                payload_template={
                    "node": "{node}",
                    "max_retries": 1,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- TOPS Diagnose ---
    registry.register(Recipe(
        name="tops_diagnose_recipe",
        description="Diagnose failures on a TOP node.",
        triggers=[
            r"^diagnose\s+(?P<node>[\w\-./]+)$",
            r"^what(?:'s|\s+is)\s+wrong\s+with\s+(?P<node>[\w\-./]+)$",
        ],
        parameters=["node"],
        gate_level=GateLevel.REVIEW,
        category="tops",
        steps=[
            RecipeStep(
                action="tops_diagnose",
                payload_template={
                    "node": "{node}",
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- TOPS Workflow Recipes ---

    registry.register(Recipe(
        name="resume_failed_tops_cook",
        description="Dirty failed work items and re-cook a TOP node",
        triggers=[
            r"^(?:re-?)?cook\s+failed\s+(?:items?\s+)?(?:in\s+|on\s+)?(?P<node>.+)$",
            r"^retry\s+failed\s+(?:tops?\s+)?(?:in\s+|on\s+)?(?P<node>.+)$",
            r"^resume\s+(?:failed\s+)?(?:tops?\s+)?cook\s+(?:in\s+|on\s+)?(?P<node>.+)$",
        ],
        parameters=["node"],
        gate_level=GateLevel.REVIEW,
        category="tops",
        steps=[
            RecipeStep(
                action="tops_dirty_node",
                payload_template={"node": "{node}", "dirty_upstream": False},
                gate_level=GateLevel.INFORM,
            ),
            RecipeStep(
                action="tops_cook_node",
                payload_template={"node": "{node}", "block": True},
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    registry.register(Recipe(
        name="tops_monitored_render",
        description="Render a frame sequence via TOPS with live monitoring",
        triggers=[
            r"^render\s+(?:frames?\s+)?(?P<frame_start>\d+)\s*[-\u2013to]+\s*(?P<frame_end>\d+)\s+with\s+monitor(?:ing)?$",
            r"^(?:tops?\s+)?render\s+(?:and\s+)?monitor\s+(?:frames?\s+)?(?P<frame_start>\d+)\s*[-\u2013to]+\s*(?P<frame_end>\d+)$",
            r"^monitored?\s+render\s+(?P<frame_start>\d+)\s*[-\u2013to]+\s*(?P<frame_end>\d+)$",
        ],
        parameters=["frame_start", "frame_end"],
        gate_level=GateLevel.REVIEW,
        category="tops",
        steps=[
            RecipeStep(
                action="tops_render_sequence",
                payload_template={
                    "frame_range": ["{frame_start}", "{frame_end}"],
                    "blocking": False,
                },
                gate_level=GateLevel.REVIEW,
                output_var="render",
            ),
            RecipeStep(
                action="tops_monitor_stream",
                payload_template={
                    "node": "$render.topnet",
                },
                gate_level=GateLevel.INFORM,
            ),
        ],
    ))

