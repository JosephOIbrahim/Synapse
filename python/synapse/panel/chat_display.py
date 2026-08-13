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
# W2-S2 (F4): the off-main formatting pipeline. Qt-free / hou-free by construction,
# so importing it never pulls Qt and the ordering/off-main proof is unit-testable
# headless (see async_format.py's module docstring).
from synapse.panel.async_format import OrderedAsyncFormatter, FormatJob
from synapse.panel.styles import get_chat_display_stylesheet
# FRZ attribution: times the formatter + insertHtml re-layout that this widget does
# on Houdini's main thread. Measurement only; degrades to a no-op context manager.
try:
    from synapse.panel.result_telemetry import timed_phase as _timed_phase
except Exception:  # pragma: no cover
    from contextlib import nullcontext as _nullctx

    def _timed_phase(*_a, **_k):
        return _nullctx()
from synapse.panel.designsystem import tokens as t

# Grouping window: messages from the same sender within this many seconds
# are grouped together (no repeated label, tight margin).
_GROUP_WINDOW_S = 60

# Chat-local layout (was tokens.CHAT_BUBBLE_MARGIN_Y; inlined so chat_display
# sources nothing from the ~/.synapse/design bridge — see designsystem.tokens).
_BUBBLE_MARGIN_Y = 2  # px between grouped messages


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

    # W2-S2 (F4): emitted from the off-main formatter's WORKER thread when a job
    # finishes rendering. Connected with a QueuedConnection so the drain (insertHtml)
    # runs on the Qt main thread -- Qt objects are only ever touched there.
    _fmt_ready = Signal()

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
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(get_chat_display_stylesheet(self._font_scale))

        # Connect anchor clicks
        self.anchorClicked.connect(self._on_anchor_clicked)
        self.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextBrowserInteraction | QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )

        # W2-S2 (F4): off-main formatting pipeline. format_synapse_message (pure, zero
        # Qt / zero hou) runs on a worker thread; only insertHtml stays on this Qt
        # thread. Ordering across a burst of results is guaranteed by the pipeline's
        # single-consumer FIFO. OFF BY DEFAULT so append_synapse_message keeps its
        # historical synchronous contract (the panel's result path flips this on — a
        # one-line opt-in that lives in synapse_panel.py; see the W2-S2 receipt). The
        # worker thread is daemon and started lazily: a ChatDisplay that never runs the
        # off-main path spawns no thread.
        self._async_format_enabled = False
        self._fmt = OrderedAsyncFormatter(on_ready=self._on_fmt_ready)
        self._fmt_ready.connect(
            self._drain_fmt, QtCore.Qt.ConnectionType.QueuedConnection
        )

    # -- Font scaling --------------------------------------------------------

    @property
    def font_scale(self):
        return self._font_scale

    @font_scale.setter
    def font_scale(self, value):
        self._font_scale = value
        # Re-apply the base stylesheet so the QTextBrowser document default (and
        # thus streamed plain-text tokens) tracks the new scale. Already-rendered
        # messages keep their baked inline sizes — new messages use the new scale.
        try:
            self.setStyleSheet(get_chat_display_stylesheet(value))
        except Exception:
            pass

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

    # Reading measure, in CHARACTERS rather than pixels.
    #
    # The v9 rule capped the document at a fixed 492px (a ~440px measure plus
    # 26px padding either side). The principle is right - a line of prose gets
    # harder to track past roughly 90 characters, so a wide dock should not
    # stretch text to its full width. The expression was wrong in two ways:
    #
    #   * pixels do not scale with the Aa control, so raising the font size
    #     shrank the measure in characters - exactly backwards
    #   * 440px is ~55 characters at the default size, the LOW end of the
    #     comfortable band, and in an 1830px pane it left 73% of the width
    #     empty and read as a bug rather than a decision
    #
    # Measured from the live font, clamped, so it holds at every Aa step.
    _MEASURE_CHARS = 90          # upper end of the comfortable band
    _MEASURE_MIN_PX = 460        # never narrower than the old rule
    _MEASURE_MAX_PX = 1100       # never a full-bleed wall of text

    def _reading_measure(self):
        """The document width that keeps ~90 characters per line at the CURRENT
        text size.

        The size is NOT on ``self.font()``. It is applied through the stylesheet
        built from ``self._font_scale`` (line 78), and a Qt stylesheet overrides
        setFont — so asking the widget's font returns a constant and the measure
        never moves. My first version did exactly that and its control caught
        it: 630px at every Aa step, which is the fallback constant times 90.

        So the scaled pixel size is computed the same way the formatter computes
        it, and the metrics are measured from a font built at that size.
        """
        try:
            from synapse.panel.message_formatter import _BODY_PX, _scale
            px = _scale(_BODY_PX, getattr(self, "_font_scale", 1.0))
        except Exception:
            px = 12
        adv = 0.0
        try:
            from PySide6.QtGui import QFont, QFontMetricsF
            f = QFont(self.font())
            f.setPixelSize(int(px))
            adv = QFontMetricsF(f).averageCharWidth()
        except Exception:
            pass
        if not adv or adv <= 0:
            adv = float(px) * 0.55      # proportional-sans rule of thumb
        target = adv * self._MEASURE_CHARS
        return max(self._MEASURE_MIN_PX, min(target, self._MEASURE_MAX_PX))

    def resizeEvent(self, event):
        """Hold a readable measure inside wide panes, and CENTRE it.

        A measure alone is not enough. At 630px in an 1830px dock the text hugs
        the left edge and two thirds of the pane reads as broken rather than as
        margin — which is exactly how it looked when Joe flagged it.

        The fix is the one every reading surface uses: keep the measure, centre
        the column, and let the leftover become symmetric margin. Widening the
        column instead would trade legibility for coverage, and ~90 characters
        is already the upper end of the comfortable band.

        Best-effort: if the cap ever fights QTextBrowser's relayout, the
        fallback is dropping it (long lines, no breakage)."""
        super().resizeEvent(event)
        try:
            measure = self._reading_measure()
            avail = self.viewport().width()
            self.document().setTextWidth(min(avail, measure))
            # Symmetric margin only when there is real slack; a narrow dock
            # keeps every pixel for the text.
            slack = avail - measure
            pad = int(slack / 2) if slack > 40 else 0
            self.setViewportMargins(pad, 0, pad, 0)
        except Exception:
            pass

    # -- Message append methods ----------------------------------------------

    def append_user_message(self, text):
        """Append a user message to the chat history.

        Parameters
        ----------
        text : str
            The user's message text.
        """
        # W2-S2 (F4): land any in-flight off-main synapse format first, so this
        # synchronous insert never jumps ahead of a still-formatting reply.
        self._flush_pending_formats()
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

    def append_synapse_message(self, content, signed=None):
        """Append a SYNAPSE response message to the chat history.

        Automatically hides the typing indicator if visible.

        W2-S2 (F4): the convergence seat of BOTH result paths (the streaming finalize
        via ``end_stream`` and the non-streaming direct append). The grouping decision
        and the sender-state advance always happen HERE, on the Qt thread (cheap).

        When the off-main path is ENABLED (``_async_format_enabled``), the pure formatter
        (``format_synapse_message`` — zero Qt, zero ``hou``) runs OFF the Qt thread on the
        pipeline's worker and only the prerendered HTML string crosses back for
        ``insertHtml`` on main; sender state advances at enqueue time so a rapid follow-up
        groups correctly while this one is still formatting, and a burst inserts in submit
        order (single-consumer FIFO).

        The off-main path is **OFF BY DEFAULT**, so this method keeps its historical
        SYNCHRONOUS contract (format + insert inline, on main, in a single ``append``
        telemetry phase). That is deliberate: many callers and tests read the document
        right after appending, and the panel's own result path (``synapse_panel._on_done``)
        is where the F4 design flips the switch — a one-line opt-in that this leg cannot
        land while ``synapse_panel.py`` is claimed by a peer. Enabling here without that
        wiring would change a synchronous contract the panel still depends on. See the
        W2-S2 receipt: mechanism shipped + proven, panel activation is the blocked
        remainder.

        Parameters
        ----------
        content : dict or str
            Response payload from the server.
        signed : str, optional
            Display-only authorship note (the model that produced the result),
            shown once at the head of a SYNAPSE group.
        """
        self.hide_typing_indicator()

        grouped = self._should_group("synapse")
        self._maybe_insert_timestamp_divider("synapse")
        ts = _format_time(time.time())
        fs = self._font_scale

        if not getattr(self, "_async_format_enabled", False) or self._fmt is None:
            # DEFAULT: synchronous — format + insert inline on this (main) thread, in a
            # SINGLE 'append' phase, exactly as the result path did before this leg.
            self._update_sender("synapse")
            with _timed_phase("append") as _ph:
                html_str = self._render_synapse_html(content, grouped, ts, signed, fs)
                try:
                    _ph.set_sizes(doc_chars=self.document().characterCount(),
                                  payload_chars=len(html_str))
                except Exception:
                    pass
                self._do_insert(html_str)
            return

        # OFF-MAIN: advance grouping state now (on main) so a rapid follow-up groups
        # correctly even though this message's HTML is still being formatted off-main.
        self._update_sender("synapse")
        job = FormatJob(
            render=lambda: self._render_offmain(content, grouped, ts, signed, fs),
            apply=lambda j: self._insert_prerendered(j.html),
        )
        self._fmt.submit(job)

    # -- Off-main format / on-main insert (W2-S2, F4) ------------------------

    def _render_synapse_html(self, content, grouped, ts, signed, font_scale):
        """PURE, off-main-safe render: ``format_synapse_message`` only. Touches NO Qt and
        NO ``hou`` — ``font_scale`` is passed in, never read off the widget off-main. No
        telemetry here; the caller owns the phase timing, so the sync path records ONE
        'append' sample (like base) while the async path times format and insert apart."""
        return format_synapse_message(
            content, grouped=grouped, timestamp=ts,
            font_scale=font_scale, signed=signed,
        )

    def _render_offmain(self, content, grouped, ts, signed, font_scale):
        """The worker-thread render: the pure formatter timed under the ``append`` phase.
        Run off the Qt thread it lands in that phase's OFF-MAIN counters
        (``record_result_phase`` derives the thread identity itself) — exactly how the F4
        win (the four-regex pass leaving the Qt thread) becomes visible in the ledger,
        never confused for a main-thread stall."""
        with _timed_phase("append") as _ph:
            html_str = self._render_synapse_html(content, grouped, ts, signed, font_scale)
            try:
                _ph.set_sizes(payload_chars=len(html_str))
            except Exception:
                pass
        return html_str

    def _do_insert(self, html_str):
        """Raw cursor insert at End (no telemetry). The only Qt work in the result path —
        ``insertHtml``'s O(document) re-layout — and it only ever runs on the Qt main
        thread (the sync path is on main; the async path routes here via ``_drain_fmt``)."""
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertHtml(html_str or "")
        cursor.insertBlock()
        self.setTextCursor(cursor)
        self._scroll_to_bottom()

    def _insert_prerendered(self, html_str):
        """Insert a PRERENDERED HTML string on the Qt main thread, timed as an on-main
        ``append`` sample. Ordering across a burst is guaranteed upstream by the
        pipeline's single-consumer FIFO, so this simply appends at End in drain order.
        ``doc_chars`` is captured BEFORE the insert, recording the document size the
        layout had to walk."""
        with _timed_phase("append") as _ph:
            try:
                _ph.set_sizes(doc_chars=self.document().characterCount(),
                              payload_chars=len(html_str or ""))
            except Exception:
                pass
            self._do_insert(html_str)

    def _on_fmt_ready(self):
        """Called FROM the formatter's worker thread when a job finishes. Marshal the
        drain onto the Qt main thread via the queued signal — no Qt object is touched
        here; the actual insert happens in ``_drain_fmt`` / ``_insert_prerendered``."""
        try:
            self._fmt_ready.emit()
        except Exception:
            pass

    @Slot()
    def _drain_fmt(self):
        """Main-thread slot: insert every ready prerendered result, in submit order."""
        fmt = getattr(self, "_fmt", None)
        if fmt is None:
            return
        try:
            fmt.drain()
        except Exception:
            pass

    def _flush_pending_formats(self, timeout=2.0):
        """Drain any in-flight off-main synapse formats to the document BEFORE a
        synchronous same-thread insert (user / system message, stream open), so the
        GLOBAL insert order equals the call order across senders. Bounded: it waits only
        for already-submitted formats — pure millisecond string work — and is a no-op in
        the common case (nothing pending). Call on the main thread."""
        fmt = getattr(self, "_fmt", None)
        if fmt is None:
            return
        try:
            fmt.wait_idle(timeout)
            fmt.drain()
        except Exception:
            pass

    def enable_off_main_format(self, enabled=True):
        """Turn the off-main formatting path on (or off). This is the panel's F4 opt-in:
        ``synapse_panel`` calls it once (in the result path / at panel construction) so
        ``format_synapse_message`` runs on the worker thread for panel results. Off by
        default because it changes ``append_synapse_message`` from synchronous to
        deferred — safe only where the caller does not read the document synchronously
        after appending (the live panel, driven by a running Qt event loop, does not)."""
        self._async_format_enabled = bool(enabled)

    def shutdown(self):
        """Stop the off-main formatter thread. Optional — the thread is a daemon and
        dies with the process; call it for a clean teardown (tests, panel close)."""
        fmt = getattr(self, "_fmt", None)
        if fmt is not None:
            try:
                fmt.stop()
            except Exception:
                pass

    def append_system_message(self, text):
        """Append a system/status message to the chat history.

        Parameters
        ----------
        text : str
            The system message text.
        """
        # W2-S2 (F4): land any in-flight off-main synapse format first (call order).
        self._flush_pending_formats()
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

    # -- Result-path cost bound (W1-MTFIX) -----------------------------------

    def set_max_result_blocks(self, n):
        """Bound the QTextDocument to at most ``n`` blocks (oldest trimmed first).

        The append/finalize main-thread cost is dominated by ``insertHtml``'s Qt
        rich-text re-layout, which is O(document): it grows with conversation length
        because the document is unbounded. This is the O(1) Qt-native lever that
        caps it — ``QTextDocument.setMaximumBlockCount`` — so the worst-case
        re-layout stays flat no matter how long the session runs, which is the
        architectural fix FRZ_REPRO names for the result path.

        OPT-IN, default unlimited: not called at construction, because trimming is a
        content decision (a message spans several blocks, so a block cap can clip the
        oldest message mid-body — whole-message trimming is the follow-up). Enabling
        it, and picking the cap, is a UX call this leg does not make unilaterally
        against the 'no result-content regression' bar. ``n <= 0`` restores unlimited.

        Verified present on this build's PySide6 (QTextDocument.setMaximumBlockCount,
        H22.0.400). Best-effort: never raises."""
        try:
            self.document().setMaximumBlockCount(int(n) if n and n > 0 else 0)
        except Exception:
            pass

    # -- Streaming (token-by-token) ------------------------------------------

    def begin_stream(self):
        """Open a streaming SYNAPSE reply. Tokens append as plain text; a single
        end_stream() replaces them with the fully-formatted message. One removal
        at the end (not per-tick) — no typing-indicator-style accumulation."""
        # W2-S2 (F4): land any in-flight off-main synapse format before opening a new
        # stream, so streamed tokens never interleave ahead of a prior reply.
        self._flush_pending_formats()
        self.hide_typing_indicator()
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self._stream_anchor = cursor.position()
        self._streaming = True

    def stream_chunk(self, text):
        """Append a streamed token as plain text (fast, no reformat)."""
        if not getattr(self, "_streaming", False):
            return
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self._scroll_to_bottom()

    def end_stream(self, final_content=None, signed=None):
        """Close the stream: drop the streamed plain text and re-append the
        message fully formatted (markdown, code blocks, clickable node links).
        ``signed`` adds the display-only authorship note to the finalized reply."""
        if not getattr(self, "_streaming", False):
            return
        self._streaming = False
        cursor = self.textCursor()
        cursor.setPosition(getattr(self, "_stream_anchor", cursor.position()))
        cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        self.setTextCursor(cursor)
        if final_content:
            self.append_synapse_message(final_content, signed=signed)
        else:
            self._update_sender("synapse")
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
            dim=t.TEXT_SECONDARY,
            sz=int(t.SIZE_SMALL * self._font_scale),
            dots=dots,
            my=_BUBBLE_MARGIN_Y,
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
