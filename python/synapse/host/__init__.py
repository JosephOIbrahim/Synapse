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

from synapse.host.main_thread_executor import (
    DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS,
    MainThreadTimeoutError,
    main_thread_exec,
)

__all__ = [
    "DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS",
    "MainThreadTimeoutError",
    "main_thread_exec",
]
