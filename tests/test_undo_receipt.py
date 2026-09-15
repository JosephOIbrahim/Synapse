"""The Undo Receipt (TRUST-2 / TRUST-4 disclosure).

Every mutating handler already computes the artist's answer to "what does one
Ctrl+Z reverse?" as its ``hou.undos.group("<label>")`` label. Before this leg
the label was discarded at every call site and a repo-wide grep for
``Ctrl+Z|undoable|can be undone`` over ``*.py`` returned zero artist-facing
strings. The receipt turns the label into words and rides on the result dict.

Pure: no hou, no Houdini. The label table below is taken from real
``hou.undos.group("...")`` call sites under ``python/synapse/server/`` and a
pin asserts every entry still exists there, so the table cannot drift into
fiction. A second pin asserts the inverse: no ``undo_receipt("X")`` call
exists in a file that does not also open ``hou.undos.group("X")`` -- the
receipt never promises a group nobody entered.
"""
import inspect
import os
import re
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "python"))

from synapse.core.tool_results import (  # noqa: E402
    UNDO_RECEIPT_PREFIX, undo_receipt_line)
from synapse.panel.activity import (  # noqa: E402
    UNDO_RECEIPT_SEP, split_undo_receipt, tool_status, with_undo_receipt)
from synapse.server.handler_helpers import (  # noqa: E402
    undo_label_words, undo_receipt)

_SERVER = os.path.join(_ROOT, "python", "synapse", "server")
_GROUP_RE = re.compile(r'hou\.undos\.group\("([^"]+)"\)')
_RECEIPT_RE = re.compile(r'undo_receipt\("([^"]+)"')

#: label -> artist words. Every label is a live hou.undos.group call site.
LABEL_WORDS = [
    ("synapse_node_create", "node create"),                       # handlers_node.py
    ("synapse_node_delete", "node delete"),                       # handlers_node.py
    ("synapse_node_connect", "node connect"),                     # handlers_node.py
    ("synapse_set_parm", "set parameter"),                        # handlers.py
    ("synapse_set_keyframe", "set keyframe"),                     # handlers_render.py
    ("synapse_batch", "batch"),                                   # handlers.py
    ("synapse_execute", "execute"),                               # handlers.py
    ("SYNAPSE: build_graph", "build graph"),                      # handlers_solaris_graph.py
    ("SYNAPSE: set_usd_attribute", "set USD attribute"),          # handlers_usd.py
    ("SYNAPSE: create_usd_prim", "create USD primitive"),         # handlers_usd.py
    ("synapse_cops_create_copnet", "COPs create COP network"),    # handlers_cops.py
    ("synapse_cops_set_opencl", "COPs set OpenCL"),               # handlers_cops.py
    ("SYNAPSE: matlib_bind", "material library bind"),            # handlers_solaris_compose.py
    ("SYNAPSE: set_payload_loadstate", "set payload load state"), # handlers_usd.py
    ("SYNAPSE: Copernicus lookdev", "Copernicus lookdev"),        # solaris_lookdev.py
    ("synapse_hda_create", "HDA create"),                         # handlers_hda.py
]

#: The handlers this leg wired (CLAUDE.md §Identity names them as undo-wrapped).
WIRED_LABELS = {
    "synapse_node_create", "synapse_node_delete", "synapse_node_connect",
    "synapse_set_parm", "synapse_set_keyframe",
}


def _server_sources():
    for name in sorted(os.listdir(_SERVER)):
        if name.endswith(".py"):
            path = os.path.join(_SERVER, name)
            with open(path, encoding="utf-8") as fh:
                yield name, fh.read()


def _live_group_labels():
    labels = {}
    for name, text in _server_sources():
        for label in _GROUP_RE.findall(text):
            labels.setdefault(label, set()).add(name)
    return labels


# ── label -> words ──────────────────────────────────────────────────

@pytest.mark.parametrize("label,words", LABEL_WORDS)
def test_label_words_table(label, words):
    assert undo_label_words(label) == words
    assert undo_receipt(label)["undo"]["artist"] == UNDO_RECEIPT_PREFIX + words


def test_every_table_label_is_a_live_group_call_site():
    live = _live_group_labels()
    missing = [label for label, _ in LABEL_WORDS if label not in live]
    assert not missing, "table labels with no hou.undos.group call site: %r" % missing


def test_the_table_covers_at_least_eight_real_labels():
    assert len({label for label, _ in LABEL_WORDS}) >= 8


def test_words_never_come_back_empty():
    assert undo_label_words("") == "this change"
    assert undo_label_words(None) == "this change"
    assert undo_label_words("synapse_") == "this change"
    assert undo_receipt("")["undo"]["artist"] == UNDO_RECEIPT_PREFIX + "this change"


# ── the receipt dict ────────────────────────────────────────────────

def test_receipt_shape():
    r = undo_receipt("synapse_node_create")
    assert set(r) == {"undo"}
    undo = r["undo"]
    assert set(undo) == {"label", "artist", "rolls_back_on_failure", "on_failure"}
    assert undo["label"] == "synapse_node_create"           # verbatim, citable
    assert undo["artist"].startswith(UNDO_RECEIPT_PREFIX)
    assert "Ctrl+Z" in undo["artist"]                       # the string that was absent
    assert undo["rolls_back_on_failure"] is False           # the honest default
    assert "partial work stays" in undo["on_failure"]


