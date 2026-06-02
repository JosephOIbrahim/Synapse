"""Unified command palette — the 1:1 + discovery surface.

Ctrl+K fuzzy-searches across EVERYTHING the artist can ask for:
  * the 110 server tools (canonical _tool_registry.TOOL_DEFS), destructive ones
    flagged off the registry's own annotation;
  * the legacy knowledge base — slash-commands, network recipes, APEX rigs, VEX
    functions (via command_palette.build_palette_entries);
  * per-domain "galleries" — material presets and render-quality tiers.
Every pick emits a ready-to-send prompt that routes through the agent (and thus
the gated bridge path), so the palette is deterministic discovery with the
safety model intact.
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

try:
    from synapse.panel.tool_filter import (
        classify_tool, PALETTE_VERBS, PALETTE_CONTEXTS,
    )
except Exception:  # pragma: no cover
    classify_tool = None
    PALETTE_VERBS = ("build", "fix", "explain", "optimize", "render")
    PALETTE_CONTEXTS = ("SOP", "LOP", "COP", "Karma", "USD")


def _ctx_rank(ctx):
    return list(PALETTE_CONTEXTS).index(ctx) if ctx in PALETTE_CONTEXTS else len(PALETTE_CONTEXTS)


def _ctx_label(ctx):
    return ctx if ctx else "Other"


def _classify(name, title, desc):
    if classify_tool is None:
        return "build", None
    try:
        return classify_tool(name, title, desc)
    except Exception:
        return "build", None

_MATERIAL_PRESETS = [
    "glass", "mirror", "rough_metal", "polished_metal", "skin",
    "cloth", "plastic", "ceramic", "wax", "rubber",
]
_RENDER_TIERS = ["draft", "preview", "production"]
_CATEGORY_DOMAIN = {
    "command": "Commands", "recipe": "Recipes", "apex": "APEX Rigging", "vex": "VEX",
}
_CATEGORY_PREFIX = {
    "recipe": "Build this network recipe — ",
    "apex": "Build this APEX rig — ",
    "vex": "Explain this VEX — ",
}


def _domain(name):
    """Friendly domain for a registry tool name (drives grouping)."""
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
        if any(k in name for k in ("usd", "prim", "stage", "solaris", "reference",
                                   "payload", "variant", "collection", "instancer", "light")):
            return "USD / Solaris"
        if any(k in name for k in ("material", "mtlx")):
            return "Materials"
        if any(k in name for k in ("render", "karma", "viewport")):
            return "Render"
        if "hda" in name:
            return "HDA Authoring"
        return "Scene & Nodes"
    return "Other"


def _load_entries():
    """All palette entries as dicts {domain, title, desc, send, destructive}."""
    entries = []

    # a) the 110 registry tools — classified on both axes (verb × context)
    try:
        from synapse.mcp._tool_registry import TOOL_DEFS
        for d in TOOL_DEFS:
            name, desc, destr = d[0], d[3], bool(d[6])
            title = name.replace("houdini_", "").replace("synapse_", "").replace("_", " ").title()
            verb, ctx = _classify(name, title, desc)
            entries.append(dict(domain=_domain(name), title=title, desc=desc,
                                send="Use the `%s` tool." % name, destructive=destr,
                                verb=verb, context=ctx))
    except Exception:
        pass

    # b) legacy knowledge: slash-commands + recipes + APEX + VEX (pre-tagged)
    try:
        from synapse.panel.command_palette import build_palette_entries
        for e in build_palette_entries():
            send = (_CATEGORY_PREFIX.get(e.category, "") + (e.description or e.label)).strip()
            entries.append(dict(domain=_CATEGORY_DOMAIN.get(e.category, "Commands"),
                                title=e.label, desc=e.description or "", send=send,
                                destructive=False,
                                verb=getattr(e, "verb", "build"),
                                context=getattr(e, "context", None)))
    except Exception:
        pass

    # c) galleries: material presets (build · Karma) + render tiers (render · Karma)
    for m in _MATERIAL_PRESETS:
        pretty = m.replace("_", " ").title()
        entries.append(dict(domain="Materials", title="Material: %s" % pretty,
                            desc="Create a %s material and assign it" % pretty.lower(),
                            send="Create a %s material (houdini_create_material) and assign it "
                                 "to the selected geometry." % m,
                            destructive=False, verb="build", context="Karma"))
    for tier in _RENDER_TIERS:
        entries.append(dict(domain="Render", title="Render: %s" % tier.title(),
                            desc="Render at %s quality" % tier,
                            send="Render the current scene at %s quality (render_progressively)." % tier,
                            destructive=False, verb="render", context="Karma"))

    # grouped by context (where), then verb (what), then title
    entries.sort(key=lambda e: (_ctx_rank(e["context"]), e["verb"], e["title"]))
    return entries


class ToolPalette(QtWidgets.QWidget):
    """Frameless fuzzy palette over tools + recipes + commands + galleries."""

    command_selected = Signal(str)  # emits a ready-to-send prompt

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsRoot")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlags(Qt.Popup)
        self.setMinimumSize(440, 480)
        self._rows = _load_entries()

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(t.SPACE_SM, t.SPACE_SM, t.SPACE_SM, t.SPACE_SM)
        lay.setSpacing(t.SPACE_XS)

        self._search = QtWidgets.QLineEdit()
        self._search.setObjectName("DsField")
        self._search.setPlaceholderText("Search %d tools, recipes & commands…" % len(self._rows))
        self._search.textChanged.connect(self._refilter)
        self._search.installEventFilter(self)
        lay.addWidget(self._search)

        # two axes — reach a tool by what you want DOne or by WHERE you are
        self._verb = None
        self._context = None
        self._verb_chips = {}
        self._ctx_chips = {}
        lay.addLayout(self._build_chip_row("verb", "DO"))
        lay.addLayout(self._build_chip_row("context", "WHERE"))
        self._style_chips()

        self._list = QtWidgets.QListWidget()
        self._list.setObjectName("DsList")
        self._list.itemActivated.connect(self._choose)
        self._list.itemClicked.connect(self._choose)
        lay.addWidget(self._list, 1)

        hint = c.label("↑↓ navigate · Enter run · Esc close · filter by DO × WHERE · "
                       "destructive items are gated", role="caption")
        lay.addWidget(hint)

        self._populate(self._rows)
        self._search.setFocus()

    # ------------------------------------------------------------------
    def _build_chip_row(self, kind, tag_text):
        """A row of toggle chips for one axis (verb or context). 'All' clears it."""
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(t.SPACE_XS)
        tag = c.label(tag_text, role="caption")
        tag.setStyleSheet("color:%s; letter-spacing:1.5px;" % t.TEXT_TERTIARY)
        tag.setMinimumWidth(44)
        row.addWidget(tag)
        chips = self._verb_chips if kind == "verb" else self._ctx_chips
        values = [None] + list(PALETTE_VERBS if kind == "verb" else PALETTE_CONTEXTS)
        for v in values:
            text = "All" if v is None else (v.title() if kind == "verb" else v)
            btn = QtWidgets.QPushButton(text)
            btn.setObjectName("DsChip")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFlat(True)
            btn.clicked.connect(lambda _=False, k=kind, val=v: self._set_axis(k, val))
            chips[v] = btn
            row.addWidget(btn)
        row.addStretch(1)
        return row

    def _set_axis(self, kind, value):
        """Set (or toggle off) the active filter on one axis, then re-filter."""
        if kind == "verb":
            self._verb = None if self._verb == value else value
        else:
            self._context = None if self._context == value else value
        self._style_chips()
        self._refilter(self._search.text())

    def _style_chips(self):
        for v, btn in self._verb_chips.items():
            self._style_chip(btn, v == self._verb)
        for v, btn in self._ctx_chips.items():
            self._style_chip(btn, v == self._context)

    def _style_chip(self, btn, active):
        if active:
            btn.setStyleSheet(
                "QPushButton#DsChip{background:%s; color:%s; border:none;"
                " border-radius:3px; padding:3px 8px; font-family:%s;"
                " font-size:10px; letter-spacing:1px;}"
                % (t.SIGNAL_TINT, t.TEXT_ACCENT, t.FONT_MONO))
        else:
            btn.setStyleSheet(
                "QPushButton#DsChip{background:transparent; color:%s; border:none;"
                " padding:3px 8px; font-family:%s; font-size:10px; letter-spacing:1px;}"
                "QPushButton#DsChip:hover{color:%s;}"
                % (t.TEXT_TERTIARY, t.FONT_MONO, t.TEXT_SECONDARY))

    # ------------------------------------------------------------------
    def _visible(self):
        """Rows passing the active verb + context filters (axis navigation)."""
        rows = self._rows
        if self._verb:
            rows = [e for e in rows if e.get("verb") == self._verb]
        if self._context:
            rows = [e for e in rows if e.get("context") == self._context]
        return rows

    def _populate(self, rows):
        self._list.clear()
        last_domain = None
        for e in rows:
            group = _ctx_label(e.get("context"))
            if group != last_domain:
                head = QtWidgets.QListWidgetItem(group.upper())
                head.setFlags(Qt.NoItemFlags)
                try:
                    head.setForeground(QColor(t.TEXT_TERTIARY))
                except Exception:
                    pass
                self._list.addItem(head)
                last_domain = group
            label = ("  ⚠ " if e["destructive"] else "  ") + e["title"]
            item = QtWidgets.QListWidgetItem(label)
            item.setData(Qt.UserRole, e["send"])
            item.setToolTip("%s%s" % (
                e["desc"],
                "\n\n(destructive — will ask before running)" if e["destructive"] else ""))
            if e["destructive"]:
                try:
                    item.setForeground(QColor(t.WARN))
                except Exception:
                    pass
            self._list.addItem(item)
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.UserRole):
                self._list.setCurrentRow(i)
                break

    def _refilter(self, text):
        q = text.strip().lower()
        rows = self._visible()              # apply the verb × context axes first
        if q:
            rows = [e for e in rows
                    if q in e["title"].lower() or q in e["desc"].lower()
                    or q in e["send"].lower()]
        self._populate(rows)

    def _choose(self, item):
        send = item.data(Qt.UserRole)
        if send:
            self.command_selected.emit(send)
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
