"""W5-PARMGATE: the weak-domain COP handlers route parm writes through the gate.

Pins acceptance predicate 2 (handlers route through the gate; the kernelcode/
code hedge is gone) and predicate 3 (a gated set still wraps in exactly one
undo group) at the HANDLER level, complementing the hermetic gate unit tests in
``test_parm_gate.py``.

Two layers:
  * source pins -- the `parm("kernelcode") or parm("code")` phantom hedge is
    deleted from both opencl handlers and replaced by ``gated_set``;
  * one behavioral end-to-end -- ``_handle_cops_reaction_diffusion`` run against
    a recording COP network with the fixture catalog wired authoritative:
    ``kernelcode`` is written through the gate, once, inside the single
    ``synapse_cops_reaction_diffusion`` undo group.
"""

import re
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ── hou / hdefereval bootstrap (must precede the handler import) ────────────
if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.undos = MagicMock()
    sys.modules["hou"] = _hou
if "hdefereval" not in sys.modules:
    _hd = types.ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    _hd.executeDeferred = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hd

import synapse.server.handlers_cops as cops_mod  # noqa: E402
from synapse.validation import catalog as catalog_mod  # noqa: E402

_COPS_SRC = Path(cops_mod.__file__).read_text(encoding="utf-8")
_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "parm_catalog" / "h22.0.400"


# ── Source pins: the phantom hedge is gone, the gate is wired ───────────────

class TestHedgeDeletedAndGateWired:
    def test_reaction_diffusion_code_hedge_is_gone(self):
        assert 'opencl_node.parm("kernelcode") or opencl_node.parm("code")' not in _COPS_SRC

    def test_pixel_sort_code_hedge_is_gone(self):
        assert 'sort_node.parm("kernelcode") or sort_node.parm("code")' not in _COPS_SRC

    def test_no_kernelcode_or_code_hedge_anywhere(self):
        # Any `parm("kernelcode") or ... parm("code")` pattern is the defect.
        assert not re.search(r'parm\("kernelcode"\)\s*or\s+\w+\.parm\("code"\)', _COPS_SRC)

    def test_gate_is_imported(self):
        assert "from ..validation.parm_gate import gated_set" in _COPS_SRC

    def test_both_opencl_handlers_call_the_gate(self):
        assert "gated_set(opencl_node, {\"kernelcode\": kernel_code})" in _COPS_SRC
        assert "gated_set(sort_node, {\"kernelcode\": kernel_code})" in _COPS_SRC


# ── Behavioral: kernelcode written through the gate, in ONE undo group ──────

class _UndoRecorder:
    def __init__(self):
        self.groups = []
        self.depth = 0
        self.mutations = []

    def group(self, name=""):
        return _Group(self, name)

    performUndo = staticmethod(lambda *a, **k: None)


class _Group:
    def __init__(self, rec, name):
        self._rec, self._name = rec, name

    def __enter__(self):
        self._rec.groups.append(self._name)
        self._rec.depth += 1
        return self

    def __exit__(self, *exc):
        self._rec.depth -= 1
        return False


class _RecParm:
    def __init__(self, name, rec):
        self._name, self._rec = name, rec
        self.value = None
        self.set_calls = 0

    def name(self):
        return self._name

    def set(self, value):
        self.value = value
        self.set_calls += 1
        self._rec.mutations.append((self._name, self._rec.depth))


class _RecType:
    def __init__(self, name, category="Cop"):
        self._name, self._cat = name, category

    def name(self):
        return self._name

    def category(self):
        return types.SimpleNamespace(name=lambda: self._cat)


class _RecNode:
    """Permissive recording COP node: any parm name resolves (live surface),
    each set stamps the current undo depth. Type identity is real so the gate
    can look ('Cop', <type>) up in the fixture catalog."""

    def __init__(self, path, type_name, rec, absent=None):
        self._path, self._type, self.rec = path, _RecType(type_name), rec
        self._absent = set(absent or ())
        self.made = {}

    def path(self):
        return self._path

    def name(self):
        return self._path.rsplit("/", 1)[-1]

    def type(self):
        return self._type

    def parm(self, name):
        if name in self._absent:          # a parm the node genuinely lacks
            return None
        if name not in self.made:
            self.made[name] = _RecParm(name, self.rec)
        return self.made[name]

    def parmTuple(self, name):
        return None

    def setInput(self, *a, **k):
        pass

    def moveToGoodPosition(self, *a, **k):
        pass

    def setDisplayFlag(self, *a, **k):
        pass


