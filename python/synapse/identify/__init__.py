"""Identify: every selected node explains itself in a zero-token canvas bubble.

Code builds each bubble from exact sources (the local SideFX library and the
node's own runtime facts), so there is no model call, no network call and no
token cost. A second click, or one Ctrl+Z, takes every bubble away and leaves
the scene byte-identical.

Layout (IDENTIFY_BLUEPRINT sec. 4):

* :mod:`compose`  — pure ``facts -> bubble lines`` (no ``hou``, no Qt)
* :mod:`library`  — node type -> summary, by exact help path only
* :mod:`facts`    — the one short main-thread read of per-node facts
* :mod:`apply`    — the only writer: sentinel block, undo groups, save safety

``compose`` and ``library`` are pure and import cheaply on system Python;
``facts`` and ``apply`` import ``hou`` under a guard, so import them explicitly.
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
