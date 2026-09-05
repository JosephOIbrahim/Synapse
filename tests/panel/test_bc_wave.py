"""design/bc-wave — direction B + C pins (Joe's ruling 2026-09-05).

One file, one test per spec item, each committed RED before its fix:

  BC-1  the verb rail retires; EXPLAIN / FIX / OPTIMIZE live in the slash
        palette, BUILD HDA in the overflow; the CHAT face is transcript ->
        composer with nothing clipped at 340.
  BC-2  the rail says one truth: a state sentence that never elides.
  BC-3  slash-palette rows breathe on the grid.
  BC-4  one signal per fact at boot; beats on the grid.
  BC-5  the profile row folds into the overflow; the conversation takes >= 50%.
  BC-6a consent card in the panel's own vocabulary; turn receipt offers revert.
  BC-6b consent surfaces inline on CHAT (gated on the human G3 edit).

Real Qt only (hython 22.0.400 offscreen); skips under stock Python. Builds
against a scratch settings file so the artist's real picks are never read
or written (settings.py honours SYNAPSE_PANEL_SETTINGS).
"""
import os
import sys
import tempfile
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_hou = types.ModuleType("hou")
sys.modules.setdefault("hou", _hou)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
if not os.environ.get("SYNAPSE_PANEL_SETTINGS"):
    os.environ["SYNAPSE_PANEL_SETTINGS"] = os.path.join(
        tempfile.mkdtemp(prefix="synapse_bc_"), "panel_settings.json")

try:
    from PySide6 import QtWidgets, QtGui, QtCore
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets, QtGui, QtCore
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False

if _HAVE_QT:
    try:
        _qapp = getattr(QtWidgets, "QApplication", None)
        if not (isinstance(_qapp, type) and "PySide" in getattr(_qapp, "__module__", "")):
            _HAVE_QT = False
    except Exception:
        _HAVE_QT = False

import pytest

if not _HAVE_QT:
    pytestmark = pytest.mark.skip(reason="PySide unavailable - run via hython")

PROFILES = ("curious", "expert", "ml")
DENSITY = {"curious": "airy", "expert": "standard", "ml": "tight"}
W, H = 340, 760

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        from synapse.panel.designsystem import fontload
        fontload.load_application_fonts()
    return _APP


def _panel(profile="expert"):
    """A composed panel at the docking pref width, driven to the CHAT face."""
    _app()
    from synapse.panel.synapse_panel import SynapsePanel
    p = SynapsePanel()
    p._recompose(profile)
    p.resize(W, H)
    p.show()
    _app().processEvents()
    p._set_face("direct")
    p._converse_stack.setCurrentIndex(0)
    _app().processEvents()
    return p


def _chat_face(panel):
    return panel._faces.widget(0)


def _visible_buttons(root):
    return [b for b in root.findChildren(QtWidgets.QAbstractButton) if b.isVisible()]


# --------------------------------------------------------------------- BC-1
def test_verb_rail_retired_and_verbs_reachable():
    from synapse.panel.synapse_panel import SynapsePanel, _QUICK_ACTIONS
    from synapse.panel.tool_palette import ToolPalette
    assert not hasattr(SynapsePanel, "_build_act"), "the verb rail builder must be gone"
    for profile in PROFILES:
        p = _panel(profile)
        try:
            assert not hasattr(p, "_font_btn"), "Aa duplicated the overflow's text-size entries"
            # The three quick actions are palette rows: title = label, send = prompt.
            pal = ToolPalette(p, scale=p._chrome_scale)
            sends = {pal._list.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
                     for i in range(pal._list.count())}
            for _label, prompt in _QUICK_ACTIONS:
                assert prompt in sends, prompt
            pal.close()
            # BUILD HDA is an overflow action.
            menu = p._build_overflow_menu()
            texts = [a.text() for a in menu.actions()]
            assert any(t.startswith("Build HDA") for t in texts), texts
            # The CHAT face is [converse stack] ... [composer]; no act band, no divider.
            face = _chat_face(p)
            lay = face.layout()
            assert lay.itemAt(0).widget() is p._converse_stack
            assert lay.itemAt(lay.count() - 1).widget() is p._input.parentWidget()
            assert not face.findChildren(QtWidgets.QWidget, "DsDivider")
            # Nothing elided at 340 (F1): every visible text-bearing button
            # holds its hint. (The icon-only attach glyph sits at a fixed 52
            # against a 74 hint - F10's attach redesign, out of this wave; the
            # 36px icon draws whole inside 52, so no glyph is cut.)
            clipped = [(b.objectName(), b.text(), b.width(), b.sizeHint().width())
                       for b in _visible_buttons(face)
                       if b.text() and b.width() < b.sizeHint().width()]
            assert not clipped, (profile, clipped)
        finally:
            p.close()


