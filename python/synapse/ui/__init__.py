"""
Synapse UI - Qt Panel Interface

UI components for the unified Synapse panel.
"""

try:
    from .panel import SynapsePanel, create_panel
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    SynapsePanel = None  # type: ignore[assignment,misc]
    create_panel = None  # type: ignore[assignment]

# Backwards compatibility
NexusPanel = SynapsePanel

__all__ = [
    'SynapsePanel',
    'NexusPanel',
    'create_panel',
    'UI_AVAILABLE',
]
