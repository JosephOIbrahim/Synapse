"""Panel-local design tokens — a RE-EXPORT of the one authority, plus aliases.

    The panel has exactly ONE colour authority: ``synapse.panel.designsystem.tokens``.

This module declares no colour. It re-exports the design system's, and adds the
panel-specific names that have no design-system home (HDA mode, chat layout,
the LED/state aliases). Import from HERE inside panel code, or from the design
system directly — both now resolve to the same values, which is the point.

WHY THIS FILE LOOKS THE WAY IT DOES
-----------------------------------
It used to inject ``~/.synapse/design`` — a directory OUTSIDE the repository,
not version controlled, absent on a teammate's machine — onto ``sys.path`` and
re-export colours from it, with hardcoded fallback literals behind an
``except ImportError``. The design system declared the same names with
different values. So a panel line rendered one of two different accent blues
depending on which import it happened to reach for, and which machine it ran
on. Fifteen names diverged, not one: SIGNAL/SIGNAL_HOVER/SIGNAL_PRESS, six
neutrals, both type families, and two panel dimensions.

An earlier pass converted call sites and left both modules declaring, which is
why converting call sites again would not have fixed it — with two authorities
alive, every new line is a coin flip. The repair is here, at the source.

Consequences worth knowing:

* The off-repo side channel is gone. The panel now renders identically on any
  machine with the package installed, which it did not before.
* ``ICON_SIZES`` and ``STATES`` used to exist ONLY in that off-repo file. They
  are defined below so the panel keeps them without depending on an
  unversioned file. ``STATES`` derives its colours from the re-exported names —
  deriving is not declaring, and it stays correct as the seeded ramp moves.
* ``TEXT``/``TEXT_DIM``/``HOVER``/``SCROLLBAR``/``HDA_INPUT_BG`` were hardcoded
  greys. They are now the design system's seeded roles, so they track the live
  Houdini colour scheme like the rest of the panel instead of staying dark on a
  light host.

Pinned by ``tests/panel/test_token_authority.py`` — whose reader is itself
calibrated, because a reader that cannot see a redeclaration would certify this
file while the collision survived.
"""

# ── The one authority ───────────────────────────────────────────────────
# A hard import, deliberately: the design system ships inside this package, so
# a failure here is a broken install, not a degraded environment. The old
# try/except existed to survive a missing OFF-REPO directory; there is no
# off-repo directory anymore, and a silent fallback would just re-create the
# second authority this file exists to remove (Law 3).
from synapse.panel.designsystem.tokens import (  # noqa: F401  — re-export
    # Colors — canonical palette
    SIGNAL, VOID, NEAR_BLACK, CARBON, GRAPHITE,
    SLATE, SILVER, BONE, WHITE,
    FIRE, GROW, WARN, ERROR,
    HOU_ORANGE, HOU_DARK, HOU_WIRE,
    # Interaction-state ramp
    SIGNAL_HOVER, SIGNAL_PRESS,
    PALETTE, color,
    # Typography
    FONT_MONO, FONT_MONO_FALLBACKS, FONT_MONO_CSS,
    FONT_SANS, FONT_SANS_FALLBACKS, FONT_SANS_CSS,
    SIZE_LABEL, SIZE_SMALL, SIZE_UI, SIZE_BODY, SIZE_TITLE, SIZE_HERO,
    # Spacing
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL,
    # Panel dimensions
    PANEL_MIN_WIDTH, PANEL_PREF_WIDTH, PANEL_MIN_HEIGHT,
    # The Aa font-scale ladder — see the FONT_SCALE block near the bottom
    FONT_SCALE_STEPS, FONT_SCALE_DEFAULT,
)
from synapse.panel.designsystem.tokens import (  # noqa: F401  — seeded roles
    TEXT_PRIMARY as _TEXT_PRIMARY,
    TEXT_SECONDARY as _TEXT_SECONDARY,
    HOVER_BG as _HOVER_BG,
    BORDER_STRONG as _BORDER_STRONG,
    FIELD_INSET as _FIELD_INSET,
)

# ``SIZE_HERO`` used to be assigned twice in this module: 44 in the off-repo
# fallback block, then 19 from the design system a few lines later. 19 was the
# live value in EVERY import path — the second assignment ran unconditionally,
# so the 44 could not survive to be read. Both assignments are gone now; the
# scale has one source and the ambiguity cannot recur.


