"""H-4 regression: session summaries must not collapse to identical rows.

Before the fix, SynapseMemory.add() had no `summary` param, so every memory's
summary auto-derived from the first content line (Memory.__post_init__). Session
summaries all start with the literal "## Session Summary" heading, so
get_connection_context surfaced N identical recent_activity rows to the AI on
every connect. The fix plumbs an explicit, session-distinguishing summary through
add() at the tracker write site.

Pure-Python (no Qt / no hou) — runs in stock CI.
"""

import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

from synapse.memory.store import SynapseMemory
from synapse.memory.models import MemoryType


_TEMPLATED_BODY = "## Session Summary\n- did some things\n- and more"


def test_explicit_summary_is_honored_not_autoderived(tmp_path):
    mem = SynapseMemory(project_path=str(tmp_path))
    m = mem.add(
        content=_TEMPLATED_BODY,
        memory_type=MemoryType.SUMMARY,
        source="auto",
        summary="Session summary — 3 cmds, 2 nodes (sess-A)",
    )
    # the explicit summary wins — the duplicated heading never leaks through
    assert m.summary == "Session summary — 3 cmds, 2 nodes (sess-A)"
    assert not m.summary.startswith("## Session Summary")


def test_two_identical_bodies_get_distinct_summaries(tmp_path):
    mem = SynapseMemory(project_path=str(tmp_path))
    a = mem.add(content=_TEMPLATED_BODY, memory_type=MemoryType.SUMMARY,
                source="auto", summary="Session summary — 3 cmds, 2 nodes (sess-A)")
    b = mem.add(content=_TEMPLATED_BODY, memory_type=MemoryType.SUMMARY,
                source="auto", summary="Session summary — 5 cmds, 1 nodes (sess-B)")
    # the symptom — identical templated bodies — now yields distinct summaries
    assert a.summary != b.summary


def test_omitted_summary_still_autoderives(tmp_path):
    # backward-compat: the defaulted param preserves the auto-derive path
    mem = SynapseMemory(project_path=str(tmp_path))
    m = mem.add(content="hello world\nmore detail", memory_type=MemoryType.NOTE,
                source="test")
    assert m.summary and m.summary.startswith("hello world")
