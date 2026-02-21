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
