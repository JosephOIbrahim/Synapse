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
QWidget#DsRoot {{
    background: {t.PANEL};
    color: {t.TEXT_PRIMARY};
    font-size: {s(t.SIZE_BODY)}px;
}}
QWidget#DsSection {{ background: {t.PANEL}; }}
QTextBrowser {{ background: {t.GROUND}; border: none; }}
/* Cohere 'gradient atmosphere' — a faint cool→warm wash across the header. */
QWidget#DsHeader {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #2B2E33, stop:0.5 {t.PANEL}, stop:1 #332E2C);
}}
QToolTip {{
    background: {t.SURFACE}; color: {t.TEXT_PRIMARY};
    border: 1px solid {t.BORDER}; padding: {t.SPACE_XS}px {t.SPACE_SM}px;
    border-radius: {t.RADIUS_SM}px; font-size: {s(t.SIZE_SMALL)}px;
}}

/* ---- buttons (variant via dynamic property) ------------------ */
QPushButton#DsButton {{
    border-radius: {t.RADIUS_MD}px;
    padding: {t.SPACE_SM}px {t.SPACE_MD}px;
    font-size: {s(t.SIZE_UI)}px;
    font-weight: 600;
    border: 1px solid transparent;
}}
QPushButton#DsButton[variant="primary"] {{
    background: {t.SIGNAL}; color: {t.TEXT_ON_ACCENT};
}}
QPushButton#DsButton[variant="primary"]:hover  {{ background: {t.SIGNAL_HOVER}; }}
QPushButton#DsButton[variant="primary"]:pressed {{ background: {t.SIGNAL_PRESS}; }}
QPushButton#DsButton[variant="secondary"] {{
    background: {t.SURFACE}; color: {t.TEXT_PRIMARY}; border: 1px solid {t.BORDER};
}}
QPushButton#DsButton[variant="secondary"]:hover  {{ background: {t.RAISED}; border-color: {t.BORDER_STRONG}; }}
QPushButton#DsButton[variant="secondary"]:pressed {{ background: {t.PRESS_BG}; }}
QPushButton#DsButton[variant="ghost"] {{
    background: transparent; color: {t.TEXT_SECONDARY}; border: 1px solid transparent;
}}
QPushButton#DsButton[variant="ghost"]:hover  {{ background: {t.HOVER_BG}; color: {t.TEXT_PRIMARY}; }}
QPushButton#DsButton[variant="danger"] {{
    background: transparent; color: {t.ERROR}; border: 1px solid {t.ERROR};
}}
QPushButton#DsButton[variant="danger"]:hover  {{ background: {t.STATE_TINTS["error"]}; }}
QPushButton#DsButton:disabled {{ background: {t.DISABLED_BG}; color: {t.TEXT_DISABLED}; border-color: transparent; }}

/* ---- tabs: underline on a baseline track (v9 call 1) --------- */
/* Retires the filled-pill active state: tabs read as text on a shared 2px
   baseline; the active tab lights its rule + text. Flat, native font; the
   active accent is the only chrome. */
QPushButton#DsPill {{
    background: none; color: {t.TEXT_SECONDARY};
    border: none; border-bottom: 2px solid transparent; border-radius: 0;
    padding: {t.SPACE_XS}px {t.SPACE_MD}px;
    font-size: {s(t.SIZE_UI + 2)}px; font-weight: 500;
}}
QPushButton#DsPill:hover  {{ color: {t.TEXT_ACCENT}; }}
QPushButton#DsPill:disabled {{ color: {t.TEXT_DISABLED}; }}
QPushButton#DsPill[active="true"] {{
    color: {t.TEXT_ACCENT}; border-bottom: 2px solid {t.SIGNAL};
}}

/* ---- engine selector: a segmented control (model selection must be
   APPARENT, not buried in the ⋯ menu) — the active engine is a SIGNAL fill --- */
