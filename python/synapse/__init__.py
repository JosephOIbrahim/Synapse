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

Author: Joseph Ibrahim
Version: 5.57.0
"""

# ---------------------------------------------------------------------------
# Vendored dependencies (Sprint 3 Spike 2.2)
# ---------------------------------------------------------------------------
# Houdini point releases (21.0.631, 21.0.671, 21.5.x) ship separate Python
# site-packages directories. A ``pip install anthropic`` into one release's
# site-packages is invisible to the next. Vendoring the SDK + its deps
# directly into SYNAPSE's tree fixes this — every Houdini install that can
# see ``python/synapse/`` automatically gets anthropic, httpx, pydantic, etc.
#
# The prepend MUST run before any ``from .inspector import ...`` or other
# synapse-internal import that transitively pulls pydantic / httpx /
# anthropic — otherwise an older copy on sys.path wins and the vendor path
# never gets consulted. Hence: top of module, before everything else.
#
# ABI lock (win_amd64): _vendor/pydantic_core + jiter each carry native
# ``.pyd`` binaries built per Houdini Python line. As of the H22 drop
# (2026-07-15) BOTH ABIs ship side by side at the SAME package versions
# (pydantic_core 2.46.3, jiter 0.14.0): ``.cp311-win_amd64.pyd`` covers
# H20.5/21.0/21.5 and ``.cp313-win_amd64.pyd`` covers H22 — the running
# interpreter loads whichever matches. Prepending _vendor on an interpreter
# with NO matching binary would break imports (stock Python 3.14 in
# particular — the test suite runs there and resolves pydantic from the user
# site, untouched by this vendoring). The gate below keeps the vendor active
# only for a vendored ABI *on Windows*. On non-Windows platforms (Linux CI,
# macOS) the vendored native binary is unloadable, so we fall through to
# whatever real pydantic the consumer has installed (pyproject.toml lists it
# as a hard dependency, so pip install -e installs it cleanly).
#
# Widen ``_VENDOR_PYS`` — and its lockstep test (tests/conftest.py
# ``VENDOR_PYS``) — in the SAME commit that adds a new ABI's .pyd. See
# docs/studio/UPGRADE.md Step 2a + python/synapse/_vendor/README.md.
import os as _synapse_os
import sys as _synapse_sys

_vendor_path: str = _synapse_os.path.join(
    _synapse_os.path.dirname(__file__), "_vendor"
)

# (major, minor) interpreter lines for which a matching native .pyd is
# vendored. Keep in lockstep with the actual _vendor/*/*.pyd ABI tags.
_VENDOR_PYS = frozenset({(3, 11), (3, 13)})

if (
    _synapse_sys.version_info[:2] in _VENDOR_PYS
    and _synapse_sys.platform.startswith("win")
    and _synapse_os.path.isdir(_vendor_path)
    and _vendor_path not in _synapse_sys.path
):
    _synapse_sys.path.insert(0, _vendor_path)


# ---------------------------------------------------------------------------
# Vendored-SDK ABI risk detection (H22 / Python 3.12+ legibility)
# ---------------------------------------------------------------------------
# The block above prepends _vendor only when the interpreter's ABI is one we
# vendored a .pyd for (``_VENDOR_PYS`` — cp311 + cp313 as of the H22 drop). On
# an interpreter OUTSIDE that set (e.g. stock Python 3.14, or a future Houdini
# line we haven't re-vendored yet) the vendor is skipped and SYNAPSE silently
# falls back to whatever real pydantic/anthropic the interpreter has installed.
# That fallback is CORRECT when a real install exists (the test suite is green
# on stock Python 3.14 precisely because it resolves a pip-installed pydantic)
# — so we must NOT hard-raise here.
#
# What we DO: when we're on Windows with an interpreter OUTSIDE _VENDOR_PYS and
# the (always committed) _vendor tree is present, flag the configuration as
# RISKY and emit one prominent, actionable warning. No vendored binary can load
# on this interpreter; if no real pydantic/anthropic is installed, the eventual
# failure would be a cryptic deep ImportError far from here. The flag below
# lets doctor/diagnostics surface the risk early; the warning points the
# operator at the two known remediations (re-vendor for this ABI, or the sidecar).
_VENDOR_ABI_RISK: bool = (
    _synapse_sys.platform.startswith("win")
    and _synapse_sys.version_info[:2] not in _VENDOR_PYS
    and _synapse_os.path.isdir(_vendor_path)
)

if _VENDOR_ABI_RISK:
    import warnings as _synapse_warnings

    _py = (
        f"{_synapse_sys.version_info.major}."
        f"{_synapse_sys.version_info.minor}."
        f"{_synapse_sys.version_info.micro}"
    )
    _synapse_warnings.warn(
        "SYNAPSE vendored-SDK ABI mismatch: the bundled native wheels under "
        f"{_vendor_path} ship cp311 + cp313 win_amd64 binaries, but this "
        f"interpreter is Python {_py} on Windows (no matching ABI). The "
        "vendor tree is INACTIVE on this "
        "Python, so SYNAPSE will rely on a real pip-installed "
        "pydantic/anthropic. If those are absent, the brain (agent loop) "
        "will fail later with a cryptic deep ImportError. Remediate by "
        "re-vendoring for this Python (see python/synapse/_vendor/README.md) "
        "or by using the out-of-process sidecar "
        "(see harness/notes/gate-0.1-sidecar-vs-abi3.md). "
        "Query synapse._VENDOR_ABI_RISK to detect this in diagnostics.",
        RuntimeWarning,
        stacklevel=2,
    )
    del _synapse_warnings, _py


__title__ = "Synapse"
__version__ = "5.57.0"
__author__ = "Joseph Ibrahim"
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

# Inspector (Sprint 2 Week 1) — pydantic-only at import time, safe to eager
# load. Gives scene-awareness via /stage AST extraction.
try:
    from .inspector import (
        ASTNode,
        SCHEMA_VERSION as INSPECTOR_SCHEMA_VERSION,
        StageAST,
        configure_transport as inspector_configure_transport,
        synapse_inspect_stage,
    )
    from .inspector.exceptions import (
        InspectorError,
        StageNotFoundError,
    )
    INSPECTOR_AVAILABLE = True
except ImportError:
    INSPECTOR_AVAILABLE = False
    ASTNode = None  # type: ignore[assignment,misc]
    StageAST = None  # type: ignore[assignment,misc]
    synapse_inspect_stage = None  # type: ignore[assignment]
    inspector_configure_transport = None  # type: ignore[assignment]
    INSPECTOR_SCHEMA_VERSION = None  # type: ignore[assignment]
    InspectorError = None  # type: ignore[assignment,misc]
    StageNotFoundError = None  # type: ignore[assignment,misc]

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

    # --- Agent protocol: GONE (R202, 2026-08-02) ---
    # python/synapse/agent/ was deleted in full. The executor and v8-DSA
    # modules went 2026-08-01 (RL-3); protocol.py survived one day on a
    # single test import (tests/test_set_usd_primvar.py "wiring site 1"),
    # whose gate map was consulted by nothing at runtime — the live gate
    # authority is panel/bridge_adapter._TOOL_TO_OPERATION ->
    # shared/bridge.OPERATION_GATES. Code lives in git history (last live
    # at 9d7bd17).

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

    # Inspector (Sprint 2 Week 1)
    'ASTNode',
    'StageAST',
    'synapse_inspect_stage',
    'inspector_configure_transport',
    'INSPECTOR_SCHEMA_VERSION',
    'INSPECTOR_AVAILABLE',
    'InspectorError',
    'StageNotFoundError',

    # UI
    'SynapsePanel',
    'NexusPanel',        # Backwards compat
    'create_panel',
    'UI_AVAILABLE',
]