def _make_network(rec, absent=None):
    net = MagicMock()
    net.path.return_value = "/img/copnet1"
    net.name.return_value = "copnet1"

    def _create(node_type, name=None):
        child_name = name or node_type
        return _RecNode(f"/img/copnet1/{child_name}", node_type, rec, absent=absent)

    net.createNode = MagicMock(side_effect=_create)
    return net


@pytest.fixture
def authoritative_catalog(monkeypatch):
    """Point the process catalog at the committed fixture (opencl is known)."""
    monkeypatch.setenv("SYNAPSE_PARM_CATALOG_ROOT", str(_FIXTURE_DIR))
    catalog_mod.reset_default()
    # sanity: the gate really is authoritative for the opencl COP now
    assert catalog_mod.default_catalog().has_type("Cop", "opencl")
    yield
    catalog_mod.reset_default()


@pytest.fixture
def degraded_catalog(monkeypatch):
    """Force the process catalog to the degraded (no-data) state this branch
    actually ships in, so the permissive safe-set path is exercised."""
    monkeypatch.delenv("SYNAPSE_PARM_CATALOG_ROOT", raising=False)
    monkeypatch.setattr(catalog_mod, "_default_root", lambda: None)
    catalog_mod.reset_default()
    assert catalog_mod.default_catalog().available is False
    yield
    catalog_mod.reset_default()


class TestReactionDiffusionRoutesThroughGate:
    def _run(self, monkeypatch, absent=None):
        rec = _UndoRecorder()
        net = _make_network(rec, absent=absent)
        monkeypatch.setattr(cops_mod.hou, "node", lambda p: net, raising=False)
        monkeypatch.setattr(cops_mod.hou, "undos", rec, raising=False)
        monkeypatch.setattr(cops_mod, "HOU_AVAILABLE", True, raising=False)

        class _Cops(cops_mod.CopsHandlerMixin):
            pass

        result = _Cops()._handle_cops_reaction_diffusion({"parent": "/img/copnet1"})
        return rec, net, result

    def test_kernelcode_written_through_gate_in_one_undo_group(
            self, monkeypatch, authoritative_catalog):
        rec, _net, result = self._run(monkeypatch)
        # the op succeeded and scaffolded a kernel node
        assert result["kernel_node"] == "/img/copnet1/reaction_diffusion_kernel"
        # the gate wrote kernelcode and the handler surfaces that verdict
        assert result["kernel_written"] is True
        assert result["kernel_skipped"] == []
        # exactly one undo group wrapped the whole operation
        assert rec.groups == ["synapse_cops_reaction_diffusion"]
        # kernelcode was written (through the gate) exactly once, INSIDE the group
        kc_mutations = [(n, d) for (n, d) in rec.mutations if n == "kernelcode"]
        assert kc_mutations == [("kernelcode", 1)]

    def test_gate_did_not_open_a_second_group(
            self, monkeypatch, authoritative_catalog):
        rec, _net, _result = self._run(monkeypatch)
        # one and only one group name -> gate added none of its own
        assert len(rec.groups) == 1
        # every mutation happened at depth 1 (inside the single group)
        assert all(d == 1 for _n, d in rec.mutations)
        assert rec.mutations, "expected at least the kernelcode write recorded"

    def test_dropped_kernel_write_is_observable_not_silent(
            self, monkeypatch, degraded_catalog):
        # Criterion 3: when the created node lacks 'kernelcode' (the defensive
        # fallback path), the gate skips the write -- and the handler SURFACES
        # that as kernel_written=False + kernel_skipped, never a silent no-op.
        rec, _net, result = self._run(monkeypatch, absent={"kernelcode"})
        assert result["scaffolded"] is True          # op still succeeds
        assert result["kernel_written"] is False       # but the drop is visible
        assert result["kernel_skipped"] == ["kernelcode"]
        # nothing was written to kernelcode, and no extra undo group appeared
        assert not any(n == "kernelcode" for n, _d in rec.mutations)
        assert rec.groups == ["synapse_cops_reaction_diffusion"]
