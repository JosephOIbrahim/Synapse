"""PNL-L3A: the palette's ranking is pure python, and it RANKS.

Before this leg the slash palette (``ToolPalette``) flat-filtered on substring
and kept whatever order the grouping had left rows in, while the real ranking
sat in the unwired ``CommandPaletteWidget``. So typing ``/re`` put the row the
artist meant wherever the alphabet happened to put it.

These tests are stock pytest on purpose: the ranking must be reachable and
provable with no Qt, no panel and no Houdini.
"""
import pytest

from synapse.panel.command_palette import (
    PANEL_ANSWERED_COMMANDS,
    fuzzy_match,
    rank_row,
    rank_rows,
)


def _row(title, desc, send):
    return {"title": title, "desc": desc, "send": send}


# The row the artist means when they type "/re": the panel answers /render
# itself (it opens the render workspace), so its title is a sentence and the
# command only shows up in what the pick sends.
RENDER_ROW = _row(
    "Open the render workspace",
    "Prepare a saved scene, render with TOPs and revisit recent jobs",
    "/render",
)

# A recipes row, listed FIRST so "it came out first" can never be an accident
# of input order. Its send is the generated recipe prompt (that is what
# tool_palette._load_entries builds for a non-command category), so nothing on
# it matches "/re" at all.
RECIPES_ROW = _row(
    "Recipe: three point lighting",
    "Three point lighting rig -- key, fill and rim",
    "Build this network recipe — three point lighting",
)

# An APEX row that matches "/re" only as a SUBSEQUENCE ('/' ... 'r' ... 'e'),
# so it scores well below 1.0. The old substring filter dropped it entirely;
# ranking keeps it, below the row that actually matches.
APEX_ROW = _row("/apex recipes", "Browse APEX rigging recipes", "/apex recipes")


def test_rank_row_is_pure_and_scores_the_best_of_three_fields():
    """No Qt, no state: a row's score is the best of title / desc / send."""
    assert rank_row("/re", **RENDER_ROW) == fuzzy_match("/re", "/render")
    assert rank_row("/re", **RENDER_ROW) == pytest.approx(1.0)
    # Nothing on the recipes row carries a "/" at all.
    assert rank_row("/re", **RECIPES_ROW) == 0.0
    # Calling it twice gives the same answer; it holds nothing.
    assert rank_row("/re", **RENDER_ROW) == rank_row("/re", **RENDER_ROW)


def test_render_row_ranks_first_for_slash_re_against_a_recipes_row():
    """The leg's named case: '/re' finds the render workspace, not the recipe.

    The recipes row is handed in first. Ranking has to move the render row
    above it, and the recipes row must fall out (it does not match).
    """
    ranked = rank_rows("/re", [RECIPES_ROW, RENDER_ROW])
    assert ranked, "ranking dropped every row"
    assert ranked[0] is RENDER_ROW, [r["title"] for r in ranked]
    assert RECIPES_ROW not in ranked


def test_a_weaker_match_survives_but_ranks_below():
    """Ranking is not the old substring filter.

    The APEX row matches "/re" only as a subsequence — the substring filter
    this replaced would have thrown it away. It is kept, and it is second.
    """
    assert 0.0 < rank_row("/re", **APEX_ROW) < 1.0
    ranked = rank_rows("/re", [APEX_ROW, RECIPES_ROW, RENDER_ROW])
    assert [r["title"] for r in ranked] == [
        "Open the render workspace", "/apex recipes"]


def test_ties_keep_the_order_they_arrived_in():
    """Ties keep today's order — ranking only lifts a better match."""
    a = _row("/render", "", "/render")
    b = _row("/rename", "", "/render")
    assert rank_row("/re", **a) == rank_row("/re", **b)
    assert rank_rows("/re", [a, b]) == [a, b]
    assert rank_rows("/re", [b, a]) == [b, a]


def test_empty_query_returns_every_row_untouched():
    rows = [RECIPES_ROW, RENDER_ROW, APEX_ROW]
    assert rank_rows("", rows) == rows
    assert rank_rows("", rows) is not rows      # a copy, never the caller's list


def test_the_five_panel_answered_commands_are_marked_at_the_one_build_path():
    """One registry: the literals the panel intercepts are declared once."""
    from synapse.panel.command_palette import build_palette_entries

    assert PANEL_ANSWERED_COMMANDS == frozenset({
        "/render", "/events", "/saved-recipes", "/lookdev-suggestion",
        "/restore-session"})
    marked = {e.command for e in build_palette_entries(force_rebuild=True)
              if getattr(e, "panel_answered", False)}
    # AMENDED BY DECLARATION (PNL-L3B). L3a asserted
    # ``PANEL_ANSWERED_COMMANDS - {"/restore-session"}`` because
    # /restore-session had never been listed in _SLASH_COMMANDS, although the
    # panel has intercepted it since W7-SESSCOPE. L3b added the row, so all
    # five panel-answered commands are now built and marked.
    assert marked == PANEL_ANSWERED_COMMANDS
    assert "/render" in marked


