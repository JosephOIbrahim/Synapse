"""
Synapse Session - Session Tracking and Management

Components for tracking AI sessions and generating summaries.
"""

from .tracker import (
    SynapseSession,
    SynapseBridge,
    get_bridge,
    reset_bridge,
    # Backwards compatibility
    NexusSession,
    NexusBridge,
    EngramBridge,
)

from .summary import (
    generate_session_summary,
)

__all__ = [
    'SynapseSession',
    'SynapseBridge',
    'NexusSession',
    'NexusBridge',
    'EngramBridge',
    'get_bridge',
    'reset_bridge',
    'generate_session_summary',
]
