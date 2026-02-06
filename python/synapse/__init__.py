"""
Synapse - Unified AI-Houdini Bridge with Project Memory

Synapse consolidates communication (WebSocket server), resilience,
and Engram (project memory) into a unified package for AI-native VFX workflows.

Features:
- WebSocket server for AI assistant communication
- Persistent project memory with human-readable markdown
- Session tracking and auto-summary generation
- Decision logging with reasoning
- Semantic memory search

Storage: $HIP/.synapse/

Author: Joe Ibrahim
Version: 4.1.0
"""

__title__ = "Synapse"
__version__ = "4.1.0"
__author__ = "Joe Ibrahim"
__license__ = "MIT"
__product__ = "Synapse - AI-Houdini Bridge"

# Core protocol
from .core.protocol import (
    CommandType,
    SynapseCommand,
    SynapseResponse,
    PROTOCOL_VERSION,
)

from .core.queue import (
    DeterministicCommandQueue,
    ResponseDeliveryQueue,
)

from .core.aliases import (
    PARAM_ALIASES,
    resolve_param,
    resolve_param_with_default,
)

# Foundation (determinism, audit, gates)
from .core.determinism import (
    DeterministicConfig,
    deterministic_uuid,
    round_float,
    deterministic,
)

from .core.audit import (
    AuditLog,
    AuditLevel,
    AuditCategory,
    AuditEntry,
    audit_log,
)

from .core.gates import (
    HumanGate,
    GateLevel,
    GateDecision,
    GateProposal,
    human_gate,
    propose_change,
)

# Hyphae backwards compatibility (import from synapse instead of hyphae)
HyphaeAuditLog = AuditLog
HyphaeGate = HumanGate

# Memory system
from .memory.models import (
    Memory,
    MemoryType,
    MemoryTier,
    MemoryLink,
    LinkType,
    MemoryQuery,
    MemorySearchResult,
)

from .memory.store import (
    SynapseMemory,
    MemoryStore,
    get_synapse_memory,
    reset_synapse_memory,
    # Backwards compatibility aliases
    NexusMemory,
    EngramMemory,
    get_nexus_memory,
    get_engram,
    reset_nexus_memory,
    reset_engram,
)

from .memory.context import (
    ShotContext,
    load_context,
    save_context,
    get_current_context,
    update_context,
)

from .memory.markdown import (
    MarkdownSync,
    parse_decisions_md,
    render_decisions_md,
)

# Session management
from .session.tracker import (
    SynapseSession,
    SynapseBridge,
    get_bridge,
    reset_bridge,
    # Backwards compatibility aliases
    NexusSession,
    NexusBridge,
    EngramBridge,
)

# Server components (lazy load to avoid websockets dependency)
try:
    from .server.websocket import SynapseServer
    from .server.handlers import SynapseHandler, CommandHandlerRegistry
    from .server.resilience import (
        RateLimiter,
        CircuitBreaker,
        CircuitBreakerConfig,
        CircuitState,
        PortManager,
        Watchdog,
        BackpressureController,
        BackpressureLevel,
        HealthMonitor,
        HealthStatus,
    )
    # Backwards compatibility
    NexusServer = SynapseServer
    NexusHandler = SynapseHandler
    SERVER_AVAILABLE = True
except ImportError:
    SERVER_AVAILABLE = False
    SynapseServer = None
    SynapseHandler = None
    NexusServer = None
    NexusHandler = None

# UI components (lazy load to avoid Qt dependency)
try:
    from .ui.panel import SynapsePanel, create_panel
    # Backwards compatibility
    NexusPanel = SynapsePanel
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    SynapsePanel = None
    NexusPanel = None
    create_panel = None

__all__ = [
    # Protocol
    'CommandType',
    'SynapseCommand',
    'SynapseResponse',
    'PROTOCOL_VERSION',
    'DeterministicCommandQueue',
    'ResponseDeliveryQueue',
    'PARAM_ALIASES',
    'resolve_param',
    'resolve_param_with_default',

    # Foundation
    'DeterministicConfig',
    'deterministic_uuid',
    'round_float',
    'deterministic',
    'AuditLog',
    'AuditLevel',
    'AuditCategory',
    'AuditEntry',
    'audit_log',
    'HumanGate',
    'GateLevel',
    'GateDecision',
    'GateProposal',
    'human_gate',
    'propose_change',
    'HyphaeAuditLog',    # Backwards compat
    'HyphaeGate',        # Backwards compat

    # Memory
    'Memory',
    'MemoryType',
    'MemoryTier',
    'MemoryLink',
    'LinkType',
    'MemoryQuery',
    'MemorySearchResult',
    'SynapseMemory',
    'MemoryStore',
    'get_synapse_memory',
    'reset_synapse_memory',
    'NexusMemory',       # Backwards compat
    'EngramMemory',      # Backwards compat
    'get_nexus_memory',  # Backwards compat
    'get_engram',        # Backwards compat
    'reset_nexus_memory',  # Backwards compat
    'reset_engram',      # Backwards compat
    'ShotContext',
    'load_context',
    'save_context',
    'get_current_context',
    'update_context',
    'MarkdownSync',
    'parse_decisions_md',
    'render_decisions_md',

    # Session
    'SynapseSession',
    'SynapseBridge',
    'NexusSession',      # Backwards compat
    'NexusBridge',       # Backwards compat
    'EngramBridge',      # Backwards compat
    'get_bridge',
    'reset_bridge',

    # Server
    'SynapseServer',
    'SynapseHandler',
    'NexusServer',       # Backwards compat
    'NexusHandler',      # Backwards compat
    'CommandHandlerRegistry',
    'RateLimiter',
    'CircuitBreaker',
    'CircuitBreakerConfig',
    'CircuitState',
    'PortManager',
    'Watchdog',
    'BackpressureController',
    'BackpressureLevel',
    'HealthMonitor',
    'HealthStatus',
    'SERVER_AVAILABLE',

    # UI
    'SynapsePanel',
    'NexusPanel',        # Backwards compat
    'create_panel',
    'UI_AVAILABLE',
]
