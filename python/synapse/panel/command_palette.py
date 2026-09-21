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
import html as _html
from typing import List, Optional

# ---------------------------------------------------------------------------
# Qt import guard (PySide6 first, PySide2 fallback)
# ---------------------------------------------------------------------------

try:
    from PySide6.QtWidgets import (  # type: ignore[import-untyped]
        QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QFrame,
    )
    from PySide6.QtCore import Qt, Signal  # type: ignore[import-untyped]
    from PySide6.QtGui import QColor, QKeyEvent  # type: ignore[import-untyped]
    _QT_AVAILABLE = True
except ImportError:
    try:
        from PySide2.QtWidgets import (  # type: ignore[import-untyped]
            QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
            QLabel, QHBoxLayout, QFrame,
        )
        from PySide2.QtCore import Qt, Signal  # type: ignore[import-untyped]
        from PySide2.QtGui import QColor, QKeyEvent  # type: ignore[import-untyped]
        _QT_AVAILABLE = True
    except ImportError:
        _QT_AVAILABLE = False

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

# Palette and text roles from the single vendored design system.
# The former `except ImportError` arm carried a private palette (SIGNAL and
# five neutrals that matched neither authority) and was REACHABLE by a by-path
# load -- a live third authority, removed rather than corrected.
from synapse.panel.designsystem import tokens as _ds
from synapse.panel.designsystem import qss

_SIGNAL = _ds.SIGNAL
_TEXT = _ds.TEXT_PRIMARY
_TEXT_DIM = _ds.TEXT_SECONDARY


# ===================================================================
# 1. PaletteEntry dataclass
# ===================================================================

try:
    from synapse.panel.tool_filter import classify_tool
except Exception:  # pragma: no cover
    classify_tool = None


@dataclass
class PaletteEntry:
    """Single searchable entry in the command palette."""

    label: str          # display text
    command: str         # the command to execute (e.g. "/diagnose")
    category: str        # "command", "recipe", "apex", "vex", "recent"
    description: str     # brief description
    score: float = 0.0   # fuzzy match score (higher = better match)
    verb: str = "build"          # two-axis (Mile 6): what the artist wants done
    context: Optional[str] = None  # two-axis (Mile 6): where they are
    # PNL-L3A: True when the PANEL answers this pick locally (no model turn).
    panel_answered: bool = False


# ===================================================================
# 2. Palette entry builder
# ===================================================================

# PNL-L3A (spec leg L3a, ruling R2-misc — "one registry, one name"):
# these five commands are answered by the PANEL ITSELF. A pick never reaches
# the model: synapse_panel._send intercepts the literal and opens a local view
# (pinned by tests/test_panel_finesse.py and tests/test_first_session_panel.py,
# and the '/render' send by tests/native_render_workspace.py +
# tests/test_farm_integration.py). They are marked HERE, at the one place rows
# are built, so tool_palette._load_entries — the single row source — carries
# the fact forward instead of the palette merging this list blindly.
PANEL_ANSWERED_COMMANDS: frozenset[str] = frozenset({
    "/render",
    "/events",
    "/saved-recipes",
    "/lookdev-suggestion",
    "/restore-session",
})

