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
]
