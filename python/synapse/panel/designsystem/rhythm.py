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
# Edge condition (Joe's five, J5, 2026-09-05): a shell that meets the pane's
# TOP edge (rhythm_edge="top") takes one grid step more air above than the
# role's SPACE_SM - SPACE_MD, density-scaled through tokens.gap (24/16/12) -
# so the identity row is not choked by the pane edge. The role's default is
# unchanged: the ribbon and the faces (the other shell owners) keep SPACE_SM,
# so the air UNDER the rail does not move. Sides stay GUTTER, bottom SPACE_SM.
_EDGE_TOP = {"shell": tokens.SPACE_MD}
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


def apply_layout_margins(layout, role, density="standard", edge=None):
    """Use the shared role margins for both widget-owned and nested layouts."""
    margins = _MARGINS.get(role, (0, 0, 0, 0))
    if edge == "top" and role in _EDGE_TOP:
        margins = (margins[0], tokens.gap(_EDGE_TOP[role], density),
                   margins[2], margins[3])
    layout.setContentsMargins(*margins)


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
            # J5: the top-edge condition is the owner's, not the role's; the
            # value is the role table's, scaled like every other gap.
            apply_layout_margins(layout, role, level, prop("rhythm_edge"))
            applied += 1
        else:
            # bc-wave BC-3: a marked item VIEW (a QListView - no layout of
            # its own, but a viewport and setSpacing) takes the role's gap as
            # its view spacing. Duck-typed, no Qt import. The view pays the
            # spacing on both sides of every item, so `stack` (4/6/3) puts
            # rows gap(SPACE_SM) = 8/12/6 apart - arithmetic on the grid,
            # not a new role.
            set_spacing = getattr(widget, "setSpacing", None)
            if callable(set_spacing) and callable(getattr(widget, "viewport", None)):
                set_spacing(tokens.gap(ROLE_GAPS[role], level))
                applied += 1
        _apply_type(widget, role)
    return applied
