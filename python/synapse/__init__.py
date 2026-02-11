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
Version: 5.1.0
"""

__title__ = "Synapse"
__version__ = "5.1.0"
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
    kahan_sum,
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

# Encryption (lazy load to avoid cryptography dependency)
try:
    from .core.crypto import CryptoEngine, ENCRYPTION_AVAILABLE, get_crypto
except ImportError:
    ENCRYPTION_AVAILABLE = False
    CryptoEngine = None  # type: ignore[assignment,misc]
    get_crypto = None  # type: ignore[assignment]

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

# Agent protocol
from .agent.protocol import (
    AgentTask,
    AgentPlan,
    AgentStep,
    StepStatus,
    PlanStatus,
    DEFAULT_GATE_LEVELS,
    classify_gate_level,
)
from .agent.executor import AgentExecutor
from .agent.learning import OutcomeTracker

# Routing, Server, UI — all deferred to first access via __getattr__
# This avoids importing ~3,000 lines of code (regex compilation, websockets,
# Qt widgets) on every `import synapse`, keeping Houdini startup fast.

def __getattr__(name):
    """Lazy-load heavy modules on first attribute access."""
    # --- Routing ---
    _routing_names = {
        'TieredRouter', 'RoutingResult', 'RoutingTier', 'RoutingConfig',
        'CommandParser', 'KnowledgeIndex', 'RecipeRegistry', 'Recipe',
        'ROUTING_AVAILABLE',
    }
    if name in _routing_names:
        from . import routing as _routing
        _map = {
            'TieredRouter': _routing.TieredRouter,
            'RoutingResult': _routing.RoutingResult,
            'RoutingTier': _routing.RoutingTier,
            'RoutingConfig': _routing.RoutingConfig,
            'CommandParser': _routing.CommandParser,
            'KnowledgeIndex': _routing.KnowledgeIndex,
            'RecipeRegistry': _routing.RecipeRegistry,
            'Recipe': _routing.Recipe,
            'ROUTING_AVAILABLE': True,
        }
        # Hoist into module namespace so subsequent access is O(1)
        globals().update(_map)
        return _map[name]

    # --- Server ---
    _server_names = {
        'SynapseServer', 'SynapseHandler', 'CommandHandlerRegistry',
        'RateLimiter', 'CircuitBreaker', 'CircuitBreakerConfig', 'CircuitState',
        'PortManager', 'Watchdog', 'BackpressureController', 'BackpressureLevel',
        'HealthMonitor', 'HealthStatus', 'SERVER_AVAILABLE',
        'NexusServer', 'NexusHandler',
    }
    if name in _server_names:
        try:
            from .server.websocket import SynapseServer as _SynapseServer
            from .server.handlers import SynapseHandler as _SynapseHandler, CommandHandlerRegistry as _CommandHandlerRegistry
            from .server.resilience import (
                RateLimiter as _RateLimiter,
                CircuitBreaker as _CircuitBreaker,
                CircuitBreakerConfig as _CircuitBreakerConfig,
                CircuitState as _CircuitState,
                PortManager as _PortManager,
                Watchdog as _Watchdog,
                BackpressureController as _BackpressureController,
                BackpressureLevel as _BackpressureLevel,
                HealthMonitor as _HealthMonitor,
                HealthStatus as _HealthStatus,
            )
            _map = {
                'SynapseServer': _SynapseServer,
                'SynapseHandler': _SynapseHandler,
                'CommandHandlerRegistry': _CommandHandlerRegistry,
                'RateLimiter': _RateLimiter,
                'CircuitBreaker': _CircuitBreaker,
                'CircuitBreakerConfig': _CircuitBreakerConfig,
                'CircuitState': _CircuitState,
                'PortManager': _PortManager,
                'Watchdog': _Watchdog,
                'BackpressureController': _BackpressureController,
                'BackpressureLevel': _BackpressureLevel,
                'HealthMonitor': _HealthMonitor,
                'HealthStatus': _HealthStatus,
                'SERVER_AVAILABLE': True,
                'NexusServer': _SynapseServer,
                'NexusHandler': _SynapseHandler,
            }
            globals().update(_map)
            return _map[name]
        except ImportError:
            _fallback = {
                'SERVER_AVAILABLE': False,
                'SynapseServer': None, 'SynapseHandler': None,
                'NexusServer': None, 'NexusHandler': None,
                'CommandHandlerRegistry': None,
                'RateLimiter': None, 'CircuitBreaker': None,
                'CircuitBreakerConfig': None, 'CircuitState': None,
                'PortManager': None, 'Watchdog': None,
                'BackpressureController': None, 'BackpressureLevel': None,
                'HealthMonitor': None, 'HealthStatus': None,
            }
            globals().update(_fallback)
            return _fallback.get(name)

    # --- hwebserver (native C++ transport, optional — requires Houdini) ---
    _hwebserver_names = {
        'start_hwebserver', 'stop_hwebserver', 'HWEBSERVER_AVAILABLE',
    }
    if name in _hwebserver_names:
        try:
            from .server.hwebserver_adapter import (
                start_hwebserver as _start_hwebserver,
                stop_hwebserver as _stop_hwebserver,
                HWEBSERVER_AVAILABLE as _HWEBSERVER_AVAILABLE,
            )
            _map = {
                'start_hwebserver': _start_hwebserver,
                'stop_hwebserver': _stop_hwebserver,
                'HWEBSERVER_AVAILABLE': _HWEBSERVER_AVAILABLE,
            }
            globals().update(_map)
            return _map[name]
        except ImportError:
            _fallback = {
                'start_hwebserver': None,
                'stop_hwebserver': None,
                'HWEBSERVER_AVAILABLE': False,
            }
            globals().update(_fallback)
            return _fallback.get(name)

    # --- UI ---
    _ui_names = {'SynapsePanel', 'NexusPanel', 'create_panel', 'UI_AVAILABLE'}
    if name in _ui_names:
        try:
            from .ui.panel import SynapsePanel as _SynapsePanel, create_panel as _create_panel
            _map = {
                'SynapsePanel': _SynapsePanel,
                'NexusPanel': _SynapsePanel,
                'create_panel': _create_panel,
                'UI_AVAILABLE': True,
            }
            globals().update(_map)
            return _map[name]
        except ImportError:
            _fallback = {
                'UI_AVAILABLE': False,
                'SynapsePanel': None, 'NexusPanel': None,
                'create_panel': None,
            }
            globals().update(_fallback)
            return _fallback.get(name)

    raise AttributeError(f"module 'synapse' has no attribute {name!r}")

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
    'kahan_sum',
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

    # Routing
    'TieredRouter',
    'RoutingResult',
    'RoutingTier',
    'RoutingConfig',
    'CommandParser',
    'KnowledgeIndex',
    'RecipeRegistry',
    'Recipe',
    'ROUTING_AVAILABLE',

    # Agent
    'AgentTask',
    'AgentPlan',
    'AgentStep',
    'StepStatus',
    'PlanStatus',
    'DEFAULT_GATE_LEVELS',
    'classify_gate_level',
    'AgentExecutor',
    'OutcomeTracker',

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

    # Encryption
    'CryptoEngine',
    'ENCRYPTION_AVAILABLE',
    'get_crypto',

    # UI
    'SynapsePanel',
    'NexusPanel',        # Backwards compat
    'create_panel',
    'UI_AVAILABLE',
]
