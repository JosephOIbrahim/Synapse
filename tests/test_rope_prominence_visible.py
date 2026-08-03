"""L5-13: prominence must be visible. L5-14: hero takes the accent.

The compositor half already works -- widget.setProperty("prominence", ...)
plus repolish -- but a repolish repaints nothing unless the stylesheet
selects on the property. These tests pin the stylesheet half: a rule for
hero, a rule for quiet, and the two must not collapse into the same paint.

L5-14 amends the hero rung: ID-qualified hero rules lift to the accent
the widget's role calls for -- WARM (human/orientation) or SIGNAL
(technical/economic) -- and never a hex tokens.py doesn't define
(SIGNAL + WARM are the two-accent ceiling).

L5-16 amends BUTTONS only (Joe's seat call: coral too loud): hero
buttons and SEND share one deep blue -- SIGNAL_DEEP at rest, SIGNAL on
hover, SIGNAL_PRESS pressed. WARM leaves hero BUTTON rules entirely;
non-button hero rules (meters, labels, verbs) keep their L5-14 accents.
SIGNAL_DEEP is a shade within SIGNAL (x0.85), not a third accent.

L5-20: Stop is the mark's second surface (MarkDot.set_halt_handler fires
the same _on_stop the rail button fires), so #DsStop takes the mark's one
warm note as a knockout -- WARM fill, TEXT_ON_ACCENT ink, WARM_HOVER /
WARM_PRESS on touch, the shared DISABLED_BG / TEXT_DISABLED grey when
idle. Not a hero-button rule: the L5-16 no-WARM-on-hero-buttons pin is
untouched, and no hex outside tokens.py may appear.
"""

import re

from synapse.panel.designsystem import tokens as t
from synapse.panel.designsystem.qss import stylesheet


def _rules(qss: str, level: str) -> list[str]:
    pattern = re.compile(r'[^\n{}]*\[prominence="' + level + r'"\][^{}]*\{[^{}]*\}')
    return [m.group(0).strip() for m in pattern.finditer(qss)]


def test_hero_rule_present():
    assert _rules(stylesheet(), "hero"), 'no QSS rule selects [prominence="hero"]'


def test_quiet_rule_present():
    assert _rules(stylesheet(), "quiet"), 'no QSS rule selects [prominence="quiet"]'


def test_hero_and_quiet_are_not_the_same_paint():
    qss = stylesheet()
    hero = re.search(r'^\*\[prominence="hero"\]\s*\{([^{}]*)\}', qss, re.M)
    quiet = re.search(r'^\*\[prominence="quiet"\]\s*\{([^{}]*)\}', qss, re.M)
    assert hero, 'no generic *[prominence="hero"] rule'
    assert quiet, 'no generic *[prominence="quiet"] rule'
    # same selector shape, so a byte-identical body would mean the two
    # prominence levels paint identically -- the exact bug this task fixes
    assert hero.group(1) != quiet.group(1)
    assert set(_rules(qss, "hero")) != set(_rules(qss, "quiet"))


def _hexes(text: str) -> set[str]:
    return {h.lower() for h in re.findall(r"#[0-9a-fA-F]{8}|#[0-9a-fA-F]{6}", text)}


def test_hero_takes_the_warm_accent():
    """L5-14: at least one hero rule lifts to the WARM (human) family."""
    hero = "\n".join(_rules(stylesheet(), "hero"))
    warm_family = _hexes(t.WARM) | _hexes(t.WARM_HOVER) | _hexes(t.WARM_PRESS)
    assert _hexes(hero) & warm_family, "no hero rule references the WARM accent family"


def test_hero_takes_the_signal_accent():
    """L5-14: at least one hero rule lifts to the SIGNAL (technical) family."""
    hero = "\n".join(_rules(stylesheet(), "hero"))
    signal_family = _hexes(t.SIGNAL) | _hexes(t.SIGNAL_HOVER) | _hexes(t.SIGNAL_PRESS)
    assert _hexes(hero) & signal_family, "no hero rule references the SIGNAL accent family"


def test_hero_button_reads_as_knockout():
    """L5-15/L5-16: a hero button promotes to the construction
    [variant="primary"] already uses -- accent fill + TEXT_ON_ACCENT ink
    (knockout) -- rather than tinting the outline, and paints only hexes
    tokens.py sanctions for it (the deep-blue rest/hover/press triple +
    the one reversed ink)."""
    qss = stylesheet()
    rules = [r for r in _rules(qss, "hero") if r.startswith("QPushButton#DsButton")]
    assert rules, 'no QSS rule selects QPushButton#DsButton[prominence="hero"]'
    base = [r for r in rules if ":hover" not in r and ":pressed" not in r]
    assert base, 'no base QPushButton#DsButton[prominence="hero"] rule'
    assert re.search(r"background\s*:", base[0]), (
        "hero button rule sets no fill -- it still reads as outline"
    )
    assert _hexes(t.TEXT_ON_ACCENT) & _hexes(base[0]), (
        "hero button ink is not TEXT_ON_ACCENT -- not a knockout"
    )
    sanctioned = (
        _hexes(t.SIGNAL_DEEP) | _hexes(t.SIGNAL) | _hexes(t.SIGNAL_PRESS)
        | _hexes(t.TEXT_ON_ACCENT)
    )
    rogue = _hexes("\n".join(rules)) - sanctioned
    assert not rogue, f"hero button rules paint hexes outside the assigned accent + ink: {sorted(rogue)}"


