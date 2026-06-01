"""SYNAPSE design tokens — the single vendored source of truth.

Reconciles the three divergent token sources the redesign audit found
(design/tokens.py @ 9-20px true-black, ~/.synapse/design @ Houdini-grey,
panel/tokens.py fallback @ 22-44px) into ONE table that ships on the package
path. Stdlib-only; usable standalone and inside Houdini.

What's new vs the canonical design/tokens.py (which this preserves for
back-compat): explicit SURFACE-ELEVATION roles (so VOID/CARBON/GRAPHITE stop
being used interchangeably), a complete INTERACTION-STATE ramp
(hover/press/disabled/focus — formalizing the ad-hoc #33DDFF/#484848), TYPE
ROLES (not just sizes), MOTION tokens, and one STATUS grammar.
"""

from typing import Dict, Tuple, Any

# ─────────────────────────────────────────────────────────────
# 1. COLOR — canonical palette (preserved verbatim for back-compat)
# ─────────────────────────────────────────────────────────────

SIGNAL      = "#00D4FF"   # primary accent — connectivity, intelligence
VOID        = "#0A0A0A"   # deepest ground
NEAR_BLACK  = "#111111"   # panel background
CARBON      = "#1A1A1A"   # surface / container
GRAPHITE    = "#2A2A2A"   # borders, dividers
SLATE       = "#555555"   # tertiary / disabled text
SILVER      = "#999999"   # secondary text
BONE        = "#CCCCCC"   # primary text on dark
WHITE       = "#F0F0F0"   # bright text

FIRE        = "#FF6B35"   # execution active
GROW        = "#00E676"   # success / verified
WARN        = "#FFAB00"   # warning / caution
ERROR       = "#FF3D71"   # error / disconnected

HOU_ORANGE  = "#D07020"
HOU_DARK    = "#2B2B2B"
HOU_WIRE    = "#6A9BC3"

# ─────────────────────────────────────────────────────────────
# 2. SURFACE ELEVATION — semantic roles, tuned to Houdini 21's NATIVE greys
# Verified against $HFS/houdini/config/UIDark.hcs so the panel sits IN Houdini's
# UI instead of reading as a black "hole". Each step is one elevation up.
# ─────────────────────────────────────────────────────────────

GROUND   = "#262626"   # input wells / deepest inset (Houdini PaneBorder, GREY .15)
PANEL    = "#2E2E2E"   # the panel body — Houdini's pane grey (DRKBASE, GREY .179)
SURFACE  = "#3A3A3A"   # cards, drawers, containers (Houdini BackColor, GREY .229)
RAISED   = "#565656"   # raised / hover surface (Houdini ButtonGradHi, GREY .338)
BORDER   = "#262626"   # hairline divider (Houdini PaneBorder)
BORDER_STRONG = "#4C4C4C"  # separator (Houdini Separator, GREY .30)

ELEVATION = {  # role -> bg color, for components to read by name
    "ground": GROUND, "panel": PANEL, "surface": SURFACE,
    "raised": RAISED, "border": BORDER,
}

# ─────────────────────────────────────────────────────────────
# 3. TEXT roles
# ─────────────────────────────────────────────────────────────

TEXT_PRIMARY   = "#CCCCCC"  # body (Houdini TEXT, GREY .8)
TEXT_SECONDARY = "#808080"  # secondary (Houdini SecondaryText, GREY .5)
TEXT_TERTIARY  = "#6E6E6E"  # captions / hints
TEXT_BRIGHT    = "#E6E6E6"  # emphasis / headings (Houdini highlighted text)
TEXT_ACCENT    = SIGNAL     # links, accent labels (NOT body — see WCAG note)
TEXT_DISABLED  = "#6A6A6A"
TEXT_ON_ACCENT = "#0A1014"  # text drawn on a SIGNAL fill (dark on cyan = AA-safe)

# WCAG note: SIGNAL (#00D4FF) on PANEL passes AA for >=14px / bold, but FAILS
# for small body text. Use TEXT_ACCENT for labels/links/icons only; never for
# running body copy. Body uses TEXT_PRIMARY.

