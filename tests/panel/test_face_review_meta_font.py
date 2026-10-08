"""DES-D06: the Review hero's metadata overlay is on the type system.

``RenderHero._paint_meta`` painted the frame metadata at ``setPixelSize(10)`` in
a generic ``"monospace"`` family: one pixel under ``FONT_FLOOR_PX`` (11) and off
the bundled mono (offscreen hython resolved it to Courier). It now paints on the
``status`` role (mono, ``SIZE_SMALL``, DATA tracking) via the bundled Space Mono.

Two pins:
  * a stock-CPython source pin, so every CI leg sees the regression;
  * a hython pin that paints a real frame and reads the QFont the painter held
    while drawing the metadata, which is what the artist actually sees.

Run the Qt half offscreen via Houdini's Python:
    hython -m pytest tests/panel/test_face_review_meta_font.py
"""

import ast
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_FACE_REVIEW = _ROOT / "python" / "synapse" / "panel" / "face_review.py"

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtGui, QtWidgets
    _HAVE_QT = True
except ImportError:
    _HAVE_QT = False

# Real Qt only: sibling tests leave MagicMock / ModuleType stubs in sys.modules.
if _HAVE_QT:
    try:
        _qapp = getattr(QtWidgets, "QApplication", None)
        if not (isinstance(_qapp, type) and "PySide" in getattr(_qapp, "__module__", "")):
            _HAVE_QT = False
    except Exception:
        _HAVE_QT = False

_needs_qt = pytest.mark.skipif(not _HAVE_QT, reason="PySide unavailable - run via hython")


def _render_hero_methods():
    tree = ast.parse(_FACE_REVIEW.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "RenderHero":
            return {f.name: ast.unparse(f) for f in node.body
                    if isinstance(f, ast.FunctionDef)}
    raise AssertionError("RenderHero not found in face_review.py")


def test_meta_overlay_source_is_on_the_status_token():
    methods = _render_hero_methods()
    painted = methods.get("_paint_meta", "") + "\n" + methods.get("_meta_font", "")
    assert "setPixelSize(10)" not in painted, "meta overlay paints under FONT_FLOOR_PX"
    assert "'monospace'" not in painted and '"monospace"' not in painted, \
        "meta overlay names a generic family instead of the bundled mono"
    assert "tracked_font('DATA', t.SIZE_SMALL, mono=True)" in painted, \
        "meta overlay must use the status role: DATA tracking, SIZE_SMALL, bundled mono"


@_needs_qt
def test_painted_meta_font_clears_floor_and_uses_bundled_mono(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app is not None
    from synapse.panel.designsystem import fontload, tokens as t
    status = fontload.load_application_fonts() or {}
    from synapse.panel import face_review

    frame = QtGui.QImage(320, 180, QtGui.QImage.Format.Format_RGB32)
    frame.fill(QtGui.QColor("#303236"))
    frame_path = str(tmp_path / "frame.png")
    assert frame.save(frame_path)

    hero = face_review.RenderHero()
    hero.resize(320, 180)
    assert hero.set_image(frame_path)
    hero.set_meta("karma xpu  1920x1080  f1001")

    seen = []
    orig = hero._paint_meta

    def _spy(painter, rect):
        orig(painter, rect)
        seen.append(QtGui.QFont(painter.font()))

    hero._paint_meta = _spy
    hero.grab()
    assert seen, "metadata overlay was never painted"
    font = seen[-1]

    _family_css, role_px, _weight, _tracking = t.TYPE_ROLES["status"]
    assert font.pixelSize() >= t.FONT_FLOOR_PX
    assert font.pixelSize() == role_px
    if status.get("ok") and not status.get("build_mismatch"):
        assert QtGui.QFontInfo(font).family() == t.FONT_MONO
    else:
        assert status.get("build_mismatch"), "unregistered bundle must be flagged"
    assert QtGui.QFontInfo(font).fixedPitch()
