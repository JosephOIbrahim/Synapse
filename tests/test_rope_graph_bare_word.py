"""A single word is not a line: the veto never passes a seed on one quoted or bare word.

159216d5 stopped the veto reading a string literal out of cited code as a span. One road was
still open: the whole evidence string is tried first, as a substring of each line. Evidence
that is only an ordinary word -- "claude", `running`, running -- is a substring of any line
that holds it, so the veto passed it and moved the seed to the first such line. A lone word
cannot anchor a line, so it must be vetoed like any evidence the file does not hold.

No model is started: veto() only reads files under a temp ROOT.
"""
import importlib.util
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(REPO, "harness", "rope", "graph.py")

STORE = (
    "import os\n"
    "\n"
    "\n"
    "def session_dir(hip_dir):\n"
    '    return os.path.join(hip_dir, "claude")\n'
)
PANEL = (
    "def verb(phase):\n"
    "    _check_symbol_table(),\n"
    "    return 'running' if phase else \"running\"\n"
)


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


@pytest.fixture
def G(tmp_path):
    spec = importlib.util.spec_from_file_location("_rope_graph_bare_word", GRAPH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    root = str(tmp_path / "repo")
    _write(root, "pkg/session_store.py", STORE)
    _write(root, "pkg/panel.py", PANEL)
    mod.ROOT = mod.rope.ROOT = root
    return mod


@pytest.mark.parametrize("evidence", ['"claude"', "`claude`", "'claude'", "claude", '  "claude"  '])
def test_an_uncited_quoted_word_does_not_survive_the_veto(G, evidence):
    """Fails if a seed whose whole evidence is one word passes because a line holds that word."""
    c = {"file": "pkg/session_store.py", "line": 1, "evidence": evidence}
    assert G.veto(c) == "no evidence line"
    assert c["line"] == 1          # never moved to the line that happens to hold the word


@pytest.mark.parametrize("evidence", ['"running"', "'running'", "`running`", "running"])
def test_running_is_not_a_line_either(G, evidence):
    """Fails if the TT-2/TT-3 word "running" passes the veto on its own, in any quoting."""
    c = {"file": "pkg/panel.py", "line": 1, "evidence": evidence}
    assert G.veto(c) == "no evidence line"
    assert c["line"] == 1


def test_a_cited_single_word_is_not_a_line(G):
    """Fails if a file:line cite turns one quoted word into line evidence (the prefix-strip road)."""
    for evidence in ('session_store.py:5 "claude"', "session_store.py:5 `claude`"):
        c = {"file": "pkg/session_store.py", "line": 1, "evidence": evidence}
        assert G.veto(c) == "evidence not found in the file"
        assert c["line"] == 1


def test_a_compound_seed_skips_its_word_span_for_its_line_span(G):
    """Fails if the bare-word rule drops a compound seed whose other span is a real line."""
    c = {"file": "pkg/session_store.py", "line": 1,
         "evidence": 'session_store.py:2 "claude"; session_store.py:5 `return os.path.join(hip_dir, "claude")`'}
    assert G.veto(c) == ""
    assert c["evidence"] == 'return os.path.join(hip_dir, "claude")'
    assert c["line"] == 1          # the line sits inside the cited window; nothing moves


def test_a_code_line_without_whitespace_still_passes(G):
    """Fails if the rule widens to 'no whitespace': SC-02's real span is one token plus punctuation."""
    c = {"file": "pkg/panel.py", "line": 2, "evidence": "panel.py:2 `_check_symbol_table(),`"}
    assert G.veto(c) == ""
    assert c["evidence"] == "_check_symbol_table(),"
