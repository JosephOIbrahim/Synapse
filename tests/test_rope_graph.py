"""The rope graph must keep its three laws when nobody is watching.

    1. The cap is counted here and nowhere else, before a session starts.
    2. A fix may only declare files outside the fences and outside the exam.
    3. The loop never edits its own exam; keep or discard is decided by checks.

Every test builds a throwaway git repo in tmp_path and never touches the real
tree. No model is started: `spawn` is replaced, and a "session" is whatever the
test writes into the slot worktree or the run folder.
"""
import importlib.util
import json
import os
import subprocess
import sys
import time

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(REPO, "harness", "rope", "graph.py")


def _load_graph():
    spec = importlib.util.spec_from_file_location("_rope_graph", GRAPH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _write(path, text):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _read(path):
    with open(str(path), encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def world(tmp_path):
    """A repo with one module, one existing test, one bystander, and one slot worktree."""
    repo = tmp_path / "repo"
    _write(repo / "pkg" / "a.py", "VALUE = 'broken'\n")
    _write(repo / "tests" / "test_old.py", "def test_old():\n    assert True\n")
    _write(repo / "bystander.txt", "not yours\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    slot = tmp_path / "slots" / "s1"
    assert _git(repo, "worktree", "add", "-q", "--detach", str(slot), "HEAD").returncode == 0
    G = _load_graph()
    G.ROOT = G.rope.ROOT = str(repo)
    run = tmp_path / "run"
    run.mkdir()
    st = {"version": "rope-graph/1", "root": str(repo), "run": str(run), "cap": 50, "sessions": 0,
          "minutes": 60, "started": None, "stop": "", "parallel": 6,
          "models": {"mechanical": "m", "reasoning": "r", "referee": "f"}, "trailer": "",
          "slots": [{"path": str(slot), "busy": "", "retired": ""}],
          "areas": {"pkg": {"blast": 0, "files": [["pkg/a.py", 1]]}}, "items": []}
    return G, st, repo, slot


def _scouts(n):
    return [{"id": "S%02d" % i, "kind": "scout", "title": "scout pkg", "areas": ["pkg"],
             "files": ["pkg/a.py"], "lines": 1, "deps": [], "status": "pending", "attempts": 0}
            for i in range(1, n + 1)]


def _fix(st, slot, **kw):
    it = {"id": "F01", "kind": "fix", "title": "set the value", "files": ["pkg/a.py", "tests/test_new.py"],
          "change": "- make VALUE fixed", "deps": [], "status": "running", "attempts": 1,
          "accept": [{"kind": "grep_min", "path": "pkg/a.py", "pattern": "fixed"}],
          "slot": str(slot)}
    it.update(kw)
    st["items"].append(it)
    st["slots"][0]["busy"] = it["id"]
    return it


def _head(repo):
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


# ------------------------------------------------------------------ law 1: cap

def test_the_cap_is_counted_before_a_session_starts(world, monkeypatch):
    """Fails if the count moves after spawn, or if a third session starts under a cap of two."""
    G, st, repo, slot = world
    st["cap"], st["items"] = 2, _scouts(3)
    started = []
    monkeypatch.setattr(G, "spawn", lambda s, it: started.append((it["id"], s["sessions"])))
    G.tick(st, ("scout",), 6)
    assert started == [("S01", 1), ("S02", 2)]
    assert "cap reached" in G.refuse_session(st)
    assert G.by_id(st, "S03")["status"] == "pending"
    G.tick(st, ("scout",), 6)
    assert len(started) == 2 and st["sessions"] == 2


def test_the_clock_stops_new_sessions(world, monkeypatch):
    """Fails if a session may start after the run's minutes are spent."""
    G, st, repo, slot = world
    st["items"], st["started"] = _scouts(2), time.time() - 61 * 60
    started = []
    monkeypatch.setattr(G, "spawn", lambda s, it: started.append(it["id"]))
    G.tick(st, ("scout",), 6)
    assert started == [] and "clock ran out" in G.refuse_session(st)


def test_parallel_limits_how_many_run_at_once(world, monkeypatch):
    G, st, repo, slot = world
    st["items"] = _scouts(3)
    started = []
    monkeypatch.setattr(G, "spawn", lambda s, it: started.append(it["id"]))
    assert G.tick(st, ("scout",), 2) == 2
    assert started == ["S01", "S02"]


def test_a_usage_limit_stops_the_loop_and_is_never_retried(world, monkeypatch):
    """Fails if the loop starts another session after one reports a usage limit."""
    G, st, repo, slot = world
    st["items"] = _scouts(2)
    st["items"][0].update(status="running", attempts=1, launched=time.time())
    st["sessions"] = 1
    _write(os.path.join(st["run"], "S01.exit"), json.dumps({"rc": 1, "dur": 3, "note": ""}))
    _write(os.path.join(st["run"], "S01.out"),
           json.dumps({"is_error": True, "result": "Claude usage limit reached. Resets at 5pm."}))
    started = []
    monkeypatch.setattr(G, "spawn", lambda s, it: started.append(it["id"]))
    G.tick(st, ("scout",), 6)
    assert st["stop"].startswith("quota") and started == []
    assert G.by_id(st, "S01")["status"] == "pending"
    assert "quota-pause" in _read(os.path.join(st["run"], "results.tsv"))


def test_a_scout_reply_is_kept_as_data(world, monkeypatch):
    G, st, repo, slot = world
    st["items"] = _scouts(1)
    st["items"][0].update(status="running", attempts=1, launched=time.time())
    reply = 'Here you go.\n```json\n{"scout": "S01", "candidates": [{"file": "pkg/a.py", "line": 1}]}\n```'
    _write(os.path.join(st["run"], "S01.exit"), json.dumps({"rc": 0, "dur": 9, "note": ""}))
    _write(os.path.join(st["run"], "S01.out"),
           json.dumps({"is_error": False, "result": reply, "usage": {"input_tokens": 10, "output_tokens": 5}}))
    monkeypatch.setattr(G, "spawn", lambda s, it: None)
    G.tick(st, ("scout",), 6)
    assert G.by_id(st, "S01")["status"] == "done"
    assert json.loads(_read(os.path.join(st["run"], "S01.result.json")))["candidates"][0]["line"] == 1
    assert "\t15\t" in _read(os.path.join(st["run"], "results.tsv"))


# --------------------------------------------------------------- law 2: fences

def test_a_fix_may_not_declare_the_fences_the_exam_or_another_fix_s_file(world):
    """Fails if any of these reach a fixer: the refusal is code, not a model's opinion."""
    G, st, repo, slot = world
    ok = {"id": "F01", "kind": "fix", "files": ["pkg/a.py", "tests/test_new.py"], "status": "pending"}
    assert G.refuse_item(st, ok) == ""
    bad = {
        "python/synapse/server/handlers_tops/x.py": "fenced",
        "python/synapse/_vendor/y.py": "fenced",
        "harness/rope/graph.py": "the exam",
        "tests/fixtures/base.json": "the exam",
        "rag/catalog/h22/Lop.json": "the exam",
        "tests/test_old.py": "existing test",
        "VERSION": "owner-only",
        ".claude/settings.json": "owner-only",
        "../outside.py": "leaves the tree",
        "C:/Users/x.py": "leaves the tree",
    }
    for path, why in bad.items():
        assert why in G.refuse_item(st, {"id": "F09", "kind": "fix", "files": [path]}), path
    assert "declares no files" in G.refuse_item(st, {"id": "F09", "kind": "fix", "files": []})
    st["items"].append(ok)
    assert "already owned by F01" in G.refuse_item(st, {"id": "F02", "kind": "fix", "files": ["pkg/a.py"]})
    refused = G.add_items(st, [{"id": "F02", "kind": "fix", "files": ["pkg/a.py"]},
                               {"id": "F03", "kind": "fix", "files": ["pkg/b.py"]}])
    assert [r[0] for r in refused] == ["F02"]
    assert [i["id"] for i in st["items"]] == ["F01", "F03"]


# ----------------------------------------------------------------- law 3: gate

def test_the_gate_keeps_a_scoped_change_as_one_commit(world):
    """Fails if the commit carries anything the card did not declare, or the slot is left dirty."""
    G, st, repo, slot = world
    it = _fix(st, slot)
    _write(slot / "pkg" / "a.py", "VALUE = 'fixed'\n")
    _write(slot / "tests" / "test_new.py", "def test_new():\n    assert True\n")
    before = _head(repo)
    verdict, note = G.gate(st, it)
    assert verdict == "kept", note
    show = _git(repo, "show", "--name-only", "--format=%s", "HEAD").stdout.split("\n")
    assert show[0] == "rope:F01 set the value [sweep]"
    assert sorted(x for x in show[1:] if x) == ["pkg/a.py", "tests/test_new.py"]
    assert _git(repo, "rev-parse", "HEAD~1").stdout.strip() == before
    assert _read(repo / "bystander.txt") == "not yours\n"
    assert _git(slot, "status", "--porcelain").stdout.strip() == ""
    assert st["slots"][0] == {"path": str(slot), "busy": "", "retired": ""}


def test_the_gate_discards_and_restores_when_a_check_fails(world):
    """Fails if a failed fix leaves a single byte in the integration tree."""
    G, st, repo, slot = world
    it = _fix(st, slot, accept=[{"kind": "grep_min", "path": "pkg/a.py", "pattern": "never there"}])
    _write(slot / "pkg" / "a.py", "VALUE = 'fixed'\n")
    _write(slot / "tests" / "test_new.py", "def test_new():\n    assert True\n")
    before = _head(repo)
    verdict, note = G.gate(st, it)
    assert verdict == "fail" and "grep_min" in note
    assert _head(repo) == before
    assert _read(repo / "pkg" / "a.py") == "VALUE = 'broken'\n"
    assert not os.path.exists(str(repo / "tests" / "test_new.py"))
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""


def test_the_gate_refuses_a_stray_edit_without_copying_anything(world):
    """Fails if a worker that wandered outside its card gets any of its work into the tree."""
    G, st, repo, slot = world
    it = _fix(st, slot)
    _write(slot / "pkg" / "a.py", "VALUE = 'fixed'\n")
    _write(slot / "bystander.txt", "mine now\n")
    verdict, note = G.gate(st, it)
    assert verdict == "stray" and "bystander.txt" in note
    assert _read(repo / "pkg" / "a.py") == "VALUE = 'broken'\n"
    assert _read(repo / "bystander.txt") == "not yours\n"
    assert _git(slot, "status", "--porcelain").stdout.strip() == ""
    assert st["slots"][0]["retired"] == ""


def test_the_gate_refuses_deletions_broken_python_and_empty_work(world):
    G, st, repo, slot = world
    it = _fix(st, slot)
    assert G.gate(st, it)[0] == "no_change"
    st["slots"][0]["busy"] = "F01"
    _write(slot / "pkg" / "a.py", "VALUE = (\n")
    assert G.gate(st, it)[0] == "syntax"
    st["slots"][0]["busy"] = "F01"
    os.remove(str(slot / "pkg" / "a.py"))
    assert G.gate(st, it)[0] == "deletion"
    assert _read(repo / "pkg" / "a.py") == "VALUE = 'broken'\n"
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""


def test_a_referee_drop_reverts_the_commit_without_rewriting_history(world, monkeypatch):
    """Fails if a drop deletes history instead of adding a revert, or leaves the fix in place."""
    G, st, repo, slot = world
    it = _fix(st, slot, files=["pkg/a.py"])
    _write(slot / "pkg" / "a.py", "VALUE = 'fixed'\n")
    assert G.gate(st, it)[0] == "kept"
    it["status"] = "kept"
    kept = _head(repo)
    assert [r["id"] for r in G.add_reviews(st)] == ["R01"]
    assert G.add_reviews(st) == []                      # a commit is refereed once
    assert "set the value" in G.build_prompt(st, G.by_id(st, "R01"))
    G.by_id(st, "R01").update(status="running", attempts=1, launched=time.time())
    _write(os.path.join(st["run"], "R01.exit"), json.dumps({"rc": 0, "dur": 5, "note": ""}))
    _write(os.path.join(st["run"], "R01.out"), json.dumps({"is_error": False, "result": json.dumps(
        {"verdicts": [{"id": "F01", "verdict": "drop", "why": "does more than the card"}]})}))
    monkeypatch.setattr(G, "spawn", lambda s, i: None)
    G.tick(st, ("review",), 6)
    assert G.by_id(st, "F01")["status"] == "dropped"
    assert _read(repo / "pkg" / "a.py") == "VALUE = 'broken'\n"
    assert _git(repo, "rev-parse", "HEAD~1").stdout.strip() == kept


# ---------------------------------------------------------------- the two graphs

def test_the_code_graph_knows_who_imports_whom_and_skips_the_fences(world):
    """Fails if reach is miscounted: reach is what orders the work and raises the tier."""
    G, st, repo, slot = world
    base = repo / "python" / "synapse"
    _write(base / "__init__.py", "")
    _write(base / "core" / "__init__.py", "X = 1\n")
    _write(base / "server" / "h.py", "from ..core import X\nimport synapse.core\n")
    _write(base / "server" / "handlers_tops" / "t.py", "from ..panel import p\n")
    _write(base / "panel" / "p.py", "from synapse.server import h\nfrom synapse import core\n")
    _write(repo / "mcp_server.py", "import synapse.panel.p\n")
    g = G.code_graph()
    assert "handlers_tops" not in g and all("handlers_tops" not in f for f, _ in g["server"]["files"])
    assert g["server"]["imports"] == ["core"] and g["panel"]["imports"] == ["core", "server"]
    assert g["mcp_stdio"]["imports"] == ["panel"]
    assert (g["core"]["blast"], g["server"]["blast"], g["panel"]["blast"], g["mcp_stdio"]["blast"]) == (3, 2, 1, 0)
    items = G.plan_scouts(g, 2)
    assert [f for i in items for f in i["files"]].count("python/synapse/core/__init__.py") == 1
    assert (g["core"]["direct"], g["server"]["direct"], g["panel"]["direct"]) == (2, 1, 1)
    order = [a for i in items for a in i["areas"]]
    assert g[order[0]]["direct"] == 0 and order[-1] == "core"    # fewest importers first, most last


def test_the_veto_checks_the_quoted_line_against_the_file(world):
    """Fails if a candidate whose evidence is not in the file can reach a fixer."""
    G, st, repo, slot = world
    good = {"file": "pkg/a.py", "line": 1, "evidence": "VALUE = 'broken'"}
    assert G.veto(good) == ""
    moved = {"file": "pkg/a.py", "line": 40, "evidence": "VALUE   =   'broken'"}
    assert G.veto(moved) == "" and moved["line"] == 1
    assert G.veto({"file": "pkg/a.py", "line": 1, "evidence": "VALUE = 'fine'"}) == "evidence not found in the file"
    assert G.veto({"file": "pkg/nope.py", "line": 1, "evidence": "VALUE = 1"}) == "no such file"
    assert G.veto({"file": "tests/test_old.py", "line": 1, "evidence": "def test_old():"}) == "the exam is read-only"


def test_route_groups_by_file_and_only_fix_now_becomes_an_item(world, monkeypatch):
    """Fails if a vetoed or proposed candidate becomes a fix item, or two items share a file."""
    G, st, repo, slot = world
    sys.path.insert(0, os.path.join(REPO, "harness", "jev"))
    import jev_sweep

    def fake(cands, wave, workers=4):
        for c in cands:
            keep = "broken" in c["evidence"]
            c["decision"] = {"route": "fix_now" if keep else "propose_only", "tier": "mechanical",
                             "priority": 0.9 if c["line"] == 1 else 0.5, "reason": "test", "jev": {}}
    monkeypatch.setattr(jev_sweep, "resolve_many", fake)
    _write(repo / "pkg" / "b.py", "OTHER = 2\n")
    _write(os.path.join(st["run"], "seeds.json"), json.dumps([
        {"file": "pkg/a.py", "line": 1, "claim": "value is broken", "evidence": "VALUE = 'broken'", "fix": "f", "check": "c"},
        {"file": "pkg/a.py", "line": 1, "claim": "second on the same file", "evidence": "VALUE = 'broken'", "fix": "f", "check": "c"},
        {"file": "pkg/b.py", "line": 1, "claim": "taste", "evidence": "OTHER = 2", "fix": "f", "check": "c"},
        {"file": "pkg/a.py", "line": 1, "claim": "made up", "evidence": "NOT IN THE FILE", "fix": "f", "check": "c"}]))
    cands, items = G.route(st)
    assert [c["decision"]["route"] for c in cands] == ["fix_now", "fix_now", "propose_only", "vetoed"]
    assert len(items) == 1 and items[0]["id"] == "F01" and items[0]["from"] == ["SEED-1", "SEED-2"]
    assert items[0]["files"][0] == "pkg/a.py" and items[0]["files"][1].startswith("tests/test_graph_")
    assert G.refuse_item(st, items[0]) == ""
    assert items[0]["accept"][0] == {"kind": "exists", "path": items[0]["files"][1]}


def test_json_in_finds_the_reply_object():
    G = _load_graph()
    assert G.json_in('note {"a": 1} tail') == {"a": 1}
    assert G.json_in('```json\n{"a": {"b": [1, 2]}}\n```\nDONE') == {"a": {"b": [1, 2]}}
    assert G.json_in("no json here") is None


def test_a_scout_knows_its_turn_budget_and_may_carry_a_brief(world):
    """Fails if a scout is not told when to stop reading: 3 of 20 ran out of turns on 2026-10-06."""
    G, st, repo, slot = world
    it = _scouts(1)[0]
    plain = G.build_prompt(st, it)
    assert "about %d tool calls" % G.TURNS["scout"] in plain and "YOUR BRIEF" not in plain
    it["brief"] = "Only tooltips."
    aimed = G.build_prompt(st, it)
    assert "YOUR BRIEF" in aimed and "Only tooltips." in aimed