# ─────────────────────────────────────────────────────────────
# 4. INTERACTION-STATE ramp (formalized, not ad-hoc)
# ─────────────────────────────────────────────────────────────

SIGNAL_HOVER = "#33DDFF"   # accent hover
SIGNAL_PRESS = "#00AADD"   # accent press
SIGNAL_TINT  = "rgba(0, 212, 255, 0.12)"   # subtle accent wash (focus/selection)
SIGNAL_TINT_STRONG = "rgba(0, 212, 255, 0.22)"
HOVER_WASH = "rgba(255, 255, 255, 0.09)"   # native Houdini flat-toolbar hover (white wash)

HOVER_BG   = RAISED        # neutral hover surface
PRESS_BG   = "#202022"     # neutral press surface
FOCUS_RING = SIGNAL        # focus outline color
DISABLED_BG = SURFACE

STATE_TINTS = {  # status-hue washes for cards/badges
    "fire":  "rgba(255, 107, 53, 0.14)",
    "grow":  "rgba(0, 230, 118, 0.14)",
    "warn":  "rgba(255, 171, 0, 0.14)",
    "error": "rgba(255, 61, 113, 0.14)",
    "signal": SIGNAL_TINT,
}

# ─────────────────────────────────────────────────────────────
# 5. TYPOGRAPHY — families, sizes, and ROLES
# ─────────────────────────────────────────────────────────────

FONT_MONO = "JetBrains Mono"
FONT_MONO_FALLBACKS = ("IBM Plex Mono", "Consolas", "monospace")
FONT_MONO_CSS = ", ".join(f'"{f}"' for f in (FONT_MONO,) + FONT_MONO_FALLBACKS)

FONT_SANS = "DM Sans"
FONT_SANS_FALLBACKS = ("Instrument Sans", "Segoe UI", "sans-serif")
FONT_SANS_CSS = ", ".join(f'"{f}"' for f in (FONT_SANS,) + FONT_SANS_FALLBACKS)

# px scale (Qt). Calibrated to the panel's true rendering DPI (the canonical
# 9-20 scale, NOT the bug-prone 22-44 fallback).
SIZE_MICRO  = 9    # tiny labels / numbers
SIZE_SMALL  = 10   # captions, metadata
SIZE_UI     = 11   # button labels, menu items
SIZE_BODY   = 12   # chat messages, descriptions
SIZE_TITLE  = 14   # section headers
SIZE_HERO   = 20   # panel title

# Back-compat alias (design/tokens.py name)
SIZE_LABEL = SIZE_MICRO

# Roles: (family_css, size_px, weight, letter_spacing_px) — components read these.
TYPE_ROLES: Dict[str, Tuple[str, int, int, float]] = {
    "display": (FONT_SANS_CSS, SIZE_HERO,  600, 0.5),
    "title":   (FONT_MONO_CSS, SIZE_TITLE, 600, 1.0),
    "body":    (FONT_SANS_CSS, SIZE_BODY,  400, 0.0),
    "label":   (FONT_MONO_CSS, SIZE_UI,    500, 0.5),
    "code":    (FONT_MONO_CSS, SIZE_BODY,  400, 0.0),
    "caption": (FONT_SANS_CSS, SIZE_SMALL, 400, 0.0),
    "status":  (FONT_MONO_CSS, SIZE_SMALL, 500, 0.5),
}

# One user font-scale drives BOTH chrome QSS and chat HTML (today only chat).
FONT_SCALE_STEPS = (0.85, 1.0, 1.15, 1.3)
FONT_SCALE_DEFAULT = 1.0

# ─────────────────────────────────────────────────────────────
# 6. SPACING / RADIUS — load-bearing scale
# ─────────────────────────────────────────────────────────────

SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 40

RADIUS_SM = 4
RADIUS_MD = 8
RADIUS_LG = 12
RADIUS_PILL = 14

