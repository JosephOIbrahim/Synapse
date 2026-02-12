"""
Synapse Design System — Qt Stylesheet Generator

Generates QSS (Qt Style Sheets) from design tokens for the Synapse panel.
Houdini 21+ uses PySide6/Qt6; older versions use PySide2/Qt5.

Usage:
    from synapse_styles import generate_stylesheet, STATUS_STYLES
    widget.setStyleSheet(generate_stylesheet())
"""

import sys
import os

# Allow importing tokens from the design directory
_design_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
if _design_dir not in sys.path:
    sys.path.insert(0, _design_dir)

from tokens import (
    SIGNAL, VOID, NEAR_BLACK, CARBON, GRAPHITE, SLATE, SILVER, BONE, WHITE,
    FIRE, GROW, WARN, ERROR,
    FONT_MONO, FONT_MONO_FALLBACKS, FONT_SANS, FONT_SANS_FALLBACKS,
    SIZE_LABEL, SIZE_SMALL, SIZE_UI, SIZE_BODY, SIZE_TITLE, SIZE_HERO,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    STATES,
)


def _font_family(primary, fallbacks):
    """Build a CSS font-family string."""
    fonts = [primary] + list(fallbacks)
    return ", ".join(f'"{f}"' for f in fonts)


MONO_FAMILY = _font_family(FONT_MONO, FONT_MONO_FALLBACKS)
SANS_FAMILY = _font_family(FONT_SANS, FONT_SANS_FALLBACKS)


