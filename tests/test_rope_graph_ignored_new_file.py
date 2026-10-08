"""A fix that creates a declared file under a gitignored path ships the whole card, or nothing.

Post-demo loop 1 lesson: `.synapse/` is gitignored ('/.synapse/') and its contracts are
force-tracked (`git add -f`, per .synapse/DO_NOT_FORCE_COPY.md). A card that split a contract
into a NEW .synapse/contracts/*.yaml plus a code edit was kept by the rope gate with only the
code edit: plain `git status` never shows an ignored new file, so the gate never saw it, never
copied it, never added it, and the commit shipped half the split while local tests stayed green.

Every repo here is a throwaway in tmp_path; no model is started. git runs with every GIT_*
variable removed, so no fixture can write into a shared .git.
"""
import importlib.util
import os
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(REPO, "harness", "rope", "graph.py")
NEW = ".synapse/contracts/demo-gate0-gui.yaml"
OLD = ".synapse/contracts/demo-gate0.yaml"


def _env():
    return {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, env=_env())


def _write(path, text):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A repo that ignores /.synapse/ and force-tracks one contract, plus one slot worktree."""
    for k in [k for k in os.environ if k.upper().startswith("GIT_")]:
        monkeypatch.delenv(k)                     # graph.git inherits os.environ
    repo = tmp_path / "repo"
    _write(repo / ".gitignore", "/.synapse/\n__pycache__/\n")
    _write(repo / "pkg" / "a.py", "VALUE = 'old'\n")
    _write(repo / OLD, "name: demo-gate0\nsteps: [gui, headless]\n")
    assert _git(repo, "init", "-q").returncode == 0
    assert _git(repo, "rev-parse", "--absolute-git-dir").stdout.strip().replace("\\", "/") \
        .startswith(str(tmp_path).replace("\\", "/")), "fixture repo must not resolve to a shared .git"
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "add", ".gitignore", "pkg/a.py")
    assert _git(repo, "add", "-f", OLD).returncode == 0
    _git(repo, "commit", "-q", "-m", "base")
    slot = tmp_path / "slots" / "s1"
    assert _git(repo, "worktree", "add", "-q", "--detach", str(slot), "HEAD").returncode == 0
    spec = importlib.util.spec_from_file_location("_rope_graph_ignored", GRAPH)
    G = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(G)
    G.ROOT = G.rope.ROOT = str(repo)
    run = tmp_path / "run"
    run.mkdir()
    st = {"version": "rope-graph/1", "root": str(repo), "run": str(run), "cap": 50, "sessions": 0,
          "minutes": 60, "started": None, "stop": "", "parallel": 6,
          "models": {"mechanical": "m", "reasoning": "r", "referee": "f"}, "trailer": "",
          "slots": [{"path": str(slot), "busy": "", "retired": ""}],
          "areas": {}, "items": []}
    return G, st, repo, slot


def _fix(st, slot, files, accept=()):
    it = {"id": "F01", "kind": "fix", "title": "split the gui gate", "files": files, "change": "- split",
          "deps": [], "status": "running", "attempts": 1, "accept": list(accept), "slot": str(slot)}
    st["items"].append(it)
    st["slots"][0]["busy"] = "F01"
    return it


def _split(slot):
    _write(slot / OLD, "name: demo-gate0\nsteps: [headless]\n")
    _write(slot / NEW, "name: demo-gate0-gui\nsteps: [gui]\n")
    _write(slot / "pkg" / "a.py", "VALUE = 'new'\n")


def _committed(repo):
    out = _git(repo, "show", "--name-only", "--format=", "HEAD").stdout
    return {ln.strip() for ln in out.splitlines() if ln.strip()}


def test_a_new_file_under_an_ignored_path_ships_in_the_same_commit(world):
    """Fails if the gate keeps the card while the new gitignored contract is left out of the commit."""
    G, st, repo, slot = world
    it = _fix(st, slot, ["pkg/a.py", OLD, NEW])
    _split(slot)
    verdict, note = G.gate(st, it)
    assert verdict == "kept", note
    assert _committed(repo) == {"pkg/a.py", OLD, NEW}
    assert _git(repo, "ls-files", "--error-unmatch", "--", NEW).returncode == 0
    assert _git(repo, "status", "--porcelain", "--ignored", "--", *it["files"]).stdout.strip() == ""


def test_the_slot_is_handed_back_without_the_ignored_leftover(world):
    """Fails if the worker's ignored new file survives in the slot for the next card to inherit."""
    G, st, repo, slot = world
    it = _fix(st, slot, ["pkg/a.py", OLD, NEW])
    _split(slot)
    assert G.gate(st, it)[0] == "kept"
    assert not (slot / NEW).exists()
    assert st["slots"][0]["retired"] == ""


def test_a_card_that_only_creates_an_ignored_file_is_not_no_change(world):
    """Fails if a card whose whole change is a new gitignored contract reads as 'worker changed nothing'."""
    G, st, repo, slot = world
    it = _fix(st, slot, [NEW], accept=[{"kind": "grep_min", "path": NEW, "pattern": "demo-gate0-gui"}])
    _write(slot / NEW, "name: demo-gate0-gui\nsteps: [gui]\n")
    verdict, note = G.gate(st, it)
    assert verdict == "kept", note
    assert _committed(repo) == {NEW}


def test_undeclared_ignored_files_are_still_out_of_view(world):
    """Fails if asking about ignored files widened the gate to caches the worker never declared."""
    G, st, repo, slot = world
    it = _fix(st, slot, ["pkg/a.py"])
    _write(slot / "pkg" / "a.py", "VALUE = 'new'\n")
    _write(slot / "pkg" / "__pycache__" / "a.cpython-313.pyc", "x")
    _write(slot / ".synapse" / "scratch.json", "{}")
    verdict, note = G.gate(st, it)
    assert verdict == "kept", note
    assert _committed(repo) == {"pkg/a.py"}
    assert _git(repo, "ls-files", "--", ".synapse/scratch.json").stdout.strip() == ""


def test_a_failed_check_removes_the_ignored_file_it_copied(world):
    """Fails if a discarded card leaves its new gitignored file behind in the root."""
    G, st, repo, slot = world
    it = _fix(st, slot, [NEW], accept=[{"kind": "grep_min", "path": NEW, "pattern": "never-there"}])
    _write(slot / NEW, "name: demo-gate0-gui\n")
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert G.gate(st, it)[0] == "fail"
    assert not (repo / NEW).exists()
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before
