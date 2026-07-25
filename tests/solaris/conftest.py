"""
Shared test fixtures for the Solaris tool tests.

SR1 M1: the tools live INSIDE the installable package at
`python/synapse/mcp/tool_impls/solaris/` (NOT `mcp/tools/solaris/` — a
regular package there shadows the existing `python/synapse/mcp/tools.py`
HTTP-transport module; proven live, see the M1 report). Importing here
(rather than only in the test files) keeps the failure loud if the package
move regresses.

SR1 M3 — the mock-`hou` fixtures that used to live here are DELETED.

Constitution Law 1: "Mock-`hou` tests are banned for host-behaviour
assertions. They assert your assumptions back at you. Use hython-gated live
tests that **skip** without Houdini. A skip is honest; a pass is a lie."

Ruling 12 item 3 names this the load-bearing move: the mock fixture is
exactly how F7 (`set_purpose` reports success having set nothing) and F9
(`import_megascans` raises `PermissionError` on every invocation) stayed
green.

What remains in this directory:
  * pure-Python `validate()` / `plan()` tests — no `hou` at all, they were
    never mock-driven and are honest as written;
  * `test_live_wiring.py` — host-behaviour assertions, module-level gated on
    a real `import hou`, SKIPPED without Houdini and EXECUTED under
    hython 22.0.368.

Run the live tier with `tests/solaris/run_live.py`.
"""

from synapse.mcp.tool_impls.solaris import (  # noqa: F401
    component_builder,
    create_variants,
    import_megascans,
    scene_template,
    set_purpose,
)
