"""Mile 2 — three faces + state→face controller. Behavioral pins.

Adversarial G1 check: instantiation isn't enough — the gate is "switches
manually + auto on simulated state changes." These exercise the controller
directly (no live worker, no Houdini) so the contract can't silently regress.

Run offscreen via Houdini's Python (stock CPython lacks PySide):
    hython tests/test_panel_faces.py        # exits 0 / 1
Also collectable by pytest where PySide imports.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
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


def _idx(panel):
    return panel._faces.currentIndex()


def test_initial_face_is_direct():
    p = _make_panel()
    assert p._current_face == "direct"
    assert _idx(p) == 0


def test_manual_pill_switches_and_holds():
    p = _make_panel()
    p._set_face("review", manual=True)
    assert _idx(p) == 2 and p._current_face == "review"
    assert p._manual_face == "review"
    # auto request is deferred while a manual pick holds
    p._request_face("work")
    assert _idx(p) == 2, "manual park must not be overridden by an auto request"
    assert p._pending_face == "work"


def test_busy_rising_edge_clears_manual_and_shows_work():
    p = _make_panel()
    p._set_face("review", manual=True)
    p._set_busy(True)
    assert p._manual_face is None, "a new work cycle clears the manual park"
    assert _idx(p) == 1 and p._current_face == "work"


def test_busy_falling_edge_shows_review():
    p = _make_panel()
    p._set_busy(True)
    p._set_busy(False)
    assert _idx(p) == 2 and p._current_face == "review"


def test_tool_running_shows_work():
    p = _make_panel()
    p._set_face("direct")
    p._on_tool_status("houdini_render", "running", "")
    assert _idx(p) == 1 and p._current_face == "work"


def test_focus_guard_defers_then_applies_on_focus_out():
    p = _make_panel()
    p._set_face("direct")
    orig = p._input_focused
    p._input_focused = lambda: True          # artist is typing
    try:
        p._request_face("work")
        assert _idx(p) == 0, "must never yank away from Direct while typing"
        assert p._pending_face == "work"
    finally:
        p._input_focused = orig
    p._apply_pending_face()                  # input lost focus
    assert _idx(p) == 1 and p._current_face == "work"


def test_gate_raised_shows_review_and_supersedes_manual():
    p = _make_panel()
    p._set_face("direct", manual=True)
    p._on_gate_raised({"level": "approve"})
    assert _idx(p) == 2 and p._current_face == "review"


def test_inform_gate_is_ignored():
    p = _make_panel()
    p._set_face("direct")
    p._on_gate_raised({"level": "inform"})
    assert _idx(p) == 0, "noisy INFORM proposals must not steal the face"


def test_scripted_conversation_renders():
    # Mile 3 — a scripted Direct conversation must render through ChatDisplay
    # without choking on the new HTML (table-based human rule, artifact chips),
    # and node refs must keep their clickable node: anchor.
    p = _make_panel()
    chat = p._chat
    chat.append_user_message("swap crystal_import to Dark_Glass and re-render")
    chat.append_synapse_message(
        "On it — rebinding at /materials/AMD/Dark_Glass, then a draft cook."
    )
    chat.append_system_message("Added to context: /obj/geo1")
    plain = chat.toPlainText()
    assert "Dark_Glass" in plain and "crystal_import" in plain
    html_ = chat.toHtml()
    assert "node:/materials/AMD/Dark_Glass" in html_, "node ref must stay a chip anchor"


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("  ok   %s" % fn.__name__)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print("  FAIL %s — %s" % (fn.__name__, exc))
    print("%d/%d passed" % (len(fns) - failed, len(fns)))
    return 1 if failed else 0


if __name__ == "__main__":
    if not _HAVE_QT:
        print("PySide unavailable — run via hython.")
        sys.exit(1)
    sys.exit(_run_all())
