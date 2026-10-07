"""Hour2 design T2c (2026-10-06): the wordmark's weight names the token it
means. ``weight=600`` became ``weight=t.WEIGHT_BOLD`` (700) on the brand
path; ``tracked_font`` maps any weight >= 600 to ``setBold``, so the QFont the
wordmark receives is identical. The 15px size literal stays (F9, Joe's
2026-09-05 addendum; pinned in test_type_scale_native.py).

The source check is stdlib and always runs. The QFont check needs a REAL Qt:
a MagicMock PySide6 installed by another test would let importorskip pass
while asserting nothing, so it is refused explicitly (gate-width trap).
"""
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_PANEL = os.path.join(_ROOT, "python", "synapse", "panel", "synapse_panel.py")
_CALL = re.compile(
    r'tracked_font\("WORDMARK",\s*15,\s*scale=self\._chrome_scale,\s*weight=([^)]+)\)')


def test_wordmark_call_names_weight_bold_not_a_literal():
    src = open(_PANEL, encoding="utf-8").read()
    calls = _CALL.findall(src)
    assert calls == ["t.WEIGHT_BOLD"], calls
    assert "weight=600" not in src


def _real_qt():
    qtgui = pytest.importorskip("PySide6.QtGui")
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    if not isinstance(qtgui.QFont, type) or type(qtgui).__name__ != "module":
        pytest.skip("PySide6 is a stub in this process, not a real Qt")
    return qtgui, qtwidgets


@pytest.mark.parametrize("scale", (1.0, 2.25))
def test_wordmark_qfont_is_identical_under_the_token(scale):
    qtgui, qtwidgets = _real_qt()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None
    from synapse.panel.designsystem import fontload
    from synapse.panel.designsystem import tokens as t

    via_token = fontload.tracked_font("WORDMARK", 15, scale=scale,
                                      weight=t.WEIGHT_BOLD)
    via_literal = fontload.tracked_font("WORDMARK", 15, scale=scale, weight=600)
    assert isinstance(via_token, qtgui.QFont)
    assert via_token == via_literal
    assert via_token.key() == via_literal.key()
    assert via_token.bold()
    assert via_token.pixelSize() == t.scaled(15, scale)
