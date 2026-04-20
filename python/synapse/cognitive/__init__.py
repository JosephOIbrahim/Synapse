"""synapse.cognitive — host-agnostic cognitive substrate.

The cognitive layer is pure Python with ZERO ``hou`` imports. It composes
across DCCs (Houdini, Nuke / Moneta, Octavius) unchanged. Host-specific
code — daemon bootstrap, thread marshaling, UI — lives in
``synapse.host.*`` instead.

This boundary is enforced structurally by ``tests/test_cognitive_boundary.py``
which fails on any ``import hou`` or ``from hou`` under this package tree.

Sprint 3 Spike 1.0 ships the test-mode dispatch bypass. The main-thread
``hdefereval`` marshal path is wired in Spike 1.
"""

from __future__ import annotations

from synapse.cognitive.dispatcher import (
    AgentToolError,
    Dispatcher,
)

__all__ = [
    "AgentToolError",
    "Dispatcher",
]
