"""Shared, responsive geometry for the composer's quiet inset controls."""

from .designsystem import components as c, tokens as t

QtCore, QtGui, QtWidgets = c.QtCore, c.QtGui, c.QtWidgets


class InsetFooter(QtWidgets.QWidget):
    """Four equal columns, then two or one when the actual labels need room.

    Connection evidence and every control's existing signal connections belong
    to the panel, not to this layout.
    """

    reflow_requested = QtCore.Signal()

    def __init__(self, controls, parent=None, scale=t.FONT_SCALE_DEFAULT):
        super().__init__(parent)
        self.setObjectName("DsInsetFooter")
        self.controls = tuple(controls)
        self._gap = t.scaled(t.FOOTER_GAP, scale)
        self._height = t.scaled(t.FOOTER_HEIGHT, scale)
        self._padding = t.scaled(t.SPACE_SM, scale)
        self._columns = 4
        policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                       QtWidgets.QSizePolicy.Fixed)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        for widget in self.controls:
            widget.setParent(self)
            widget.setObjectName("DsFooterStatus" if isinstance(widget, QtWidgets.QLabel)
                                 else "DsFooterLink")
            c.apply_font_role(widget, "body", scale=scale)
            font = widget.font()
            font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, 0.0)
            widget.setFont(font)
            widget.setMinimumWidth(0)
            widget.setFixedHeight(self._height)
            widget.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
            if isinstance(widget, QtWidgets.QLabel):
                widget.setAlignment(QtCore.Qt.AlignCenter)
                widget.setWordWrap(False)
                widget.setMargin(0)
            widget.show()

    def _cell_width(self):
        return max(widget.fontMetrics().horizontalAdvance(widget.text())
                   for widget in self.controls) + 2 * self._padding + 2

    def columns_for_width(self, width):
        for columns in (4, 2):
            if columns * self._cell_width() + (columns - 1) * self._gap <= width:
                return columns
        return 1

    def sizeHint(self):
        return QtCore.QSize(4 * self._cell_width() + 3 * self._gap,
                            2 * self._height + self._gap)

    def minimumSizeHint(self):
        return QtCore.QSize(0, self._height)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        columns = self.columns_for_width(width)
        extras = max(0, len(self.controls) - 4)
        rows = 4 // columns + (extras + columns - 1) // columns
        return rows * self._height + (rows - 1) * self._gap

    def fit_width(self, width):
        height = self.heightForWidth(width)
        if self.minimumHeight() != height:
            self.setMinimumHeight(height)
            self.updateGeometry()
            self.reflow_requested.emit()
        self._arrange(width)

    def _arrange(self, width):
        columns = self._columns = self.columns_for_width(width)
        # Equal integer widths keep both lower controls identical even when
        # Qt has a remainder pixel. That remainder stays at the outer edges.
        cell = max(0, (width - (columns - 1) * self._gap) // columns)
        left = max(0, (width - columns * cell - (columns - 1) * self._gap) // 2)
        for index, widget in enumerate(self.controls):
            if index < 4 or columns == 1:
                row, column = divmod(index, columns)
            else:
                extra_row, column = divmod(index - 4, columns)
                row = 4 // columns + extra_row
                # Keep Connect models on the right; World Labs follows the
                # connection-location control in the same row when it fits.
                if index == len(self.controls) - 1:
                    column = columns - 1
            widget.setGeometry(left + column * (cell + self._gap),
                               row * (self._height + self._gap), cell, self._height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_width(self.width())

    def event(self, event):
        result = super().event(event)
        if event.type() == QtCore.QEvent.LayoutRequest and hasattr(self, "controls"):
            self.fit_width(self.width())
        return result


class FooterViewport(QtWidgets.QScrollArea):
    """Only scroll the footer when enlarged chrome exhausts a short dock."""

    def __init__(self, controls, scale=t.FONT_SCALE_DEFAULT):
        super().__init__()
        self.setObjectName("DsInsetFooterScroll")
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.grid = InsetFooter(controls, scale=scale)
        self.controls = self.grid.controls
        self._cap = None
        self.setWidget(self.grid)
        for control in self.controls:
            control.installEventFilter(self)
        policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                       QtWidgets.QSizePolicy.Fixed)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def sizeHint(self):
        size = self.grid.sizeHint()
        return QtCore.QSize(size.width(), self.heightForWidth(size.width()))

    def minimumSizeHint(self):
        return QtCore.QSize(0, self.grid._height)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        natural = self.grid.heightForWidth(width)
        return min(natural, self._cap) if self._cap is not None else natural

    def cap_height(self, height):
        self._cap = None if height is None else max(self.grid._height, int(height))
        self.fit_width(self.width())

    def fit_width(self, width):
        height = self.heightForWidth(width)
        if self.height() != height or self.minimumHeight() != height:
            self.setFixedHeight(height)
            self.updateGeometry()
        self.grid.fit_width(self.viewport().width())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grid.fit_width(self.viewport().width())
        QtCore.QTimer.singleShot(0, self, self._keep_focus_visible)

    def _keep_focus_visible(self):
        focused = QtWidgets.QApplication.focusWidget()
        if focused in self.controls:
            self.ensureWidgetVisible(focused, 0, 0)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.FocusIn and watched in self.controls:
            QtCore.QTimer.singleShot(0, self, self._keep_focus_visible)
        return super().eventFilter(watched, event)


def install_footer(panel, column=None):
    """Install once, including on an already open panel without rebuilding it.

    Only footer widgets move. Chat, composer, workers, timers and their signal
    connections are retained. Calling this again returns the installed footer.
    """
    existing = getattr(panel, "_inset_footer", None)
    if existing is not None:
        return existing
    if column is None:
        column = panel._composer_hints.parentWidget().layout()
    from .worldlabs_dialog import create_worldlabs_button
    worldlabs = create_worldlabs_button(panel)
    controls = (panel._commands_btn, panel._render_btn, panel._recipes_btn,
                panel._events_btn, panel._connection_location, worldlabs,
                panel._connection_status)
    old_row = getattr(panel, "_connection_row", None)
    # The pre-inset panel has a layout for the top four and an EdgeRow below.
    # Release layout items before reparenting; never delete a control.
    for index in range(column.count() - 1, -1, -1):
        item = column.itemAt(index)
        layout = item.layout()
        if layout is not None and any(layout.itemAt(i).widget() is controls[0]
                                      for i in range(layout.count())):
            column.takeAt(index)
            while layout.count():
                layout.takeAt(0)
            layout.deleteLater()
    footer = FooterViewport(controls, scale=panel._chrome_scale)
    if old_row is not None:
        column.removeWidget(old_row)
        old_row.hide()
        old_row.deleteLater()
    panel._inset_footer = footer
    panel._connection_row = footer  # existing refresh hook, now shared geometry
    column.addWidget(footer)
    # Text changes can alter the column count without a panel resize. Queue
    # one fit after Qt finishes that layout request; never rebuild the panel.
    def reflow():
        if getattr(panel, "_footer_fit_pending", False):
            return
        panel._footer_fit_pending = True
        def fit():
            panel._footer_fit_pending = False
            panel._fit_composer_to_pane()
        QtCore.QTimer.singleShot(0, panel, fit)
    footer.grid.reflow_requested.connect(reflow)
    footer.show()
    return footer
