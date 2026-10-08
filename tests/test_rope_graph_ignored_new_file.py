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
    _write(repo / ".gitignore", "/.synapse/\n__pycache__/\ndemo/.synapse/\n")
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


def test_force_add_only_follows_a_force_tracked_directory(world):
    """Fails if `add -f` would track a new file in an ignored directory nothing is tracked from.

    demo/.synapse/ is a memory store that must never be tracked (origin is public); a card that
    declares a file there is the owner's call, and the gate says so without copying anything.
    """
    G, st, repo, slot = world
    store = "demo/.synapse/memory.json"
    it = _fix(st, slot, ["pkg/a.py", store])
    _write(slot / "pkg" / "a.py", "VALUE = 'new'\n")
    _write(slot / store, "{}")
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    verdict, note = G.gate(st, it)
    assert verdict == "ignored", note
    assert store in note
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before
    assert not (repo / store).exists()
    assert not (slot / store).exists()


def test_a_failed_check_removes_the_ignored_file_it_copied(world):
    """Fails if a discarded card leaves its new gitignored file behind in the root."""
    G, st, repo, slot = world
    it = _fix(st, slot, [NEW], accept=[{"kind": "grep_min", "path": NEW, "pattern": "never-there"}])
    _write(slot / NEW, "name: demo-gate0-gui\n")
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert G.gate(st, it)[0] == "fail"
    assert not (repo / NEW).exists()
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before


def _exclude(repo, *patterns):
    """Ignore more names through the shared info/exclude, the way the real .gitignore ignores
    .env, *.key and *.log; every worktree of the fixture repo reads it."""
    info = _git(repo, "rev-parse", "--git-common-dir").stdout.strip()
    path = os.path.join(str(repo), info) if not os.path.isabs(info) else info
    with open(os.path.join(path, "info", "exclude"), "a", encoding="utf-8", newline="\n") as f:
        f.write("".join(p + "\n" for p in patterns))


def test_force_add_needs_a_force_tracked_sibling_in_the_same_directory(world):
    """Fails if `add -f` would track a secret-like ignored file just because something is tracked nearby.

    Four declared ignored files, none with precedent: one at the repo root (`ls-files -- .` is never
    empty), one beside a tracked file that is not itself ignored (pkg/a.py licenses nothing), one
    with a log extension, and one in .synapse/ whose only force-tracked file lives a level down in
    contracts/. The whole card is refused, nothing is copied, and the slot is handed back clean.
    """
    G, st, repo, slot = world
    _exclude(repo, ".env", "*.key", "*.log")
    secrets = [".env", "pkg/secret.key", "pkg/run.log", ".synapse/memory.json"]
    it = _fix(st, slot, ["pkg/a.py", *secrets])
    _write(slot / "pkg" / "a.py", "VALUE = 'new'\n")
    for rel in secrets:
        _write(slot / rel, "token=abc\n")
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    verdict, note = G.gate(st, it)
    assert verdict == "ignored", note
    for rel in secrets:
        assert rel in note
        assert not (repo / rel).exists()
        assert not (slot / rel).exists()
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before
    assert _git(repo, "ls-files", "--", *secrets).stdout.strip() == ""


def test_the_force_tracked_directory_is_still_a_precedent_beside_a_refused_file(world):
    """Fails if the precedent rule refuses .synapse/contracts/ itself (the loop-1 split must still ship),
    or names it as the offender when a root-level secret in the same card is what got refused."""
    G, st, repo, slot = world
    _exclude(repo, ".env")
    it = _fix(st, slot, [NEW, ".env"])
    _write(slot / NEW, "name: demo-gate0-gui\n")
    _write(slot / ".env", "token=abc\n")
    verdict, note = G.gate(st, it)
    assert verdict == "ignored", note
    assert ".env" in note and NEW not in note
    assert G._force_tracked_dir(str(slot), NEW)
    assert not G._force_tracked_dir(str(slot), ".env")
    assert not G._force_tracked_dir(str(slot), "pkg/secret.key")


def test_a_log_line_moved_into_a_new_ignored_file_is_not_dropped(world):
    """Fails if a logger call moved INTO a new gitignored file reads as dropped_log.

    A new ignored file has no HEAD side: every line in it is an added line, exactly as for an
    untracked one. Read through `git diff HEAD` instead, it shows nothing and the move is lost.
    """
    G, st, repo, slot = world
    line = 'log.info("gate split loaded")'
    _write(repo / "pkg" / "a.py", "import logging\nlog = logging.getLogger(__name__)\nVALUE = 'old'\n%s\n" % line)
    _git(repo, "add", "pkg/a.py")
    assert _git(repo, "commit", "-q", "-m", "log").returncode == 0
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert _git(slot, "checkout", "-q", "--detach", head).returncode == 0
    it = _fix(st, slot, ["pkg/a.py", NEW])
    _write(slot / "pkg" / "a.py", "import logging\nlog = logging.getLogger(__name__)\nVALUE = 'new'\n")
    _write(slot / NEW, "name: demo-gate0-gui\n%s\n" % line)
    verdict, note = G.gate(st, it)
    assert verdict == "kept", note
    assert _committed(repo) == {"pkg/a.py", NEW}


@pytest.mark.parametrize("pattern", ["never-there", "demo-gate0-gui"], ids=["failing", "passing"])
def test_an_untracked_ignored_file_already_in_the_root_is_never_overwritten(world, pattern):
    """Fails if the gate copies a declared ignored path over a file the root already holds untracked.

    rope.revert cannot restore it (git has no copy; `existed` only says it was there), and a keep
    would force-commit the overwrite. So the card is refused before any copy, whether its checks
    would have failed or passed, and the root's own draft stays byte-for-byte and untracked.
    """
    G, st, repo, slot = world
    draft = "name: demo-gate0-gui\nowner: local draft, not in git\n"
    _write(repo / NEW, draft)
    assert _git(repo, "status", "--porcelain", "--ignored", "--", NEW).stdout.startswith("!! ")
    it = _fix(st, slot, [NEW], accept=[{"kind": "grep_min", "path": NEW, "pattern": pattern}])
    _write(slot / NEW, "name: demo-gate0-gui\nsteps: [gui]\n")
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    verdict, note = G.gate(st, it)
    assert verdict == "ignored", note
    assert NEW in note
    with open(str(repo / NEW), encoding="utf-8", newline="") as f:
        assert f.read() == draft
    assert _git(repo, "ls-files", "--error-unmatch", "--", NEW).returncode != 0
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before
    assert not (slot / NEW).exists()
    assert st["slots"][0]["retired"] == ""
