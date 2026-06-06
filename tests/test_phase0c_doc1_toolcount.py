"""Phase 0c / DOC-1 (tool-count slice): the documented MCP tool count is single-sourced.

v4 §4a.4: "N MCP tools registered" is a claim ABOUT the system -- it must bind to code,
not drift. The canonical source is the registry itself: ``synapse.mcp._tool_registry.TOOL_DEFS``.
The version slice of DOC-1 lives in ``test_phase0c_doc1_version_conformance.py``; this is the
tool-count slice the CTO review flagged (the 108/110/117 ambiguity).

This test BINDS the CLAUDE.md banner number to ``len(TOOL_DEFS)``. If a tool is added or
removed and the banner is not updated (or vice versa), it fails loud -- the drift the CTO
review called out cannot recur silently. To change the count, change the registry; then this
test tells you to update the banner (or update this test if the banner moved).

Floor note: the registry side is an IMPORT of the running package (not a hardcoded number),
so the test cannot go green against an assumed count.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _registry_count():
    """Authoritative count: import the registry the MCP server actually serves from."""
    from synapse.mcp._tool_registry import TOOL_DEFS
    return len(TOOL_DEFS)


def _documented_count():
    """The number stated in the CLAUDE.md banner: '... · N MCP tools registered'."""
    claude = (_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    m = re.search(r"(\d+)\s+MCP tools registered", claude)
    assert m, (
        "CLAUDE.md banner has no 'N MCP tools registered' phrase -- DOC-1 tool-count "
        "claim went missing (did the banner change shape?)."
    )
    return int(m.group(1))


def test_doc_tool_count_matches_registry():
    documented = _documented_count()
    actual = _registry_count()
    assert documented == actual, (
        f"CLAUDE.md says '{documented} MCP tools registered' but "
        f"synapse.mcp._tool_registry.TOOL_DEFS has {actual} entries (DOC-1). "
        "A tool was added/removed without updating the banner -- update CLAUDE.md "
        "to the registry count (or this test if the registry is the thing that moved)."
    )
