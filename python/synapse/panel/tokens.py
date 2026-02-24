"""Panel-local design tokens.

Re-exports the canonical design system tokens from ``~/.synapse/design/tokens.py``
and adds panel-specific tokens (HDA mode, hover variants, text aliases).

Import from HERE inside panel code — never from the design directory directly.
"""

import os as _os
import sys as _sys

# ── Bootstrap: import canonical tokens from ~/.synapse/design/ ──────────
_DESIGN_DIR = _os.path.join(_os.path.expanduser("~"), ".synapse", "design")
if _DESIGN_DIR not in _sys.path:
    _sys.path.insert(0, _DESIGN_DIR)

try:
    from tokens import (  # noqa: F401  — re-export
        # Colors
        SIGNAL, VOID, NEAR_BLACK, CARBON, GRAPHITE,
        SLATE, SILVER, BONE, WHITE,
        FIRE, GROW, WARN, ERROR,
        HOU_ORANGE, HOU_DARK, HOU_WIRE,
        PALETTE, color,
        # Typography
        FONT_MONO, FONT_MONO_FALLBACKS, FONT_MONO_CSS,
        FONT_SANS, FONT_SANS_FALLBACKS, FONT_SANS_CSS,
        SIZE_LABEL, SIZE_SMALL, SIZE_UI, SIZE_BODY, SIZE_TITLE, SIZE_HERO,
        # Spacing
        SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL,
        # Icons / States / Panel
        ICON_SIZES, STATES,
        PANEL_MIN_WIDTH, PANEL_PREF_WIDTH, PANEL_MIN_HEIGHT,
    )
    _HAS_DESIGN = True
except ImportError:
    # Fallback constants when design system is unavailable
    _HAS_DESIGN = False
    SIGNAL = "#00D4FF"
    VOID = "#252525"
    NEAR_BLACK = "#3A3A3A"
    CARBON = "#333333"
    GRAPHITE = "#222222"
    SLATE = "#888888"
    SILVER = "#AAAAAA"
    BONE = "#CCCCCC"
    WHITE = "#F0F0F0"
    FIRE = "#FF6B35"
    GROW = "#00E676"
    WARN = "#FFAB00"
    ERROR = "#FF3D71"
    FONT_MONO = "JetBrains Mono"
    FONT_SANS = "DM Sans"
    SIZE_LABEL = 22
    SIZE_SMALL = 22
    SIZE_UI = 24
    SIZE_BODY = 26
    SIZE_TITLE = 32
    SIZE_HERO = 44
    SPACE_XS = 4
    SPACE_SM = 8
    SPACE_MD = 16
    SPACE_LG = 24
    SPACE_XL = 40
    PANEL_MIN_WIDTH = 280
    PANEL_PREF_WIDTH = 320
    PANEL_MIN_HEIGHT = 400


# ── Panel-specific aliases (not in canonical tokens) ────────────────────
TEXT = "#E0E0E0"          # Primary text on dark (between BONE and WHITE)
TEXT_DIM = "#999999"      # Dimmed text (between SLATE and SILVER)
HOVER = "#484848"         # Button hover background
SIGNAL_HOVER = "#33DDFF"  # SIGNAL lightened for hover
SIGNAL_PRESS = "#00AADD"  # SIGNAL darkened for press
SCROLLBAR = "#444444"     # Scrollbar handle
SUCCESS_LED = GROW        # Connection LED (canonical, not the old #6BCB77)
ERROR_LED = ERROR         # Disconnected LED (canonical, not the old #FF6B6B)

# Alias used in error display (spec references ERROR_COLOR)
ERROR_COLOR = ERROR


# ── HDA Mode State Colors ──────────────────────────────────────────────
STATE_DESCRIBE = SIGNAL     # Cyan — inviting input
STATE_BUILDING = FIRE       # Orange — active processing
STATE_RESULT = GROW         # Green — success/completion

# HDA Mode UI tokens
HDA_INPUT_BG = "#141414"          # Slightly lighter than VOID for text input
HDA_INPUT_BORDER = GRAPHITE       # "#222222"
HDA_INPUT_FOCUS = SIGNAL + "40"   # SIGNAL at ~25% opacity
HDA_PROGRESS_BG = CARBON          # "#333333"
HDA_PROGRESS_TRACK = GRAPHITE     # "#222222"
HDA_STAGE_INACTIVE = SLATE        # "#888888"
HDA_STAGE_ACTIVE = FIRE           # "#FF6B35"
HDA_STAGE_COMPLETE = GROW         # "#00E676"
HDA_RESULT_SUCCESS_BG = GROW + "10"   # Very subtle green tint
HDA_RESULT_ERROR_BG = ERROR + "10"    # Very subtle red tint

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
CHAT_INPUT_MAX_H = 160         # Maximum input height (~6 lines, px)
CHAT_TIMESTAMP_SIZE = 18       # Timestamp font size (px)
CHAT_TYPING_DOT_SIZE = 8       # Typing indicator dot diameter (px)

# Font size control (user-adjustable via Aa icon)
FONT_SCALE_MIN = 0.75
FONT_SCALE_MAX = 1.5
FONT_SCALE_DEFAULT = 1.0
FONT_SCALE_STEP = 0.125
FONT_SCALE_STEPS = [0.75, 1.0, 1.25, 1.5]
