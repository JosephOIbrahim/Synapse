"""H-PREFLIGHT: no fixer starts while the ratchets are red on the base tree.

Every fix item's acceptance runs the four ratchets in the root. When one of them is
already red before any fixer touches the tree (a cto run hit this: a stale local master
ref turned tests/test_d_track.py red), every fix is discarded and the ledger never says
why. graph.py now runs the ratchets once against the base tree before the first fixer,
holds every fix item while they are red, names each failing test in the ledger and the
status line, and still lets read-only scouts and referees run. Code decides; no model.

These tests reuse the throwaway `world` repo from tests/test_rope_graph.py.
"""
import argparse
import importlib.util
import json
import os
import subprocess

import pytest

_spec = importlib.util.spec_from_file_location(
    "_rope_graph_tests_preflight",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_rope_graph.py"))
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
_write, _read, _scouts = _base._write, _base._read, _base._scouts
world = _base.world  # the fixture, re-exported so pytest finds it here

RED = "def test_red():\n    assert False\n"
GREEN = "def test_green():\n    assert True\n"


def _ratchet(repo, body, rel="tests/test_d_track.py"):
    _write(repo / rel, body)


def _pending_fix(st, iid="F01"):
    it = {"id": iid, "kind": "fix", "title": "set the value", "files": ["pkg/a.py"],
          "change": "- make VALUE fixed", "deps": [], "status": "pending", "attempts": 0,
          "accept": [{"kind": "grep_min", "path": "pkg/a.py", "pattern": "fixed"}]}
    st["items"].append(it)
    return it


def _ledger(st):
    p = os.path.join(st["run"], "results.tsv")
    return _read(p) if os.path.exists(p) else ""


def _record(G, monkeypatch):
    started = []
    monkeypatch.setattr(G, "spawn", lambda s, it: started.append(it["id"]))
    return started


def test_a_red_ratchet_holds_every_fix_and_names_the_failing_test(world, monkeypatch):
    """Fails if a fixer starts while a ratchet is red on the base tree, or the test is not named."""
    G, st, repo, slot = world
    _ratchet(repo, RED)
    _pending_fix(st)
    started = _record(G, monkeypatch)
    G.tick(st, ("fix",), 6)
    assert started == []
    assert G.by_id(st, "F01")["status"] == "pending" and st["sessions"] == 0
    assert st["slots"][0]["busy"] == ""
    assert "tests/test_d_track.py::test_red" in _ledger(st)
    assert "tests/test_d_track.py::test_red" in G.status_line(st)


def test_green_ratchets_let_the_fix_start(world, monkeypatch):
    G, st, repo, slot = world
    _ratchet(repo, GREEN)
    _pending_fix(st)
    started = _record(G, monkeypatch)
    G.tick(st, ("fix",), 6)
    assert started == ["F01"]


def test_scouts_and_referees_still_run_while_fixes_are_held(world, monkeypatch):
    """Fails if a red base holds read-only work too, or lets the fix through."""
    G, st, repo, slot = world
    _ratchet(repo, RED)
    st["items"] = _scouts(1)
    _pending_fix(st)
    started = _record(G, monkeypatch)
    G.tick(st, ("scout", "fix"), 6)
    assert started == ["S01"]


def test_the_ratchets_run_once_per_run_not_once_per_tick(world, monkeypatch):
    """Fails if no preflight runs, or if a green preflight is repeated on every tick."""
    G, st, repo, slot = world
    _ratchet(repo, GREEN)
    _pending_fix(st, "F01")
    _pending_fix(st, "F02")
    calls, real = [], G.rope.sh

    def counting(args, *a, **kw):
        if "pytest" in args:
            calls.append(args)
        return real(args, *a, **kw)
    monkeypatch.setattr(G.rope, "sh", counting)
    _record(G, monkeypatch)
    G.tick(st, ("fix",), 1)
    G.tick(st, ("fix",), 6)
    assert len(calls) == 1
    assert "tests/test_d_track.py" in calls[0]


class _Done:
    def __init__(self, rc, out):
        self.returncode, self.stdout = rc, out


@pytest.mark.parametrize("outcome", ["unparsed", "timeout", "syntax", "none_collected"])
def test_a_red_that_names_no_test_is_still_red(world, monkeypatch, outcome):
    """Fails if a crashed, timed-out or uncollectable ratchet run reads as green."""
    G, st, repo, slot = world
    if outcome == "syntax":
        _ratchet(repo, "def test_broken(:\n")
    else:
        _ratchet(repo, GREEN)
        real = G.rope.sh

        def broken(args, *a, **kw):
            if "pytest" not in args:
                return real(args, *a, **kw)
            if outcome == "timeout":
                raise subprocess.TimeoutExpired(args, 1)
            if outcome == "none_collected":     # the gate's pytest check is rc == 0, so 5 is red there
                return _Done(5, "no tests ran\n")
            return _Done(3, "INTERNALERROR> boom\n")
        monkeypatch.setattr(G.rope, "sh", broken)
    _pending_fix(st)
    started = _record(G, monkeypatch)
    G.tick(st, ("fix",), 6)
    assert started == []
    assert "ratchet" in G.status_line(st).lower()
    if outcome == "syntax":
        assert "tests/test_d_track.py" in _ledger(st)


def test_a_red_hold_ends_a_looping_tick_instead_of_spinning(world, monkeypatch):
    """Fails if `tick --loop` keeps waiting on fix items it will never start."""
    G, st, repo, slot = world
    _ratchet(repo, RED)
    _pending_fix(st)
    G.save(st)
    started = _record(G, monkeypatch)

    def no_sleep(s):
        raise AssertionError("the loop waited on work that can never start")
    monkeypatch.setattr(G.time, "sleep", no_sleep)
    G.cmd_tick(argparse.Namespace(run=st["run"], kinds="fix", parallel=0, loop=1))
    assert started == []


def test_a_new_tick_command_rechecks_a_red_base(world, monkeypatch):
    """Fails if a red verdict outlives the operator repairing the base (a stale ref moves no HEAD)."""
    G, st, repo, slot = world
    _ratchet(repo, RED)
    _pending_fix(st)
    started = _record(G, monkeypatch)
    G.tick(st, ("fix",), 6)
    assert started == []
    G.save(st)
    _ratchet(repo, GREEN)          # the operator repairs the base; HEAD does not move
    G.cmd_tick(argparse.Namespace(run=st["run"], kinds="fix", parallel=0, loop=0))
    assert started == ["F01"]


def test_init_reports_a_red_base_before_any_session(world, monkeypatch, capsys):
    """Fails if `init` records nothing about a red base, so the operator learns only from discards."""
    G, st, repo, slot = world
    _ratchet(repo, RED)
    run = os.path.join(os.path.dirname(st["run"]), "run2")
    a = argparse.Namespace(run=run, slots=os.path.dirname(str(slot)), nslots=1, cap=5, minutes=5,
                           scouts=1, parallel=1, models="", trailer="", live_seat_ok="test")
    monkeypatch.setattr(G, "_houdini_alive", lambda: False)
    G.cmd_init(a)
    with open(os.path.join(run, "GRAPH.json"), encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["preflight"]["ok"] is False
    assert "tests/test_d_track.py::test_red" in saved["preflight"]["failing"]
    assert "tests/test_d_track.py::test_red" in capsys.readouterr().out