# --------------------------------------------------------------------- BC-2
def _rail(panel):
    return panel._region_cache["_build_rail"]


def _in_a_layout(w):
    parent = w.parentWidget()
    lay = parent.layout() if parent is not None else None
    return lay is not None and lay.indexOf(w) != -1


def test_rail_one_state_sentence_never_elides():
    from synapse.panel.designsystem import tokens as t
    bounds = {"curious": 400, "expert": 380, "ml": 380}
    for profile in PROFILES:
        p = _panel(profile)
        try:
            rail = _rail(p)
            # Exactly one visible text label on the rail besides the wordmark.
            labels = [w for w in rail.findChildren(QtWidgets.QLabel)
                      if w.isVisible() and w.text() and w is not p._wordmark]
            assert labels == [p._header_status], [(w.objectName(), w.text()) for w in labels]
            sentence = p._header_status
            assert sentence.width() >= sentence.sizeHint().width(), (
                profile, sentence.text(), sentence.width(), sentence.sizeHint().width())
            # One truth at boot: not connected (headless), said once.
            assert sentence.text() == t.STATUS["disconnected"][2]
            assert p._mark._state == "disconnected"
            # Nothing on the rail gives way silently (no Ignored policy).
            ignored = [w.objectName() or type(w).__name__
                       for w in rail.findChildren(QtWidgets.QWidget)
                       if w.isVisible()
                       and w.sizePolicy().horizontalPolicy() == QtWidgets.QSizePolicy.Policy.Ignored]
            assert not ignored, ignored
            # Working: Stop shows, Connect hides, the sentence follows STATUS and
            # ignores tool chatter (the Work face's plan already carries it).
            p._set_busy(True)
            _app().processEvents()
            assert p._stop_btn.isVisible() and not p._connect_btn.isVisible()
            assert sentence.text() == t.STATUS["working"][2]
            p._on_tool_status("houdini_render", "running", "")
            assert sentence.text() == t.STATUS["working"][2]
            p._on_stop()
            assert sentence.text().startswith("Stopping")
            assert sentence.width() >= sentence.sizeHint().width()
            p._set_busy(False)
            _app().processEvents()
            assert sentence.text() == "Result ready"
            assert p._connect_btn.isVisible() and not p._stop_btn.isVisible()
            # The rail fits the docking bound for its density.
            assert rail.minimumSizeHint().width() <= bounds[profile], (
                profile, rail.minimumSizeHint().width())
            # The chrome that left the rail is read through the overflow.
            texts = [a.text() for a in p._build_overflow_menu().actions()]
            for want in ("Palette", "Ground the corpus", "Health", "Help"):
                assert any(x.startswith(want) for x in texts), (want, texts)
            # Hidden owners: constructed for their writers, in no layout.
            # (Joe's Addendum 2: the model token is NOT one of them - it
            # stays visible top right; see test_author_token_visible_top_right.)
            for name in ("_foot_label", "_foot_dot", "_meter_lbl", "_palette_hint",
                         "_corpus_btn", "_help_btn"):
                w = getattr(p, name)
                assert not w.isVisible() and not _in_a_layout(w), name
            assert not hasattr(p, "_observe")
            assert not hasattr(p, "_health_strip")
        finally:
            p.close()


