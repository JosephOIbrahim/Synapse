"""Relationship-aware get/set_usd_attribute (W.5-H22-karmarels, SB-4).

N-3 (docs/reviews/h22-now-probes-2026-07-16.md) proved that on H22.0.368 a
set of karma/husk + stock UsdRender/UsdLux properties are USD **relationships**,
not attributes -- ``camera``, ``products``, ``orderedVars``,
``husk:orderedImageFilters``, ``light:filters``, the ``collection:*``
includes/excludes, ``proxyPrim``. For every one of them
``prim.GetAttribute(name).IsValid()`` is ``False`` even with a populated
target, so the old handlers:

  * READ path raised ``ValueError`` ("didn't match") and the hint could never
    name the relationship the caller asked for; and
  * WRITE path silently no-op'd (``if attr:`` is falsy for an invalid attr, so
    the generated pythonscript authored nothing while the handler reported the
    node created).

This pins the fix: the read path falls back to ``GetRelationship`` (returning
targets as a path-string list with an additive ``property_kind`` field), the
write path authors via ``SetTargets``/``CreateRelationship``, and the
miss-both hint lists relationships too. Every prior *attribute* behavior is
preserved byte-for-byte.

Headless + hermetic. Handler-module globals are patched directly (sys.modules
residency is order-fragile -- docs/HARDENING_RUN_2026-06-10.md Mile 3). The
write-path authoring logic is genuinely exercised by exec-ing the emitted
pythonscript against a stubbed prim + a fake ``pxr.Sdf``.
"""

