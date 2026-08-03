"""L5-13: prominence must be visible. L5-14: hero takes the accent.

The compositor half already works -- widget.setProperty("prominence", ...)
plus repolish -- but a repolish repaints nothing unless the stylesheet
selects on the property. These tests pin the stylesheet half: a rule for
hero, a rule for quiet, and the two must not collapse into the same paint.

L5-14 amends the hero rung: ID-qualified hero rules lift to the accent
the widget's role calls for -- WARM (human/orientation) or SIGNAL
(technical/economic) -- and never a hex tokens.py doesn't define
(SIGNAL + WARM are the two-accent ceiling).
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
