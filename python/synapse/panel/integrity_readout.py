"""IntegrityReadout — the panel's fidelity/IntegrityBlock window (Mile 4).

SYNAPSE records an ``IntegrityBlock`` per mutation (CLAUDE.md §1.3) into the
session-integrity tracker, but until now no installed widget read it — the core
guarantee *"fidelity = 1.0 or stop"* had no visible readout in the panel Joe
actually runs (panel-capability audit A.2.2). This surfaces it, honestly.

It sits in the Work-face telemetry cluster beside ``HealthInfographic`` and is
fed ``SessionIntegrityTracker.summary()`` via the worker's ``integrity_updated``
signal. The honesty rule is the whole point:

  · no data yet          → QUIET SLATE "no operations tracked yet" (NOT green,
                           NOT a fabricated 100%). ``session_fidelity`` reads a
                           clean 1.0 at ``total == 0``; ``has_data`` is the guard
                           that keeps that from looking like a real pass.
  · all-clear            → OK_SOFT (green) "fidelity 100% · N verified".
  · any violation / <1.0 → NEVER green. HOT_SOFT (amber), or NO_SOFT (red) once
                           the tracker says ``should_warn`` (3+ violations).

The verdict→color decision lives in the pure ``_fidelity_color`` helper so the
Qt-free honesty source-pin (``tests/test_panel_fidelity_honesty_sourcepin.py``)
can prove green is unreachable from a no-data / violation state. House idiom:
``QWidget`` + ``objectName('DsSection')`` + ``WA_StyledBackground``, RichText
dot-rows, ``_clear`` + rebuild — the same grammar as the render receipt.
"""

try:
    from PySide6 import QtWidgets
    from PySide6.QtCore import Qt
except ImportError:  # pragma: no cover - Houdini ships PySide6
    from PySide2 import QtWidgets
    from PySide2.QtCore import Qt

from synapse.panel.designsystem import tokens as t
from synapse.panel.designsystem import fontload


def _fidelity_color(summary):
    """Verdict → dot color for the fidelity readout.

    Green (``OK_SOFT``) is reachable ONLY from a genuine all-clear: data
    present, zero violations, full fidelity. No data → SLATE (the honest empty
    state, never a pass). Any violation or sub-1.0 fidelity → NO_SOFT when the
    tracker wants a warning (3+), else HOT_SOFT — never green. This mirrors the
    render receipt's ``_receipt_dot_color`` honesty rule (Mile 4).
    """
    if not summary or not summary.get("has_data"):
        return t.SLATE
    violations = summary.get("violations", 0)
    fidelity = summary.get("fidelity", 1.0)
    if violations == 0 and fidelity >= 1.0:
        return t.OK_SOFT
    if summary.get("should_warn"):
        return t.NO_SOFT
    return t.HOT_SOFT


def _fidelity_text(summary):
    """The readout's one status line. No-data is stated plainly; an all-clear
    reports the verified count; a degraded session reports the fidelity percent
    and the violation count. Never claims 100% without data."""
    if not summary or not summary.get("has_data"):
        return "no operations tracked yet"
    verified = summary.get("verified", 0)
    violations = summary.get("violations", 0)
    fidelity = summary.get("fidelity", 1.0)
    if violations == 0 and fidelity >= 1.0:
        return "fidelity 100%% · %d verified" % verified
    return "fidelity %.0f%% · %d violation%s" % (
        fidelity * 100, violations, "" if violations == 1 else "s")


class IntegrityReadout(QtWidgets.QWidget):
    """Compact fidelity/IntegrityBlock readout. Feed it with set_integrity()."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsSection")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._box = QtWidgets.QVBoxLayout(self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(1)
        self.set_integrity(None)   # honest empty state at rest — never green

    def set_integrity(self, summary):
        """Repaint from a ``SessionIntegrityTracker.summary()`` dict (or None).

        Rebuilds the eyebrow + a single tri-state dot-row. The dot color comes
        solely from ``_fidelity_color`` — this method never names the green
        token itself, so the honesty invariant lives in one pinned place.
        """
        self._clear(self._box)
        self._box.addWidget(self._eyebrow())
        self._box.addWidget(self._row(_fidelity_color(summary),
                                      _fidelity_text(summary)))

    def _eyebrow(self):
        """The 'INTEGRITY' section label — LABEL_SM mono, tertiary, tracked."""
        row = QtWidgets.QLabel()
        row.setTextFormat(Qt.TextFormat.RichText)
        row.setFont(fontload.tracked_font("LABEL_SM", 10, mono=True))
        row.setText('<span style="color:%s; letter-spacing:1px;">INTEGRITY</span>'
                    % t.TEXT_TERTIARY)
        return row

    def _row(self, color, text):
        """One dot-row — the same RichText dot idiom as the render receipt
        (10px mono DATA, coloured dot + TEXT_SECONDARY body)."""
        row = QtWidgets.QLabel()
        row.setTextFormat(Qt.TextFormat.RichText)
        row.setWordWrap(True)
        row.setFont(fontload.tracked_font("DATA", 10, mono=True))
        row.setText(
            '<span style="color:%s;">&#9679;</span> '
            '<span style="color:%s;">%s</span>' % (color, t.TEXT_SECONDARY, text)
        )
        return row

    def _clear(self, box):
        while box.count():
            item = box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
