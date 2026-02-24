"""Panel stylesheets and transition helpers.

Generates Qt stylesheets from design tokens. Import ``get_hda_stylesheet()``
for HDA mode views, ``animate_stack_transition()`` for smooth page switches.
"""

from . import tokens as t


def get_hda_stylesheet():
    """Qt stylesheet for HDA mode views. Extends base panel styling."""
    return (
        # === HDA Mode Container ===
        "QWidget#HdaModeWidget {{"
        "  background: {VOID};"
        "}}".format(VOID=t.VOID)

        # === Describe View ===
        + " QTextEdit#HdaPromptInput {{"
        "  background: {bg};"
        "  color: {fg};"
        "  border: 1px solid {border};"
        "  border-radius: 4px;"
        "  padding: 12px;"
        "  font-family: {font};"
        "  font-size: {sz}px;"
        "  selection-background-color: {sel};"
        "}}".format(
            bg=t.HDA_INPUT_BG, fg=t.BONE, border=t.HDA_INPUT_BORDER,
            font=t.FONT_SANS, sz=t.SIZE_BODY, sel=t.HDA_INPUT_FOCUS,
        )
        + " QTextEdit#HdaPromptInput:focus {{"
        "  border-color: {sig};"
        "}}".format(sig=t.SIGNAL)

        + " QComboBox#HdaContextSelector {{"
        "  background: {bg};"
        "  color: {fg};"
        "  border: 1px solid {border};"
        "  border-radius: 4px;"
        "  padding: 6px 12px;"
        "  font-family: {font};"
        "  font-size: {sz}px;"
        "}}".format(
            bg=t.CARBON, fg=t.SILVER, border=t.GRAPHITE,
            font=t.FONT_MONO, sz=t.SIZE_LABEL,
        )

        + " QPushButton#HdaGenerateBtn {{"
        "  background: {bg};"
        "  color: {fg};"
        "  border: none;"
        "  border-radius: 4px;"
        "  padding: 10px 24px;"
        "  font-family: {font};"
        "  font-size: {sz}px;"
        "  font-weight: 700;"
        "  letter-spacing: 1px;"
        "}}".format(
            bg=t.STATE_DESCRIBE, fg=t.VOID,
            font=t.FONT_MONO, sz=t.SIZE_LABEL,
        )
        + " QPushButton#HdaGenerateBtn:hover {{"
        "  background: {bg}CC;"
        "}}".format(bg=t.STATE_DESCRIBE)
        + " QPushButton#HdaGenerateBtn:pressed {{"
        "  background: {bg}99;"
        "}}".format(bg=t.STATE_DESCRIBE)

        # === Building View ===
        + " QWidget#BuildingView {{"
        "  background: {bg};"
        "}}".format(bg=t.HDA_PROGRESS_BG)

        + " QLabel#StageLabel {{"
        "  font-family: {font};"
        "  font-size: {sz}px;"
        "  letter-spacing: 0.5px;"
        "}}".format(font=t.FONT_MONO, sz=t.SIZE_LABEL)

        + " QProgressBar#HdaProgressBar {{"
        "  background: {bg};"
        "  border: none;"
        "  border-radius: 3px;"
        "  height: 6px;"
        "}}".format(bg=t.HDA_PROGRESS_TRACK)
        + " QProgressBar#HdaProgressBar::chunk {{"
        "  background: {bg};"
        "  border-radius: 3px;"
        "}}".format(bg=t.STATE_BUILDING)

        # === Result View ===
        + " QLabel#NodePathLabel {{"
        "  font-family: {font};"
        "  font-size: {sz}px;"
        "  color: {fg};"
        "  padding: 8px 12px;"
        "  background: {bg};"
        "  border-radius: 4px;"
        "}}".format(
            font=t.FONT_MONO, sz=t.SIZE_BODY,
            fg=t.GROW, bg=t.HDA_RESULT_SUCCESS_BG,
        )

        + " QTableWidget#ParamTable {{"
        "  background: {bg};"
        "  color: {fg};"
        "  border: 1px solid {border};"
        "  gridline-color: {border};"
        "  font-family: {font};"
        "  font-size: {sz}px;"
        "}}".format(
            bg=t.CARBON, fg=t.SILVER, border=t.GRAPHITE,
            font=t.FONT_MONO, sz=t.SIZE_LABEL,
        )
        + " QTableWidget#ParamTable::item {{"
        "  padding: 4px 8px;"
        "}}"

        + " QHeaderView::section {{"
        "  background: {bg};"
        "  color: {fg};"
        "  font-weight: 700;"
        "  padding: 4px 8px;"
        "  border: none;"
        "}}".format(bg=t.GRAPHITE, fg=t.BONE)

        # === Mode Toggle ===
        + " QPushButton#ModeToggleActive {{"
        "  background: {bg};"
        "  border: 1px solid {border};"
        "  color: {fg};"
        "  border-radius: 4px;"
        "  padding: 4px 12px;"
        "  font-family: {font};"
        "  font-size: {sz}px;"
        "  font-weight: 700;"
        "}}".format(
            bg=t.MODE_ACTIVE_BG, border=t.MODE_ACTIVE_BORDER,
            fg=t.SIGNAL, font=t.FONT_MONO, sz=t.SIZE_LABEL,
        )

        + " QPushButton#ModeToggleInactive {{"
        "  background: {bg};"
        "  border: 1px solid {border};"
        "  color: {fg};"
        "  border-radius: 4px;"
        "  padding: 4px 12px;"
        "  font-family: {font};"
        "  font-size: {sz}px;"
        "}}".format(
            bg=t.MODE_INACTIVE_BG, border=t.MODE_INACTIVE_BORDER,
            fg=t.SLATE, font=t.FONT_MONO, sz=t.SIZE_LABEL,
        )
        + " QPushButton#ModeToggleInactive:hover {{"
        "  border-color: {border};"
        "  color: {fg};"
        "}}".format(border=t.SILVER, fg=t.SILVER)

        # === Action Buttons ===
        + " QPushButton#HdaActionBtn {{"
        "  background: {bg};"
        "  color: {fg};"
        "  border: 1px solid {border};"
        "  border-radius: 4px;"
        "  padding: 8px 16px;"
        "  font-family: {font};"
        "  font-size: {sz}px;"
        "}}".format(
            bg=t.CARBON, fg=t.SILVER, border=t.GRAPHITE,
            font=t.FONT_MONO, sz=t.SIZE_LABEL,
        )
        + " QPushButton#HdaActionBtn:hover {{"
        "  border-color: {border};"
        "  color: {fg};"
        "}}".format(border=t.SIGNAL + "66", fg=t.BONE)

        + " QPushButton#CancelBtn {{"
        "  background: transparent;"
        "  color: {fg};"
        "  border: 1px solid {border};"
        "  border-radius: 4px;"
        "  padding: 8px 16px;"
        "  font-family: {font};"
        "  font-size: {sz}px;"
        "}}".format(
            fg=t.SLATE, border=t.GRAPHITE,
            font=t.FONT_MONO, sz=t.SIZE_LABEL,
        )
        + " QPushButton#CancelBtn:hover {{"
        "  color: {fg};"
        "  border-color: {border};"
        "}}".format(fg=t.ERROR_COLOR, border=t.ERROR_COLOR + "66")
    )


