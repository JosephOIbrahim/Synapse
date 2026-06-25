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

import os
from typing import Dict, Tuple, Any

# ─────────────────────────────────────────────────────────────
# 1. COLOR — canonical palette (preserved verbatim for back-compat)
# ─────────────────────────────────────────────────────────────

SIGNAL      = "#8FB3D9"   # primary accent — muted light blue (SYNAPSE signature)
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
# HOST-THEME SEEDING (contract C1: theme-seed-tokens)
# Surface roles are SEEDED from the live Houdini color scheme at construction so
# the panel tracks the artist's light/dark theme; the hardcoded hexes are the
# HEADLESS fallback (not the source of truth — that inversion was the bug). Pure
# stdlib; any failure degrades cleanly to the fallback, so the dark scheme stays
# byte-identical in tests/CI/headless and only a live LIGHT host flips the panel.
# ─────────────────────────────────────────────────────────────

def _clamp8(v):
    return 0 if v < 0 else (255 if v > 255 else int(round(v)))

def _hexrgb(r, g, b):
    return "#%02X%02X%02X" % (_clamp8(r), _clamp8(g), _clamp8(b))

def _rgb_lum(r, g, b):
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0

# --- WCAG-correct luminance + a contrast-solving grey picker -----------------
# The 85%-dim ramp passed the headless contrast floor but the panel RESEEDS its
# surfaces from the host pane grey at construction; a lighter host then dropped
# body text below AA while the static audit (which reads the fallback) stayed
# green. So the text ramp is no longer a fixed table — it is SOLVED from the
# seeded surface to hit a target contrast on ANY host, light or dark. Gated by
# audit_panel.py's seeded-contrast sweep (A3).

def _srgb_lin(c8):
    c = c8 / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

def _wcag_lum(hex_str):
    h = hex_str.lstrip("#")
    return (0.2126 * _srgb_lin(int(h[0:2], 16))
            + 0.7152 * _srgb_lin(int(h[2:4], 16))
            + 0.0722 * _srgb_lin(int(h[4:6], 16)))

def _contrast(fg_hex, bg_hex):
    a, b = _wcag_lum(fg_hex), _wcag_lum(bg_hex)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)

def _lin_to_ch(L):
    """Inverse sRGB: a target relative luminance L (grey) → an 8-bit channel."""
    L = 0.0 if L < 0 else (1.0 if L > 1 else L)
    c = 12.92 * L if L <= 0.0031308 else 1.055 * (L ** (1 / 2.4)) - 0.055
    return _clamp8(c * 255)

def _grey_for_contrast(bg_hex, ratio, lighter):
    """The neutral grey hex that yields ``ratio`` WCAG contrast against
    ``bg_hex`` — ``lighter`` picks the text-lighter-than-bg solution (dark host)
    vs the darker solution (light host). Clamps into gamut."""
    lb = _wcag_lum(bg_hex)
    lt = ratio * (lb + 0.05) - 0.05 if lighter else (lb + 0.05) / ratio - 0.05
    v = _lin_to_ch(lt)
    return "#%02X%02X%02X" % (v, v, v)

def _host_surface_rgb():
    """The host pane-background as (r, g, b), or None when headless/unavailable.
    ADAPT: 'PaneEmptyApp' is a placeholder color-scheme role — tune it to the
    exact .hcs entry that reads your build's pane grey (CRUCIBLE can cross-check
    hou.qt.color() live). Any failure -> None -> the hardcoded fallback below."""
    try:
        import hou
        c = hou.qt.color("PaneEmptyApp")
    except Exception:
        return None
    if c is None:
        return None
    try:
        return (int(c.red()), int(c.green()), int(c.blue()))
    except Exception:
        try:
            r, g, b = c.getRgb()[:3]
            return (int(r), int(g), int(b))
        except Exception:
            return None

