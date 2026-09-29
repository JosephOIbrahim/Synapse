"""Identify: every selected node explains itself in a zero-token bubble.

Code builds each bubble from exact sources (the local SideFX library and the
node's own runtime facts), so there is no model call, no network call and no
token cost. The bubbles are an overlay on the network editor: nothing is
written to the scene, and a second click takes them away.

Layout (IDENTIFY_BLUEPRINT sec. 4):

* :mod:`compose`  - pure ``facts -> lines`` (no ``hou``, no Qt)
* :mod:`bubble`   - pure ``facts -> bubble model`` for the overlay
* :mod:`layout`   - pure bubble placement on the editor
* :mod:`library`  - node type -> summary, by exact help path only
* :mod:`facts`    - the one short main-thread read of per-node facts
* :mod:`overlay`  - the Qt paint layer over the network editor (reads only)
* :mod:`apply`    - the only writer: removes old ``~ identify ~`` comment blocks

``compose``, ``bubble``, ``layout`` and ``library`` are pure and import cheaply
on system Python; ``facts``, ``overlay`` and ``apply`` import ``hou`` (and Qt)
under a guard, so import them explicitly.
"""
from __future__ import annotations

# Note: the ``compose`` *submodule* is intentionally not shadowed by re-exporting
# the ``compose`` function, so ``synapse.identify.compose`` stays the module.
from .compose import WIDTH, bubble_text
from .library import derive_help_keys, first_sentence, summarize

__all__ = [
    "WIDTH", "bubble_text",
    "derive_help_keys", "first_sentence", "summarize",
]
