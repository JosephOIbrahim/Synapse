"""Shared, responsive geometry for the composer's quiet inset controls."""

from .designsystem import components as c, tokens as t

QtCore, QtGui, QtWidgets = c.QtCore, c.QtGui, c.QtWidgets


class InsetFooter(QtWidgets.QWidget):
    """Three equal columns, then two or one when the actual labels need room.

    An optional tail takes the row below the grid, across the grid's outer
    edges. One control spans it (Render, 9/30). Several share it in equal cells
    (Identify, Spatial, Render, 10/2): at three columns each cell sits on a
    grid column, and the tail stays ONE row for as long as its own labels fit,
    so the dock is no taller than with a single control. Only when they do not
    fit does the tail wrap, by the rule the grid uses for itself. The tail
    never changes the grid's column count.

    Connection evidence and every control's existing signal connections belong
    to the panel, not to this layout.
    """

    reflow_requested = QtCore.Signal()

    def __init__(self, controls, parent=None, scale=t.FONT_SCALE_DEFAULT, tail=None):
        super().__init__(parent)
        self.setObjectName("DsInsetFooter")
        self.grid_controls = tuple(controls)
        # tail: nothing, one widget (the 9/30 call), or the row's widgets in order.
        if tail is None:
            tail = ()
        elif isinstance(tail, QtWidgets.QWidget):
            tail = (tail,)
        self.tail_controls = tuple(tail)
        # Every footer widget, tail last: styling, focus order and the panel's
        # shared connections use controls; the column grid uses grid_controls.
        self.controls = self.grid_controls + self.tail_controls
        self._gap = t.scaled(t.FOOTER_GAP, scale)
        self._height = t.scaled(t.FOOTER_HEIGHT, scale)
        self._padding = t.scaled(t.SPACE_SM, scale)
        self._columns = 3
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
                   for widget in self.grid_controls) + 2 * self._padding + 2

    def columns_for_width(self, width):
        for columns in (3, 2):
            if columns * self._cell_width() + (columns - 1) * self._gap <= width:
                return columns
        return 1

    def _grid_geometry(self, width):
        """(columns, cell, left, span): equal integer cells, the remainder
        pixel split between the outer edges, and the grid's own outer span."""
        columns = self.columns_for_width(width)
        cell = max(0, (width - (columns - 1) * self._gap) // columns)
        left = max(0, (width - columns * cell - (columns - 1) * self._gap) // 2)
        return columns, cell, left, columns * cell + (columns - 1) * self._gap

    def tail_columns_for_width(self, width):
        """Tail cells per row: all of them while their own labels fit inside
        the grid's span, then as many as do. 0 with no tail."""
        count = len(self.tail_controls)
        if count <= 1:
            return count
        span = self._grid_geometry(width)[3]
        need = max(widget.fontMetrics().horizontalAdvance(widget.text())
                   for widget in self.tail_controls) + 2 * self._padding + 2
        for per_row in range(count, 1, -1):
            if per_row * need + (per_row - 1) * self._gap <= span:
                return per_row
        return 1

    def _tail_rows(self, width):
        per_row = self.tail_columns_for_width(width)
        return (len(self.tail_controls) + per_row - 1) // per_row if per_row else 0

    def sizeHint(self):
        width = 3 * self._cell_width() + 2 * self._gap
        return QtCore.QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self):
        return QtCore.QSize(0, self._height)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        columns = self.columns_for_width(width)
        rows = (len(self.grid_controls) + columns - 1) // columns + self._tail_rows(width)
        return rows * self._height + (rows - 1) * self._gap

    def fit_width(self, width):
        height = self.heightForWidth(width)
        if self.minimumHeight() != height:
            self.setMinimumHeight(height)
            self.updateGeometry()
            self.reflow_requested.emit()
        self._arrange(width)

    def _arrange(self, width):
        # Equal integer widths keep both lower controls identical even when
        # Qt has a remainder pixel. That remainder stays at the outer edges.
        columns, cell, left, span = self._grid_geometry(width)
        self._columns = columns
        for index, widget in enumerate(self.grid_controls):
            row, column = divmod(index, columns)
            widget.setGeometry(left + column * (cell + self._gap),
                               row * (self._height + self._gap), cell, self._height)
        if not self.tail_controls:
            return
        # The tail spans the grid's outer edges. Each of its rows shares that
        # span in equal cells, so a row of `columns` cells lands on the grid's
        # own columns and a lone control spans the grid (Render, 9/30). When a
        # row cannot divide the span exactly, the spare pixels go into its
        # first gaps: the cells stay equal and both outer edges stay exact.
        per_row = self.tail_columns_for_width(width)
        row = (len(self.grid_controls) + columns - 1) // columns
        for start in range(0, len(self.tail_controls), per_row):
            widgets = self.tail_controls[start:start + per_row]
            count = len(widgets)
            tail_cell = max(0, (span - (count - 1) * self._gap) // count)
            spare = max(0, span - count * tail_cell - (count - 1) * self._gap)
            x = left
            for index, widget in enumerate(widgets):
                widget.setGeometry(x, row * (self._height + self._gap), tail_cell, self._height)
                x += tail_cell + self._gap + (1 if index < spare else 0)
            row += 1

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

    def __init__(self, controls, scale=t.FONT_SCALE_DEFAULT, tail=None):
        super().__init__()
        self.setObjectName("DsInsetFooterScroll")
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.grid = InsetFooter(controls, scale=scale, tail=tail)
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
    controls = (panel._commands_btn, panel._recipes_btn,
                panel._events_btn, panel._connection_location, worldlabs,
                panel._connection_status)
    old_row = getattr(panel, "_connection_row", None)
    # The pre-inset panel has a layout for its actions and an EdgeRow below.
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
    # The last row (Joe, 10/2): the verbs that act on the scene with no
    # conversation turn -- Identify, Spatial, Render -- one cell each on the
    # grid's columns. A panel without one of them keeps the rest; Render alone
    # is the 9/30 full-width row.
    tail = tuple(control for control in (getattr(panel, "_identify_btn", None),
                                         getattr(panel, "_spatial_btn", None),
                                         getattr(panel, "_render_btn", None))
                 if control is not None)
    footer = FooterViewport(controls, scale=panel._chrome_scale, tail=tail or None)
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
