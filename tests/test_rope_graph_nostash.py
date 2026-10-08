"""Every prompt the rope graph writes forbids git stash and names the safe way to test old code.

On 2026-10-07 two lanes working in separate worktrees swapped patches: stash refs live in the
shared .git, so one lane's `git stash pop` took the other lane's stash. The safe way to run old
code is `git archive <rev> python | tar -x -C <scratch>` with PYTHONPATH on the scratch copy;
`git show <rev>:<path>` alone breaks package imports.

No model is started and no repo is touched: `git` is replaced for the referee's `git show`.
"""
import importlib.util
import os
import types

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(REPO, "harness", "rope", "graph.py")


def _load_graph():
    spec = importlib.util.spec_from_file_location("_rope_graph_nostash", GRAPH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _prompt(G, kind, monkeypatch):
    fix = {"id": "F01", "kind": "fix", "title": "set the value", "files": ["pkg/a.py"],
           "change": "- make VALUE fixed", "accept": []}
    st = {"areas": {"pkg": {"direct": 2}}, "items": [fix]}
    if kind == "scout":
        it = {"id": "S01", "kind": "scout", "areas": ["pkg"], "files": ["pkg/a.py"], "lines": 1}
    elif kind == "fix":
        it = fix
    else:
        monkeypatch.setattr(G, "git", lambda *a, **k: types.SimpleNamespace(stdout="abc1234 fix\n"))
        it = {"id": "R01", "kind": "review", "commits": [["abc1234", "F01"]]}
    return G.build_prompt(st, it)


@pytest.mark.parametrize("kind", ["scout", "fix", "review"])
def test_every_prompt_forbids_git_stash_and_names_git_archive(kind, monkeypatch):
    """Fails if any session the graph starts is not told stash is shared across worktrees."""
    G = _load_graph()
    text = _prompt(G, kind, monkeypatch)
    assert "Never run git stash" in text
    assert "shared by every worktree" in text
    assert "git archive <rev> python | tar -x -C <scratch>" in text
    assert "PYTHONPATH" in text
    assert "git show <rev>:<path>" in text


def test_the_fixer_keeps_its_pytest_only_rule(monkeypatch):
    """Fails if the git rule displaced the fixer's one permitted command or widened its tools."""
    G = _load_graph()
    text = _prompt(G, "fix", monkeypatch)
    assert "The only command you may run is: python -m pytest" in text
    assert "git" not in G.FIX_ALLOW and "tar" not in G.FIX_ALLOW
