"""library: node type -> summary by EXACT help path only, never a search."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

import pytest

from synapse.identify import library as LIB
from synapse.cognitive.tools import sidefx_library as SL


@pytest.fixture(autouse=True)
def _fresh_summary_memo():
    """Every test starts and ends with an empty summary memo (CRUX2 N1)."""
    LIB._SUMMARY_CACHE.clear()
    yield
    LIB._SUMMARY_CACHE.clear()


# ── temp corpus (real DB, real help_summary) ─────────────────────────────────

def _build_corpus(tmp_path, rows):
    """rows: list of (id, source_url, title, body). Returns the corpus root."""
    root = tmp_path / "corpus"
    (root / "indexes").mkdir(parents=True)
    (root / "current.json").write_text(json.dumps({
        "schema": "sidefx_library_pointer/v1",
        "generation": "gen1",
        "database": "indexes/gen1.sqlite3",
        "coverage": {"docs": 1},
    }), encoding="utf-8")
    db = root / "indexes" / "gen1.sqlite3"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, source_url TEXT, "
                "title TEXT, body TEXT, metadata TEXT, domain TEXT)")
    for cid, url, title, body in rows:
        con.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?)",
                    (cid, url, title, body, "{}", "docs"))
    con.commit()
    con.close()
    return root


_DOCS = "https://www.sidefx.com/docs/houdini"
# Real corpus naming (verified live 2026-09-28): node pages are .md; the
# versioned-doc base page is ``<name>-`` (trailing dash), versions are
# ``<name>-<ver>``; example pages live under examples/ and must be excluded.
_POLYBEVEL = f"{_DOCS}/nodes/sop/polybevel-.md"
_POLYBEVEL_V = f"{_DOCS}/nodes/sop/polybevel-2.0.md"
_POLYBEVEL_EXAMPLE = f"{_DOCS}/examples/nodes/sop/polybevel/PolybevelBox.md"
# Corpus node pages read "Title\n\nSummary sentence.\n\n..." — the leading title
# paragraph must be dropped by the summary extractor.
_BODY = "PolyBevel\n\nBevels or chamfers the edges of polygons.\n\nIn the simplest case ..."


# ── derive_help_keys ─────────────────────────────────────────────────────────

def test_derive_keys_versioned_most_specific_first():
    """The versioned page, then the unversioned page, then the manager page."""
    assert LIB.derive_help_keys("operator:Sop/polybevel?version=3.0") == [
        "nodes/sop/polybevel-3.0", "nodes/sop/polybevel", "nodes/manager/polybevel"]


def test_derive_keys_base_only():
    """A plain type tries its own page, then ``nodes/manager/<name>`` (BP12 item 3).

    The manager fallback mirrors ``houdinihelp.api.components_to_path`` with
    ``maybe_manager=True`` in Houdini 22: a network manager placed in another
    context (a ``sopnet`` inside a COP network, a ``ropnet`` inside SOPs) has
    no page of its own there, so Houdini's help opens the manager page. On the
    seat's Houdini 22.0.400, 73 node types reach their page only this way.
    """
    assert LIB.derive_help_keys("operator:Sop/box") == ["nodes/sop/box", "nodes/manager/box"]


def test_derive_keys_non_operator_is_empty():
    assert LIB.derive_help_keys("https://example.com/foo") == []
    assert LIB.derive_help_keys("") == []


def test_first_sentence():
    assert LIB.first_sentence("Bevels edges. And more.") == "Bevels edges."
    assert LIB.first_sentence("  no period here ") == "no period here"


# ── summarize orchestration (injected lookup) ────────────────────────────────

def test_summarize_library_hit_strips_title_and_takes_first_sentence():
    lookup = lambda keys: (_BODY, _POLYBEVEL)
    text, source = LIB.summarize("operator:Sop/polybevel?version=3.0", lookup=lookup)
    assert (text, source) == ("Bevels or chamfers the edges of polygons.", "library")


def test_summary_paragraph_drops_leading_title():
    assert LIB.summary_paragraph(_BODY) == "Bevels or chamfers the edges of polygons."
    # No title paragraph -> whole first paragraph kept.
    assert LIB.summary_paragraph("Just a summary. More.") == "Just a summary. More."


def test_summarize_unknown_when_no_row_and_no_hda():
    text, source = LIB.summarize("operator:Sop/mystery", lookup=lambda keys: None)
    assert (text, source) == (None, "unknown")


def test_summarize_hda_embedded_help_fallback():
    text, source = LIB.summarize("operator:Sop/my_hda", hda_help="Does a thing. More.",
                                 lookup=lambda keys: None)
    assert (text, source) == ("Does a thing.", "hda")


def test_summarize_swallows_lookup_error_to_unknown():
    def boom(keys):
        raise RuntimeError("db exploded")
    assert LIB.summarize("operator:Sop/box", lookup=boom) == (None, "unknown")


# ── help_summary against a real DB ───────────────────────────────────────────

def test_help_summary_exact_hit_on_trailing_dash_base(tmp_path, monkeypatch):
    # The base page URL carries a trailing dash; the canonical key does not.
    root = _build_corpus(tmp_path, [(1, _POLYBEVEL, "PolyBevel", _BODY)])
    monkeypatch.setenv(SL.ROOT_ENV, str(root))
    hit = SL.help_summary(["nodes/sop/polybevel"])
    assert hit is not None
    assert "Bevels or chamfers" in hit[0]
    assert hit[1] == _POLYBEVEL


def test_help_summary_excludes_example_pages(tmp_path, monkeypatch):
    # Only an example page exists; there is no node help page -> unknown.
    root = _build_corpus(tmp_path, [(1, _POLYBEVEL_EXAMPLE, "PolybevelBox", "A demo.")])
    monkeypatch.setenv(SL.ROOT_ENV, str(root))
    assert SL.help_summary(["nodes/sop/polybevel"]) is None


def test_help_summary_prefers_versioned_page(tmp_path, monkeypatch):
    root = _build_corpus(tmp_path, [
        (1, _POLYBEVEL, "PolyBevel", "PolyBevel\n\nBase page summary."),
        (2, _POLYBEVEL_V, "PolyBevel 2.0", "PolyBevel\n\nVersioned page summary."),
    ])
    monkeypatch.setenv(SL.ROOT_ENV, str(root))
    hit = SL.help_summary(["nodes/sop/polybevel-2.0", "nodes/sop/polybevel"])
    assert "Versioned page summary." in hit[0]
    assert hit[1] == _POLYBEVEL_V


def test_summarize_end_to_end_against_corpus(tmp_path, monkeypatch):
    root = _build_corpus(tmp_path, [(1, _POLYBEVEL, "PolyBevel", _BODY)])
    monkeypatch.setenv(SL.ROOT_ENV, str(root))
    text, source = LIB.summarize("operator:Sop/polybevel?version=3.0")
    assert (text, source) == ("Bevels or chamfers the edges of polygons.", "library")


def test_help_summary_unavailable_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setenv(SL.ROOT_ENV, str(tmp_path / "does_not_exist"))
    assert SL.help_summary(["nodes/sop/polybevel"]) is None


# ── the mutation: exact vs search (acceptance 4) ─────────────────────────────

def test_exact_returns_unknown_where_search_would_phantom(tmp_path, monkeypatch):
    """A type with no exact page is 'unknown'; a search would hand back a phantom.

    The corpus has only the polybevel page. The exact lookup for a *different*
    type keyed ``nodes/sop/polybevel_old`` correctly returns None (unknown). A
    search-style substring match would instead return the polybevel page — the
    wrong node's summary. Swapping help_summary's keyed exact match for that
    search is exactly what makes this test fail, so it pins rule 6.
    """
    root = _build_corpus(tmp_path, [
        (1, _POLYBEVEL, "PolyBevel", "Bevels or chamfers the edges of polygons."),
    ])
    monkeypatch.setenv(SL.ROOT_ENV, str(root))

    # Exact: no page for polybevel_old -> honest unknown.
    assert SL.help_summary(["nodes/sop/polybevel_old"]) is None

    # Search mutant: a substring match on the stem returns the polybevel page.
    db = root / "indexes" / "gen1.sqlite3"
    con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
    phantom = con.execute(
        "SELECT source_url, body FROM chunks WHERE source_url LIKE ? LIMIT 1",
        ("%polybevel%",)).fetchone()
    con.close()
    assert phantom is not None            # a search WOULD return a row ...
    assert phantom[0] == _POLYBEVEL       # ... the wrong node's page (phantom)
    # Therefore the exact 'unknown' above is the guarantee; a search breaks it.


# ── BP11-IDFIX T2: BOM + '#key: value' header lines are skipped ───────────────

_BOM = "﻿"
_HELP_WITH_HEADER = (_BOM + "#type: node\n#context: sop\n\n"
                     "Extrudes polygons into 3D. More text follows.")


def test_summary_paragraph_strips_bom_and_header_directives():
    assert LIB.summary_paragraph(_HELP_WITH_HEADER) == (
        "Extrudes polygons into 3D. More text follows.")


def test_summarize_bom_header_yields_first_prose_sentence():
    # G2 showed '﻿#type: node' as the summary; the prose sentence must win.
    text, source = LIB.summarize("operator:Sop/polyextrude",
                                 lookup=lambda keys: (_HELP_WITH_HEADER, "u"))
    assert (text, source) == ("Extrudes polygons into 3D.", "library")


def test_summarize_header_only_is_honest_unknown():
    # A page that is only a BOM and directives has no prose -> honest unknown,
    # never a '#type: node' bubble.
    header_only = _BOM + "#type: node\n#context: sop\n#icon: SOP/polyextrude"
    text, source = LIB.summarize("operator:Sop/polyextrude",
                                 lookup=lambda keys: (header_only, "u"))
    assert (text, source) == (None, "unknown")


def test_first_prose_line_wins_even_without_blank_line():
    # No blank line between the last directive and the prose line.
    body = _BOM + "#type: node\nJust one line of prose."
    assert LIB.summary_paragraph(body) == "Just one line of prose."


# ── BP11-IDFIX T3: summarize memoizes the default path per (help_url, hda) ─────

def test_summarize_memoizes_default_path_one_lookup_per_key(monkeypatch):
    """200 summarize calls over 5 types cost 5 library lookups, not 200 (sec. 5)."""
    LIB._SUMMARY_CACHE.clear()
    calls = []

    def counter(keys):
        calls.append(tuple(keys))
        return ("Type\n\nDoes a thing.", "u")

    monkeypatch.setattr(SL, "help_summary", counter)
    urls = [f"operator:Sop/type{i}" for i in range(5)]
    for _ in range(40):                       # 40 x 5 = 200 summarize calls
        for u in urls:
            text, source = LIB.summarize(u)   # lookup=None -> memoized path
            assert source == "library" and text == "Does a thing."
    assert len(calls) == 5                     # one underlying lookup per type
    LIB._SUMMARY_CACHE.clear()


def test_injected_lookup_is_never_served_from_cache(monkeypatch):
    """An injected test lookup bypasses the memo, so it always runs."""
    LIB._SUMMARY_CACHE.clear()
    hits = []

    def spy(keys):
        hits.append(tuple(keys))
        return None

    LIB.summarize("operator:Sop/box", lookup=spy)
    LIB.summarize("operator:Sop/box", lookup=spy)
    assert len(hits) == 2                       # called both times, not cached


# ── BP11-IDFIX2 T2: markup paragraphs AFTER the title are skipped ──────────────

# The exact real-corpus body for PolyExtrude — help_summary(['nodes/sop/polyextrude'])
# at bp11/idfix, SYNAPSE_SIDEFX_CORPUS_ROOT=G:/HOUDINI22/_CORPUS (seat finding
# 17:10). The BOM+directive block and the include line sit AFTER the title, not
# at the very top, so header-stripping from the top left '#type: node' as the
# summary (the G2 bubble bug). The markup-only paragraphs must be skipped
# wherever they sit, so the first prose paragraph after the title wins.
_POLYEXTRUDE_REAL = (
    "PolyExtrude\n\n\ufeff#type: node\n\n"
    "Extrudes polygonal faces and edges.\n\n"
    ":include /shelf/polyextrude#includeme:")


def test_summary_paragraph_skips_markup_after_title_real_shape():
    assert LIB.summary_paragraph(_POLYEXTRUDE_REAL) == (
        "Extrudes polygonal faces and edges.")


def test_summarize_polyextrude_real_shape_yields_prose():
    # summarize with the exact real body -> the prose sentence, source 'library'.
    text, source = LIB.summarize("operator:Sop/polyextrude::2.0",
                                 lookup=lambda keys: (_POLYEXTRUDE_REAL, "u"))
    assert (text, source) == ("Extrudes polygonal faces and edges.", "library")


def test_is_markup_only_covers_directive_include_and_bom():
    # markup-only paragraphs (dropped wherever they sit):
    assert LIB._is_markup_only("\ufeff#type: node")
    assert LIB._is_markup_only("#type: node\n#context: sop")
    assert LIB._is_markup_only(":include /shelf/polyextrude#includeme:")
    assert LIB._is_markup_only(":include /news/beta:")
    # NOT markup-only (prose kept): a sentence, a wiki heading, and an inline
    # ':warning:' admonition on real prose (line-level markup, out of scope).
    assert not LIB._is_markup_only("Extrudes polygonal faces and edges.")
    assert not LIB._is_markup_only("= Name =")
    assert not LIB._is_markup_only(":warning:Deprecated: the node is gone.")


def _corpus_top_bodies(patterns=("%nodes/sop/%", "%nodes/lop/%")):
    """page-top chunk body per indexed node key, or skip if no corpus.

    *patterns* are ``source_url LIKE`` filters (SOP and LOP pages by default).
    Uses sidefx_library's own key normalization (``page_key``) and its
    earliest-chunk ('page-top') selection, so the invariant is checked on
    exactly the bodies the product summarizes.
    """
    root = os.environ.get(SL.ROOT_ENV)
    if not root or not (Path(root) / "current.json").exists():
        pytest.skip(f"{SL.ROOT_ENV} not configured / corpus absent")
    root = Path(root)
    pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
    db = root / pointer["database"]
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as con:
        con.execute("PRAGMA query_only = ON")
        like = " OR ".join("source_url LIKE ?" for _ in patterns)
        rows = con.execute(
            f"SELECT id, source_url, body FROM chunks WHERE domain='docs' AND ({like}) "
            "ORDER BY id", list(patterns)).fetchall()
    top: dict[str, tuple] = {}
    for cid, url, body in rows:
        key = SL.page_key(url)
        if key is None:
            continue
        if key not in top or cid < top[key][0]:
            top[key] = (cid, body)
    return top


def test_no_indexed_sop_lop_summary_is_a_markup_only_paragraph():
    """Corpus-gated invariant (BP11-IDFIX2 T2): across every indexed SOP/LOP node
    page, the chosen summary paragraph is never a help-markup-only block — no
    '#key: value' directive, ':name ...:' include, or BOM+directive leaks as a
    node's What line. Residual LINE-level markup ('=' stub headings, ':warning:'
    inline admonitions, '@' TOC/index pages) is not a markup-only paragraph and
    is out of this rule's scope; it is tracked in the leg receipt's for_ruling.
    Removing the markup-paragraph skip in summary_paragraph makes this bite.
    """
    top = _corpus_top_bodies()
    assert top, "no indexed SOP/LOP pages found in the corpus"
    leaks = [key for key, (_cid, body) in top.items()
             if LIB._is_markup_only(LIB.summary_paragraph(body))]
    assert leaks == [], f"markup-only summaries leaked for: {sorted(leaks)[:10]}"


# ── CRUX2 N1: an outage is never remembered; a rebuilt library is read again ──

def test_n1_a_lookup_that_raised_is_looked_up_again(monkeypatch):
    calls = []

    def lookup(keys):
        calls.append(tuple(keys))
        if len(calls) == 1:
            raise OSError("the library drive is not mounted")
        return ("Box\n\nMakes a box.", "u")

    monkeypatch.setattr(SL, "help_summary", lookup)
    monkeypatch.setattr(SL, "corpus_identity", lambda: ("G:/corpus", "gen1"))
    assert LIB.summarize("operator:Sop/box") == (None, "unknown")
    assert LIB.summarize("operator:Sop/box") == ("Makes a box.", "library")
    assert LIB.summarize("operator:Sop/box") == ("Makes a box.", "library")
    assert len(calls) == 2          # the outage was retried; the hit is remembered


def test_n1_a_miss_while_the_library_is_unreadable_is_not_remembered(monkeypatch):
    answers = [None, ("Box\n\nMakes a box.", "u")]
    monkeypatch.setattr(SL, "help_summary", lambda keys: answers.pop(0))
    monkeypatch.setattr(SL, "corpus_identity", lambda: None)
    assert LIB.summarize("operator:Sop/box") == (None, "unknown")
    assert LIB.summarize("operator:Sop/box") == ("Makes a box.", "library")


def test_n1_a_definite_miss_is_remembered_per_corpus_generation(monkeypatch):
    calls = []
    identity = {"now": ("G:/corpus", "gen1")}
    monkeypatch.setattr(SL, "help_summary", lambda keys: calls.append(tuple(keys)))
    monkeypatch.setattr(SL, "corpus_identity", lambda: identity["now"])
    LIB.summarize("operator:Sop/box")
    LIB.summarize("operator:Sop/box")
    assert len(calls) == 1          # a miss in a readable library is remembered
    identity["now"] = ("G:/corpus", "gen2")
    LIB.summarize("operator:Sop/box")
    assert len(calls) == 2          # a rebuilt library is looked up afresh


def test_corpus_identity_names_the_root_and_its_generation(tmp_path, monkeypatch):
    root = _build_corpus(tmp_path, [(1, _POLYBEVEL, "PolyBevel", _BODY)])
    monkeypatch.setenv(SL.ROOT_ENV, str(root))
    assert SL.corpus_identity() == (str(root.resolve()), "gen1")


def test_corpus_identity_is_none_when_the_database_is_missing(tmp_path, monkeypatch):
    root = _build_corpus(tmp_path, [(1, _POLYBEVEL, "PolyBevel", _BODY)])
    (root / "indexes" / "gen1.sqlite3").unlink()
    monkeypatch.setenv(SL.ROOT_ENV, str(root))
    assert SL.corpus_identity() is None


def test_corpus_identity_is_none_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.delenv(SL.ROOT_ENV, raising=False)
    monkeypatch.setattr(SL, "CONFIG_PATH", tmp_path / "missing.json")
    assert SL.corpus_identity() is None


# ── BP12 item 3: help paths built the way Houdini builds them ─────────────────
# URL shapes are the ones Houdini 22.0.400's defaultHelpUrl() writes (seat
# probe, 2026-09-29). Before this item, every Object, ROP and Labs node, and a
# VOP network, missed its page: the category was lower-cased instead of mapped
# (``Object`` is ``nodes/obj``, ``Driver`` is ``nodes/out``, ``VopNet`` is
# ``nodes/vex``), and a ``?namespace=`` query failed the pattern outright.

@pytest.mark.parametrize("url, keys", [
    ("operator:Object/geo", ["nodes/obj/geo", "nodes/manager/geo"]),
    ("operator:Driver/karma", ["nodes/out/karma", "nodes/manager/karma"]),
    ("operator:VopNet/vopmaterial", ["nodes/vex/vopmaterial", "nodes/manager/vopmaterial"]),
    ("operator:Cop/uv_grid_texture?namespace=labs&version=1.0",
     ["nodes/cop/labs--uv_grid_texture-1.0", "nodes/cop/labs--uv_grid_texture"]),
    ("operator:Sop/autouv?namespace=labs", ["nodes/sop/labs--autouv"]),
    ("operator:Sop/Rig_Delay?namespace=MOPSPlus&version=1.0",
     ["nodes/sop/mopsplus--rig_delay-1.0", "nodes/sop/mopsplus--rig_delay"]),
    ("operator:Sop/tool?namespace=studio::fx", ["nodes/sop/studio$$fx--tool"]),
])
def test_derive_keys_mirror_houdini_help_paths(url, keys):
    """Category folder, ``<namespace>--`` prefix (colons as ``$``), ``-<version>`` suffix."""
    assert LIB.derive_help_keys(url) == keys


def test_derive_keys_scoped_type_is_honestly_unknown():
    """A scoped type's page name needs ``hou`` to decode its scope: no key, no guess."""
    assert LIB.derive_help_keys("operator:Data/highpass?scopeop=cop/filterfrequencies") == []


