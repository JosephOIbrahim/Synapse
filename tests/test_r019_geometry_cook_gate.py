"""R-019 (OBSERVER-3) — geometry reads never force a cook, are bounded, and
their timeout names the payload still running.

The mandatory negative control mirrors ``tests/test_cache_no_forced_cook.py``:
a fake dirty SOP reports ``needsToCook()`` True and a ``geometry()`` tripwire;
the introspection geometry reader must complete WITHOUT touching geometry()
and return ``observation_status: dirty_not_forced``.

The rest pins the other half of the predicate: counts read through
``hou.Geometry.intrinsicValue`` instead of materialising the element tuples,
the primitive census is CAPPED with an explicit ``dropped`` stamp, the walk is
wrapped in ``long_operation`` (cancellable, not a silent freeze), the marshal
carries the canonical ``inspect_node``/``inspect_selection`` budget, and an
over-budget read raises a timeout that names the still-running payload.

Pure Python — no hou, no hython, no network.
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from synapse.server import introspection


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _GeometryTripwire(AssertionError):
    """Distinct type so a forced-cook failure can never be confused with an
    unrelated assertion raised elsewhere in the call."""


class _FakeCategory:
    def name(self):
        return "Sop"


class _FakeNodeType:
    def name(self):
        return "null"

    def category(self):
        return _FakeCategory()


class DirtySopNode:
    """needsToCook() True; geometry() would force the exact cook being avoided."""

    def __init__(self, path="/obj/geo1/expensive_solver1"):
        self._path = path
        self.geometry_call_count = 0
        self.cook_count = 42

    def path(self):
        return self._path

    def name(self):
        return self._path.rsplit("/", 1)[-1]

    def needsToCook(self):
        return True

    def cookCount(self):
        return self.cook_count

    def geometry(self):
        self.geometry_call_count += 1
        self.cook_count += 1  # a forced cook is exactly what would move this
        raise _GeometryTripwire(
            "geometry() was called on a dirty node -- the read forced the cook "
            "this observation exists to avoid"
        )

    # Remaining members inspect_node_detail touches. Everything the fake does
    # not implement (childTypeCategory, isDisplayFlagSet, type().definition)
    # is guarded by the production read helpers.
    def type(self):
        return _FakeNodeType()

    def sessionId(self):
        return 7

    def parent(self):
        return None

    def parms(self):
        return []

    def inputs(self):
        return ()

    def inputConnections(self):
        return ()

    def outputConnections(self):
        return ()

    def warnings(self):
        return []

    def errors(self):
        return []


class UnknownDirtyNode(DirtySopNode):
    """needsToCook() itself fails: neither branch is a green light to guess."""

    def needsToCook(self):
        raise RuntimeError("simulated hou query failure")


class _FakePrimType:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _FakePrim:
    def __init__(self, name):
        self._type = _FakePrimType(name)

    def type(self):
        return self._type


class IntrinsicGeometry:
    """Counts are O(1) intrinsics; points()/prims() are tripwires.

    If the reader falls back to materialising the element tuples, the tripwire
    raises inside the guarded fallback and the count comes back None — the
    assertions on the count then fail, which is the point.
    """

    def __init__(self, points, prims, prim_names=()):
        self._counts = {"pointcount": points, "primitivecount": prims}
        self._prim_names = list(prim_names)
        self.points_calls = 0
        self.prims_calls = 0

    def intrinsicValue(self, name):
        return self._counts[name]

    def points(self):
        self.points_calls += 1
        raise _GeometryTripwire("points() materialised the full point tuple")

    def prims(self):
        self.prims_calls += 1
        raise _GeometryTripwire("prims() materialised the full prim tuple")

    def iterPrims(self):
        return iter(_FakePrim(name) for name in self._prim_names)

    def vertices(self):
        return []

    def pointAttribs(self):
        return []

    def primAttribs(self):
        return []

    def globalAttribs(self):
        return []

    def boundingBox(self):
        return None


class CleanSopNode:
    """needsToCook() False — reading the cached geometry is safe and expected."""

    def __init__(self, geometry, path="/obj/geo1/static_box1"):
        self._path = path
        self._geometry = geometry
        self.geometry_call_count = 0

    def path(self):
        return self._path

    def needsToCook(self):
        return False

    def geometry(self):
        self.geometry_call_count += 1
        return self._geometry


# ---------------------------------------------------------------------------
# The mandatory negative control (mirrors tests/test_cache_no_forced_cook.py)
# ---------------------------------------------------------------------------

def test_dirty_node_never_reads_geometry_and_reports_dirty_not_forced():
    node = DirtySopNode()
    before = node.cookCount()

    result = introspection._geometry_summary(node)

    assert node.geometry_call_count == 0, (
        "geometry() was called on a dirty node -- the mandatory negative control failed"
    )
    assert node.cookCount() == before, "the observation must not force a cook"
    assert result["observation_status"] == "dirty_not_forced"
    assert result["geometry_read"] is False
    assert result["needs_to_cook"] is True


def test_include_geometry_true_through_inspect_node_detail_leaves_cookcount_unchanged(monkeypatch):
    node = DirtySopNode()
    monkeypatch.setattr(
        introspection, "hou",
        type("FakeHou", (), {"node": staticmethod(
            lambda path: node if path == node.path() else None)}),
    )
    before = node.cookCount()

    info = introspection.inspect_node_detail(node.path(), include_geometry=True)

    assert info["geometry"]["observation_status"] == "dirty_not_forced"
    assert node.geometry_call_count == 0
    assert node.cookCount() == before


def test_include_geometry_true_through_inspect_selection_never_forces_the_cook(monkeypatch):
    node = DirtySopNode()
    fake_hou = SimpleNamespace(
        selectedNodes=lambda: [node],
        hipFile=SimpleNamespace(path=lambda: "/show/a.hip"),
        applicationVersionString=lambda: "22.0.400",
        node=lambda path: node if path == node.path() else None,
    )
    monkeypatch.setattr(introspection, "hou", fake_hou)
    before = node.cookCount()

    result = introspection.inspect_selection(include_geometry=True)

    geometry = result["nodes"][0]["geometry"]
    assert geometry["observation_status"] == "dirty_not_forced"
    assert node.geometry_call_count == 0
    assert node.cookCount() == before


def test_unknown_dirty_state_never_reads_geometry_either():
    node = UnknownDirtyNode()

    result = introspection._geometry_summary(node)

    assert node.geometry_call_count == 0, (
        "a failed needsToCook() query must never default to the permissive branch"
    )
    assert result["observation_status"] == "dirty_unknown"
    assert result["needs_to_cook"] is None


def test_clean_node_contrast_still_reads_geometry():
    geo = IntrinsicGeometry(100, 50, ["Polygon"] * 3)
    node = CleanSopNode(geo)

    result = introspection._geometry_summary(node)

    assert node.geometry_call_count == 1
    assert "observation_status" not in result
    assert result["points"] == 100
    assert result["prims"] == 50


# ---------------------------------------------------------------------------
# Counts come from intrinsics, never from materialised element tuples
# ---------------------------------------------------------------------------

def test_counts_come_from_intrinsic_values_not_element_tuples():
    geo = IntrinsicGeometry(2_000_000, 4_000_000, ["Polygon"] * 2)

    result = introspection._geometry_summary(CleanSopNode(geo))

    assert result["points"] == 2_000_000
    assert result["prims"] == 4_000_000
    assert geo.points_calls == 0, "the point tuple was materialised for a count"
    assert geo.prims_calls == 0, "the prim tuple was materialised for a count"
    assert result["large_geometry"] is True


# ---------------------------------------------------------------------------
# The primitive census is capped, with an honest dropped stamp
# ---------------------------------------------------------------------------

def test_prim_census_is_capped_with_a_dropped_stamp(monkeypatch):
    monkeypatch.setattr(introspection, "_PRIM_CENSUS_CAP", 5)
    monkeypatch.setattr(introspection, "_CENSUS_PROGRESS_EVERY", 2)
    geo = IntrinsicGeometry(0, 8, ["Polygon"] * 8)

    result = introspection._geometry_summary(CleanSopNode(geo))

    census = result["primitive_types_census"]
    assert census["examined"] == 5
    assert census["dropped"] == 3, "a partial census must say how much it omitted"
    assert census["ceiling"] == 5
    assert result["primitive_types"] == {"Polygon": 5}


def test_complete_census_reports_a_measured_zero_dropped():
    geo = IntrinsicGeometry(3, 2, ["Polygon", "Polygon"])

    result = introspection._geometry_summary(CleanSopNode(geo))

    census = result["primitive_types_census"]
    assert census["examined"] == 2
    assert census["dropped"] == 0, "a fully walked census dropped nothing"


def test_census_with_an_unknown_count_never_fabricates_a_dropped_number():
    geo = IntrinsicGeometry(3, 2, ["Polygon", "Polygon"])
    geo._counts["primitivecount"] = None  # intrinsic unavailable...
    geo.prims = lambda: (_ for _ in ()).throw(_GeometryTripwire("no prim tuple"))

    result = introspection._geometry_summary(CleanSopNode(geo))

    census = result["primitive_types_census"]
    assert census["dropped"] is None, "an unknown denominator stays unknown"


# ---------------------------------------------------------------------------
# The whole geometry walk is a long_operation (progress + Cancel)
# ---------------------------------------------------------------------------

def test_geometry_walk_is_wrapped_in_long_operation(monkeypatch):
    long_op_module = importlib.import_module("synapse.server.long_operation")
    entered = []

    class _Recorder:
        def __init__(self, title):
            self.title = title

        def __enter__(self):
            entered.append(self.title)
            return self

        def __exit__(self, *_exc):
            return False

        def step(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(long_op_module, "long_operation", _Recorder)
    geo = IntrinsicGeometry(3, 2, ["Polygon", "Polygon"])
    node = CleanSopNode(geo)

    introspection._geometry_summary(node)

    assert entered == ["SYNAPSE: reading geometry of %s" % node.path()], (
        "the geometry walk must open one legible, cancellable operation"
    )


# ---------------------------------------------------------------------------
# Marshal budget + a timeout that names the still-running payload
# ---------------------------------------------------------------------------

def _patched_handlers(monkeypatch):
    from synapse.server import handlers as handlers_mod
    from synapse.server import introspection as introspection_mod
    from synapse.server import main_thread as main_thread_mod

    monkeypatch.setattr(handlers_mod, "HOU_AVAILABLE", True)
    monkeypatch.setattr(introspection_mod, "inspect_node_detail",
                        lambda **kwargs: {"ok": True, "kwargs": kwargs})
    monkeypatch.setattr(introspection_mod, "inspect_selection",
                        lambda **kwargs: {"ok": True, "kwargs": kwargs})
    return handlers_mod, main_thread_mod


def _new_handler(handlers_mod):
    return handlers_mod.SynapseHandler.__new__(handlers_mod.SynapseHandler)


def test_inspect_node_marshal_uses_the_inspect_node_budget(monkeypatch):
    from synapse.core.timeouts import timeout_for

    handlers_mod, main_thread_mod = _patched_handlers(monkeypatch)
    captured = {}

    def runner(fn, *, timeout, label):
        captured["timeout"], captured["label"] = timeout, label
        return fn()

    monkeypatch.setattr(main_thread_mod, "run_on_main", runner)

    _new_handler(handlers_mod)._handle_inspect_node(
        {"node": "/obj/geo1", "include_geometry": True})

    assert captured["timeout"] == timeout_for("inspect_node") == 30.0
    assert captured["label"] == "handlers:_handle_inspect_node"


def test_inspect_selection_marshal_uses_the_inspect_selection_budget(monkeypatch):
    from synapse.core.timeouts import timeout_for

    handlers_mod, main_thread_mod = _patched_handlers(monkeypatch)
    captured = {}

    def runner(fn, *, timeout, label):
        captured["timeout"], captured["label"] = timeout, label
        return fn()

    monkeypatch.setattr(main_thread_mod, "run_on_main", runner)

    _new_handler(handlers_mod)._handle_inspect_selection(
        {"include_geometry": True})

    assert captured["timeout"] == timeout_for("inspect_selection") == 30.0
    assert captured["label"] == "handlers:_handle_inspect_selection"


def test_an_over_budget_geometry_read_names_the_still_running_payload(monkeypatch):
    from synapse.server.main_thread import MainThreadTimeout

    handlers_mod, main_thread_mod = _patched_handlers(monkeypatch)
    stock = MainThreadTimeout(
        "Houdini's main thread didn't respond in time -- it may be busy cooking "
        "or rendering. The call may still be running; check the scene before "
        "trying again."
    )

    def runner(fn, *, timeout, label):
        raise stock

    monkeypatch.setattr(main_thread_mod, "run_on_main", runner)

    with pytest.raises(MainThreadTimeout) as caught:
        _new_handler(handlers_mod)._handle_inspect_node(
            {"node": "/obj/geo1/very_heavy_sop", "include_geometry": True})

    message = str(caught.value)
    assert caught.value is not stock, "the stock message names no payload"
    assert "inspect_node" in message
    assert "/obj/geo1/very_heavy_sop" in message
    assert "include_geometry=True" in message
    assert "still running" in message
    assert "30.0" in message
