"""RSI-3: every fix is also judged by the composed gates, not only by tests that name its module.

Hour 3 kept a fix that broke tests/test_d_track.py, and a fix can add a silent broad
except without any judging test noticing, because tests_for only finds tests by module
name. The ratchets are now four: catalog conformance, recipe-string conformance, the
D-track TOPs quarantine, and the broad-except ratchet. route() prepends every ratchet
that exists in the root to each fix item's pytest acceptance. Code decides; no model is asked.

These tests reuse the throwaway `world` repo from tests/test_rope_graph.py.
"""
import importlib.util
import json
import os
import sys

_spec = importlib.util.spec_from_file_location(
    "_rope_graph_tests_rsi3", os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_rope_graph.py"))
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
_write, REPO, _load_graph = _base._write, _base.REPO, _base._load_graph
world = _base.world  # the fixture, re-exported so pytest finds it here

OLD = ("tests/test_harden_catalog_conformance.py", "tests/test_b4_recipe_strings_conformance.py")
NEW = ("tests/test_d_track.py", "tests/test_except_ratchet.py")
SEED = {"file": "pkg/a.py", "line": 1, "claim": "value is broken", "evidence": "VALUE = 'broken'",
        "fix": "f", "check": "c"}


def _plant(repo, paths):
    # No word "a" in the body, so tests_for("pkg/a.py") never picks a ratchet as a judging test.
    for p in paths:
        _write(repo / p, "def test_ok():\n    assert True\n")


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


def _ratchet_args(item):
    """The pytest accept entry that is not the item's own new test."""
    new_test = item["files"][1]
    runs = [a["args"].split() for a in item["accept"]
            if a["kind"] == "pytest" and not a["args"].startswith(new_test)]
    assert len(runs) == 1, item["accept"]
    return runs[0]


def test_ratchets_include_the_composed_gates():
    """Fails if the D-track quarantine or the broad-except ratchet is not a ratchet."""
    G = _load_graph()
    assert "tests/test_d_track.py" in G.RATCHETS
    assert "tests/test_except_ratchet.py" in G.RATCHETS
    for t in OLD:
        assert t in G.RATCHETS


def test_route_acceptance_runs_the_composed_gates(world, monkeypatch):
    """Fails if a fix item's pytest acceptance does not run both composed gates ahead of its judging tests."""
    G, st, repo, slot = world
    _plant(repo, OLD + NEW)
    _write(repo / "tests" / "test_uses_a.py", "from pkg import a\n\n\ndef test_uses_a():\n    assert a.VALUE\n")
    item = _route_one(G, st, monkeypatch)
    args = _ratchet_args(item)
    for t in OLD + NEW:
        assert t in args, args
    assert "tests/test_uses_a.py" in args, args
    judge = args.index("tests/test_uses_a.py")
    assert args.index("tests/test_d_track.py") < judge
    assert args.index("tests/test_except_ratchet.py") < judge


def test_a_missing_ratchet_file_is_skipped_not_fatal(world, monkeypatch):
    """Regression guard (passes before and after RSI-3): a ratchet absent from the root is dropped, not run."""
    G, st, repo, slot = world
    _plant(repo, OLD)
    item = _route_one(G, st, monkeypatch)
    args = _ratchet_args(item)
    for t in OLD:
        assert t in args, args
    for t in NEW:
        assert t not in args, args
