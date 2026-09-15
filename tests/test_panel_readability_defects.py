"""READABILITY.md 2026-09-15 - the four measured defects, pinned.

Every contrast number below is computed HERE, from WCAG 2.1 relative luminance,
against an implementation that does not import the one in ``tokens.py``. If the
design system's own arithmetic ever drifts, these still read true.

  D1  five context-bar rules emitted ``pt`` where the whole sheet emits ``px``,
      so SIZE_LABEL (11, the smallest token) rendered at 15 - SIZE_TITLE.
  D2  SEND rested on SIGNAL_DEEP under TEXT_ON_ACCENT at 3.78:1 and only passed
      on :hover.
  D3  the quiet ramp (tertiary / disabled / the placeholder) never cleared AA,
      and the placeholder was not a design-system colour at all.
  D4  roles asked for weights their family cannot draw, and the one weight the
      family CAN draw (sans 500) was thrown away.

The pure tests need no Qt. The raster tests need a Qt binding and are skipped
without one - run this file under hython to exercise them.
"""

import ast
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_DS = os.path.join(_ROOT, "python", "synapse", "panel", "designsystem")

AA = 4.5


# -- WCAG 2.1, implemented here on purpose ---------------------------------
def _chan(v):
    v = v / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _luminance(hex_str):
    h = hex_str.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _chan(r) + 0.7152 * _chan(g) + 0.0722 * _chan(b)


