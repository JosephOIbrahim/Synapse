"""probe_first_click.py -- PNL-L3B: the first click cannot dead-end.

    QT_QPA_PLATFORM=offscreen hython python/synapse/panel/scripts/probe_first_click.py

WHAT IT PROVES. An artist opens SYNAPSE on an empty scene, types "/" in an
empty composer, and picks the first thing they see. Before this leg the top of
that list was whatever the alphabet had put there -- usually a registry tool
row whose only honest answer is "nothing is selected". This probe walks the
first EIGHT rows of the list the artist actually gets and asserts each one
leads somewhere on an empty scene:

    rows 1-4   open a local view -- render workspace, updates, saved
               networks, saved lookdev. They never reach a model.
    row 5      restore last session, which on a fresh boot answers with the
               'No parked previous session' system line. An answer, not a
               dead end.
    rows 6-8   the ASK rows. They send a prompt sentence that states its own
               empty-selection fallback, so the model can act with nothing
               selected.

READ-ONLY, and now actually. It builds the panel offscreen against a throwaway settings file
(SYNAPSE_PANEL_SETTINGS in a temp dir, so the artist's real picks are never
read or written), never touches the Houdini scene, and never sends anything
to a model: rows 6-8 are INSPECTED, not fired. The four local-view openers of
rows 1-4 are replaced with recorders for the duration, so the probe proves the
row -> send -> local-view wiring without putting four dialogs on screen.

EXIT. 0 when all eight rows lead somewhere. Non-zero on the first dead end,
with the row that dead-ended named. It always prints the eight row titles.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback


def _prepare_env() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
    if not os.environ.get("SYNAPSE_PANEL_SETTINGS"):
        os.environ["SYNAPSE_PANEL_SETTINGS"] = os.path.join(
            tempfile.mkdtemp(prefix="synapse_probe_first_click_"),
            "panel_settings.json")
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(os.path.dirname(here)))  # .../python
    if root not in sys.path:
        sys.path.insert(0, root)

    # PNL-L3B repair. SYNAPSE_PANEL_SETTINGS isolates the panel's SETTINGS only. The
    # conversation store resolves somewhere else entirely -- from the HIP directory, or from a
    # SHARED temp dir when hou is absent (session_store.py:57). So merely constructing
    # SynapsePanel() runs load_conversation_scoped(), which parks the live conversation with
    # os.replace(target, prev) at session_store.py:250 and DESTROYS whatever was already parked
    # there. A probe whose own docstring says READ-ONLY was eating an artist's previous session.
    # Pin the store at a throwaway directory before any panel is built.
    from synapse.server import session_store as _store
    _scratch = tempfile.mkdtemp(prefix="synapse_probe_store_")
    _store._resolve_store_dir = lambda _d=_scratch: _d


class _Recorder:
    """Stands in for a local-view opener and remembers that it was called."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *_args, **_kwargs):
        self.calls += 1


# The four rows that must open a local view, in the order the list shows them,
# keyed by the send the panel intercepts.
_LOCAL_VIEWS = [
    ("/render", "_open_render_workspace"),
    ("/events", "_open_notifications"),
    ("/saved-recipes", "_open_saved_recipes"),
    ("/lookdev-suggestion", "_open_lookdev_suggestion"),
]
_RESTORE_SEND = "/restore-session"
_RESTORE_LINE = "No parked previous session"
_FALLBACK_PHRASE = "if nothing is selected"


def _rows_of(palette):
    """(title, send) for every OPTION in the list -- group heads carry no
    send, so they drop out here and never count toward the eight."""
    from PySide6.QtCore import Qt
    rows = []
    for i in range(palette._list.count()):
        item = palette._list.item(i)
        send = item.data(Qt.ItemDataRole.UserRole)
        if send:
            rows.append((item.text().strip().lstrip("⚠").strip(), send))
    return rows


