"""BP11-IDSURF: the Identify action-row button, /identify registry, and the
compose-off-main / apply-on-main threading — driven against fake Qt leaves.

These tests drive the REAL ``SynapsePanel`` handlers (the
``test_rope_switcher_wires_profile`` convention: unbound methods on a fake self,
no QApplication, no Houdini) so the production wiring itself is pinned, not a
paraphrase of it. Thread placement is asserted with real thread identities
through a marshaller that runs ``run_on_main`` closures on the test's main
thread — so moving compose onto the main thread (the crucible's mutation) makes
the thread rows go red.
"""
from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qt_stub_window import qt_stub_window  # noqa: E402

with qt_stub_window():
    from synapse.panel import synapse_panel as sp  # noqa: E402
    from synapse.panel.synapse_panel import SynapsePanel  # noqa: E402
    from synapse.panel.tool_palette import _load_entries  # noqa: E402
    from synapse.panel.command_palette import PANEL_ANSWERED_COMMANDS  # noqa: E402

_IDENTIFY_TOOLTIP = sp._IDENTIFY_TOOLTIP
_IDENTIFY_NO_SELECTION = sp._IDENTIFY_NO_SELECTION


# --------------------------------------------------------------------------- #
# Fake Qt leaves — surface only, no logic.
# --------------------------------------------------------------------------- #

class _FakeButton:
    def __init__(self):
        self._enabled = True
        self._tooltip = ""

    def setEnabled(self, value):
        self._enabled = bool(value)

    def isEnabled(self):
        return self._enabled

    def setToolTip(self, text):
        self._tooltip = str(text)

    def toolTip(self):
        return self._tooltip


class _Chat:
    def __init__(self):
        self.messages = []

    def append_system_message(self, text, *a, **k):
        self.messages.append(text)


def _fake_hou_with_selection(paths):
    nodes = [SimpleNamespace(path=lambda p=p: p) for p in paths]
    return SimpleNamespace(selectedNodes=lambda: nodes,
                           node=lambda p: SimpleNamespace(path=lambda: p))


def _panel(**attrs):
    """A fake self that delegates the real Identify helper methods back to the
    unbound ``SynapsePanel`` implementations (the ``_FakePanel`` convention),
    while carrying whatever leaf attributes a test supplies."""
    fake = SimpleNamespace(**attrs)
    if not hasattr(fake, "_identify_selection_paths"):
        fake._identify_selection_paths = lambda: SynapsePanel._identify_selection_paths(fake)
    fake._identify_worker = lambda paths, mode: SynapsePanel._identify_worker(fake, paths, mode)
    return fake


# --------------------------------------------------------------------------- #
# T2: /identify is registered once and answered by the panel (never the model).
# --------------------------------------------------------------------------- #

def test_identify_is_panel_answered_and_appears_exactly_once():
    assert "/identify" in PANEL_ANSWERED_COMMANDS
    rows = _load_entries()
    identify_rows = [r for r in rows if r.get("send") == "/identify"]
    assert len(identify_rows) == 1, identify_rows
    row = identify_rows[0]
    assert row.get("panel_answered") is True
    assert row.get("group") == "PANEL"


def test_send_identify_toggles_locally_and_never_reaches_the_model():
    """A model send path spy (``_prepare_connection``) must stay at count 0."""
    for text, mode in (("/identify", "toggle"), ("/IDENTIFY", "toggle"),
                       ("/identify off", "clear")):
        fake = SimpleNamespace(
            _run_identify=Mock(),
            _prepare_connection=Mock(side_effect=AssertionError("reached model send")),
            _chat=_Chat(),
            _worker=None,
        )
        assert SynapsePanel._send(fake, text) is True
        fake._run_identify.assert_called_once_with(mode)
        fake._prepare_connection.assert_not_called()


# --------------------------------------------------------------------------- #
# T1: the button enables on a selection and disables with a reason without one.
# --------------------------------------------------------------------------- #

def test_button_disabled_with_a_reason_when_nothing_is_selected(monkeypatch):
    monkeypatch.setitem(sys.modules, "hou", _fake_hou_with_selection([]))
    fake = _panel(_identify_btn=_FakeButton())
    SynapsePanel._refresh_identify_enabled(fake)
    assert fake._identify_btn.isEnabled() is False
    assert fake._identify_btn.toolTip() == _IDENTIFY_NO_SELECTION
    assert fake._identify_btn.toolTip().strip()  # the reason is non-empty


def test_button_enabled_with_the_action_tooltip_when_a_selection_exists(monkeypatch):
    monkeypatch.setitem(sys.modules, "hou", _fake_hou_with_selection(["/obj/geo1"]))
    fake = _panel(_identify_btn=_FakeButton())
    SynapsePanel._refresh_identify_enabled(fake)
    assert fake._identify_btn.isEnabled() is True
    assert fake._identify_btn.toolTip() == _IDENTIFY_TOOLTIP


def test_run_identify_with_nothing_selected_says_why_and_launches_nothing(monkeypatch):
    monkeypatch.setitem(sys.modules, "hou", _fake_hou_with_selection([]))
    launched = []
    fake = _panel(_chat=_Chat(), _identify_launch=lambda fn: launched.append(fn))
    SynapsePanel._run_identify(fake, "toggle")
    assert launched == []
    assert fake._chat.messages == [_IDENTIFY_NO_SELECTION]


