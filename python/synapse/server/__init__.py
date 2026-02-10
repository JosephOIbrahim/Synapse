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
]
