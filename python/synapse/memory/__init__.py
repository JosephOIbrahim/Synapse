"""
Synapse Memory - Persistent Project Memory System

Memory components for storing context, decisions, and task history.
"""

from .models import (
    Memory,
    MemoryType,
    MemoryTier,
    MemoryLink,
    LinkType,
    MemoryQuery,
    MemorySearchResult,
)

from .store import (
    SynapseMemory,
    MemoryStore,
    get_synapse_memory,
    reset_synapse_memory,
    # Backwards compatibility
    NexusMemory,
    EngramMemory,
    get_nexus_memory,
    get_engram,
    reset_nexus_memory,
    reset_engram,
)

from .context import (
    ShotContext,
    load_context,
    save_context,
    get_current_context,
    update_context,
)

from .markdown import (
    MarkdownSync,
    parse_decisions_md,
    render_decisions_md,
    parse_context_md,
)

__all__ = [
    # Models
    'Memory',
    'MemoryType',
    'MemoryTier',
    'MemoryLink',
    'LinkType',
    'MemoryQuery',
    'MemorySearchResult',

    # Store
    'SynapseMemory',
    'MemoryStore',
    'get_synapse_memory',
    'reset_synapse_memory',
    'NexusMemory',
    'EngramMemory',
    'get_nexus_memory',
    'get_engram',
    'reset_nexus_memory',
    'reset_engram',

    # Context
    'ShotContext',
    'load_context',
    'save_context',
    'get_current_context',
    'update_context',

    # Markdown
    'MarkdownSync',
    'parse_decisions_md',
    'render_decisions_md',
    'parse_context_md',
]
