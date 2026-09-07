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

import pytest

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
# current release tag derives from VERSION. An explicit Preview may retain an
# older Latest release; ordinary stable releases still require Latest == VERSION.

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


def _assert_release_tags(readme, canonical, notes):
    """Bind the actual banner's current channel, version and release notes.

    Older Latest ordering is not remote-state attestation; publication separately
    verifies GitHub's retained Latest against the approved release plan.
    """
    version = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    assert re.fullmatch(version, canonical), "VERSION must be comparable X.Y.Z"
    banners = [text for text in re.findall(r"<sub>(.*?)</sub>", readme, re.S)
               if "tags:" in text]
    assert len(banners) == 1, "README must have exactly one release-tag banner"
    lines = re.findall(r"(?:^|<br\s*/?>)\s*tags:\s*([^<\n]+)", banners[0])
    assert len(lines) == 1, "README release-tag line is missing or malformed"
    parts = [part.strip() for part in lines[0].split("·")]
    if parts[-1] == "vNEXT tags only via the release ritual (g-receipts are human acts)":
        parts.pop()
    parsed = [re.fullmatch(rf"v({version}) is (Latest|Preview|RC)", part) for part in parts]
    assert parsed and all(parsed), "README release tags must name exact versions and channels"
    claims = [match.groups() for match in parsed]
    current, channel = claims[0]
    assert current == canonical, "README current release tag differs from VERSION"
    title = notes.splitlines()[0] if notes else ""
    preview_notes = re.fullmatch(rf"# v{re.escape(canonical)} (?:Preview(?:/RC)?|RC)(?:\s.*)?", title)
    if channel == "Latest":
        assert len(claims) == 1, "Stable banner must have one current Latest claim"
        assert not preview_notes, "Preview release notes cannot claim the current tag as Latest"
    else:
        assert len(claims) == 2 and claims[1][1] == "Latest", "Preview must retain one older Latest tag"
        assert tuple(map(int, claims[1][0].split("."))) < tuple(map(int, canonical.split("."))), (
            "Preview cannot be Latest; retained Latest must be older than VERSION"
        )
        assert preview_notes, "Current Preview requires matching RELEASE_vVERSION.md Preview/RC notes"


def test_readme_latest_tag_matches_version_file():
    """Keep stable drift red; allow a version-bound, documented Preview channel."""
    canonical = (_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    path = _ROOT / "harness" / "notes" / f"RELEASE_v{canonical}.md"
    notes = path.read_text(encoding="utf-8") if path.exists() else None
    _assert_release_tags(_readme(), canonical, notes)


@pytest.mark.parametrize("tags,notes", [
    ("v9.10.0 is Latest", None),
    ("v9.10.0 is Latest", "# v9.10.0 — Stable release"),
    ("v9.10.0 is Preview · v9.9.9 is Latest", "# v9.10.0 Preview — Example"),
    ("v9.10.0 is RC · v9.9.9 is Latest", "# v9.10.0 RC — Example"),
])
def test_release_channels_accept_matching_stable_and_preview(tags, notes):
    _assert_release_tags(f"<sub>v9.10.0 · Houdini<br>tags: {tags}</sub>", "9.10.0", notes)


@pytest.mark.parametrize("tags,notes", [
    ("v9.9.9 is Latest", None),  # Original stable drift must still fail.
    ("", None),
    ("v9.10 is Latest", None),
    ("v09.10.0 is Latest", None),
    ("v9.10.0 is Beta", None),
    ("v9.9.9 is Preview · v9.8.0 is Latest", "# v9.10.0 Preview"),
    ("v9.10 is Preview · v9.9.9 is Latest", "# v9.10.0 Preview"),
    ("v9.10.0 is Preview", "# v9.10.0 Preview"),
    ("v9.10.0 is Preview · v9.10.0 is Latest", "# v9.10.0 Preview"),
    ("v9.10.0 is Preview · v10.0.0 is Latest", "# v9.10.0 Preview"),
    ("v9.10.0 is Latest", "# v9.10.0 Preview — Example"),
    ("v9.10.0 is Latest · v9.9.9 is Preview", "# v9.10.0 Stable"),
    ("v9.10.0 is Preview · v9.9.9 is Latest", None),
    ("v9.10.0 is Preview · v9.9.9 is Latest", ""),
    ("v9.10.0 is Preview · v9.9.9 is Latest", "# v9.9.9 Preview"),
    ("v9.10.0 is Preview · v9.9.9 is Latest", "# v9.10.0 Stable\nHistorical Preview/RC mention"),
    ("v9.10.0 is Preview · v9.9.9 is Latest", "# v9.10.0 Previewed"),
    ("v9.10.0 is Preview · v9.9.9 is Latest · v9.10.0 is Latest", "# v9.10.0 Preview"),
])
def test_release_channels_reject_drift_and_false_claims(tags, notes):
    with pytest.raises(AssertionError):
        _assert_release_tags(f"<sub>v9.10.0 · Houdini<br>tags: {tags}</sub>", "9.10.0", notes)


def test_release_claim_cannot_be_satisfied_by_prose_outside_banner():
    with pytest.raises(AssertionError, match="banner"):
        _assert_release_tags("<sub>v9.10.0 · Houdini</sub>\ntags: v9.10.0 is Latest", "9.10.0", None)