def test_derive_keys_read_a_full_type_name_in_the_path():
    """``polyextrude::2.0`` or ``labs::widget::1.0`` written into the path still resolves."""
    assert LIB.derive_help_keys("operator:Sop/polyextrude::2.0") == [
        "nodes/sop/polyextrude-2.0", "nodes/sop/polyextrude", "nodes/manager/polyextrude"]
    assert LIB.derive_help_keys("operator:Sop/labs::widget::1.0") == [
        "nodes/sop/labs--widget-1.0", "nodes/sop/labs--widget"]


def test_summarize_end_to_end_labs_and_object_pages(tmp_path, monkeypatch):
    """Through the real help_summary, a Labs page and an Object page now resolve.

    Mutation: map ``Object`` to ``object``, or drop the ``?namespace=`` read,
    and the matching half of this test returns the honest unknown instead.
    """
    root = _build_corpus(tmp_path, [
        (1, f"{_DOCS}/nodes/sop/labs--widget-1.0.md", "Labs Widget",
         "Labs Widget\nLabs Widget\n# Labs Widget\n\nMakes widgets.\n\nMore text."),
        (2, f"{_DOCS}/nodes/obj/geo.md", "Geometry", "Geometry\n\nHolds geometry. More."),
    ])
    monkeypatch.setenv(SL.ROOT_ENV, str(root))
    assert LIB.summarize("operator:Sop/widget?namespace=labs&version=1.0") == (
        "Makes widgets.", "library")
    assert LIB.summarize("operator:Object/geo") == ("Holds geometry.", "library")