# ── Chat Panel Component Stylesheets ──────────────────────────────────


def get_quick_action_button_stylesheet():
    """Quick action button: matches main panel tool_button style."""
    return (
        "QPushButton {{"
        "  background: {bg};"
        "  color: {fg};"
        "  border: 1px solid {border};"
        "  border-radius: 4px;"
        "  padding: {pad}px;"
        "  min-height: 36px;"
        "  font-family: '{mono}', 'Consolas', monospace;"
        "  font-size: {sz}px;"
        "}}"
        "QPushButton:hover {{"
        "  background: {hover};"
        "  border-color: {accent};"
        "  color: {white};"
        "}}"
        "QPushButton:pressed {{"
        "  background: rgba(0, 212, 255, 0.15);"
        "  border-color: {accent};"
        "  color: {accent};"
        "}}".format(
            bg=t.CARBON, fg=t.BONE, border=t.GRAPHITE,
            sz=t.SIZE_SMALL, pad=t.SPACE_SM, hover=t.HOVER,
            accent=t.SIGNAL, white=t.WHITE, mono=t.FONT_MONO,
        )
    )


def get_input_stylesheet():
    """Standard text input field: rounded, cyan focus border."""
    return (
        "QLineEdit {{"
        "  background: {bg};"
        "  color: {fg};"
        "  border: 1px solid {border};"
        "  border-radius: 6px;"
        "  padding: 8px 12px;"
        "  font-family: '{sans}', 'Segoe UI', sans-serif;"
        "  font-size: {sz}px;"
        "}}"
        "QLineEdit:focus {{"
        "  border: 1px solid {accent};"
        "}}".format(
            bg=t.VOID, fg=t.BONE, border=t.GRAPHITE,
            sz=t.SIZE_UI, accent=t.SIGNAL, sans=t.FONT_SANS,
        )
    )


