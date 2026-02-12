"""
Synapse Design System — Design Tokens

Encodes the Pentagram-style design system as importable Python constants.
Usable standalone (asset generation scripts) AND inside Houdini's Python
environment (panel UI). Zero external dependencies — stdlib only.

Usage:
    from tokens import SIGNAL, VOID, FONT_MONO, SPACE_MD, ICON_SIZES
    print(color(SIGNAL))  # {'hex': '#00D4FF', 'rgb_int': (0, 212, 255), ...}
"""

from typing import Dict, Tuple, Any


# ─────────────────────────────────────────────────────────────
# 1. COLOR PALETTE
# ─────────────────────────────────────────────────────────────

# Primary palette — aligned with Houdini 21 dark theme
SIGNAL      = "#00D4FF"   # Primary cyan — connectivity, intelligence
VOID        = "#252525"   # Recessed areas (activity log, inputs)
NEAR_BLACK  = "#3C3C3C"   # Panel background (matches Houdini Window)
CARBON      = "#333333"   # Surface/container (status bar, buttons)
GRAPHITE    = "#222222"   # Borders, dividers (darker edges)
SLATE       = "#888888"   # Tertiary text
SILVER      = "#AAAAAA"   # Secondary text
BONE        = "#CCCCCC"   # Primary text (dark bg)
WHITE       = "#F0F0F0"   # Bright text

# Functional (status states, NOT icons — icons stay monochromatic)
FIRE        = "#FF6B35"   # Execution active
GROW        = "#00E676"   # Success/verified
WARN        = "#FFAB00"   # Warning/caution
ERROR       = "#FF3D71"   # Error/disconnected

# Houdini-native (for context matching)
HOU_ORANGE  = "#D07020"
HOU_DARK    = "#2B2B2B"
HOU_WIRE    = "#6A9BC3"


def _hex_to_rgb_int(hex_str: str) -> Tuple[int, int, int]:
    """Convert '#RRGGBB' to (R, G, B) integers 0-255."""
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _hex_to_rgb_float(hex_str: str) -> Tuple[float, float, float]:
    """Convert '#RRGGBB' to (R, G, B) floats 0.0-1.0 (Houdini uses this)."""
    r, g, b = _hex_to_rgb_int(hex_str)
    return (r / 255.0, g / 255.0, b / 255.0)


def color(hex_str: str, alpha: float = 1.0) -> Dict[str, Any]:
    """
    Return a color in all useful formats.

    Args:
        hex_str: Color as '#RRGGBB'.
        alpha: Alpha value 0.0-1.0.

    Returns:
        dict with hex, rgb_int, rgb_float, rgba_float, qt_rgba
    """
    ri = _hex_to_rgb_int(hex_str)
    rf = _hex_to_rgb_float(hex_str)
    return {
        "hex": hex_str,
        "rgb_int": ri,
        "rgb_float": rf,
        "rgba_float": (rf[0], rf[1], rf[2], alpha),
        "qt_rgba": f"rgba({ri[0]}, {ri[1]}, {ri[2]}, {alpha})",
    }


# All palette colors for iteration
PALETTE = {
    "SIGNAL": SIGNAL, "VOID": VOID, "NEAR_BLACK": NEAR_BLACK,
    "CARBON": CARBON, "GRAPHITE": GRAPHITE, "SLATE": SLATE,
    "SILVER": SILVER, "BONE": BONE, "WHITE": WHITE,
    "FIRE": FIRE, "GROW": GROW, "WARN": WARN, "ERROR": ERROR,
    "HOU_ORANGE": HOU_ORANGE, "HOU_DARK": HOU_DARK, "HOU_WIRE": HOU_WIRE,
}


# ─────────────────────────────────────────────────────────────
# 2. TYPOGRAPHY
# ─────────────────────────────────────────────────────────────

FONT_MONO = "JetBrains Mono"
FONT_MONO_FALLBACKS = ("IBM Plex Mono", "Consolas", "monospace")
FONT_MONO_CSS = ", ".join(f'"{f}"' for f in (FONT_MONO,) + FONT_MONO_FALLBACKS)

