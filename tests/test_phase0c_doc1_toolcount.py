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


# ── DOC-1 tool-count, transport relationship (v5 runbook Task A) ──────────────
# CTO decision #2: the registry (synapse.mcp._tool_registry.TOOL_DEFS) is the
# CANONICAL core; CLAUDE.md derives from it (pinned above); transports may
# legitimately differ. They surface the core differently, and the difference is a
# fixed, named set -- pinned here so a tool silently moving between layers (or an
# accidental duplicate registration) fails loud:
#   · HTTP  /mcp  (synapse.mcp.server -> synapse.mcp.tools.get_tools): registry core
#   · stdio       (mcp_server.py -> list_tools): registry core + the NAMED local
#     tools below, served WITHOUT a Houdini connection -- 6 group-knowledge
#     preambles + the Inspector + Scout. These are NOT dispatch handlers (absent
#     from the registry), so they are stdio-only and never double-counted.
#     stdio == len(TOOL_DEFS) + len(_STDIO_LOCAL_TOOLS); no absolute numbers here
#     on purpose -- the 110/117 prose in an earlier revision went stale silently.

_STDIO_LOCAL_TOOLS = [
    "synapse_group_scene", "synapse_group_render", "synapse_group_usd",
    "synapse_group_tops", "synapse_group_memory", "synapse_group_cops",
    "synapse_inspect_stage",
    "synapse_scout",
    # BLOCKS reconciler (M5). Same class as the Inspector: local Python that
    # composes ONE execute_python round-trip, dispatched via its own branch in
    # call_tool() -- absent from the registry, so stdio-only and never
    # double-counted. Listed here so the stdio == registry + named-locals
    # relationship still holds exactly after M5.
    "synapse_apply_fixture",
    "synapse_remove_fixture",
]


def _registry_names():
    from synapse.mcp._tool_registry import TOOL_DEFS
    return {t[0] for t in TOOL_DEFS}


def test_stdio_equals_registry_core_plus_named_local_tools():
    """stdio surface == registry core + the NAMED local tools (the value/mechanism
    binding the CTO review asked for, not bare identifier presence). The locals are
    wired into mcp_server.py's list_tools assembly (_GROUP_INFO_TOOLS keys +
    _INSPECTOR_TOOL_NAME + _SCOUT_TOOL_NAME), and NONE of them are in the dispatch
    registry -- so the extras are legitimate transport tools, never accidental
    duplicate registrations. Source-scanned so it needs no mcp/websockets import
    (CI-safe)."""
    src = (_ROOT / "mcp_server.py").read_text(encoding="utf-8")
    for token in ("_REGISTRY_TOOL_DEFS", "_GROUP_INFO_TOOLS", "_INSPECTOR_TOOL_NAME",
                  "_SCOUT_TOOL_NAME", "_BLOCKS_APPLY_TOOL_NAME",
                  "_BLOCKS_REMOVE_TOOL_NAME"):
        assert token in src, (
            f"stdio list_tools no longer composes {token} -- the documented "
            "stdio == registry + 6 group + inspector relationship moved."
        )
    missing = [n for n in _STDIO_LOCAL_TOOLS if n not in src]
    assert not missing, f"stdio local tools not wired in mcp_server.py: {missing}"
    overlap = sorted(_registry_names() & set(_STDIO_LOCAL_TOOLS))
    assert not overlap, (
        f"local tools double-registered in the dispatch registry: {overlap} -- a "
        "transport tool became a handler (or vice versa); reconcile the count "
        "before pinning it (DOC-1 A.3: do not pin a buggy count)."
    )


def test_http_lists_registry_core_only():
    """TEST-2 (stdio-vs-HTTP relationship): the HTTP /mcp transport
    (synapse.mcp.tools.get_tools) lists EXACTLY the registry core; the stdio-local
    tools are stdio-only. Transports may legitimately differ (decision #2) -- this
    pins the documented relationship (stdio = HTTP core + the named locals) so the
    difference can't drift silently into a real divergence."""
    from synapse.mcp.tools import get_tools
    http_names = {t["name"] for t in get_tools()}
    assert http_names == _registry_names(), (
        "HTTP /mcp tool surface drifted from the registry core "
        f"(symmetric diff: {sorted(http_names ^ _registry_names())})."
    )
    leaked = sorted(http_names & set(_STDIO_LOCAL_TOOLS))
    assert not leaked, f"stdio-local tools leaked into the HTTP surface: {leaked}"


# ── README release-truth slice (CTO B8, 2026-09-05) ───────────────────────────
# README carried "115 tools" and "v5.60.0 is Latest" three releases past the
# registry (128) and VERSION (5.63.0). Two more bindings so that class of drift
# fails loud instead of ageing silently: README's tool number derives from the
# registry (same authority as the CLAUDE.md banner above), and README's
# "vX.Y.Z is Latest" tag line derives from VERSION (the canonical version file,
# per test_phase0c_doc1_version_conformance.py).

def _readme():
    return (_ROOT / "README.md").read_text(encoding="utf-8")


def test_readme_tool_count_matches_registry():
    """FAILS IF: README's '**N tools, two paths.**' claim is not len(TOOL_DEFS)."""
    m = re.search(r"\*\*(\d+) tools, two paths\.\*\*", _readme())
    assert m, (
        "README.md no longer carries the '**N tools, two paths.**' claim -- the "
        "tool-count sentence moved or was reworded; re-pin it here."
    )
    documented = int(m.group(1))
    actual = _registry_count()
    assert documented == actual, (
        f"README.md says '{documented} tools, two paths' but "
        f"synapse.mcp._tool_registry.TOOL_DEFS has {actual} entries (DOC-1 / B8). "
        "Update README to the registry count (or this test if the registry moved)."
    )


def test_readme_latest_tag_matches_version_file():
    """FAILS IF: README's 'tags: vX.Y.Z is Latest' line names a version other
    than VERSION. The GitHub 'Latest' badge is a human act at release time; the
    README line must follow the canonical version, not lag it by three tags."""
    canonical = (_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    m = re.search(r"tags:\s*v(\d+\.\d+\.\d+) is Latest", _readme())
    assert m, (
        "README.md banner has no 'tags: vX.Y.Z is Latest' line -- the release "
        "tag claim went missing (did the banner change shape?)."
    )
    assert m.group(1) == canonical, (
        f"README.md says 'v{m.group(1)} is Latest' but VERSION is {canonical} (B8 "
        "release-truth drift). Update the README banner with the release ritual."
    )
