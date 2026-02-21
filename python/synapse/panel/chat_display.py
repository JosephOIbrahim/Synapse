"""Chat display widget for rendering message history.

A read-only QTextEdit subclass that renders user and SYNAPSE messages
with styled HTML, clickable node paths, and code block formatting.
"""

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Signal, Slot, QUrl
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Signal, Slot, QUrl

from synapse.panel.message_formatter import (
    format_user_message,
    format_synapse_message,
    format_system_message,
)
from synapse.panel import tokens as t

# -- Design tokens (from canonical design system) -------------------------
_VOID = t.VOID
_TEXT = t.TEXT
_BODY_PX = t.SIZE_BODY
_GRAPHITE = t.GRAPHITE
_FONT_SANS = t.FONT_SANS


class ChatDisplay(QtWidgets.QTextBrowser):
    """Read-only rich text display for chat messages.

    Renders messages with:
    - User messages right-aligned with subtle background
    - SYNAPSE messages left-aligned
    - Code blocks with monospace font and dark background
    - Node paths as clickable links
    - Status indicators (success/warning/error via Unicode)

    Uses QTextBrowser (subclass of QTextEdit) for anchor click support.
    """

    node_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAcceptRichText(True)
        self.setOpenExternalLinks(False)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(
            "QTextBrowser {{"
            "  background: {bg};"
            "  color: {fg};"
            "  font-family: '{sans}', 'Segoe UI', sans-serif;"
            "  font-size: {sz}px;"
            "  border: none;"
            "  padding: 8px;"
            "  selection-background-color: rgba(0, 212, 255, 0.3);"
            "  selection-color: #F0F0F0;"
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
                bg=_VOID, fg=_TEXT, sz=_BODY_PX, sans=_FONT_SANS,
                scrollbar=_GRAPHITE, scrollhover=t.SLATE,
            )
        )

        # Connect anchor clicks
        self.anchorClicked.connect(self._on_anchor_clicked)
        # Ensure links don't auto-follow
        self.setTextInteractionFlags(
            QtCore.Qt.TextBrowserInteraction | QtCore.Qt.TextSelectableByMouse
        )

    def _on_anchor_clicked(self, url):
        """Handle clicks on anchors in the chat display."""
        url_str = url.toString() if hasattr(url, "toString") else str(url)
        if url_str.startswith("node:"):
            node_path = url_str[5:]  # Strip "node:" prefix
            self.node_clicked.emit(node_path)

    def _scroll_to_bottom(self):
        """Scroll the display to the bottom after appending content."""
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def append_user_message(self, text):
        """Append a user message to the chat history.

        Parameters
        ----------
        text : str
            The user's message text.
        """
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertHtml(format_user_message(text))
        cursor.insertBlock()
        self.setTextCursor(cursor)
        self._scroll_to_bottom()

    def append_synapse_message(self, content):
        """Append a SYNAPSE response message to the chat history.

        Parameters
        ----------
        content : dict or str
            Response payload from the server.
        """
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertHtml(format_synapse_message(content))
        cursor.insertBlock()
        self.setTextCursor(cursor)
        self._scroll_to_bottom()

    def append_system_message(self, text):
        """Append a system/status message to the chat history.

        Parameters
        ----------
        text : str
            The system message text.
        """
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertHtml(format_system_message(text))
        cursor.insertBlock()
        self.setTextCursor(cursor)
        self._scroll_to_bottom()
