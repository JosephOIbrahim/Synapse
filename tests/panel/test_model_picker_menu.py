"""Goalpost — the '...' Engine menu must list MORE THAN ONE Claude model.

Contract: model-picker (order 2). Encodes the goal:

    "via the '...' overflow Engine menu rendered as a per-provider submenu" —
    Claude: sonnet / opus / haiku.

Today ``_show_overflow`` (synapse_panel.py ~814-824) builds an "Engine" submenu
with ONE flat action per PROVIDER (Claude, Gemini) — there is no per-model
choice. This goalpost asserts the Claude branch of that Engine menu offers more
than one model entry, which is exactly what the per-provider submenu delivers.

RUNTIME ENVIRONMENT — read before trusting a green:
    Building the menu needs a live QWidget (the panel + a real QMenu), so this
    needs PySide. ``synapse_panel.py`` hard-imports PySide6/PySide2 at module
    top, so under stock CPython (no PySide) this module SKIPS — matching
    tests/test_panel_faces.py (panel widgets are verified via hython offscreen).
    A SKIP exits 0, which the harness reads as PASSING; the contract therefore
    routes this verify through .synapse/hytest.py so it runs under hython for a
    real pass/fail.
"""

import os
import sys

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

# Real Qt only — reject leaked PySide stubs (see tests/test_panel_faces.py).
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


def _make_panel():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from synapse.panel.synapse_panel import SynapsePanel
    return SynapsePanel()


def _capture_overflow_menu(panel):
    """Invoke the panel's ``_show_overflow`` with QMenu.exec / exec_ stubbed to
    a no-op that records the menu instance, so we can inspect the built menu
    without blocking on a modal popup. Returns the captured QMenu (or None)."""
    captured = []

    def _record(self, *_a, **_k):
        captured.append(self)
        return None

    QMenu = QtWidgets.QMenu
    saved = {}
    for name in ("exec", "exec_"):
        if hasattr(QMenu, name):
            saved[name] = getattr(QMenu, name)
            setattr(QMenu, name, _record)
    try:
        panel._show_overflow()
    finally:
        for name, fn in saved.items():
            setattr(QMenu, name, fn)
    return captured[0] if captured else None


def _find_submenu(menu, title_substr):
    """Find the first submenu of ``menu`` whose title contains ``title_substr``
    (case-insensitive). Returns the submenu's QMenu, or None."""
    want = title_substr.lower()
    for act in menu.actions():
        sub = act.menu()
        if sub is not None and want in (act.text() or "").lower():
            return sub
    return None


def _model_action_texts(menu):
    """Visible texts of leaf (non-submenu) actions on ``menu``, separators
    dropped. These are the per-entry menu items."""
    out = []
    for act in menu.actions():
        if act.isSeparator():
            continue
        if act.menu() is not None:
            continue
        txt = (act.text() or "").strip()
        if txt:
            out.append(txt)
    return out


def test_engine_menu_lists_claude_models():
    # The '...' Engine menu must offer MORE THAN ONE Claude model. Today the
    # Engine menu has one flat action PER PROVIDER (Claude, Gemini) and no
    # per-model entries, so the Claude branch lists exactly one item -> FAILS.
    # With the per-provider submenu, the Claude branch lists >1 model -> PASSES.
    panel = _make_panel()

    overflow = _capture_overflow_menu(panel)
    assert overflow is not None, (
        "_show_overflow did not build an inspectable QMenu (exec/exec_ stub "
        "captured nothing)"
    )

    engine = _find_submenu(overflow, "engine")
    assert engine is not None, (
        "the '...' overflow menu must contain an 'Engine' submenu; found "
        "actions %r" % ([a.text() for a in overflow.actions()],)
    )

    # The Claude models live either directly on the Engine submenu or, in the
    # per-provider design, under a nested 'Claude' submenu. Collect whichever
    # holds the model entries.
    claude_sub = _find_submenu(engine, "claude")
    if claude_sub is not None:
        entries = _model_action_texts(claude_sub)
    else:
        # Flat layout: Claude model rows live directly on the Engine submenu.
        # Keep only entries that name a Claude model family.
        entries = [
            t for t in _model_action_texts(engine)
            if any(fam in t.lower() for fam in ("sonnet", "opus", "haiku"))
        ]

    assert len(entries) > 1, (
        "the Engine menu's Claude branch must list more than one model "
        "(sonnet / opus / haiku); found %d entr%s: %r — still one action per "
        "provider, no per-model picker"
        % (len(entries), "y" if len(entries) == 1 else "ies", entries)
    )