def test_page_key_is_the_one_help_summary_matches_on():
    """``page_key`` normalizes host, extension, trailing dash; examples never key."""
    assert SL.page_key(f"{_DOCS}/nodes/cop/labs--uv_grid_texture-1.0.md") == (
        "nodes/cop/labs--uv_grid_texture-1.0")
    assert SL.page_key(_POLYBEVEL) == "nodes/sop/polybevel"
    assert SL.page_key(_POLYBEVEL_EXAMPLE) is None


# ── BP12 item 3: the What line carries no help markup ─────────────────────────
# One test per shape the corpus sweep found. The bodies are invented; each
# copies the markup shape of a real library page named in its docstring.

def test_wiki_title_headings_are_skipped():
    """``= Name =`` titles: the Name SOP's prose sits after two of them, one behind a BOM."""
    body = "= Naming things =\n\n\ufeff= Widget =\n\nMakes widgets for you.\n\nMore."
    assert LIB.summary_text(body) == "Makes widgets for you."


def test_text_before_a_mid_body_bom_is_dropped():
    """A stray ``== Main ==`` above the page's own file (the Mantra procedural pages)."""
    body = "== Main ==\n\n\ufeff= Widget Procedural =\n\nRuns widgets at render time."
    assert LIB.summary_text(body) == "Runs widgets at render time."