# ── Icon specs — geometry only, no colour ───────────────────────────────
# Relocated from the off-repo design directory so the panel's icon geometry is
# version controlled. Rules preserved verbatim: dendrites are dropped at shelf
# size and below, and stroke weight INCREASES as size decreases, for legibility.
ICON_SIZES = {
    "hero": {
        "size": 120, "stroke": 5.0, "node_r": 8,
        "dendrite": True, "opacity_decay": [0.35, 0.25, 0.15],
    },
    "large": {
        "size": 64, "stroke": 3.0, "node_r": 3.5,
        "dendrite": True, "opacity_decay": [0.3, 0.2],
    },
    "medium": {
        "size": 48, "stroke": 2.5, "node_r": 3.0,
        "dendrite": True, "opacity_decay": [0.3],
    },
    "shelf": {
        "size": 32, "stroke": 4.0, "node_r": 4.5,
        "dendrite": False, "opacity_decay": [],
    },
    "small": {
        "size": 20, "stroke": 6.0, "node_r": 6.0,
        "dendrite": False, "opacity_decay": [],
    },
}

# ── Status states — DERIVED from the re-exported palette ────────────────
STATES = {
    "connected":    {"color": GROW,   "label": "Connected",    "icon": "synapse"},
    "executing":    {"color": FIRE,   "label": "Executing",    "icon": "execute"},
    "idle":         {"color": SIGNAL, "label": "Idle",         "icon": "synapse"},
    "warning":      {"color": WARN,   "label": "Warning",      "icon": "verify"},
    "error":        {"color": ERROR,  "label": "Error",        "icon": "synapse"},
    "disconnected": {"color": ERROR,  "label": "Disconnected", "icon": "synapse"},
}


# ── Panel-specific aliases (no design-system home) ──────────────────────
# Every one of these is an ALIAS or a DERIVED value. None is a declaration, so
# none creates a second authority — and each now tracks the host colour scheme
# through the seeded ramp it points at.
TEXT = _TEXT_PRIMARY        # primary text on the panel body
TEXT_DIM = _TEXT_SECONDARY  # dimmed / secondary text
HOVER = _HOVER_BG           # neutral button-hover surface
SCROLLBAR = _BORDER_STRONG  # scrollbar handle
SUCCESS_LED = GROW          # connection LED
ERROR_LED = ERROR           # disconnected LED

# Alias used in error display (spec references ERROR_COLOR)
ERROR_COLOR = ERROR


# ── HDA Mode State Colors ──────────────────────────────────────────────
STATE_DESCRIBE = SIGNAL     # accent — inviting input
STATE_BUILDING = FIRE       # orange — active processing
STATE_RESULT = GROW         # green — success/completion

# HDA Mode UI tokens
HDA_INPUT_BG = _FIELD_INSET       # editable-field well for text input
HDA_INPUT_BORDER = GRAPHITE
HDA_INPUT_FOCUS = SIGNAL + "40"   # SIGNAL at ~25% opacity
HDA_PROGRESS_BG = CARBON
HDA_PROGRESS_TRACK = GRAPHITE
HDA_STAGE_INACTIVE = SLATE
HDA_STAGE_ACTIVE = FIRE
HDA_STAGE_COMPLETE = GROW
HDA_RESULT_SUCCESS_BG = GROW + "10"   # very subtle green tint
HDA_RESULT_ERROR_BG = ERROR + "10"    # very subtle red tint

# Mode toggle tokens
MODE_ACTIVE_BG = SIGNAL + "15"
MODE_ACTIVE_BORDER = SIGNAL + "40"
MODE_INACTIVE_BG = "transparent"
MODE_INACTIVE_BORDER = GRAPHITE


# ── Chat Layout Tokens ───────────────────────────────────────────────
CHAT_BUBBLE_PADDING = 14       # Inner bubble padding (px)
CHAT_BUBBLE_RADIUS = 12        # Bubble corner radius (px)
CHAT_BUBBLE_MARGIN_Y = 2       # Between messages in same group (px)
CHAT_GROUP_MARGIN_Y = 16       # Between different-sender groups (px)
CHAT_BUBBLE_MAX_WIDTH_PCT = 85  # Bubble max width (percentage)
CHAT_INPUT_MIN_H = 44          # Minimum input height (px)
CHAT_INPUT_MAX_H = 300         # Maximum input height (~10 lines, px)
CHAT_TIMESTAMP_SIZE = 18       # Timestamp font size (px)
CHAT_TYPING_DOT_SIZE = 8       # Typing indicator dot diameter (px)

# ── Font size control (the Aa icon) — ONE ladder ────────────────────────
# This was the same two-authority defect in a non-colour dimension, and it had
# a live behavioural effect rather than a cosmetic one: the bridge declared
# [0.75, 1.0, 1.25, 1.5] while the design system declared
# (1.0, 1.15, 1.25, 1.4, 1.6), and synapse_panel.py stepped the second ladder
# while chat_panel.py stepped the first. One panel, two Aa controls, different
# stops. A colour-only audit would not have found it.
#
# MIN/MAX are DERIVED from the ladder rather than restated, so a future edit to
# the steps cannot leave the bounds behind.
FONT_SCALE_STEP = 0.125   # legacy increment; no consumer in panel/ today
FONT_SCALE_MIN = min(FONT_SCALE_STEPS)
FONT_SCALE_MAX = max(FONT_SCALE_STEPS)
