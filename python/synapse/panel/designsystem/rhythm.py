"""Opt-in layout rhythm; no Qt or QApplication needed at import time.

QSS handles the box/paint rules. This applier handles QLayout spacing and
QFont features QSS cannot express. Call after polish on the UI thread.
Unmarked widgets keep their current layout values, including on role removal.
"""

import logging

from . import tokens


logger = logging.getLogger(__name__)

# The existing grid is the vocabulary, not a second token system.
#
# Landing r3 (CTO rulings 2026-09-05, RULING-3 / RULING-4a):
#   shell - an edge container of the panel: the GUTTER inset left/right and
#           SPACE_SM air top/bottom (the comp's structural whitespace, one
#           consumer of tokens.GUTTER so the token is never a lie); gap 16.
#   stack - a flush utility stack (toolbars, input rows, card interiors):
#           gap 4, no margins, no QSS, no type. Not a parameter grid -
#           parm_row is reserved for real label/value grids.
#   band  - chrome bands that own their own hairlines (the panel root,
#           act + divider + input): gap 0, margins 0.
ROLE_GAPS = {
    "label": tokens.SPACE_GRID[2],
    "row": tokens.SPACE_GRID[2],
    "tag": tokens.SPACE_GRID[3],
    "card": tokens.SPACE_GRID[3],
    "parm_row": tokens.SPACE_GRID[0],
    "group": tokens.SPACE_GRID[3],
    "shell": tokens.SPACE_GRID[3],
    "stack": tokens.SPACE_GRID[0],
    "band": 0,
}
_MARGINS = {
    "row": (tokens.SPACE_MD, tokens.SPACE_12,
            tokens.SPACE_MD, tokens.SPACE_12),
    "tag": (tokens.SPACE_SM + tokens.SPACE_XS // 2, tokens.SPACE_12 // 2,
            tokens.SPACE_SM + tokens.SPACE_XS // 2, tokens.SPACE_12 // 2),
    "shell": (tokens.GUTTER, tokens.SPACE_SM, tokens.GUTTER, tokens.SPACE_SM),
}
_WARNED = set()


def _warn_once(kind, value):
    key = (kind, repr(value))
    if key not in _WARNED:
        _WARNED.add(key)
        logger.warning("rhythm: unknown %s %r; using standard group rhythm",
                       kind, value)


def _apply_type(widget, role):
    """Keep the existing family loader; no new families or tracking tokens."""
    if role not in ("label", "tag"):
        return
    # Lazy: importing rhythm/compositor remains safe without Qt installed.
    from . import fontload

    font = widget.font()
    fontload.apply_family(font, mono=True)
    font.setCapitalization(type(font).AllUppercase)
    # Battleplan section 4 values: label +0.08 em, tag +0.06 em. No tracking
    # token carries those names (tokens.py is frozen), so the numerically
    # equal existing entries are borrowed: SEND == 0.08, DATA * 2 == 0.06.
    em = (tokens.TRACKING_EM["SEND"] if role == "label"
          else tokens.TRACKING_EM["DATA"] * 2)
    font.setLetterSpacing(type(font).PercentageSpacing, 100.0 + em * 100.0)
    widget.setFont(font)


def apply(root, density="standard"):
    """Apply fixed margins and density-scaled base gaps to marked widgets.

    Returns the number of layouts visited, not a success verdict for unmarked
    regions. An unknown role uses standard group spacing and logs once per
    distinct value. Unknown density falls back to standard (manifests reject
    it upstream). Qt objects are walked without importing Qt or touching hou.
    """
    if not isinstance(density, str) or density not in tokens.DENSITY_GAP_SCALE:
        _warn_once("density", density)
        density = "standard"
    applied = 0
    stack = [root]
    while stack:
        widget = stack.pop()
        children = getattr(widget, "children", None)
        if callable(children):
            stack.extend(children())
        prop = getattr(widget, "property", None)
        layout_getter = getattr(widget, "layout", None)
        if not callable(prop) or not callable(layout_getter):
            continue  # QObject/layout/timer, not a QWidget owner
        role = prop("rhythm_role")
        if role is None or role == "":
            continue
        level = density
        if not isinstance(role, str) or role not in ROLE_GAPS:
            _warn_once("role", role)
            role, level = "group", "standard"
        layout = layout_getter()
        if layout is not None:
            layout.setSpacing(tokens.gap(ROLE_GAPS[role], level))
            layout.setContentsMargins(*_MARGINS.get(role, (0, 0, 0, 0)))
            applied += 1
        _apply_type(widget, role)
    return applied
