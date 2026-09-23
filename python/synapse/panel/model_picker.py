"""Provider-organized model choice; browsing never changes the saved pick."""
from html import escape
try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover - Houdini's older Qt build
    from PySide2 import QtCore, QtGui, QtWidgets

from .designsystem import components as c, fontload, rhythm, tokens as t
from .providers.registry import model_label

Qt = QtCore.Qt
ROW = Qt.UserRole
PROVIDERS = {
    "claude": ("Anthropic", "Claude"),
    "gemini": ("Google", "Gemini"),
    "nemotron": ("NVIDIA", "Nemotron"),
    "ollama": ("Ollama", "Installed models and cloud relays"),
    "custom": ("Custom", "Compatible endpoint"),
}


class _Rows(QtWidgets.QStyledItemDelegate):
    """Two readable text lines; exact identities also remain accessible."""
    def __init__(self, parent, scale):
        super().__init__(parent)
        self.scale = scale

    def _fonts(self):
        label = QtGui.QFont(self.parent().font())
        detail = QtGui.QFont(label)
        fontload.apply_family(detail, mono=True)
        return label, detail

    def model_row_height(self):
        label, detail = self._fonts()
        return (QtGui.QFontMetrics(label).height() + QtGui.QFontMetrics(detail).height()
                + t.scaled(t.SPACE_MD, self.scale))

    def sizeHint(self, option, index):
        row = index.data(ROW) or {}
        line = QtGui.QFontMetrics(self.parent().font()).height()
        height = (line + t.scaled(t.SPACE_LG, self.scale) if row.get("kind") == "provider"
                  else self.model_row_height())
        return QtCore.QSize(t.SPACE_48, height)

    def paint(self, painter, option, index):
        row = index.data(ROW) or {}
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setClipRect(option.rect)
        rect = option.rect
        inset = t.scaled(t.SPACE_MD, self.scale)
        font, detail_font = self._fonts()
        painter.setFont(font)
        fm = QtGui.QFontMetrics(font)
        detail_metrics = QtGui.QFontMetrics(detail_font)
        if row.get("kind") == "provider":
            painter.setPen(QtGui.QColor(t.TEXT_SECONDARY))
            painter.drawText(rect.adjusted(inset, 0, -inset, 0), Qt.AlignVCenter,
                             fm.elidedText(row["label"].upper(), Qt.ElideRight,
                                           max(0, rect.width() - 2 * inset)))
            painter.restore()
            return
        selected = bool(option.state & QtWidgets.QStyle.State_Selected)
        hovered = bool(option.state & QtWidgets.QStyle.State_MouseOver)
        cell = rect.adjusted(t.SPACE_XS, 1, -t.SPACE_XS, -1)
        radius = t.scaled(t.RADIUS_MD, self.scale)
        if row.get("active") or selected or hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QtGui.QColor(t.MODEL_SELECTION if row.get("active") else t.HOVER_BG))
            painter.drawRoundedRect(cell, radius, radius)
        mark_width = t.scaled(t.SPACE_LG, self.scale)
        text_rect = rect.adjusted(inset + mark_width, 0, -inset, 0)
        if row.get("active"):
            painter.setPen(QtGui.QPen(QtGui.QColor(t.MODEL_ACCENT), max(1, round(2 * self.scale))))
            center = QtCore.QPoint(rect.left() + inset + mark_width // 3, rect.center().y())
            arm = max(1, round(t.SPACE_XS * self.scale))
            painter.drawLine(center + QtCore.QPoint(-arm, 0), center + QtCore.QPoint(0, arm))
            painter.drawLine(center + QtCore.QPoint(0, arm), center + QtCore.QPoint(2 * arm, -arm))
        top = rect.center().y() - (fm.height() + detail_metrics.height()) // 2
        painter.setPen(QtGui.QColor(t.MODEL_ACCENT if row.get("active") else t.TEXT_PRIMARY))
        painter.drawText(QtCore.QRect(text_rect.left(), top, text_rect.width(), fm.height()),
                         Qt.AlignVCenter, fm.elidedText(row["label"], Qt.ElideRight, text_rect.width()))
        painter.setPen(QtGui.QColor(t.MODEL_DETAIL if row.get("active") else t.TEXT_SECONDARY))
        painter.setFont(detail_font)
        painter.drawText(QtCore.QRect(text_rect.left(), top + fm.height(), text_rect.width(), detail_metrics.height()),
                         Qt.AlignVCenter, detail_metrics.elidedText(row["detail"], Qt.ElideMiddle, text_rect.width()))
        if option.state & QtWidgets.QStyle.State_HasFocus:
            painter.setPen(QtGui.QPen(QtGui.QColor(t.MODEL_ACCENT), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(cell, radius, radius)
        painter.restore()


class ModelPicker(QtWidgets.QWidget):
    model_chosen = QtCore.Signal(str, str)
    connect_requested = QtCore.Signal()
    configure_requested = QtCore.Signal()

    def __init__(self, parent, rows, discovery, scale=t.FONT_SCALE_DEFAULT):
        super().__init__(parent, Qt.Popup)
        self.setObjectName("DsModelPicker")
        self.setWindowTitle("Choose generation model")
        self.setAccessibleName("Choose generation model")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._rows = rows
        self._discovery = discovery
        self._scale = scale
        self._committed = False
        self._query = ""
        self._current_title = "No saved model"
        self._current_id = ""
        self._compact = False
        c.apply_stylesheet(self, scale)
        c.apply_font_role(self, "body", scale)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        title = self._title = c.label("Choose a model", role="title", scale=scale)
        title.setWordWrap(True)
        title.setMinimumWidth(0)
        outer.addWidget(title)
        self.current = c.label("", role="body", scale=scale)
        self.current.setTextFormat(Qt.PlainText)
        self.current.setWordWrap(False)
        self.current.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.current.setMinimumWidth(0)
        self.current.setObjectName("DsModelCurrent")
        outer.addWidget(self.current)
        self.search = QtWidgets.QLineEdit(self)
        self.search.setObjectName("DsModelSearch")
        self.search.setPlaceholderText("Search providers or models")
        self.search.setAccessibleName("Search providers or models")
        self.search.setClearButtonEnabled(True)
        c.apply_font_role(self.search, "body", scale)
        outer.addWidget(self.search)
        self.list = QtWidgets.QListWidget(self)
        self.list.setObjectName("DsModelList")
        self.list.setAccessibleName("Models grouped by provider")
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.list.setMouseTracking(True)
        c.apply_font_role(self.list, "body", scale)
        self.list.setItemDelegate(_Rows(self.list, scale))
        outer.addWidget(self.list, 1)
        self.empty = c.label("No models match. Try another name or connect a model.", role="body", scale=scale)
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        outer.addWidget(self.empty, 1)
        self.status = c.label("", role="body", scale=scale)
        self.status.setObjectName("DsModelDiscovery")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        outer.addWidget(self.status)
        footer = self._footer = QtWidgets.QHBoxLayout()
        rhythm.model_picker_layout(outer, footer, scale)
        self.connect_button = c.Button("Connect models…", "secondary", self)
        self.refresh_button = c.Button("Refresh Ollama", "ghost", self)
        for button in (self.connect_button, self.refresh_button):
            c.apply_font_role(button, "body", scale)
        footer.addWidget(self.connect_button)
        footer.addStretch(1)
        footer.addWidget(self.refresh_button)
        outer.addLayout(footer)
        self.search.textChanged.connect(self.refresh)
        self.search.installEventFilter(self)
        self.list.installEventFilter(self)
        self.list.itemClicked.connect(self._choose)
        self.list.itemActivated.connect(self._choose)
        self.connect_button.clicked.connect(self._connect)
        self.refresh_button.clicked.connect(discovery.refresh)
        # Bound Qt receiver: late replies cannot call a deleted popup.
        self._connection = discovery.changed.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _identity(item):
        row = item.data(ROW) if item is not None else {}
        return (row.get("kind"), row.get("provider"), row.get("model"))

    def refresh(self, *_):
        """Preserve browsing position while local discovery updates the catalog."""
        previous = self._identity(self.list.currentItem())
        previous_top = (self.list.visualItemRect(self.list.currentItem()).top()
                        if self.list.currentItem() is not None else None)
        scroll = self.list.verticalScrollBar().value()
        search = self.search.text()
        query_changed = search != self._query
        self._query = search
        query = search.casefold().split()
        self.list.clear()
        matching, chosen, active_item = [], None, None
        self._current_title, self._current_id = "No saved model", ""
        for pid, fallback, models in self._rows():
            provider, alias = PROVIDERS.get(pid, (fallback, fallback))
            candidates = []
            for mid, label, active in models:
                if pid == "ollama" and label == mid:
                    label = model_label(pid, mid)
                if active:
                    self._current_title = "%s / %s" % (provider, label)
                    self._current_id = mid
                haystack = " ".join((provider, alias, label, mid)).casefold()
                if all(word in haystack for word in query):
                    candidates.append({"kind": "model", "provider": pid, "model": mid,
                                       "label": label, "detail": mid, "active": active})
            if pid == "custom" and all(word in "custom compatible endpoint configure" for word in query):
                candidates.append({"kind": "configure", "provider": pid, "model": "",
                                   "label": "Configure custom endpoint…", "detail": "Service address and model ID"})
            if not candidates:
                continue
            heading = QtWidgets.QListWidgetItem(provider, self.list)
            heading.setData(ROW, {"kind": "provider", "provider": pid, "label": provider})
            heading.setFlags(Qt.NoItemFlags)
            for row in candidates:
                item = QtWidgets.QListWidgetItem(row["label"], self.list)
                item.setData(ROW, row)
                description = "%s · %s\n%s%s" % (provider, row["label"], row["detail"],
                    "\nSelected for next task" if row.get("active") else "")
                item.setToolTip("<qt>" + escape(description).replace("\n", "<br>") + "</qt>")
                item.setData(Qt.AccessibleTextRole, description)
                matching.append(item)
                if self._identity(item) == previous:
                    chosen = item
                if row.get("active"):
                    active_item = item
        self._fit_current()
        self.list.setCurrentItem(chosen or active_item or (matching[0] if matching else None))
        self.list.doItemsLayout()
        if query_changed:
            self.list.scrollToItem(self.list.currentItem(), QtWidgets.QAbstractItemView.EnsureVisible)
        elif self.list.hasFocus() and chosen is not None and previous_top is not None:
            bar = self.list.verticalScrollBar()
            bar.setValue(bar.value() + self.list.visualItemRect(chosen).top() - previous_top)
            self.list.scrollToItem(chosen, QtWidgets.QAbstractItemView.EnsureVisible)
        else:
            self.list.verticalScrollBar().setValue(scroll)
        if not matching and self.list.hasFocus():
            self.search.setFocus()
        self.list.setVisible(bool(matching))
        self.empty.setVisible(not matching)
        self.status.setText(self._discovery.message())
        self.status.setVisible(bool(self.status.text()) and not self._compact)
        self.refresh_button.setEnabled(not self._discovery.loading)
        self.refresh_button.setToolTip(self.status.text())
        self.refresh_button.setText("Refreshing…" if self._discovery.loading else "Refresh Ollama")

    def _fit_current(self, width=None):
        full = "Selected for next task\n" + self._current_title
        if self._current_id:
            full += "\n" + self._current_id
        width = max(t.SPACE_48, (width or self.width()) - 2 * t.SPACE_MD)
        fm = self.current.fontMetrics()
        visible = ("Next task · " + self._current_title + "\n" + self._current_id
                   if self._compact else full)
        self.current.setText("\n".join(fm.elidedText(line, Qt.ElideMiddle, width)
                                       for line in visible.splitlines()))
        self.current.setAccessibleName(full)
        self.current.setToolTip("<qt>" + escape(full).replace("\n", "<br>") + "</qt>")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_footer"):
            self._fit_chrome(self.width(), self.height())

    def _fit_chrome(self, width, height):
        """Reserve a usable result area before fitting secondary popup chrome."""
        inner = max(t.SPACE_48, width - 2 * t.SPACE_MD)
        buttons = (self.connect_button, self.refresh_button)
        stacked = sum(b.sizeHint().width() for b in buttons) + self._footer.spacing() > inner
        self._footer.setDirection(QtWidgets.QBoxLayout.TopToBottom if stacked
                                  else QtWidgets.QBoxLayout.LeftToRight)
        footer_height = (sum(b.sizeHint().height() for b in buttons) + self._footer.spacing()
                         if stacked else max(b.sizeHint().height() for b in buttons))
        line = self.list.fontMetrics().height()
        chrome = (max(self._title.sizeHint().height(), self._title.heightForWidth(inner))
                  + 3 * self.current.fontMetrics().height() + self.search.sizeHint().height()
                  + max(0, self.status.heightForWidth(inner)) + footer_height
                  + 2 * t.SPACE_MD + 6 * self.layout().spacing())
        row_height = self.list.itemDelegate().model_row_height()
        self._compact = height < chrome + 2 * row_height
        self._title.setVisible(not self._compact)
        self.status.setVisible(bool(self.status.text()) and not self._compact)
        self._fit_current(width)

    def _choose(self, item):
        if item is None or self._committed:
            return
        row = item.data(ROW) or {}
        if row.get("kind") not in ("model", "configure"):
            return
        self._committed = True
        self.close()
        if row["kind"] == "model":
            self.model_chosen.emit(row["provider"], row["model"])
        else:
            self.configure_requested.emit()

    def _connect(self):
        self.close()
        self.connect_requested.emit()

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Escape:
                self.close()
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._choose(self.list.currentItem())
                return True
            if watched is self.search and key in (Qt.Key_Down, Qt.Key_Up, Qt.Key_PageDown, Qt.Key_PageUp):
                self.list.setFocus()
                QtWidgets.QApplication.sendEvent(self.list, event)
                return True
        return super().eventFilter(watched, event)

    def popup(self, anchor):
        available = anchor.screen().availableGeometry()
        position = anchor.mapToGlobal(QtCore.QPoint(0, anchor.height()))
        width = min(t.scaled(390, self._scale), available.width() - 2 * t.SPACE_SM)
        height = min(t.scaled(600, self._scale), available.height() - 2 * t.SPACE_SM)
        self._fit_chrome(width, height)
        self.resize(width, height)
        x = max(available.left() + t.SPACE_SM, min(position.x(), available.right() - width - t.SPACE_SM + 1))
        y = max(available.top() + t.SPACE_SM, min(position.y(), available.bottom() - height - t.SPACE_SM + 1))
        self.move(x, y)
        self.show()
        self.search.setFocus()
        if self.list.currentItem() is not None:
            self.list.scrollToItem(self.list.currentItem(), QtWidgets.QAbstractItemView.EnsureVisible)

    def closeEvent(self, event):
        if self._connection is not None:
            QtCore.QObject.disconnect(self._connection)
            self._connection = None
        super().closeEvent(event)
