"""synapse.host — Houdini-specific integration layer.

Mirror image of ``synapse.cognitive``: host-specific code lives here and
is allowed to import ``hou`` / ``hdefereval``. Cognitive code stays
host-agnostic and is injected across the Dispatcher boundary via
callables defined in this package.

Keeping the two layers structurally separated is how SYNAPSE stays
portable to Moneta (Nuke), Octavius, and the Cognitive Bridge later —
only ``synapse.host.*`` is swapped per DCC; ``synapse.cognitive.*``
composes unchanged.
"""

from __future__ import annotations

from synapse.host.auth import (
    CREDENTIAL_LABEL,
    ENV_VAR,
    get_anthropic_api_key,
)
from synapse.host.daemon import (
    DEFAULT_START_TIMEOUT_SECONDS,
    DEFAULT_STOP_TIMEOUT_SECONDS,
    DaemonBootError,
    SynapseDaemon,
)
from synapse.cognitive.agent_loop import (
    AgentTurnConfig,
    AgentTurnResult,
    STATUS_API_ERROR,
    STATUS_CANCELLED,
    STATUS_COMPLETE,
    STATUS_MAX_ITERATIONS,
    STATUS_UNKNOWN_STOP,
)
from synapse.host.dialog_suppression import (
    SUPPRESSED_METHODS,
    ModalDialogSuppressedError,
    suppress_modal_dialogs,
)
from synapse.host.main_thread_executor import (
    DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS,
    MainThreadTimeoutError,
    main_thread_exec,
)
from synapse.host.transport import execute_python
from synapse.host.tops_bridge import (
    Subscription,
    TopsBridgeError,
    TopsEvent,
    TopsEventBridge,
)
from synapse.host.scene_load_bridge import (
    SceneLoadBridge,
    SceneLoadBridgeError,
)
from synapse.host.turn_handle import (
    TurnCancelled,
    TurnHandle,
    TurnNotComplete,
)

__all__ = [
    # Auth
    "CREDENTIAL_LABEL",
    "ENV_VAR",
    "get_anthropic_api_key",
    # Daemon
    "DEFAULT_START_TIMEOUT_SECONDS",
    "DEFAULT_STOP_TIMEOUT_SECONDS",
    "DaemonBootError",
    "SynapseDaemon",
    # Agent loop (re-exported for convenience)
    "AgentTurnConfig",
    "AgentTurnResult",
    "STATUS_API_ERROR",
    "STATUS_CANCELLED",
    "STATUS_COMPLETE",
    "STATUS_MAX_ITERATIONS",
    "STATUS_UNKNOWN_STOP",
    # Dialog suppression
    "SUPPRESSED_METHODS",
    "ModalDialogSuppressedError",
    "suppress_modal_dialogs",
    # Main-thread executor
    "DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS",
    "MainThreadTimeoutError",
    "main_thread_exec",
    # In-process transport
    "execute_python",
    # TopsEventBridge (Spike 3.1 — in-process PDG perception channel)
    "Subscription",
    "TopsBridgeError",
    "TopsEvent",
    "TopsEventBridge",
    # SceneLoadBridge (Spike 3.2 — auto-warm on hou.hipFile.AfterLoad)
    "SceneLoadBridge",
    "SceneLoadBridgeError",
    # Turn handle (Spike 2.4 — Future-shaped submit_turn return)
    "TurnCancelled",
    "TurnHandle",
    "TurnNotComplete",
]