def test_markdown_breadcrumb_title_is_skipped():
    """``Title / Title / # Title`` above the summary, as on every Labs page."""
    body = "Labs Widget\nLabs Widget\n# Labs Widget\n\nMakes widgets.\n\nIt does more."
    assert LIB.summary_text(body) == "Makes widgets."


def test_a_long_title_is_still_a_title():
    """A title up to 60 characters is skipped (Houdini Engine Procedural pages ran 42)."""
    body = "Widget Engine Procedural: Point Generate Mode\n\nCooks a widget per point."
    assert LIB.summary_text(body) == "Cooks a widget per point."


def test_warning_and_note_boxes_are_not_the_summary():
    """``:warning:Deprecated:`` (the Muscle tools), ``**NOTE:**``, ``> **Note**`` (Labs)."""
    for box in (":warning:Deprecated:\n    The Widget SOP is deprecated.",
                "**NOTE:**\n    Use the Gadget SOP instead.",
                "> **Note**\n> To be removed in a later version."):
        body = f"Widget\n\n{box}\n\nMakes widgets."
        assert LIB.summary_text(body) == "Makes widgets.", box


def test_picture_line_is_dropped():
    """``[Image:...]`` between the title and the summary (the MaterialX pages)."""
    body = "Widget\n\n[Image:/images/nodes/vop/widget.jpg]\n\nMakes widgets."
    assert LIB.summary_text(body) == "Makes widgets."


