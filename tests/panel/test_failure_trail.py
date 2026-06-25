"""Goalpost — a swallowed failure on a guarded runtime path must leave a
logger.debug trail; the dead 'open in render view' verb must be hidden when the
render bridge is absent.

Contract: failure-trail (C3). Encodes Codebase §1.4 ("bare `except: pass` …
converts failures into silent no-ops … should at minimum logger.debug with the
exception") and Design §2.5 ("a clean no-op that does nothing visible … a dead
affordance reads as broken. … Don't ship a visible control that no-ops").

RUNTIME ENVIRONMENT — read before trusting a green:
    These exercise REAL panel widgets. `synapse_panel.py` and `face_review.py`
    hard-import PySide6/PySide2 at module top (no third fallback), so they can
    only be imported where PySide exists. Under stock CPython (no PySide) this
    module SKIPS — matching the established tests/test_panel_faces.py convention
    (panel widgets are verified via hython offscreen). A SKIP exits 0, which the
    harness reads as PASSING; run these via hython for a real signal. See
    GOALPOST_TESTS_REPORT.md §(d).
"""

import logging
import os
import sys
import types as _types

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# --- tiny hou stub so the panel's best-effort context reads don't explode ---
class _Hou:
    class _HipFile:
        def basename(self):
            return "untitled.hip"

    hipFile = _HipFile()

    @staticmethod
    def frame():
        return 1

    @staticmethod
    def selectedNodes():
        return []


sys.modules.setdefault("hou", _Hou)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtWidgets  # noqa: F401
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets  # noqa: F401
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False

# Real Qt only. Sibling tests evict real PySide and leave stubs in sys.modules
# (test_chat_panel: a MagicMock; test_hda_panel: a types.ModuleType with
# QApplication=MagicMock) — neither can build a panel. Verify
# QtWidgets.QApplication is a genuine PySide *type*; any stub fails that, so we
# skip (this suite is hython-only). Mirrors tests/test_panel_faces.py exactly.
if _HAVE_QT:
    try:
        _qapp = getattr(QtWidgets, "QApplication", None)
        if not (isinstance(_qapp, type) and "PySide" in getattr(_qapp, "__module__", "")):
            _HAVE_QT = False
    except Exception:
        _HAVE_QT = False

try:
    import pytest
    if not _HAVE_QT:
        pytestmark = pytest.mark.skip(reason="PySide unavailable — run via hython")
except Exception:
    pytest = None


_APP = None


def _ensure_app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def test_runtime_paths_log(caplog):
    # Codebase §1.4 — force a guarded runtime path to fail and assert it leaves a
    # logger.debug trail. `_wire_gate` (synapse_panel.py:783-794) is the review's
    # named example: it swallows a gate-wiring failure with a bare `except: pass`.
    # Called unbound with a fake `self` so no QWidget is built — the failure path
    # is the whole point, not the panel. FAILS today (silent); PASSES once the
    # bare except logs the exception.
    from synapse.panel.synapse_panel import SynapsePanel

    class _BoomSignal:
        def connect(self, *_a, **_k):
            raise RuntimeError("boom-wiring")

    fake = _types.SimpleNamespace(
        _gate=_types.SimpleNamespace(_proposal_received=_BoomSignal()),
        _on_gate_raised=lambda *a, **k: None,
    )

    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        # Must NOT raise — the path is guarded. The contract is that it no longer
        # swallows SILENTLY.
        SynapsePanel._wire_gate(fake)

    trailed = any(
        rec.levelno == logging.DEBUG
        and ("boom-wiring" in rec.getMessage() or rec.exc_info is not None)
        for rec in caplog.records
    )
    assert trailed, (
        "a swallowed failure on a guarded runtime path (_wire_gate) left no "
        "logger.debug trail — the bare `except: pass` is still silent "
        "(Codebase §1.4). A field failure must leave a trail."
    )


def test_dead_verb_hidden():
    # Design §2.5 — the '⤢ open in render view' verb (face_review.py:212) is a
    # clean no-op when the render bridge is absent; a visible control that
    # no-ops reads as broken. With no live bridge it must be hidden (or not
    # created). Shown today (the locator + verb are visible at rest) -> FAILS;
    # PASSES once the verb is gated on render-bridge availability.
    _ensure_app()
    from synapse.panel.face_review import FaceReview

    face = FaceReview()
    # show() offscreen so isVisible() is meaningful: a never-shown top-level
    # widget reports isHidden()==True for ITSELF, which would make every child
    # look hidden and pass this test trivially. Showing it realizes the real
    # visibility state (respecting any setVisible(False) on the verb/container).
    face.show()
    try:
        verbs = [
            b for b in face.findChildren(QtWidgets.QPushButton)
            if "render view" in (b.text() or "").lower()
        ]
        shown = [b for b in verbs if b.isVisible()]
        assert not shown, (
            "the 'open in render view' verb is present and shown while the "
            "render bridge is absent — a visible no-op (Design §2.5). Hide it "
            "(or omit it) until the confirmed hou.ui render-view chain is wired."
        )
    finally:
        face.hide()