def probe() -> int:
    from PySide6 import QtWidgets
    from synapse.panel.designsystem import fontload

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    fontload.load_application_fonts()

    from synapse.panel.synapse_panel import SynapsePanel

    panel = SynapsePanel()
    panel._recompose("expert")
    panel.resize(340, 760)
    panel.show()
    app.processEvents()

    failures: list[str] = []
    try:
        # Open Commands the way the artist does: "/" on an empty composer.
        panel._input.clear()
        panel._input.slash.emit()
        app.processEvents()
        palette = getattr(panel, "_palette", None)
        if palette is None:
            print("DEAD END: the slash signal opened no palette.")
            return 1

        rows = _rows_of(palette)
        print("first eight rows of Commands (empty scene, empty composer):")
        for index, (title, _send) in enumerate(rows[:8], start=1):
            print("  %d. %s" % (index, title))
        if len(rows) < 8:
            print("DEAD END: the list offers only %d rows." % len(rows))
            return 1

        # A standing property of the whole list, not just the first eight:
        # the only sends that are still literals are the five the panel
        # answers itself.
        slashes = [s for _t, s in rows if str(s).startswith("/")]
        print("sends beginning with '/': %d" % len(slashes))
        if len(slashes) != 5:
            failures.append("expected exactly 5 literal sends, found %d: %s"
                            % (len(slashes), slashes))

        # -- rows 1-4: a local view, no model ---------------------------
        for position, (expected_send, opener) in enumerate(_LOCAL_VIEWS, start=1):
            title, send = rows[position - 1]
            if send != expected_send:
                failures.append("row %d (%s) sends %r, expected %r"
                                % (position, title, send, expected_send))
                continue
            recorder = _Recorder()
            original = getattr(panel, opener)
            setattr(panel, opener, recorder)
            try:
                handled = panel._send(send)
            finally:
                setattr(panel, opener, original)
            if not handled:
                failures.append("row %d (%s) was not answered by the panel"
                                % (position, title))
            elif recorder.calls != 1:
                failures.append("row %d (%s) did not open %s (%d calls)"
                                % (position, title, opener, recorder.calls))

        # -- row 5: restore answers, even with nothing parked -----------
        title, send = rows[4]
        if send != _RESTORE_SEND:
            failures.append("row 5 (%s) sends %r, expected %r"
                            % (title, send, _RESTORE_SEND))
        else:
            lines: list[str] = []
            original = panel._chat.append_system_message

            def _capture(text, *args, **kwargs):
                lines.append(str(text))
                return original(text, *args, **kwargs)

            # The fresh-boot case, forced. Left to the real store this row
            # would CONSUME whatever the artist has parked on this
            # workstation -- the probe would stop being read-only, and on a
            # machine with a parked session it would measure the wrong
            # branch. The panel's own wiring is what is under test here.
            from synapse.server import session_store as _store
            store_original = _store.restore_previous_conversation
            _store.restore_previous_conversation = lambda: []
            panel._chat.append_system_message = _capture
            try:
                handled = panel._send(send)
            finally:
                panel._chat.append_system_message = original
                _store.restore_previous_conversation = store_original
            if not handled:
                failures.append("row 5 (%s) was not answered by the panel" % title)
            elif not any(_RESTORE_LINE in line for line in lines):
                failures.append("row 5 (%s) said %r, expected the %r line"
                                % (title, lines, _RESTORE_LINE))

        # -- rows 6-8: a prompt that works with nothing selected --------
        # INSPECTED, never fired: sending them would reach a model.
        for position in (6, 7, 8):
            title, send = rows[position - 1]
            send = str(send)
            if send.startswith("/"):
                failures.append("row %d (%s) still sends a bare literal %r"
                                % (position, title, send))
            elif len(send.split()) < 4:
                failures.append("row %d (%s) sends %r, which is not a prompt"
                                % (position, title, send))
            elif _FALLBACK_PHRASE not in send.lower():
                failures.append(
                    "row %d (%s) sends a prompt that never says what happens "
                    "with nothing selected: %r" % (position, title, send))
    finally:
        try:
            panel.close()
        except Exception:
            pass

    if failures:
        print("")
        print("DEAD ENDS (%d):" % len(failures))
        for f in failures:
            print("  - %s" % f)
        return 1
    print("")
    print("first click: all eight rows lead somewhere on an empty scene.")
    return 0


def main() -> int:
    _prepare_env()
    try:
        return probe()
    except Exception:
        traceback.print_exc()
        print("DEAD END: the probe could not complete.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
