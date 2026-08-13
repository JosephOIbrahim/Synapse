"""W2-S5 — the 2s context tick reads Houdini OFF the Qt/main thread.

Before: ``SynapsePanel._update_context`` (the 2s ``_ctx_timer`` tick) called
``hou.frame()`` / ``hou.selectedNodes()`` / ``hou.hipFile.basename()`` INLINE on
the Qt/main thread, unmarshalled — the W1-MTFIX crash-path class. ``run_on_main``'s
Fast path 2 (caller IS main → ``fn()`` inline, no timeout) meant every read froze
the GUI for its duration while ``ws_bridge.gather_context_off_main`` — built to do
exactly this read off-main — sat unused.

After: ``_update_context`` delegates the three reads to
``ws_bridge.gather_context_off_main`` (daemon thread → ``run_on_main`` DEFERRED
path) and the result marshals back to the Qt thread through the panel's
``_context_ready`` queued signal, where ``_apply_context`` renders the ribbon +
health strip. ``import hou`` remains only as the availability guard (no data read).

These pin the mission's four acceptance predicates:

  1. the tick performs ZERO direct ``hou.*`` reads on the Qt/main path
     (hook the tick with a recording ``hou`` + a gather spy),
  2. ``gather_context_off_main`` is the producer and the result is marshalled
     back BEFORE any Qt use (emit from a non-main thread does not touch the
     widget until the main-thread event loop spins),
  3. the rendered payload is BYTE-EQUAL to the former inline computation for
     fixed fixture scene states (the derivations — ``scene_file`` basename and
     the first selection's parent path — were confirmed equal to
     ``hipFile.basename()`` / ``node.parent().path()`` on live H22.0.400),
  4. is the slice-run itself (see the receipt); this file is part of that slice.

Panel widgets need real PySide, so this is an hython-offscreen suite (it SKIPS
under stock CPython, exactly like ``tests/test_panel_faces.py``):

    QT_QPA_PLATFORM=offscreen hython -m pytest tests/test_w2_s5_context_offmain.py
"""

import os
import sys
import threading
from unittest.mock import MagicMock, patch

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# --- tiny hou stub so the panel constructs headless when hou is absent ---
class _Hou:
    class _HipFile:
        def basename(self):
            return "untitled.hip"

        def path(self):
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

# Real Qt only — a leaked MagicMock/types-stub QApplication from a sibling panel
# test can't build a widget. Verify QtWidgets.QApplication is a genuine PySide
# *type*; any stub fails that and we skip (this suite is hython-only). Mirrors
# the guard in tests/test_panel_faces.py.
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
    """Construct a panel offscreen, then stop its background timers so the
    deterministic assertions below are never perturbed by a stray tick."""
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from synapse.panel.synapse_panel import SynapsePanel
    p = SynapsePanel()
    for _name in ("_ctx_timer", "_health_timer", "_freeze_timer"):
        _t = getattr(p, _name, None)
        if _t is not None:
            try:
                _t.stop()
            except Exception:
                pass
    return p


# ---------------------------------------------------------------------------
# Predicate 1 — zero direct hou.* reads on the Qt/main path
# ---------------------------------------------------------------------------
def test_tick_makes_no_direct_hou_reads_on_main():
    p = _make_panel()
    rec_hou = MagicMock(name="hou")            # records every attribute CALL
    with patch.dict(sys.modules, {"hou": rec_hou}), \
            patch("synapse.panel.ws_bridge.gather_context_off_main") as gather:
        p._update_context()
    # The tick delegated the reads to the off-main producer...
    gather.assert_called_once()
    # ...and made NO hou data read on the calling (Qt/main) thread. `import hou`
    # is an availability guard only — it never touches these attributes here.
    assert rec_hou.frame.call_count == 0, "hou.frame() must not run on the tick's main path"
    assert rec_hou.selectedNodes.call_count == 0, "hou.selectedNodes() must not run on main"
    assert rec_hou.hipFile.basename.call_count == 0, "hou.hipFile.basename() must not run on main"
    assert rec_hou.hipFile.path.call_count == 0, "hou.hipFile.path() must not run on main"


