"""
Synapse Core - Protocol, Queue, Aliases, and Foundation Utilities

Core components for the Synapse communication protocol,
plus foundational utilities (determinism, audit, gates).
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

from .determinism import (
    DeterministicConfig,
    DeterministicOperation,
    DeterministicRandom,
    get_config,
    set_config,
    round_float,
    round_vector,
    round_color,
    deterministic_uuid,
    deterministic_sort,
    deterministic_dict_items,
    deterministic,
)

from .audit import (
    AuditLevel,
    AuditCategory,
    AuditEntry,
    AuditLog,
    audit_log,
)

from .gates import (
    GateLevel,
    GateDecision,
    GateProposal,
    GateBatch,
    HumanGate,
    human_gate,
    propose_change,
)

from .errors import (
    SynapseError,
    SynapseUserError,
    SynapseServiceError,
    NodeNotFoundError,
    ParameterError,
    ExecutionError,
    HoudiniUnavailableError,
    ValidationError,
)

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
    # Determinism
    'DeterministicConfig',
    'DeterministicOperation',
    'DeterministicRandom',
    'get_config',
    'set_config',
    'round_float',
    'round_vector',
    'round_color',
    'deterministic_uuid',
    'deterministic_sort',
    'deterministic_dict_items',
    'deterministic',
    # Audit
    'AuditLevel',
    'AuditCategory',
    'AuditEntry',
    'AuditLog',
    'audit_log',
    # Gates
    'GateLevel',
    'GateDecision',
    'GateProposal',
    'GateBatch',
    'HumanGate',
    'human_gate',
    'propose_change',
    # Errors
    'SynapseError',
    'SynapseUserError',
    'SynapseServiceError',
    'NodeNotFoundError',
    'ParameterError',
    'ExecutionError',
    'HoudiniUnavailableError',
    'ValidationError',
]
