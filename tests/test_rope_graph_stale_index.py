"""A kept fix that edits what the embeddings are built from says, out loud, that the index is stale.

RSI loop 1 lesson: editing rag/skills/houdini21-reference/*.md leaves
rag/semantic_index/manifest.json stale, and only the full gate
(harness/verify/checks.py::check_semantic_index_fresh) noticed. The rope graph merges a kept
fix in gate(); from now on that fix's note carries the refresh instruction, and the run's
status line batches every such lane into one refresh.

Every repo here is a throwaway in tmp_path; no model is started and no GIT_* variable is set.
"""
import hashlib
import importlib.util
import json
import os
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(REPO, "harness", "rope", "graph.py")
CHECKS = os.path.join(REPO, "harness", "verify", "checks.py")
MSG = "semantic index stale: run scripts/refresh_knowledge.py"
SKILL = "rag/skills/houdini21-reference/lops.md"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def _write(path, text):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


@pytest.fixture
def world(tmp_path):
    """A repo with one module and one reference page, and one slot worktree."""
    repo = tmp_path / "repo"
    _write(repo / "pkg" / "a.py", "VALUE = 'broken'\n")
    _write(repo / SKILL, "# LOPs\nold text\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    slot = tmp_path / "slots" / "s1"
    assert _git(repo, "worktree", "add", "-q", "--detach", str(slot), "HEAD").returncode == 0
    G = _load("_rope_graph_stale", GRAPH)
    G.ROOT = G.rope.ROOT = str(repo)
    run = tmp_path / "run"
    run.mkdir()
    st = {"version": "rope-graph/1", "root": str(repo), "run": str(run), "cap": 50, "sessions": 0,
          "minutes": 60, "started": None, "stop": "", "parallel": 6,
          "models": {"mechanical": "m", "reasoning": "r", "referee": "f"}, "trailer": "",
          "slots": [{"path": str(slot), "busy": "", "retired": ""}],
          "areas": {"pkg": {"blast": 0, "files": [["pkg/a.py", 1]]}}, "items": []}
    return G, st, repo, slot


def _fix(st, slot, iid, files, accept):
    it = {"id": iid, "kind": "fix", "title": "edit " + files[0], "files": files, "change": "- edit",
          "deps": [], "status": "running", "attempts": 1, "accept": accept, "slot": str(slot)}
    st["items"].append(it)
    st["slots"][0]["busy"] = iid
    return it


def _keep_skill_fix(G, st, slot, iid="F01"):
    it = _fix(st, slot, iid, [SKILL], [{"kind": "grep_min", "path": SKILL, "pattern": "new text"}])
    _write(slot / SKILL, "# LOPs\nnew text\n")
    verdict, note = G.gate(st, it)
    assert verdict == "kept", note
    it["status"], it["note"] = "kept", note
    return it, note


def test_a_kept_fix_on_a_reference_page_records_the_refresh_in_its_result(world):
    """Fails if a merged rag/skills edit is kept without naming the stale index and its refresh."""
    G, st, repo, slot = world
    it, note = _keep_skill_fix(G, st, slot)
    assert MSG in note
    assert it.get("stale_index") is True
    line = G.status_line(st)
    assert MSG in line and "F01" in line


def test_the_status_line_batches_every_stale_lane_into_one_refresh(world):
    """Fails if two stale lanes produce two refresh steps, or a lane is left out of the batch."""
    G, st, repo, slot = world
    _keep_skill_fix(G, st, slot, "F01")
    it = _fix(st, slot, "F02", [SKILL], [{"kind": "grep_min", "path": SKILL, "pattern": "newer"}])
    _write(slot / SKILL, "# LOPs\nnewer text\n")
    assert G.gate(st, it)[0] == "kept"
    it["status"] = "kept"
    line = G.status_line(st)
    assert line.count(MSG) == 1
    assert "(F01, F02)" in line


def test_a_kept_fix_elsewhere_says_nothing_about_the_index(world):
    """Fails if the flag fires on a lane that never touched what the embeddings read."""
    G, st, repo, slot = world
    it = _fix(st, slot, "F01", ["pkg/a.py"], [{"kind": "grep_min", "path": "pkg/a.py", "pattern": "fixed"}])
    _write(slot / "pkg" / "a.py", "VALUE = 'fixed'\n")
    verdict, note = G.gate(st, it)
    assert verdict == "kept", note
    it["status"] = "kept"
    assert MSG not in note and not it.get("stale_index")
    assert MSG not in G.status_line(st)


def test_a_discarded_or_dropped_lane_is_not_counted(world):
    """Fails if a lane whose edit never landed, or was reverted by the referee, still asks for a refresh."""
    G, st, repo, slot = world
    it = _fix(st, slot, "F01", [SKILL], [{"kind": "grep_min", "path": SKILL, "pattern": "never there"}])
    _write(slot / SKILL, "# LOPs\nnew text\n")
    verdict, note = G.gate(st, it)
    assert verdict == "fail" and MSG not in note and not it.get("stale_index")
    st["items"].clear()
    st["slots"][0]["busy"] = ""
    it, _ = _keep_skill_fix(G, st, slot, "F02")
    it["status"] = "dropped"
    assert MSG not in G.status_line(st)


# The predicate must agree with the gate that owns the truth, not with a memory of it.
PATHS = [
    "rag/skills/houdini21-reference/new_page.md",
    "rag/skills/houdini21-reference/sub/nested.md",
    "rag/skills/houdini21-reference/notes.txt",
    "rag/skills/other-skill/page.md",
    "rag/documentation/_metadata/semantic_index.json",
    "rag/documentation/_metadata/other.json",
    "pkg/a.py",
]


def _empty_digest():
    """The digest of a tree with no embedded inputs, by the formula checks.py documents."""
    return hashlib.blake2b(b"", digest_size=16).hexdigest()


@pytest.mark.parametrize("rel", PATHS)
def test_the_predicate_matches_check_semantic_index_fresh(rel, tmp_path):
    """Fails if graph.py flags a path the freshness gate ignores, or misses one it reads."""
    G = _load("_rope_graph_stale_pred", GRAPH)
    C = _load("_verify_checks_stale_pred", CHECKS)
    wt = tmp_path / "wt"
    _write(wt / "rag" / "semantic_index" / "manifest.json",
           json.dumps({"content_digest": _empty_digest(), "entries": 0}))
    assert C.check_semantic_index_fresh({"wt": str(wt)})["ok"] is True
    _write(wt / rel, "{}\n")
    gate_says_stale = not C.check_semantic_index_fresh({"wt": str(wt)})["ok"]
    assert G.stales_index(rel) is gate_says_stale