def generate_stylesheet():
    """Generate the full QSS stylesheet for the Synapse panel."""
    return f"""
/* ═══════════════════════════════════════════════════════
   SYNAPSE DESIGN SYSTEM — Qt Stylesheet
   Generated from design tokens. Do not edit directly.
   ═══════════════════════════════════════════════════════ */

/* ── Base Panel ──────────────────────────────────────── */

QWidget#synapse_panel {{
    background-color: {NEAR_BLACK};
    color: {BONE};
    font-family: {SANS_FAMILY};
    font-size: {SIZE_BODY}px;
}}

/* ── Title Bar ───────────────────────────────────────── */

QFrame#title_bar {{
    background-color: {VOID};
    border-bottom: 1px solid {GRAPHITE};
    padding: {SPACE_SM}px {SPACE_MD}px;
    min-height: 64px;
    max-height: 64px;
}}

QLabel#title_label {{
    color: {WHITE};
    font-family: {MONO_FAMILY};
    font-size: {SIZE_HERO}px;
    font-weight: 600;
    letter-spacing: 4px;
}}

QLabel#version_label {{
    color: {SLATE};
    font-family: {MONO_FAMILY};
    font-size: {SIZE_LABEL}px;
}}

/* ── Status Bar ──────────────────────────────────────── */

QFrame#status_bar {{
    background-color: {CARBON};
    border-bottom: 1px solid {GRAPHITE};
    padding: {SPACE_SM}px {SPACE_MD}px;
    min-height: 48px;
    max-height: 48px;
}}

QLabel#status_dot {{
    font-size: 18px;
    min-width: 18px;
    max-width: 18px;
}}

QLabel#status_label {{
    color: {SILVER};
    font-family: {MONO_FAMILY};
    font-size: {SIZE_SMALL}px;
    letter-spacing: 1px;
}}

QLabel#status_detail {{
    color: {SLATE};
    font-family: {MONO_FAMILY};
    font-size: {SIZE_LABEL}px;
}}

/* ── Tool Grid ───────────────────────────────────────── */

QFrame#tool_grid {{
    background-color: transparent;
    padding: {SPACE_SM}px;
}}

QPushButton.tool_button {{
    background-color: {CARBON};
    color: {BONE};
    border: 1px solid {GRAPHITE};
    border-radius: 4px;
    font-family: {MONO_FAMILY};
    font-size: {SIZE_UI}px;
    padding: {SPACE_SM}px;
    min-height: 80px;
    text-align: center;
}}

QPushButton.tool_button:hover {{
    background-color: #484848;
    border-color: {SIGNAL};
    color: {WHITE};
}}

QPushButton.tool_button:pressed {{
    background-color: rgba(0, 212, 255, 0.15);
    border-color: {SIGNAL};
    color: {SIGNAL};
}}

QPushButton.tool_button:disabled {{
    background-color: {NEAR_BLACK};
    color: {SLATE};
    border-color: {GRAPHITE};
}}

/* ── Activity Log ────────────────────────────────────── */

QFrame#activity_frame {{
    background-color: transparent;
    padding: 0px {SPACE_SM}px;
}}

QLabel#activity_header {{
    color: {SLATE};
    font-family: {MONO_FAMILY};
    font-size: {SIZE_LABEL}px;
    letter-spacing: 2px;
    padding: {SPACE_XS}px 0px;
}}

QTextEdit#activity_log {{
    background-color: {VOID};
    color: {SILVER};
    border: 1px solid {GRAPHITE};
    border-radius: 4px;
    font-family: {MONO_FAMILY};
    font-size: {SIZE_SMALL}px;
    padding: {SPACE_SM}px;
    selection-background-color: rgba(0, 212, 255, 0.3);
    selection-color: {WHITE};
}}

QScrollBar:vertical {{
    background-color: {VOID};
    width: 10px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: {GRAPHITE};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {SLATE};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background-color: transparent;
}}

/* ── Connection Controls ─────────────────────────────── */

QFrame#connection_frame {{
    background-color: {CARBON};
    border-top: 1px solid {GRAPHITE};
    padding: {SPACE_SM}px {SPACE_MD}px;
    min-height: 52px;
    max-height: 52px;
}}

QPushButton#connect_button {{
    background-color: transparent;
    color: {SIGNAL};
    border: 1px solid {SIGNAL};
    border-radius: 3px;
    font-family: {MONO_FAMILY};
    font-size: {SIZE_SMALL}px;
    padding: {SPACE_XS}px {SPACE_SM}px;
    min-width: 120px;
}}

QPushButton#connect_button:hover {{
    background-color: rgba(0, 212, 255, 0.1);
}}

QPushButton#connect_button:pressed {{
    background-color: rgba(0, 212, 255, 0.2);
}}

QPushButton#ws_path_button {{
    background-color: transparent;
    color: {SLATE};
    border: 1px solid {GRAPHITE};
    border-radius: 3px;
    font-family: {MONO_FAMILY};
    font-size: {SIZE_LABEL}px;
    padding: {SPACE_XS}px {SPACE_SM}px;
}}

QPushButton#ws_path_button:hover {{
    color: {SIGNAL};
    border-color: {SIGNAL};
    background-color: rgba(0, 212, 255, 0.1);
}}

QPushButton#ws_path_button:pressed {{
    background-color: rgba(0, 212, 255, 0.2);
}}

/* ── Tooltip ─────────────────────────────────────────── */

QToolTip {{
    background-color: {CARBON};
    color: {BONE};
    border: 1px solid {GRAPHITE};
    font-family: {SANS_FAMILY};
    font-size: {SIZE_SMALL}px;
    padding: {SPACE_XS}px {SPACE_SM}px;
}}
"""


# ── Status-specific styles ──────────────────────────────

STATUS_STYLES = {}
for state_name, state_info in STATES.items():
    STATUS_STYLES[state_name] = f"""
        QLabel#status_dot {{ color: {state_info['color']}; }}
        QLabel#status_label {{ color: {state_info['color']}; }}
    """


# ── Convenience: animation keyframes as color tuples ────

STATUS_COLORS = {name: info["color"] for name, info in STATES.items()}


if __name__ == "__main__":
    print("=" * 50)
    print("  SYNAPSE QSS STYLESHEET")
    print("=" * 50)
    qss = generate_stylesheet()
    print(f"\nStylesheet length: {len(qss)} characters")
    print(f"Status styles: {list(STATUS_STYLES.keys())}")
    print("\n--- Preview (first 500 chars) ---")
    print(qss[:500])
    print("...")