def get_send_button_stylesheet():
    """Primary send button: solid cyan background, mono bold."""
    return (
        "QPushButton {{"
        "  background: {accent};"
        "  color: {bg};"
        "  border: none;"
        "  border-radius: 6px;"
        "  padding: 8px 20px;"
        "  font-family: '{mono}', 'Consolas', monospace;"
        "  font-size: {sz}px;"
        "  font-weight: 700;"
        "  letter-spacing: 1px;"
        "}}"
        "QPushButton:hover {{"
        "  background: {hover};"
        "}}"
        "QPushButton:pressed {{"
        "  background: {pressed};"
        "}}".format(
            accent=t.SIGNAL, bg=t.VOID, sz=t.SIZE_UI,
            hover=t.SIGNAL_HOVER, pressed=t.SIGNAL_PRESS,
            mono=t.FONT_MONO,
        )
    )


def get_connect_button_stylesheet():
    """Outlined connect/disconnect button: cyan border, transparent bg."""
    return (
        "QPushButton#connect_button {{"
        "  background: transparent;"
        "  color: {accent};"
        "  border: 1px solid {accent};"
        "  border-radius: 3px;"
        "  font-family: '{mono}', 'Consolas', monospace;"
        "  font-size: {sz}px;"
        "  padding: 4px 12px;"
        "  min-width: 100px;"
        "}}"
        "QPushButton#connect_button:hover {{"
        "  background: rgba(0, 212, 255, 0.1);"
        "}}"
        "QPushButton#connect_button:pressed {{"
        "  background: rgba(0, 212, 255, 0.2);"
        "}}".format(
            accent=t.SIGNAL, mono=t.FONT_MONO, sz=t.SIZE_SMALL,
        )
    )


def get_ws_url_button_stylesheet():
    """WebSocket URL button: subtle outlined, cyan hover."""
    return (
        "QPushButton#ws_path_button {{"
        "  background: transparent;"
        "  color: {slate};"
        "  border: 1px solid {border};"
        "  border-radius: 3px;"
        "  font-family: '{mono}', 'Consolas', monospace;"
        "  font-size: {sz}px;"
        "  padding: 4px 8px;"
        "}}"
        "QPushButton#ws_path_button:hover {{"
        "  color: {accent};"
        "  border-color: {accent};"
        "  background: rgba(0, 212, 255, 0.1);"
        "}}"
        "QPushButton#ws_path_button:pressed {{"
        "  background: rgba(0, 212, 255, 0.2);"
        "}}".format(
            slate=t.SLATE, border=t.GRAPHITE, mono=t.FONT_MONO,
            sz=t.SIZE_LABEL, accent=t.SIGNAL,
        )
    )