# Hardcoded slash commands with descriptions. NOT a second registry: this is
# DATA, and build_palette_entries below is the only path that turns it into
# rows. PNL-L3B decided every one of them; the three tables underneath carry
# the decisions.
#
# PNL-L3B correction to its own brief: the brief says "the 20 rows that have
# no panel handler". The list held 25 rows of which only FOUR were
# panel-answered -- "/restore-session" had never been listed at all, though
# the panel has intercepted it since W7-SESSCOPE. It is added here, which is
# what makes the panel group five rows, and leaves 21 rows to decide.
_SLASH_COMMANDS: list[tuple[str, str]] = [
    ("/help", "Show help and available commands"),
    ("/diagnose", "Scene health audit and diagnostics"),
    ("/fix", "Auto-fix detected scene issues"),
    ("/preflight", "Pre-render validation checklist"),
    ("/render", "Prepare a saved scene, render with TOPs and revisit recent jobs"),
    ("/journal", "Session journal and history"),
    ("/explain", "Explain selected node or network"),
    ("/trace", "Trace node dependencies and data flow"),
    ("/vex", "VEX code help, explain, or generate"),
    ("/recipes", "Browse and build network recipes"),
    ("/saved-recipes", "Save, tag and reuse local Solaris networks"),
    ("/lookdev-suggestion", "Ask for a saved lookdev setup and prepare an editable prompt"),
    ("/events", "See local work updates and watch selected render or cache outputs"),
    ("/restore-session", "Bring back the conversation parked by the last fresh boot"),
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

# PNL-L3B (1): the five panel rows are TITLED BY OUTCOME and read in this
# order at the top of the list. The send stays the literal the panel
# intercepts -- unchanged, and after this leg the only sends in the whole
# palette that begin with "/".
PANEL_ROW_ORDER: tuple[str, ...] = (
    "/render",
    "/events",
    "/saved-recipes",
    "/lookdev-suggestion",
    "/restore-session",
)
PANEL_ROW_TITLES: dict[str, str] = {
    "/render": "Open the render workspace",
    "/events": "Show updates",
    "/saved-recipes": "Saved networks",
    "/lookdev-suggestion": "Saved lookdev suggestion",
    "/restore-session": "Restore last session",
}

# PNL-L3B (2a): the rows that survive as a REAL PROMPT --
# ``command -> (row title, the sentence the pick sends)``. Every prompt is
# actionable with nothing selected: each names its own empty-scene or
# empty-selection fallback, the same rule the ASK rows follow.
COMMAND_PROMPTS: dict[str, tuple[str, str]] = {
    "/diagnose": (
        "Check the scene for problems",
        "Audit the current scene for problems -- node errors and warnings, "
        "broken file paths, missing inputs -- and report what you find, "
        "worst first.",
    ),
    "/preflight": (
        "Pre-render check",
        "Run a pre-render check on the current scene: camera, render "
        "settings, output paths, lights and materials. List anything that "
        "would break or spoil the render.",
    ),
    "/journal": (
        "Recap this session",
        "Recap what we have done in this session so far, and what is still "
        "open.",
    ),
    "/trace": (
        "Trace what feeds this node",
        "Trace the dependencies and data flow into the selected node, or "
        "into the display node of the current network if nothing is "
        "selected.",
    ),
    "/hda": (
        "Make a digital asset",
        "Build a digital asset from the selected nodes, promoting the "
        "parameters that matter. If nothing is selected, ask me what the "
        "asset should do before you build anything.",
    ),
    "/apex explain": (
        "Explain this APEX graph",
        "Explain the structure of the selected APEX graph, or of the rig in "
        "the scene if nothing is selected.",
    ),
    "/apex trace": (
        "Trace APEX evaluation order",
        "Trace the evaluation order of the selected APEX graph, or of the "
        "rig in the scene if nothing is selected.",
    ),
    "/apex overview": (
        "How APEX rigging works",
        "Give me a high-level overview of how APEX rigging fits together in "
        "Houdini 22, and where it replaces KineFX.",
    ),
    "/apex migrate": (
        "Move a KineFX rig to APEX",
        "Walk me through migrating a KineFX rig to APEX, step by step, using "
        "the rig in this scene if there is one.",
    ),
    "/scene": (
        "Summarize the scene",
        "Summarize the current scene: contexts, object and node counts, "
        "cameras, renderers, and anything unusual.",
    ),
    "/inspect": (
        "Inspect the selected node",
        "Inspect the selected node -- its geometry, attributes and the "
        "parameters that are off their defaults. If nothing is selected, "
        "inspect the display node of the current network.",
    ),
}

# PNL-L3B (2b): DROPPED. A row is dropped when its send could only ever have
# been the bare literal: no panel handler behind it, and no sentence a model
# can act on that some other row does not already carry better. The reasons
# are the rows' own, not one reason repeated.
DROPPED_COMMANDS: dict[str, str] = {
    "/help": "the palette IS the help surface; '/help' reached a model that "
             "cannot enumerate the panel's own affordances",
    "/fix": "duplicate of the ASK row 'Fix', which carries the real prompt",
    "/explain": "duplicate of the ASK row 'Explain', which carries the real "
                "prompt",
    "/vex": "bare verb with no object; the '/vex help <function>' rows are "
            "the reachable form and they stay",
    "/recipes": "the RECIPES group is the browse surface; the bare row "
                "opened nothing",
    "/login": "shot login / context setup was never implemented anywhere -- "
              "a dead row, not a prompt",
    "/apex": "bare overview, superseded by the 'How APEX rigging works' row",
    "/apex recipes": "the APEX rig rows in RECIPES are the browse surface",
    "/apex build": "the per-recipe '/apex build <name>' rows are the real "
                   "thing",
    "/search": "searching is what the palette's own search field does",
}

_cached_entries: Optional[list[PaletteEntry]] = None


def _trigger_to_phrase(triggers, fallback: str) -> str:
    """Turn a recipe's trigger REGEX into the sentence an artist would type.

    S3-F3. Registry recipes fire on a regex matched against free text, so the
    capability was reachable and undiscoverable — nothing told you the words.
    This recovers them:

        ^scatter\\s+(?P<source>[\\w\\-./]+)\\s+(?:on(?:to)?|over)\\s+(?P<target>...)
        -> "scatter <source> onto <target>"

    Named groups become <placeholders> so the phrase reads as a template. If a
    trigger cannot be reduced to something readable, the recipe NAME is used
    rather than a mangled regex — an unreadable entry is worse than a plain one.
    """
    import re as _re

    pat = None
    if isinstance(triggers, (list, tuple)) and triggers:
        pat = str(triggers[0])
    elif isinstance(triggers, str):
        pat = triggers
    if not pat:
        return fallback.replace("_", " ")

    s = pat.lstrip("^").rstrip("$")
    s = _re.sub(r"\(\?P<(\w+)>[^)]*\)", r"<\1>", s)     # named group -> <name>

    # Reduce non-capturing groups INNERMOST-FIRST, taking the first alternative.
    # (?:on(?:to)?|over) must become "onto", not "on:toover" - which is what a
    # single outer pass produces, and what shipped in the first attempt at this.
    for _ in range(6):
        new = _re.sub(r"\(\?:([^()|]*)(?:\|[^()]*)?\)\??", r"\1", s)
        if new == s:
            break
        s = new

    s = s.replace("\\s+", " ").replace("\\s*", " ").replace("\\b", "")
    s = s.replace("\\.", ".").replace("\\-", "-").replace("\\/", "/")
    s = _re.sub(r"[\\\[\]{}+*?()|^$]", "", s)
    s = _re.sub(r"\s{2,}", " ", s).strip()

    # A phrase that still carries regex debris is not a phrase. A leftover ':'
    # is the tell - it is what a half-reduced (?: leaves behind.
    if not s or len(s) > 60 or ":" in s or any(c in s for c in "\\[]{}|"):
        return fallback.replace("_", " ")
    return s


def build_palette_entries(*, force_rebuild: bool = False) -> list[PaletteEntry]:
    """Build the full list of searchable palette entries from all sources.

    Results are cached. Pass ``force_rebuild=True`` to regenerate.
    """
    global _cached_entries
    if _cached_entries is not None and not force_rebuild:
        return _cached_entries

    entries: list[PaletteEntry] = []

    # -- a) Slash commands (hardcoded) ------------------------------------
    # PNL-L3B: a listed command is exactly one of three things -- a PANEL row
    # (outcome title, literal send), a PROMPT row (outcome title, sentence
    # send), or DROPPED. A command that somehow matches none of the three is
    # dropped rather than shipped as a bare literal, so "exactly five sends
    # begin with '/'" cannot rot the next time a row is added to the data.
    for cmd, desc in _SLASH_COMMANDS:
        if cmd in DROPPED_COMMANDS:
            continue
        if cmd in PANEL_ANSWERED_COMMANDS:
            entries.append(PaletteEntry(
                label=PANEL_ROW_TITLES.get(cmd, cmd),
                command=cmd,
                category="command",
                description=desc,
                panel_answered=True,
            ))
            continue
        decided = COMMAND_PROMPTS.get(cmd)
        if decided is None:
            continue
        title, prompt = decided
        entries.append(PaletteEntry(
            label=title,
            command=prompt,
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

    # -- b2) Registry recipes from routing.recipes.RecipeRegistry ---------
    # S3-F3: the palette showed 21 recipes from recipe_book while the registry
    # holds 62. The other 41 were not unreachable - they fire on a TRIGGER
    # REGEX matched against what the artist types. So the capability existed and
    # nothing anywhere told you the words. Function without affordance.
    #
    # These entries surface the phrasing. The command is a readable template
    # derived from the trigger, with named groups shown as <placeholders>, so
    # the palette teaches the sentence rather than hiding it.
    try:
        from synapse.routing.recipes import RecipeRegistry
        for rec in RecipeRegistry()._recipes:
            phrase = _trigger_to_phrase(getattr(rec, "triggers", None),
                                        getattr(rec, "name", "?"))
            desc = (getattr(rec, "description", "") or "")
            if len(desc) > 80:
                desc = desc[:77] + "..."
            cat = getattr(rec, "category", "") or ""
            entries.append(PaletteEntry(
                label=phrase,
                command=phrase,
                category="recipe",
                description=f"{cat} -- {desc}" if cat and desc else (desc or cat),
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

    # Tag every entry on the two axes (verb × context) for ⌘K navigation.
    if classify_tool is not None:
        for e in entries:
            try:
                e.verb, e.context = classify_tool(e.command, e.label, e.description)
            except Exception:
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
# 3b. Row ranking (pure) — PNL-L3A
# ===================================================================

# The fields a palette row is ranked over, in the order the spec names them.
RANK_FIELDS: tuple[str, ...] = ("title", "desc", "send")


def rank_row(query: str, title: str = "", desc: str = "", send: str = "") -> float:
    """Score ONE palette row against *query*. Pure python, no Qt, no state.

    PNL-L3A (spec leg L3a): the ranking used to live inside
    ``CommandPaletteWidget`` while the slash palette that artists actually open
    did a flat substring filter, so 'the good row' was wherever the sort had
    left it. Same scoring rules as :func:`fuzzy_match` (substring 1.0 /
    subsequence length-ratio / all-words 0.8, +0.2 prefix, +0.1 word
    boundary); a row scores the BEST of its three fields, and 0.0 means the row
    does not match at all.
    """
    return max(fuzzy_match(query, title or ""),
               fuzzy_match(query, desc or ""),
               fuzzy_match(query, send or ""))


def rank_rows(query: str, rows):
    """Rank ``rows`` (dicts with title/desc/send) best-first, dropping 0.0.

    Ties keep the order they arrived in — the palette's own grouping
    (context, verb, title) stays the tiebreak, so ranking only ever lifts a
    better match above a worse one. An empty query returns ``rows`` untouched.
    """
    rows = list(rows)
    if not query:
        return rows
    scored = []
    for index, row in enumerate(rows):
        score = rank_row(query, row.get("title", ""), row.get("desc", ""),
                         row.get("send", ""))
        if score > 0.0:
            scored.append((score, index, row))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [row for _score, _index, row in scored]


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

# Group heads for the unsearched list (bc-wave BC-3), keyed like _BADGE_MAP.
_CATEGORY_HEADS = {
    "command": "Commands",
    "recipe": "Recipes",
    "apex": "APEX Rigging",
    "vex": "VEX",
    "recent": "Recent",
}

# Badge colors per category
_BADGE_COLORS = {
    "command": _SIGNAL,
    "recipe": _ds.TEXT_SECONDARY,
    "apex": _ds.TEXT_SECONDARY,
    "vex": _ds.TEXT_SECONDARY,
    "recent": _ds.TEXT_TERTIARY,
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
            self.setObjectName("DsRoot")
            self.setProperty("rhythm_role", "group")
            self.setProperty("panel_popup", "command")
            self._scale = getattr(parent, "_font_scale", _ds.FONT_SCALE_DEFAULT)
            self.resize(_ds.PANEL_PREF_WIDTH, _ds.PANEL_MIN_HEIGHT - _ds.SPACE_LG)
            self.setMaximumHeight(400)

            # -- Container (for rounded-corner background) --
            container = QFrame(self)
            container.setObjectName("PaletteContainer")
            container.setProperty("rhythm_role", "stack")

            outer = QVBoxLayout(self)
            outer.addWidget(container)

            layout = QVBoxLayout(container)

            # -- Search field --
            self._search = QLineEdit()
            self._search.setPlaceholderText("Type to search commands...")
            self._search.setObjectName("DsCommandSearch")
            layout.addWidget(self._search)

            # -- Separator line --
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setObjectName("DsCommandDivider")
            sep.setFixedHeight(1)
            layout.addWidget(sep)

            # -- Results list --
            self._list = QListWidget()
            self._list.setObjectName("DsCommandResults")
            # bc-wave BC-3: same list rhythm as the slash palette - a `stack`
            # consumer (view spacing 4/6/3 from rhythm.apply) under the shared
            # ::item row rule (SPACE_XL boxes).
            self._list.setProperty("rhythm_role", "stack")
            self._list.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            # bc-wave repair: rows elide right instead of running off the
            # edge (the hidden scrollbar used to clip them mid-word).
            from synapse.panel.tool_palette import fit_rows
            fit_rows(self._list)
            layout.addWidget(self._list)

            # -- Connections --
            self._search.textChanged.connect(self._on_search)
            self._list.itemActivated.connect(self._on_select)
            self._search.installEventFilter(self)

            qss.prepare_sweep_b_popup(self, self._scale)

        def showEvent(self, event):
            qss.prepare_sweep_b_popup(self, self._scale)
            super().showEvent(event)

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
            """Fill the QListWidget with palette entries.

            bc-wave BC-3: the full (unsearched) list reads in category
            groups under SPACE_48 eyebrow heads - the same head treatment as
            the slash palette - in _BADGE_MAP order; a ranked search result
            keeps its rank order and carries no heads."""
            self._list.clear()
            grouped = not self._search.text().strip()
            if grouped:
                order = {cat: i for i, cat in enumerate(_BADGE_MAP)}
                entries = sorted(entries, key=lambda e: order.get(e.category, len(order)))
            from synapse.panel.tool_palette import group_head_item
            last_category = None
            for entry in entries:
                if grouped and entry.category != last_category:
                    self._list.addItem(group_head_item(
                        _CATEGORY_HEADS.get(entry.category, entry.category), self._scale))
                    last_category = entry.category
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
                # Tint badge portion via tooltip (simple approach). The label
                # and description are escaped (bc-wave repair): a title such
                # as 'solaris sets-dressing at <parent>' used to lose its
                # '<parent>' to the HTML parser, and the tooltip is where a
                # row that elides must read whole.
                item.setToolTip(
                    f"<b style='color:{badge_color}'>[{badge}]</b> "
                    f"<span style='color:{_TEXT}'>{_html.escape(entry.label)}</span><br/>"
                    f"<span style='color:{_TEXT_DIM}'>{_html.escape(entry.description)}</span>"
                )
                self._list.addItem(item)

            # Select the first OPTION (heads are not rows)
            if self._list.count() > 0:
                self._list.setCurrentRow(self._step_row(-1, +1))

        def _step_row(self, start, delta):
            """The next selectable row from ``start`` in ``delta`` direction;
            group heads (NoItemFlags) are skipped. Returns ``start`` when
            nothing selectable lies that way."""
            n = self._list.count()
            row = start
            for _ in range(n):
                row += delta
                if row < 0 or row >= n:
                    return start
                if self._list.item(row).flags() & Qt.ItemFlag.ItemIsSelectable:
                    return row
            return start

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
                    # BC-3: step over group heads, never onto them.
                    new_row = self._step_row(current, +1 if key == Qt.Key.Key_Down else -1)
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
