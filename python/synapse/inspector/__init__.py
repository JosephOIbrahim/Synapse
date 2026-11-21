"""SYNAPSE 2.0 Inspector — Scene-memory subsystem.

Public API for extracting structured representations of Houdini Solaris
networks. Gives Claude scene awareness across sessions by reading what
already exists in /stage instead of starting blind every time.

Quick start
-----------
    from synapse.inspector import (
        configure_transport,
        synapse_inspect_stage,
    )
    # In application bootstrap (wire once):
    from synapse.server.websocket import execute_python
    configure_transport(execute_python)

    # In MCP tool or any consumer:
    ast = synapse_inspect_stage()
    display = ast.display_node()
    for err in ast.error_nodes():
        print(f"{err.hou_path}: {err.error_message}")

Sprint roadmap
--------------
- Sprint 2 Week 1: flat /stage traversal
- Sprint 2 Week 2: recursive subnet descent — shipped; ``children`` is
  populated within the walk's depth cap and node ceiling, and a bounded
  walk is stamped ``truncated`` with the level reached
- Sprint 3: USD provenance — shipped; ``provenance`` reads the creator
  node, Houdini user data and ``synapse:*`` attributes on the prims the
  node last modified
- Sprint 4: session-start handshake
"""

from __future__ import annotations

# Exception hierarchy
from synapse.inspector.exceptions import (
    HoudiniExtractionError,
    InspectorError,
    InvalidTargetPathError,
    SchemaValidationError,
    SchemaVersionMismatchError,
    StageNotFoundError,
    TransportError,
    TransportNotConfiguredError,
    TransportTimeoutError,
)

# Data models
from synapse.inspector.models import (
    SCHEMA_VERSION,
    ASTNode,
    ErrorState,
    InputConnection,
    StageAST,
)

# Tool function
from synapse.inspector.tool_inspect_stage import (
    DEFAULT_TIMEOUT_SECONDS,
    INSPECT_STAGE_TOOL_DESCRIPTION,
    MAX_KEY_PARMS,
    MAX_WALK_DEPTH,
    MAX_WALK_NODES,
    synapse_inspect_stage,
)

# Transport registration
from synapse.inspector.transport import (
    TransportFn,
    configure_transport,
    get_transport,
    is_transport_configured,
    reset_transport,
    wrap_script_base64,
)

__version__ = "1.0.0"

__all__ = [
    # Version
    "__version__",
    "SCHEMA_VERSION",
    # Tool function
    "synapse_inspect_stage",
    "DEFAULT_TIMEOUT_SECONDS",
    "INSPECT_STAGE_TOOL_DESCRIPTION",
    "MAX_WALK_DEPTH",
    "MAX_WALK_NODES",
    "MAX_KEY_PARMS",
    # Models
    "ASTNode",
    "InputConnection",
    "StageAST",
    "ErrorState",
    # Transport
    "TransportFn",
    "configure_transport",
    "get_transport",
    "is_transport_configured",
    "reset_transport",
    "wrap_script_base64",
    # Exceptions
    "InspectorError",
    "TransportNotConfiguredError",
    "TransportError",
    "TransportTimeoutError",
    "InvalidTargetPathError",
    "StageNotFoundError",
    "HoudiniExtractionError",
    "SchemaValidationError",
    "SchemaVersionMismatchError",
]