def test_inline_markup_becomes_plain_words():
    """Bold, italics, code spans and links keep only the words a reader sees."""
    body = ("Widget\n\nMakes **Shape Match** widgets with *Gadget SOP* and ''care'', "
            "a _value clip_, `usda` code, [Node:sop/gadget], "
            "[the guide|/help/widgets] and [Labs Guide](../sop/labs--guide).")
    assert LIB.summary_text(body) == (
        "Makes Shape Match widgets with Gadget SOP and care, a value clip, usda code, "
        "gadget, the guide and Labs Guide.")


def test_code_span_is_protected_from_italics():
    """``_id_`` inside backticks is code, not italics."""
    assert LIB.summary_text("Widget\n\nSets the `_id_` attribute.") == (
        "Sets the _id_ attribute.")


def test_brackets_and_globs_in_prose_are_left_alone():
    """A range, an array (``[in1, in2]``) or one glob is prose, not a link or italics."""
    body = "Widget\n\nMakes an array [in1, in2] of values in [0, 1] from *.bgeo files."
    assert LIB.summary_text(body) == (
        "Makes an array [in1, in2] of values in [0, 1] from *.bgeo files.")


def test_triple_quoted_tooltip_is_the_summary():
    """Houdini's tooltip rule, as HDA help writes it (the MOPs HDAs)."""
    help_text = ('= Widget Delay =\n#icon: opdef:.?widget.svg\n\n'
                 '""" Delays widgets. """\n\nThe Widget Delay behaves like the Delay.')
    assert LIB.summary_text(help_text) == "Delays widgets."
    assert LIB.summarize("operator:Sop/Widget_Delay?namespace=studio&version=1.0",
                         hda_help=help_text, lookup=lambda keys: None) == (
        "Delays widgets.", "hda")


