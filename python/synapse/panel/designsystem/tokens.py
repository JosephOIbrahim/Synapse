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

# The ONE seam to the live host theme. Historically the Houdini Color Scheme
# read (the hou Qt color accessor -> the .hcs / UIDark.hcs greys) lived inline
# here; it now lives behind theme_source so an H22 QML Theme-Editor backend can
# be swapped in without touching this table. The 'hcs' backend is active +
# byte-identical to the former inline read.
from . import theme_source

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

# The host color-scheme read (the hou Qt color accessor -> the .hcs / UIDark.hcs
# greys) now lives in theme_source.host_surface_rgb() — see the import note at
# the top of this module. Nothing in tokens.py reads the host theme directly
# anymore; the single seam owns it so an H22 QML backend can replace it.

# Houdini-native dark pane grey (verified vs UIDark.hcs) — the HEADLESS surface
# anchor. The text ramp is no longer a fixed table; it is solved from these by
# _derive_palette so headless and live use the identical contrast-aware path.
# v9: retuned to the ratified comp's --panel (#2A2A2A) — a seeded fallback
# input, never a scattered literal (the comp hexes land HERE only).
_FALLBACK_RGB = (42, 42, 42)   # #2A2A2A — the host pane grey when no scheme reads

# Contrast targets for the solved text ramp, against the WORST-CASE landing
# surface (see _derive_palette's anchor). body=primary is held a hair above AA
# (4.5); bright is AAA-crisp.
#
# D3 (READABILITY.md 2026-09-15, recomputed here): tertiary shipped at 3.3 --
# 3.32:1 on SURFACE -- and tertiary is ACTIVE caption/hint text, so the 4.5 AA
# floor governs it. It now sits AT the floor, measured on the headless seed:
#   tertiary  #868686 -> #9E9E9E   panel 3.94 -> 5.36 - surface 3.32 -> 4.51
#
# D3b (2026-09-15): D3 also raised disabled 2.0 -> 4.5, on the stated premise
# that "shipping a role below AA was not an option". For this one role the
# premise was wrong. WCAG 2.1 SC 1.4.3 exempts text that is part of an INACTIVE
# user interface component ("Incidental"), so the raise bought no conformance,
# and it cost the entire signal: at 4.5 the solver returns the SAME ink for
# disabled and tertiary at EVERY host grey (swept 0..255 step 8: 32 of 32
# rows). Four live rules carry "disabled"/"inactive" in ink alone with no fill
# behind them, and all four became literal no-ops --
#   QPushButton#DsPill:disabled          vs its rest ink   1.000:1
#   QPushButton#DsAuthor[liveness="off"] vs its rest ink   1.025:1
#   QPushButton#DsFooterLink:disabled    vs its rest ink   1.025:1
#   network_trace's trivial-step left rule vs the normal one  1.000:1
# -- so the mitigation the old note claimed here ("carried by DISABLED_BG, not
# by illegible ink") was false for precisely the sites that needed it.
#
# disabled is therefore back at 2.0, with the exemption stated instead of a
# floor violation claimed. Measured on the headless seed: 2.01:1 on
# DISABLED_BG, and -- the number that actually matters -- 2.24:1 away from
# tertiary. Swept over EVERY host grey 0..255 (not the step-8 grid the report
# used, which skips the low point): the disabled-to-tertiary step never falls
# below 1.94:1, at host grey 117.
#
# The corollary, and why this is not a plain revert: the ink is exempt only
# where it paints something INACTIVE. Two rules were spending it as a "quieter
# than tertiary" rung on ACTIVE labels (DsMeter / DsKHint at prominence=quiet);
# those now name TEXT_TERTIARY, which is what every other quiet rung in the
# sheet already names and is the exact grey they have rendered since D3 -- so
# nothing moves on screen and D3's AA win for them is kept.
#
# What remains true from D3, and is still a design call for a later pass: with
# secondary frozen at 4.6 and the floor at 4.5, the quiet ACTIVE end has no
# room left. tertiary #9E9E9E and secondary #A0A0A0 are two rungs that value
# can barely separate; form (tracking / caps / the mono family) has to carry
# any further step down. That is a separate problem from this one, and it is
# not solved by spending the inactive ink on active text.
_TEXT_CONTRAST = {
    "primary": 7.0, "secondary": 4.6, "tertiary": 4.5, "bright": 9.0,
    "disabled": 2.0,          # inactive-only: SC 1.4.3 exempt, see D3b above
}

