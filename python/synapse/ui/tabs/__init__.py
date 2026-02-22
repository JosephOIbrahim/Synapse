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
    ConnectionTab = None  # type: ignore[assignment,misc]
    ContextTab = None  # type: ignore[assignment,misc]
    DecisionsTab = None  # type: ignore[assignment,misc]
    ActivityTab = None  # type: ignore[assignment,misc]
    SearchTab = None  # type: ignore[assignment,misc]

__all__ = [
    'ConnectionTab',
    'ContextTab',
    'DecisionsTab',
    'ActivityTab',
    'SearchTab',
    'TABS_AVAILABLE',
]