import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: hython-safe (never plants when real hou is resident -- conftest
# convention). Enrich the resident fake so sibling handler modules keep working.
# ---------------------------------------------------------------------------
if "hou" not in sys.modules:
    sys.modules["hou"] = ModuleType("hou")
_h = sys.modules["hou"]
for _attr in ("undos", "node", "ui"):
    if not hasattr(_h, _attr):
        setattr(_h, _attr, MagicMock())
if not hasattr(_h, "OperationFailed"):
    _h.OperationFailed = type("OperationFailed", (Exception,), {})
if "hdefereval" not in sys.modules:
    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hd

from synapse.server.handlers import SynapseHandler  # noqa: E402
from synapse.server import handlers_usd as husd  # noqa: E402


# ---------------------------------------------------------------------------
# Read-path stubs (prim exposes GetAttribute/GetRelationship on node.stage()).
# The read path calls attr.IsValid()/rel.IsValid() explicitly.
# ---------------------------------------------------------------------------


class _Attr:
    def __init__(self, valid, value=None, type_name="float"):
        self._valid, self._value, self._tn = valid, value, type_name

    def IsValid(self):
        return self._valid

    def Get(self):
        return self._value

    def GetTypeName(self):
        return self._tn


class _Rel:
    def __init__(self, valid, targets=()):
        self._valid, self._targets = valid, list(targets)

    def IsValid(self):
        return self._valid

    def GetTargets(self):
        return list(self._targets)


class _Named:
    def __init__(self, name):
        self._name = name

    def GetName(self):
        return self._name


class _Prim:
    def __init__(self, attr, rel, attrs=(), rels=()):
        self._attr, self._rel = attr, rel
        self._attrs, self._rels = attrs, rels

    def IsValid(self):
        return True

    def GetAttribute(self, name):
        return self._attr

    def GetRelationship(self, name):
        return self._rel

    def GetAttributes(self):
        return [_Named(a) for a in self._attrs]

    def GetRelationships(self):
        return [_Named(r) for r in self._rels]


def _handler_reading(monkeypatch, prim):
    """A SynapseHandler whose resolved LOP exposes `prim` on its stage."""
    mt = importlib.import_module("synapse.server.main_thread")
    monkeypatch.setattr(mt, "run_on_main", lambda fn, timeout=None: fn())
    stage = SimpleNamespace(GetPrimAtPath=lambda p: prim)
    lop = SimpleNamespace(stage=lambda: stage, path=lambda: "/stage/krs")
    monkeypatch.setattr(
        SynapseHandler, "_resolve_lop_node", lambda self, p: lop, raising=False
    )
    return SynapseHandler()


# ---- READ: attribute hit is unchanged (plus additive property_kind) --------


def test_get_attribute_hit_unchanged(monkeypatch):
    prim = _Prim(_Attr(True, value=5.0, type_name="float"), _Rel(False))
    handler = _handler_reading(monkeypatch, prim)
    res = handler._handle_get_usd_attribute(
        {"prim_path": "/lights/key", "usd_attribute": "inputs:exposure"}
    )
    assert res["value"] == 5.0
    assert res["type_name"] == "float"
    assert res["attribute"] == "inputs:exposure"
    assert res["prim_path"] == "/lights/key"
    assert res["node"] == "/stage/krs"
    assert res["property_kind"] == "attribute"


# ---- READ: relationship fallback -------------------------------------------


def test_get_relationship_fallback_read(monkeypatch):
    prim = _Prim(_Attr(False), _Rel(True, targets=["/blocker", "/blocker2"]))
    handler = _handler_reading(monkeypatch, prim)
    res = handler._handle_get_usd_attribute(
        {"prim_path": "/lights/key", "usd_attribute": "light:filters"}
    )
    assert res["value"] == ["/blocker", "/blocker2"]
    assert res["type_name"] == "relationship"
    assert res["property_kind"] == "relationship"
    assert res["attribute"] == "light:filters"


def test_get_relationship_targets_are_path_strings(monkeypatch):
    # GetTargets yields Sdf.Path objects live; the handler must str() them.
    class _SdfPathLike:
        def __init__(self, s):
            self._s = s

        def __str__(self):
            return self._s

    prim = _Prim(_Attr(False), _Rel(True, targets=[_SdfPathLike("/blocker")]))
    handler = _handler_reading(monkeypatch, prim)
    res = handler._handle_get_usd_attribute(
        {"prim_path": "/lights/key", "usd_attribute": "light:filters"}
    )
    assert res["value"] == ["/blocker"]
    assert all(isinstance(v, str) for v in res["value"])


# ---- READ: miss both -> ValueError matching the current error envelope ------


def test_get_miss_both_raises_with_relationship_hint(monkeypatch):
    prim = _Prim(
        _Attr(False), _Rel(False),
        attrs=["inputs:intensity", "inputs:exposure"],
        rels=["light:filters", "collection:lightLink:includes"],
    )
    handler = _handler_reading(monkeypatch, prim)
    with pytest.raises(ValueError) as ei:
        handler._handle_get_usd_attribute(
            {"prim_path": "/lights/key", "usd_attribute": "nope"}
        )
    msg = str(ei.value)
    # Same envelope shape: names the property, names the prim, lists available.
    assert "('nope')" in msg
    assert "/lights/key" in msg
    assert "Available attributes:" in msg and "inputs:intensity" in msg
    # New: the hint can now name relationships (the N-3 fix).
    assert "Available relationships:" in msg and "light:filters" in msg


def test_get_miss_both_no_relationships_omits_that_clause(monkeypatch):
    prim = _Prim(_Attr(False), _Rel(False), attrs=["inputs:intensity"], rels=[])
    handler = _handler_reading(monkeypatch, prim)
    with pytest.raises(ValueError) as ei:
        handler._handle_get_usd_attribute(
            {"prim_path": "/lights/key", "usd_attribute": "nope"}
        )
    assert "Available relationships:" not in str(ei.value)


# ---- READ: golden envelope key lists ---------------------------------------


def test_get_golden_envelope_keys(monkeypatch):
    attr_prim = _Prim(_Attr(True, value=1.0), _Rel(False))
    rel_prim = _Prim(_Attr(False), _Rel(True, targets=["/blocker"]))
    ha = _handler_reading(monkeypatch, attr_prim)
    attr_res = ha._handle_get_usd_attribute(
        {"prim_path": "/p", "usd_attribute": "inputs:exposure"}
    )
    hr = _handler_reading(monkeypatch, rel_prim)
    rel_res = hr._handle_get_usd_attribute(
        {"prim_path": "/p", "usd_attribute": "light:filters"}
    )
    golden = {"node", "prim_path", "attribute", "value", "type_name", "property_kind"}
    assert set(attr_res) == golden
    assert set(rel_res) == golden


# ---------------------------------------------------------------------------
# Write-path: the handler emits a pythonscript LOP. Capture the emitted code,
# assert the relationship fallback is present, then exec it against a stubbed
# prim to prove the authoring logic (SetTargets/CreateRelationship) is correct.
# ---------------------------------------------------------------------------


class _FakeOperationFailed(Exception):
    pass


class _UndoGroup:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _CapturingParm:
    def __init__(self, store):
        self._store = store

    def set(self, v):
        self._store["code"] = v


@pytest.fixture()
def writing(monkeypatch):
    """(handler, code_store) -- drive _handle_set_usd_attribute, capture code."""
    fake_hou = SimpleNamespace(
        undos=SimpleNamespace(group=lambda label: _UndoGroup()),
        OperationFailed=_FakeOperationFailed,
    )
    monkeypatch.setattr(husd, "hou", fake_hou)
    monkeypatch.setattr(husd, "HOU_AVAILABLE", True, raising=False)
    monkeypatch.setattr(husd, "_wire_display", lambda *a, **k: {})
    mt = importlib.import_module("synapse.server.main_thread")
    monkeypatch.setattr(mt, "run_on_main", lambda fn, timeout=None: fn())

    store = {}
    py_lop = MagicMock(name="py_lop")
    py_lop.path.return_value = "/stage/set_attr"
    py_lop.parm.return_value = _CapturingParm(store)
    parent = MagicMock()
    parent.createNode.return_value = py_lop
    lop = MagicMock()
    lop.parent.return_value = parent
    monkeypatch.setattr(
        SynapseHandler, "_resolve_lop_node", lambda self, p: lop, raising=False
    )
    return SynapseHandler(), store


def _emit(handler, store, *, attr_name, value):
    handler._handle_set_usd_attribute(
        {"prim_path": "/lights/key", "usd_attribute": attr_name, "value": value}
    )
    return store["code"]


# ---- Emitted-code shape -----------------------------------------------------


def test_set_emits_relationship_fallback_but_keeps_attribute_branch(writing):
    handler, store = writing
    code = _emit(handler, store, attr_name="light:filters", value=["/blocker"])
    # Attribute branch preserved byte-for-byte.
    assert "attr = prim.GetAttribute('light:filters')" in code
    assert "    if attr:\n        attr.Set(['/blocker'])" in code
    # Relationship fallback added.
    assert "rel = prim.GetRelationship('light:filters')" in code
    assert "rel.SetTargets(" in code
    assert "prim.CreateRelationship('light:filters')" in code


# ---- Exec the emitted code against a stubbed prim + fake pxr.Sdf ------------


class _ExAttr:
    def __init__(self, valid):
        self.valid, self.set_calls = valid, []

    def __bool__(self):
        return self.valid

    def Set(self, v):
        self.set_calls.append(v)


class _ExRel:
    def __init__(self, valid):
        self.valid, self.targets = valid, None

    def __bool__(self):
        return self.valid

    def SetTargets(self, t):
        self.targets = list(t)


class _ExPrim:
    def __init__(self, attr, rel, created=None):
        self._attr, self._rel, self._created = attr, rel, created
        self.create_calls = []

    def __bool__(self):
        return True

    def GetAttribute(self, n):
        return self._attr

    def GetRelationship(self, n):
        return self._rel

    def CreateRelationship(self, n):
        self.create_calls.append(n)
        return self._created


def _run_emitted(monkeypatch, code, prim):
    fake_pxr = ModuleType("pxr")
    fake_pxr.Sdf = SimpleNamespace(Path=lambda p: p)
    monkeypatch.setitem(sys.modules, "pxr", fake_pxr)
    stage = SimpleNamespace(GetPrimAtPath=lambda p: prim)
    pwd = SimpleNamespace(editableStage=lambda: stage)
    fake_hou = SimpleNamespace(pwd=lambda: pwd)
    exec(compile(code, "<emitted-set_usd_attribute>", "exec"), {"hou": fake_hou})


def test_exec_valid_attribute_sets_attr_only(writing, monkeypatch):
    handler, store = writing
    code = _emit(handler, store, attr_name="inputs:exposure", value=5.0)
    attr, rel = _ExAttr(True), _ExRel(True)
    _run_emitted(monkeypatch, code, _ExPrim(attr, rel))
    assert attr.set_calls == [5.0]          # attribute authored, unchanged
    assert rel.targets is None              # relationship untouched


def test_exec_relationship_targets_written(writing, monkeypatch):
    handler, store = writing
    code = _emit(handler, store, attr_name="light:filters", value=["/blocker"])
    attr, rel = _ExAttr(False), _ExRel(True)   # invalid attr, existing rel
    prim = _ExPrim(attr, rel)
    _run_emitted(monkeypatch, code, prim)
    assert rel.targets == ["/blocker"]
    assert prim.create_calls == []             # existing rel -> no create
    assert attr.set_calls == []


def test_exec_scalar_on_unknown_name_stays_noop(writing, monkeypatch):
    handler, store = writing
    code = _emit(handler, store, attr_name="nope", value=5.0)
    attr, rel = _ExAttr(False), _ExRel(False)  # neither attr nor rel
    prim = _ExPrim(attr, rel)
    _run_emitted(monkeypatch, code, prim)
    # Preserve the pre-fix behavior: a scalar set on an unknown name no-ops.
    assert attr.set_calls == []
    assert rel.targets is None
    assert prim.create_calls == []


def test_exec_pathlist_on_missing_rel_creates_relationship(writing, monkeypatch):
    handler, store = writing
    code = _emit(handler, store, attr_name="light:filters", value=["/blocker"])
    attr, absent_rel = _ExAttr(False), _ExRel(False)
    created = _ExRel(True)
    prim = _ExPrim(attr, absent_rel, created=created)
    _run_emitted(monkeypatch, code, prim)
    assert prim.create_calls == ["light:filters"]
    assert created.targets == ["/blocker"]


def test_exec_pathlist_requires_rooted_paths(writing, monkeypatch):
    # A list that is NOT prim paths must not spawn a relationship.
    handler, store = writing
    code = _emit(handler, store, attr_name="whatever", value=["not", "paths"])
    attr, absent_rel = _ExAttr(False), _ExRel(False)
    prim = _ExPrim(attr, absent_rel, created=_ExRel(True))
    _run_emitted(monkeypatch, code, prim)
    assert prim.create_calls == []


# ---- WRITE golden envelope keys (unchanged from pre-fix) --------------------


def test_set_golden_envelope_keys(writing):
    handler, store = writing
    res = handler._handle_set_usd_attribute(
        {"prim_path": "/p", "usd_attribute": "inputs:exposure", "value": 5.0}
    )
    # _wire_display patched to {}; scalar value -> no advisory.
    assert set(res) == {"created_node", "prim_path", "attribute", "value"}