# ─────────────────────────────────────────────────────────────
# 7. MOTION — tokenized (Qt QSS has no transition; QPropertyAnimation uses these)
# ─────────────────────────────────────────────────────────────

DUR_FAST = 120   # ms — hover/press
DUR_BASE = 200   # ms — page fades
DUR_SLOW = 320   # ms — drawer open, gate flash
EASE = "OutCubic"  # resolved to QEasingCurve.Type.OutCubic by motion.py

# ─────────────────────────────────────────────────────────────
# 8. STATUS grammar — ONE vocabulary (replaces Connected/Ready/Fidelity 1.0)
# kind -> (color, dot_label, plain_phrase)
# ─────────────────────────────────────────────────────────────

STATUS = {
    "connected":    (GROW,   "connected",    "Ready"),
    "working":      (FIRE,   "working",      "Working on it"),
    "idle":         (SIGNAL, "idle",         "Standing by"),
    "warning":      (WARN,   "warning",      "Worth a look"),
    "error":        (ERROR,  "error",        "We hit a snag"),
    "disconnected": (SLATE,  "offline",      "Not connected"),
}

# Bridge gate levels -> (color, plain label, default timeout seconds)
GATE_LEVELS = {
    "INFORM":   (SIGNAL, "Heads up",      0),
    "REVIEW":   (WARN,   "Quick review",  0),
    "APPROVE":  (FIRE,   "Approve?",      120),
    "CRITICAL": (ERROR,  "Confirm",       300),
}

# ─────────────────────────────────────────────────────────────
# 9. PANEL dimensions
# ─────────────────────────────────────────────────────────────

PANEL_MIN_WIDTH  = 280
PANEL_PREF_WIDTH = 340
PANEL_MIN_HEIGHT = 400

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _hex_to_rgb_int(hex_str: str) -> Tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def color(hex_str: str, alpha: float = 1.0) -> Dict[str, Any]:
    """Return a color in hex / rgb_int / rgb_float / qt_rgba forms."""
    ri = _hex_to_rgb_int(hex_str)
    rf = tuple(c / 255.0 for c in ri)
    return {
        "hex": hex_str,
        "rgb_int": ri,
        "rgb_float": rf,
        "rgba_float": (rf[0], rf[1], rf[2], alpha),
        "qt_rgba": f"rgba({ri[0]}, {ri[1]}, {ri[2]}, {alpha})",
    }


def rgba(hex_str: str, alpha: float) -> str:
    """'#RRGGBB' + alpha -> 'rgba(r, g, b, a)' for QSS."""
    return color(hex_str, alpha)["qt_rgba"]


def scaled(size_px: int, scale: float = FONT_SCALE_DEFAULT) -> int:
    """Apply the user font-scale to a px size (min 8px)."""
    return max(8, round(size_px * scale))


PALETTE = {
    "SIGNAL": SIGNAL, "VOID": VOID, "NEAR_BLACK": NEAR_BLACK, "CARBON": CARBON,
    "GRAPHITE": GRAPHITE, "SLATE": SLATE, "SILVER": SILVER, "BONE": BONE,
    "WHITE": WHITE, "FIRE": FIRE, "GROW": GROW, "WARN": WARN, "ERROR": ERROR,
    "HOU_ORANGE": HOU_ORANGE, "HOU_DARK": HOU_DARK, "HOU_WIRE": HOU_WIRE,
    "BORDER": BORDER, "BORDER_STRONG": BORDER_STRONG,
}


if __name__ == "__main__":
    print("SYNAPSE design tokens (vendored, single source)")
    print(f"  elevation: {ELEVATION}")
    print(f"  type roles: {list(TYPE_ROLES)}")
    print(f"  status: {list(STATUS)}  gates: {list(GATE_LEVELS)}")
    print(f"  space: {SPACE_XS}/{SPACE_SM}/{SPACE_MD}/{SPACE_LG}/{SPACE_XL}"
          f"  motion: {DUR_FAST}/{DUR_BASE}/{DUR_SLOW}ms {EASE}")
