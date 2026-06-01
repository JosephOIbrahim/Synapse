"""SYNAPSE panel design system — the single, vendored source of truth.

One token table, one QSS generator, one component library, one motion helper.
Self-contained: NO dependency on the un-shipped ~/.synapse/design side-channel
and NO raw hex in widget code. Import everything from here.

    from synapse.panel.designsystem import tokens as t
    from synapse.panel.designsystem.qss import stylesheet
    from synapse.panel.designsystem.components import Button, StatusDot

Replaces the three divergent token sources (design/tokens.py,
~/.synapse/design/tokens.py, panel/tokens.py) the redesign audit found.
"""

from . import tokens  # noqa: F401

__all__ = ["tokens"]
