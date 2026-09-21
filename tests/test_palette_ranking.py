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
    # /restore-session is not in the slash list today (L3b decides row by row);
    # every command that IS listed and panel-answered must carry the mark.
    assert marked == PANEL_ANSWERED_COMMANDS - {"/restore-session"}
    assert "/render" in marked
