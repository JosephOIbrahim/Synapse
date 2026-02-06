"""
Synapse Core - Protocol, Queue, and Aliases

Core components for the Synapse communication protocol.
"""

from .protocol import (
    CommandType,
    SynapseCommand,
    SynapseResponse,
    PROTOCOL_VERSION,
)

from .queue import (
    DeterministicCommandQueue,
    ResponseDeliveryQueue,
)

from .aliases import (
    PARAM_ALIASES,
    resolve_param,
    resolve_param_with_default,
)

__all__ = [
    'CommandType',
    'SynapseCommand',
    'SynapseResponse',
    'PROTOCOL_VERSION',
    'DeterministicCommandQueue',
    'ResponseDeliveryQueue',
    'PARAM_ALIASES',
    'resolve_param',
    'resolve_param_with_default',
]