QPushButton#DsSeg {{
    background: {t.SURFACE}; color: {t.TEXT_SECONDARY};
    border: 1px solid {t.BORDER}; border-radius: {t.RADIUS_PILL}px;
    padding: 3px {t.SPACE_MD}px;
    font-size: {s(t.SIZE_SMALL)}px; font-weight: 600;
}}
QPushButton#DsSeg:hover {{ color: {t.TEXT_PRIMARY}; border-color: {t.BORDER_STRONG}; }}
QPushButton#DsSeg[active="true"] {{
    background: {t.SIGNAL}; color: {t.TEXT_ON_ACCENT}; border-color: {t.SIGNAL};
}}

/* ---- type-set verbs (Direct act bar + Review actions) — Mile 7 --- */
/* Verbs read as type, not buttons: flat, mono, the chrome recedes. */
QPushButton#DsVerb {{
    background: transparent; border: none; padding: 2px 0;
    color: {t.TEXT_SECONDARY};
    font-size: {s(11)}px;
}}
QPushButton#DsVerb:hover {{ color: {t.TEXT_ACCENT}; }}
QPushButton#DsVerb[tone="ok"]     {{ color: {t.GROW}; }}
QPushButton#DsVerb[tone="hot"]    {{ color: {t.WARM}; }}
QPushButton#DsVerb[tone="accent"] {{ color: {t.TEXT_ACCENT}; }}

/* ---- two-axis palette chips (⌘K · DO × WHERE) ---------------- */
QPushButton#DsChip {{
    background: transparent; color: {t.TEXT_TERTIARY};
    border: none; border-radius: {t.RADIUS_SM}px; padding: 3px 8px;
    font-size: {s(10)}px;
}}
QPushButton#DsChip:hover {{ color: {t.TEXT_SECONDARY}; }}
QPushButton#DsChip[active="true"] {{ background: {t.SIGNAL_TINT}; color: {t.TEXT_ACCENT}; }}

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

/* ---- text inputs (v9 call 2: darker field-inset grey) -------- */
QTextEdit#DsInput, QLineEdit#DsField {{
    background: {t.FIELD_INSET}; color: {t.TEXT_PRIMARY};
    border: 1px solid {t.BORDER}; border-radius: {t.RADIUS_MD}px;
    padding: {t.SPACE_SM}px; font-size: {s(t.SIZE_UI)}px;
    selection-background-color: {t.SIGNAL_TINT_STRONG};
}}
QTextEdit#DsInput:focus, QLineEdit#DsField:focus {{ border-color: {t.SIGNAL}; }}

/* ---- role labels (color; font set in Python from TYPE_ROLES) -- */
QLabel[role="title"]   {{ color: {t.TEXT_BRIGHT}; }}
QLabel[role="body"]    {{ color: {t.TEXT_PRIMARY}; }}
QLabel[role="caption"] {{ color: {t.TEXT_TERTIARY}; }}
QLabel[role="label"]   {{ color: {t.TEXT_SECONDARY}; }}
QLabel[role="accent"]  {{ color: {t.TEXT_ACCENT}; }}

/* ---- progress ------------------------------------------------ */
QProgressBar#DsProgress {{
    background: {t.SURFACE}; border: none; border-radius: {t.RADIUS_SM}px;
    height: {t.SPACE_XS}px; text-align: center;
}}
QProgressBar#DsProgress::chunk {{ background: {t.SIGNAL}; border-radius: {t.RADIUS_SM}px; }}

/* ---- scrollbars (quiet) -------------------------------------- */
QScrollBar:vertical {{ background: transparent; width: {t.SPACE_SM}px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t.RAISED}; border-radius: {t.RADIUS_SM}px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {t.BORDER_STRONG}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- menus --------------------------------------------------- */
QMenu {{ background: {t.SURFACE}; color: {t.TEXT_PRIMARY}; border: 1px solid {t.BORDER}; padding: {t.SPACE_XS}px; }}
QMenu::item {{ padding: {t.SPACE_XS}px {t.SPACE_MD}px; border-radius: {t.RADIUS_SM}px; }}
QMenu::item:selected {{ background: {t.HOVER_BG}; color: {t.TEXT_ACCENT}; }}
"""