def ratio(fg, bg):
    a, b = _luminance(fg), _luminance(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def _src(name):
    with open(os.path.join(_DS, name), "r", encoding="utf-8") as fh:
        return fh.read()


def test_wcag_helper_matches_published_reference_pairs():
    """The instrument before the measurement: black on white is exactly 21."""
    assert round(ratio("#000000", "#FFFFFF"), 2) == 21.0
    assert round(ratio("#FFFFFF", "#FFFFFF"), 2) == 1.0
    assert round(ratio("#777777", "#FFFFFF"), 2) == 4.48   # the classic AA miss


# -- D1 - one unit character inverted four rungs ---------------------------

_FONT_SIZE_UNIT = re.compile(r"font-size\s*:\s*[^;}\n]*?\b(pt|em|ex|pc|in|cm|mm)\b")


def test_d1_no_font_size_in_the_design_system_uses_a_non_px_unit():
    offenders = []
    for name in ("qss.py", "components.py", "tokens.py", "rhythm.py"):
        body = re.sub(r"/\*.*?\*/", "", _src(name), flags=re.DOTALL)
        for m in _FONT_SIZE_UNIT.finditer(body):
            offenders.append("%s:L%d %s" % (
                name, body[:m.start()].count("\n") + 1,
                body[m.start():].split("\n", 1)[0].strip()))
    assert not offenders, (
        "font-size in a non-px unit: Qt resolves pt through DPI, so the SAME "
        "token renders at a different rung than the rest of the sheet "
        "(11pt = 15px at 96 DPI = SIZE_TITLE): %r" % offenders)


def test_d1_context_bar_rules_carry_their_intended_tokens():
    from synapse.panel.designsystem import qss, tokens as t

    sheet = qss.stylesheet()

    def blocks(key):
        """Every generated rule body carrying this sweep_a_style key."""
        out = []
        for m in re.finditer(re.escape('sweep_a_style="%s"' % key), sheet):
            close = sheet.index("}", m.end())
            open_ = sheet.rindex("{", 0, close)
            out.append(sheet[open_:close])
        return out

    crumb = blocks("context_breadcrumb")
    assert crumb, "context_breadcrumb rule vanished"
    assert any("font-size: %dpx" % t.SIZE_LABEL in b for b in crumb), crumb
    assert t.SIZE_LABEL < t.SIZE_TITLE, "SIZE_LABEL must stay the smaller rung"
    assert not any("font-size: %dpx" % t.SIZE_TITLE in b for b in crumb), (
        "the breadcrumb is still rendering at the TITLE rung")
    for key in ("context_memory", "context_health", "context_action",
                "context_frame"):
        sized = [b for b in blocks(key) if "font-size" in b]
        assert sized, key
        assert all("font-size: %dpx" % t.SIZE_UI in b for b in sized), (key, sized[0])


# -- D2 - a knockout that only passed on hover -----------------------------

_KNOCKOUT = re.compile(
    r"background:\s*(#[0-9A-Fa-f]{6})\s*;\s*color:\s*(#[0-9A-Fa-f]{6})\s*;")


def test_d2_every_generated_knockout_fill_clears_AA():
    """Not just SEND: any rule that sets a fill and an ink in one breath."""
    from synapse.panel.designsystem import qss, tokens as t

    ink = t.TEXT_ON_ACCENT.upper()
    failures = []
    for fill, colour in _KNOCKOUT.findall(qss.stylesheet()):
        if colour.upper() != ink:
            continue
        r = ratio(colour, fill)
        if r < AA:
            failures.append("ink %s on fill %s = %.2f:1" % (colour, fill, r))
    assert not failures, "knockout text below AA %.1f: %r" % (AA, failures)


def test_d2_send_rest_state_clears_AA_not_only_its_hover():
    from synapse.panel.designsystem import tokens as t

    rest = ratio(t.TEXT_ON_ACCENT, t.SIGNAL_DEEP)
    hover = ratio(t.TEXT_ON_ACCENT, t.SIGNAL)
    assert rest >= AA, (
        "SEND at REST is %.2f:1 on SIGNAL_DEEP %s; it only passes on :hover "
        "(%.2f:1). A button is read at rest." % (rest, t.SIGNAL_DEEP, hover))


def test_d2_token_comment_no_longer_claims_AA_for_a_fill_it_never_lands_on():
    body = _src("tokens.py")
    line = [l for l in body.splitlines() if l.startswith("TEXT_ON_ACCENT")]
    assert len(line) == 1, line
    assert "AA-safe" not in line[0], (
        "the TEXT_ON_ACCENT line still carries the unqualified 'AA-safe' claim; "
        "it was only ever true of SIGNAL, never of SIGNAL_DEEP")


# -- D3 - the quiet ramp, and a colour the system did not own --------------

_LANDING = ("ground", "field_inset", "panel", "surface", "raised", "border")


def _ramp(host=(42, 42, 42)):
    from synapse.panel.designsystem import tokens as t
    return t._derive_palette(*host)


@pytest.mark.parametrize(
    "role", ["primary", "secondary", "tertiary", "bright", "disabled"])
def test_d3_every_text_role_clears_AA_on_every_surface_it_lands_on(role):
    surf, txt = _ramp()
    worst = min((ratio(txt[role], surf[s]), s) for s in _LANDING)
    assert worst[0] >= AA, (
        "%s %s is %.2f:1 on %s (%s) - under AA %.1f. The ramp's own docstring "
        "claims AA holds at every host grey." % (
            role, txt[role], worst[0], worst[1], surf[worst[1]], AA))


def test_d3_body_rungs_did_not_move():
    """The brief freezes these three. If a remedy moved them, it overreached."""
    surf, txt = _ramp()
    panel = surf["panel"]
    for role, expected in (("primary", 8.32), ("secondary", 5.49),
                           ("bright", 10.67)):
        assert round(ratio(txt[role], panel), 2) == expected, role


def test_d3_placeholder_is_a_named_token_not_a_qt_palette_default():
    from synapse.panel.designsystem import tokens as t

    assert hasattr(t, "TEXT_PLACEHOLDER"), (
        "the input placeholder is painted from QPalette::PlaceholderText, "
        "whose default is the text colour at 50 percent alpha - no token in "
        "the design system could reach it")
    # read components by source: importing it needs a Qt binding, and this
    # assertion is about ownership, not about rendering.
    names = {n.name for n in ast.walk(ast.parse(_src("components.py")))
             if isinstance(n, ast.FunctionDef)}
    assert "apply_placeholder_palette" in names, (
        "no design-system seam installs QPalette::PlaceholderText")
    installed = [f for f in os.listdir(os.path.join(_ROOT, "python", "synapse", "panel"))
                 if f == "synapse_panel.py"]
    assert installed, "panel root missing"
    root_src = open(os.path.join(_ROOT, "python", "synapse", "panel",
                                 "synapse_panel.py"), "r",
                    encoding="utf-8").read()
    assert "apply_placeholder_palette" in root_src, (
        "the seam exists but nothing calls it at the panel root, so Qt's "
        "default still paints the placeholder")
    r = ratio(t.TEXT_PLACEHOLDER, t.FIELD_INSET)
    assert r >= AA, "placeholder %s on FIELD_INSET %s = %.2f:1" % (
        t.TEXT_PLACEHOLDER, t.FIELD_INSET, r)


def test_d3_qt_default_placeholder_is_the_value_being_replaced():
    """Shows the defect's arithmetic so the fix is not taken on trust."""
    from synapse.panel.designsystem import tokens as t

    h_fg, h_bg = t.TEXT_PRIMARY.lstrip("#"), t.FIELD_INSET.lstrip("#")
    blended = "#%02X%02X%02X" % tuple(
        round(int(h_fg[i:i + 2], 16) * 0.5 + int(h_bg[i:i + 2], 16) * 0.5)
        for i in (0, 2, 4))
    assert ratio(blended, t.FIELD_INSET) < AA
    assert ratio(t.TEXT_PLACEHOLDER, t.FIELD_INSET) > ratio(blended,
                                                            t.FIELD_INSET)


# -- D4 - weights asking for faces that do not ship ------------------------

def test_d4_no_role_asks_its_family_for_a_weight_it_cannot_draw():
    from synapse.panel.designsystem import tokens as t

    assert hasattr(t, "FAMILY_WEIGHTS"), "the shippable weights must be named"
    bad = {}
    for role, spec in t.TYPE_ROLES.items():
        fam, weight = spec[0], spec[2]
        key = "mono" if fam == t.FONT_MONO_CSS else "sans"
        if weight not in t.FAMILY_WEIGHTS[key]:
            bad[role] = (key, weight, t.FAMILY_WEIGHTS[key])
    assert not bad, (
        "role(s) asking for a weight the family does not ship - the stylesheet "
        "says one thing and the raster says another: %r" % bad)


def test_d4_apply_font_role_delivers_the_medium_the_variable_face_ships():
    """sans 500 is a real face; the role path used to collapse it to 400."""
    tree = ast.parse(_src("components.py"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "apply_font_role")
    body = ast.unparse(fn)
    assert "setWeight" in body, (
        "apply_font_role never calls setWeight, so a role asking for 500 falls "
        "through setBold(weight >= 600) and is drawn at 400 - the Medium the "
        "variable Space Grotesk actually ships is discarded")
    assert "Medium" in body


def test_d4_the_two_weight_ladders_agree():
    """fontload.tracked_font and components.apply_font_role must not disagree
    about what a weight means; one ladder, two call sites."""
    for name, fnname in (("fontload.py", "tracked_font"),
                         ("components.py", "apply_font_role")):
        fn = next(n for n in ast.walk(ast.parse(_src(name)))
                  if isinstance(n, ast.FunctionDef) and n.name == fnname)
        body = ast.unparse(fn)
        assert "setBold" in body and "setWeight" in body, (name, fnname)


# -- raster proof (Qt only) ------------------------------------------------

def _qt():
    QtGui = pytest.importorskip("PySide6.QtGui")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    QtCore = pytest.importorskip("PySide6.QtCore")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["t"])
    return app, QtGui, QtWidgets, QtCore


def _ink(QtGui, QtCore, font, text="Handgloves 8", w=420, h=60):
    img = QtGui.QImage(w, h, QtGui.QImage.Format_Grayscale8)
    img.fill(0)
    p = QtGui.QPainter(img)
    p.setFont(font)
    p.setPen(QtGui.QColor("white"))
    p.drawText(QtCore.QRect(0, 0, w, h),
               QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, text)
    p.end()
    return sum(sum(bytes(img.constScanLine(y)[:w])) for y in range(h))


def test_d1_raster_a_pt_font_size_resolves_to_a_different_rung_than_px():
    app, QtGui, QtWidgets, _ = _qt()
    from synapse.panel.designsystem import tokens as t

    def px(css):
        lbl = QtWidgets.QLabel("Ag")
        lbl.setStyleSheet("QLabel { font-size: %s; }" % css)
        lbl.ensurePolished()
        return QtGui.QFontInfo(lbl.font()).pixelSize()

    dpi = app.primaryScreen().logicalDotsPerInchY()
    assert px("%dpx" % t.SIZE_LABEL) == t.SIZE_LABEL
    assert px("%dpt" % t.SIZE_LABEL) == round(t.SIZE_LABEL * dpi / 72.0), (
        "this is the defect's mechanism: pt goes through DPI, px does not")
    assert px("%dpt" % t.SIZE_LABEL) != t.SIZE_LABEL


def test_d4_raster_label_role_now_draws_more_ink_than_body_role():
    app, QtGui, QtWidgets, QtCore = _qt()
    from synapse.panel.designsystem import tokens as t, components, fontload

    fontload.load_application_fonts()

    def role_ink(role):
        lbl = QtWidgets.QLabel("Handgloves 8")
        components.apply_font_role(lbl, role)
        f = QtGui.QFont(lbl.font())
        f.setPixelSize(24)   # same size for both: weight is the only variable
        return _ink(QtGui, QtCore, f)

    body_ink = role_ink("body")
    label_ink = role_ink("label")
    assert t.TYPE_ROLES["label"][2] == t.WEIGHT_MEDIUM
    assert label_ink > body_ink, (
        "the `label` role asks for sans 500 and draws exactly as much ink as "
        "400 (%d vs %d) - the Medium is being discarded" % (label_ink, body_ink))


def test_d4_raster_roles_now_name_the_weight_they_actually_get():
    app, QtGui, QtWidgets, QtCore = _qt()
    from synapse.panel.designsystem import tokens as t, components, fontload

    fontload.load_application_fonts()
    for role, spec in t.TYPE_ROLES.items():
        lbl = QtWidgets.QLabel("Handgloves 8")
        components.apply_font_role(lbl, role)
        f = QtGui.QFont(lbl.font())
        f.setPixelSize(24)
        got = int(QtGui.QFontInfo(f).weight())
        assert got == spec[2], (
            "TYPE_ROLES[%r] declares weight %d but the screen draws %d"
            % (role, spec[2], got))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
