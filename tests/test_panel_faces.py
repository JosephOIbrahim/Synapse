"""Panel tabs + Work cook/done sub-state — behavioral pins (v9 re-layout).

Adversarial G1 check: instantiation isn't enough — the gate is "tabs switch
ONLY on a user pill click; agent state drives the Work face's cook/done
sub-state + the rail mark, never the visible tab (the same-pane law)." These
exercise the controller directly (no live worker, no Houdini) so the contract
can't silently regress.

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

# Real Qt only. Sibling tests evict real PySide and leave stubs in sys.modules
# (test_chat_panel: a MagicMock; test_hda_panel: a types.ModuleType subclass with
# QApplication=MagicMock) — neither can build a panel. Verify QtWidgets.QApplication
# is a genuine PySide *type*; any stub fails that, so we skip (this suite is
# hython-only). Without this, a leaked stub flips _HAVE_QT True and every test
# fails on fake widgets (passes alone, fails under the full stock-CI suite).
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


def _idx(panel):
    return panel._faces.currentIndex()


def test_initial_face_is_direct():
    p = _make_panel()
    assert p._current_face == "direct"
    assert _idx(p) == 0


def test_manual_pill_switches():
    # v9: a pill click is the ONLY thing that moves the visible tab. It switches
    # and stays — agent state never overrides it (the same-pane law).
    p = _make_panel()
    p._set_face("work")
    assert _idx(p) == 1 and p._current_face == "work"
    p._set_face("direct")
    assert _idx(p) == 0 and p._current_face == "direct"


def test_busy_sets_cook_substate_no_tab_switch():
    # A new work cycle shows the Work face's COOK sub-state and lifts the rail
    # mark — but it must NOT switch the visible tab (the same-pane law).
    p = _make_panel()
    p._set_face("direct")
    p._set_busy(True)
    assert _idx(p) == 0, "busy must not auto-switch the tab"
    assert p._work_substate == "cook"
    assert p._work_stack.currentIndex() == 0
    assert p._mark._state == "working"


def test_busy_falling_sets_done_substate_no_switch():
    # Work finishing fills the done sub-state (the payoff) and marks done —
    # still no tab switch; the rail mark is the signal.
    p = _make_panel()
    p._set_face("direct")
    p._set_busy(True)
    p._set_busy(False)
    assert _idx(p) == 0, "finishing must not auto-switch the tab"
    assert p._work_substate == "done"
    assert p._work_stack.currentIndex() == 1
    assert p._mark._state == "done"


def test_tool_running_does_not_switch_tab():
    # A live tool feeds the Work plan + rail mark but never steals the tab.
    p = _make_panel()
    p._set_face("direct")
    p._on_tool_status("houdini_render", "running", "")
    assert _idx(p) == 0, "a running tool must not auto-switch the tab"
    assert "houdini_render" in [s[0] for s in p._work_face._steps]


def test_state_persists_across_tab_switch():
    # The same-pane law: switching tabs is a QStackedWidget index change, so each
    # face keeps its state. Drive Work to the done sub-state, visit Direct,
    # return — the sub-state and its content survive.
    p = _make_panel()
    p._set_busy(True)
    p._set_busy(False)                       # Work → done sub-state
    assert p._work_substate == "done"
    p._set_face("direct")
    assert _idx(p) == 0
    p._set_face("work")
    assert _idx(p) == 1
    assert p._work_substate == "done", "Work sub-state must persist across a tab switch"
    assert p._work_stack.currentIndex() == 1


def test_gate_raised_sets_done_substate_no_switch():
    # A real gate proposal surfaces in Work's done sub-state and marks a ready
    # result — but never auto-switches the visible tab (the same-pane law).
    p = _make_panel()
    p._set_face("direct")
    p._on_gate_raised({"level": "approve"})
    assert _idx(p) == 0, "a gate must not auto-switch the tab"
    assert p._work_substate == "done"
    assert p._mark._state == "done"


def test_inform_gate_is_ignored():
    p = _make_panel()
    p._set_face("direct")
    p._on_gate_raised({"level": "inform"})
    assert _idx(p) == 0, "noisy INFORM proposals must not steal the tab"
    assert p._work_substate == "cook", "INFORM must not flip the Work sub-state"


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


def test_direct_input_is_roomy_multiline():
    # v9 — the Direct composer defaults to the comp's roomy 132px (Preferred
    # policy: it may compress toward the 64px floor only when the pane is
    # short, so the embedded Send never crops). Needs an activated layout.
    p = _make_panel()
    p.resize(500, 700)
    p.show()                                   # offscreen: activates layout
    QtWidgets.QApplication.processEvents()
    try:
        assert p._input.height() >= 120, "the prompt must be roomy multi-line"
        assert p._send_btn is not None
        # Send is embedded INSIDE the composer (comp), never a separate row
        assert p._send_btn.parent() is p._input
    finally:
        p.hide()


def test_synapse_reply_carries_signed_author():
    # Spike 4 — a SYNAPSE result in the Direct conversation carries a
    # display-only signed-author note (once per group) via ChatDisplay.
    p = _make_panel()
    p._chat.append_synapse_message(
        "Rebound the material and cooked a draft.", signed="sonnet-4.6")
    assert "sonnet-4.6" in p._chat.toHtml()


def test_work_face_present():
    # Mile 4 — the Work face is the real FaceWork, not a placeholder.
    p = _make_panel()
    assert p._work_face is not None
    assert hasattr(p._work_face, "_cook")


def test_work_face_pulses_while_thinking():
    # The cook bar runs its indeterminate busy sweep while the agent thinks
    # (QProgressBar range 0..0 — v9 DsCookBar), and rests static after.
    p = _make_panel()
    p._set_thinking(True)
    assert p._work_face._cook.maximum() == 0, "thinking → indeterminate sweep"
    p._set_thinking(False)
    assert p._work_face._cook.maximum() != 0, "at rest → static track"


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
    # Real cook counts switch the bar out of the busy sweep into determinate
    # progress; the cookline reads the comp's "cooked d/t" grammar.
    p = _make_panel()
    p._work_face.set_cook(14, 30)
    assert p._work_face._cook.maximum() == 30
    assert p._work_face._cook.value() == 14
    assert "14/30" in p._work_face._cook_lbl.text()


def test_review_face_present_with_gate():
    # Mile 5 — the Review face is the real FaceReview, and self._gate aliases
    # the embedded gate so the consent wiring stays intact.
    p = _make_panel()
    assert p._review_face is not None
    assert p._gate is p._review_face.gate


def test_review_show_result_populates_all_parts():
    # Simulated 'done' → render + verdict + SIGNED + credit + flags + detail.
    # v9 synthesis: DECISION leads the headline; VIA + paths fold into the
    # collapsed detail; SIGNED is a display-only authorship line.
    p = _make_panel()
    rf = p._review_face
    rf.show_result(
        verdict="The crystal reads at the scene's IOR now — Dark_Glass landed.",
        credit=[("DECISION", "Dark_Glass", "over Diamond, closer to scene IOR"),
                ("VIA", "materiallinker → link_type_1", "")],
        flags=[("ok", "render ok"), ("fail", "EXR not written — BL-007")],
        paths=["/materials/AMD/link_type_1", "/Render/Products/render_settings"],
        meta="karma_xpu · f1 · 1920×1080",
        signed="sonnet-4.6",
    )
    assert "Dark_Glass" in rf._verdict.text()
    # DECISION leads the credit grid; VIA folds into the (collapsed) detail
    assert len(rf._decisions) == 1
    assert rf._via_box.count() == 1
    assert rf._flags_box.count() == 2
    # SIGNED line is display-only and shown
    assert "sonnet-4.6" in rf._signed.text() and not rf._signed.isHidden()
    # detail (VIA + paths) starts collapsed, expands on toggle
    assert rf._detail.isHidden()
    rf._toggle_detail()
    assert not rf._detail.isHidden()
    assert "link_type_1" in rf._paths.text()


def test_signed_line_is_display_only():
    # Spike 3 — SIGNED is a display-only label; setting it shows the text and
    # clearing it hides it. FaceReview has no hou/USD access by construction, so
    # the SIGNED line can never author customData (invariant 3).
    p = _make_panel()
    rf = p._review_face
    rf.set_signed("sonnet-4.6")
    assert "sonnet-4.6" in rf._signed.text() and not rf._signed.isHidden()
    rf.set_signed("")
    assert rf._signed.isHidden()


def test_bl007_flag_detects_missing_output():
    # BL-007: no file on disk → the silent-no-output failure is flagged red.
    from synapse.panel.face_review import bl007_flag
    status, text = bl007_flag("")
    assert status == "fail" and "BL-007" in text


def test_review_actions_wired_to_panel():
    # accept/commit signals reach the panel handlers without error; commit keeps
    # the done sub-state forward (it routes through the gate, not /stage) and
    # never switches the tab.
    p = _make_panel()
    p._review_face.accepted.emit()
    p._review_face.committed.emit()
    assert p._work_substate == "done"


def test_done_edge_populates_review_verdict():
    # The done edge fills the Work done sub-state and lifts the first line as the
    # verdict (no tab switch — the same-pane law).
    p = _make_panel()
    p._stream_buf = ["Dark_Glass landed; the crystal reads at the scene IOR now."]
    p._was_busy = True
    p._set_busy(False)
    assert p._work_substate == "done"
    assert "Dark_Glass" in p._review_face._verdict.text()


def test_fonts_bundled_and_registered():
    # Spike 6 — both bundled families register in QFontDatabase (or the
    # build-mismatch flag is raised, per locked call #3 — never a hard fail).
    p = _make_panel()
    st = p._font_status
    assert st["ok"] or st["build_mismatch"]
    if st["ok"]:
        assert "Space Grotesk" in st["families"] and "Space Mono" in st["families"]


def test_font_load_survives_panel_reload_purge():
    # v9 hardening (CRUCIBLE) — the .pypanel loader purges synapse.* from
    # sys.modules on every panel reopen, which resets fontload's module cache.
    # The QFontDatabase registrations OUTLIVE the purge, so a fresh import must
    # adopt the process-level status instead of re-registering the bundle
    # (3 duplicate registrations per reopen, unbounded over a session).
    from synapse.panel.designsystem import fontload
    QtGui = fontload.QtGui
    first = fontload.load_application_fonts()     # ensure the real load ran
    calls = {"n": 0}
    real = QtGui.QFontDatabase.addApplicationFont

    def counted(path):
        calls["n"] += 1
        return real(path)

    QtGui.QFontDatabase.addApplicationFont = staticmethod(counted)
    try:
        fontload._STATUS = None                   # what a fresh import sees
        again = fontload.load_application_fonts()
        assert calls["n"] == 0, "a reload purge must not re-register the bundle"
        assert again["ok"] == first["ok"]
        assert again["build_mismatch"] == first["build_mismatch"]
        assert again["families"] == first["families"]
    finally:
        QtGui.QFontDatabase.addApplicationFont = real


def test_tracking_applied_per_role():
    # v9 comp — the factory sets PercentageSpacing = 100 + em×100 per role
    # (the AbsoluteSpacing form was superseded with the TRACKING_EM restore).
    from synapse.panel.designsystem import fontload
    from synapse.panel.designsystem import tokens as t
    f = fontload.tracked_font("BRAND", 16)
    PercentageSpacing = type(f).PercentageSpacing
    assert f.letterSpacingType() == PercentageSpacing
    assert abs(f.letterSpacing() - (100 + t.TRACKING_EM["BRAND"] * 100)) < 0.05
    # negative tracking for the display role (tighter verdict) → below 100%
    fd = fontload.tracked_font("DISPLAY", 15)
    assert 0 < fd.letterSpacing() < 100
    # BODY: untracked — spacing left at the QFont default (0 / Percentage)
    fb = fontload.tracked_font("BODY", 13)
    assert fb.letterSpacingType() == PercentageSpacing
    assert fb.letterSpacing() == 0


def test_tracked_font_uses_bundled_families():
    # v9 ratified call — tracked_font defaults to the bundled Space Grotesk;
    # mono=True opts into Space Mono. When the bundle failed to register, the
    # factory keeps the native family instead (graceful fallback, flagged).
    from synapse.panel.designsystem import fontload
    p = _make_panel()                    # panel init loads the bundle
    st = fontload.font_status() or p._font_status or {}
    sans = fontload.tracked_font("BRAND", 14)
    mono = fontload.tracked_font("DATA", 11, mono=True)
    if st.get("ok") and not st.get("build_mismatch"):
        assert sans.family() == "Space Grotesk"
        assert mono.family() == "Space Mono"
    else:
        assert st.get("build_mismatch"), "unregistered bundle must be flagged"


def test_wordmark_carries_brand_tracking():
    # v9 — the wordmark QFont carries BRAND PercentageSpacing (QSS can't track).
    from synapse.panel.designsystem import tokens as t
    p = _make_panel()
    f = p._wordmark.font()
    assert f.letterSpacingType() == type(f).PercentageSpacing
    assert abs(f.letterSpacing() - (100 + t.TRACKING_EM["BRAND"] * 100)) < 0.05


def test_rail_author_token_shows():
    # v9 — the rail author token is the ENGINE+MODEL click target: a clickable
    # button whose text tracks _author_token(); its menu data covers every
    # provider with exactly one active (engine, model) pair.
    from synapse.panel.providers.registry import PROVIDER_IDS
    p = _make_panel()
    assert p._author_lbl is not None
    assert isinstance(p._author_lbl, QtWidgets.QAbstractButton)
    assert p._author_lbl.text() == p._author_token()
    assert hasattr(p, "_open_author_menu")
    items = p._author_menu_items()
    assert [pid for pid, _, _ in items] == list(PROVIDER_IDS)
    active = [(pid, mid) for pid, _, rows in items for mid, _, on in rows if on]
    assert active == [(p._provider_id, p._active_model())]


def test_author_menu_tracks_engine_and_model_switch():
    # v9 — selection stays OBSERVABLE on the token: a provider switch and a
    # model switch each repaint the author token and move the single active row.
    p = _make_panel()
    pid0, mid0 = p._provider_id, p._active_model()   # restore whatever was picked
    p._set_provider("gemini")
    try:
        assert p._author_lbl.text() == p._author_token()
        active = [(pid, mid) for pid, _, rows in p._author_menu_items()
                  for mid, _, on in rows if on]
        assert active == [("gemini", p._active_model())]
        # a row pick through the menu path switches engine AND model in one go
        p._pick_engine_model("claude", "claude-fable-5")
        assert p._provider_id == "claude"
        assert p._active_model() == "claude-fable-5"
        assert p._author_lbl.text() == p._author_token()
        active = [(pid, mid) for pid, _, rows in p._author_menu_items()
                  for mid, _, on in rows if on]
        assert active == [("claude", "claude-fable-5")]
    finally:
        p._pick_engine_model(pid0, mid0)


def test_stale_persisted_model_selection_stays_observable():
    # v9 hardening (CRUCIBLE) — a persisted model pick can go STALE between
    # sessions (registry rotation) while its provider stays valid. The boot
    # merge keeps the pick; the selection must stay OBSERVABLE: every menu
    # still leads with the registry rows in order, and the active pair is
    # present + checked (exactly one) — never a silently blank menu.
    from synapse.panel.providers import registry as reg
    p = _make_panel()
    pid = p._provider_id
    stale = "claude-sonnet-4-5-RETIRED-TEST"
    p._model_by_provider[pid] = stale     # what boot merges from a stale file
    try:
        want_ids = [m for m, _ in reg.models_for(pid)]
        items = p._model_menu_items()
        got_ids = [m for m, _, _ in items]
        actives = [m for m, _, a in items if a]
        assert got_ids[: len(want_ids)] == want_ids, "registry rows must lead, in order"
        assert actives == [stale], "the stale pick must be checked (exactly one)"
        assert got_ids[-1] == stale, "the stale row is appended at the tail"
        a_active = [(apid, mid) for apid, _, rows in p._author_menu_items()
                    for mid, _, on in rows if on]
        assert a_active == [(pid, stale)], "author menu: exactly one active pair"
        assert p._author_token(), "the token still renders a signature"
    finally:
        p._model_by_provider[pid] = reg.PROVIDER_DEFAULT_MODEL[pid]


def test_stop_gated_to_working_state():
    # Spike 5 — Stop is visible ONLY while working (mark sweeping), wired to the
    # existing stop handler; hidden at rest.
    p = _make_panel()
    assert p._stop_btn.isHidden(), "Stop hidden at rest"
    p._set_busy(True)
    assert not p._stop_btn.isHidden() and p._stop_btn.isEnabled()
    assert p._mark._state == "working"
    p._set_busy(False)
    assert p._stop_btn.isHidden(), "Stop hidden when not working"


def test_context_line_reflects_frame_and_selection():
    # Spike 5 — the selection-context line is built from the confirmed
    # hou.selectedNodes / hou.frame API; the selection callback funnels to the
    # same updater (V0-guarded — no phantom call when hou.ui is absent).
    p = _make_panel()
    p._update_context()
    assert "f1" in p._ctx_label.text()
    p._on_selection_changed()
    assert "f1" in p._ctx_label.text()


def test_reduced_motion_stops_animations():
    # Spike 7 — reduced-motion honored: the thinking pulse stops the mark spin
    # AND the cook-preview pulse (no continuous repaints).
    from synapse.panel.designsystem import tokens as t
    t.set_reduced_motion(True)
    try:
        p = _make_panel()
        p._set_thinking(True)
        assert not p._mark._spin.isActive(), "mark must not spin under reduced-motion"
        assert p._work_face._cook.maximum() != 0, "cook bar must stay static"
    finally:
        t.set_reduced_motion(None)


def test_motion_default_still_animates():
    # Guard the inverse: with motion on (default), the thinking pulse runs — so
    # the reduced-motion test isn't trivially passing on a dead animation.
    from synapse.panel.designsystem import tokens as t
    t.set_reduced_motion(False)
    try:
        p = _make_panel()
        p._set_thinking(True)
        assert p._work_face._cook.maximum() == 0   # indeterminate busy sweep
    finally:
        t.set_reduced_motion(None)


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
