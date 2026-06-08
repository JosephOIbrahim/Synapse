"""CRUCIBLE for host/introspect_runtime.py — the bounded dir() walk.

The membership table is built by recursively dir()-walking hou/pdg/pxr. The walk
MUST terminate on USD's large, cyclic binding graph and must not leak dunder /
_private noise. These tests exercise the pure ``_walk`` on synthetic object
graphs (zero ``hou`` — the script imports hou only inside build_table())."""

import importlib.util
import types
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "host" / "introspect_runtime.py"


@pytest.fixture(scope="module")
def introspect():
    spec = importlib.util.spec_from_file_location("introspect_runtime", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)        # safe: no hou at import time
    return mod


def test_walk_terminates_on_cycle(introspect):
    a = types.ModuleType("A")
    b = types.ModuleType("B")
    a.B = b
    b.A = a                              # cycle A -> B -> A
    a.leaf = 1                           # non-module/class leaf: recorded, not recursed
    out = set()
    introspect._walk(a, "A", 0, introspect.DEPTH_HOU_PDG, set(), out)
    # returns at all => no infinite recursion
    assert "A.B" in out and "A.leaf" in out
    assert "A.B.A" in out                # the back-edge is recorded once
    assert all(s.count("A") < 12 for s in out)   # cycle did not unroll forever


def test_walk_skips_dunder_and_private(introspect):
    m = types.ModuleType("M")
    m.public = 1
    m._private = 2
    setattr(m, "__dunder__", 3)
    out = set()
    introspect._walk(m, "M", 0, 1, set(), out)
    assert "M.public" in out
    assert "M._private" not in out and "M.__dunder__" not in out


def test_walk_respects_node_cap(introspect, monkeypatch):
    monkeypatch.setattr(introspect, "NODE_CAP", 5)
    m = types.ModuleType("Big")
    for i in range(100):
        setattr(m, f"attr{i}", i)
    out = set()
    introspect._walk(m, "Big", 0, 1, set(), out)
    assert len(out) <= 5                 # hard cap honored — no unbounded growth


def test_data_path_targets_package(introspect):
    p = introspect._data_path()
    assert p.name == "h21_symbol_table.json"
    assert p.parts[-4:] == ("cognitive", "tools", "data", "h21_symbol_table.json")
