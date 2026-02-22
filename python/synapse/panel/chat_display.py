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
from synapse.panel.styles import get_chat_display_stylesheet
from synapse.panel import tokens as t


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

    # Typing indicator HTML — styled to match SYNAPSE message format
    _TYPING_HTML = (
        '<div style="margin:4px 0; padding:6px 10px;">'
        '<span style="color:{sig}; font-family:monospace; font-size:10px;'
        ' letter-spacing:1px; font-weight:700;">SYNAPSE</span>'
        '<br/>'
        '<span style="color:{dim}; font-style:italic;">'
        'thinking...</span></div>'
    ).format(sig=t.SIGNAL, dim=t.TEXT_DIM if hasattr(t, "TEXT_DIM") else "#999")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._typing_indicator_active = False
        self.setReadOnly(True)
        self.setAcceptRichText(True)
        self.setOpenExternalLinks(False)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(get_chat_display_stylesheet())

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

        Automatically hides the typing indicator if visible.

        Parameters
        ----------
        content : dict or str
            Response payload from the server.
        """
        self.hide_typing_indicator()
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

    def show_typing_indicator(self):
        """Show a 'thinking...' indicator at the bottom of the chat."""
        if self._typing_indicator_active:
            return
        self._typing_indicator_active = True
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertHtml(self._TYPING_HTML)
        cursor.insertBlock()
        self.setTextCursor(cursor)
        self._scroll_to_bottom()

    def hide_typing_indicator(self):
        """Remove the typing indicator by deleting the last block."""
        if not self._typing_indicator_active:
            return
        self._typing_indicator_active = False
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.movePosition(QtGui.QTextCursor.StartOfBlock, QtGui.QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deletePreviousChar()  # Remove the block separator
        self.setTextCursor(cursor)