# Houdini-native dark pane grey (verified vs UIDark.hcs) — the HEADLESS surface
# anchor. The text ramp is no longer a fixed table; it is solved from these by
# _derive_palette so headless and live use the identical contrast-aware path.
_FALLBACK_RGB = (46, 46, 46)   # #2E2E2E — the host pane grey when no scheme reads

# Contrast targets for the solved text ramp. body=primary is held a hair above
# AA (4.5); bright is AAA-crisp; tertiary stays above the dark-DCC pragmatic
# line; disabled is intentionally low (it reads as inactive, not as body).
_TEXT_CONTRAST = {
    "primary": 7.0, "secondary": 4.6, "tertiary": 3.3, "bright": 9.0,
    "disabled": 2.0,
}

def _derive_palette(r, g, b):
    """Pure (surface, text) from a host pane (r, g, b) — no `hou`, no globals.

    Surfaces are elevation offsets from the base (holds for a light OR dark
    host). The text ramp is SOLVED so each role hits its target contrast against
    the surface it can land on: light text on a dark host, dark text on a light
    host. Because contrast is guaranteed against the *worst-case* surface the
    text sits on, AA holds at every host grey — that's the seed-blind gap the
    A3 sweep gates. Exposed (underscore) so the audit can sweep it directly."""
    def step(d):
        return _hexrgb(r + d, g + d, b + d)
    surface = {
        "ground": step(-8), "field_inset": step(-16), "panel": _hexrgb(r, g, b),
        "surface": step(12), "raised": step(40), "border": step(-8),
        "border_strong": step(30),
    }
    # Text lands on ground / panel / surface. Choose the text DIRECTION (light
    # vs dark) that MAXIMIZES the achievable contrast on those surfaces — not a
    # fixed lum>0.5 rule. The old rule chose light text on a mid-grey host where
    # dark text has far more contrast, dropping body below AA in the ~107-127
    # band; picking by max-min-contrast fixes that and is correct for dark AND
    # light hosts. (A true mid-grey background can't reach AA 4.5 in EITHER
    # direction once the elevation spread is included — a WCAG hard limit, not a
    # bug; the audit gates the realistic host range at AA and the pragmatic floor
    # everywhere.)
    lands = [surface[k] for k in ("ground", "panel", "surface")]
    lightest = max(lands, key=_wcag_lum)
    darkest = min(lands, key=_wcag_lum)
    lighter = min(_contrast("#FFFFFF", s) for s in lands) >= min(_contrast("#000000", s) for s in lands)
    anchor = lightest if lighter else darkest
    text = {role: _grey_for_contrast(anchor, ratio, lighter=lighter)
            for role, ratio in _TEXT_CONTRAST.items()}
    return surface, text

def _seed_palette():
    """(surface, text) from the live host pane color, or the headless fallback —
    both routed through the one contrast-aware _derive_palette path."""
    return _derive_palette(*(_host_surface_rgb() or _FALLBACK_RGB))

_SURF, _TXT = _seed_palette()

# ─────────────────────────────────────────────────────────────
# 2. SURFACE ELEVATION — semantic roles, tuned to Houdini 21's NATIVE greys
# Verified against $HFS/houdini/config/UIDark.hcs so the panel sits IN Houdini's
# UI instead of reading as a black "hole". Each step is one elevation up.
# ─────────────────────────────────────────────────────────────

# Seeded from the host pane grey (see HOST-THEME SEEDING above); these resolve
# to the hardcoded Houdini-native greys headless, or to host-derived greys when
# a live scheme is read — so the panel sits IN Houdini's UI on dark OR light.
GROUND        = _SURF["ground"]         # input wells / deepest inset
FIELD_INSET   = _SURF["field_inset"]    # darker editable-field well for inputs
PANEL         = _SURF["panel"]          # the panel body — host pane grey
SURFACE       = _SURF["surface"]        # cards, drawers, containers
RAISED        = _SURF["raised"]         # raised / hover surface
BORDER        = _SURF["border"]         # hairline divider
BORDER_STRONG = _SURF["border_strong"]  # separator