def get_status_dot_stylesheet(color):
    """Status dot indicator with given color."""
    return "color: {c}; font-size: 18px; border: none;".format(c=color)


def get_status_label_stylesheet(color):
    """Mono-font status label with given color."""
    return (
        "color: {c}; font-family: '{mono}', 'Consolas', monospace;"
        " font-size: {sz}px; letter-spacing: 1px;"
        " border: none;".format(
            c=color, mono=t.FONT_MONO, sz=t.SIZE_SMALL,
        )
    )


# ── Context Bar Stylesheets ───────────────────────────────────────────


def get_context_bar_stylesheet():
    """Context bar container: graphite bg, carbon top-border."""
    return (
        "background: {bg}; border-top: 1px solid {border};".format(
            bg=t.GRAPHITE, border=t.CARBON
        )
    )


def get_context_bar_path_stylesheet():
    """Context bar path label: mono font, SIGNAL cyan."""
    return (
        "color: {c}; font-size: {s}px; font-family: '{mono}', "
        "'Consolas', monospace; letter-spacing: 0.5px;"
        " border: none;".format(
            c=t.SIGNAL, s=t.SIZE_SMALL, mono=t.FONT_MONO
        )
    )


def get_context_bar_dim_label_stylesheet():
    """Context bar dim label: selection count, frame, connection text."""
    return (
        "color: {c}; font-size: {s}px; border: none;".format(
            c=t.TEXT_DIM, s=t.SIZE_SMALL
        )
    )


def get_context_bar_led_stylesheet(color):
    """Context bar LED indicator with given color."""
    return (
        "background: {c}; border-radius: 6px; border: none;".format(c=color)
    )


def get_context_bar_conn_label_stylesheet(color):
    """Context bar connection label with given color."""
    return (
        "color: {c}; font-size: {s}px; border: none;".format(
            c=color, s=t.SIZE_SMALL
        )
    )


def get_evolution_label_stylesheet(color):
    """Evolution stage label with given stage color."""
    return (
        "color: {c}; font-size: {s}px; font-family: '{mono}', "
        "'Consolas', monospace; font-weight: 700; border: none;".format(
            c=color, s=t.SIZE_SMALL, mono=t.FONT_MONO
        )
    )


def get_project_name_stylesheet():
    """Project name label in context bar."""
    return (
        "color: {c}; font-size: {s}px; font-family: '{mono}', "
        "'Consolas', monospace; border: none;".format(
            c=t.SILVER, s=t.SIZE_SMALL, mono=t.FONT_MONO
        )
    )


# ── HDA Views Inline Style Helpers ───────────────────────────────────


def get_section_label_stylesheet():
    """HDA Describe view section label: mono, SIGNAL cyan, letter-spaced."""
    return (
        "color: {sig}; font-size: 10px; "
        "font-family: monospace; letter-spacing: 2px;".format(sig=t.SIGNAL)
    )


def get_option_label_stylesheet(color=None):
    """HDA Describe view option/checkbox label: mono, given color."""
    c = color or t.SLATE
    return (
        "color: {c}; font-family: monospace; font-size: 11px;".format(c=c)
    )


def get_stage_label_stylesheet():
    """HDA Building view stage label: mono, BONE, bold."""
    return (
        "color: {c}; font-family: monospace; font-size: 14px; "
        "font-weight: 700;".format(c=t.BONE)
    )


def get_stage_dot_stylesheet(color, size=8):
    """HDA Building view stage dot: colored circle at given size."""
    return "color: {c}; font-size: {s}px;".format(c=color, s=size)


def get_detail_label_stylesheet():
    """HDA Building view detail text: mono, SLATE, small."""
    return (
        "color: {c}; font-family: monospace; font-size: 10px;".format(
            c=t.SLATE
        )
    )


