"""
Synapse Design System — Qt Stylesheet Generator

Generates QSS (Qt Style Sheets) from design tokens for the Synapse panel.
Houdini uses PySide2/Qt5 — all styles target that environment.

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

/* ── Unified Header ──────────────────────────────────── */

QWidget#panel_header {{
    background-color: {VOID};
    border-bottom: 1px solid {GRAPHITE};
    min-height: 36px;
    max-height: 36px;
}}

QLabel#title_label {{
    color: {WHITE};
    font-family: {MONO_FAMILY};
    font-size: {SIZE_TITLE}px;
    font-weight: 600;
    letter-spacing: 2px;
}}

QLabel#status_dot {{
    font-size: 8px;
    min-width: 8px;
    max-width: 8px;
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

QToolButton#overflow_button {{
    background-color: transparent;
    color: {SILVER};
    border: none;
    font-family: {MONO_FAMILY};
    font-size: {SIZE_UI}px;
    padding: 2px {SPACE_SM}px;
    min-width: 28px;
}}

QToolButton#overflow_button:hover {{
    color: {WHITE};
    background-color: {GRAPHITE};
    border-radius: 3px;
}}

QToolButton#overflow_button::menu-indicator {{
    image: none;
}}

/* ── Overflow Menu ───────────────────────────────────── */

QMenu#overflow_menu {{
    background-color: {CARBON};
    color: {BONE};
    border: 1px solid {GRAPHITE};
    border-radius: 4px;
    font-family: {MONO_FAMILY};
    font-size: {SIZE_SMALL}px;
    padding: {SPACE_XS}px 0px;
}}

QMenu#overflow_menu::item {{
    padding: {SPACE_SM}px {SPACE_MD}px;
}}

QMenu#overflow_menu::item:selected {{
    background-color: {GRAPHITE};
    color: {SIGNAL};
}}

/* ── Activity Log (collapsible) ──────────────────────── */

QFrame#activity_frame {{
    background-color: transparent;
    padding: 0px {SPACE_SM}px;
}}

QPushButton#activity_toggle {{
    background-color: transparent;
    color: {SLATE};
    border: none;
    font-family: {MONO_FAMILY};
    font-size: {SIZE_LABEL}px;
    letter-spacing: 2px;
    padding: {SPACE_XS}px 0px;
    text-align: left;
}}

QPushButton#activity_toggle:hover {{
    color: {SILVER};
}}

QTextEdit#activity_log {{
    background-color: {VOID};
    color: {SILVER};
    border: 1px solid {GRAPHITE};
    border-radius: 4px;
    font-family: {MONO_FAMILY};
    font-size: {SIZE_SMALL}px;
    padding: {SPACE_SM}px;
    max-height: 150px;
    selection-background-color: rgba(0, 212, 255, 0.3);
    selection-color: {WHITE};
}}

QScrollBar:vertical {{
    background-color: {VOID};
    width: 6px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: {GRAPHITE};
    border-radius: 3px;
    min-height: 20px;
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

/* ── Chat Input & Send (WhatsApp pill) ─────────────── */

QPlainTextEdit#chat_input {{
    background-color: {CARBON};
    color: {BONE};
    border: 1px solid {GRAPHITE};
    border-radius: 12px;
    font-family: {MONO_FAMILY};
    font-size: {SIZE_BODY}px;
    padding: 8px {SPACE_MD}px;
    min-height: 36px;
}}

QPlainTextEdit#chat_input:focus {{
    border-color: {SLATE};
}}

QPushButton#send_button {{
    background-color: {SIGNAL};
    color: {VOID};
    border: none;
    border-radius: 18px;
    font-family: {MONO_FAMILY};
    font-size: {SIZE_SMALL}px;
    font-weight: 600;
    padding: 10px 16px;
    min-width: 40px;
    min-height: 36px;
    max-height: 36px;
}}

QPushButton#send_button:hover {{
    background-color: #33DFFF;
}}

QPushButton#send_button:pressed {{
    background-color: #00A8CC;
}}

QPushButton#send_button:disabled {{
    color: {SLATE};
    border-color: {GRAPHITE};
}}

/* ── Stop Button ────────────────────────────────────── */

QPushButton#stop_button {{
    background-color: transparent;
    color: {ERROR};
    border: none;
    border-radius: 8px;
    font-size: 16px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    padding: 0px;
}}

QPushButton#stop_button:hover {{
    background-color: {CARBON};
    color: {WHITE};
}}

QPushButton#stop_button:pressed {{
    background-color: {GRAPHITE};
    color: {ERROR};
}}

/* ── Zoom Buttons (A- / A+) ────────────────────────── */

QPushButton#zoom_button {{
    background-color: transparent;
    color: {SLATE};
    border: none;
    border-radius: 3px;
    font-family: {MONO_FAMILY};
    font-size: {SIZE_LABEL}px;
    font-weight: 600;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    padding: 0px;
}}

QPushButton#zoom_button:hover {{
    color: {WHITE};
    background-color: {GRAPHITE};
}}

QPushButton#zoom_button:pressed {{
    color: {SIGNAL};
    background-color: {GRAPHITE};
}}

/* ── Attach Button ──────────────────────────────────── */

QPushButton#attach_button {{
    background-color: transparent;
    color: {SILVER};
    border: none;
    border-radius: 8px;
    font-size: 18px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    padding: 0px;
}}

QPushButton#attach_button:hover {{
    background-color: {CARBON};
    color: {WHITE};
}}

QPushButton#attach_button:pressed {{
    background-color: {GRAPHITE};
    color: {SIGNAL};
}}

/* ── Connection Controls (compact footer) ────────────── */

QFrame#connection_frame {{
    background-color: {CARBON};
    border-top: 1px solid {GRAPHITE};
    padding: {SPACE_XS}px {SPACE_MD}px;
    min-height: 28px;
    max-height: 28px;
}}

QPushButton#connect_button {{
    background-color: transparent;
    color: {SIGNAL};
    border: 1px solid {SIGNAL};
    border-radius: 3px;
    font-family: {MONO_FAMILY};
    font-size: {SIZE_SMALL}px;
    padding: 2px {SPACE_SM}px;
    min-width: 72px;
}}

QPushButton#connect_button:hover {{
    background-color: rgba(0, 212, 255, 0.1);
}}

QPushButton#connect_button:pressed {{
    background-color: rgba(0, 212, 255, 0.2);
}}

QLabel#version_label {{
    color: {SLATE};
    font-family: {MONO_FAMILY};
    font-size: {SIZE_LABEL}px;
}}

QLabel#port_label {{
    color: {SLATE};
    font-family: {MONO_FAMILY};
    font-size: {SIZE_LABEL}px;
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
