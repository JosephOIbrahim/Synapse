"""F05: the comment over PANEL_ROW_ORDER must not carry a stale row count."""

import re
from pathlib import Path

_SRC = (
    Path(__file__).resolve().parent.parent
    / "python" / "synapse" / "panel" / "command_palette.py"
)

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _panel_row_comment_and_count():
    src = _SRC.read_text(encoding="utf-8")
    start = src.index("# PNL-L3B (1):")
    tuple_start = src.index("PANEL_ROW_ORDER: tuple[str, ...] = (", start)
    comment = src[start:tuple_start]
    body = src[tuple_start:src.index(")", tuple_start + len("PANEL_ROW_ORDER: tuple[str, ...] = ("))]
    count = len(re.findall(r'"/[^"]+"', body))
    return src, comment, count


def test_stale_five_count_removed():
    src, _, _ = _panel_row_comment_and_count()
    assert "the five panel rows" not in src


def test_any_count_in_comment_matches_tuple():
    _, comment, count = _panel_row_comment_and_count()
    assert count == 7
    for word, n in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\s+panel rows\b", comment):
            assert n == count, f"comment says {word} panel rows, tuple has {count}"
