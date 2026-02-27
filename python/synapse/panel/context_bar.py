"""Context Bar v2 -- rich contextual status bar for the Synapse panel.

Shows breadcrumb path, memory status, health indicator, contextual quick
action buttons (adapting to SOP/LOP/DOP/TOP/APEX network types), and the
current frame number.

Replaces the v1 ContextChips implementation while keeping backward compat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ── Qt imports (PySide6 primary, PySide2 fallback, None standalone) ─────
_QT_AVAILABLE = False
try:
    from PySide6 import QtWidgets, QtCore, QtGui  # noqa: F401
    from PySide6.QtCore import Signal
    _QT_AVAILABLE = True
except ImportError:
    try:
        from PySide2 import QtWidgets, QtCore, QtGui  # noqa: F401
        from PySide2.QtCore import Signal
        _QT_AVAILABLE = True
    except ImportError:
        QtWidgets = None
        QtCore = None
        QtGui = None
        Signal = None

# ── Houdini import (optional for standalone/testing) ────────────────────
_HOU_AVAILABLE = False
try:
    import hou
    _HOU_AVAILABLE = True
except ImportError:
    hou = None

# ── Design tokens (panel-local re-exports) ──────────────────────────────
try:
    from synapse.panel import tokens as _t
    FIRE = _t.FIRE
    GROW = _t.GROW
    WARN = getattr(_t, "WARN", "#FFAB00")
    ERROR = _t.ERROR
    VOID = _t.VOID
    CARBON = _t.CARBON
    GRAPHITE = _t.GRAPHITE
    NEAR_BLACK = _t.NEAR_BLACK
    BONE = _t.BONE
    TEXT = getattr(_t, "TEXT", "#E0E0E0")
    TEXT_DIM = getattr(_t, "TEXT_DIM", "#999999")
    HOVER = getattr(_t, "HOVER", "#484848")
    SIGNAL = _t.SIGNAL
    FONT_MONO = _t.FONT_MONO
    SIZE_LABEL = _t.SIZE_LABEL
    SPACE_SM = _t.SPACE_SM
    SPACE_XS = _t.SPACE_XS
except ImportError:
    FIRE = "#e8833a"
    GROW = "#4caf50"
    WARN = "#ff9800"
    ERROR = "#f44336"
    VOID = "#252525"
    CARBON = "#333333"
    GRAPHITE = "#222222"
    NEAR_BLACK = "#3c3c3c"
    BONE = "#cccccc"
    TEXT = "#E0E0E0"
    TEXT_DIM = "#999999"
    HOVER = "#484848"
    SIGNAL = "#00D4FF"
    FONT_MONO = "JetBrains Mono"
    SIZE_LABEL = 22
    SPACE_SM = 8
    SPACE_XS = 4


# ======================================================================
# 1. State
# ======================================================================

@dataclass
class ContextBarState:
    """Holds current state for the context bar.  Updated periodically."""

    network_path: str = "/"
    breadcrumbs: List[str] = field(default_factory=list)
    memory_stage: str = "none"          # "flat", "structured", "composed", "none"
    health: str = "good"                # "good", "warning", "error"
    health_issues: int = 0
    network_type: str = "OBJ"           # SOP, LOP, DOP, TOP, APEX, OBJ, OUT, SHOP
    frame: int = 1
    frame_range: Tuple[int, int] = (1, 240)
    selected_count: int = 0
    quick_actions: List[Tuple[str, str]] = field(default_factory=list)


# ======================================================================
# 2. Quick-action lookup
# ======================================================================

def _get_quick_actions(network_type: str, has_selection: bool) -> List[Tuple[str, str]]:
    """Return contextual action buttons based on *network_type*.

    Each entry is ``(label, command)`` where *command* is a slash-command
    string the panel routes via ``_route_cmd``.
    """
    ntype = (network_type or "").upper()

    if ntype in ("SOP", "OBJ"):
        actions = [
            ("Explain", "/explain"),
            ("Diagnose", "/diagnose"),
            ("Trace", "/trace"),
        ]
        if has_selection:
            actions.append(("Inspect", "/inspect"))
        return actions

    if ntype == "LOP":
        return [
            ("Stage Info", "/scene"),
            ("Materials", "/explain"),
            ("Preflight", "/preflight"),
            ("Render", "/preflight"),
        ]

    if ntype == "DOP":
        return [
            ("Explain", "/explain"),
            ("Diagnose", "/diagnose"),
        ]

    if ntype == "TOP":
        return [
            ("Explain", "/explain"),
            ("Diagnose", "/diagnose"),
        ]

    if ntype == "APEX":
        return [
            ("APEX Explain", "/apex explain"),
            ("APEX Trace", "/apex trace"),
            ("APEX Recipes", "/apex recipes"),
        ]

    if ntype == "OUT":
        return [
            ("Preflight", "/preflight"),
            ("Diagnose", "/diagnose"),
        ]

    # Default fallback
    return [
        ("Explain", "/explain"),
        ("Diagnose", "/diagnose"),
    ]


# ======================================================================
# 3. State builder
# ======================================================================

def _detect_network_type(path: str) -> str:
    """Infer network type from a Houdini node path string."""
    if not path or path == "/":
        return "OBJ"

    # If hou is available, try the node directly
    if _HOU_AVAILABLE and hou is not None:
        try:
            node = hou.node(path)
            if node is not None:
                cat = node.childTypeCategory()
                if cat is not None:
                    cat_name = cat.name()
                    mapping = {
                        "Sop": "SOP",
                        "Lop": "LOP",
                        "Dop": "DOP",
                        "Top": "TOP",
                        "apex": "APEX",
                        "Object": "OBJ",
                        "Driver": "OUT",
                        "Shop": "SHOP",
                    }
                    for key, value in mapping.items():
                        if key.lower() in cat_name.lower():
                            return value
        except Exception:
            pass

    # Fallback: heuristic from path segments
    path_lower = path.lower()
    if "/stage" in path_lower or "/lop" in path_lower:
        return "LOP"
    if "/out" in path_lower:
        return "OUT"
    if "/dop" in path_lower:
        return "DOP"
    if "/topnet" in path_lower or "/top" in path_lower:
        return "TOP"
    if "/apex" in path_lower:
        return "APEX"
    if "/shop" in path_lower:
        return "SHOP"
    if "/obj" in path_lower:
        # Could be OBJ level or inside a SOP network
        parts = path.strip("/").split("/")
        if len(parts) >= 2:
            return "SOP"
        return "OBJ"
    return "OBJ"


def update_context(
    login_data: Optional[dict] = None,
    last_diagnosis=None,
) -> ContextBarState:
    """Gather current state from Houdini and return a populated state object.

    Parameters
    ----------
    login_data : dict, optional
        Shot-login payload; used to read ``memory_stage``.
    last_diagnosis : object, optional
        Result from the scene doctor.  Expects ``.items`` list where each item
        has a ``.severity`` string (``"critical"``, ``"error"``, ``"warning"``).
    """
    state = ContextBarState()

    # -- Network path + breadcrumbs ------------------------------------
    if _HOU_AVAILABLE and hou is not None:
        try:
            editor = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
            if editor is not None:
                state.network_path = editor.pwd().path()
        except Exception:
            state.network_path = "/"
    else:
        state.network_path = "/"

    crumbs = [c for c in state.network_path.strip("/").split("/") if c]
    state.breadcrumbs = crumbs if crumbs else ["/"]

    # -- Memory stage --------------------------------------------------
    if login_data and isinstance(login_data, dict):
        stage = login_data.get("memory_stage", "none")
        if stage in ("flat", "structured", "composed", "none"):
            state.memory_stage = stage
        else:
            state.memory_stage = "none"
    else:
        state.memory_stage = "none"

    # -- Health --------------------------------------------------------
    if last_diagnosis is not None:
        items = getattr(last_diagnosis, "items", None) or []
        crits = 0
        warns = 0
        for item in items:
            sev = getattr(item, "severity", "").lower()
            if sev in ("critical", "error"):
                crits += 1
            elif sev == "warning":
                warns += 1
        total = crits + warns
        state.health_issues = total
        if crits > 0:
            state.health = "error"
        elif warns > 0:
            state.health = "warning"
        else:
            state.health = "good"
    else:
        state.health = "good"
        state.health_issues = 0

    # -- Network type --------------------------------------------------
    state.network_type = _detect_network_type(state.network_path)

    # -- Frame ---------------------------------------------------------
    if _HOU_AVAILABLE and hou is not None:
        try:
            state.frame = int(hou.frame())
        except Exception:
            state.frame = 1
        try:
            fr = hou.playbar.frameRange()
            state.frame_range = (int(fr[0]), int(fr[1]))
        except Exception:
            state.frame_range = (1, 240)
    else:
        state.frame = 1
        state.frame_range = (1, 240)

    # -- Selection -----------------------------------------------------
    if _HOU_AVAILABLE and hou is not None:
        try:
            state.selected_count = len(hou.selectedNodes())
        except Exception:
            state.selected_count = 0
    else:
        state.selected_count = 0

    # -- Quick actions -------------------------------------------------
    state.quick_actions = _get_quick_actions(
        state.network_type, state.selected_count > 0,
    )

    return state


# ======================================================================
# 4. Widget helpers (used by builder + updater)
# ======================================================================

_HEALTH_COLORS = {
    "good": GROW,
    "warning": WARN,
    "error": ERROR,
}

_MEMORY_COLORS = {
    "none": TEXT_DIM,
    "flat": TEXT_DIM,
    "structured": SIGNAL,
    "composed": GROW,
}

_MEMORY_ICONS = {
    "none": "",
    "flat": "flat",
    "structured": "structured",
    "composed": "composed",
}


def _breadcrumb_text(state: ContextBarState) -> str:
    """Format breadcrumbs with separator."""
    if not state.breadcrumbs or state.breadcrumbs == ["/"]:
        return "/"
    return "/" + " > ".join(state.breadcrumbs)


def _health_label(state: ContextBarState) -> str:
    """Human-readable health string."""
    if state.health == "warning":
        return "{n} issue{s}".format(
            n=state.health_issues,
            s="s" if state.health_issues != 1 else "",
        )
    if state.health == "error":
        return "{n} error{s}".format(
            n=state.health_issues,
            s="s" if state.health_issues != 1 else "",
        )
    return "Ready"


def _btn_stylesheet() -> str:
    """Stylesheet for compact action buttons."""
    return (
        "QPushButton {{"
        "  background: {bg}; color: {fg}; border: 1px solid {border};"
        "  border-radius: 4px; padding: 2px 8px;"
        "  font-size: 9pt; font-family: '{mono}', Consolas, monospace;"
        "}}"
        "QPushButton:hover {{"
        "  background: {hover}; border-color: {accent};"
        "}}"
        "QPushButton:pressed {{"
        "  background: {pressed};"
        "}}"
    ).format(
        bg=NEAR_BLACK, fg=TEXT, border=CARBON, mono=FONT_MONO,
        hover=HOVER, accent=FIRE, pressed=GRAPHITE,
    )


# ======================================================================
# 5. Widget builder + updater (Qt-dependent)
# ======================================================================

if _QT_AVAILABLE:

    def build_context_bar_widget(
        state: ContextBarState,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> "QtWidgets.QWidget":
        """Create the full context bar as a Qt widget.

        Layout::

            +-------------------------------------------------------+
            | /obj/geo1 > mountain_setup   structured   * Ready     |
            | [Explain] [Diagnose] [Trace]              frame 24    |
            +-------------------------------------------------------+

        Quick-action buttons store their command string in the Qt property
        ``"command"``.  The host panel connects ``clicked`` to a handler
        that reads ``sender().property("command")``.
        """
        root = QtWidgets.QWidget(parent)
        root.setObjectName("context_bar_v2")
        root.setStyleSheet(
            "QWidget#context_bar_v2 {{"
            "  background: transparent;"
            "}}".format()
        )

        outer = QtWidgets.QVBoxLayout(root)
        outer.setContentsMargins(16, SPACE_XS, 16, SPACE_XS)
        outer.setSpacing(SPACE_XS)

        # -- Row 1: breadcrumb | stretch | memory badge | health dot --
        row1 = QtWidgets.QHBoxLayout()
        row1.setSpacing(SPACE_SM)

        breadcrumb = QtWidgets.QLabel(_breadcrumb_text(state))
        breadcrumb.setObjectName("ctx_breadcrumb")
        breadcrumb.setStyleSheet(
            "color: {fg}; font-size: 10pt;"
            " font-family: '{mono}', Consolas, monospace;"
            " background: transparent;".format(fg=SIGNAL, mono=FONT_MONO)
        )
        row1.addWidget(breadcrumb)

        row1.addStretch()

        # Memory stage badge
        mem_color = _MEMORY_COLORS.get(state.memory_stage, TEXT_DIM)
        mem_text = _MEMORY_ICONS.get(state.memory_stage, "")
        memory_label = QtWidgets.QLabel(mem_text)
        memory_label.setObjectName("ctx_memory")
        memory_label.setStyleSheet(
            "color: {fg}; font-size: 9pt;"
            " font-family: '{mono}', Consolas, monospace;"
            " background: transparent; padding: 0 4px;".format(
                fg=mem_color, mono=FONT_MONO,
            )
        )
        if not mem_text:
            memory_label.setVisible(False)
        row1.addWidget(memory_label)

        # Health indicator (colored dot + label)
        health_color = _HEALTH_COLORS.get(state.health, GROW)
        health_text = _health_label(state)

        health_label = QtWidgets.QLabel(
            "<span style='color:{dot};'>&#9679;</span> {txt}".format(
                dot=health_color, txt=health_text,
            )
        )
        health_label.setObjectName("ctx_health")
        health_label.setStyleSheet(
            "color: {fg}; font-size: 9pt;"
            " font-family: '{mono}', Consolas, monospace;"
            " background: transparent;".format(fg=health_color, mono=FONT_MONO)
        )
        row1.addWidget(health_label)

        outer.addLayout(row1)

        # -- Row 2: quick actions | stretch | frame number ------------
        row2 = QtWidgets.QHBoxLayout()
        row2.setSpacing(SPACE_XS)

        actions_container = QtWidgets.QWidget()
        actions_container.setObjectName("ctx_actions")
        actions_container.setStyleSheet("background: transparent;")
        actions_layout = QtWidgets.QHBoxLayout(actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(SPACE_XS)

        btn_style = _btn_stylesheet()
        for label, command in state.quick_actions:
            btn = QtWidgets.QPushButton(label)
            btn.setProperty("command", command)
            btn.setObjectName(
                "ctx_action_" + label.lower().replace(" ", "_")
            )
            btn.setStyleSheet(btn_style)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            actions_layout.addWidget(btn)

        row2.addWidget(actions_container)
        row2.addStretch()

        frame_label = QtWidgets.QLabel("frame {f}".format(f=state.frame))
        frame_label.setObjectName("ctx_frame")
        frame_label.setStyleSheet(
            "color: {fg}; font-size: 9pt;"
            " font-family: '{mono}', Consolas, monospace;"
            " background: transparent;".format(fg=TEXT_DIM, mono=FONT_MONO)
        )
        row2.addWidget(frame_label)

        outer.addLayout(row2)

        return root

    def update_context_bar_widget(
        widget: "QtWidgets.QWidget",
        state: ContextBarState,
    ) -> None:
        """Update an existing context-bar widget with new state (no rebuild).

        Finds child widgets by object names and updates text / styles.
        Called every few seconds by the panel's refresh timer.
        """
        # Breadcrumb
        breadcrumb = widget.findChild(QtWidgets.QLabel, "ctx_breadcrumb")
        if breadcrumb is not None:
            breadcrumb.setText(_breadcrumb_text(state))

        # Memory badge
        memory = widget.findChild(QtWidgets.QLabel, "ctx_memory")
        if memory is not None:
            mem_text = _MEMORY_ICONS.get(state.memory_stage, "")
            mem_color = _MEMORY_COLORS.get(state.memory_stage, TEXT_DIM)
            memory.setText(mem_text)
            memory.setStyleSheet(
                "color: {fg}; font-size: 9pt;"
                " font-family: '{mono}', Consolas, monospace;"
                " background: transparent; padding: 0 4px;".format(
                    fg=mem_color, mono=FONT_MONO,
                )
            )
            memory.setVisible(bool(mem_text))

        # Health
        health = widget.findChild(QtWidgets.QLabel, "ctx_health")
        if health is not None:
            health_color = _HEALTH_COLORS.get(state.health, GROW)
            health_text = _health_label(state)
            health.setText(
                "<span style='color:{dot};'>&#9679;</span> {txt}".format(
                    dot=health_color, txt=health_text,
                )
            )
            health.setStyleSheet(
                "color: {fg}; font-size: 9pt;"
                " font-family: '{mono}', Consolas, monospace;"
                " background: transparent;".format(
                    fg=health_color, mono=FONT_MONO,
                )
            )

        # Frame
        frame_lbl = widget.findChild(QtWidgets.QLabel, "ctx_frame")
        if frame_lbl is not None:
            frame_lbl.setText("frame {f}".format(f=state.frame))

        # Quick actions -- rebuild buttons inside the container
        actions_container = widget.findChild(
            QtWidgets.QWidget, "ctx_actions",
        )
        if actions_container is not None:
            layout = actions_container.layout()
            if layout is not None:
                # Clear existing buttons
                while layout.count():
                    item = layout.takeAt(0)
                    w = item.widget()
                    if w is not None:
                        w.deleteLater()

                # Add new buttons
                btn_style = _btn_stylesheet()
                for label, command in state.quick_actions:
                    btn = QtWidgets.QPushButton(label)
                    btn.setProperty("command", command)
                    btn.setObjectName(
                        "ctx_action_" + label.lower().replace(" ", "_")
                    )
                    btn.setStyleSheet(btn_style)
                    btn.setCursor(QtCore.Qt.PointingHandCursor)
                    layout.addWidget(btn)

    # ==================================================================
    # Backwards compatibility wrapper
    # ==================================================================

    class ContextChips(QtWidgets.QWidget):
        """Thin backwards-compat wrapper around v2 context bar.

        Existing panel code that instantiates ``ContextChips`` and calls
        ``set_network_path`` / ``set_frame`` etc. continues to work.
        """

        def __init__(self, parent=None):
            super().__init__(parent)
            self._state = ContextBarState()
            self._inner = build_context_bar_widget(self._state, self)
            lay = QtWidgets.QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(self._inner)

        def _refresh(self):
            update_context_bar_widget(self._inner, self._state)

        def set_connected(self, connected):
            # v2 doesn't have a connection LED; no-op for compat.
            pass

        def set_network_path(self, path):
            self._state.network_path = path or "/"
            crumbs = (
                [c for c in path.strip("/").split("/") if c]
                if path else ["/"]
            )
            self._state.breadcrumbs = crumbs
            self._state.network_type = _detect_network_type(path or "/")
            self._state.quick_actions = _get_quick_actions(
                self._state.network_type, self._state.selected_count > 0,
            )
            self._refresh()

        def set_selection_count(self, count):
            self._state.selected_count = count
            self._state.quick_actions = _get_quick_actions(
                self._state.network_type, count > 0,
            )
            self._refresh()

        def set_frame(self, frame):
            self._state.frame = int(frame)
            self._refresh()

        def set_project_context(self, project_name, evolution_stage=""):
            stage_map = {
                "charmander": "flat",
                "charmeleon": "structured",
                "charizard": "composed",
            }
            self._state.memory_stage = stage_map.get(
                (evolution_stage or "").lower(),
                "flat" if project_name else "none",
            )
            self._refresh()

    # Keep old alias
    ContextBar = ContextChips

else:
    # No Qt -- stub out widget-dependent names so pure-data imports work.

    def build_context_bar_widget(state, parent=None):
        raise RuntimeError("Qt (PySide6/PySide2) is required for widgets")

    def update_context_bar_widget(widget, state):
        raise RuntimeError("Qt (PySide6/PySide2) is required for widgets")

    class ContextChips:
        """Stub -- Qt unavailable."""
        pass

    ContextBar = ContextChips