# ===================================================================
# PNL-L3B: the wiring, and the row decisions
# ===================================================================

def _refilter_of():
    """``ToolPalette._refilter`` + ``._visible``, lifted by AST and exec'd in
    a bare namespace -- the same trick tests/test_panel_finesse.py uses, so
    the wiring is provable with no Qt, no panel and no Houdini."""
    import ast
    from pathlib import Path

    source = (Path(__file__).parents[1]
              / "python/synapse/panel/tool_palette.py").read_text(encoding="utf-8")
    wanted = [n for n in ast.walk(ast.parse(source))
              if isinstance(n, ast.FunctionDef) and n.name in {"_refilter", "_visible"}]
    assert {n.name for n in wanted} == {"_refilter", "_visible"}
    ns = {}
    exec(compile(ast.Module(body=wanted, type_ignores=[]), "tool_palette.py", "exec"), ns)
    return ns


def test_refilter_ranks_through_the_shared_scorer():
    """L3a left the ranking pure and tested but its WIRING unpinned -- the nit
    L3b closes. A typed query must reach command_palette.rank_rows, and the
    result must arrive at _populate ungrouped and best-first."""
    from types import SimpleNamespace

    ns = _refilter_of()
    rows = [dict(RECIPES_ROW), dict(RENDER_ROW), dict(APEX_ROW)]
    seen = {}
    palette = SimpleNamespace(
        _rows=rows, _verb=None, _context=None,
        _populate=lambda r, grouped=True: seen.update(rows=r, grouped=grouped),
    )
    palette._visible = lambda: ns["_visible"](palette)

    ns["_refilter"](palette, "/re")
    assert seen["grouped"] is False, "a ranked list must not draw browse heads"
    assert seen["rows"] == rank_rows("/re", rows)
    assert seen["rows"][0]["title"] == "Open the render workspace"

    ns["_refilter"](palette, "   ")
    assert seen["grouped"] is True, "an empty query is browsing, heads and all"
    assert seen["rows"] == rows


def test_exactly_five_palette_sends_are_still_literals():
    """PNL-L3B (2): every other listed command became a prompt or was
    dropped, and each decision is declared in ONE of the three tables."""
    from synapse.panel.command_palette import (
        COMMAND_PROMPTS, DROPPED_COMMANDS, PANEL_ROW_ORDER, PANEL_ROW_TITLES,
        _SLASH_COMMANDS, build_palette_entries,
    )

    listed = [cmd for cmd, _desc in _SLASH_COMMANDS]
    assert len(listed) == len(set(listed)), "a command is listed twice"
    undecided = [c for c in listed if c not in PANEL_ANSWERED_COMMANDS
                 and c not in COMMAND_PROMPTS and c not in DROPPED_COMMANDS]
    assert not undecided, undecided
    assert frozenset(PANEL_ROW_ORDER) == PANEL_ANSWERED_COMMANDS
    assert set(PANEL_ROW_TITLES) == PANEL_ANSWERED_COMMANDS

    entries = build_palette_entries(force_rebuild=True)
    # A "command" entry's ``command`` IS the row's send (tool_palette only
    # rewrites the other categories, which it sends through a pinned prefix
    # -- "Build this network recipe -- ...", never a literal). So these five
    # are every literal send in the palette; the offscreen probe re-counts
    # them on the real rows.
    literals = sorted(e.command for e in entries
                      if e.category == "command" and e.command.startswith("/"))
    assert literals == sorted(PANEL_ANSWERED_COMMANDS), literals
    assert not [e for e in entries
                if e.category == "command" and not e.command.startswith("/")
                and e.command.split()[0].startswith("/")]
    # A panel row reads as its outcome, never as its literal.
    for e in entries:
        if e.panel_answered:
            assert e.label == PANEL_ROW_TITLES[e.command]
            assert not e.label.startswith("/")
    # A prompt row is a sentence, not a command word.
    for cmd, (title, prompt) in COMMAND_PROMPTS.items():
        assert not prompt.startswith("/"), cmd
        assert not title.startswith("/"), cmd
        assert len(prompt.split()) >= 4, cmd
