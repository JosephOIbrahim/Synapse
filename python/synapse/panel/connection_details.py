"""Read-only connection evidence behind the footer's location control."""
from .designsystem import components as c, submenus, tokens as t

QtWidgets, QtCore = c.QtWidgets, c.QtCore


class ConnectionDetailsDialog(QtWidgets.QDialog):
    """Display existing facts without probing, configuring or sending anything."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsRoot")
        self.setWindowTitle("Model connection")
        self.setModal(False)
        scale = getattr(parent, "_chrome_scale", t.FONT_SCALE_DEFAULT)
        c.apply_stylesheet(self, scale)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(c.label("Model connection", role="title", scale=scale))
        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setAccessibleName("Model connection details")
        self.details.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
        layout.addWidget(self.details, 1)
        close = c.Button("Close", variant="secondary")
        close.clicked.connect(self.close)
        layout.addWidget(close)
        submenus.prepare(self, scale, kind="connection_details")
        self.resize(round(520 * min(scale, 1.4)), round(280 * min(scale, 1.4)))

    def set_details(self, text):
        # Refreshes from the panel's prepared/task connection facts; never
        # resolve a credential or initiate metadata traffic from this view.
        if self.details.toPlainText() != text:
            self.details.setPlainText(text)
