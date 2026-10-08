"""The graph's veto keeps the one quoted span a seed's own file holds, instead of vetoing it.

The cto run of 2026-10-07 wrote compound evidence for 5 of its 12 seeds: several
`file:line "quote"` pieces joined by ';' or '|', some naming other files. The veto wanted one
exact line, so all five read "evidence not found in the file" until a one-off script outside
the repo cut them down by hand -- and that script tried quoted spans before the whole string,
so three clean lines were cut to a bare token. The shapes below are those seeds' shapes.

No model is started: veto() and collect() only read files under a temp ROOT.
"""
import importlib.util
import json
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
POLICY = (
    "REASONS = (\n"
    '    "a refusal is not a "\n'
    '            "bridge /mcp consent-gated call)"\n'
    ")\n"
)
DOC = (
    "# Demo\n"
    "\n"
    "Show the downloaded `SYNAPSE-5.67.4-Setup.exe`, then open it.\n"
)
RECIPE = '    {"type": "usdrop", "name": "usdrop1", "parms": {}},\n'
OTHER = "bridge = LosslessExecutionBridge(consent_callback=lambda op: True)\n"


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


@pytest.fixture
def G(tmp_path):
    spec = importlib.util.spec_from_file_location("_rope_graph_evidence", GRAPH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    root = str(tmp_path / "repo")
    for rel, text in (("pkg/session_store.py", STORE), ("pkg/worker_policy.py", POLICY),
                      ("docs/demo.md", DOC), ("pkg/recipe_book.py", RECIPE), ("pkg/bridge.py", OTHER)):
        _write(root, rel, text)
    mod.ROOT = mod.rope.ROOT = root
    return mod


def test_backtick_spans_keep_the_one_in_the_seeds_own_file(G):
    """Fails if a compound seed whose first span names another file is vetoed."""
    c = {"file": "pkg/session_store.py", "line": 67,
         "evidence": 'bridge.py:1 `bridge = LosslessExecutionBridge(consent_callback=lambda op: True)`; '
                     'session_store.py:67 `return os.path.join(hip_dir, "claude")`; '
                     'synapse_panel.py:4634 `_session_store.save_conversation(self._messages)`.'}
    assert G.veto(c) == ""
    assert c["evidence"] == 'return os.path.join(hip_dir, "claude")'
    assert c["line"] == 5          # the cited line was wrong; the span's own line wins


def test_double_quoted_span_with_escaped_quotes(G):
    """Fails if a "..." span carrying \\" escapes is not unescaped before it is looked up."""
    c = {"file": "pkg/worker_policy.py", "line": 3,
         "evidence": 'worker_policy.py:3 "            \\"bridge /mcp consent-gated call)\\"" ; '
                     'bridge.py:1 "bridge = LosslessExecutionBridge(consent_callback=lambda op: True)"'}
    assert G.veto(c) == ""
    assert c["evidence"] == '"bridge /mcp consent-gated call)"'
    assert c["line"] == 3


def test_a_quoted_span_that_holds_backticks_is_kept_whole(G):
    """Fails if a span is cut at an inner backtick pair instead of read in order."""
    c = {"file": "docs/demo.md", "line": 3,
         "evidence": 'docs/demo.md:3 "Show the downloaded `SYNAPSE-5.67.4-Setup.exe`, then open it" | '
                     'docs/status.md:5 "This feature map was reviewed on **2026-09-28**."'}
    assert G.veto(c) == ""
    assert c["evidence"] == "Show the downloaded `SYNAPSE-5.67.4-Setup.exe`, then open it"


def test_a_file_line_prefix_is_dropped(G):
    """Fails if an unquoted 'file:line text' seed is vetoed for its prefix."""
    c = {"file": "pkg/session_store.py", "line": 5,
         "evidence": 'python/synapse/server/session_store.py:5 return os.path.join(hip_dir, "claude")'}
    assert G.veto(c) == ""
    assert c["evidence"] == 'return os.path.join(hip_dir, "claude")'


def test_a_clean_line_is_never_cut_to_a_token_inside_it(G):
    """Fails if the whole line is not tried before the quoted tokens it contains."""
    c = {"file": "pkg/recipe_book.py", "line": 1, "evidence": RECIPE.rstrip("\n")}
    assert G.veto(c) == ""
    assert c["evidence"] == RECIPE.rstrip("\n")


def test_a_line_gone_from_the_file_is_not_rescued_by_a_token_inside_it(G):
    """Fails if a stale or invented line passes because a quoted token in it still occurs."""
    c = {"file": "pkg/recipe_book.py", "line": 1,
         "evidence": '{"type": "usdrop", "name": "usdrop1", "parms": {"flag": 1}},'}
    assert G.veto(c) == "evidence not found in the file"


def test_a_literal_inside_cited_code_is_not_a_span(G):
    """Fails if a cited code line that is not in the file passes on a string literal inside it.

    The cto run's TT-2 shape: unquoted code, a (file:line) suffix, a second segment. Its literal
    "claude" occurs in this file on another line; the veto must not move the seed there.
    """
    c = {"file": "pkg/session_store.py", "line": 5,
         "evidence": 'name = {"claude": "claude", "codex": "x"}.get(k, k)  (session_store.py:5); '
                     'status = "ok" if name else "fail"  (:9)'}
    assert G.veto(c) == "evidence not found in the file"
    assert c["line"] == 5


def test_spans_from_other_files_only_are_still_vetoed(G):
    """Fails if the normaliser lets evidence through that this file does not hold."""
    c = {"file": "pkg/session_store.py", "line": 5,
         "evidence": 'bridge.py:1 `bridge = LosslessExecutionBridge(consent_callback=lambda op: True)`; '
                     'panel.py:9 "self._messages = load_conversation()"'}
    assert G.veto(c) == "evidence not found in the file"
    assert G.veto({"file": "pkg/session_store.py", "line": 5, "evidence": '`os.p` "join"'}) \
        == "evidence not found in the file"
    assert G.veto({"file": "pkg/session_store.py", "line": 5, "evidence": "  x  "}) == "no evidence line"


def test_collect_passes_a_compound_seed(G, tmp_path):
    """Fails if a seed written the way the cto run wrote it reaches route() vetoed."""
    run = tmp_path / "run"
    run.mkdir()
    (run / "seeds.json").write_text(json.dumps([
        {"file": "pkg/session_store.py", "line": 67, "claim": "c", "fix": "f", "check": "k",
         "evidence": 'session_store.py:67 `return os.path.join(hip_dir, "claude")`; '
                     'synapse_panel.py:745 `self._messages, _sess_scope = load()`'}]), encoding="utf-8")
    st = {"run": str(run), "items": [], "areas": {}}
    (c,) = G.collect(st)
    assert c["id"] == "SEED-1" and c["veto"] == ""
    assert c["evidence"] == 'return os.path.join(hip_dir, "claude")' and c["line"] == 5