# ---------------------------------------------------------------------------
# Predicate 2 — gather is the producer; result marshalled back before any Qt use
# ---------------------------------------------------------------------------
def test_gather_is_producer_and_result_marshalled_to_main():
    p = _make_panel()
    holder = {}

    def fake_gather(on_ready, timeout=None):
        holder["cb"] = on_ready

    with patch("synapse.panel.ws_bridge.gather_context_off_main", fake_gather):
        p._update_context()
    assert "cb" in holder, "the tick must hand a callback to gather_context_off_main"

    # Emit the marshal-back from a NON-main thread (as the daemon gather does).
    # AutoConnection across threads is queued: the slot must NOT run on the
    # producer thread, so the widget stays untouched until the event loop spins.
    p._ctx_label.setText("SENTINEL-W2S5")
    fixture = {"selected_nodes": [], "current_network": "",
               "scene_file": "/proj/shot.hip", "frame": 7.0}
    done = threading.Event()

    def worker():
        holder["cb"](fixture)      # panel._context_ready.emit(ctx), off-main
        done.set()

    th = threading.Thread(target=worker)
    th.start()
    assert done.wait(2.0), "the off-main emit never completed"
    th.join(2.0)
    # Queued, not yet delivered: the producer thread did not touch the widget.
    assert p._ctx_label.text() == "SENTINEL-W2S5", (
        "marshal-back touched the Qt widget off the main thread — the emit ran "
        "the slot inline instead of queuing it"
    )
    # Spin the main-thread event loop → the queued slot renders the ribbon.
    QtWidgets.QApplication.processEvents()
    assert p._ctx_label.text() == "shot.hip · f7", (
        "after the main-thread loop spins, _apply_context renders the ribbon"
    )


# ---------------------------------------------------------------------------
# Predicate 3 — payload byte-equal to the former inline computation
# ---------------------------------------------------------------------------
# Each case: (off-main ctx, expected ribbon text, expected health-strip project).
# The ctx shape is exactly what ws_bridge._gather_context_on_main_thread yields
# (selected_nodes = node paths, scene_file = FULL path, frame = float). The
# expected strings reproduce the pre-W2-S5 inline render byte-for-byte; the
# derivations reproducing hipFile.basename() and sel[0].parent().path() were
# confirmed on live H22.0.400 (W2-S5 probe — see the receipt).
_BYTE_EQUAL_CASES = [
    ({"selected_nodes": ["/obj/geo1", "/obj/geo2"], "current_network": "/obj",
      "scene_file": "/proj/shots/shot_010.hip", "frame": 24.0},
     "/obj · 2 selected · f24", "shot_010.hip"),
    ({"selected_nodes": ["/obj/geo1/pointgen/scatter"], "current_network": "/obj/geo1",
      "scene_file": "/p/fx.hip", "frame": 1001.0},
     "/obj/geo1/pointgen · 1 selected · f1001", "fx.hip"),
    ({"selected_nodes": ["/obj"], "current_network": "/",
      "scene_file": "/p/top.hip", "frame": 3.0},
     "/ · 1 selected · f3", "top.hip"),          # top-level node → parent "/" boundary
    ({"selected_nodes": [], "current_network": "/obj",
      "scene_file": "/p/lookdev.hip", "frame": 48.0},
     "lookdev.hip · f48", "lookdev.hip"),
    ({"selected_nodes": [], "current_network": "/stage",
      "scene_file": "C:/Users/User/untitled.hip", "frame": 1.0},
     "untitled.hip · f1", None),                 # untitled → project stays None
]


def test_context_payload_byte_equal_to_baseline():
    p = _make_panel()
    seen = []
    # Capture what the health strip is fed without touching the real widget.
    p._update_health_strip = lambda conn, proj: seen.append((conn, proj))
    for ctx, want_label, want_proj in _BYTE_EQUAL_CASES:
        seen.clear()
        p._apply_context(ctx)
        assert p._ctx_label.text() == want_label, (
            "ribbon drifted from baseline for %r: got %r" % (ctx, p._ctx_label.text()))
        assert seen and seen[-1][1] == want_proj, (
            "project derivation drifted from baseline for %r: got %r" % (ctx, seen))


# hython entrypoint (mirrors the sibling panel suites): exit 0 on pass.
if __name__ == "__main__":
    if not _HAVE_QT:
        print("SKIP: PySide unavailable — run via hython")
        raise SystemExit(0)
    test_tick_makes_no_direct_hou_reads_on_main()
    test_gather_is_producer_and_result_marshalled_to_main()
    test_context_payload_byte_equal_to_baseline()
    print("W2-S5 offmain context: OK")
    raise SystemExit(0)
