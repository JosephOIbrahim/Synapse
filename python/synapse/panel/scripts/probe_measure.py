"""probe_measure.py - MEASURE the transcript's characters per line (PNL-L5).

``ChatDisplay._MEASURE_CHARS`` is a TARGET. This probe reports what the
transcript actually lays out, because the two are not the same number: the
target is multiplied by ``QFontMetricsF.averageCharWidth()``, a weighted
average over the whole font, while real prose has its own letter mix, its own
spaces, and wraps on word boundaries.

So nothing here is arithmetic. A real ``ChatDisplay`` renders a known
400-character paragraph, and the count comes off the laid-out
``QTextLine``s - ``line.textLength()`` per wrapped line of the body block.

Four measurements, the corners of the space the panel is actually used in:

    panel width 340 px  (the narrow dock)  x  Aa 1.0 and Aa 1.6
    panel width 1100 px (a wide dock)      x  Aa 1.0 and Aa 1.6

The band is **45-75 characters**, and the verdict has two halves, because two
different things can put a corner outside it and they take opposite fixes:

* **MEASURE failure** - over 75 characters anywhere, or under 45 while the
  measure was still narrowing a column that had width to spare. The rule is
  wrong. The probe FAILS.
* **PANE-LIMITED** - under 45 because the whole pane is already the column and
  45 characters of type that size would not fit in it. No measure rule can
  widen a dock. The probe prints the arithmetic and does not call it a pass in
  disguise: the corner is named, on its own line, every run.

The brief for PNL-L5 asked for all four corners in band. Measured, two of them
cannot be: at a 340 px dock the column IS 340 px, and at Aa 1.6 one character
costs 12.7 px, so 45 characters would need 570 px. The 45 floor is a property
of a column wide enough to have one - it is reported here, not enforced
against physics. Run the probe to see the current numbers.

Read-only: it builds widgets offscreen, measures, and writes nothing.

How to run (from the repo root)::

    QT_QPA_PLATFORM=offscreen PYTHONPATH=$PWD/python \\
        hython python/synapse/panel/scripts/probe_measure.py

Exit codes: 0 no measure failure; 1 a measure failure; 2 no usable Qt.
"""

import os
import sys

# The transcript is a reading surface; these are the numbers it is judged on.
MIN_CPL = 45
MAX_CPL = 75

# A 400-character paragraph of ordinary prose - ordinary because the letter mix
# is what a proportional font's wrap depends on. Counted, not estimated: the
# probe asserts the length below so a future edit cannot silently change it.
PARAGRAPH = (
    "The transcript is a reading surface before it is a log, so the measure "
    "has to hold at every size the artist can pick. A line that runs too long "
    "makes the eye lose its place on the return sweep, and a line that runs "
    "too short breaks a sentence into pieces the reader has to reassemble. "
    "Between those two failures sits the band this probe checks for, "
    "forty-five to seventy-five characters on each line."
)

WIDTHS = (340, 1100)
SCALES = (1.0, 1.6)


def _w(line=""):
    sys.stdout.write(line + "\n")


def _qt():
    """Return (QtWidgets, QtGui) for whichever PySide this seat ships."""
    try:
        from PySide6 import QtWidgets, QtGui
        return QtWidgets, QtGui, "PySide6"
    except Exception:
        try:
            from PySide2 import QtWidgets, QtGui
            return QtWidgets, QtGui, "PySide2"
        except Exception:
            return None, None, None


def _body_lines(chat, QtGui):
    """Characters per laid-out line for the BODY of the last turn.

    Walks the document's blocks, keeps the longest one (the paragraph - the
    speaker label and the timestamp are their own short block), and reads its
    ``QTextLayout`` line by line. The FINAL line of a wrapped paragraph is a
    remainder, not a measure, so it is dropped when there is more than one.
    """
    doc = chat.document()
    block = doc.begin()
    best = None
    while block.isValid():
        if best is None or len(block.text()) > len(best.text()):
            best = block
        block = block.next()
    if best is None:
        return []
    layout = best.layout()
    lines = [layout.lineAt(i).textLength() for i in range(layout.lineCount())]
    if len(lines) > 1:
        lines = lines[:-1]
    return [n for n in lines if n > 0]


