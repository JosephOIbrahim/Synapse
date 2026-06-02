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


def test_work_face_present():
    # Mile 4 — the Work face is the real FaceWork, not a placeholder.
    p = _make_panel()
    assert p._work_face is not None
    assert hasattr(p._work_face, "_cook")


def test_work_face_pulses_while_thinking():
    # The cook preview runs its indeterminate sweep while the agent thinks,
    # and stops at rest — "the walk-away glance" reads alive.
    p = _make_panel()
    p._set_thinking(True)
    assert p._work_face._cook._timer.isActive()
    p._set_thinking(False)
    assert not p._work_face._cook._timer.isActive()


def test_tool_status_feeds_plan():
    # Live tool events drive the plan-with-progress; a phase change updates the
    # step in place (no duplicate), and normalizes done→ok.
    p = _make_panel()
    p._on_tool_status("houdini_render", "running", "")
    assert "houdini_render" in [s[0] for s in p._work_face._steps]
    p._on_tool_status("houdini_render", "done", "")
    steps = p._work_face._steps
    assert [s[0] for s in steps].count("houdini_render") == 1
    assert steps[-1][1] == "ok"


def test_cook_progress_is_determinate():
    # Real cook counts switch the grid out of pulse into determinate progress.
    p = _make_panel()
    p._work_face.set_cook(14, 30)
    assert p._work_face._cook._determinate
    assert not p._work_face._cook._timer.isActive()
    assert "14 / 30" in p._work_face._cook_lbl.text()


def test_review_face_present_with_gate():
    # Mile 5 — the Review face is the real FaceReview, and self._gate aliases
    # the embedded gate so the consent wiring stays intact.
    p = _make_panel()
    assert p._review_face is not None
    assert p._gate is p._review_face.gate


def test_review_show_result_populates_all_parts():
    # Simulated 'done' → render + verdict + credit + flags + paths all render.
    p = _make_panel()
    rf = p._review_face
    rf.show_result(
        verdict="The crystal reads at the scene's IOR now — Dark_Glass landed.",
        credit=[("DECISION", "Dark_Glass", "over Diamond, closer to scene IOR"),
                ("VIA", "materiallinker → link_type_1", "")],
        flags=[("ok", "render ok"), ("fail", "EXR not written — BL-007")],
        paths=["/materials/AMD/link_type_1", "/Render/Products/render_settings"],
        meta="karma_xpu · f1 · 1920×1080",
    )
    assert "Dark_Glass" in rf._verdict.text()
    assert rf._credit_box.count() == 2
    assert rf._flags_box.count() == 2
    # offscreen: the window is never shown, so check explicit visibility state
    assert not rf._paths.isHidden()
    assert "link_type_1" in rf._paths.text()


def test_bl007_flag_detects_missing_output():
    # BL-007: no file on disk → the silent-no-output failure is flagged red.
    from synapse.panel.face_review import bl007_flag
    status, text = bl007_flag("")
    assert status == "fail" and "BL-007" in text


def test_review_actions_wired_to_panel():
    # accept/commit signals reach the panel handlers without error; commit
    # keeps the Review face forward (it routes through the gate, not /stage).
    p = _make_panel()
    p._review_face.accepted.emit()
    p._review_face.committed.emit()
    assert _idx(p) == 2


def test_done_edge_populates_review_verdict():
    # The done edge switches to Review and lifts the first line as the verdict.
    p = _make_panel()
    p._stream_buf = ["Dark_Glass landed; the crystal reads at the scene IOR now."]
    p._was_busy = True
    p._set_busy(False)
    assert _idx(p) == 2
    assert "Dark_Glass" in p._review_face._verdict.text()


def test_classify_tool_two_axes():
    # Mile 6 — the verb × context taxonomy classifies tools sensibly.
    from synapse.panel.tool_filter import classify_tool
    assert classify_tool("houdini_render")[0] == "render"
    assert classify_tool("houdini_create_usd_prim") == ("build", "USD")
    assert classify_tool("cops_pixel_sort")[1] == "COP"
    assert classify_tool("synapse_inspect_scene")[0] == "explain"
    assert classify_tool("tops_diagnose")[0] == "fix"


def test_tool_palette_two_axis_filter():
    # The ⌘K palette opens with both axes navigable; each filters the rows.
    from synapse.panel.tool_palette import ToolPalette
    _make_panel()                       # ensure a QApplication exists
    pal = ToolPalette()
    assert None in pal._verb_chips and "render" in pal._verb_chips and len(pal._verb_chips) == 6
    assert None in pal._ctx_chips and "COP" in pal._ctx_chips and len(pal._ctx_chips) == 6
    base = len(pal._visible())
    pal._set_axis("verb", "render")
    assert pal._verb == "render"
    assert all(e["verb"] == "render" for e in pal._visible())
    assert len(pal._visible()) <= base
    pal._set_axis("context", "Karma")   # combine both axes
    assert all(e["verb"] == "render" and e["context"] == "Karma" for e in pal._visible())
    pal._set_axis("verb", "render")     # toggling the same chip clears it
    assert pal._verb is None


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
