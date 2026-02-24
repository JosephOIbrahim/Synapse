"""Chat display widget for rendering message history.

A read-only QTextBrowser subclass that renders user and SYNAPSE messages
with styled HTML, clickable node paths, code block formatting, message
grouping with timestamps, and animated typing indicator.
"""

import time

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Signal, Slot, QUrl, QTimer
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Signal, Slot, QUrl, QTimer

from synapse.panel.message_formatter import (
    format_user_message,
    format_synapse_message,
    format_system_message,
    format_timestamp_divider,
)
from synapse.panel.styles import get_chat_display_stylesheet
from synapse.panel import tokens as t

# Grouping window: messages from the same sender within this many seconds
# are grouped together (no repeated label, tight margin).
_GROUP_WINDOW_S = 60


def _format_time(epoch):
    """Format an epoch timestamp as a short time string."""
    lt = time.localtime(epoch)
    hour = lt.tm_hour % 12 or 12
    ampm = "AM" if lt.tm_hour < 12 else "PM"
    return "{h}:{m:02d} {ap}".format(h=hour, m=lt.tm_min, ap=ampm)


class ChatDisplay(QtWidgets.QTextBrowser):
    """Read-only rich text display for chat messages.

    Features:
    - User messages right-aligned with subtle background
    - SYNAPSE messages left-aligned
    - Code blocks with monospace font and dark background
    - Node paths as clickable links
    - Message grouping with timestamp dividers
    - Animated typing indicator (cycling dots)
    - Font scaling support
    """

    node_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._typing_indicator_active = False
        self._font_scale = t.FONT_SCALE_DEFAULT

        # Grouping state
        self._last_sender = None    # "user" / "synapse" / "system"
        self._last_message_time = 0  # epoch seconds

        # Typing animation
        self._typing_timer = QTimer(self)
        self._typing_timer.setInterval(500)
        self._typing_timer.timeout.connect(self._cycle_typing_dots)
        self._typing_phase = 0

        self.setReadOnly(True)
        self.setAcceptRichText(True)
        self.setOpenExternalLinks(False)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(get_chat_display_stylesheet())

        # Connect anchor clicks
        self.anchorClicked.connect(self._on_anchor_clicked)
        self.setTextInteractionFlags(
            QtCore.Qt.TextBrowserInteraction | QtCore.Qt.TextSelectableByMouse
        )

    # -- Font scaling --------------------------------------------------------

    @property
    def font_scale(self):
        return self._font_scale

    @font_scale.setter
    def font_scale(self, value):
        self._font_scale = value

    # -- Grouping helpers ----------------------------------------------------

    def _should_group(self, sender):
        """Check if the new message should be grouped with the previous one."""
        now = time.time()
        if (
            sender == self._last_sender
            and (now - self._last_message_time) < _GROUP_WINDOW_S
        ):
            return True
        return False

    def _maybe_insert_timestamp_divider(self, sender):
        """Insert a timestamp divider if switching sender groups."""
        now = time.time()
        if self._last_sender is not None and self._last_sender != sender:
            ts_text = _format_time(now)
            cursor = self.textCursor()
            cursor.movePosition(QtGui.QTextCursor.End)
            cursor.insertHtml(
                format_timestamp_divider(ts_text, self._font_scale)
            )
            cursor.insertBlock()
            self.setTextCursor(cursor)

    def _update_sender(self, sender):
        """Record the current sender and timestamp."""
        self._last_sender = sender
        self._last_message_time = time.time()

    # -- Anchor clicks -------------------------------------------------------

    def _on_anchor_clicked(self, url):
        """Handle clicks on anchors in the chat display."""
        url_str = url.toString() if hasattr(url, "toString") else str(url)
        if url_str.startswith("node:"):
            node_path = url_str[5:]
            self.node_clicked.emit(node_path)

    def _scroll_to_bottom(self):
        """Scroll the display to the bottom after appending content."""
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # -- Message append methods ----------------------------------------------

    def append_user_message(self, text):
        """Append a user message to the chat history.

        Parameters
        ----------
        text : str
            The user's message text.
        """
        grouped = self._should_group("user")
        self._maybe_insert_timestamp_divider("user")

        ts = _format_time(time.time())
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertHtml(
            format_user_message(
                text, grouped=grouped, timestamp=ts,
                font_scale=self._font_scale,
            )
        )
        cursor.insertBlock()
        self.setTextCursor(cursor)
        self._update_sender("user")
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

        grouped = self._should_group("synapse")
        self._maybe_insert_timestamp_divider("synapse")

        ts = _format_time(time.time())
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertHtml(
            format_synapse_message(
                content, grouped=grouped, timestamp=ts,
                font_scale=self._font_scale,
            )
        )
        cursor.insertBlock()
        self.setTextCursor(cursor)
        self._update_sender("synapse")
        self._scroll_to_bottom()

    def append_system_message(self, text):
        """Append a system/status message to the chat history.

        Parameters
        ----------
        text : str
            The system message text.
        """
        # System messages don't participate in grouping — they break groups
        self._last_sender = "system"
        self._last_message_time = time.time()

        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertHtml(
            format_system_message(text, font_scale=self._font_scale)
        )
        cursor.insertBlock()
        self.setTextCursor(cursor)
        self._scroll_to_bottom()

    # -- Typing indicator (animated dots) ------------------------------------

    def show_typing_indicator(self):
        """Show an animated 'SYNAPSE is thinking...' indicator."""
        if self._typing_indicator_active:
            return
        self._typing_indicator_active = True
        self._typing_phase = 0
        self._insert_typing_html()
        self._typing_timer.start()

    def hide_typing_indicator(self):
        """Remove the typing indicator and stop animation."""
        if not self._typing_indicator_active:
            return
        self._typing_indicator_active = False
        self._typing_timer.stop()
        # Remove the last block (typing indicator)
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.movePosition(
            QtGui.QTextCursor.StartOfBlock, QtGui.QTextCursor.KeepAnchor
        )
        cursor.removeSelectedText()
        cursor.deletePreviousChar()
        self.setTextCursor(cursor)

    def _insert_typing_html(self):
        """Insert or replace typing indicator HTML."""
        dots = "." * (self._typing_phase + 1)
        html_str = (
            '<div style="margin:{my}px 0; padding:6px 10px;">'
            '<span style="color:{sig}; font-family:monospace; '
            'font-size:{sz}px; letter-spacing:1px; font-weight:700;">'
            'SYNAPSE</span> '
            '<span style="color:{dim}; font-style:italic; '
            'font-size:{sz}px;">is thinking'
            '<span style="color:{sig};">{dots}</span>'
            '</span></div>'
        ).format(
            sig=t.SIGNAL,
            dim=t.TEXT_DIM,
            sz=int(t.SIZE_SMALL * self._font_scale),
            dots=dots,
            my=t.CHAT_BUBBLE_MARGIN_Y,
        )
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertHtml(html_str)
        cursor.insertBlock()
        self.setTextCursor(cursor)
        self._scroll_to_bottom()

    def _cycle_typing_dots(self):
        """Timer callback: cycle through ., .., ... phases."""
        if not self._typing_indicator_active:
            return
        # Remove current indicator
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.movePosition(
            QtGui.QTextCursor.StartOfBlock, QtGui.QTextCursor.KeepAnchor
        )
        cursor.removeSelectedText()
        cursor.deletePreviousChar()
        self.setTextCursor(cursor)
        # Advance phase and re-insert
        self._typing_phase = (self._typing_phase + 1) % 3
        self._insert_typing_html()
