"""Shared type and layout treatment for SYNAPSE's secondary windows.

The painter stays in qss; this module owns only native geometry and fonts.
It never reads settings, starts work, changes a choice or grants permission.
"""
try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtGui, QtWidgets

from . import components as c, tokens as t

_TITLES = {
    "tool": "Commands", "connection": "Connect models", "recipes": "Saved networks",
    "notifications": "Updates", "doctor": "Check SYNAPSE", "model_rules": "Project rules",
}
_PAGES = {"DsConnectionPage", "DsRecipePage", "DsEventsPage", "DsRenderPage",
          "DsRulesPage", "DsSelectionPage"}


def _body_font(widget, scale):
    font = QtGui.QFont(widget.font())
    font.setCapitalization(QtGui.QFont.MixedCase)
    font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, 0)
    widget.setFont(font)
    c.apply_font_role(widget, "body", scale)


class _LayoutStyle(QtCore.QObject):
    def __init__(self, root, scale):
        super().__init__(root)
        self.root, self.scale = root, scale
        self._fitting = False
        self._minimum_width = None

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.Show:
            self.finish()
        elif event.type() == QtCore.QEvent.Resize:
            self.fit_actions()
        return False

    def finish(self):
        root, scale = self.root, self.scale
        layout = root.layout()
        if layout is None:
            return
        if self._minimum_width is None:
            self._minimum_width = root.minimumWidth()
        kind = root.property("panel_popup")
        title = _TITLES.get(kind)
        if title and not getattr(root, "_submenu_heading", None):
            heading = c.label(title, role="title", scale=scale)
            heading.setWordWrap(True)
            heading.setMinimumWidth(0)
            heading.setObjectName("DsSubmenuHeading")
            layout.insertWidget(0, heading)
            root._submenu_heading = heading
        gutter = t.scaled(t.SPACE_MD, min(scale, 1.5))
        gap = t.scaled(t.SPACE_SM, min(scale, 1.5))
        # The picker has its own compact-state geometry owner.
        if root.objectName() != "DsModelPicker":
            # The legacy command palette already has an inset inner frame.
            inset = 0 if kind == "command" else gutter
            layout.setContentsMargins(inset, inset, inset, inset)
            layout.setSpacing(gap)
        for widget in root.findChildren(QtWidgets.QWidget):
            if widget.window() is not root:
                continue
            if isinstance(widget, QtWidgets.QLabel):
                role = widget.property("role") or "body"
                if not widget.property("role"):
                    widget.setProperty("role", role)
                    c.repolish(widget)
                _body_font(widget, scale)
                # Explanatory prose should read quietly, without the panel's
                # letter-spaced metadata voice running through paragraphs.
                if role != "caption":
                    c.apply_font_role(widget, role, scale)
            elif isinstance(widget, (QtWidgets.QAbstractButton, QtWidgets.QLineEdit,
                                     QtWidgets.QComboBox, QtWidgets.QAbstractSpinBox,
                                     QtWidgets.QAbstractItemView, QtWidgets.QPlainTextEdit)):
                _body_font(widget, scale)
                if isinstance(widget, QtWidgets.QComboBox):
                    widget.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
                    widget.setMinimumContentsLength(12)
                    c.repolish(widget)
                    if widget.lineEdit() is not None:
                        c.repolish(widget.lineEdit())
            if widget.objectName() in _PAGES and widget.layout() is not None:
                widget.layout().setContentsMargins(0, gap, t.SPACE_XS, gap)
                widget.layout().setSpacing(gap)
        for form in root.findChildren(QtWidgets.QFormLayout):
            if form.parentWidget().window() is not root:
                continue
            form.setVerticalSpacing(gap)
            if form.rowWrapPolicy() == QtWidgets.QFormLayout.DontWrapRows:
                form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        self.fit_actions()
        if getattr(root, "_submenu_heading", None) is not None:
            root._submenu_heading.setMinimumHeight(root._submenu_heading.sizeHint().height())
        # Scroll pages may hide a horizontal scrollbar without constraining
        # their minimum width. Keep complete labels visible at the host font;
        # on unusually small screens retain native horizontal navigation.
        screen = root.screen()
        available = screen.availableGeometry().width() - 32 if screen else 1600
        minimum_width = self._minimum_width
        for scroll in root.findChildren(QtWidgets.QScrollArea):
            if scroll.window() is not root or scroll.widget() is None:
                continue
            page_width = scroll.widget().minimumSizeHint().width()
            needed = page_width + 2 * gutter + scroll.verticalScrollBar().sizeHint().width()
            minimum_width = max(minimum_width, needed)
            if needed > available:
                scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        root.setMinimumWidth(min(available, minimum_width))

    def fit_actions(self):
        if self._fitting or self.root.objectName() == "DsModelPicker":
            return
        self._fitting = True
        try:
            # A row of buttons may stack; form rows and filter grids retain
            # their own geometry. Recompute from size hints after every resize.
            for row in self.root.findChildren(QtWidgets.QHBoxLayout):
                if row.parentWidget().window() is not self.root:
                    continue
                widgets = [row.itemAt(i).widget() for i in range(row.count())
                           if row.itemAt(i).widget() is not None]
                if not widgets or not all(isinstance(w, QtWidgets.QPushButton) for w in widgets):
                    continue
                width = min(row.geometry().width(), self.root.width() - 2 * t.scaled(t.SPACE_MD, min(self.scale, 1.5)))
                if width <= 0:
                    continue
                needed = sum(w.sizeHint().width() for w in widgets) + max(0, len(widgets)-1) * row.spacing()
                row.setDirection(QtWidgets.QBoxLayout.TopToBottom if needed > width
                                 else QtWidgets.QBoxLayout.LeftToRight)
        finally:
            self._fitting = False


def prepare(root, scale, *, kind=None):
    """Opt in at a popup boundary; finish after its constructor has built it."""
    from . import qss
    if kind:
        root.setProperty("panel_popup", kind)
    root.setProperty("synapse_submenu", True)
    root.setAttribute(QtCore.Qt.WA_StyledBackground, True)
    _body_font(root, scale)
    c.apply_placeholder_palette(root)
    root.setStyleSheet(root.styleSheet() + qss.submenu_stylesheet(scale))
    helper = getattr(root, "_submenu_layout_style", None)
    if helper is None:
        helper = _LayoutStyle(root, scale)
        root._submenu_layout_style = helper
        root.installEventFilter(helper)
    else:
        helper.scale = scale
    if root.layout() is not None:
        helper.finish()


def prepare_menu(menu, scale):
    """Retain native menu navigation, checkmarks and disabled-state behavior."""
    from . import qss
    menu.setObjectName("DsSubmenu")
    c.apply_font_role(menu, "body", scale)
    menu.setStyleSheet(qss.stylesheet(scale) + qss.submenu_stylesheet(scale))
    menu.setToolTipsVisible(True)
    for action in menu.actions():
        child = action.menu()
        if child is not None:
            prepare_menu(child, scale)