def test_template_placeholder_is_honestly_unknown():
    """``[Basic Description]`` is a help template's blank, not a summary (Labs Tree Branch Placer)."""
    help_text = ('= Widget =\n\n#type: node\n#context: sop\n\n""" [Basic Description] """\n\n'
                 '[ Detailed description]\n\n@parameters\n    Tag:\n        [Needs tooltip]')
    assert LIB.summary_text(help_text) == ""
    assert LIB.summarize("operator:Sop/widget", hda_help=help_text,
                         lookup=lambda keys: None) == (None, "unknown")


def test_a_section_before_any_summary_is_honestly_unknown():
    """``## Overview`` or ``## Parameters`` first: the page top has no summary line.

    Load Layer for Editing opens on an Overview section and Cloth Solver on its
    Parameters. The text there describes a part or a context of the node, so
    the What line stays honestly unknown rather than borrowing it.
    """
    for section, text in (("Overview", "This node is like the Gadget node."),
                          ("Parameters", "Size:\n    How big the widget is."),
                          ("Related", "- [Node:sop/gadget]")):
        body = f"Widget\n{section}\n## {section}\n{text}"
        assert LIB.summary_text(body) == "", section


def test_a_sentence_above_a_heading_is_still_prose():
    """Only title-like lines above a heading are breadcrumbs; a sentence is kept."""
    assert LIB.summary_text("Makes widgets.\n## Parameters") == "Makes widgets."


