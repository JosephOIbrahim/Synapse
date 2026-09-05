"""Real Qt camera probes in isolated processes (never substitutes a mock Qt)."""

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


if __name__ != "__main__":
    import pytest

    @pytest.mark.parametrize("density", ["airy", "standard", "tight"])
    def test_camera_rows_card_and_document_in_real_qt(density):
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", SYNAPSE_REDUCED_MOTION="1",
                   PYTHONDONTWRITEBYTECODE="1")
        bound = os.environ.get("SYNAPSE_HYTHON")
        command = [bound] if bound else [sys.executable, "-I"]
        run = subprocess.run([*command, str(Path(__file__).resolve()), density],
                             cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
        if run.returncode == 77:
            pytest.skip(run.stdout.strip())
        assert run.returncode == 0, run.stdout + run.stderr
        assert '"verified": true' in run.stdout


def probe(density):
    import logging
    logging.disable(logging.CRITICAL)  # avoid the product's external log sink
    sys.path.insert(0, str(ROOT / "python"))
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        try:
            from PySide2 import QtCore, QtGui, QtWidgets
        except ImportError:
            print("NOT_RUN: no PySide6/PySide2 in this interpreter")
            raise SystemExit(77)
    from synapse.panel import compositor
    from synapse.panel.designsystem import rhythm, tokens as t
    from synapse.panel.synapse_panel import SynapsePanel
    from synapse.panel.face_token import UNKNOWN
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = SynapsePanel()
    profile = {"airy": "curious", "standard": "expert", "tight": "ml"}[density]
    panel._recompose(profile)
    panel.resize(380, 760)
    panel.show()
    app.processEvents()
    composed_initial = {name: list(widget.minimumSizeHint().toTuple())
                        for name, widget in panel._region_cache.items()}
    composed_initial["panel"] = list(panel.minimumSizeHint().toTuple())
    try:
        # Existing layout owners, including nested anonymous rows, all inherit
        # their owner's spacing. These are geometry checks, not source guesses.
        regions = [panel._region_cache["_build_mode_bar"],
                   panel._font_btn.parentWidget(), panel._token_face]
        for region in regions:
            assert region.minimumSizeHint().width() <= 380, (region.objectName(), region.minimumSizeHint())
            layout = region.layout()
            assert layout.spacing() == t.gap(rhythm.ROLE_GAPS[region.property("rhythm_role")], density)
        header = panel._region_cache["_build_rail"]
        row = header.layout().itemAt(0).layout()
        assert row.spacing() == header.layout().spacing()
        assert sum(header.layout().itemAt(i).layout() is not None
                   for i in range(header.layout().count())) == 1
        assert panel._help_btn.text() == "?"
        assert all(p.property("rhythm_role") == "row" for p in panel._profile_pills.values())
        active = panel._profile_pills["expert"]
        active.setProperty("active", True)
        compositor._repolish_tree(panel)
        # The inherited active underline is SIGNAL. The sheet is the owner.
        assert t.SIGNAL in panel.styleSheet()
        for value in panel._token_face._rows.values():
            assert value.objectName() == "DsParmValue"
            assert value.parentWidget().property("rhythm_role") == "parm_row"
            assert value.width() == 64
        panel._token_face.set_row("cost", None)
        assert panel._token_face._rows["cost"].text() == UNKNOWN == "UNKNOWN"
        panel._token_face.set_row("cost", 0)
        assert panel._token_face._rows["cost"].text() == "0"

        card = panel._recall_card
        for status, hit, expected in (("SUCCESS", True, "HIT"), ("BLOCKED", True, "BLOCKED"),
                                      ("UNAVAILABLE", True, "UNAVAILABLE"), ("SUCCESS", False, "NO HIT")):
            panel._display_recall_result({"STATUS": status, "payload": {"hit": hit, "deposit": "line\n" * 100}})
            app.processEvents()
            assert card.status.text() == expected
            assert card.minimumSizeHint().width() <= 380
            assert card.layout().spacing() == 0
            assert card.header.height() == 40
            footer = card.findChild(QtWidgets.QWidget, "DsCardFooter")
            assert footer.height() == 40
            ink = card.status.palette().color(QtGui.QPalette.WindowText)
            assert ink == QtGui.QColor(t.HOT_SOFT if status == "BLOCKED" else t.TEXT_SECONDARY)
        deposit = "<b>literal deposit</b>\n" * 50
        card.set_result({"found": True, "matches": [{"content": deposit}]})
        assert card.body.toPlainText() == deposit
        card._copy_deposit()
        assert app.clipboard().text() == deposit
        card.set_result({"found": True})
        assert card.body.toPlainText() == "UNKNOWN" and not card.action.isEnabled()

        chat = panel._chat
        chat.clear()
        chat.append_synapse_message("First reply.\n\nSecond paragraph.")
        chat._flush_pending_formats()
        first = chat.document().begin()
        # Switching from the greeting leaves an empty timestamp separator.
        # Measure the inserted reply, not that preceding placeholder block.
        while first.isValid() and not first.text():
            first = first.next()
        assert first.isValid()
        assert first.blockFormat().lineHeight() == t.chat_leading_px()
        assert first.blockFormat().topMargin() == t.gap(rhythm.ROLE_GAPS["group"], density)
        label_cursor = QtGui.QTextCursor(first)
        label_cursor.movePosition(QtGui.QTextCursor.NextCharacter, QtGui.QTextCursor.KeepAnchor)
        assert label_cursor.charFormat().foreground().color() == QtGui.QColor(t.TEXT_SECONDARY)
        chat.append_synapse_message("YOUR shader stays body text.")
        chat._flush_pending_formats()
        grouped = chat.document().find("YOUR shader")
        assert not grouped.isNull()
        assert not grouped.blockFormat().property(QtGui.QTextFormat.UserProperty + 1)
        assert grouped.blockFormat().topMargin() == t.gap(rhythm.ROLE_GAPS["row"], density)
        content = chat.toPlainText()
        for target in ("tight", "airy", density):
            panel._recompose({"airy": "curious", "standard": "expert", "tight": "ml"}[target])
            assert chat.toPlainText() == content
            assert first.blockFormat().topMargin() == t.gap(rhythm.ROLE_GAPS["group"], target)
        chat.font_scale = 1.5
        chat.begin_stream()
        chat.stream_chunk("live words")
        assert chat.document().defaultFont().pixelSize() == t.scaled(t.SIZE_BODY, 1.5)
        live = chat.document().find("live words")
        assert live.charFormat().font().pixelSize() == t.scaled(t.SIZE_BODY, 1.5)
        panel._input.setPlainText("existing prompt")
        cursor = panel._input.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        panel._input.setTextCursor(cursor)
        panel._set_prompt_font(panel._input, 1.5)
        assert panel._input.currentFont().pixelSize() == t.scaled(t.SIZE_UI, 1.5)
        old_text = panel._input.document().find("existing prompt")
        assert old_text.charFormat().font().pixelSize() == t.scaled(t.SIZE_UI, 1.5)
        print(json.dumps({"density": density, "verified": True,
                          "scope": "owned component assertions; composed gate not certified",
                          "composed_initial": composed_initial}, sort_keys=True))
    finally:
        panel.close()


if __name__ == "__main__":
    assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"
    assert os.environ.get("SYNAPSE_REDUCED_MOTION") == "1"
    probe(sys.argv[1])