ELEVATION = {  # role -> bg color, for components to read by name
    "ground": GROUND, "panel": PANEL, "surface": SURFACE,
    "raised": RAISED, "border": BORDER,
}

# ─────────────────────────────────────────────────────────────
# 3. TEXT roles
# ─────────────────────────────────────────────────────────────

# Neutral text ramp dimmed to 85% brightness (artist request) — every grey
# multiplied ×0.85: CC→AD, 80→6D, 6E→5E, E6→C4, 6A→5A. Brand/semantic accents
# (SIGNAL/WARM/status) are left at full strength — "fonts" = the readable ramp.
# Seeded ramp: the 85%-dimmed greys headless, or a contrast-flipped DARK ramp
# when the host surface is light (a surface-only seed would be dark-on-light).
TEXT_PRIMARY   = _TXT["primary"]    # body
TEXT_SECONDARY = _TXT["secondary"]  # secondary
TEXT_TERTIARY  = _TXT["tertiary"]   # captions / hints
TEXT_BRIGHT    = _TXT["bright"]     # emphasis / headings
TEXT_ACCENT    = SIGNAL     # links, accent labels (NOT body — see WCAG note)
TEXT_DISABLED  = _TXT["disabled"]
TEXT_ON_ACCENT = "#13212C"  # text on a SIGNAL fill (dark navy on light blue = AA-safe)

# WCAG note: SIGNAL (#8FB3D9) on PANEL passes AA for >=14px / bold, but FAILS
# for small body text. Use TEXT_ACCENT for labels/links/icons only; never for
# running body copy. Body uses TEXT_PRIMARY.

# ─────────────────────────────────────────────────────────────
# 4. INTERACTION-STATE ramp (formalized, not ad-hoc)
# ─────────────────────────────────────────────────────────────

SIGNAL_HOVER = "#A9C7E6"   # accent hover (lighter)
SIGNAL_PRESS = "#7398BE"   # accent press (deeper)
SIGNAL_TINT  = "rgba(143, 179, 217, 0.12)"   # subtle accent wash (focus/selection)
SIGNAL_TINT_STRONG = "rgba(143, 179, 217, 0.22)"
HOVER_WASH = "rgba(255, 255, 255, 0.09)"   # native Houdini flat-toolbar hover (white wash)

# Warm "human" accent — Cohere's 'Bittersweet' coral. The dual-accent counterpart
# to the cool SIGNAL: used for the agent's human/active moments (the thinking toy,
# warm highlights), NOT for connectivity/links (those stay SIGNAL — distinct from
# Houdini's own orange UI). Pentagram Cohere: warmth keeps the AI from reading clinical.
WARM        = "#FF7759"
WARM_HOVER  = "#FF8E72"
WARM_PRESS  = "#E5634A"
WARM_TINT   = "rgba(255, 119, 89, 0.14)"

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

# v9 type pass: the bundled families (designsystem/fonts/, loaded at panel init
# via QFontDatabase — see fontload.py). Fallbacks keep the panel legible if the
# bundle ever fails to register (the build-mismatch flag is raised then).
FONT_MONO = "Space Mono"
FONT_MONO_FALLBACKS = ("JetBrains Mono", "Consolas", "monospace")
FONT_MONO_CSS = ", ".join(f'"{f}"' for f in (FONT_MONO,) + FONT_MONO_FALLBACKS)

FONT_SANS = "Space Grotesk"
FONT_SANS_FALLBACKS = ("DM Sans", "Segoe UI", "sans-serif")
FONT_SANS_CSS = ", ".join(f'"{f}"' for f in (FONT_SANS,) + FONT_SANS_FALLBACKS)

