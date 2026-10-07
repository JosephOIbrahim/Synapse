"""TT-2 / PUX-03: the panel's read of a tool that ran but reported misses.

TT-2. The verb map knew only running/done/error, the turn accumulator recorded
only done/error, and ``_turn_evidence`` collapsed everything that was not 'ok'
to 'fail'. A 'warn' (cook_error, parms_missed, ...) now reaches the Review face
as a HOT_SOFT flag and never earns a DECISION credit.

PUX-03. COMMIT TO /STAGE? posted "routing through the consent gate" and raised
nothing. The line now says what happens: nothing is written to /stage.

The ``test_turn_receipt_credit`` convention: the real unbound method on a fake
self, with no QApplication, no SynapsePanel() and no Houdini.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qt_stub_window import qt_stub_window  # noqa: E402

with qt_stub_window():
    from synapse.panel.synapse_panel import SynapsePanel  # noqa: E402


def _evidence(tools):
    fake = SimpleNamespace(_turn_tools=list(tools), _MUTATORS=SynapsePanel._MUTATORS)
    return SynapsePanel._turn_evidence(fake)


def test_warn_row_is_a_warn_flag_and_no_credit():
    credit, flags, _paths = _evidence([("houdini_set_usd_attribute", "warn", "No prim at /a")])
    assert credit == []
    assert flags == [("warn", "houdini_set_usd_attribute — No prim at /a")]


def test_ok_mutator_still_earns_credit_and_fail_stays_fail():
    credit, flags, _paths = _evidence([
        ("houdini_create_node", "ok", "/obj/geo1"),
        ("houdini_create_material", "warn", "parms missed: karmamaterial.resx"),
        ("houdini_set_parm", "failed", "no parm"),
    ])
    assert credit == [("DECISION", "houdini_create_node", "/obj/geo1")]
    assert [f[0] for f in flags] == ["ok", "warn", "fail"]


def _status_fake():
    wf = MagicMock()
    return SimpleNamespace(_turn_tools=[], _work_face=wf), wf


def test_on_tool_status_records_a_warn_row():
    fake, wf = _status_fake()
    SynapsePanel._on_tool_status(fake, "houdini_set_usd_attribute", "warn", "No prim at /a")
    assert fake._turn_tools == [("houdini_set_usd_attribute", "warn", "No prim at /a")]
    wf.set_tool_status.assert_called_once_with(
        "houdini_set_usd_attribute", "warn", "No prim at /a")


def test_on_tool_status_done_and_error_unchanged():
    fake, _wf = _status_fake()
    SynapsePanel._on_tool_status(fake, "houdini_create_node", "done", "/obj/geo1")
    SynapsePanel._on_tool_status(fake, "houdini_set_parm", "error", "no parm")
    assert fake._turn_tools == [("houdini_create_node", "ok", "/obj/geo1"),
                                ("houdini_set_parm", "failed", "no parm")]


def test_warn_end_to_end_status_to_evidence():
    fake, _wf = _status_fake()
    SynapsePanel._on_tool_status(fake, "houdini_create_material", "warn",
                                 "parms missed: karmamaterial.resx")
    credit, flags, _paths = _evidence(fake._turn_tools)
    assert credit == []
    assert flags[0][0] == "warn"


def test_warn_flag_maps_to_the_hot_soft_dot_in_source():
    """face_review's flag colour table already maps warn to HOT_SOFT; pin it by
    source so this file never has to import the Qt face."""
    root = Path(__file__).resolve().parents[2] / "python" / "synapse" / "panel"
    text = (root / "face_review.py").read_text(encoding="utf-8")
    assert '"warn": t.HOT_SOFT' in text
    work = (root / "face_work.py").read_text(encoding="utf-8")
    assert '"warn":' in work and "t.HOT_SOFT" in work


def test_commit_line_claims_no_consent_gate():
    chat = MagicMock()
    fake = SimpleNamespace(_chat=chat, _set_work_substate=MagicMock())
    SynapsePanel._on_commit(fake)
    (line,), _kw = chat.append_system_message.call_args
    assert "consent gate" not in line
    assert "nothing was written to /stage" in line
    fake._set_work_substate.assert_called_once_with("done")


def test_no_source_still_claims_the_commit_gate():
    root = Path(__file__).resolve().parents[2] / "python" / "synapse" / "panel"
    for name in ("synapse_panel.py", "face_review.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "routing through the consent gate" not in text
        assert "*raises a gate*" not in text
