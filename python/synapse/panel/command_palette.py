"""Command Palette module for SYNAPSE.

Fuzzy-search popup (Ctrl+K) that searches across slash commands, recipes,
APEX recipes, VEX functions, and recent journal entries. Designed to overlay
the SYNAPSE panel inside Houdini 21.

Usage:
    palette = CommandPaletteWidget(parent=panel_widget)
    palette.command_selected.connect(handle_command)
    palette.show_palette(recent_entries=[...])
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# ---------------------------------------------------------------------------
# Qt import guard (PySide6 first, PySide2 fallback)
# ---------------------------------------------------------------------------

try:
    from PySide6.QtWidgets import (  # type: ignore[import-untyped]
        QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
        QLabel, QHBoxLayout, QFrame,
    )
    from PySide6.QtCore import Qt, Signal  # type: ignore[import-untyped]
    from PySide6.QtGui import QFont, QColor, QPalette, QKeyEvent  # type: ignore[import-untyped]
    _QT_AVAILABLE = True
except ImportError:
    try:
        from PySide2.QtWidgets import (  # type: ignore[import-untyped]
            QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
            QLabel, QHBoxLayout, QFrame,
        )
        from PySide2.QtCore import Qt, Signal  # type: ignore[import-untyped]
        from PySide2.QtGui import QFont, QColor, QPalette, QKeyEvent  # type: ignore[import-untyped]
        _QT_AVAILABLE = True
    except ImportError:
        _QT_AVAILABLE = False

# ---------------------------------------------------------------------------
# Design tokens (fallback for standalone use)
# ---------------------------------------------------------------------------

try:
    from synapse.panel import tokens as _t
    _SIGNAL = _t.SIGNAL
    _TEXT = _t.TEXT
    _TEXT_DIM = _t.TEXT_DIM
    _VOID = _t.VOID
    _CARBON = _t.CARBON
    _GRAPHITE = _t.GRAPHITE
    _NEAR_BLACK = _t.NEAR_BLACK
    _FONT_SANS = _t.FONT_SANS
except ImportError:
    _SIGNAL = "#00D4FF"
    _TEXT = "#F0F0F0"
    _TEXT_DIM = "#888888"
    _VOID = "#252525"
    _CARBON = "#333333"
    _GRAPHITE = "#222222"
    _NEAR_BLACK = "#3A3A3A"
    _FONT_SANS = "Segoe UI"


# ===================================================================
# 1. PaletteEntry dataclass
# ===================================================================

@dataclass
class PaletteEntry:
    """Single searchable entry in the command palette."""

    label: str          # display text
    command: str         # the command to execute (e.g. "/diagnose")
    category: str        # "command", "recipe", "apex", "vex", "recent"
    description: str     # brief description
    score: float = 0.0   # fuzzy match score (higher = better match)


# ===================================================================
# 2. Palette entry builder
# ===================================================================

# Hardcoded slash commands with descriptions
_SLASH_COMMANDS: list[tuple[str, str]] = [
    ("/help", "Show help and available commands"),
    ("/diagnose", "Scene health audit and diagnostics"),
    ("/fix", "Auto-fix detected scene issues"),
    ("/preflight", "Pre-render validation checklist"),
    ("/journal", "Session journal and history"),
    ("/explain", "Explain selected node or network"),
    ("/trace", "Trace node dependencies and data flow"),
    ("/vex", "VEX code help, explain, or generate"),
    ("/recipes", "Browse and build network recipes"),
    ("/hda", "Create HDA from selection or description"),
    ("/login", "Shot login and context setup"),
    ("/apex", "APEX rigging overview"),
    ("/apex explain", "Explain APEX graph structure"),
    ("/apex trace", "Trace APEX evaluation order"),
    ("/apex recipes", "Browse APEX rigging recipes"),
    ("/apex build", "Build an APEX rig from recipe"),
    ("/apex overview", "High-level APEX architecture"),
    ("/apex migrate", "KineFX to APEX migration guide"),
    ("/scene", "Scene summary and statistics"),
    ("/inspect", "Inspect geometry or node details"),
    ("/search", "Search nodes, parameters, or assets"),
]

_cached_entries: Optional[list[PaletteEntry]] = None


def build_palette_entries(*, force_rebuild: bool = False) -> list[PaletteEntry]:
    """Build the full list of searchable palette entries from all sources.

    Results are cached. Pass ``force_rebuild=True`` to regenerate.
    """
    global _cached_entries
    if _cached_entries is not None and not force_rebuild:
        return _cached_entries

    entries: list[PaletteEntry] = []

    # -- a) Slash commands (hardcoded) ------------------------------------
    for cmd, desc in _SLASH_COMMANDS:
        entries.append(PaletteEntry(
            label=cmd,
            command=cmd,
            category="command",
            description=desc,
        ))

    # -- b) Recipes from recipe_book.RECIPES ------------------------------
    try:
        from synapse.panel.recipe_book import RECIPES
        for category_name, category_recipes in sorted(RECIPES.items()):
            for recipe_name, recipe_data in sorted(category_recipes.items()):
                title = recipe_data.get("title", recipe_name)
                desc = recipe_data.get("description", "")
                # Truncate long descriptions
                if len(desc) > 80:
                    desc = desc[:77] + "..."
                entries.append(PaletteEntry(
                    label=f"/recipes build {category_name} {recipe_name}",
                    command=f"/recipes build {category_name} {recipe_name}",
                    category="recipe",
                    description=f"{title} -- {desc}" if desc else title,
                ))
    except (ImportError, AttributeError):
        pass

    # -- c) APEX recipes from apex_recipes.APEX_RECIPES -------------------
    try:
        from synapse.panel.apex_recipes import APEX_RECIPES
        for recipe_name, recipe_data in sorted(APEX_RECIPES.items()):
            title = recipe_data.get("title", recipe_name)
            desc = recipe_data.get("description", "")
            if len(desc) > 80:
                desc = desc[:77] + "..."
            entries.append(PaletteEntry(
                label=f"/apex build {recipe_name}",
                command=f"/apex build {recipe_name}",
                category="apex",
                description=f"{title} -- {desc}" if desc else title,
            ))
    except (ImportError, AttributeError):
        pass

    # -- d) VEX functions from vex_tutor.VEX_REFERENCE --------------------
    try:
        from synapse.panel.vex_tutor import VEX_REFERENCE
        for func_name, func_data in sorted(VEX_REFERENCE.items()):
            desc = func_data.get("description", "")
            if len(desc) > 80:
                desc = desc[:77] + "..."
            category_tag = func_data.get("category", "")
            label = f"/vex help {func_name}"
            entries.append(PaletteEntry(
                label=label,
                command=label,
                category="vex",
                description=f"[{category_tag}] {desc}" if category_tag else desc,
            ))
    except (ImportError, AttributeError):
        pass

    _cached_entries = entries
    return entries


# ===================================================================
# 3. Fuzzy matching
# ===================================================================

def fuzzy_match(query: str, text: str) -> float:
    """Simple fuzzy matching. Returns score 0.0--1.0.

    Algorithm:
    - Empty query matches everything (1.0).
    - Exact substring match (case-insensitive): 1.0.
    - All query chars appear in order in text: fraction matched.
    - All query words appear in text: 0.8.
    - Otherwise 0.0.

    Bonuses:
    - Prefix match: +0.2
    - Word boundary match: +0.1
    """
    if not query:
        return 1.0

    q = query.lower()
    t = text.lower()

    score = 0.0

    # Exact substring match
    if q in t:
        score = 1.0
    else:
        # Subsequence match: all chars of query appear in order in text
        qi = 0
        for ch in t:
            if qi < len(q) and ch == q[qi]:
                qi += 1
        if qi == len(q):
            # Score based on how tight the match is (length ratio)
            score = len(q) / len(t) if len(t) > 0 else 0.0
        else:
            # Word match: all space-separated query words appear in text
            words = q.split()
            if words and all(w in t for w in words):
                score = 0.8
            else:
                return 0.0

    # Bonus: prefix match
    if t.startswith(q):
        score = min(score + 0.2, 1.0)

    # Bonus: word boundary match (query matches start of a word)
    if re.search(rf'(?:^|[\s/\-_]){re.escape(q)}', t):
        score = min(score + 0.1, 1.0)

    return score


# ===================================================================
# 4. Search function
# ===================================================================

def search_palette(
    query: str,
    entries: Optional[list[PaletteEntry]] = None,
    limit: int = 10,
) -> list[PaletteEntry]:
    """Search palette entries with fuzzy matching.

    Returns the top *limit* results sorted by score descending.
    Entries with score 0.0 are filtered out.
    """
    if entries is None:
        entries = build_palette_entries()

    results: list[PaletteEntry] = []
    for entry in entries:
        label_score = fuzzy_match(query, entry.label)
        desc_score = fuzzy_match(query, entry.description)
        best = max(label_score, desc_score)
        if best > 0.0:
            # Create a copy with the score set
            results.append(PaletteEntry(
                label=entry.label,
                command=entry.command,
                category=entry.category,
                description=entry.description,
                score=best,
            ))

    results.sort(key=lambda e: e.score, reverse=True)
    return results[:limit]


# ===================================================================
# 5. CommandPaletteWidget
# ===================================================================

# Category badge labels
_BADGE_MAP = {
    "command": "CMD",
    "recipe": "RCP",
    "apex": "APX",
    "vex": "VEX",
    "recent": "RCT",
}

# Badge colors per category
_BADGE_COLORS = {
    "command": _SIGNAL,
    "recipe": "#00E676",
    "apex": "#FF6B35",
    "vex": "#FFAB00",
    "recent": "#888888",
}


if _QT_AVAILABLE:

    class CommandPaletteWidget(QWidget):
        """Fuzzy-search command palette overlay for the SYNAPSE panel.

        Signals
        -------
        command_selected(str)
            Emitted when the artist picks a command from the palette.
        """

        command_selected = Signal(str)

        def __init__(self, parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)

            # -- Entries --
            self._entries: list[PaletteEntry] = build_palette_entries()
            self._recent: list[PaletteEntry] = []

            # -- Window flags: frameless popup --
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setFixedWidth(520)
            self.setMaximumHeight(400)

            # -- Container (for rounded-corner background) --
            container = QFrame(self)
            container.setObjectName("PaletteContainer")
            container.setStyleSheet(self._container_style())

            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.addWidget(container)

            layout = QVBoxLayout(container)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(6)

            # -- Search field --
            self._search = QLineEdit()
            self._search.setPlaceholderText("Type to search commands...")
            self._search.setStyleSheet(self._search_style())
            font = QFont(_FONT_SANS, 12)
            self._search.setFont(font)
            layout.addWidget(self._search)

            # -- Separator line --
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"color: {_NEAR_BLACK};")
            sep.setFixedHeight(1)
            layout.addWidget(sep)

            # -- Results list --
            self._list = QListWidget()
            self._list.setStyleSheet(self._list_style())
            self._list.setFont(QFont(_FONT_SANS, 10))
            self._list.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            layout.addWidget(self._list)

            # -- Connections --
            self._search.textChanged.connect(self._on_search)
            self._list.itemActivated.connect(self._on_select)
            self._search.installEventFilter(self)

        # ----- Styles -------------------------------------------------------

        @staticmethod
        def _container_style() -> str:
            return (
                "QFrame#PaletteContainer {"
                f"  background-color: rgba(26, 26, 26, 242);"  # ~95% opacity
                "  border-radius: 8px;"
                f"  border: 1px solid {_NEAR_BLACK};"
                "}"
            )

        @staticmethod
        def _search_style() -> str:
            return (
                "QLineEdit {"
                f"  background: {_GRAPHITE};"
                f"  color: {_TEXT};"
                "  border: none;"
                "  border-radius: 4px;"
                "  padding: 8px 10px;"
                "}"
                "QLineEdit:focus {"
                f"  border: 1px solid {_SIGNAL};"
                "}"
            )

        @staticmethod
        def _list_style() -> str:
            return (
                "QListWidget {"
                "  background: transparent;"
                f"  color: {_TEXT};"
                "  border: none;"
                "  outline: none;"
                "}"
                "QListWidget::item {"
                "  padding: 5px 8px;"
                "  border-radius: 3px;"
                "}"
                "QListWidget::item:selected {"
                f"  background: {_NEAR_BLACK};"
                "}"
                "QListWidget::item:hover {"
                f"  background: {_CARBON};"
                "}"
            )

        # ----- Public API ----------------------------------------------------

        def show_palette(
            self, recent_entries: Optional[list[PaletteEntry]] = None
        ) -> None:
            """Show the palette overlay.

            Parameters
            ----------
            recent_entries:
                Optional list of recent-action entries to include.
            """
            self._recent = recent_entries or []
            self._search.clear()

            # Position centered on parent if available
            if self.parent():
                pw = self.parent().width()
                ph = self.parent().height()
                x = (pw - self.width()) // 2
                y = max(ph // 6, 20)
                self.move(x, y)

            self._populate_list(self._all_entries())
            self.show()
            self._search.setFocus()

        # ----- Internal ------------------------------------------------------

        def _all_entries(self) -> list[PaletteEntry]:
            """Return all entries including recents."""
            return self._entries + self._recent

        def _on_search(self, text: str) -> None:
            """Filter results on every keystroke."""
            if not text.strip():
                self._populate_list(self._all_entries())
                return

            results = search_palette(text, self._all_entries(), limit=15)
            self._populate_list(results)

        def _on_select(self, item: QListWidgetItem) -> None:
            """Execute the selected command."""
            command = item.data(Qt.ItemDataRole.UserRole)
            if command:
                self.command_selected.emit(command)
            self.hide()

        def _populate_list(self, entries: list[PaletteEntry]) -> None:
            """Fill the QListWidget with palette entries."""
            self._list.clear()
            for entry in entries:
                badge = _BADGE_MAP.get(entry.category, "???")
                badge_color = _BADGE_COLORS.get(entry.category, _TEXT_DIM)

                # Truncate description for display
                desc = entry.description
                if len(desc) > 55:
                    desc = desc[:52] + "..."

                display = f"{entry.label}  --  {desc}"

                item = QListWidgetItem(f"[{badge}]  {display}")
                item.setData(Qt.ItemDataRole.UserRole, entry.command)
                item.setForeground(QColor(_TEXT))
                # Tint badge portion via tooltip (simple approach)
                item.setToolTip(
                    f"<b style='color:{badge_color}'>[{badge}]</b> "
                    f"<span style='color:{_TEXT}'>{entry.label}</span><br/>"
                    f"<span style='color:{_TEXT_DIM}'>{entry.description}</span>"
                )
                self._list.addItem(item)

            # Select first item
            if self._list.count() > 0:
                self._list.setCurrentRow(0)

        # ----- Event handling ------------------------------------------------

        def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
            """Handle Escape to close, arrows to navigate."""
            if event.key() == Qt.Key.Key_Escape:
                self.hide()
                event.accept()
                return
            super().keyPressEvent(event)

        def eventFilter(self, obj, event) -> bool:  # type: ignore[override]
            """Forward Up/Down/Enter from search field to the list."""
            if obj is self._search and hasattr(event, "key"):
                key = event.key()
                if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                    # Forward arrow keys to list navigation
                    current = self._list.currentRow()
                    count = self._list.count()
                    if count == 0:
                        return False
                    if key == Qt.Key.Key_Down:
                        new_row = min(current + 1, count - 1)
                    else:
                        new_row = max(current - 1, 0)
                    self._list.setCurrentRow(new_row)
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    item = self._list.currentItem()
                    if item:
                        self._on_select(item)
                    return True
            return super().eventFilter(obj, event)

else:
    # Stub when Qt is not available (testing/CI)
    class CommandPaletteWidget:  # type: ignore[no-redef]
        """Stub CommandPaletteWidget for non-Qt environments."""

        def __init__(self, parent=None):
            self._entries = build_palette_entries()

        def show_palette(self, recent_entries=None):
            pass