# px scale (Qt) — matched to Houdini's native UI font (QApplication default
# 9pt ≈ 12px, verified on H21.0.671/.729) so the panel sits IN Houdini's UI
# instead of over it, and its text stops cropping the buttons/labels. The
# Pentagram character is preserved by TYPE_ROLES + TRACKING_EM below (families,
# tracking, hierarchy); only the absolute sizes shrink. The Aa control
# (FONT_SCALE_STEPS) scales the whole set up for the artist.
SIZE_MICRO  = 10   # tiny labels / numbers
SIZE_SMALL  = 11   # captions, metadata
SIZE_UI     = 12   # buttons, pills, menu items, labels — Houdini-native; scalable via Aa
SIZE_BODY   = 12   # chat body — Houdini-native default (9pt ≈ 12px)
SIZE_TITLE  = 15   # section headers — gentle step above native
SIZE_HERO   = 19   # panel title — present, not shouting

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

# v9 tracking map — em per role. Tracking lives on QFont (AbsoluteSpacing =
# em × px), NEVER in QSS (Qt QSS has no letter-spacing). fontload.tracked_font()
# reads this. Roles → where they apply:
#   BRAND    +0.16  wordmark
#   LABEL    +0.15  tabs, section + action labels
#   LABEL_SM +0.12  credit keys, tiny labels
#   DATA     +0.03  author, meter, paths, cookline, chip, mini
#   DISPLAY  -0.015 verdict
#   BODY      0     conversation, prompt
# Dialed near-flat to match Houdini's native UI (which doesn't letter-space its
# labels). BRAND keeps a hair of tracking (the wordmark's only remaining flourish
# — and tracked_font needs it non-zero to apply AbsoluteSpacing); DISPLAY stays
# slightly tight. Everything else is flat.
TRACKING_EM: Dict[str, float] = {
    "BRAND": 0.02, "LABEL": 0.0, "LABEL_SM": 0.0,
    "DATA": 0.0, "DISPLAY": -0.01, "BODY": 0.0,
}


def tracking_px(role: str, px: float) -> float:
    """AbsoluteSpacing pixels for a role at a given px size (em × px). Pure —
    the QFont application lives in fontload.tracked_font()."""
    return TRACKING_EM.get(role, 0.0) * px


# One user font-scale drives BOTH chrome QSS and chat HTML (today only chat).
# Startup default bumped to 1.25 — at native Houdini 12px the panel read too
# small to be comfortable; 1.25 lifts body to ~15px (Aa cycles the rest).
FONT_SCALE_STEPS = (1.0, 1.15, 1.25, 1.4, 1.6)
FONT_SCALE_DEFAULT = 1.25

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

# Reduced-motion (v9 Spike 7). When on, continuous animations (the mark spin,
# the cook-preview pulse, the thinking toy) don't run and fades jump to their
# end. Explicit override wins; otherwise the SYNAPSE_REDUCED_MOTION env var.
_REDUCED_MOTION = None  # None → consult env; True/False → explicit override


def set_reduced_motion(on) -> None:
    """Force reduced-motion on/off, or pass None to defer to the env var."""
    global _REDUCED_MOTION
    _REDUCED_MOTION = None if on is None else bool(on)


def reduced_motion() -> bool:
    """True when motion should be minimized (accessibility / low-power)."""
    if _REDUCED_MOTION is not None:
        return _REDUCED_MOTION
    return os.environ.get("SYNAPSE_REDUCED_MOTION", "").strip().lower() in (
        "1", "true", "yes", "on")

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
    # stdout.write, not print() — the project bans bare print() in source
    # (tests/test_v5_features.py::test_no_print_in_source enforces it).
    import sys as _sys
    _sys.stdout.write("SYNAPSE design tokens (vendored, single source)\n")
    _sys.stdout.write(f"  elevation: {ELEVATION}\n")
    _sys.stdout.write(f"  type roles: {list(TYPE_ROLES)}\n")
    _sys.stdout.write(f"  status: {list(STATUS)}  gates: {list(GATE_LEVELS)}\n")
    _sys.stdout.write(
        f"  space: {SPACE_XS}/{SPACE_SM}/{SPACE_MD}/{SPACE_LG}/{SPACE_XL}"
        f"  motion: {DUR_FAST}/{DUR_BASE}/{DUR_SLOW}ms {EASE}\n"
    )
