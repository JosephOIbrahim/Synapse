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

# Sprint D: Studio Deployment (separate try to avoid breaking existing imports)
try:
    from .rbac import Role, check_permission, is_rbac_enabled
    from .sessions import SessionManager, UserSession, DeployConfig, load_deploy_config
except ImportError:
    pass

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
    'check_permission',
    'is_rbac_enabled',
    'SessionManager',
    'UserSession',
    'DeployConfig',
    'load_deploy_config',
]
