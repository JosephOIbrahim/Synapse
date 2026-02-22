"""
Synapse Server - WebSocket Server and Handlers

Server components for AI-Houdini communication.
"""

try:
    from .websocket import SynapseServer
    from .handlers import SynapseHandler, CommandHandlerRegistry
    from .resilience import (
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
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    SynapseServer = None  # type: ignore[assignment,misc]
    SynapseHandler = None  # type: ignore[assignment,misc]
    NexusServer = None  # type: ignore[assignment,misc]
    NexusHandler = None  # type: ignore[assignment,misc]
    CommandHandlerRegistry = None  # type: ignore[assignment,misc]
    RateLimiter = None  # type: ignore[assignment,misc]
    CircuitBreaker = None  # type: ignore[assignment,misc]
    CircuitBreakerConfig = None  # type: ignore[assignment,misc]
    CircuitState = None  # type: ignore[assignment,misc]
    PortManager = None  # type: ignore[assignment,misc]
    Watchdog = None  # type: ignore[assignment,misc]
    BackpressureController = None  # type: ignore[assignment,misc]
    BackpressureLevel = None  # type: ignore[assignment,misc]
    HealthMonitor = None  # type: ignore[assignment,misc]
    HealthStatus = None  # type: ignore[assignment,misc]

# Sprint D: Studio Deployment (separate try to avoid breaking existing imports)
try:
    from .rbac import Role, check_permission, is_rbac_enabled
    from .sessions import SessionManager, UserSession, DeployConfig, load_deploy_config
except ImportError:
    Role = None  # type: ignore[assignment,misc]
    check_permission = None  # type: ignore[assignment]
    is_rbac_enabled = None  # type: ignore[assignment]
    SessionManager = None  # type: ignore[assignment,misc]
    UserSession = None  # type: ignore[assignment,misc]
    DeployConfig = None  # type: ignore[assignment,misc]
    load_deploy_config = None  # type: ignore[assignment]

# Sprint E: Real-Time Monitoring (separate try for same reason)
try:
    from .live_metrics import MetricsAggregator, MetricSnapshot
except ImportError:
    MetricsAggregator = None  # type: ignore[assignment,misc]
    MetricSnapshot = None  # type: ignore[assignment,misc]

__all__ = [
    'SynapseServer',
    'SynapseHandler',
    'NexusServer',
    'NexusHandler',
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
    'WEBSOCKETS_AVAILABLE',
    # Sprint D: Studio Deployment
    'Role',
    # Sprint E: Real-Time Monitoring
    'MetricsAggregator',
    'MetricSnapshot',
    'check_permission',
    'is_rbac_enabled',
    'SessionManager',
    'UserSession',
    'DeployConfig',
    'load_deploy_config',
]