def test_deep_blue_shared_by_send_and_hero_buttons():
    """L5-16: SIGNAL_DEEP fills BOTH the SEND rest state and at least one
    hero button rule -- CONNECT/CORPUS/SEND read as one deep blue."""
    qss = stylesheet()
    send = re.search(r'QPushButton#DsSend\s*\{[^{}]*\}', qss)
    assert send, "no QPushButton#DsSend rest rule"
    assert _hexes(t.SIGNAL_DEEP) & _hexes(send.group(0)), (
        "DsSend rest fill is not SIGNAL_DEEP"
    )
    hero_buttons = [r for r in _rules(qss, "hero") if r.startswith("QPushButton#DsButton")]
    assert any(_hexes(t.SIGNAL_DEEP) & _hexes(r) for r in hero_buttons), (
        "no hero button rule consumes SIGNAL_DEEP"
    )


def test_no_hero_button_rule_references_warm():
    """L5-16: WARM leaves hero BUTTON rules entirely (non-button hero
    rules -- meters, labels, verbs -- keep their L5-14 accents)."""
    qss = stylesheet()
    hero_buttons = [r for r in _rules(qss, "hero") if r.startswith("QPushButton#DsButton")]
    warm_family = _hexes(t.WARM) | _hexes(t.WARM_HOVER) | _hexes(t.WARM_PRESS)
    for rule in hero_buttons:
        assert not (_hexes(rule) & warm_family), (
            f"hero button rule still references WARM: {rule}"
        )


def _dsstop_rules(qss: str) -> list[str]:
    return [m.group(0) for m in re.finditer(r'QPushButton#DsStop[^{}]*\{[^{}]*\}', qss)]


def test_stop_is_a_warm_knockout():
    """L5-20: the #DsStop rest rule paints WARM fill + TEXT_ON_ACCENT ink --
    the mark's warm note as a knockout, not the danger outline."""
    rules = _dsstop_rules(stylesheet())
    assert rules, "no QPushButton#DsStop rule -- Stop still rides the danger variant"
    base = [r for r in rules if ":" not in r.split("{", 1)[0]]
    assert base, "no rest-state QPushButton#DsStop rule"
    assert _hexes(t.WARM) & _hexes(base[0]), "DsStop rest fill is not WARM"
    assert _hexes(t.TEXT_ON_ACCENT) & _hexes(base[0]), (
        "DsStop ink is not TEXT_ON_ACCENT -- not a knockout"
    )


def test_stop_defines_hover_pressed_and_disabled():
    """L5-20: the interaction ramp rides the WARM companions and the
    disabled state matches the filled siblings (the button ships disabled
    and hidden until work is in flight -- that state must exist)."""
    qss = stylesheet()
    for state, token, label in (
        (":hover", t.WARM_HOVER, "WARM_HOVER"),
        (":pressed", t.WARM_PRESS, "WARM_PRESS"),
    ):
        rule = re.search(r'QPushButton#DsStop' + state + r'\s*\{[^{}]*\}', qss)
        assert rule, f"no QPushButton#DsStop{state} rule"
        assert _hexes(token) & _hexes(rule.group(0)), f"DsStop{state} is not {label}"
    disabled = re.search(r'QPushButton#DsStop:disabled\s*\{[^{}]*\}', qss)
    assert disabled, "no QPushButton#DsStop:disabled rule"
    assert _hexes(t.DISABLED_BG) & _hexes(disabled.group(0)), (
        "DsStop:disabled fill is not DISABLED_BG"
    )
    assert _hexes(t.TEXT_DISABLED) & _hexes(disabled.group(0)), (
        "DsStop:disabled ink is not TEXT_DISABLED"
    )


def test_stop_paints_only_sanctioned_tokens():
    """L5-20: no new hex -- every hex in the DsStop rules is one of the
    tokens the task sanctions (all pre-existing in tokens.py)."""
    sanctioned = (
        _hexes(t.WARM) | _hexes(t.WARM_HOVER) | _hexes(t.WARM_PRESS)
        | _hexes(t.TEXT_ON_ACCENT) | _hexes(t.DISABLED_BG) | _hexes(t.TEXT_DISABLED)
    )
    rogue = _hexes("\n".join(_dsstop_rules(stylesheet()))) - sanctioned
    assert not rogue, f"DsStop rules paint hexes outside the sanctioned tokens: {sorted(rogue)}"


def test_no_rule_introduces_a_hex_absent_from_tokens():
    """Two-accent ceiling: every hex the sheet paints exists in tokens.py --
    a token value, or a stop of tokens.py's own atmosphere() root ramp.
    A hex with no tokens.py source would be a third accent sneaking in."""
    token_hexes: set[str] = set()
    for value in vars(t).values():
        if isinstance(value, str):
            token_hexes |= _hexes(value)
        elif isinstance(value, dict):
            for item in value.values():
                if isinstance(item, str):
                    token_hexes |= _hexes(item)
    token_hexes |= _hexes(t.atmosphere(t.PANEL))  # root field ramp, computed by tokens.py
    rogue = _hexes(stylesheet()) - token_hexes
    assert not rogue, f"stylesheet paints hexes tokens.py never defined: {sorted(rogue)}"
