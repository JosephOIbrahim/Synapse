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
        # -I drops hython's stdlib bootstrap ('No module named encodings'), so
        # the isolation flag is passed only to a plain CPython runner.
        isolate = [] if "hython" in Path(sys.executable).name.lower() else ["-I"]
        command = [bound] if bound else [sys.executable, *isolate]
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
        regions = [panel._region_cache["_build_context_ribbon"], panel._token_face]
        for region in regions:
            assert region.minimumSizeHint().width() <= 380, (region.objectName(), region.minimumSizeHint())
            layout = region.layout()
            assert layout.spacing() == t.gap(rhythm.ROLE_GAPS[region.property("rhythm_role")], density)
        header = panel._region_cache["_build_rail"]
        # Landing r3: the header row is a stack-owned toolbar (gap 4/6/3) inside
        # the shell rail; twelve chrome items each pay one gap, so this owner
        # is what keeps the rail inside the docking bound with the gutter back.
        row_owner = header.layout().itemAt(0).widget()
        assert row_owner.property("rhythm_role") == "stack"
        row = row_owner.layout()
        assert row.spacing() == t.gap(rhythm.ROLE_GAPS["stack"], density)
        assert header.layout().spacing() == t.gap(rhythm.ROLE_GAPS["shell"], density)
        assert sum(header.layout().itemAt(i).layout() is not None
                   for i in range(header.layout().count())) == 0
        # Stop is state-gated to working only; a compose must not un-hide it.
        assert panel._stop_btn.isHidden()
        assert panel._help_btn.text() == "?"
        # RULING-3: the four shell regions carry the GUTTER inset; the root
        # band pays no gap and no inset (the B4 composer cap holds).
        ribbon = panel._region_cache["_build_context_ribbon"]
        direct_face = panel._recall_card.parentWidget()
        # bc-wave BC-5: no tab row - the pills ride the ribbon shell.
        assert not panel.findChildren(QtWidgets.QWidget, "DsTabRow")
        # RULING_JOE_FIVE J5 (2026-09-05): the header meets the pane's top
        # edge and carries the shell role's top-edge condition
        # (rhythm_edge="top") - SPACE_MD air, density-scaled through
        # tokens.gap - so the wordmark is not choked by the edge. The role's
        # default is unchanged: the ribbon and the faces keep SPACE_SM.
        for shell in (header, ribbon, direct_face):
            assert shell.property("rhythm_role") == "shell", shell.objectName()
            m = shell.layout().contentsMargins()
            top = t.gap(t.SPACE_MD, density) if shell is header else t.SPACE_SM
            assert (m.left(), m.top(), m.right(), m.bottom()) == (
                t.GUTTER, top, t.GUTTER, t.SPACE_SM), shell.objectName()
        assert panel.layout().spacing() == 0
        rm = panel.layout().contentsMargins()
        assert (rm.left(), rm.top(), rm.right(), rm.bottom()) == (0, 0, 0, 0)
        # Repair round (CRUX r3): the WORK and REVIEW faces are the same
        # structural whitespace as the direct face (REDESIGN section 3 'Space -
        # load-bearing') - shells with the GUTTER inset, not margin-less groups.
        for face in (panel._work_face, panel._review_face):
            assert face is not None
            assert face.property("rhythm_role") == "shell", type(face).__name__
            m = face.layout().contentsMargins()
            assert (m.left(), m.top(), m.right(), m.bottom()) == (
                t.GUTTER, t.SPACE_SM, t.GUTTER, t.SPACE_SM), type(face).__name__
        # Repair round (CRUX r3): the brand never elides. At PANEL_PREF_WIDTH
        # the composed layout can be below its minimum (airy: 393); Qt then
        # takes from the biggest items first, and the wordmark was the biggest.
        # The Ignored chrome labels give way; the wordmark holds its own hint.
        panel.resize(t.PANEL_PREF_WIDTH, 760)
        app.processEvents()
        word = panel._wordmark
        assert word.minimumWidth() >= word.sizeHint().width(), (word.minimumWidth(), word.sizeHint().width())
        assert word.width() >= word.sizeHint().width(), (word.width(), word.sizeHint().width())
        panel.resize(380, 760)
        app.processEvents()
        # bc-wave BC-1 (direction B): the act band and its divider are gone;
        # the composer sits directly in the direct-face shell, whose own gap
        # is the transcript->composer beat.
        composer = panel._input.parentWidget()
        assert composer.parentWidget() is direct_face
        assert not direct_face.findChildren(QtWidgets.QWidget, "DsDivider")
        assert not hasattr(panel, "_font_btn")
        # RULING-4c: one type applier per widget - CHAT, TOKEN and every rail
        # control (DsVerb) share pixel size and tracking byte-for-byte.
        # (FaceReview / RecallCard verbs keep their own ratified L5 type.)
        chat_pill, token_pill = panel._face_pills["direct"], panel._face_pills["token"]
        verbs = header.findChildren(QtWidgets.QPushButton, "DsVerb")
        assert len(verbs) >= 2, [v.text() for v in verbs]
        reference = (QtGui.QFontInfo(chat_pill.font()).pixelSize(), chat_pill.font().letterSpacing())
        for widget in [token_pill, *verbs]:
            assert (QtGui.QFontInfo(widget.font()).pixelSize(),
                    widget.font().letterSpacing()) == reference, widget.text()
        # RULING-4d: the context label is UI label text (sans); the recall
        # header is the section eyebrow (mono). Two things, two treatments.
        from synapse.panel.designsystem import fontload
        sans = QtGui.QFontInfo(fontload.apply_family(QtGui.QFont())).family()
        mono = QtGui.QFontInfo(fontload.apply_family(QtGui.QFont(), mono=True)).family()
        assert sans != mono
        assert QtGui.QFontInfo(panel._ctx_label.font()).family() == sans
        assert QtGui.QFontInfo(panel._recall_card.header.font()).family() == mono
        chat_pill.setProperty("active", True)
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
        # J3 (RULING_JOE_FIVE, 2026-09-05): the SYNAPSE label is CONIFEROUS, not
        # the TEXT_SECONDARY grey that flattened both speakers ("grey for both").
        assert label_cursor.charFormat().foreground().color() == QtGui.QColor(t.CONIFEROUS)
        chat.append_synapse_message("YOUR shader stays body text.")
        chat._flush_pending_formats()
        grouped = chat.document().find("YOUR shader")
        assert not grouped.isNull()
        assert not grouped.blockFormat().property(QtGui.QTextFormat.UserProperty + 1)
        assert grouped.blockFormat().topMargin() == t.gap(rhythm.ROLE_GAPS["row"], density)
        # J3 twin: the artist's label is SIGNAL (the accent already means "the
        # artist"); searched from the end so "YOUR shader" above is never it.
        you_start = chat.document().characterCount() - 1
        chat.append_user_message("you speak")
        chat._flush_pending_formats()
        you_cursor = chat.document().find("YOU", you_start)
        assert not you_cursor.isNull()
        assert you_cursor.block().blockFormat().property(QtGui.QTextFormat.UserProperty + 1) == "YOU"
        you_label = QtGui.QTextCursor(you_cursor.block())
        you_label.movePosition(QtGui.QTextCursor.NextCharacter, QtGui.QTextCursor.KeepAnchor)
        assert you_label.charFormat().foreground().color() == QtGui.QColor(t.SIGNAL)
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
