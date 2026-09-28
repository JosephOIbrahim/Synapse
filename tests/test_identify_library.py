"""library: node type -> summary by EXACT help path only, never a search."""
from __future__ import annotations

import json
import sqlite3

from synapse.identify import library as LIB
from synapse.cognitive.tools import sidefx_library as SL


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
    assert LIB.derive_help_keys("operator:Sop/polybevel?version=3.0") == [
        "nodes/sop/polybevel-3.0", "nodes/sop/polybevel"]


def test_derive_keys_base_only():
    assert LIB.derive_help_keys("operator:Sop/box") == ["nodes/sop/box"]


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
