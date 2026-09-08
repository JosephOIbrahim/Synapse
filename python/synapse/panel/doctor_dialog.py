"""Artist-requested install diagnostics, without a model turn or scene edits."""
from __future__ import annotations

import json


def format_report(result):
    """Read the real MCP envelope; missing or unrun checks are never passes."""
    if not isinstance(result, dict):
        raise ValueError("The check returned no diagnostic report.")
    if result.get("isError"):
        detail = "\n".join(block.get("text", "") for block in result.get("content", [])
                           if isinstance(block, dict) and block.get("type") == "text")
        raise ValueError(detail or "The diagnostic tool reported an error.")
    if "checks" not in result:
        payload = result.get("structuredContent")
        if not isinstance(payload, dict):
            payload = None
            for block in result.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    try:
                        candidate = json.loads(block.get("text", ""))
                    except (ValueError, TypeError):
                        continue
                    if isinstance(candidate, dict) and "checks" in candidate:
                        payload = candidate
                        break
        result = payload if isinstance(payload, dict) else {}
    checks = result.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("The check returned no diagnostic report.")
    counts = {"ok": 0, "fail": 0, "skipped": 0}
    labels = {"ok": "PASS", "fail": "NEEDS ATTENTION", "skipped": "NOT CHECKED"}
    lines = []
    for check in checks:
        if (not isinstance(check, dict) or check.get("status") not in counts
                or not isinstance(check.get("name"), str)
                or not isinstance(check.get("detail"), str)):
            raise ValueError("The diagnostic report was incomplete or unreadable.")
        status = check["status"]
        counts[status] += 1
        lines.append("%s — %s\n%s" % (
            labels[status], check["name"].replace("_", " "), check["detail"]))
    summary = "%d passed · %d need attention · %d not checked" % (
        counts["ok"], counts["fail"], counts["skipped"])
    return summary + "\n\n" + "\n\n".join(lines)


try:
    from PySide6 import QtCore, QtWidgets
except ImportError:
    try:
        from PySide2 import QtCore, QtWidgets
    except ImportError:
        QtCore = QtWidgets = None


# A closing/deleted panel must not destroy a running QThread. No scene or
# memory handles live here; each bounded transport call releases itself.
_CALLS = set()


if QtWidgets is not None:
    from .direct_tool import DirectToolCall
    from .designsystem import components as c

    class DoctorDialog(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Check SYNAPSE")
            self.setModal(False)
            self.resize(640, 480)
            self._worker = None
            layout = QtWidgets.QVBoxLayout(self)
            description = QtWidgets.QLabel(
                "Check this SYNAPSE installation. No model request or scene changes.")
            description.setWordWrap(True)
            layout.addWidget(description)
            self.report = QtWidgets.QPlainTextEdit()
            self.report.setReadOnly(True)
            self.report.setAccessibleName("SYNAPSE diagnostic report")
            layout.addWidget(self.report, 1)
            row = QtWidgets.QHBoxLayout()
            self.run_button = c.Button("Run again", variant="primary")
            self.run_button.clicked.connect(self.run_check)
            self.copy_button = c.Button("Copy report", variant="ghost")
            self.copy_button.setEnabled(False)
            self.copy_button.clicked.connect(self._copy_report)
            close = c.Button("Close", variant="ghost")
            close.clicked.connect(self.close)
            row.addWidget(self.run_button)
            row.addWidget(self.copy_button)
            row.addStretch(1)
            row.addWidget(close)
            layout.addLayout(row)

        @QtCore.Slot()
        def run_check(self):
            if self._worker is not None:
                return
            self.run_button.setEnabled(False)
            self.run_button.setText("Checking…")
            self.copy_button.setEnabled(False)
            self.report.setPlainText("Checking SYNAPSE… You can keep working in Houdini.")
            # Explicit no-bundle request: the artist asked for a check, not an export.
            call = DirectToolCall("synapse_doctor", {"bundle": False}, parent=None)
            self._worker = call
            _CALLS.add(call)
            call.finished_ok.connect(self._show_report)
            call.failed.connect(self._show_failure)
            call.finished.connect(self._finished)
            call.finished.connect(lambda active=call: _CALLS.discard(active))
            call.finished.connect(call.deleteLater)
            call.start()

        @QtCore.Slot(object)
        def _show_report(self, result):
            try:
                self.report.setPlainText(format_report(result))
            except (ValueError, TypeError) as exc:
                self._show_failure(str(exc))
            self.copy_button.setEnabled(True)

        @QtCore.Slot(str)
        def _show_failure(self, message):
            self.report.setPlainText("SYNAPSE check unavailable\n\n" + message)
            self.copy_button.setEnabled(True)

        @QtCore.Slot()
        def _finished(self):
            self._worker = None
            self.run_button.setText("Run again")
            self.run_button.setEnabled(True)

        def _copy_report(self):
            QtWidgets.QApplication.clipboard().setText(self.report.toPlainText())
