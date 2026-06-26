"""L8 minimum mitigation — heavy-path main-thread dispatch routes through
``run_on_main(timeout)`` so a busy/cooking main thread fast-fails the TRANSPORT at
the per-tool budget instead of hanging forever.

Honest scope: this bounds the agent/transport, it does NOT stop the GUI freeze
(the cook still holds the main thread for its duration — only an out-of-process
husk render keeps the GUI responsive). Source-scan pins the routing against
regression; the live MCP/TOPS protocol tests in the suite exercise the behavior.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_PY = os.path.join(_ROOT, "python", "synapse")


def _src(*parts):
    return open(os.path.join(_PY, *parts), encoding="utf-8").read()


def test_mcp_dispatch_routes_through_run_on_main():
    s = _src("mcp", "server.py")
    assert "run_on_main(" in s
    assert "from ..core.timeouts import timeout_for" in s
    assert "timeout=timeout_for(tool_name)" in s
    # the bare blocking call is no longer the heavy-tool dispatch primitive
    assert "executeInMainThreadWithResult(\n                dispatch_tool, handler, tool_name, arguments\n            )" not in s


def test_tops_pdg_dispatch_enforces_timeout():
    s = _src("server", "handlers_tops", "_common.py")
    assert "run_on_main(func, timeout=effective_timeout)" in s


def test_canonical_timeout_table_has_render_budgets():
    # the timeout the dispatch uses must actually carry render/cook budgets.
    from synapse.core.timeouts import timeout_for
    assert timeout_for("houdini_render") >= 120
    assert timeout_for("synapse_solaris_build_graph") >= 30
    assert timeout_for("houdini_get_parm") <= 10   # cheap read stays tight
