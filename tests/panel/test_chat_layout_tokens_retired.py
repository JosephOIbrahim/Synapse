"""Hour2 design M1 (2026-10-06): the nine chat-layout tokens in the legacy
``synapse.panel.tokens`` module had no live consumer and are deleted.

Two independent checks, so neither can pass by accident:

1. The token outcome: the module no longer exposes any of the nine names
   (including the phantom CHAT_TIMESTAMP_SIZE=18, a timestamp size no surface
   ever drew).
2. No shipped source names them as an attribute or a bare identifier, scanned
   by AST so comments (chat_display.py's "was tokens.CHAT_BUBBLE_MARGIN_Y"
   history note) do not count as consumers and a real read cannot hide in one.

Pure / stdlib: runs under stock ``pytest`` and under hython.
"""
import ast
import importlib
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RETIRED = (
    "CHAT_BUBBLE_PADDING",
    "CHAT_BUBBLE_RADIUS",
    "CHAT_BUBBLE_MARGIN_Y",
    "CHAT_GROUP_MARGIN_Y",
    "CHAT_BUBBLE_MAX_WIDTH_PCT",
    "CHAT_INPUT_MIN_H",
    "CHAT_INPUT_MAX_H",
    "CHAT_TIMESTAMP_SIZE",
    "CHAT_TYPING_DOT_SIZE",
)


@pytest.mark.parametrize("name", RETIRED)
def test_retired_chat_layout_token_is_gone(name):
    tokens = importlib.import_module("synapse.panel.tokens")
    assert not hasattr(tokens, name), name


def _names_in(path):
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            yield node.attr
        elif isinstance(node, ast.Name):
            yield node.id


def test_no_shipped_source_reads_a_retired_chat_layout_token():
    src_root = os.path.join(_ROOT, "python", "synapse")
    hits = []
    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if fn.endswith(".py"):
                path = os.path.join(dirpath, fn)
                used = set(_names_in(path)) & set(RETIRED)
                if used:
                    hits.append((os.path.relpath(path, _ROOT), sorted(used)))
    assert not hits, hits
