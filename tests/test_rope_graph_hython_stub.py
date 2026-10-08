"""Every prompt the rope graph writes forbids a bare `import synapse` under hython and names the stub.

Post-demo loop 2: the mandated run puts <worktree>/python on sys.path inside hython, so a
measurement script that runs `import synapse.cv` bare executes python/synapse/__init__.py
headless, which imports synapse.core, synapse.inspector and synapse.memory.store first. The
stub the rule teaches is also executed here, against a throwaway package whose __init__ fails
loudly, so the rule cannot teach a snippet that does not work.

No model is started, no hython is run and no repo is touched: `git` is replaced for the
referee's `git show`, and the stub runs in a child Python against a tmp_path package.
"""
import importlib.util
import os
import subprocess
import sys
import types

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(REPO, "harness", "rope", "graph.py")


def _load_graph():
    spec = importlib.util.spec_from_file_location("_rope_graph_hython_stub", GRAPH)
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
def test_every_prompt_forbids_a_bare_synapse_import_under_hython(kind, monkeypatch):
    """Fails if any session the graph starts is not told why and how to stub synapse in hython."""
    G = _load_graph()
    text = _prompt(G, kind, monkeypatch)
    assert "Never import synapse" in text
    assert "hython" in text
    assert "python/synapse/__init__.py" in text
    assert 'types.ModuleType("synapse")' in text
    assert "__path__" in text
    # the stash rule is still there: the new rule joined it, it did not replace it
    assert "Never run git stash" in text


def test_the_referee_drops_an_unstubbed_hython_script(monkeypatch):
    """Fails if the referee has no DROP criterion for a hython script that skips the stub."""
    G = _load_graph()
    text = _prompt(G, "review", monkeypatch)
    drop = text.split("DROP a commit when", 1)[1].split("Otherwise KEEP", 1)[0]
    assert "hython" in drop and "stub" in drop


def test_the_fixer_still_runs_only_pytest(monkeypatch):
    """Fails if the hython rule widened the fixer's tools or displaced its one permitted command."""
    G = _load_graph()
    text = _prompt(G, "fix", monkeypatch)
    assert "The only command you may run is: python -m pytest" in text
    assert "hython" not in G.FIX_ALLOW


def test_the_taught_stub_imports_a_submodule_without_running_the_package_init(tmp_path):
    """Fails if the snippet the rule teaches would still execute synapse/__init__.py."""
    G = _load_graph()
    lines = [ln[4:] for ln in G.HYTHON_RULES.splitlines() if ln.startswith("    ")]
    assert lines, "HYTHON_RULES carries no indented stub snippet"
    pkg = tmp_path / "python" / "synapse"
    (pkg / "cv").mkdir(parents=True)
    (pkg / "__init__.py").write_text("raise SystemExit('synapse/__init__.py ran')\n", encoding="utf-8")
    (pkg / "cv" / "__init__.py").write_text("LOADED = 'cv'\n", encoding="utf-8")
    code = "\n".join(lines).replace("<worktree>", (tmp_path).as_posix())
    code += "\nprint(synapse.cv.LOADED)\n"
    r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True,
                       cwd=str(tmp_path), timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "cv"
    # control: the same package imported bare does run its __init__, so the probe can fail
    bare = "import sys; sys.path.insert(0, %r); import synapse.cv" % (tmp_path / "python").as_posix()
    c = subprocess.run([sys.executable, "-I", "-c", bare], capture_output=True, text=True,
                       cwd=str(tmp_path), timeout=60)
    assert c.returncode != 0 and "synapse/__init__.py ran" in (c.stdout + c.stderr)
