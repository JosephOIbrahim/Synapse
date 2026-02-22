"""
Agent capabilities -- wraps the autonomy pipeline for agent tool-use.

Provides async functions the agent can call to leverage:
- Render planning, evaluation, and prediction
- Pre-flight validation
- Scene inspection and modification
"""

from .render import plan_render, evaluate_render, predict_render, run_autonomous_render
from .validation import validate_scene, check_render_readiness
from .scene import get_scene_summary, find_nodes_by_type, validate_connections

__all__ = [
    "plan_render",
    "evaluate_render",
    "predict_render",
    "run_autonomous_render",
    "validate_scene",
    "check_render_readiness",
    "get_scene_summary",
    "find_nodes_by_type",
    "validate_connections",
]
