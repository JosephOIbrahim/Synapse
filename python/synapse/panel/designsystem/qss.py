"""The single QSS generator — one stylesheet from the one token table.

Applied once at the panel root; cascades to every component by objectName +
dynamic property. This replaces the 314 inline-style occurrences and the 30
one-off get_*_stylesheet() helpers the audit found. Widget code carries NO raw
hex — it sets objectName/properties and lets this sheet style it.
"""

from . import tokens as t


def stylesheet(scale: float = t.FONT_SCALE_DEFAULT) -> str:
    """Return the full panel stylesheet at the given user font-scale."""
    s = lambda px: t.scaled(px, scale)  # noqa: E731

    return f"""
/* ---- root + opaque sections ---------------------------------- */
/* NO global `QWidget {{ background: transparent }}` — that rule was the
   repaint-ghosting cause (transparent widgets never erase their backing store,
   so Houdini composites stale pixels). Every container is opaque instead.
   No font-family: inherit Houdini's app-level UI font (native). */
/* Atmosphere, never dominant: the root is a gradient FIELD rather than a flat
   fill -- PANEL +/- ATMOSPHERE_DELTA (4 of 255) top to bottom. At that
   amplitude it is not a shape and not information; it just stops a tall pane
   reading as dead vinyl, and it gives the content something to sit ON. Text
   contrast moves by well under 1%, so the WCAG sweep still governs the ramp.
   Sections stay flat so the field reads once, at the back, and never stacks. */
QWidget#DsRoot {{
    background: {t.atmosphere(t.PANEL)};
    color: {t.TEXT_PRIMARY};
    font-size: {s(t.SIZE_BODY)}px;
}}
QWidget#DsSection {{ background: {t.PANEL}; }}
QTextBrowser {{ background: {t.GROUND}; border: none; }}
/* v9 rail: flat PANEL with a 1px HAIR bottom rule (the comp retired the
   cool→warm gradient wash). */
QWidget#DsHeader {{
    background: {t.PANEL};
    border-bottom: 1px solid {t.HAIR};
}}
QToolTip {{
    background: {t.SURFACE}; color: {t.TEXT_PRIMARY};
    border: 1px solid {t.BORDER}; padding: {t.SPACE_XS}px {t.SPACE_SM}px;
    border-radius: {t.RADIUS_SM}px; font-size: {s(t.SIZE_SMALL)}px;
}}

/* ---- buttons (variant via dynamic property) ------------------ */
QPushButton#DsButton {{
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_SM}px {t.SPACE_MD}px;
    font-size: {s(t.SIZE_UI)}px;
    font-weight: 600;
    border: 1px solid transparent;
}}
QPushButton#DsButton[variant="primary"] {{
    background: {t.SIGNAL_DEEP}; color: {t.TEXT_ON_ACCENT};
}}
QPushButton#DsButton[variant="primary"]:hover  {{ background: {t.SIGNAL}; }}
QPushButton#DsButton[variant="primary"]:pressed {{ background: {t.SIGNAL_PRESS}; }}
QPushButton#DsButton[variant="secondary"] {{
    background: {t.SURFACE}; color: {t.TEXT_PRIMARY}; border: 1px solid {t.BORDER_STRONG};
}}
QPushButton#DsButton[variant="secondary"]:hover  {{ background: {t.RAISED}; border-color: {t.TEXT_TERTIARY}; }}
QPushButton#DsButton[variant="secondary"]:pressed {{ background: {t.PRESS_BG}; }}
QPushButton#DsButton[variant="ghost"] {{
    background: transparent; color: {t.TEXT_SECONDARY}; border: 1px solid transparent;
}}
QPushButton#DsButton[variant="ghost"]:hover  {{ background: {t.HOVER_BG}; color: {t.TEXT_PRIMARY}; }}
QPushButton#DsButton[variant="danger"] {{
    background: transparent; color: {t.ERROR}; border: 1px solid {t.ERROR};
}}
QPushButton#DsButton[variant="danger"]:hover  {{ background: {t.STATE_TINTS["error"]}; }}
/* prominence (L5-16 amends L5-15): hero buttons keep the KNOCKOUT
   construction [variant="primary"] already uses -- accent fill,
   TEXT_ON_ACCENT ink -- but the fill is now SIGNAL_DEEP, the one deep
   blue SEND also takes (Joe's seat call: the coral read too loud on
   buttons; WARM keeps its non-button hero rules). Darkening the rest
   state is what frees the ramp: hover steps UP to SIGNAL (the old
   rest) and press steps DOWN to SIGNAL_PRESS, so the fill still
   responds to touch. TEXT_ON_ACCENT is the one sanctioned ink
   (5.60:1 on SIGNAL_DEEP -- AA). Quiet steps the type down the
   ladder. Placed before :disabled so the disabled state still
   wins and a hero button greys correctly. */
QPushButton#DsButton[prominence="hero"] {{
    background: {t.SIGNAL_DEEP}; color: {t.TEXT_ON_ACCENT}; border-color: transparent;
}}
QPushButton#DsButton[prominence="hero"]:hover   {{ background: {t.SIGNAL}; color: {t.TEXT_ON_ACCENT}; border-color: transparent; }}
QPushButton#DsButton[prominence="hero"]:pressed {{ background: {t.SIGNAL_PRESS}; border-color: transparent; }}
QPushButton#DsButton[prominence="quiet"] {{ color: {t.TEXT_TERTIARY}; }}
QPushButton#DsButton:disabled {{ background: {t.DISABLED_BG}; color: {t.TEXT_DISABLED}; border-color: transparent; }}

/* ---- STOP — the mark's second surface (L5-20, Joe's seat call) --
   MarkDot.set_halt_handler binds the loading mark to this button: one
   control, two surfaces. The mark's rule is "always in the one warm
   note (WARM)", so Stop takes the same coral as a knockout -- WARM
   fill, TEXT_ON_ACCENT ink (6.42:1 on WARM, past AA) -- instead of
   the danger red that made the two surfaces read unrelated. Hover and
   press ride the WARM companions; disabled matches its filled
   siblings (the button ships disabled + hidden until work is in
   flight). Metrics mirror #DsButton so only the paint changes. The
   danger variant itself is untouched: other widgets may rely on it.
   Not profile-conditional -- Stop looks identical in all three. */
QPushButton#DsStop {{
    background: {t.HOT_SOFT}; color: {t.TEXT_ON_ACCENT};
    border: none; border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_SM}px {t.SPACE_MD}px;
    font-size: {s(t.SIZE_UI)}px; font-weight: 600;
}}
QPushButton#DsStop:hover   {{ background: {t.WARM}; }}
QPushButton#DsStop:pressed {{ background: {t.WARM_PRESS}; }}
QPushButton#DsStop:disabled {{ background: {t.DISABLED_BG}; color: {t.TEXT_DISABLED}; }}

/* ---- tabs: underline on a baseline track (v9 call 1) --------- */
/* Retires the filled-pill active state: tabs read as text on a shared 2px
   baseline; the active tab lights its rule + text (TEXT_BRIGHT per comp).
   Font family/size/tracking live on the QFont (LABEL role), never here. */
QWidget#DsTabRow {{
    background: {t.PANEL};
    border-bottom: 1px solid {t.BORDER};
}}
QPushButton#DsPill {{
    background: none; color: {t.TEXT_TERTIARY};
    border: none; border-bottom: 2px solid transparent; border-radius: 0;
    padding: 0 0 12px 0;
}}
QPushButton#DsPill:hover  {{ color: {t.TEXT_BRIGHT}; }}
QPushButton#DsPill:disabled {{ color: {t.TEXT_DISABLED}; }}
QPushButton#DsPill[active="true"] {{
    color: {t.TEXT_BRIGHT}; border-bottom: 2px solid {t.SIGNAL};
}}

/* ---- rail author token — THE engine+model click target (v9) ----
   Mono/DATA family+tracking live on the QFont; hover underline + pointing
   hand carry discoverability (the comp shows no ▾). */
QPushButton#DsAuthor {{
    background: transparent; border: none; padding: 0 {t.SPACE_XS}px;
    color: {t.SIGNAL};
}}
QPushButton#DsAuthor:hover {{
    color: {t.SIGNAL_HOVER}; text-decoration: underline;
}}

/* ---- rail token meter (tokens only, never $) + ⌘K chip -------- */
QLabel#DsMeter {{ color: {t.TEXT_TERTIARY}; }}
QLabel#DsKHint {{
    color: {t.TEXT_TERTIARY};
    border: 1px solid {t.BORDER}; border-radius: {t.RADIUS_SM}px;
    padding: 3px 7px;
}}
/* prominence (L5-14 amends L5-13): hero takes the accent its role calls
   for -- the token meter is economic, so SIGNAL; the ⌘K chip is an
   action affordance, so WARM. Quiet keeps the L5-13 rung below standard
   (TEXT_DISABLED); the hint's box quiets to the HAIR rule. */
QLabel#DsMeter[prominence="hero"]  {{ color: {t.SIGNAL}; }}
QLabel#DsMeter[prominence="quiet"] {{ color: {t.TEXT_DISABLED}; }}
QLabel#DsKHint[prominence="hero"]  {{ color: {t.WARM}; }}
QLabel#DsKHint[prominence="quiet"] {{ color: {t.TEXT_DISABLED}; border-color: {t.HAIR}; }}

/* ---- type-set verbs (Direct act bar + Review actions) — Mile 7 --- */
/* Verbs read as type, not buttons: flat, mono, the chrome recedes. */
QPushButton#DsVerb {{
    background: transparent; border: none; padding: 2px 0;
    color: {t.TEXT_SECONDARY};
    font-size: {s(11)}px;
}}
QPushButton#DsVerb:hover {{ color: {t.TEXT_ACCENT}; }}
QPushButton#DsVerb[tone="ok"]     {{ color: {t.CONIFEROUS}; }}
QPushButton#DsVerb[tone="hot"]    {{ color: {t.HOT_SOFT}; }}
QPushButton#DsVerb[tone="accent"] {{ color: {t.TEXT_ACCENT}; }}
/* prominence (L5-14 amends L5-13): verbs are actions, so hero takes
   WARM, the human accent; after the tone rows so hero outranks a tone
   at rest. The :hover companion rides WARM_HOVER so hover feedback
   stays alive on hero verbs. */
QPushButton#DsVerb[prominence="hero"]  {{ color: {t.WARM}; }}
QPushButton#DsVerb[prominence="hero"]:hover {{ color: {t.WARM_HOVER}; }}
QPushButton#DsVerb[prominence="quiet"] {{ color: {t.TEXT_TERTIARY}; }}

/* ---- two-axis palette chips (⌘K · DO × WHERE) ---------------- */
/* Cells, not boxes: the chip is no longer a rounded rectangle floating in the
   row. Selection is carried by a left edge-marker plus a flat wash that runs
   to the type -- an irregular cell boundary (marked on one side, open on the
   others) instead of a uniform pill. Radius drops to 0 so nothing reads as a
   button; the asymmetric padding keeps the type optically centred. */
QPushButton#DsChip {{
    background: transparent; color: {t.MUSHROOM};
    border: none; border-left: {t.STROKE_PX:.0f}px solid transparent;
    border-radius: 0px; padding: 3px 8px 3px 7px;
    font-size: {s(10)}px;
}}
QPushButton#DsChip:hover {{ color: {t.TEXT_SECONDARY}; }}
QPushButton#DsChip[active="true"] {{
    background: {t.SIGNAL_TINT}; color: {t.TEXT_ACCENT};
    border-left: {t.STROKE_PX:.0f}px solid {t.SIGNAL};
}}

/* ---- command-palette list ------------------------------------ */
QListWidget#DsList {{
    background: transparent; color: {t.TEXT_PRIMARY};
    border: none; outline: none;
}}
QListWidget#DsList::item {{ padding: {t.SPACE_XS}px {t.SPACE_SM}px; border-radius: {t.RADIUS_SM}px; }}
QListWidget#DsList::item:selected {{ background: {t.SIGNAL_TINT}; color: {t.TEXT_ACCENT}; }}

/* ---- cards & drawers ----------------------------------------- */
QWidget#DsCard {{
    background: {t.SURFACE}; border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_LG}px;
}}
QWidget#DsCard[tone="warn"]  {{ border-color: {t.WARN}; }}
QWidget#DsCard[tone="approve"] {{ border-color: {t.FIRE}; }}
QWidget#DsCard[tone="critical"] {{ border-color: {t.ERROR}; }}

/* ---- badges / chips ------------------------------------------ */
QLabel#DsBadge {{
    border-radius: {t.RADIUS_SM}px; padding: 1px {t.SPACE_SM}px;
    font-size: {s(t.SIZE_MICRO)}px; font-weight: 600;
    background: {t.RAISED}; color: {t.TEXT_SECONDARY};
}}
QLabel#DsBadge[kind="grow"]  {{ color: {t.GROW};  background: {t.STATE_TINTS["grow"]}; }}
QLabel#DsBadge[kind="warn"]  {{ color: {t.WARN};  background: {t.STATE_TINTS["warn"]}; }}
QLabel#DsBadge[kind="error"] {{ color: {t.ERROR}; background: {t.STATE_TINTS["error"]}; }}
QLabel#DsBadge[kind="signal"]{{ color: {t.SIGNAL};background: {t.STATE_TINTS["signal"]}; }}
/* prominence (L5-14 amends L5-13): badges report technical status, so
   hero takes SIGNAL; type only -- kind backgrounds keep. */
QLabel#DsBadge[prominence="hero"]  {{ color: {t.SIGNAL}; }}
QLabel#DsBadge[prominence="quiet"] {{ color: {t.TEXT_TERTIARY}; }}

/* ---- text inputs (v9 call 2: darker field-inset grey) -------- */
QTextEdit#DsInput, QLineEdit#DsField {{
    background: {t.FIELD_INSET}; color: {t.TEXT_PRIMARY};
    border: 1px solid {t.BORDER}; border-radius: {t.RADIUS_SM}px;
    padding: 16px 15px; font-size: {s(t.SIZE_UI)}px;
    selection-background-color: {t.SIGNAL_TINT_STRONG};
}}
QTextEdit#DsInput:focus, QLineEdit#DsField:focus {{ border-color: {t.SIGNAL}; }}

/* ---- SEND — embedded bottom-right inside the composer (comp) --- */
/* L5-16 (Joe's seat call): rest darkens to SIGNAL_DEEP so SEND and hero
   buttons read as the same deep blue knockout; hover rises to SIGNAL
   (the old rest) and press keeps SIGNAL_PRESS -- the ramp still moves. */
QPushButton#DsSend {{
    background: {t.SIGNAL_DEEP}; color: {t.TEXT_ON_ACCENT};
    border: none; border-radius: {t.RADIUS_SM}px;
    padding: 9px 15px;
}}
QPushButton#DsSend:hover   {{ background: {t.SIGNAL}; }}
QPushButton#DsSend:pressed {{ background: {t.SIGNAL_PRESS}; }}
QPushButton#DsSend:disabled {{ background: {t.DISABLED_BG}; color: {t.TEXT_DISABLED}; }}

/* ---- role labels (color; font set in Python from TYPE_ROLES) -- */
QLabel[role="title"]   {{ color: {t.TEXT_BRIGHT}; }}
QLabel[role="body"]    {{ color: {t.TEXT_PRIMARY}; }}
QLabel[role="caption"] {{ color: {t.TEXT_TERTIARY}; }}
QLabel[role="label"]   {{ color: {t.TEXT_SECONDARY}; }}
QLabel[role="accent"]  {{ color: {t.TEXT_ACCENT}; }}

/* ---- prominence (set by the profile compositor) -- L5-13/L5-14 -- */
/* Hero TAKES THE ACCENT (L5-14): each ID-qualified rule above lifts its
   widget to the accent its own role already calls for -- WARM for
   human/orientation widgets, SIGNAL for technical/economic ones, per
   the roles tokens.py records for the two accents. SIGNAL + WARM are
   the two-accent ceiling: never a third. Quiet steps DOWN the emphasis
   ladder (toward TEXT_TERTIARY) -- colour emphasis only, never size,
   font, or layout. Standard prominence has NO rule on purpose: expert
   == v5.42.0 exactly (L5-5), so unmarked widgets must render exactly
   as today. The bare selectors below are the roleless fallback: with
   no role to read they step to TEXT_BRIGHT -- an accent here would
   pick a side the stylesheet has no basis for. ID-qualified variants
   live beside their components above -- a bare attribute selector
   loses the QSS specificity contest against the `#Ds*` rules. */
*[prominence="hero"]  {{ color: {t.TEXT_BRIGHT}; }}
*[prominence="quiet"] {{ color: {t.TEXT_TERTIARY}; }}
QLabel[prominence="hero"]  {{ color: {t.TEXT_BRIGHT}; }}
QLabel[prominence="quiet"] {{ color: {t.TEXT_TERTIARY}; }}

/* ---- density (set by the profile compositor) -- L5-18 -------- */
/* The second profile axis: ONE panel-wide rhythm, keyed on the root's
   `density` dynamic property and driving descendants -- never a
   per-widget spacing spec. Two rules ONLY (airy / tight). Standard has
   NO rule ON PURPOSE: the unstyled sheet IS the standard rhythm, so
   expert == v5.42.0 exactly (L5-5) -- an unconditional spacing rule
   here would move that pin. Every value is a rung of the existing
   tokens.py scale (SPACE_XS 4 / SPACE_SM 8 / SPACE_MD 16 / SPACE_LG
   24): airy steps a surface ONE rung up from its rest value, tight ONE
   rung down. Surfaces resting at zero (the chat viewport, the rail and
   tab-row shells) have no rung below them, so tight omits them rather
   than invent a negative; off-scale literals (DsSend 9/15, DsPill 12)
   do not step -- stepping them would mean inventing a number. Spacing
   only: no colour, size, weight, font, radius or border may ever
   appear in this block. */
/* airy — Curious: one rung more air. The chat surface answers Joe's
   seat call directly: replies get more vertical room to breathe. */
#DsRoot[density="airy"] QTextBrowser {{
    padding-top: {t.SPACE_XS}px; padding-bottom: {t.SPACE_XS}px;
}}
#DsRoot[density="airy"] QWidget#DsHeader {{
    padding-top: {t.SPACE_XS}px; padding-bottom: {t.SPACE_XS}px;
}}
#DsRoot[density="airy"] QWidget#DsTabRow {{
    padding-top: {t.SPACE_XS}px; padding-bottom: {t.SPACE_XS}px;
}}
#DsRoot[density="airy"] QPushButton#DsButton {{
    padding: {t.SPACE_MD}px {t.SPACE_LG}px;
}}
#DsRoot[density="airy"] QTextEdit#DsInput,
#DsRoot[density="airy"] QLineEdit#DsField {{
    padding-top: {t.SPACE_LG}px; padding-bottom: {t.SPACE_LG}px;
}}
/* tight — ML: one rung less. Only surfaces with a rung below rest. */
#DsRoot[density="tight"] QPushButton#DsButton {{
    padding: {t.SPACE_XS}px {t.SPACE_SM}px;
}}
#DsRoot[density="tight"] QTextEdit#DsInput,
#DsRoot[density="tight"] QLineEdit#DsField {{
    padding-top: {t.SPACE_SM}px; padding-bottom: {t.SPACE_SM}px;
}}

/* ---- progress ------------------------------------------------ */
QProgressBar#DsProgress {{
    background: {t.SURFACE}; border: none; border-radius: {t.RADIUS_SM}px;
    height: {t.SPACE_XS}px; text-align: center;
}}
QProgressBar#DsProgress::chunk {{ background: {t.SIGNAL}; border-radius: {t.RADIUS_SM}px; }}

/* ---- cook bar (comp .cookbar): 3px neutral track, RAISED fill --- */
QProgressBar#DsCookBar {{
    background: {t.GROUND}; border: none; border-radius: 2px;
}}
QProgressBar#DsCookBar::chunk {{ background: {t.RAISED}; border-radius: 2px; }}

/* ---- rail meter (rail .observe): 3px strip, 2px-on-3px per the
   cook bar above; idle SIGNAL_TINT, busy WARM via [busy] -------- */
QWidget#DsRailMeter {{
    background: {t.SIGNAL_TINT}; border: none; border-radius: 2px;
}}
/* prominence (L5-13): hero lifts the idle tint to full SIGNAL -- the
   accent this strip already carries in tint form. Placed before [busy]
   so the busy WARM state still wins the tie. */
QWidget#DsRailMeter[prominence="hero"] {{ background: {t.SIGNAL}; }}
QWidget#DsRailMeter[busy="true"] {{ background: {t.WARM}; }}

/* ---- Work-face acts row (comp .acts): quiet HAIR top rule ----- */
QWidget#DsActs {{
    background: {t.PANEL};
    border-top: 1px solid {t.HAIR};
}}

/* ---- scrollbars (quiet) -------------------------------------- */
QScrollBar:vertical {{ background: transparent; width: {t.SPACE_SM}px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t.RAISED}; border-radius: {t.RADIUS_SM}px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {t.BORDER_STRONG}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- menus --------------------------------------------------- */
QMenu {{ background: {t.SURFACE}; color: {t.TEXT_PRIMARY}; border: 1px solid {t.BORDER}; padding: {t.SPACE_SM}px; }}
QMenu::item {{ padding: {t.SPACE_SM}px {t.SPACE_MD}px; border-radius: {t.RADIUS_SM}px; }}
QMenu::item:selected {{ background: {t.HOVER_BG}; color: {t.TEXT_ACCENT}; }}
"""