def test_author_token_visible_top_right():
    """Joe's Addendum 2 (2026-09-05): the MODEL is always visible, top right.

    The active provider/model is the one fact the artist must never lose. It
    sits top right of the panel at rest, in every profile and density, at
    PANEL_PREF_WIDTH 340: Space Mono (the data voice), DATA tracking, at or
    above the type floor, never elided (a hard minimum from its own hint),
    never in the overflow; it names the live provider/model and click opens
    the existing picker."""
    from synapse.panel.designsystem import tokens as t, fontload
    _app()   # a QFont before the QApplication is a silent hython abort
    mono = QtGui.QFontInfo(fontload.apply_family(QtGui.QFont(), mono=True)).family()
    for profile in PROFILES:
        p = _panel(profile)
        try:
            rail = _rail(p)
            tok = p._author_lbl
            assert tok.isVisible() and _in_a_layout(tok), profile
            assert tok.text() and tok.text() == p._author_token(), tok.text()
            assert tok.minimumWidth() >= tok.sizeHint().width(), (
                profile, tok.minimumWidth(), tok.sizeHint().width())
            assert tok.width() >= tok.sizeHint().width(), (
                profile, tok.text(), tok.width(), tok.sizeHint().width())
            # Top right of the rail: right edge inside the rail's gutter, on
            # the wordmark's row (the identity row), right of the panel's midline.
            tl = tok.mapTo(rail, QtCore.QPoint(0, 0))
            wl = p._wordmark.mapTo(rail, QtCore.QPoint(0, 0))
            assert tl.x() + tok.width() <= rail.width() - t.GUTTER + 1, (
                profile, tl.x(), tok.width(), rail.width())
            assert tl.x() > rail.width() // 2, (profile, tl.x())
            assert abs((tl.y() + tok.height() // 2) - (wl.y() + p._wordmark.height() // 2))                 <= p._wordmark.height(), (profile, tl.y(), wl.y())
            # The data voice at the floor, tracked as DATA.
            f = tok.font()
            assert QtGui.QFontInfo(f).family() == mono
            assert QtGui.QFontInfo(f).pixelSize() >= t.scaled(t.SIZE_SMALL, p._chrome_scale)
            assert abs(f.letterSpacing() - (100.0 + t.TRACKING_EM["DATA"] * 100.0)) < 0.05
            # Never in the overflow.
            texts = [a.text() for a in p._build_overflow_menu().actions()]
            assert tok.text() not in texts
            # G3 target floor: the token is a click target >= 26px tall.
            assert tok.sizeHint().height() >= 26, tok.sizeHint().height()
        finally:
            p.close()


# --------------------------------------------------------------------- BC-3
DENSITIES = ("airy", "standard", "tight")


def _ds_root(density, w=W, h=396):
    """A DsRoot stamped with a density - the opener the popups read."""
    from synapse.panel.designsystem import qss
    root = QtWidgets.QWidget()
    root.setObjectName("DsRoot")
    root.setProperty("density", density)
    root.setStyleSheet(qss.stylesheet())
    root.resize(w, h)
    root.show()
    _app().processEvents()
    return root


def _open_palettes(root):
    """Both palettes as the opener shows them (ToolPalette grows toward the
    opener until six rungs show; CommandPaletteWidget is capped at 400)."""
    from synapse.panel.tool_palette import ToolPalette
    from synapse.panel.command_palette import CommandPaletteWidget
    tp = ToolPalette(root)
    tp.show()
    cp = CommandPaletteWidget(root)
    cp.show_palette()
    _app().processEvents()
    return tp, cp


def _heads_and_rows(lst):
    items = [lst.item(i) for i in range(lst.count())]
    sel = QtCore.Qt.ItemFlag.ItemIsSelectable
    return ([it for it in items if not (it.flags() & sel)],
            [it for it in items if it.flags() & sel], items)


def test_palette_rows_breathe():
    """Ruling item 3: the option list gets real vertical rhythm from the roles.

    Rows are SPACE_XL (40) boxes on a 48/52/46 pitch (the list is a `stack`
    consumer: view spacing 4/6/3 paid on both sides = gap(SPACE_SM) between
    rows), group heads are SPACE_48 cells wearing the rhythm-label eyebrow
    (mono, upper, SEND +0.08em), and at least five options read whole at
    340x396 standard - for the slash palette AND the Ctrl+K palette."""
    from synapse.panel.designsystem import tokens as t
    _app()
    for density in DENSITIES:
        # The opener is the panel at the wave's docking size (340x760).
        root = _ds_root(density, h=H)
        try:
            for pal in _open_palettes(root):
                name = type(pal).__name__
                lst = pal._list
                heads, rows, items = _heads_and_rows(lst)
                assert heads and len(rows) >= 5, (name, len(heads), len(rows))
                gap = t.gap(t.SPACE_XS, density)
                # Five options read whole at the size the opener shows the
                # popup (a 396 ToolPalette holds a head + three: the search,
                # two axis grids and the legend own the rest, so it grows
                # toward the opener - never past it - until six rungs show).
                if density == "standard":
                    vp_h = lst.viewport().height()
                    full = [it for it in rows
                            if lst.visualItemRect(it).top() >= 0
                            and lst.visualItemRect(it).bottom() < vp_h]
                    assert len(full) >= 5, (name, pal.height(), vp_h, len(full))
                    assert pal.height() <= root.height() - t.SPACE_LG, (name, pal.height())
                # Row box and pitch, measured at the design size 340x396.
                pal.resize(W, 396)
                _app().processEvents()
                assert lst.spacing() == gap, (name, density, lst.spacing(), gap)
                # Row box and pitch: the first two adjacent option rows.
                pair = next((items[i], items[i + 1]) for i in range(len(items) - 1)
                            if items[i] in rows and items[i + 1] in rows)
                r0, r1 = lst.visualItemRect(pair[0]), lst.visualItemRect(pair[1])
                assert r0.height() == t.SPACE_XL, (name, density, r0.height())
                assert r1.y() - r0.y() == t.SPACE_XL + 2 * gap, (name, density, r1.y() - r0.y())
                # Group head: one SPACE_48 cell, the eyebrow type.
                h0 = lst.visualItemRect(heads[0])
                assert h0.height() == t.SPACE_48, (name, density, h0.height())
                f = heads[0].font()
                assert f.capitalization() == QtGui.QFont.Capitalization.AllUppercase, name
                assert abs(f.letterSpacing() - 108.0) < 0.05, (name, f.letterSpacing())
                pal.close()
        finally:
            root.close()


# --------------------------------------------------------------------- BC-4
def test_one_signal_per_fact_at_boot():
    """Ruling item 5 (ADHD spacing, light touch): outside the transcript the
    CHAT face says its idle state ONCE (the rail sentence) - the ribbon is
    absence, not 'no scene context'; the composer tells '/' exactly once
    (the placeholder G3 pins) and its legend sits at the chrome floor; the
    composer is a `stack` (grip / input / legend at 4/6/3); the recall card
    is a `band` through the applier, with no exemption lines left."""
    import io
    from synapse.panel.designsystem import tokens as t, rhythm
    src = open(os.path.join(_ROOT, "python", "synapse", "panel", "recall_card.py"),
               encoding="utf-8").read()
    assert "rhythm-exempt" not in src, "recall_card.py still carries exemption lines"
    for profile in PROFILES:
        p = _panel(profile)
        try:
            density = DENSITY[profile]
            assert p._ctx_label.text() == "", (profile, p._ctx_label.text())
            khint = p._khint
            assert QtGui.QFontInfo(khint.font()).pixelSize() >= t.scaled(t.SIZE_SMALL, p._chrome_scale), (
                profile, QtGui.QFontInfo(khint.font()).pixelSize())
            tellings = p._input.placeholderText().count("/") + khint.text().count("/")
            assert tellings == 1, (profile, p._input.placeholderText(), khint.text())
            composer = p._input.parentWidget()
            assert composer.property("rhythm_role") == "stack"
            assert composer.layout().spacing() == t.gap(t.SPACE_XS, density), (
                profile, composer.layout().spacing())
            # No hand-added spacer between the input row and the legend.
            assert all(composer.layout().itemAt(i).spacerItem() is None
                       for i in range(composer.layout().count()))
            card = p._recall_card
            assert card.property("rhythm_role") == "band"
            rhythm.apply(card, density)
            m = card.layout().contentsMargins()
            assert card.layout().spacing() == 0
            assert (m.left(), m.top(), m.right(), m.bottom()) == (0, 0, 0, 0)
        finally:
            p.close()


# --------------------------------------------------------------------- BC-5
def test_profile_row_folded():
    """Ruling item 6: the profile row folds into the overflow so the
    conversation holds a majority of the pane. No DsTabRow in the composed
    tree; the overflow's 'Profile >' holds three checkable actions with
    exactly one checked (the saved profile); triggering another recomposes
    live (root density changes, _layout_profile follows); the ribbon carries
    the CHAT / TOKEN pills; and the measured goal: chat.h / 760 >= 0.5 in
    curious, expert and ml at 340x760."""
    from synapse.panel.synapse_panel import SynapsePanel
    assert not hasattr(SynapsePanel, "_build_mode_bar"), "the tab strip builder must be gone"
    for profile in PROFILES:
        p = _panel(profile)
        try:
            assert not p.findChildren(QtWidgets.QWidget, "DsTabRow"), profile
            ribbon = p._region_cache["_build_context_ribbon"]
            lay = ribbon.layout()
            for key in ("direct", "token"):
                assert lay.indexOf(p._face_pills[key]) != -1, key
            menu = p._build_overflow_menu()
            # Reach the submenu through its parent (findChildren keeps C++
            # ownership with the menu; a bare QAction.menu() wrapper does not).
            prof = next((m for m in menu.findChildren(QtWidgets.QMenu)
                         if m.title() == "Profile"), None)
            assert prof is not None, [a.text() for a in menu.actions()]
            acts = [a for a in prof.actions() if a.isCheckable()]
            assert len(acts) == 3, [a.text() for a in acts]
            checked = [a for a in acts if a.isChecked()]
            assert len(checked) == 1 and checked[0].data() == p._layout_profile, (
                [(a.text(), a.isChecked()) for a in acts], p._layout_profile)
            # The conversation takes the majority at rest. Two readings, both
            # honest: (a) at first run L5-22 opens the composer divider at half
            # the space the chat and the prompt share (settings
            # .composer_start_height), so the transcript is never smaller than
            # the prompt; (b) with the composer at its floor - the state the
            # ruling's instrument (measure_regions.py) reads - the transcript
            # holds >= 50% of the 760 pane. Chrome (rail + ribbon + insets) is
            # what BC-5 governs; the divider is the artist's (L6).
            assert p._chat.height() >= p._input.height(), (
                profile, p._chat.height(), p._input.height())
            p._input.set_user_height(p._input._floor)
            _app().processEvents()                 # the composer's own LayoutRequest
            _chat_face(p).layout().activate()      # then the face re-lays
            _app().processEvents()
            share = p._chat.height() / H
            assert share >= 0.5, (profile, p._chat.height(), share)
            # A different profile recomposes live.
            # `profile` is what _panel() composed; _layout_profile is the boot
            # pick - choose a third so both the density and the pick move.
            other = next(a for a in acts if a.data() not in (p._layout_profile, profile))
            before = (p.property("density"), p._layout_profile)
            other.trigger()
            _app().processEvents()
            assert p._layout_profile == other.data()
            assert p.property("density") != before[0], (before, p.property("density"))
            assert [a for a in acts if a.isChecked()] == [other]
        finally:
            p.close()


# -------------------------------------------------------------------- BC-6a
def _proposal(level):
    return {"proposal_id": "p-%s" % level, "level": level,
            "operation": "delete_node" if level == "review" else "submit_render",
            "agent_id": "HANDS", "description": "bc-wave probe", "created_at": ""}


def _verbs(card):
    return {b.text(): b for b in card.findChildren(QtWidgets.QPushButton, "DsVerb")}


def _tags(card):
    return [w for w in card.findChildren(QtWidgets.QLabel)
            if w.property("rhythm_role") == "tag" and w.isVisible()]


def test_consent_card_vocabulary():
    """F4: the consent card speaks the panel's own vocabulary - a DsCard with
    the three bands, the level as a `tag` (HOT_SOFT only via status=BLOCKED
    for CRITICAL), DsVerb verbs at the 26px / SPACE_32 target floor, APPROVE
    the one accented thing on the card, REJECT hot; REVIEW gets '<- REVERT'
    (CLAUDE.md 1.2: REVIEW continues unless rejected, so the verb after the
    fact is a revert); a decision reads as a tag, never a hue."""
    import inspect
    from synapse.panel import gate_widget as gw
    from synapse.panel.designsystem import tokens as t, rhythm
    src = inspect.getsource(gw)
    assert "_LEVEL_COLORS" not in src, "level hues must be gone from the module"
    for density in DENSITIES:
        root = _ds_root(density, h=760)
        try:
            cards = {}
            for level in ("review", "approve", "critical"):
                card = gw._ProposalCard(_proposal(level), parent=root)
                root.layout() or QtWidgets.QVBoxLayout(root)
                root.layout().addWidget(card)
                cards[level] = card
            rhythm.apply(root, density)
            root.show()
            _app().processEvents()
            for level, card in cards.items():
                assert card.objectName() == "DsCard", level
                assert card.property("rhythm_role") == "band", level
                assert card.layout().spacing() == 0
                for band in ("DsCardHeader", "DsCardBody", "DsCardFooter"):
                    assert card.findChildren(QtWidgets.QWidget, band), (level, band)
                verbs = _verbs(card)
                if level == "review":
                    assert list(verbs) == ["← REVERT"], list(verbs)
                    assert verbs["← REVERT"].property("tone") in (None, ""), level
                else:
                    assert set(verbs) == {"REJECT", "APPROVE"}, list(verbs)
                    assert verbs["REJECT"].property("tone") == "hot"
                    assert verbs["APPROVE"].property("tone") == "accent"
                accented = [w for w in card.findChildren(QtWidgets.QWidget)
                            if w.property("tone") == "accent"]
                assert accented == ([verbs["APPROVE"]] if level != "review" else []), level
                for text, v in verbs.items():
                    assert v.isVisible(), (level, text)
                    assert min(v.width(), v.height()) >= 26, (level, text, v.width(), v.height())
                    assert v.height() >= t.SPACE_32, (level, text, v.height())
                level_tags = [w for w in _tags(card) if w.text() == level.upper()]
                assert len(level_tags) == 1, (level, [w.text() for w in _tags(card)])
                assert (level_tags[0].property("status") == "BLOCKED") == (level == "critical"), level
            # A decision is a tag, never a hue: verbs hide, the card disables.
            card = cards["approve"]
            card.mark_decided("rejected")
            _app().processEvents()
            assert all(not v.isVisible() for v in _verbs(card).values())
            decided = [w for w in _tags(card) if w.text() == "REJECTED"]
            assert decided and decided[0].property("status") == "BLOCKED"
            assert not card.isEnabled()
            # Not recorded: a tag too, and the card stays live (RULING 18).
            card = cards["critical"]
            card.mark_gate_unreachable()
            _app().processEvents()
            assert card.isEnabled() and all(v.isVisible() for v in _verbs(card).values())
            assert any(w.text() == "NOT RECORDED" and w.property("status") == "BLOCKED"
                       for w in _tags(card))
        finally:
            root.close()


def test_turn_receipt_offers_revert_on_chat():
    """F11: after a quiet turn that changed the scene, the CHAT surface offers
    an artist-clickable REVERT (the turn receipt in the consent slot); it is
    gone again once the artist sends the next message."""
    for profile in PROFILES:
        p = _panel(profile)
        try:
            p._start_worker = lambda: None     # the seam under test is the UI, not the worker
            p._set_busy(True)
            p._on_tool_status("houdini_create_node", "running", "/obj/geo1")
            p._on_tool_status("houdini_create_node", "done", "/obj/geo1")
            p._on_done()
            _app().processEvents()
            assert p._faces.currentIndex() == 0, profile
            face = _chat_face(p)
            reverts = [b for b in face.findChildren(QtWidgets.QAbstractButton)
                       if b.isVisible() and "REVERT" in b.text()]
            assert len(reverts) == 1, (profile, [b.text() for b in reverts])
            assert p._consent_slot.isVisible()
            assert p._consent_slot.property("rhythm_role") == "card"
            badge = [w for w in p._consent_slot.findChildren(QtWidgets.QLabel)
                     if w.isVisible() and "CHANGE" in w.text()]
            assert badge and badge[0].property("rhythm_role") == "tag", profile
            p._send("x")
            _app().processEvents()
            assert not any(b.isVisible() and "REVERT" in b.text()
                           for b in face.findChildren(QtWidgets.QAbstractButton)), profile
            assert not p._consent_slot.isVisible()
        finally:
            p.close()
