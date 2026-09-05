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


# --- CTO B2 (2026-09-05): SWIG namespace instances --------------------------------
# hou.undos / hou.hipFile / hou.hda (22 siblings on 22.0.400) are NOT classes or
# modules: they are instances of SWIG-generated types defined in `hou`
# (``type(hou.undos).__name__ == 'undos'``, ``__module__ == 'hou'``). The old
# walk recursed only into ``(type, types.ModuleType)``, so the committed table
# carried the bare namespace and none of its members -- scout answered
# exists_in_runtime=False for hou.undos.group while 13 server files call it.

def test_walk_recurses_into_namespace_instances(introspect):
    root = types.ModuleType("A")

    class undos:                          # SWIG-style namespace type owned by the root
        __module__ = "A"

        def group(self, label): ...

        def areEnabled(self): ...

    class Foreign:                        # a type from some OTHER module: leaf only
        __module__ = "elsewhere"

        def member(self): ...

    class EnumValue:                      # hou.EnumValue-style: instances hang off CLASSES, depth 2
        __module__ = "A"
        name = "Chop"

    class nodeTypeFilter:                 # a real class at depth 1 ...
        __module__ = "A"
        Chop = EnumValue()                # ... whose member is a root-typed INSTANCE

    root.undos = undos()
    root.foreign = Foreign()
    root.nodeTypeFilter = nodeTypeFilter
    root.leaf = 3
    out = set()
    introspect._walk(root, "A", 0, introspect.DEPTH_HOU_PDG, set(), out)
    assert "A.undos" in out and "A.undos.group" in out and "A.undos.areEnabled" in out
    assert "A.foreign" in out and "A.foreign.member" not in out   # rule: type owned by the root, not "any object"
    assert "A.nodeTypeFilter.Chop" in out                          # class member recorded as before ...
    assert "A.nodeTypeFilter.Chop.name" not in out                 # ... but enum-value instances are not recursed
    assert "A.leaf" in out


_H22_TABLE = (Path(__file__).resolve().parents[1] / "python" / "synapse" / "cognitive"
              / "tools" / "data" / "h22_symbol_table.json")


def test_committed_h22_table_carries_namespace_members():
    """The committed H22 authority must certify the namespace members the server
    actually calls. Regenerate with hython host/introspect_runtime.py on the
    target build if this fails after a Houdini drop."""
    import hashlib
    import json
    raw = json.loads(_H22_TABLE.read_text(encoding="utf-8"))
    syms = set(raw["symbols"])
    for q in ("hou.undos.group", "hou.undos.areEnabled", "hou.undos.undoLabels",
              "hou.undos.performUndo", "hou.hipFile.save", "hou.hda.definitionsInFile"):
        assert q in syms, f"{q} missing from committed h22 table (namespace walk regressed?)"
    assert raw["truncated"] is False
    assert raw["houdini_version"].startswith("22.")
    digest = hashlib.blake2b("\n".join(sorted(syms)).encode("utf-8"), digest_size=16).hexdigest()
    assert digest == raw["blake2b"]       # the checksum still binds the regenerated table