def get_result_status_stylesheet(color):
    """HDA Result view status header: mono, bold, given color."""
    return (
        "color: {c}; font-family: monospace; font-size: 14px; "
        "font-weight: 700;".format(c=color)
    )


def get_result_path_stylesheet(fg_color, bg_color):
    """HDA Result view node path label: mono, colored bg."""
    return (
        "color: {fg}; font-family: monospace; font-size: 12px; "
        "padding: 8px 12px; background: {bg}; "
        "border-radius: 4px;".format(fg=fg_color, bg=bg_color)
    )


def get_validation_label_stylesheet():
    """HDA Result view validation summary: mono, SLATE, small."""
    return (
        "color: {c}; font-family: monospace; font-size: 10px;".format(
            c=t.SLATE
        )
    )


def get_root_widget_stylesheet():
    """Root panel QWidget: matches main Synapse panel bg and font."""
    return (
        "QWidget {{ background: {bg}; "
        "font-family: '{sans}', 'Segoe UI', sans-serif; "
        "color: {fg}; }}".format(bg=t.NEAR_BLACK, sans=t.FONT_SANS, fg=t.BONE)
    )


def get_section_container_stylesheet():
    """Container widget for quick actions row or input area."""
    return (
        "background: transparent; border-top: 1px solid {border};".format(
            border=t.GRAPHITE
        )
    )


def get_connection_frame_stylesheet():
    """Connection bar frame: CARBON bg, GRAPHITE top border, matched height."""
    return (
        "QWidget#connection_frame {{"
        "  background: {bg};"
        "  border-top: 1px solid {border};"
        "  min-height: 52px;"
        "  max-height: 52px;"
        "}}".format(bg=t.CARBON, border=t.GRAPHITE)
    )


def get_mode_toolbar_stylesheet():
    """Mode toggle toolbar: CARBON bg, GRAPHITE bottom border (matches status bar)."""
    return (
        "background: {bg}; border-bottom: 1px solid {border};".format(
            bg=t.CARBON, border=t.GRAPHITE
        )
    )


def get_chat_display_stylesheet():
    """Chat display QTextBrowser: spacious padding for conversational feel."""
    return (
        "QTextBrowser {{"
        "  background: {bg};"
        "  color: {fg};"
        "  font-family: '{sans}', 'Segoe UI', sans-serif;"
        "  font-size: {sz}px;"
        "  border: 1px solid {border};"
        "  border-radius: 4px;"
        "  padding: {pad}px;"
        "  selection-background-color: rgba(0, 212, 255, 0.3);"
        "  selection-color: {white};"
        "}}"
        "QScrollBar:vertical {{"
        "  width: 10px;"
        "  background: {bg};"
        "}}"
        "QScrollBar::handle:vertical {{"
        "  background: {scrollbar};"
        "  border-radius: 5px;"
        "  min-height: 30px;"
        "}}"
        "QScrollBar::handle:vertical:hover {{"
        "  background: {scrollhover};"
        "}}"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
        "  height: 0;"
        "}}"
        "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{"
        "  background: transparent;"
        "}}".format(
            bg=t.VOID, fg=t.SILVER, sz=t.SIZE_SMALL, sans=t.FONT_SANS,
            border=t.GRAPHITE, pad=t.SPACE_MD, white=t.WHITE,
            scrollbar=t.GRAPHITE, scrollhover=t.SLATE,
        )
    )


# ── Chat Panel Redesign Stylesheets ──────────────────────────────────


def get_growing_input_stylesheet():
    """Growing QTextEdit input: replaces QLineEdit for multi-line support."""
    return (
        "QTextEdit {{"
        "  background: {bg};"
        "  color: {fg};"
        "  border: 1px solid {border};"
        "  border-radius: 6px;"
        "  padding: 8px 12px;"
        "  font-family: '{sans}', 'Segoe UI', sans-serif;"
        "  font-size: {sz}px;"
        "}}"
        "QTextEdit:focus {{"
        "  border: 1px solid {accent};"
        "}}".format(
            bg=t.VOID, fg=t.BONE, border=t.GRAPHITE,
            sz=t.SIZE_UI, accent=t.SIGNAL, sans=t.FONT_SANS,
        )
    )