def probe():
    QtWidgets, QtGui, binding = _qt()
    if QtWidgets is None:
        _w("UNAVAILABLE: no PySide6/PySide2 - run under hython, not python.")
        return 2

    assert len(PARAGRAPH) == 400, "paragraph is %d chars, not 400" % len(PARAGRAPH)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from synapse.panel.designsystem import fontload, qss, rhythm
    from synapse.panel.chat_display import ChatDisplay
    fontload.load_application_fonts()

    _w("=" * 62)
    _w("SYNAPSE PNL-L5 - transcript measure probe (read-only, %s)" % binding)
    _w("paragraph: %d characters   band: %d-%d cpl" % (len(PARAGRAPH), MIN_CPL, MAX_CPL))
    _w("=" * 62)

    failures = []
    pane_limits = []
    for width in WIDTHS:
        for scale in SCALES:
            root = QtWidgets.QWidget()
            root.setObjectName("DsRoot")
            root.setProperty("density", "standard")
            qss.apply_to(root)          # via the design system: see qss.apply_to
            lay = QtWidgets.QVBoxLayout(root)
            rhythm.apply_layout_margins(lay, "band")   # the sanctioned zero-margin role
            chat = ChatDisplay(root)
            lay.addWidget(chat)
            root.resize(width, 600)
            root.show()
            app.processEvents()
            chat.font_scale = scale
            chat.append_synapse_message(PARAGRAPH)
            chat._flush_pending_formats()
            app.processEvents()
            # The measure is applied in resizeEvent; a scale change after show
            # has to be re-laid out before anything is read back.
            root.resize(width, 601)
            app.processEvents()

            lines = _body_lines(chat, QtGui)
            cpl = (sum(lines) / float(len(lines))) if lines else 0.0
            # The column the text actually got, and what one character of it
            # cost. Without these two a failure is a number with no cause:
            # a measure that is too generous and a pane that is too narrow
            # both read as "out of band" and take opposite fixes.
            col = float(chat.document().textWidth() or 0.0)
            per_char = (col / cpl) if cpl else 0.0
            # The width the widget COULD have given the text, before the
            # measure narrowed anything - the same quantity resizeEvent works
            # from. If the column already equals it, the measure is not what is
            # holding the line short; the dock is.
            m = chat.viewportMargins()
            avail = float(chat.viewport().width() + m.left() + m.right())
            pane_limited = (cpl < MIN_CPL and col >= avail - 1.0
                            and per_char * MIN_CPL > col)
            if cpl > MAX_CPL or (cpl < MIN_CPL and not pane_limited):
                verdict = "MEASURE FAILURE"
                failures.append((width, scale, cpl, col, per_char, avail))
            elif pane_limited:
                verdict = "PANE-LIMITED"
                pane_limits.append((width, scale, cpl, col, per_char))
            else:
                verdict = "ok"
            _w("panel %4dpx  Aa %.2f  ->  %5.1f cpl  (%d lines, column %.0fpx "
               "of %.0fpx available, %.1fpx/char)  %s"
               % (width, scale, cpl, len(lines), col, avail, per_char, verdict))
            root.close()
            root.deleteLater()
            app.processEvents()

    _w("-" * 62)
    # Named every run, pass or fail. A corner nobody can fix is still a corner
    # the reader lives in, and a silent one would be an abstention printed as
    # a pass.
    for width, scale, cpl, col, per_char in pane_limits:
        _w("PANE-LIMITED  %dpx @ Aa %.2f measured %.1f cpl, under the %d floor."
           % (width, scale, cpl, MIN_CPL))
        _w("              the column is %.0fpx - the whole pane - and one "
           "character costs %.1fpx, so %d would need %.0fpx. No measure rule "
           "reaches it; a wider dock or a lower Aa step does."
           % (col, per_char, MIN_CPL, per_char * MIN_CPL))
    if failures:
        for width, scale, cpl, col, per_char, avail in failures:
            _w("FAIL  %dpx @ Aa %.2f measured %.1f cpl, outside %d-%d - and "
               "this one IS the measure: it held the column to %.0fpx of the "
               "%.0fpx available."
               % (width, scale, cpl, MIN_CPL, MAX_CPL, col, avail))
        return 1
    _w("PASS  no measure failure: nothing over %d cpl, and every corner under "
       "%d is pane-limited (%d of %d)."
       % (MAX_CPL, MIN_CPL, len(pane_limits), len(WIDTHS) * len(SCALES)))
    return 0


if __name__ == "__main__":
    sys.exit(probe())
