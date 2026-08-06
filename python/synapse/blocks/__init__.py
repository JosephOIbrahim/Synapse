"""synapse.blocks -- BLOCKS fixtures and the reconciler that makes them real.

A BLOCKS fixture is a committed JSON definition of a deterministic Houdini
network with a verified composed-USD baseline. The reconciler's job is to make
a live stage match one, idempotently, without ever touching a node the artist
made.

Layering
--------
``canonical``  pure   the ONE c2 canonicalizer; harness/autoresearch imports it
``fixtures``   pure   load + validate a definition
``plan``       pure   the reconcile diff -- D2 and D3 live here, testable
                      without Houdini and without a mocked ``hou``
``transport``  pure   how a caller outside the Houdini process reaches in
``runtime``    hou    the only module that mutates a scene

This ``__init__`` deliberately does NOT import ``runtime``. Importing
``synapse.blocks`` must stay free of ``hou`` so the planner, the fixture
loader and the canonicalizer are usable from the MCP server process, from
pytest, and from the evidence harness -- none of which have Houdini.
"""

from __future__ import annotations

from synapse.blocks.canonical import (
    C1_RULES,
    CANONICALIZER_VERSION,
    canonicalize_usda,
)
from synapse.blocks.fixtures import (
    FixtureError,
    FixtureNotFoundError,
    box_name_for,
    fixture_path,
    list_fixtures,
    load_fixture,
    repo_root,
    validate_fixture,
)
from synapse.blocks.plan import Plan, build_plan, collisions

__all__ = [
    "C1_RULES",
    "CANONICALIZER_VERSION",
    "canonicalize_usda",
    "FixtureError",
    "FixtureNotFoundError",
    "box_name_for",
    "fixture_path",
    "list_fixtures",
    "load_fixture",
    "repo_root",
    "validate_fixture",
    "Plan",
    "build_plan",
    "collisions",
]