def test_rolls_back_flag_is_static_and_changes_only_the_failure_words():
    group_only = undo_receipt("SYNAPSE: build_graph")["undo"]
    rolls_back = undo_receipt("SYNAPSE: build_graph", rolls_back_on_failure=True)["undo"]
    assert group_only["artist"] == rolls_back["artist"]
    assert group_only["label"] == rolls_back["label"]
    assert rolls_back["rolls_back_on_failure"] is True
    assert group_only["on_failure"] != rolls_back["on_failure"]
    assert "undone for you" in rolls_back["on_failure"]
    # a truthy non-bool is coerced, never leaked
    assert undo_receipt("x", rolls_back_on_failure=1)["undo"]["rolls_back_on_failure"] is True


def test_helper_is_pure_no_hou_no_group():
    """The helper records a group; it never opens one. Checked on the AST so a
    docstring that *names* hou.undos.group (it does) cannot fool the pin."""
    import ast
    import textwrap
    names = set()
    for fn in (undo_receipt, undo_label_words):
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
    assert "hou" not in names
    assert "undos" not in names and "group" not in names


# ── wiring pins (source text, no Houdini) ───────────────────────────

def test_no_receipt_without_a_group_in_the_same_file():
    """undo_receipt("X") may only appear in a file that opens hou.undos.group("X")."""
    orphans = []
    for name, text in _server_sources():
        if name == "handler_helpers.py":
            continue
        groups = set(_GROUP_RE.findall(text))
        for label in _RECEIPT_RE.findall(text):
            if label not in groups:
                orphans.append((name, label))
    assert not orphans, "receipt promises a group its file never opens: %r" % orphans


def test_the_five_named_handlers_carry_the_receipt():
    wired = set()
    for _name, text in _server_sources():
        wired.update(_RECEIPT_RE.findall(text))
    assert WIRED_LABELS <= wired, "receipt dropped from: %r" % sorted(WIRED_LABELS - wired)


def test_set_parm_group_literal_survives_the_wiring():
    """test_node_undo_grouping pins the literal group call; the receipt must not
    have hoisted it into a variable."""
    with open(os.path.join(_SERVER, "handlers.py"), encoding="utf-8") as fh:
        text = fh.read()
    body = re.search(r"\n    def _handle_set_parm\(.*?(?=\n    def )", text, re.S).group(0)
    assert body.count('hou.undos.group("synapse_set_parm")') == 3
    assert body.count('undo_receipt("synapse_set_parm")') == 3


# ── the panel side ──────────────────────────────────────────────────

def test_undo_receipt_line_reads_only_minted_receipts():
    r = undo_receipt("synapse_set_parm")
    assert undo_receipt_line(r) == UNDO_RECEIPT_PREFIX + "set parameter"
    assert undo_receipt_line({"node": "/obj/geo1", **r}) == UNDO_RECEIPT_PREFIX + "set parameter"
    assert undo_receipt_line(None) == ""
    assert undo_receipt_line("not a dict") == ""
    assert undo_receipt_line({}) == ""
    assert undo_receipt_line({"undo": "yes"}) == ""
    assert undo_receipt_line({"undo": {"artist": "trust me"}}) == ""   # hand-built: no
    assert undo_receipt_line({"undo": {"label": "synapse_set_parm"}}) == ""


def test_with_undo_receipt_keeps_the_request_summary_behind_the_receipt():
    r = undo_receipt("synapse_node_create")
    summary = '{"parent": "/obj", "node_type": "geo"}'
    detail = with_undo_receipt(summary, r)
    assert detail == UNDO_RECEIPT_PREFIX + "node create" + UNDO_RECEIPT_SEP + summary
    assert split_undo_receipt(detail) == (UNDO_RECEIPT_PREFIX + "node create", summary)
    # no receipt -> the detail is untouched, whatever it is
    assert with_undo_receipt(summary, {"path": "/obj/geo1"}) == summary
    assert with_undo_receipt(summary, None) == summary
    assert with_undo_receipt(None, None) == ""
    assert with_undo_receipt("", r) == UNDO_RECEIPT_PREFIX + "node create"
    assert split_undo_receipt(summary) == ("", summary)
    assert split_undo_receipt(None) == ("", "")


def test_tool_status_line_carries_the_receipt_only_when_present():
    r = undo_receipt("synapse_set_parm")
    detail = with_undo_receipt('{"node": "/obj/geo1"}', r)
    assert tool_status("houdini_set_parm", "done", detail) == (
        "Finished: Set a parameter — One Ctrl+Z reverses: set parameter")
    # the running phase carries the request summary, never a receipt
    assert tool_status("houdini_set_parm", "running", '{"node": "/obj/geo1"}') == (
        "Running: Set a parameter")
    # the old two-argument form is byte-identical to before
    assert tool_status("houdini_set_parm", "done") == "Finished: Set a parameter"
    assert tool_status("houdini_create_usd_prim", "error") == "Failed: Create USD primitive"