def test_section_marker_and_parameter_term_end_the_search():
    """``@subtopics`` (the index pages) and ``Size:`` with an indented body."""
    assert LIB.summary_text("Widget examples\n\n@subtopics Examples\n\n:list_examples:") == ""
    assert LIB.summary_text("Widget\n\nSize:\n\n    How big the widget is.") == ""


def test_a_colon_ending_summary_without_a_definition_is_kept():
    """``... such as:`` followed by a list is prose, not a parameter term (Composite VOP)."""
    body = "Widget\n\nPerforms widget operations such as:\n\n- A over B\n- A under B"
    assert LIB.summary_text(body) == "Performs widget operations such as:"


def test_html_comment_include_page_and_source_path_title():
    """``<!-- -->`` (RBD Transform), a ``#type: include`` page, a ``.txt`` path as title."""
    assert LIB.summary_text(
        "Widget\n\n<!---#icon: SOP/widget--->\n\nMakes widgets.") == "Makes widgets."
    assert LIB.summary_text(
        "nodes/sop/common.txt\n\n\ufeff#type: include\n\nShared text about widgets.") == ""
    assert LIB.summary_text(
        "nodes/sop/widget.txt\n\n\ufeff= Widget =\n\nMakes widgets.") == "Makes widgets."
    assert LIB.summary_text(
        "nodes/sop/common.txt\n\n== Channel == (channel)\n\nAlign:\n    How to align.") == ""


