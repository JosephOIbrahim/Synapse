"""
Synapse UI Tabs - Individual Tab Widgets

Tab components for the unified Synapse panel:
- Connection: Server status and controls
- Context: Project context editing
- Decisions: Decision log
- Activity: Memory feed
- Search: Memory search
"""

try:
    from .connection import ConnectionTab
    from .context import ContextTab
    from .decisions import DecisionsTab
    from .activity import ActivityTab
    from .search import SearchTab
    TABS_AVAILABLE = True
except ImportError:
    TABS_AVAILABLE = False
    ConnectionTab = None
    ContextTab = None
    DecisionsTab = None
    ActivityTab = None
    SearchTab = None

__all__ = [
    'ConnectionTab',
    'ContextTab',
    'DecisionsTab',
    'ActivityTab',
    'SearchTab',
    'TABS_AVAILABLE',
]
