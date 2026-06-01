"""Registry-driven command palette — the 1:1 surface.

Ctrl+K opens a fuzzy-searchable list of EVERY server tool (read from the
canonical _tool_registry.TOOL_DEFS), grouped by domain, with destructive tools
flagged off the registry's own ``destructive`` annotation. Selecting one hands a
clear instruction to the agent, which invokes the tool through the gated bridge
path — so the palette is deterministic discovery + the safety model is intact.

This closes the audit's core finding: the panel surfaced a chat box + 5 pills
over a 110-tool server. Now every tool is one keystroke away.
"""

try:
    from PySide6 import QtWidgets, QtCore
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QColor
except ImportError:  # pragma: no cover - Houdini ships PySide6
    from PySide2 import QtWidgets, QtCore
    from PySide2.QtCore import Qt, Signal
    from PySide2.QtGui import QColor

from synapse.panel.designsystem import tokens as t
from synapse.panel.designsystem import components as c


def _domain(name):
    """Friendly domain for a tool name (drives grouping)."""
    if name.startswith("cops_"):
        return "COPs / Generative"
    if name.startswith("tops_"):
        return "TOPS / PDG"
    if name.startswith("synapse_"):
        if any(k in name for k in ("memory", "recall", "context", "decide", "evolve")):
            return "Memory & Recall"
        if any(k in name for k in ("render", "frame", "farm", "autonomous")):
            return "Render"
        return "Orchestration & Knowledge"
    if name.startswith("houdini_"):
        if any(k in name for k in ("usd", "prim", "stage", "solaris", "reference", "payload", "variant", "collection", "instancer", "light")):
            return "USD / Solaris"
        if any(k in name for k in ("material", "mtlx")):
            return "Materials"
        if any(k in name for k in ("render", "karma", "viewport")):
            return "Render"
        if "hda" in name:
            return "HDA Authoring"
        return "Scene & Nodes"
    return "Other"


def _load_tools():
    """Read the registry → [(domain, name, title, description, destructive)]."""
    try:
        from synapse.mcp._tool_registry import TOOL_DEFS
    except Exception:
        return []
    rows = []
    for d in TOOL_DEFS:
        name, _cmd, _b, desc, _schema, _ro, destr = d[0], d[1], d[2], d[3], d[4], d[5], d[6]
        title = name.replace("houdini_", "").replace("synapse_", "").replace("_", " ").title()
        rows.append((_domain(name), name, title, desc, bool(destr)))
    rows.sort(key=lambda r: (r[0], r[2]))
    return rows


class ToolPalette(QtWidgets.QWidget):
    """Frameless fuzzy palette over the full tool registry."""

    command_selected = Signal(str)  # emits the tool name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsRoot")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlags(Qt.Popup)
        self.setMinimumSize(420, 460)
        self._rows = _load_tools()

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(t.SPACE_SM, t.SPACE_SM, t.SPACE_SM, t.SPACE_SM)
        lay.setSpacing(t.SPACE_XS)

        self._search = QtWidgets.QLineEdit()
        self._search.setObjectName("DsField")
        self._search.setPlaceholderText("Search %d tools…" % len(self._rows))
        self._search.textChanged.connect(self._refilter)
        self._search.installEventFilter(self)
        lay.addWidget(self._search)

        self._list = QtWidgets.QListWidget()
        self._list.setObjectName("DsList")
        self._list.itemActivated.connect(self._choose)
        self._list.itemClicked.connect(self._choose)
        lay.addWidget(self._list, 1)

        hint = c.label("↑↓ navigate · Enter run · Esc close · destructive tools are gated",
                       role="caption")
        lay.addWidget(hint)

        self._populate(self._rows)
        self._search.setFocus()

    # ------------------------------------------------------------------
    def _populate(self, rows):
        self._list.clear()
        last_domain = None
        for domain, name, title, desc, destr in rows:
            if domain != last_domain:
                head = QtWidgets.QListWidgetItem(domain.upper())
                head.setFlags(Qt.NoItemFlags)
                try:
                    head.setForeground(QColor(t.TEXT_TERTIARY))
                except Exception:
                    pass
                self._list.addItem(head)
                last_domain = domain
            label = ("  ⚠ " if destr else "  ") + title
            item = QtWidgets.QListWidgetItem(label)
            item.setData(Qt.UserRole, name)
            item.setToolTip("%s\n\n%s%s" % (name, desc, "\n\n(destructive — will ask before running)" if destr else ""))
            if destr:
                try:
                    item.setForeground(QColor(t.WARN))
                except Exception:
                    pass
            self._list.addItem(item)
        # select first real (non-header) row
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.UserRole):
                self._list.setCurrentRow(i)
                break

    def _refilter(self, text):
        q = text.strip().lower()
        if not q:
            self._populate(self._rows)
            return
        filtered = [r for r in self._rows
                    if q in r[1].lower() or q in r[2].lower() or q in r[3].lower()]
        self._populate(filtered)

    def _choose(self, item):
        name = item.data(Qt.UserRole)
        if name:
            self.command_selected.emit(name)
            self.close()

    def eventFilter(self, obj, event):
        if obj is self._search and event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Down, Qt.Key_Up):
                self._move(1 if key == Qt.Key_Down else -1)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                it = self._list.currentItem()
                if it:
                    self._choose(it)
                return True
            if key == Qt.Key_Escape:
                self.close()
                return True
        return super().eventFilter(obj, event)

    def _move(self, delta):
        n = self._list.count()
        if not n:
            return
        row = self._list.currentRow()
        for _ in range(n):
            row = (row + delta) % n
            if self._list.item(row).data(Qt.UserRole):
                self._list.setCurrentRow(row)
                return
