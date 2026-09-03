"""BP4-PANELFONT — typography invariants for the design-system authority.

Pins the rules this leg lands so a regression reddens:

  1. The generated stylesheet source (``designsystem/qss.py``) carries NO literal
     typography — every ``font-size`` / ``font-weight`` / ``font-family`` is a
     token interpolation (``{s(t.SIZE_*)}`` / ``{t.WEIGHT_*}``).  Re-introduce a
     hardcoded ``font-size: 13px`` or ``font-weight: 600`` → ``test_qss_*`` reddens.
  2. No size token sits below ``tokens.FONT_FLOOR_PX`` (the type floor), and the
     floor carries a provenance string opening with ``measured|DOC-STATED|
     UNKNOWN``.  Lower ``SIZE_MICRO`` under the floor → ``test_no_size_token_below_
     floor`` reddens.
  3. ``TYPE_ROLES`` weights are the three weight tokens (400/500/600), never bare
     literals.

SCOPE (stated honestly).  The authority is ``designsystem/``.  The legacy
stylesheet (``styles.py``) and the ~30 inline-styled feature modules
(``context_bar.py`` 9pt, ``gate_widget.py``, ``hda_views.py``,
``message_formatter.py``, …) still carry typography literals; those are
inventoried in ``harness/battleplan/notes/BP4_PANELFONT_AUDIT.md`` and handed
forward as held/named spawns (BP3-STYLES-MIGRATE + the BP4 typography spawns),
exactly as BP3-PANEL deferred the hex/spacing migration.  This test does NOT
assert a panel-wide purity it does not have — it guards the design-system core,
where the change set lives (T4 diff surface: designsystem / manifests / qss /
layout / scripts only).
"""

import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_DS = os.path.normpath(
    os.path.join(_HERE, "..", "python", "synapse", "panel", "designsystem")
)

# a font-* property whose FIRST non-space value char is not a `{`-interpolation
# is a literal. The final `[^\s;\n]` is load-bearing: without it `\s*` backtracks
# to zero so `(?!\{)` sits on the space before `{…}` and a token ref reads as a
# literal (the false positive this regex was rewritten to kill).
_LITERAL_TYPO = re.compile(r"font-(?:size|weight|family)\s*:\s*(?!\{)[^\s;\n]")


def _strip_css_comments(src):
    """Drop ``/* … */`` blocks so a comment that merely NAMES a font property
    (e.g. ``qss.py`` "No font-family: inherit …") never counts as a literal."""
    return re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)


def _read_ds(name):
    with open(os.path.join(_DS, name), "r", encoding="utf-8") as fh:
        return fh.read()


def test_qss_stylesheet_source_has_no_literal_typography():
    body = _strip_css_comments(_read_ds("qss.py"))
    offenders = []
    for m in _LITERAL_TYPO.finditer(body):
        ln = body[: m.start()].count("\n") + 1
        seg = body[m.start():].split(";", 1)[0].split("\n", 1)[0].strip()
        offenders.append("L%d: %s" % (ln, seg))
    assert not offenders, (
        "literal typography in designsystem/qss.py (must be a token ref such as "
        "{s(t.SIZE_UI)}px or {t.WEIGHT_SEMIBOLD}): %r" % offenders
    )


def test_type_roles_use_weight_tokens():
    from synapse.panel.designsystem import tokens as t

    allowed = {t.WEIGHT_REGULAR, t.WEIGHT_MEDIUM, t.WEIGHT_SEMIBOLD}
    assert allowed == {400, 500, 600}, "weight tokens must be 400/500/600"
    for role, spec in t.TYPE_ROLES.items():
        assert spec[2] in allowed, (
            "TYPE_ROLES[%r] weight %r is not a WEIGHT_* token" % (role, spec[2])
        )


def test_floor_constant_has_provenance():
    from synapse.panel.designsystem import tokens as t

    assert isinstance(t.FONT_FLOOR_PX, int) and t.FONT_FLOOR_PX > 0
    prov = t.FONT_FLOOR_PROVENANCE
    assert isinstance(prov, str) and prov.strip(), "floor needs a provenance string"
    assert prov.split()[0] in {"measured", "DOC-STATED", "UNKNOWN"}, (
        "floor provenance must open with measured|DOC-STATED|UNKNOWN: %r" % prov[:48]
    )


def test_no_size_token_below_floor():
    from synapse.panel.designsystem import tokens as t

    floor = t.FONT_FLOOR_PX
    sizes = {
        k: getattr(t, k)
        for k in dir(t)
        if k.startswith("SIZE_") and isinstance(getattr(t, k), int)
    }
    assert sizes, "no SIZE_* tokens found — scale missing"
    below = {k: v for k, v in sizes.items() if v < floor}
    assert not below, "size token(s) below FONT_FLOOR_PX=%d: %r" % (floor, below)

    role_below = {r: spec[1] for r, spec in t.TYPE_ROLES.items() if spec[1] < floor}
    assert not role_below, "TYPE_ROLES size(s) below floor %d: %r" % (floor, role_below)


def test_type_scale_is_at_most_five_sizes():
    """The mission caps the type scale at 5 sizes named by role."""
    from synapse.panel.designsystem import tokens as t

    unique = {
        getattr(t, k)
        for k in dir(t)
        if k.startswith("SIZE_") and isinstance(getattr(t, k), int)
    }
    assert len(unique) <= 5, "type scale has more than 5 distinct sizes: %r" % sorted(unique)


def test_probe_script_present_and_read_only():
    """The gui_required floor measurement seam ships with the leg."""
    probe = os.path.normpath(
        os.path.join(_HERE, "..", "python", "synapse", "panel", "scripts", "probe_ui_font.py")
    )
    assert os.path.exists(probe), "scripts/probe_ui_font.py missing"
    src = open(probe, "r", encoding="utf-8").read()
    assert "QApplication" in src and "pixelSize" in src and "scaledSize" in src
    # read-only: no scene/parm mutation verbs in the probe
    for verb in ("setParm", "set_parm", ".set(", "hou.hipFile", "createNode"):
        assert verb not in src, "probe must be read-only; found %r" % verb


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