FONT_SANS = "DM Sans"
FONT_SANS_FALLBACKS = ("Instrument Sans", "Segoe UI", "sans-serif")
FONT_SANS_CSS = ", ".join(f'"{f}"' for f in (FONT_SANS,) + FONT_SANS_FALLBACKS)

# Size scale (pixels, for Qt)
# Tuned to match Houdini 21 native UI defaults (~11-13px base)
SIZE_LABEL  = 11   # Tiny labels, numbers
SIZE_SMALL  = 11   # Status text, metadata
SIZE_UI     = 12   # Button labels, menu items
SIZE_BODY   = 13   # Chat messages, descriptions
SIZE_TITLE  = 16   # Section headers
SIZE_HERO   = 22   # Panel title


# ─────────────────────────────────────────────────────────────
# 3. SPACING
# ─────────────────────────────────────────────────────────────

SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 40


# ─────────────────────────────────────────────────────────────
# 4. ICON SPECS
# ─────────────────────────────────────────────────────────────

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
# Rule: At shelf size and below, dendrites are removed.
# Rule: Stroke weight INCREASES as size DECREASES (for legibility).
# Rule: At "small" size, Execute icon switches from stroked to filled.


# ─────────────────────────────────────────────────────────────
# 5. STATUS STATES
# ─────────────────────────────────────────────────────────────

STATES = {
    "connected":    {"color": GROW,   "label": "Connected",    "icon": "synapse"},
    "executing":    {"color": FIRE,   "label": "Executing",    "icon": "execute"},
    "idle":         {"color": SIGNAL, "label": "Idle",         "icon": "synapse"},
    "warning":      {"color": WARN,   "label": "Warning",      "icon": "verify"},
    "error":        {"color": ERROR,  "label": "Error",        "icon": "synapse"},
    "disconnected": {"color": ERROR,  "label": "Disconnected", "icon": "synapse"},
}


# ─────────────────────────────────────────────────────────────
# 6. PANEL DIMENSIONS
# ─────────────────────────────────────────────────────────────

PANEL_MIN_WIDTH   = 280
PANEL_PREF_WIDTH  = 320
PANEL_MIN_HEIGHT  = 400


# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  SYNAPSE DESIGN TOKENS")
    print("=" * 50)

    print("\n--- COLORS ---")
    for name, hex_val in PALETTE.items():
        c = color(hex_val)
        r, g, b = c["rgb_int"]
        print(f"  {name:12s}  {hex_val}  rgb({r:3d},{g:3d},{b:3d})  float({c['rgb_float'][0]:.2f},{c['rgb_float'][1]:.2f},{c['rgb_float'][2]:.2f})")

    print(f"\n--- TYPOGRAPHY ---")
    print(f"  Mono: {FONT_MONO_CSS}")
    print(f"  Sans: {FONT_SANS_CSS}")
    print(f"  Sizes: label={SIZE_LABEL} small={SIZE_SMALL} ui={SIZE_UI} body={SIZE_BODY} title={SIZE_TITLE} hero={SIZE_HERO}")

    print(f"\n--- SPACING ---")
    print(f"  XS={SPACE_XS}  SM={SPACE_SM}  MD={SPACE_MD}  LG={SPACE_LG}  XL={SPACE_XL}")

    print(f"\n--- ICON SPECS ---")
    for name, spec in ICON_SIZES.items():
        print(f"  {name:6s}: {spec['size']}px  stroke={spec['stroke']}  node_r={spec['node_r']}  dendrite={spec['dendrite']}")

    print(f"\n--- STATUS STATES ---")
    for state, info in STATES.items():
        print(f"  {state:14s}: {info['color']}  {info['label']}")

    print(f"\n--- PANEL ---")
    print(f"  min={PANEL_MIN_WIDTH}x{PANEL_MIN_HEIGHT}  pref_width={PANEL_PREF_WIDTH}")
    print()
