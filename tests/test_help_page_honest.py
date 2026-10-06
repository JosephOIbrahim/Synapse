"""Keep docs/help/index.html honest against the panel.

Collected: the text of every ``<span class="says">...</span>`` in the help page,
HTML-unescaped. That element is how the page quotes a word the panel shows an
artist (a status, a verdict, a button label), so each quote must exist in
python/synapse/panel source. Also pinned: the version the page prints
(``<span class="ver">`` block) equals the repo-root VERSION file.

Text only: no Houdini, no Qt.
"""
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "help" / "index.html"
PANEL = ROOT / "python" / "synapse" / "panel"

# name -> why it cannot appear verbatim in panel source. Keep short.
ALLOWLIST = {
    "2 CHANGES": "built at runtime from the format '%d CHANGE%s' (synapse_panel.py)",
}

_SAYS = re.compile(r'<span class="says">(.*?)</span>', re.S)


def collect_names():
    text = PAGE.read_text(encoding="utf-8")
    names = []
    for raw in _SAYS.findall(text):
        name = " ".join(html.unescape(re.sub(r"<[^>]+>", "", raw)).split())
        if name and name not in names:
            names.append(name)
    return names


def _panel_source():
    text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(PANEL.rglob("*.py"))
    )
    # Source spells some glyphs as escapes ("← REVERT"); the artist sees the glyph.
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)


def missing_names(names, source=None):
    source = _panel_source() if source is None else source
    return [n for n in names if n not in ALLOWLIST and n not in source]


def test_collector_finds_names():
    assert len(collect_names()) >= 10


def test_lookup_reports_made_up_name_missing():
    assert missing_names(["Zzyzx relay"]) == ["Zzyzx relay"]


def test_every_says_name_is_in_panel_source():
    missing = missing_names(collect_names())
    assert not missing, f"help page quotes names the panel never shows: {missing}"


def test_page_version_matches_version_file():
    text = PAGE.read_text(encoding="utf-8")
    m = re.search(r'<span class="ver">.*?<span>(v\d+\.\d+\.\d+)</span>', text, re.S)
    assert m, "help page prints no version"
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert m.group(1) == "v" + version
