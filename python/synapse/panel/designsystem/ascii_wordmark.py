"""Local, resolution-independent ASCII artwork for the startup invitation."""

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover - Qt5 host fallback
    from PySide2 import QtCore, QtGui, QtWidgets

from . import fontload, tokens as t


# An original five-by-seven alphabet. Two ASCII columns per pixel keep the
# letterforms proportionate in a monospace face. No external font/art asset.
_GLYPHS = {
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "N": ("10001", "11001", "11001", "10101", "10011", "10011", "10001"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
}


def _layers():
    front = ["   ".join("".join("##" if bit == "1" else "  "
                               for bit in _GLYPHS[letter][row])
                        for letter in "SYNAPSE") for row in range(7)]
    columns = len(front[0]) + 3
    sides = [[" "] * columns for _ in range(9)]
    for y, row in enumerate(front):
        for x, char in enumerate(row):
            if char == "#":
                for dx, dy, ink in ((1, 1, "/"), (2, 1, "/"), (3, 2, ":")):
                    sides[y + dy][x + dx] = ink
    return tuple(front), tuple("".join(row) for row in sides)


_FRONT, _SIDES = _layers()


class AsciiWordmark(QtWidgets.QWidget):
    """Decorative letters made of ASCII glyphs, with a plain accessible name.

    Only the artwork scales to fit. The surrounding UI text retains the host
    font size, and no timers, network requests, scene nodes or GPU are needed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsAsciiWordmark")
        self.setAccessibleName("SYNAPSE")
        self.setAccessibleDescription("SYNAPSE in dimensional ASCII lettering")
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self._ink_font = fontload.apply_family(QtGui.QFont(), mono=True)
        # Add three typographic points to the previous 16-pixel ASCII face.
        base_points = 16 * 72.0 / self.logicalDpiY()
        self._ink_font.setPointSizeF(base_points + 3.0)
        self.size_multiplier = (base_points + 3.0) / base_points
        self._ink_font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, 0)
        self._front_font = QtGui.QFont(self._ink_font)
        self._front_font.setBold(True)
        metrics = QtGui.QFontMetricsF(self._ink_font, self)
        self._cell = metrics.horizontalAdvance("#")
        self._glyph_box = metrics.tightBoundingRect("#/: ")
        self._line = self._glyph_box.height() + 2
        self._natural = QtCore.QSizeF(len(_SIDES[0]) * self._cell,
                                     8 * self._line + self._glyph_box.height())

    def heightForWidth(self, width):
        return max(1, round(width * self._natural.height() / self._natural.width()))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        factor = min(max(0, self.width() - 2) / self._natural.width(),
                     max(0, self.height() - 2) / self._natural.height())
        painter.translate((self.width() - self._natural.width() * factor) / 2,
                          (self.height() - self._natural.height() * factor) / 2)
        painter.scale(factor, factor)
        for rows, color, font in ((_SIDES, QtGui.QColor(t.WARM_PRESS).darker(180), self._ink_font),
                                  (_FRONT, QtGui.QColor(t.CHAT_ASSISTANT), self._front_font)):
            painter.setFont(font)
            painter.setPen(color)
            for row, text in enumerate(rows):
                painter.drawText(QtCore.QPointF(0, -self._glyph_box.top() + row * self._line), text)
        painter.end()
