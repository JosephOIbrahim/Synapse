"""RSI-2: a fix's new test path never collides with a test an earlier run committed.

Hour 2's seeds reused hour 1's ids. route() named the new test from the id alone
(SEED-2 -> tests/test_graph_seed_2.py), that file was already committed, and
refuse_item turned 3 of 6 items away as "an existing test is the exam".
The path is now tagged with the run folder's name and walks a numeric suffix until
it is free in git and on disk. Code decides; no model is asked.

These tests reuse the throwaway `world` repo from tests/test_rope_graph.py.
"""
import importlib.util
import json
import os
import sys

_spec = importlib.util.spec_from_file_location(
    "_rope_graph_tests_rsi2", os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_rope_graph.py"))
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
_git, _write, REPO = _base._git, _base._write, _base.REPO
world = _base.world  # the fixture, re-exported so pytest finds it here

SEED = {"file": "pkg/a.py", "line": 1, "claim": "value is broken", "evidence": "VALUE = 'broken'",
        "fix": "f", "check": "c"}


def _route_one(G, st, monkeypatch):
    """route() over one SEED-1 candidate that Jev (faked) sends to fix_now."""
    sys.path.insert(0, os.path.join(REPO, "harness", "jev"))
    import jev_sweep

    def fake(cands, wave, workers=4):
        for c in cands:
            c["decision"] = {"route": "fix_now", "tier": "mechanical", "priority": 0.9,
                             "reason": "test", "jev": {}}
    monkeypatch.setattr(jev_sweep, "resolve_many", fake)
    _write(os.path.join(st["run"], "seeds.json"), json.dumps([SEED]))
    cands, items = G.route(st)
    assert len(items) == 1 and items[0]["from"] == ["SEED-1"]
    return items[0]


def _commit(repo, rel, msg):
    _write(repo / rel, "def test_earlier_run():\n    assert True\n")
    _git(repo, "add", rel)
    assert _git(repo, "commit", "-q", "-m", msg).returncode == 0


def test_an_earlier_run_s_committed_seed_test_does_not_refuse_the_item(world, monkeypatch):
    """The hour-2 shape. Fails on the id-only name, which is exactly the committed file."""
    G, st, repo, slot = world
    _commit(repo, "tests/test_graph_seed_1.py", "hour 1 kept SEED-1")
    it = _route_one(G, st, monkeypatch)
    new_test = it["files"][1]
    assert new_test.startswith("tests/test_graph_") and new_test != "tests/test_graph_seed_1.py"
    assert not os.path.exists(str(repo / new_test))
    assert it["accept"][0] == {"kind": "exists", "path": new_test}
    assert G.refuse_item(st, it) == ""


def test_a_second_route_after_the_first_run_s_test_is_committed_picks_a_free_path(world, monkeypatch):
    """Same run folder, same seed id, the first test already kept: the suffix walks on."""
    G, st, repo, slot = world
    first = _route_one(G, st, monkeypatch)["files"][1]
    _commit(repo, first, "first run kept its test")
    second = _route_one(G, st, monkeypatch)
    assert second["files"][1] != first
    assert G.refuse_item(st, second) == ""


def test_an_untracked_leftover_on_disk_is_not_handed_out(world):
    """A leftover file would let the `exists` acceptance pass with nothing written."""
    G, st, repo, slot = world
    taken = G.new_test_path(st, "SEED-1")
    _write(repo / taken, "# left over\n")
    again = G.new_test_path(st, "SEED-1")
    assert again != taken and not os.path.exists(str(repo / again))
    assert G.new_test_path(st, "SEED-1", claimed={again}) not in (taken, again)
