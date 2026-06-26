"""Corpus activation — the panel's "Corpus" button materializes the canonical
repo rag/ corpus and grounds scout in real H21 Solaris/Karma docs.

Pure Python (no Qt, no hou) so it runs under stock ``pytest -q`` AND hython —
this is the real gate for Fix 1 (the live-panel click is only a smoke check).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def test_activate_builds_corpus_and_grounds_solaris():
    # activate() mutates module-global scout state — save/restore for isolation.
    from synapse.cognitive.tools import scout as _scout
    saved = _scout.RAG_ROOT
    try:
        from synapse.cognitive.tools import scout_ingest
        info = scout_ingest.activate()
        assert info["loaded"] is True
        assert info["store_root"]

        from synapse.cognitive.tools.scout import synapse_scout
        hits = synapse_scout("karmarendersettings xpu engine", k=4).get("hits", [])
        assert hits, "the repo rag/ corpus must surface karmarendersettings docs"
        sources = " ".join(h.get("source", "") for h in hits).lower()
        assert any(k in sources for k in ("karma", "solaris", "render")), sources
    finally:
        _scout.RAG_ROOT = saved
        for cache in (_scout._CORPUS, _scout._FTS, _scout._DENSE,
                      _scout._SYMS, _scout._TABLE_CACHE):
            cache.clear()


def test_activate_does_not_point_at_raw_g_drive():
    # The whole point: activate() uses the canonical repo rag/ corpus, NOT raw
    # G:\HOUDINI21_RAG_SYSTEM (whose corpus/ has no searchable_text → hollow).
    from synapse.cognitive.tools import scout as _scout
    saved = _scout.RAG_ROOT
    try:
        from synapse.cognitive.tools import scout_ingest
        info = scout_ingest.activate()
        assert "HOUDINI21_RAG_SYSTEM" not in info["store_root"]
        assert "scout_corpus" in info["store_root"].replace("\\", "/")
    finally:
        _scout.RAG_ROOT = saved
        for cache in (_scout._CORPUS, _scout._FTS, _scout._DENSE,
                      _scout._SYMS, _scout._TABLE_CACHE):
            cache.clear()


def test_panel_wires_corpus_button():
    # Source-scan (Qt-free): the rail defines a Corpus button + handlers that call
    # scout_ingest.activate, placed next to the Connect button.
    src = open(
        os.path.join(_ROOT, "python", "synapse", "panel", "synapse_panel.py"),
        encoding="utf-8",
    ).read()
    for marker in (
        "_corpus_btn",
        "def _on_corpus",
        "def _refresh_corpus_state",
        "scout_ingest.activate",
        "bot.addWidget(self._corpus_btn)",
    ):
        assert marker in src, marker


def test_system_prompt_grounds_solaris_builds_in_scout():
    # Fix 2: the Solaris build guidance must wire Safety Rule 15 — scout before
    # authoring non-template nodes — so the agent grounds in real H21 docs.
    src = open(
        os.path.join(_ROOT, "python", "synapse", "panel", "system_prompt.py"),
        encoding="utf-8",
    ).read()
    assert "synapse_scout" in src
    assert "Safety Rule 15" in src
    assert "exists_in_runtime" in src
