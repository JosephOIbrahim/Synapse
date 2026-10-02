"""The turn receipt credits every builder the worker may call.

THE GAP (the recorded D6 GUI test, 2026-10-02). After a turn that drew the
camera path the panel showed no receipt and no REVERT. ``_turn_evidence``
credits a tool as a change only when its NAME carries one of the ``_MUTATORS``
keywords, and ``synapse_spatial_trail`` carried none. ``_on_done`` then hides
the receipt, so the artist's only way back was Houdini's own undo.
``synapse_solaris_assemble_chain`` had the same gap and nobody had met it yet.

THE PIN. The worker's builder allowlist is the short list of composite tools
the autonomous worker may run despite a 'review' gate: each one is a scene
change in one undo step, which is exactly what a receipt is for. Every name on
it must earn credit, so adding a builder without crediting it fails here and
not at the panel.

WHAT THIS DOES NOT CLAIM. The keyword list is still a name heuristic. Other
tools that are not read-only still carry no keyword: 30 of those the worker
may call, counted on 2026-10-02, among them houdini_modify_usd_prim and
houdini_reference_usd. Crediting from the undo stack instead of from names is
the fix, and it is not made here.

The ``test_identify_button`` convention: the real unbound method on a fake
self, with no QApplication and no Houdini.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qt_stub_window import qt_stub_window  # noqa: E402

with qt_stub_window():
    from synapse.panel.synapse_panel import SynapsePanel  # noqa: E402

from synapse.panel import worker_policy  # noqa: E402


def _evidence(tools):
    fake = SimpleNamespace(_turn_tools=list(tools), _MUTATORS=SynapsePanel._MUTATORS)
    return SynapsePanel._turn_evidence(fake)


@pytest.mark.parametrize("tool", sorted(worker_policy._WORKER_BUILDER_ALLOWLIST))
def test_every_builder_the_worker_may_call_earns_a_receipt(tool):
    credit, flags, _paths = _evidence([(tool, "ok", "")])
    assert credit == [("DECISION", tool, "")], (
        "%s changes the scene and is on the worker's builder allowlist, but no "
        "_MUTATORS keyword matches its name, so a turn that ran it shows no "
        "receipt and no REVERT" % tool)
    assert flags == [("ok", tool)]


def test_the_allowlist_still_holds_the_tools_this_pin_was_written_for():
    """If the allowlist is renamed or emptied the parametrize above passes
    vacuously. Name the three it must cover."""
    assert {"synapse_solaris_build_graph", "synapse_solaris_assemble_chain",
            "synapse_spatial_trail"} <= set(worker_policy._WORKER_BUILDER_ALLOWLIST)


def test_a_failed_builder_is_a_flag_and_never_a_credit():
    credit, flags, _paths = _evidence([("synapse_spatial_trail", "failed", "No trail drawn")])
    assert credit == []
    assert flags == [("fail", "synapse_spatial_trail — No trail drawn")]


def test_reads_stay_uncredited():
    """The trail's read-only twin measures and writes nothing: no receipt."""
    for tool in ("synapse_spatial_path", "houdini_stage_info", "houdini_query_prims"):
        credit, _flags, _paths = _evidence([(tool, "ok", "")])
        assert credit == [], tool