# --------------------------------------------------------------------------- #
# Acceptance 3: compose + library run OFF the main thread, apply runs ON it.
# --------------------------------------------------------------------------- #

def _facts_stub(paths, record):
    record["facts_ident"] = threading.get_ident()
    return [{
        "path": p, "help_url": None, "hda_help": None,
        "type_name": "polybevel", "type_label": "PolyBevel", "category": "Sop",
        "params": [], "errors": [], "warnings": [], "bypassed": False,
    } for p in paths]


def test_compose_and_library_run_off_main_and_apply_runs_on_main(monkeypatch):
    from synapse.identify import apply as amod
    from synapse.identify import compose as cmod
    from synapse.identify import facts as fmod
    from synapse.identify import library as lmod

    main_ident = threading.get_ident()
    record: dict = {}
    marshalled: "queue.Queue" = queue.Queue()

    # Marshaller: run_on_main closures execute on the test's MAIN thread, so a
    # step's real thread identity tells us where it ran.
    def fake_run_on_main(fn):
        done = threading.Event()
        box: dict = {}

        def job():
            box["result"] = fn()
            done.set()

        marshalled.put(job)
        assert done.wait(5), "run_on_main closure was never drained"
        return box["result"]

    def fake_launch(fn):
        worker = threading.Thread(target=fn, daemon=True)
        worker.start()
        while worker.is_alive() or not marshalled.empty():
            try:
                marshalled.get(timeout=0.05)()
            except queue.Empty:
                continue
        worker.join(5)

    real_compose = cmod.compose
    real_summarize = lmod.summarize

    def spy_compose(facts, *a, **k):
        record["compose_ident"] = threading.get_ident()
        return real_compose(facts, *a, **k)

    def spy_summarize(*a, **k):
        record["library_ident"] = threading.get_ident()
        return real_summarize(*a, **k)

    def spy_toggle(items, total=None, editor=None):
        record["apply_ident"] = threading.get_ident()
        record["apply_total"] = total
        return {"action": "show", "shown": len(list(items)), "total": total}

    monkeypatch.setitem(sys.modules, "hou",
                        SimpleNamespace(node=lambda p: SimpleNamespace(path=lambda: p)))
    monkeypatch.setattr(fmod, "read_selection_facts",
                        lambda paths: _facts_stub(paths, record))
    monkeypatch.setattr(cmod, "compose", spy_compose)
    monkeypatch.setattr(lmod, "summarize", spy_summarize)
    monkeypatch.setattr(amod, "toggle", spy_toggle)

    fake = _panel(
        _identify_selection_paths=lambda: ["/obj/geo1"],
        _identify_launch=fake_launch,
        _identify_run_on_main=fake_run_on_main,
        _chat=_Chat(),
    )
    SynapsePanel._run_identify(fake, "toggle")

    # The live facts read and the comment/flag write are marshalled ONTO main.
    assert record["facts_ident"] == main_ident
    assert record["apply_ident"] == main_ident
    # Library lookup and composition run OFF main (on the worker thread).
    assert record["compose_ident"] != main_ident
    assert record["library_ident"] != main_ident
    assert record["apply_total"] == 1


# --------------------------------------------------------------------------- #
# T3: the Selection Inspector's read-only Identify column.
# --------------------------------------------------------------------------- #

def test_inspector_stays_read_only_no_writer_calls():
    """Predicate 4: the Inspector owns no Houdini objects — it never writes a
    comment, toggles a display flag, or opens an undo group."""
    src = (Path(__file__).resolve().parents[2]
           / "python/synapse/panel/selection_inspector.py").read_text(encoding="utf-8")
    for token in ("setComment", "setGenericFlag", ".undos"):
        assert token not in src, token


def test_inspector_identify_column_shows_compose_text(monkeypatch):
    with qt_stub_window():
        from synapse.panel import selection_inspector as si
    from synapse.identify import compose as cmod
    from synapse.identify import library as lmod

    monkeypatch.setattr(lmod, "summarize",
                        lambda *a, **k: ("Bevels polygon edges", "library"))
    facts = {
        "path": "/obj/geo/bevel1", "help_url": "operator:Sop/polybevel",
        "hda_help": None, "type_label": "PolyBevel", "type_name": "polybevel",
        "category": "Sop", "lop_writes": None,
        "params": [{"name": "offset", "label": "Offset", "kind": "float",
                    "value": 0.25, "multi": False, "is_expression": False,
                    "hidden": False}],
        "errors": [], "warnings": [], "bypassed": False,
    }
    node = {"path": "/obj/geo/bevel1", "type": "polybevel", "category": "Sop"}

    cell = si.identify_cell_text(node, facts_reader=lambda path: dict(facts))
    expected = cmod.bubble_text(
        {**facts, "summary": "Bevels polygon edges", "summary_source": "library"})
    assert cell == expected
    assert "Bevels polygon edges" in cell


def test_inspector_identify_column_degrades_honestly_without_facts():
    """When no facts are available (reader returns None, or headless), the cell
    shows only what the bounded inspection read — the node type — never a
    guessed summary."""
    with qt_stub_window():
        from synapse.panel import selection_inspector as si
    node = {"path": "/obj/geo/bevel1", "type": "polybevel", "category": "Sop"}
    cell = si.identify_cell_text(node, facts_reader=lambda path: None)
    assert "polybevel" in cell
    assert cell  # never empty for a real node row
