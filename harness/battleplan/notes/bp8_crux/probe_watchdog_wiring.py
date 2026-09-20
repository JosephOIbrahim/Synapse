#!/usr/bin/env python3
"""BP8-CRUX probe -- the PRODUCTION watchdog wiring in createInterface, under real Qt.

The leg's Layer-2 test rebuilds the timer inside the test helper (_wire_real_watchdog),
so the four production lines in createInterface (QTimer parent, setSingleShot, setInterval,
timeout.connect) are never exercised by the committed suite -- mutations W-M6/W-M7/W-M8
survive. This probe builds the real interface offscreen (same pattern as
tests/test_panel_sweep_a.py::_construct) and reads the production timer back:
  * single-shot, interval == WATCHDOG_TIMEOUT_MS, not armed until a send;
  * the production `timeout.connect` line is live: shrink the interval to 1 ms, start,
    pump the event loop, and the handler must clear the waiting flag and append ONE line.
`--delete-connect` is the negative control: it removes the production connect line for
the duration of the probe (restoring the original bytes in `finally`) and must report
fired=True with waiting_cleared=False and no line -- proving the probe catches W-M6.

Run under hython (real PySide) from a scratch clone:
  hython probe_watchdog_wiring.py --tree <scratch-w> [--delete-connect]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

CONNECT_LINE = "        self._response_watchdog.timeout.connect(self._on_response_timeout)\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True)
    ap.add_argument("--delete-connect", action="store_true")
    a = ap.parse_args()
    tree = Path(a.tree).resolve()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
    sys.path.insert(0, str(tree / "python"))

    chat_path = tree / "python" / "synapse" / "panel" / "chat_panel.py"
    original = chat_path.read_bytes()
    out = {"tree": str(tree), "delete_connect": a.delete_connect, "python": sys.version.split()[0]}
    try:
        if a.delete_connect:
            text = original.decode("utf-8")
            assert text.count(CONNECT_LINE) == 1, "connect line must occur exactly once"
            chat_path.write_bytes(text.replace(CONNECT_LINE, "").encode("utf-8"))
        try:
            from PySide6 import QtWidgets  # noqa: F401
        except ImportError:
            from PySide2 import QtWidgets  # type: ignore # noqa: F401
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        from unittest.mock import MagicMock
        from synapse.panel import chat_panel as cp
        out["chat_panel_file"] = cp.__file__
        out["WATCHDOG_TIMEOUT_MS"] = cp.WATCHDOG_TIMEOUT_MS

        c = cp.SynapseChatPanel()
        widget = c.createInterface()  # production wiring, bridge/timers never activated
        out["created_widget"] = type(widget).__name__
        t = c._response_watchdog
        out["timer_type"] = type(t).__name__
        out["isSingleShot"] = bool(t.isSingleShot())
        out["interval_ms"] = int(t.interval())
        out["interval_equals_WATCHDOG_TIMEOUT_MS"] = int(t.interval()) == cp.WATCHDOG_TIMEOUT_MS
        out["armed_after_createInterface"] = bool(t.isActive())
        out["parent_is_root"] = t.parent() is c._root

        # Prove the production connect line: fire the PRODUCTION timer.
        c._chat = MagicMock()  # capture the appended line; hide_typing_indicator becomes a no-op
        c._waiting_for_response = True
        t.setInterval(1)
        t.start()
        deadline = time.time() + 2.0
        while t.isActive() and time.time() < deadline:
            app.processEvents()
        # one more turn so a queued slot runs
        for _ in range(20):
            app.processEvents()
        lines = [call.args[0] for call in c._chat.append_system_message.call_args_list if call.args]
        out["fired"] = not t.isActive()
        out["waiting_cleared"] = c._waiting_for_response is False
        out["no_response_lines"] = sum(1 for s in lines if s == cp.NO_RESPONSE_LINE)
        out["hide_typing_indicator_calls"] = c._chat.hide_typing_indicator.call_count
        out["production_connect_live"] = out["fired"] and out["waiting_cleared"] and out["no_response_lines"] == 1
        # single-shot: after firing it must not re-arm itself
        for _ in range(50):
            app.processEvents()
        out["still_inactive_after_pump"] = not t.isActive()
    finally:
        chat_path.write_bytes(original)
        out["restored"] = chat_path.read_bytes() == original
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
