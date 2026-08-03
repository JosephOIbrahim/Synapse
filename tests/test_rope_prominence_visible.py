"""L5-13: prominence must be visible.

The compositor half already works -- widget.setProperty("prominence", ...)
plus repolish -- but a repolish repaints nothing unless the stylesheet
selects on the property. These tests pin the stylesheet half: a rule for
hero, a rule for quiet, and the two must not collapse into the same paint.
"""

import re

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
