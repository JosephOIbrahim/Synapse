"""Display an existing recall result. No transport, store, worker or timer.

The pure adapter understands the STATUS/payload contract and the existing
handlers_memory -> tracker found/matches response. Unknown is not a miss.
"""

import json
from collections.abc import Mapping


def recall_view(result):
    """Return display text, preserving explicit failure before hit evidence."""
    if not isinstance(result, Mapping):
        return {"status": "UNKNOWN", "deposit": "UNKNOWN"}
    status = result.get("STATUS", result.get("status"))
    payload = result.get("payload", result)
    if not isinstance(payload, Mapping):
        payload = {}
    error = result.get("error") or payload.get("error")
    if status in ("UNAVAILABLE", "BLOCKED"):
        return {"status": status, "deposit": str(
            result.get("reason") or payload.get("reason") or error or status)}
    if error:
        return {"status": "UNAVAILABLE", "deposit": str(error)}
    # Only the documented legacy boolean constitutes success without STATUS.
    legacy = status is None and "found" in result
    hit = result.get("found") if legacy else payload.get("hit")
    if status != "SUCCESS" and not legacy:
        return {"status": "UNKNOWN", "deposit": "UNKNOWN"}
    if type(hit) is not bool:
        return {"status": "UNKNOWN", "deposit": "UNKNOWN"}
    if not hit:
        return {"status": "NO HIT", "deposit": "No matching deposit."}
    deposit = payload.get("deposit")
    if deposit is None:
        matches = payload.get("matches")
        if isinstance(matches, list):
            parts = []
            for match in matches:
                if isinstance(match, Mapping):
                    content = match.get("content")
                    if isinstance(content, str) and content:
                        parts.append(content)
            deposit = "\n\n".join(parts) or None
    if isinstance(deposit, Mapping):
        deposit = json.dumps(dict(deposit), ensure_ascii=False, sort_keys=True, indent=2)
    elif not isinstance(deposit, str):
        deposit = None
    return {"status": "HIT", "deposit": deposit or "UNKNOWN"}


def latest_recall_result(messages):
    """Read already-returned tool_result blocks, correlated by tool_use id.

    tool_status is deliberately not a source: its detail is request text.
    Malformed result JSON stays UNKNOWN instead of reviving an older hit.
    """
    names = {}
    latest = None
    for message in messages or ():
        if not isinstance(message, Mapping):
            continue
        blocks = message.get("content")
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, Mapping):
                continue
            if block.get("type") == "tool_use":
                identifier = block.get("id")
                if isinstance(identifier, str) and identifier:
                    names[identifier] = block.get("name")
            elif (block.get("type") == "tool_result"
                  and isinstance(block.get("tool_use_id"), str)
                  and bool(block.get("tool_use_id"))
                  and names.get(block.get("tool_use_id")) == "synapse_recall"):
                value = block.get("content")
                if isinstance(value, list):
                    text_blocks = [b.get("text") for b in value
                                   if isinstance(b, Mapping) and b.get("type") == "text"]
                    value = ("\n".join(text_blocks) if all(isinstance(text, str) for text in text_blocks)
                             else None)
                if block.get("is_error"):
                    latest = {"STATUS": "UNAVAILABLE", "reason": value or "UNKNOWN"}
                    continue
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except (ValueError, TypeError):
                        value = {}
                latest = value if isinstance(value, Mapping) else {}
    return latest


try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
    except ImportError:
        QtCore = QtGui = QtWidgets = None


if QtWidgets is not None:
    from .designsystem import components as c, rhythm, tokens as t

    class RecallCard(c.Card):
        """Three existing DsCard bands; updates paint facts already received."""

        def __init__(self, parent=None):
            super().__init__(parent=parent)
            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            bands = QtWidgets.QVBoxLayout(self)
            bands.setContentsMargins(0, 0, 0, 0)  # rhythm-exempt: fixed DsCard band seam; supplied roles describe collections, not the interior
            bands.setSpacing(0)  # rhythm-exempt: bands touch at their shared hairlines; card role would separate them
            # The eyebrow: rhythm_role="label" is the one type applier here
            # (mono, upper, tracked); TYPE_ROLES['label'] is a different thing.
            self.header = c.label("what I remember")
            self.header.setObjectName("DsCardHeader")
            self.header.setProperty("rhythm_role", "label")
            self.body = QtWidgets.QTextBrowser()
            self.body.setObjectName("DsCardBody")
            self.body.setReadOnly(True)
            self.body.setOpenExternalLinks(False)
            self.body.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.body.setMinimumHeight(t.SPACE_LG)
            self.body.setMaximumHeight(t.SPACE_32 * 4)
            self.body.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
            footer = QtWidgets.QWidget()
            footer.setObjectName("DsCardFooter")
            footer.setProperty("rhythm_role", "stack")
            footer.setAttribute(QtCore.Qt.WA_StyledBackground, True)
            row = QtWidgets.QHBoxLayout(footer)
            self.action = c.Button("Copy", variant="ghost")
            self.action.setObjectName("DsVerb")
            self.action.setToolTip("Copy the displayed deposit")
            self.action.clicked.connect(self._copy_deposit)
            self.status = c.Badge("UNKNOWN")
            self.status.setProperty("rhythm_role", "tag")
            row.addWidget(self.action)
            row.addStretch(1)
            row.addWidget(self.status)
            for band in (self.header, self.body, footer):
                bands.addWidget(band)
            self.set_result(None)
            rhythm.apply(self)

        def set_result(self, result):
            view = recall_view(result)
            self.body.setPlainText(view["deposit"])
            self.status.setText(view["status"])
            self.status.setProperty("status", view["status"])
            self.action.setEnabled(view["deposit"] != "UNKNOWN")
            c.repolish(self.status)

        def _copy_deposit(self):
            QtWidgets.QApplication.clipboard().setText(self.body.toPlainText())
else:
    class RecallCard:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("UNAVAILABLE: recall card requires PySide6 or PySide2")
