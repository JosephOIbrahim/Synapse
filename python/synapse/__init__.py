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
Version: 5.3.0
"""

__title__ = "Synapse"
__version__ = "5.6.0"
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

# Memory context, markdown, session, agent — all deferred to first access via __getattr__
# Routing, Server, UI — all deferred to first access via __getattr__
# This avoids importing ~3,000 lines of code (regex compilation, websockets,
# Qt widgets) on every `import synapse`, keeping Houdini startup fast.

def __getattr__(name):
    """Lazy-load heavy modules on first attribute access."""
    # --- Memory context ---
    _context_names = {
        'ShotContext', 'load_context', 'save_context',
        'get_current_context', 'update_context',
    }
    if name in _context_names:
        from .memory.context import (
            ShotContext as _ShotContext,
            load_context as _load_context,
            save_context as _save_context,
            get_current_context as _get_current_context,
            update_context as _update_context,
        )
        _map = {
            'ShotContext': _ShotContext,
            'load_context': _load_context,
            'save_context': _save_context,
            'get_current_context': _get_current_context,
            'update_context': _update_context,
        }
        globals().update(_map)
        return _map[name]

    # --- Memory markdown ---
    _markdown_names = {
        'MarkdownSync', 'parse_decisions_md', 'render_decisions_md',
    }
    if name in _markdown_names:
        from .memory.markdown import (
            MarkdownSync as _MarkdownSync,
            parse_decisions_md as _parse_decisions_md,
            render_decisions_md as _render_decisions_md,
        )
        _map = {
            'MarkdownSync': _MarkdownSync,
            'parse_decisions_md': _parse_decisions_md,
            'render_decisions_md': _render_decisions_md,
        }
        globals().update(_map)
        return _map[name]

    # --- Session management ---
    _session_names = {
        'SynapseSession', 'SynapseBridge', 'get_bridge', 'reset_bridge',
        'NexusSession', 'NexusBridge', 'EngramBridge',
    }
    if name in _session_names:
        from .session.tracker import (
            SynapseSession as _SynapseSession,
            SynapseBridge as _SynapseBridge,
            get_bridge as _get_bridge,
            reset_bridge as _reset_bridge,
            NexusSession as _NexusSession,
            NexusBridge as _NexusBridge,
            EngramBridge as _EngramBridge,
        )
        _map = {
            'SynapseSession': _SynapseSession,
            'SynapseBridge': _SynapseBridge,
            'get_bridge': _get_bridge,
            'reset_bridge': _reset_bridge,
            'NexusSession': _NexusSession,
            'NexusBridge': _NexusBridge,
            'EngramBridge': _EngramBridge,
        }
        globals().update(_map)
        return _map[name]

    # --- Agent protocol ---
    _agent_names = {
        'AgentTask', 'AgentPlan', 'AgentStep', 'StepStatus', 'PlanStatus',
        'DEFAULT_GATE_LEVELS', 'classify_gate_level',
        'AgentExecutor', 'OutcomeTracker',
        # v8-DSA: Sparse Router
        'SparseToolIndexer', 'SparseRouterConfig', 'ToolSignature',
        'RouteCandidate', 'Domain', 'CostTier', 'build_signatures_from_registry',
        # v8-DSA: Reasoning Context
        'ReasoningContext', 'ReasoningContextManager', 'ReasoningEntry',
        'EntryCategory', 'PROTECTED_CATEGORIES',
        # v8-DSA: Specialist Modes
        'SpecialistMode', 'SpecialistDomain', 'QualitySignal',
        'SPECIALIST_REGISTRY', 'get_specialist', 'get_specialist_by_name',
        'build_enhanced_prompt', 'list_specialists',
        # v8-DSA: Task Synthesizer
        'TaskSynthesizer', 'TaskEnvironment', 'TaskConstraint',
        'SuccessCriterion', 'Complexity', 'ConstraintType', 'FailureMode',
    }
    if name in _agent_names:
        from .agent.protocol import (
            AgentTask as _AgentTask,
            AgentPlan as _AgentPlan,
            AgentStep as _AgentStep,
            StepStatus as _StepStatus,
            PlanStatus as _PlanStatus,
            DEFAULT_GATE_LEVELS as _DEFAULT_GATE_LEVELS,
            classify_gate_level as _classify_gate_level,
        )
        from .agent.executor import AgentExecutor as _AgentExecutor
        from .agent.learning import OutcomeTracker as _OutcomeTracker
        from .agent.sparse_router import (
            SparseToolIndexer as _SparseToolIndexer,
            SparseRouterConfig as _SparseRouterConfig,
            ToolSignature as _ToolSignature,
            RouteCandidate as _RouteCandidate,
            Domain as _Domain,
            CostTier as _CostTier,
            build_signatures_from_registry as _build_signatures_from_registry,
        )
        from .agent.reasoning_context import (
            ReasoningContext as _ReasoningContext,
            ReasoningContextManager as _ReasoningContextManager,
            ReasoningEntry as _ReasoningEntry,
            EntryCategory as _EntryCategory,
            PROTECTED_CATEGORIES as _PROTECTED_CATEGORIES,
        )
        from .agent.specialist_modes import (
            SpecialistMode as _SpecialistMode,
            SpecialistDomain as _SpecialistDomain,
            QualitySignal as _QualitySignal,
            SPECIALIST_REGISTRY as _SPECIALIST_REGISTRY,
            get_specialist as _get_specialist,
            get_specialist_by_name as _get_specialist_by_name,
            build_enhanced_prompt as _build_enhanced_prompt,
            list_specialists as _list_specialists,
        )
        from .agent.task_synthesizer import (
            TaskSynthesizer as _TaskSynthesizer,
            TaskEnvironment as _TaskEnvironment,
            TaskConstraint as _TaskConstraint,
            SuccessCriterion as _SuccessCriterion,
            Complexity as _Complexity,
            ConstraintType as _ConstraintType,
            FailureMode as _FailureMode,
        )
        _map = {
            'AgentTask': _AgentTask,
            'AgentPlan': _AgentPlan,
            'AgentStep': _AgentStep,
            'StepStatus': _StepStatus,
            'PlanStatus': _PlanStatus,
            'DEFAULT_GATE_LEVELS': _DEFAULT_GATE_LEVELS,
            'classify_gate_level': _classify_gate_level,
            'AgentExecutor': _AgentExecutor,
            'OutcomeTracker': _OutcomeTracker,
            # v8-DSA
            'SparseToolIndexer': _SparseToolIndexer,
            'SparseRouterConfig': _SparseRouterConfig,
            'ToolSignature': _ToolSignature,
            'RouteCandidate': _RouteCandidate,
            'Domain': _Domain,
            'CostTier': _CostTier,
            'build_signatures_from_registry': _build_signatures_from_registry,
            'ReasoningContext': _ReasoningContext,
            'ReasoningContextManager': _ReasoningContextManager,
            'ReasoningEntry': _ReasoningEntry,
            'EntryCategory': _EntryCategory,
            'PROTECTED_CATEGORIES': _PROTECTED_CATEGORIES,
            'SpecialistMode': _SpecialistMode,
            'SpecialistDomain': _SpecialistDomain,
            'QualitySignal': _QualitySignal,
            'SPECIALIST_REGISTRY': _SPECIALIST_REGISTRY,
            'get_specialist': _get_specialist,
            'get_specialist_by_name': _get_specialist_by_name,
            'build_enhanced_prompt': _build_enhanced_prompt,
            'list_specialists': _list_specialists,
            'TaskSynthesizer': _TaskSynthesizer,
            'TaskEnvironment': _TaskEnvironment,
            'TaskConstraint': _TaskConstraint,
            'SuccessCriterion': _SuccessCriterion,
            'Complexity': _Complexity,
            'ConstraintType': _ConstraintType,
            'FailureMode': _FailureMode,
        }
        globals().update(_map)
        return _map[name]

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
    # Agent v8-DSA
    'SparseToolIndexer',
    'SparseRouterConfig',
    'ToolSignature',
    'RouteCandidate',
    'Domain',
    'CostTier',
    'build_signatures_from_registry',
    'ReasoningContext',
    'ReasoningContextManager',
    'ReasoningEntry',
    'EntryCategory',
    'PROTECTED_CATEGORIES',
    'SpecialistMode',
    'SpecialistDomain',
    'QualitySignal',
    'SPECIALIST_REGISTRY',
    'get_specialist',
    'get_specialist_by_name',
    'build_enhanced_prompt',
    'list_specialists',
    'TaskSynthesizer',
    'TaskEnvironment',
    'TaskConstraint',
    'SuccessCriterion',
    'Complexity',
    'ConstraintType',
    'FailureMode',

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