def get_context_chip_stylesheet(accent=False):
    """Pill chip for context info above input."""
    fg = t.SIGNAL if accent else t.TEXT_DIM
    return (
        "background: {bg}; border: 1px solid {border}; "
        "border-radius: 10px; padding: 2px 8px; "
        "font-size: {sz}px; color: {fg}; "
        "font-family: '{mono}', 'Consolas', monospace;".format(
            bg=t.GRAPHITE, border=t.CARBON, sz=t.SIZE_LABEL,
            fg=fg, mono=t.FONT_MONO,
        )
    )


def get_quick_action_pill_stylesheet():
    """Smaller pill version of action buttons."""
    return (
        "QPushButton {{"
        "  background: {bg};"
        "  color: {fg};"
        "  border: 1px solid {border};"
        "  border-radius: 14px;"
        "  padding: 4px 12px;"
        "  font-family: '{mono}', 'Consolas', monospace;"
        "  font-size: {sz}px;"
        "}}"
        "QPushButton:hover {{"
        "  background: {hover};"
        "  border-color: {accent};"
        "  color: {white};"
        "}}"
        "QPushButton:pressed {{"
        "  background: rgba(0, 212, 255, 0.15);"
        "  border-color: {accent};"
        "  color: {accent};"
        "}}".format(
            bg=t.CARBON, fg=t.BONE, border=t.GRAPHITE,
            sz=t.SIZE_LABEL, hover=t.HOVER,
            accent=t.SIGNAL, white=t.WHITE, mono=t.FONT_MONO,
        )
    )


def get_font_size_button_stylesheet():
    """The 'Aa' font control icon button."""
    return (
        "QPushButton {{"
        "  background: transparent;"
        "  color: {fg};"
        "  border: 1px solid {border};"
        "  border-radius: 4px;"
        "  padding: 2px 4px;"
        "  font-family: '{sans}', 'Segoe UI', sans-serif;"
        "  font-size: {sz}px;"
        "  font-weight: 700;"
        "}}"
        "QPushButton:hover {{"
        "  color: {accent};"
        "  border-color: {accent};"
        "}}".format(
            fg=t.TEXT_DIM, border=t.GRAPHITE, accent=t.SIGNAL,
            sans=t.FONT_SANS, sz=t.SIZE_LABEL,
        )
    )


def get_typing_indicator_stylesheet():
    """Styling for the animated typing dots area."""
    return (
        "color: {sig}; font-style: italic;".format(sig=t.SIGNAL)
    )


def animate_stack_transition(stacked_widget, new_index, duration_ms=200):
    """Smooth opacity fade between QStackedWidget pages.

    QStackedWidget doesn't support slide animations natively.
    We use opacity fade via QGraphicsOpacityEffect.
    """
    try:
        from PySide6 import QtWidgets, QtCore
    except ImportError:
        from PySide2 import QtWidgets, QtCore

    current = stacked_widget.currentWidget()
    target = stacked_widget.widget(new_index)

    if current is target:
        return

    # Apply opacity effect to target
    effect = QtWidgets.QGraphicsOpacityEffect(target)
    target.setGraphicsEffect(effect)
    effect.setOpacity(0.0)

    # Switch immediately (target starts invisible)
    stacked_widget.setCurrentIndex(new_index)

    # Animate opacity 0 -> 1
    anim = QtCore.QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)

    # Clean up effect after animation
    def cleanup():
        target.setGraphicsEffect(None)
    anim.finished.connect(cleanup)

    # Store reference to prevent GC
    stacked_widget._current_anim = anim
    anim.start()