def test_a_directive_without_its_colon_is_markup():
    """``#icon COMMON/materialx`` (the glTF material page) is a directive, not prose.

    Found by the Jev What-line check (BP12 item 3); the colon-only pattern let it
    through as a What line."""
    body = "nodes/vop/widget.txt\n\n#icon COMMON/widget\n\nA wrapper around the widget shader."
    assert LIB.summary_text(body) == "A wrapper around the widget shader."
    assert LIB.summary_text("Widget\n\n#1 rule: widgets first.") == "#1 rule: widgets first."


def test_tables_and_lists_are_not_the_summary():
    """A wiki table row (``Code ||``) or a list item never stands in for the summary."""
    body = "Widget\n\nCode ||\n    Meaning ||\n\n- first item\n\nMakes widgets."
    assert LIB.summary_text(body) == "Makes widgets."


def test_a_page_with_only_its_title_gives_the_title():
    """Unchanged behavior: a page whose only text is its title (the MaterialX Lama pages)."""
    assert LIB.summary_text("MtlX Widget\n\n:include _materialx#widget/:") == "MtlX Widget"


def test_residue_pattern_catches_each_shape_it_names():
    """The detector the sweep and the corpus gate share flags every shape above."""
    for leak in ("\ufeff= Name =", "Cloth Solver Parameters ## Parameters",
                 ":warning:Deprecated: gone.", "[Image:/images/a.jpg]", "Makes **bold** things.",
                 '""" Delays widgets.', "@subtopics Examples", "#icon: SOP/x",
                 "a _value clip_ here", "see [Node:sop/copy]", "Code || Meaning ||",
                 "#icon COMMON/materialx",
                 "nodes/sop/widget.txt", "[Basic Description]", "with *Gadget SOP* too"):
        assert LIB.RESIDUE.search(leak), leak
    for clean in ("Makes widgets.", "Makes an array [in1, in2] of values in [0, 1].",
                  "Reads *.bgeo files.", "if value1<=value2.", "snake_case_name stays"):
        assert not LIB.RESIDUE.search(clean), clean


def test_no_node_page_what_line_carries_help_markup():
    """Corpus-gated (BP12 item 3): across every indexed node page, the What line
    carries no help markup by ``library.RESIDUE``, the same pattern
    ``scripts/sweep_identify_summaries.py`` reports with. Loosening a rule in
    summary_paragraph or plain_text makes this bite on the real library."""
    top = _corpus_top_bodies(("%nodes/%",))
    assert top, "no indexed node pages found in the corpus"
    leaks = sorted(key for key, (_cid, body) in top.items()
                   if LIB.RESIDUE.search(LIB.summary_text(body)))
    assert leaks == [], f"help markup reached a What line for: {leaks[:10]}"
