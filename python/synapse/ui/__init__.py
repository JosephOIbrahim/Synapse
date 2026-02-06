"""
Synapse UI - Qt Panel Interface

UI components for the unified Synapse panel.
"""

try:
    from .panel import SynapsePanel, create_panel
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    SynapsePanel = None
    create_panel = None

# Backwards compatibility
NexusPanel = SynapsePanel

__all__ = [
    'SynapsePanel',
    'NexusPanel',
    'create_panel',
    'UI_AVAILABLE',
]
