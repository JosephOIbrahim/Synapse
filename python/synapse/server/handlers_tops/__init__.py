"""
Synapse TOPS/PDG Handler Mixin

Split from the monolith handlers_tops.py into focused submodules.
This __init__.py re-exports TopsHandlerMixin for backward compatibility.
"""

from ._common import (
    HOU_AVAILABLE, _run_in_main_thread_pdg, _ensure_tops_warm_standby,
    _MAX_MONITOR_EVENTS,
)
from ...core.determinism import round_float, kahan_sum, deterministic_uuid
from ...core.aliases import resolve_param, resolve_param_with_default
from ..handler_helpers import _HOUDINI_UNAVAILABLE

try:
    import hou
except ImportError:
    HOU_AVAILABLE = False

from .cook import TopsCookMixin
from .work_items import TopsWorkItemsMixin
from .wedge import TopsWedgeMixin
from .diagnostics import TopsDiagnosticsMixin
from .render_sequence import TopsRenderSequenceMixin


class TopsHandlerMixin(
    TopsCookMixin,
    TopsWorkItemsMixin,
    TopsWedgeMixin,
    TopsDiagnosticsMixin,
    TopsRenderSequenceMixin,
):
    """Combined TOPS/PDG handler mixin.

    Composes all TOPS handler sub-mixins into a single class for
    backward-compatible use in SynapseHandler.
    """
    pass


__all__ = ["TopsHandlerMixin"]