def _derive_palette(r, g, b):
    """Pure (surface, text) from a host pane (r, g, b) — no `hou`, no globals.

    Surfaces are elevation offsets from the base (holds for a light OR dark
    host). The text ramp is SOLVED so each role hits its target contrast against
    the surface it can land on: light text on a dark host, dark text on a light
    host. Because contrast is guaranteed against the *worst-case* surface the
    text sits on, AA holds at every host grey for every ACTIVE role — that's
    the seed-blind gap the A3 sweep gates. `disabled` is the one INACTIVE
    role and is deliberately below the floor (SC 1.4.3); what is gated for
    it instead is that it stays a visible step away from tertiary.
    Exposed (underscore) so the audit can sweep it directly."""
    def step(d):
        return _hexrgb(r + d, g + d, b + d)
    # v9 elevation offsets, retuned to the ratified comp (relative to --panel):
    # --ground −11 · field inset = ground · --raised +8 · --line +12 (borders
    # flip lighter-than-panel) · --hair +6 (rail rule / acts rule) · strong +18.
    surface = {
        "ground": step(-11), "field_inset": step(-11), "panel": _hexrgb(r, g, b),
        "surface": step(12), "raised": step(8), "border": step(12),
        "border_strong": step(18), "hair": step(6),
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
    both routed through the one contrast-aware _derive_palette path. The host
    read goes through theme_source (the single .hcs / theme seam)."""
    return _derive_palette(*(theme_source.host_surface_rgb() or _FALLBACK_RGB))

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
HAIR          = _SURF["hair"]           # quietest rule — rail bottom, acts top

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
# D2 (READABILITY.md 2026-09-15, recomputed here): the old "#0F1F2B ... AA-safe"
# was true of the fill this ink is NEVER filled with. On SIGNAL #8FB3D9 (the
# :hover fill) it measured 7.69:1; on SIGNAL_DEEP #627A93 -- the fill SEND and
# every hero button actually rest on -- it measured 3.78:1, under the 4.5 AA
# floor for text this size. Options computed against SIGNAL_DEEP:
#   fill  #627A93 -> #6D87A3 (lighten to 4.51)  -- moves the whole button face
#   ink   #0F1F2B -> #04090C (4.5014)           -- clears the bar by 0.0014
#   ink   #0F1F2B -> #000000 (4.7245)           -- CHOSEN
# The ink is the smaller visual delta (thin strokes, not the button face), and
# black clears with margin instead of sitting on the line. It cannot introduce a
# hue -- it removes 28 points of chroma from an ink the restraint instrument was
# counting as chromatic. Every other TEXT_ON_ACCENT fill only gains:
#   SIGNAL 7.69 -> 9.62 · SIGNAL_PRESS 5.57 -> 6.96 · WARM 6.42 -> 8.03
TEXT_ON_ACCENT = "#000000"  # knockout ink on a filled action (4.72:1 on SIGNAL_DEEP)


def _warm_bias(hex_str, amount=12):
    """Warm a solved neutral grey without moving its luminance meaningfully.

    R is pushed up and B down by the same amount; the WCAG luminance delta is
    (0.2126 - 0.0722) x amount / 255 -- ~0.7% at the default 12, i.e. below any
    contrast floor's resolution. This is how MUSHROOM stays exactly as legible
    as the tertiary grey it is derived from: the contrast sweep still governs.
    """
    h = hex_str.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return _hexrgb(r + amount, g, b - amount)


# The inert-metadata note. Timestamps, counts, units, "of", separators, ghosted
# affordances -- the type that must be READ but never LOOKED AT. It is the
# tertiary grey warmed just off-neutral, so it recedes from the cool signal blue
# without becoming a third accent (SIGNAL + WARM remain the two-accent ceiling).
# Derived, never a literal, so it tracks the host seed like the rest of the ramp.
MUSHROOM = _warm_bias(_TXT["tertiary"])

# D3 (READABILITY.md 2026-09-15): the input placeholder was never a design-system
# colour at all -- Qt paints QPalette::PlaceholderText, which defaults to the
# text colour at 50% alpha. Composited over FIELD_INSET that measured #727272 at
# 3.43:1, under AA, and no token in this file could have moved it. Naming it here
# puts it back under the system; components.apply_placeholder_palette() installs
# it on the palette role. It is the hint/caption role, which is what a
# placeholder is: #9E9E9E at 6.15:1 on FIELD_INSET #1F1F1F.
TEXT_PLACEHOLDER = TEXT_TERTIARY

# WCAG note: SIGNAL (#8FB3D9) on PANEL passes AA for >=14px / bold, but FAILS
# for small body text. Use TEXT_ACCENT for labels/links/icons only; never for
# running body copy. Body uses TEXT_PRIMARY.

# ─────────────────────────────────────────────────────────────
# 4. INTERACTION-STATE ramp (formalized, not ad-hoc)
# ─────────────────────────────────────────────────────────────

SIGNAL_HOVER = "#A9C7E6"   # accent hover (lighter)
SIGNAL_PRESS = "#7398BE"   # accent press (deeper)
SIGNAL_DEEP  = "#627A93"   # filled-action blue: Connect / Corpus / SEND, one note
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


def _readable_identity(colour, surfaces):
    """Keep the approved hue, adjusting only when the host needs contrast."""
    rgb = tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))
    target = (255 if min(_contrast("#FFFFFF", s) for s in surfaces)
              >= min(_contrast("#000000", s) for s in surfaces) else 0)
    for step in range(101):
        amount = step / 100.0
        candidate = _hexrgb(*(c + (target - c) * amount for c in rgb))
        if min(_contrast(candidate, s) for s in surfaces) >= 4.5:
            return candidate
    return candidate


# Soft Editorial: identity is independent of connection health and task state.
MODEL_SELECTION = ("#44332E" if _wcag_lum(PANEL) < 0.2 else "#F5E6E0")
_IDENTITY_SURFACES = (PANEL, GROUND, RAISED)
CHAT_ASSISTANT = _readable_identity(WARM, _IDENTITY_SURFACES)
CHAT_USER = _readable_identity("#8AC7A3", _IDENTITY_SURFACES)
# Model choice shares the SYNAPSE ring's coral; the inset selection stays muted.
MODEL_ACCENT = CHAT_ASSISTANT
MODEL_DETAIL = _readable_identity(TEXT_PRIMARY, (MODEL_SELECTION,))

# The active Houdini tab marker; the fallback is H22 UIDark.hcs SELECTION_BASE
# (HSV 40, 0.825, 0.725). Keep diagnostic emphasis separate from warning status.
_TAB_RGB = theme_source.host_surface_rgb("PaneTabMarker") or (185, 134, 32)
HOUDINI_TAB_YELLOW = _hexrgb(*_TAB_RGB)
HOUDINI_TAB_YELLOW_HOVER = _hexrgb(*(channel + 24 for channel in _TAB_RGB))

# v9 muted status hues (comp --ok/--no/--hot) — the Work face's quiet verdict
# grammar (status dots, DsVerb ok/hot tones). NOT a retune of GROW/ERROR/FIRE:
# gates, badges and the STATUS table keep the full-strength hues.
#
# CONIFEROUS is the verified/ok hue, specified at design/cto_relay_01/
# L4_COHERE_SPEC.md:74 and never landed until now. It is a deeper, greyer green
# than the #6FBF8E it replaces: the ceiling is two accents per view and the
# render is the only chromatic event, so a PASS must read as settled rather
# than compete with the image. It sits beside the cool SIGNAL and the warm
# WARM without becoming a third accent, because a verdict dot is punctuation.
CONIFEROUS = "#6E8F72"   # verified / ok
NO_SOFT    = "#D96975"
# HOT_SOFT is RETIRED from the action family (CRIT.md 2026-09-15 ranked change
# 5, "one action family"): it no longer paints DsStop at rest (WARM now),
# DsVerb[tone="hot"] (TEXT_PRIMARY, no hue) or the BLOCKED tag (TEXT_BRIGHT).
# The token stays defined because the Work face still reads it as a VERDICT
# hue, where the crit counts and allows it: integrity_readout.py:55 (warning
# fidelity), face_review.py:45/:52 (warn / inconclusive) and
# network_trace.py:463 (the hot step). NO_SOFT likewise survives as the
# fail/error verdict hue -- face_review.py:46/:52/:63, integrity_readout.py:54,
# network_trace.py:477/:527 -- so it is NOT deleted; the crit's "NO_SOFT dead
# (UNVERIFIED)" line is REFUTED by that grep. Neither belongs on an action.
HOT_SOFT   = "#D08A57"

# Deprecated alias. Kept so every token name that existed before this rename
# still resolves (the panel token inventory is an oracle, not a courtesy), and
# aliased rather than left at its old value ON PURPOSE: two live greens in the
# palette is how a colour system grows a second authority, which is the exact
# defect this pass exists to remove. New code names CONIFEROUS.
OK_SOFT = CONIFEROUS

HOVER_BG   = RAISED        # neutral hover surface
CONTROL_OUTLINE = HOVER_BG  # interaction outlines share the inset footer's gray highlight
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
SIZE_UI     = 12   # buttons, pills, menu items, labels — Houdini-native; scalable via Aa
SIZE_BODY   = 12   # chat body — Houdini-native default (9pt ≈ 12px)
SIZE_TITLE  = 15   # section headers — gentle step above native
SIZE_HERO   = 19   # panel title — present, not shouting

# PNL-L4 (rulings R2-A1 / R3-A / R3-B, 2026-09-21): THREE sizes, not four.
# SIZE_SMALL was 11 — one pixel below SIZE_BODY, a rung nobody can see and the
# only reason the ramp counted four. A difference the eye cannot read is not
# hierarchy, it is noise in the token table, and it cost every caption and
# status line a pixel of legibility for nothing. Small is now BODY, and the
# quiet of a caption is carried by FORM (family, weight, caps, tracking) rather
# than by size. The ramp is 12 / 15 / 19.
SIZE_SMALL  = SIZE_BODY   # captions, metadata — quiet by form, not by size

# Back-compat alias (design/tokens.py name). Aliased to SIZE_SMALL since
# CRIT.md 2026-09-15 ranked change 1 deleted SIZE_MICRO; PNL-L4 then folded
# SIZE_SMALL into SIZE_BODY, so SIZE_LABEL's ~30 legacy consumers (styles.py,
# message_formatter.py, context_bar.py, the legacy sheet in qss.py) step
# 10 -> 11 -> 12 with it. It stays strictly below SIZE_TITLE.
SIZE_LABEL = SIZE_SMALL

# ── glyph sizes: deliberately NOT on the type scale ──────────────────────────
# 14 and 18 are not type. They are the em-box a status dot and a chevron need in
# order to draw at the right optical weight beside 12px text, and they were
# computed inline in qss.py as `SIZE_UI * 7 // 6` and `SIZE_UI * 3 // 2` -- two
# bare arithmetic expressions that a type census reads as two more sizes on the
# ramp. That is how a four-size scale gets counted as six.
#
# Naming them does not change a pixel. It states that they scale WITH the UI
# size (a glyph must stay proportional to the text it sits beside) while being
# off the hierarchy, so the next person measuring the type scale counts four
# rungs and finds these two already accounted for. READABILITY.md 2026-09-15:
# "they should be named GLYPH_MD / GLYPH_SM and taken off the type scale
# explicitly, not folded into it."
GLYPH_MD = SIZE_UI * 3 // 2   # 18 — status dots and other filled marks
GLYPH_SM = SIZE_UI * 7 // 6   # 14 — chevrons and disclosure arrows

# ── the type FLOOR (BP4-PANELFONT) ────────────────────────────
# Joe's law: "panel fonts consistent and no smaller than the Houdini default."
# The default UI font size is a MEASURED, GUI-only fact — QApplication.font()
# is meaningless under hython's app-less runtime — so it is read by
# scripts/probe_ui_font.py and pasted from a live Houdini 22.0.400 shell, never
# recalled from memory. Provenance ladder: measured GUI paste > a statement in
# the local H22 help cache (DOC-STATED) > UNKNOWN.
#
# Current provenance of the HOUDINI DEFAULT: still UNKNOWN. The local
# H22.0.400 help cache (…/houdini22.0/config/Help/cache — ref, basics, hom
# searched 2026-09-03) states no default UI font size, and the
# scripts/probe_ui_font.py GUI paste is still owed. When it lands, a follow-up
# raises the floor to the measured default and lifts any sub-floor role. The
# scale-comment recall that the sizes "matched 9pt ≈ 12px, verified on
# H21.0.671/.729" is an H21 measurement, NOT an H22 one — deliberately not used
# as the floor.
#
# WHAT THE FLOOR IS PINNED TO (changed by CRIT.md 2026-09-15, ranked change 1).
# It used to be pinned to "the smallest size already shipped on master"
# (SIZE_MICRO = 10) — which is circular: the floor could never catch the
# smallest shipped size, because the smallest shipped size WAS the floor. The
# floor is now the repo's own readability bar: audit_panel.py:388
# READABLE_FLOOR = 11 ("chrome must clear this"). That constant already existed
# and was already enforced — but only on rail-header widgets (audit_panel.py
# :402-403) while ~15 live 10px sites shipped underneath it. Pinning the token
# floor to it makes the audit's bar the whole panel's bar, and it is a reason
# external to the scale, so it cannot move just because a size moved.
#
# ONE constant, with a provenance string beside it (mission: "the floor lives
# as ONE constant in the token module with a provenance string"). Still kept
# independent of the SIZE_* scale on purpose: coupling them would make the
# "no size below the floor" test unable to catch a size token being lowered.
FONT_FLOOR_PX = 11
FONT_FLOOR_PROVENANCE = (
    # The first word is a controlled vocabulary -- measured | DOC-STATED | UNKNOWN --
    # pinned by tests/test_panel_typography.py::test_floor_constant_has_provenance.
    # This string opened UNKNOWN for months; it is the transition that guard exists
    # for, so it uses the guard's own word rather than a louder one.
    "measured 2026-09-15, live, twice independently: QFontInfo(QApplication.font()) "
    "on Houdini 22.0.400 reports family 'SideFX Source Sans Pro', pixelSize 27, "
    "pointSize 10; screen logical DPI 192.0, physical 218.66, devicePixelRatio 1.0. "
    "Probe: python/synapse/panel/scripts/probe_ui_font.py. "
    "This string previously read UNKNOWN and said it was awaiting that paste — the "
    "paste had been taken, and it also cited the probe at a repo-root path where the "
    "file has never existed. Both corrected here; no value changed. "
    "THE FLOOR IS STILL 11 AND IS STILL ABSOLUTE, which is now a stated position "
    "rather than an absence of data. The panel DOES scale to the host (PNL-L1, "
    "2026-09-21, correcting an earlier claim here that nothing scaled): "
    "synapse_panel.py seeds _chrome_scale = _host_font_scale() = host pixel size / "
    "SIZE_BODY (27 / 12 = 2.25 on the measured host) into qss.stylesheet(), so every "
    "chrome font scales, and the transcript font scales from the same base "
    "(chat_display floors it at FONT_FLOOR_PX). tokens.scaled() is "
    "max(8, round(size*scale)) with scale defaulting to 1.0 only when no host is "
    "read; in the live panel scale is the host ratio, so an authored 11px lands "
    "near 25 actual pixels beside host chrome of twenty-seven. The floor is "
    "therefore a pre-scale bar on the authored token, not a post-scale pixel "
    "count. Whether an absolute constant can be a floor against a host that moves "
    "is a DESIGN RULING and is open; see READABILITY.md 2026-09-15 'The floor is "
    "below the host' (and its 2026-09-21 correction). Until it is ruled the floor "
    "stays pinned to audit_panel.py READABLE_FLOOR = 11, the repo's own "
    "readability bar — NOT to the smallest size shipped, which was circular. "
    "PNL-L6 (ruling R3-C, 2026-09-21) wires the assertion that was missing: "
    "probe_ui_font.main() and tests/panel/test_font_scale.py::"
    "test_no_chrome_font_renders_below_the_host_ui_font both read "
    "QFontInfo(widget.font()).pixelSize() off the BUILT chrome (khint, rail "
    "author and meter, footer links, pills) and fail when the smallest of them "
    "falls under QFontInfo(QApplication.font()).pixelSize() — measured "
    "12 host / 12 min chrome under hython 22.0.400 offscreen. No value changed."
)

# ── weight tokens (BP4-PANELFONT) ─────────────────────────────
# The three CSS/Qt numeric weights the panel actually uses — named so the
# stylesheet and the roles stop hardcoding the bare numbers. Values unchanged
# (400/500/600), so every consumer sees the identical int it saw before.
WEIGHT_REGULAR  = 400   # body / caption / code
WEIGHT_MEDIUM   = 500   # label / status  (Qt QFont.Weight.Medium)
WEIGHT_SEMIBOLD = 600   # display / title / buttons / badges
# WEIGHT_BOLD is the weight the mono face actually HAS. designsystem/fonts/
# ships SpaceMono-Regular (400) + SpaceMono-Bold (700) and nothing between, and
# fontload.py maps any weight >= 600 to setBold — so 500 and 600 on mono are not
# weights the family owns. Filed by TYPE as ANSWER 1 of CRIT.md 2026-09-15
# (ranked change 19), where it was left pending M7.
#
# D4 (READABILITY.md 2026-09-15) — M7 IS NOW MEASURED. Raster ink counts of
# "Handgloves 8" at pixelSize 24, offscreen under Houdini 22.0.400, drawn through
# the same QFont ladder components.apply_font_role uses:
#     sans  400 -> 184395   sans  500 -> 230308   sans 600/700 -> 271953
#     mono  400 -> 188033   mono  500 -> 188033   mono 600/700 -> 275518
# So: mono 500 is BYTE-IDENTICAL to mono 400 (188033 = 188033) — the number was
# a request the family cannot fill. Sans 600 is BYTE-IDENTICAL to sans 700 on
# this path (271953 = 271953) — setBold resolves it to 700, QFontInfo agrees.
# And sans 500 is REAL: +24.9% ink over 400 (READABILITY.md says +14.6%; my own
# raster disagrees on the magnitude, not on the fact — see the branch report).
# TYPE_ROLES below now names the weight each role actually gets.
WEIGHT_BOLD     = 700   # sans setBold + mono's real bold (SpaceMono-Bold)

# The weights each bundled family can actually deliver, measured (see above).
# apply_font_role must never hand a family a weight outside its own set.
FAMILY_WEIGHTS = {
    "sans": (WEIGHT_REGULAR, WEIGHT_MEDIUM, WEIGHT_BOLD),
    "mono": (WEIGHT_REGULAR, WEIGHT_BOLD),
}

# v9 tracking map — em per role, RESTORED to the ratified comp values (the
# near-flat "match Houdini" dial was superseded by the ratified v9 comp).
# Tracking lives on QFont (PercentageSpacing = 100 + em×100), NEVER in QSS
# (Qt QSS has no letter-spacing). fontload.tracked_font() reads this.
#   EYEBROW  +0.22  section labels (PLAN title, credit-section heads)
#   BRAND    +0.286 wordmark — ~4px at the 14px wordmark size (0.286 × 14 =
#                    4.00px). Widened from +0.16 (2.24px): at weight 400 the
#                    word needs the air to hold its own without going bold.
#   LABEL    +0.15  the CHAT pill (DIRECT/WORK tabs removed in v9.1)
#   LABEL_SM +0.12  credit keys, acts verbs, tiny labels
#   DATA     +0.03  author, meter, paths, cookline, ⌘K chip
#   SEND     +0.08  the SEND button
#   DISPLAY  -0.015 verdict
#   BODY      0     conversation, prompt
TRACKING_EM: Dict[str, float] = {
    "EYEBROW": 0.22, "BRAND": 0.286, "LABEL": 0.15, "LABEL_SM": 0.12,
    # WORDMARK — the SYNAPSE lockup, 2026-07-27. BRAND's 0.286em (~4px at 14px)
    # was tuned for weight 400, where wide tracking IS the hierarchy. At weight
    # 600 that same tracking reads heavy-and-sparse: individually bold letters
    # sitting visually apart. Solidity is weight PLUS density, so the mark gets
    # its own value rather than bending BRAND, which other labels still use.
    "WORDMARK": 0.16,
    "DATA": 0.03, "SEND": 0.08, "DISPLAY": -0.015, "BODY": 0.0,
    # PNL-L1 (2026-09-21): rhythm._apply_type's section-4 values, named. They
    # used to borrow SEND (0.08) and DATA * 2 (0.06) by numeric coincidence;
    # a tweak to the SEND button would have moved every rail label. Same
    # numbers, zero pixel change.
    "LABEL_RHYTHM": 0.08, "TAG_RHYTHM": 0.06,
}


def tracking_px(role: str, px: float) -> float:
    """AbsoluteSpacing pixels for a role at a given px size (em × px). Pure —
    the QFont application lives in fontload.tracked_font()."""
    return TRACKING_EM.get(role, 0.0) * px


# Roles: (family_css, size_px, weight, letter_spacing_px) — components read these.
#
# Mono is for CODE, sans is for everything else. Mono earns its place where the
# glyphs are data the eye has to align or scan character by character — node
# paths, tool names, versions, token counts, VEX, the `code` and `status` roles.
# It does NOT belong on prose-shaped chrome: a title and a UI label are read as
# words, and setting them in a typewriter face made the panel read like a
# terminal emulator rather than a tool. So `title` and `label` move to sans;
# `code` and `status` stay mono, unchanged.
TYPE_ROLES: Dict[str, Tuple[str, int, int, float]] = {
    # D4: display/title asked SEMIBOLD 600 and the screen has always drawn 700
    # (setBold); status asked MEDIUM 500 on mono and the screen has always drawn
    # 400. Writing what renders changes nothing on screen — it stops the sheet
    # describing faces that never shipped. `label` keeps MEDIUM because sans 500
    # is a face the variable file really has; apply_font_role now delivers it.
    "display": (FONT_SANS_CSS, SIZE_HERO,  WEIGHT_BOLD,    0.5),
    "title":   (FONT_SANS_CSS, SIZE_TITLE, WEIGHT_BOLD,    1.0),
    "body":    (FONT_SANS_CSS, SIZE_BODY,  WEIGHT_REGULAR,  0.0),
    "label":   (FONT_SANS_CSS, SIZE_UI,    WEIGHT_MEDIUM,   0.5),
    "code":    (FONT_MONO_CSS, SIZE_BODY,  WEIGHT_REGULAR,  0.0),
    # PNL-L4 (ruling R3-B, 2026-09-21): caption and status used to be quiet
    # BY SIZE — 11px, one pixel under body, a difference no eye reads. They are
    # now quiet BY FORM at the body size. `caption` is sans 500 in ALL CAPS on
    # LABEL_SM tracking (the tiny-label voice the panel already speaks);
    # `status` is mono 400 on DATA tracking (it is data, and mono ships no 500 —
    # FAMILY_WEIGHTS). The two hand-picked 0.0 / 0.5 px values are gone: both
    # roles now derive their tracking from TRACKING_EM at their own size, so a
    # tracking change has ONE owner instead of two.
    "caption": (FONT_SANS_CSS, SIZE_SMALL, WEIGHT_MEDIUM,
                tracking_px("LABEL_SM", SIZE_SMALL)),
    "status":  (FONT_MONO_CSS, SIZE_SMALL, WEIGHT_REGULAR,
                tracking_px("DATA", SIZE_SMALL)),
}

# PNL-L4 (ruling R3-B): the roles whose quiet is carried by CASE. Kept out of
# the TYPE_ROLES tuple on purpose — three call sites unpack that tuple by
# arity (components.apply_font_role, components.label, recipe_card), and
# widening it to five would have been a refactor pretending to be a type note.
# apply_font_role reads this set; nothing else upper-cases text in Python.
#
# IT SHIPS EMPTY, AND THAT IS THE FINDING. R3-B asks for caption in ALL CAPS.
# Measured before writing it: `caption` is not the tiny-label role the ruling
# describes. Twenty-odd call sites hand it whole SENTENCES — connection_dialog
# "The check sends credentials and asks for model metadata only…",
# project_rules "Allowed background requests may send prompts, conversation,
# scene context…", notifications, saved_recipes, tool_palette's empty state.
# Upper-casing a paragraph is the opposite of the readability this leg is for,
# and it would have been done silently under a ruling written for chips.
# So the MECHANISM lands, wired and tested, and the SET stays empty until the
# caption role is split (metadata chip vs. explanatory prose) or a ruling says
# otherwise. Adding "caption" here is then a one-word change.
ROLE_CAPS: frozenset = frozenset()



# The user font-scale drives CONTENT ONLY — the chat dialogue + the prompt
# input. Chrome (header, labels, pills, palette) is frozen at the host UI size.
# Startup default is 1.0 = the host UI size ("default Houdini UI font size to
# start"); the live panel seeds an exact host-matched base, and the Aa control
# cycles the steps from there.
FONT_SCALE_STEPS = (1.0, 1.15, 1.25, 1.4, 1.6)
FONT_SCALE_DEFAULT = 1.0


def host_floored_steps(host_scale=1.0):
    """The Aa font-scale ladder with the HOST default as its FLOOR (W5-PANEL 2/4).

    The switcher's job is to scale the reading size UP from the Houdini UI
    default, never below it: "minimum font size must be the Houdini default; the
    switcher only shrinks today" (Joe, live seat). The raw ``FONT_SCALE_STEPS``
    are anchored at ``1.0 = SIZE_BODY`` (12px), which equals the host default ONLY
    when the host UI font is 12px. On a host whose UI font is larger, ``1.0`` is
    BELOW the host default, and cycling the raw ladder drops the text under the
    floor — the reported defect.

    Returns a monotonic ladder whose FIRST entry equals ``host_scale`` (the floor)
    and every entry is ``>= host_scale``: raw steps at or above the floor are kept,
    and any raw step below the floor is lifted into the floor (deduped). So the
    minimum selectable scale is always the host default and the artist scales UP.

    Pure — no Qt, no ``hou``. The caller supplies the measured host scale
    (``host_font_px / SIZE_BODY``); ``synapse_panel._host_font_scale`` already
    computes exactly that. A non-positive ``host_scale`` falls back to the 1.0
    default so a bad read never produces an empty or inverted ladder.
    """
    floor = float(host_scale) if host_scale and host_scale > 0 else FONT_SCALE_DEFAULT
    steps = [floor]
    for s in FONT_SCALE_STEPS:
        if float(s) > floor + 1e-9:
            steps.append(float(s))
    return tuple(steps)


def next_font_scale(current, host_scale=1.0):
    """The next Aa step UP from ``current``, floored at the host default.

    Cycles :func:`host_floored_steps`: each press moves to the next larger step,
    and the wrap at the top goes back to the FLOOR (host default) — never below
    it. This is the pure decision the live switcher
    (``synapse_panel._cycle_font_scale``) needs in place of cycling the raw,
    host-agnostic ``FONT_SCALE_STEPS``. A base that sits between steps picks the
    first step strictly greater; at or above the top it wraps to the floor.

    Guarantee under test (test_font_floor.py): for any starting scale, repeated
    application never yields a value ``< host_scale`` — no state below the floor
    is reachable.
    """
    ladder = host_floored_steps(host_scale)
    for s in ladder:
        if s > float(current) + 1e-9:
            return s
    return ladder[0]

# ─────────────────────────────────────────────────────────────
# 6. SPACING / RADIUS — load-bearing scale
# ─────────────────────────────────────────────────────────────

SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 40

# sec.7 4-pt rhythm grid (BP2-PANELDESIGN). The load-bearing GAP ladder is
# 4·8·12·16·24·32·48. The existing rungs above keep their names AND values
# verbatim (heavy consumers — SPACE_SM ×44 / SPACE_XS ×25 / SPACE_MD ×23 /
# SPACE_LG ×9 call sites across panel/): never renamed, never revalued. The
# three stops the grid adds are NEW + additive, named by px so the spec and QSS
# read unambiguously. SPACE_XL (40) is retained as the fixed card-band height
# (a dimension, off the gap ladder). See docs/PANEL_RHYTHM_SPEC.md §2.
SPACE_12 = 12   # row-breath / label-below rung (¾ of 16)
SPACE_32 = 32   # parm-row section-head gap
SPACE_48 = 48   # doubled group gap (verb rail); 2 × SPACE_LG
SPACE_GRID = (SPACE_XS, SPACE_SM, SPACE_12, SPACE_MD, SPACE_LG, SPACE_32, SPACE_48)

# The wordmark lockup (Joe, 2026-09-05, on the review canvas: "1pt larger and
# 5px farther to the right of the orange circle"). The px the wordmark sits
# beyond the identity row's stack gap from the mark - a dimension of the
# lockup, not a gap rung; the one token the addendum admitted this wave.
WORDMARK_GAP = 5

# Density is ONE panel-wide rhythm (L5-18): GAPS scale, PADDINGS stay fixed
# (sec.7). The compositor stamps `density` on #DsRoot and repolishes the whole
# tree (08-04, proven by PANELTRUTH); the QSS generator bakes the three stepped
# values into #DsRoot[density=...] descendant rules. Paddings NEVER call gap().
DENSITY_GAP_SCALE = {"airy": 1.5, "standard": 1.0, "tight": 0.75}


def gap(base_px, density="standard"):
    """A GAP stepped by the density multiplier (sec.7): airy ×1.5, standard ×1,
    tight ×0.75. Returns integer px (round). Pure — the QSS application lives in
    qss.stylesheet(). Only gaps call this; paddings are fixed. An unknown
    density resolves to ×1 (standard) so a malformed manifest never inverts the
    rhythm."""
    return int(round(base_px * DENSITY_GAP_SCALE.get(density, 1.0)))

# Chat dialogue leading (W5-PANEL item 5). +0.75pt of ABSOLUTE leading added
# between wrapped chat lines — Joe's "the chat reads tight" on the live seat.
# Applied in chat_display as a QTextBlockFormat LineDistanceHeight: the one
# line-spacing mechanism the QTextDocument HTML subset does NOT drop (CSS
# line-height and ProportionalHeight were both measured inert here — see
# message_formatter.py:43). Expressed in POINTS to match the request; converted
# to the device-independent px the QTextDocument lays out in at Qt's 96-DPI
# logical default (1pt = 96/72 px), so +0.75pt = +1.0px of leading per line.
# READABILITY (Joe, 2026-09-21): doubled from 0.75pt. Measured on the shipped
# v5.79.0 transcript at SIZE_BODY 12: the line-to-line step was 17.00px, a ratio of
# 1.42x the font size, UNDER the 1.50x that WCAG 1.4.12 asks for body text. Doubling
# the added distance takes the step to 18px and the ratio to exactly 1.50x. The
# doubling and the standard happen to land on the same number; both are the reason.
CHAT_LEADING_PT = 1.50


def chat_leading_px(pt=None):
    """``pt`` of leading in the device-independent px a QTextDocument lays out in.

    Qt's default logical resolution is 96 DPI, so 1pt = 96/72 px. Pure — the
    QTextBlockFormat application lives in chat_display._apply_leading. Defaults to
    :data:`CHAT_LEADING_PT` (0.75pt → 1.0px).
    """
    p = CHAT_LEADING_PT if pt is None else float(pt)
    return p * 96.0 / 72.0

RADIUS_SM = 4
RADIUS_MD = 8
RADIUS_LG = 12
RADIUS_PILL = 14

# sec.7 fixed dimensions (BP2-PANELDESIGN) — additive, never scaled by density.
# RADIUS: sec.7 "8 rows · 10 cards · 999 pills" — RADIUS_MD (8) already serves
# rows; RADIUS_CARD (10) and RADIUS_ROUND (999, fully-rounded pill) are new.
# ROW_MIN_H is the list-row min height / 44×44 glyph cell. The three-band recall
# card is greenfield (a held spawn) and will consume these; pinned by
# tests/test_bp2_paneldesign_density.py so they are contract, not dead code.
FOOTER_HEIGHT = 38 * 0.95  # approved 5% reduction, outer height before host scale
FOOTER_GAP = 9

RADIUS_CARD  = 10
RADIUS_ROUND = 999
ROW_MIN_H    = 44

# --- monolinear icon system ---------------------------------------------
# ONE line weight, ONE grid. Every drawn glyph in the panel (status dots, the
# mark, check dots, cell outlines) strokes at STROKE_PX and lays out on a
# 24px grid or an even divisor of it (24 / 16 / 12 / 8). No fills, no
# dual-tone, no second weight -- if a glyph needs emphasis it gets colour or
# size, never a heavier line.
ICON_GRID  = 24     # the icon layout grid
STROKE_PX  = 1.5    # the one icon line weight, in device-independent px

# --- atmosphere ----------------------------------------------------------
# Texture is a field BEHIND content, never a border or a fill. The gradient
# spans a few 8-bit levels either side of the surface it sits on -- enough to
# stop a large flat pane reading as dead vinyl, far too little to become a
# shape. Contrast against text is unchanged to within ~1%, so the WCAG sweep
# still governs the ramp; this is atmosphere, not information.
ATMOSPHERE_DELTA = 4   # 8-bit levels between the gradient's two stops


def atmosphere(base_hex, delta=None, angle="x1:0, y1:0, x2:0, y2:1"):
    """A QSS qlineargradient of ``base_hex`` +/- ``delta`` levels -- the
    low-contrast field that sits behind a surface. Returns a plain CSS string
    so QSS can consume it wherever a flat ``background:`` used to go."""
    d = ATMOSPHERE_DELTA if delta is None else delta
    h = base_hex.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    hi = _hexrgb(r + d, g + d, b + d)
    lo = _hexrgb(r - d, g - d, b - d)
    return ("qlineargradient(%s, stop:0 %s, stop:1 %s)" % (angle, hi, lo))


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
PANEL_MIN_HEIGHT = 420  # was 400; raised for Mile-1b vertical body air (Joe's ruling 2026-07-17). test_docking reads this token, so the enforced floor tracks the spec.
GUTTER = 30  # panel edge gutter — one dial replacing the scattered 26px literals (rail/mode-bar/direct-face). Value is the Design Director's call; 26–36 is safe on a 280px-min panel.

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
